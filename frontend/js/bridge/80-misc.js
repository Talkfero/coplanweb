<script>
// ============================================================
// coplanColFilters v2 (2026-05-12): filtros Excel-style por coluna
//
// V1 (commit 83f65f9) congelava ao abrir -- provavelmente combinacao
// de MutationObserver no thead + lucide.createIcons + double-render
// via wrappers em coplanLoadObras/coplanApplySearch.
//
// V2 evita tudo isso:
//   - SEM MutationObserver. Funis sao injetados em coplan:obras
//     (evento ja disparado por coplanRenderObras existente).
//   - SEM lucide.createIcons (mutacoes encadeadas). SVG inline.
//   - SEM wrapper em coplanLoadObras/coplanApplySearch. Em vez disso:
//     wrap apenas coplanRenderObras com version-counter; load/search
//     incrementam a versao indiretamente quando setam coplanObrasRaw
//     (detectado por compara de referencia).
//   - Feature flag window.coplanColFiltersEnabled (default true). Se
//     algo der errado em produc'ao, basta setar pra false no console.
// ============================================================
(function () {
  if (window.__coplanColFiltersIIFE) return;
  window.__coplanColFiltersIIFE = true;

  if (window.coplanColFiltersEnabled === undefined) {
    window.coplanColFiltersEnabled = true;
  }
  function enabled() { return !!window.coplanColFiltersEnabled; }

  // ----- estado -----
  window.coplanColumnFilters = {}; // col -> {values:Set<UPPER>, includeBlank}
  window.coplanCriteriosFilter = ''; // segmented Criterios state
  var snapshotKey = null; // ref do coplanObrasRaw na ultima snapshot

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function humanize(c) {
    return String(c || '').replace(/_/g, ' ').split(' ').map(function (w) {
      return w ? w.charAt(0).toUpperCase() + w.slice(1) : '';
    }).join(' ');
  }
  function hasAnyColFilter() {
    var cf = window.coplanColumnFilters || {};
    for (var k in cf) {
      if (!Object.prototype.hasOwnProperty.call(cf, k)) continue;
      var f = cf[k]; if (!f) continue;
      if ((f.values && f.values.size) || f.includeBlank) return true;
    }
    return false;
  }
  function colIdx(col) {
    var cols = window.coplanObrasColumns || [];
    return cols.indexOf(col);
  }
  function distinctFromRawAll(col) {
    var raw = window.coplanObrasRawAll || window.coplanObrasRaw || [];
    var idx = colIdx(col);
    if (idx < 0 || !raw.length) return { values: [], hasBlank: false };
    var seen = {}, out = [], hasBlank = false;
    for (var i = 0; i < raw.length; i++) {
      var v = raw[i] ? raw[i][idx] : null;
      var s = (v == null) ? '' : String(v).trim();
      if (!s) { hasBlank = true; continue; }
      var k = s.toUpperCase();
      if (!seen[k]) { seen[k] = true; out.push(s); }
    }
    out.sort(function (a, b) {
      var na = parseFloat(a), nb = parseFloat(b);
      if (!isNaN(na) && !isNaN(nb)) return na - nb;
      return a.localeCompare(b, 'pt-BR', { sensitivity: 'base' });
    });
    return { values: out, hasBlank: hasBlank };
  }

  // ----- snapshot + apply -----
  function snapshotIfStale() {
    var cur = window.coplanObrasRaw || [];
    if (cur === snapshotKey) return;
    window.coplanObrasRawAll = cur.slice();
    window.coplanObrasAll = (window.coplanObras || []).slice();
    window.coplanObrasPassouAll = (window.coplanObrasPassou || []).slice();
    snapshotKey = cur;
  }
  function applyColumnFilters() {
    var rawAll = window.coplanObrasRawAll || [];
    var curAll = window.coplanObrasAll || [];
    var passAll = window.coplanObrasPassouAll || [];
    if (!enabled() || !hasAnyColFilter()) {
      // Sem filtro: caches espelham *All. Atualiza snapshotKey para
      // evitar re-snapshot espurio.
      window.coplanObrasRaw = rawAll;
      window.coplanObras = curAll;
      window.coplanObrasPassou = passAll;
      snapshotKey = rawAll;
      return;
    }
    var cf = window.coplanColumnFilters;
    var idxMap = {};
    for (var c in cf) {
      if (Object.prototype.hasOwnProperty.call(cf, c)) {
        idxMap[c] = colIdx(c);
      }
    }
    var rawOut = [], curOut = [], passOut = [];
    for (var i = 0; i < rawAll.length; i++) {
      var r = rawAll[i];
      var keep = true;
      for (var col in cf) {
        var spec = cf[col]; if (!spec) continue;
        var hasVals = spec.values && spec.values.size;
        if (!hasVals && !spec.includeBlank) continue;
        var ci = idxMap[col];
        var v = (ci >= 0 && r) ? r[ci] : null;
        var s = (v == null) ? '' : String(v).trim();
        if (!s) {
          if (!spec.includeBlank) { keep = false; break; }
        } else {
          var u = s.toUpperCase();
          if (!(spec.values && spec.values.has(u))) {
            keep = false; break;
          }
        }
      }
      if (keep) {
        rawOut.push(r);
        if (i < curAll.length) curOut.push(curAll[i]);
        if (i < passAll.length) passOut.push(passAll[i]);
      }
    }
    window.coplanObrasRaw = rawOut;
    window.coplanObras = curOut;
    window.coplanObrasPassou = passOut;
    snapshotKey = rawOut;
  }

  // ----- wrap APENAS coplanRenderObras (pagination ja wrappou) -----
  function wrapRender() {
    if (typeof window.coplanRenderObras !== 'function') return;
    if (window.coplanRenderObras.__coplanCfV2Wrapped) return;
    var orig = window.coplanRenderObras;
    var wrapped = function () {
      if (!enabled()) return orig.apply(this, arguments);
      try {
        snapshotIfStale();
        applyColumnFilters();
      } catch (e) {
        console.warn('[coplan colFilters] snapshot/apply erro:', e);
      }
      return orig.apply(this, arguments);
    };
    wrapped.__coplanCfV2Wrapped = true;
    window.coplanRenderObras = wrapped;
  }

  function triggerReRender() {
    if (typeof window.coplanRenderObras === 'function') {
      try { window.coplanRenderObras(); } catch (e) {
        console.warn('[coplan colFilters] re-render erro:', e);
      }
    }
    renderChips();
  }

  // ----- coplanFilteredCods estendido -----
  function patchFilteredCods() {
    if (typeof window.coplanFilteredCods !== 'function') return;
    if (window.coplanFilteredCods.__coplanCfV2Patched) return;
    var origFc = window.coplanFilteredCods;
    var p = function () {
      var r = origFc.apply(this, arguments);
      if (r !== null) return r;
      if (!enabled() || !hasAnyColFilter()) return null;
      var rows = window.coplanObras || [];
      var out = [];
      for (var i = 0; i < rows.length; i++) {
        var c = rows[i] && rows[i].cod;
        if (c) out.push(String(c));
      }
      return out;
    };
    p.__coplanCfV2Patched = true;
    window.coplanFilteredCods = p;
  }

  // ----- icone funil (SVG inline, sem lucide) -----
  function funnelSvg(active) {
    var stroke = active ? 'var(--accent, #2563eb)' : 'currentColor';
    return '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" '
      + 'stroke="' + stroke + '" stroke-width="2.2" stroke-linecap="round" '
      + 'stroke-linejoin="round" style="display:block;">'
      + '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3">'
      + '</polygon></svg>';
  }

  // ----- injeta funis (chamado em coplan:obras, ja apos render) -----
  function ensureFunnels() {
    if (!enabled()) return;
    var thead = document.querySelector('#obras-table thead tr');
    if (!thead) return;
    var ths = thead.querySelectorAll('th[data-col]');
    for (var i = 0; i < ths.length; i++) {
      var th = ths[i];
      var col = th.getAttribute('data-col');
      if (!col) continue;
      var existing = th.querySelector('.coplan-cf-btn');
      var active = !!window.coplanColumnFilters[col]
        && ((window.coplanColumnFilters[col].values
              && window.coplanColumnFilters[col].values.size > 0)
            || !!window.coplanColumnFilters[col].includeBlank);
      if (existing) {
        // Sincroniza estado visual mas nao recria.
        existing.setAttribute('data-active', active ? '1' : '0');
        existing.innerHTML = funnelSvg(active);
        existing.style.opacity = active ? '1' : '.55';
        continue;
      }
      var btn = document.createElement('span');
      btn.className = 'coplan-cf-btn';
      btn.title = 'Filtrar coluna';
      btn.setAttribute('data-col', col);
      btn.setAttribute('data-active', active ? '1' : '0');
      btn.style.cssText = [
        'display:inline-flex', 'align-items:center',
        'justify-content:center',
        'margin-left:4px', 'width:14px', 'height:14px',
        'border-radius:3px', 'cursor:pointer',
        'opacity:' + (active ? '1' : '.55'),
        'transition:opacity .12s,background .12s',
        'vertical-align:middle', 'user-select:none',
      ].join(';');
      btn.innerHTML = funnelSvg(active);
      btn.addEventListener('mouseenter', function () {
        this.style.opacity = '1';
        this.style.background = 'var(--surface-2)';
      });
      btn.addEventListener('mouseleave', function () {
        this.style.opacity = (this.getAttribute('data-active') === '1')
          ? '1' : '.55';
        this.style.background = '';
      });
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        openPopover(this, this.getAttribute('data-col'));
      });
      var resizer = th.querySelector('.col-resizer');
      if (resizer) th.insertBefore(btn, resizer);
      else th.appendChild(btn);
    }
  }

  // ----- popover -----
  var __pop = null;
  function closePopover() {
    if (__pop) {
      try { __pop.remove(); } catch (e) {}
      __pop = null;
      document.removeEventListener('mousedown', onDocMouseDown, true);
      document.removeEventListener('keydown', onPopKeydown, true);
    }
  }
  function onDocMouseDown(e) {
    if (!__pop) return;
    if (__pop.contains(e.target)) return;
    closePopover();
  }
  function onPopKeydown(e) {
    if (e.key === 'Escape') { closePopover(); e.stopPropagation(); }
  }
  function openPopover(anchorEl, col) {
    closePopover();
    var distinct = distinctFromRawAll(col);
    var existing = window.coplanColumnFilters[col]
      || { values: new Set(), includeBlank: false };
    var sel = new Set(existing.values || []);
    var includeBlank = !!existing.includeBlank;

    var pop = document.createElement('div');
    pop.className = 'coplan-colfilter-popover';
    pop.style.cssText = [
      'position:absolute', 'z-index:200',
      'background:var(--surface, #fff)',
      'border:1px solid var(--border, #e2e8f0)',
      'border-radius:8px',
      'box-shadow:0 8px 24px rgba(0,0,0,.18)',
      'min-width:240px', 'max-width:320px',
      'padding:10px', 'font-size:12px',
      'display:flex', 'flex-direction:column', 'gap:8px',
    ].join(';');
    pop.innerHTML =
      '<div style="font-weight:600;color:var(--text);">'
        + esc(humanize(col)) + '</div>'
      + '<input type="text" class="input coplan-cf-search" '
        + 'placeholder="Buscar..." style="padding:6px 8px;font-size:12px;"/>'
      + '<label style="display:flex;align-items:center;gap:6px;'
        + 'padding:4px 0;border-bottom:1px solid var(--border);">'
        + '<input type="checkbox" class="coplan-cf-all"/>'
        + '<span>(Selecionar todos)</span></label>'
      + '<div class="coplan-cf-list" style="max-height:230px;'
        + 'overflow-y:auto;display:flex;flex-direction:column;'
        + 'gap:2px;padding:4px 0;"></div>'
      + '<div style="display:flex;gap:6px;justify-content:flex-end;'
        + 'margin-top:4px;">'
        + '<button type="button" class="btn ghost coplan-cf-clear">'
          + 'Limpar</button>'
        + '<button type="button" class="btn primary coplan-cf-ok">'
          + 'OK</button>'
      + '</div>';
    document.body.appendChild(pop);
    __pop = pop;

    var rect = anchorEl.getBoundingClientRect();
    var top = rect.bottom + window.scrollY + 4;
    var left = rect.left + window.scrollX;
    var vw = document.documentElement.clientWidth;
    var popW = 280;
    if (left + popW > vw - 8) left = Math.max(8, vw - popW - 8);
    pop.style.top = top + 'px';
    pop.style.left = left + 'px';

    var listEl = pop.querySelector('.coplan-cf-list');
    var searchEl = pop.querySelector('.coplan-cf-search');
    var allEl = pop.querySelector('.coplan-cf-all');

    function renderList(filterText) {
      var q = String(filterText || '').trim().toUpperCase();
      var html = '';
      if (distinct.hasBlank) {
        if (!q || '(VAZIOS)'.indexOf(q) >= 0) {
          html += '<label style="display:flex;align-items:center;'
            + 'gap:6px;padding:2px 4px;color:var(--text-soft);'
            + 'font-style:italic;">'
            + '<input type="checkbox" data-blank="1"'
            + (includeBlank ? ' checked' : '') + '/>'
            + '<span>(Vazios)</span></label>';
        }
      }
      for (var i = 0; i < distinct.values.length; i++) {
        var v = distinct.values[i];
        var u = v.toUpperCase();
        if (q && u.indexOf(q) < 0) continue;
        var checked = sel.has(u) ? ' checked' : '';
        html += '<label style="display:flex;align-items:center;'
          + 'gap:6px;padding:2px 4px;">'
          + '<input type="checkbox" data-val="' + esc(u) + '"'
          + checked + '/>'
          + '<span>' + esc(v) + '</span></label>';
      }
      if (!html) {
        html = '<div style="padding:8px;color:var(--text-soft);'
          + 'font-style:italic;">Nenhum valor.</div>';
      }
      listEl.innerHTML = html;
      syncAll();
    }
    function syncAll() {
      var boxes = listEl.querySelectorAll('input[type="checkbox"]');
      var total = boxes.length, checked = 0;
      for (var i = 0; i < total; i++) if (boxes[i].checked) checked++;
      if (!total) {
        allEl.checked = false; allEl.indeterminate = false;
      } else if (checked === total) {
        allEl.checked = true; allEl.indeterminate = false;
      } else if (checked === 0) {
        allEl.checked = false; allEl.indeterminate = false;
      } else {
        allEl.checked = false; allEl.indeterminate = true;
      }
    }

    renderList('');
    searchEl.addEventListener('input', function () { renderList(searchEl.value); });
    allEl.addEventListener('change', function () {
      var want = allEl.checked;
      var boxes = listEl.querySelectorAll('input[type="checkbox"]');
      boxes.forEach(function (b) { b.checked = want; });
      allEl.indeterminate = false;
    });
    listEl.addEventListener('change', function () { syncAll(); });

    pop.querySelector('.coplan-cf-clear').addEventListener('click', function () {
      delete window.coplanColumnFilters[col];
      closePopover();
      anchorEl.setAttribute('data-active', '0');
      anchorEl.innerHTML = funnelSvg(false);
      anchorEl.style.opacity = '.55';
      triggerReRender();
    });
    pop.querySelector('.coplan-cf-ok').addEventListener('click', function () {
      var newVals = new Set();
      var present = {};
      var boxes = listEl.querySelectorAll('input[type="checkbox"][data-val]');
      boxes.forEach(function (b) { present[b.getAttribute('data-val')] = b.checked; });
      for (var i = 0; i < distinct.values.length; i++) {
        var u = distinct.values[i].toUpperCase();
        if (Object.prototype.hasOwnProperty.call(present, u)) {
          if (present[u]) newVals.add(u);
        } else if (sel.has(u)) {
          newVals.add(u);
        }
      }
      var blankBox = listEl.querySelector('input[type="checkbox"][data-blank="1"]');
      var newBlank = blankBox ? blankBox.checked : includeBlank;
      var allCount = distinct.values.length + (distinct.hasBlank ? 1 : 0);
      var selCount = newVals.size + (newBlank ? 1 : 0);
      if (selCount === 0 || selCount === allCount) {
        delete window.coplanColumnFilters[col];
        anchorEl.setAttribute('data-active', '0');
        anchorEl.innerHTML = funnelSvg(false);
        anchorEl.style.opacity = '.55';
      } else {
        window.coplanColumnFilters[col] = {
          values: newVals, includeBlank: newBlank,
        };
        anchorEl.setAttribute('data-active', '1');
        anchorEl.innerHTML = funnelSvg(true);
        anchorEl.style.opacity = '1';
      }
      closePopover();
      triggerReRender();
    });

    setTimeout(function () {
      document.addEventListener('mousedown', onDocMouseDown, true);
      document.addEventListener('keydown', onPopKeydown, true);
      searchEl.focus();
    }, 0);
  }

  // ----- segmented Criterios -----
  var CRIT_OPTIONS = [
    { key: '',            label: 'Todas' },
    { key: 'atenderam',   label: 'Atenderam' },
    { key: 'falharam',    label: 'Falharam' },
    { key: 'aprovadas',   label: 'Aprovadas' },
    { key: 'nao aprovadas', label: 'Não aprovadas' },
  ];
  function ensureCriteriosSegmented() {
    if (!enabled()) return;
    var bar = document.querySelector('#tab-visualizar .filter-bar');
    if (!bar) return;
    if (bar.querySelector('#coplan-crit-segmented')) return;
    var wrap = document.createElement('div');
    wrap.id = 'coplan-crit-segmented';
    wrap.style.cssText = [
      'display:inline-flex', 'gap:4px', 'align-items:center',
      'margin-left:8px',
    ].join(';');
    wrap.innerHTML = '<span style="font-size:11.5px;color:var(--text-soft);'
      + 'font-weight:500;margin-right:4px;">Critérios:</span>';
    CRIT_OPTIONS.forEach(function (opt) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'pill' + (opt.key === '' ? ' active' : '');
      b.textContent = opt.label;
      b.setAttribute('data-crit', opt.key);
      b.addEventListener('click', function () {
        var prev = window.coplanCriteriosFilter || '';
        var newKey = (prev === opt.key) ? '' : opt.key;
        window.coplanCriteriosFilter = newKey;
        wrap.querySelectorAll('.pill').forEach(function (p) {
          p.classList.toggle(
            'active', (p.getAttribute('data-crit') || '') === newKey,
          );
        });
        window.coplanFilters = window.coplanFilters || {};
        delete window.coplanFilters.aprovada;
        delete window.coplanFilters.criterios;
        if (newKey === 'aprovadas') window.coplanFilters.aprovada = 'SIM';
        else if (newKey === 'nao aprovadas') window.coplanFilters.aprovada = 'NAO';
        else if (newKey === 'atenderam' || newKey === 'falharam') window.coplanFilters.criterios = newKey;
        if (typeof window.coplanApplySearch === 'function') {
          window.coplanApplySearch();
        }
        renderChips();
      });
      wrap.appendChild(b);
    });
    var searchEl = bar.querySelector('.search-input');
    if (searchEl && searchEl.nextSibling) {
      bar.insertBefore(wrap, searchEl.nextSibling);
    } else {
      bar.appendChild(wrap);
    }
  }

  // ----- chips -----
  function critLabel(key) {
    for (var i = 0; i < CRIT_OPTIONS.length; i++) {
      if (CRIT_OPTIONS[i].key === key) return CRIT_OPTIONS[i].label;
    }
    return key;
  }
  function renderChips() {
    var list = document.getElementById('filter-chips-list');
    var count = document.getElementById('filter-chips-count');
    if (!list) return;
    list.innerHTML = '';
    var n = 0;
    function addChip(html, onRemove) {
      var span = document.createElement('span');
      span.className = 'badge';
      span.style.cssText = 'display:inline-flex;align-items:center;'
        + 'gap:4px;background:var(--surface-2);'
        + 'border:1px solid var(--border);padding:2px 6px;'
        + 'font-size:11px;margin-right:4px;';
      span.innerHTML = html
        + ' <button type="button" style="background:none;border:0;'
        + 'cursor:pointer;color:var(--text-soft);font-size:13px;'
        + 'line-height:1;padding:0 0 0 2px;">×</button>';
      span.querySelector('button').addEventListener('click', onRemove);
      list.appendChild(span);
      n++;
    }
    var crit = window.coplanCriteriosFilter || '';
    if (crit) {
      addChip('Critérios: <strong>' + esc(critLabel(crit)) + '</strong>',
        function () {
          window.coplanCriteriosFilter = '';
          window.coplanFilters = window.coplanFilters || {};
          delete window.coplanFilters.aprovada;
          delete window.coplanFilters.criterios;
          var b = document.getElementById('coplan-crit-segmented');
          if (b) b.querySelectorAll('.pill').forEach(function (p) {
            p.classList.toggle(
              'active', (p.getAttribute('data-crit') || '') === '',
            );
          });
          if (typeof window.coplanApplySearch === 'function') {
            window.coplanApplySearch();
          }
        });
    }
    var cf = window.coplanColumnFilters || {};
    Object.keys(cf).forEach(function (col) {
      var spec = cf[col]; if (!spec) return;
      var parts = [];
      if (spec.values && spec.values.size) {
        var arr = []; spec.values.forEach(function (v) { arr.push(v); });
        arr.sort();
        var preview = arr.slice(0, 3).join(', ');
        if (arr.length > 3) preview += ' +' + (arr.length - 3);
        parts.push(preview);
      }
      if (spec.includeBlank) parts.push('(Vazios)');
      if (!parts.length) return;
      addChip(
        esc(humanize(col)) + ': <strong>' + esc(parts.join(' / '))
          + '</strong>',
        function () {
          delete window.coplanColumnFilters[col];
          triggerReRender();
        });
    });
    if (count) {
      count.textContent = n ? (n + ' filtro' + (n > 1 ? 's' : '')) : '—';
    }
    var bar = document.getElementById('filter-chips-bar');
    if (bar) bar.style.display = n ? '' : 'none';
  }
  window.coplanRenderFilterChips = renderChips;

  // ----- "Limpar" geral -----
  function hookLimparBtn() {
    var visTab = document.getElementById('tab-visualizar');
    if (!visTab) return;
    var btns = visTab.querySelectorAll('.filter-bar .btn');
    btns.forEach(function (b) {
      var t = (b.textContent || '').trim().toLowerCase();
      if (t !== 'limpar') return;
      if (b.__coplanCfV2LimparHook) return;
      b.__coplanCfV2LimparHook = true;
      b.addEventListener('click', function () {
        window.coplanColumnFilters = {};
        window.coplanCriteriosFilter = '';
        window.coplanFilters = window.coplanFilters || {};
        delete window.coplanFilters.aprovada;
        delete window.coplanFilters.criterios;
        var crBar = document.getElementById('coplan-crit-segmented');
        if (crBar) crBar.querySelectorAll('.pill').forEach(function (p) {
          p.classList.toggle(
            'active', (p.getAttribute('data-crit') || '') === '',
          );
        });
        triggerReRender();
      });
    });
  }

  // ----- bootstrap -----
  function init() {
    wrapRender();
    patchFilteredCods();
    ensureCriteriosSegmented();
    ensureFunnels();
    hookLimparBtn();
    renderChips();
  }

  // Apos cada render da tabela, re-injeta funis (caso thead tenha sido
  // re-rebuildado) e re-renderiza chips. Cheap: ensureFunnels e
  // idempotente (skip se .coplan-cf-btn ja existe).
  document.addEventListener('coplan:obras', function () {
    if (!enabled()) return;
    try { ensureFunnels(); } catch (e) {
      console.warn('[coplan colFilters] ensureFunnels erro:', e);
    }
    try { renderChips(); } catch (e) {}
  });
  // Aba Visualizar acabou de virar ativa: garante segmented + funis.
  document.addEventListener('coplan:tab', function (e) {
    if (!e || !e.detail || e.detail.name !== 'visualizar') return;
    setTimeout(function () {
      ensureCriteriosSegmented();
      ensureFunnels();
      hookLimparBtn();
      renderChips();
    }, 50);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>
<script>
// ============================================================
// coplanShowErrorDetails (2026-05-13): modal de detalhes pos-operacao
//
// Substitui o toast resumido quando uma operacao termina com
// falhas/chaves_inexistentes/errors. Mostra a lista completa
// para o usuario poder ver QUAL chave ou COD falhou, e salvar
// em TXT.
//
// Uso:
//   window.coplanShowErrorDetails({
//     title: 'Atualizar obras',
//     summary: '10 atualizadas / 3 falhas / 2 chaves inexistentes',
//     sections: [
//       { label: 'Falhas (3)',
//         lines: ['COD=123: motivo', 'COD=456: motivo'] },
//       { label: 'Chaves inexistentes (2)',
//         lines: ['ALIM-NORTE-15', 'XYZ-SUL-25'] }
//     ],
//     op: 'atualizar',  // slug pro filename do TXT
//   });
//
// Botões do modal:
//   - Copiar tudo (clipboard)
//   - Salvar TXT... (api.save_log_txt -> SAVE dialog)
//   - Abrir pasta de logs (api.open_logs_folder)
//   - Fechar
// ============================================================
(function () {
  if (window.coplanShowErrorDetails) return;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
  function toast(msg, type) {
    if (typeof window.coplanToast === 'function') {
      return window.coplanToast(msg, type);
    }
    var t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast ' + (type || 'info') + ' show';
    setTimeout(function () { t.className = 'toast'; }, 2400);
  }

  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function ts() {
    var d = new Date();
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-'
      + pad2(d.getDate()) + '_' + pad2(d.getHours()) + '-'
      + pad2(d.getMinutes()) + '-' + pad2(d.getSeconds());
  }

  function buildText(opts) {
    var lines = [];
    lines.push('=' + Array(60).join('='));
    lines.push(opts.title || 'Operacao');
    lines.push('Data/hora: ' + new Date().toISOString());
    if (opts.summary) lines.push('Resumo: ' + opts.summary);
    lines.push('=' + Array(60).join('='));
    lines.push('');
    (opts.sections || []).forEach(function (s) {
      if (!s || !s.lines || !s.lines.length) return;
      lines.push('-- ' + (s.label || 'Itens') + ' --');
      s.lines.forEach(function (l) { lines.push(String(l)); });
      lines.push('');
    });
    return lines.join('\n');
  }

  function close(modal) {
    if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
    document.removeEventListener('keydown', escClose, true);
  }
  var __activeModal = null;
  function escClose(e) {
    if (e.key === 'Escape' && __activeModal) {
      e.stopPropagation();
      close(__activeModal);
      __activeModal = null;
    }
  }

  window.coplanShowErrorDetails = function (opts) {
    opts = opts || {};
    var title = String(opts.title || 'Detalhes da operacao');
    var summary = String(opts.summary || '');
    var sections = Array.isArray(opts.sections) ? opts.sections : [];
    var op = String(opts.op || 'log').replace(/[^a-z0-9_-]+/gi, '_');
    var logPath = String(opts.logPath || '');
    var fullText = buildText({
      title: title, summary: summary, sections: sections,
    });
    if (logPath) {
      fullText = '# Log salvo em: ' + logPath + '\n\n' + fullText;
    }

    // Limpa modal anterior se houver
    if (__activeModal) { close(__activeModal); __activeModal = null; }

    var modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.style.cssText = 'display:grid;position:fixed;inset:0;'
      + 'background:rgba(0,0,0,.45);z-index:300;place-items:center;';
    var inner = document.createElement('div');
    inner.className = 'modal lg';
    inner.style.cssText = 'background:var(--surface, #fff);'
      + 'border:1px solid var(--border, #e2e8f0);border-radius:8px;'
      + 'box-shadow:0 12px 32px rgba(0,0,0,.22);max-width:720px;'
      + 'width:90%;max-height:80vh;display:flex;flex-direction:column;';
    modal.appendChild(inner);

    var header = document.createElement('div');
    header.className = 'modal-header';
    header.style.cssText = 'padding:14px 18px;border-bottom:1px solid '
      + 'var(--border);display:flex;align-items:center;'
      + 'justify-content:space-between;gap:8px;';
    header.innerHTML = '<div class="modal-title" style="font-weight:600;'
      + 'font-size:14px;color:var(--text);">' + esc(title) + '</div>'
      + '<button type="button" class="btn ghost btn-icon" data-close '
      + 'style="background:none;border:0;cursor:pointer;font-size:18px;'
      + 'line-height:1;color:var(--text-soft);">×</button>';
    inner.appendChild(header);

    var body = document.createElement('div');
    body.className = 'modal-body';
    body.style.cssText = 'padding:14px 18px;overflow-y:auto;'
      + 'flex:1 1 auto;font-size:12.5px;color:var(--text);';
    var summaryHtml = summary
      ? '<div style="margin-bottom:12px;padding:8px 10px;'
        + 'background:var(--surface-2);border-radius:6px;'
        + 'font-weight:500;">' + esc(summary) + '</div>'
      : '';
    var logPathHtml = logPath
      ? '<div style="margin-bottom:12px;padding:8px 10px;'
        + 'background:rgba(34,197,94,.08);border:1px solid '
        + 'rgba(34,197,94,.35);border-radius:6px;font-size:11.5px;">'
        + '<strong>Log salvo automaticamente em:</strong><br>'
        + '<span style="font-family:var(--font-mono, monospace);'
        + 'word-break:break-all;">' + esc(logPath) + '</span>'
        + '</div>'
      : '';
    var sectionsHtml = '';
    sections.forEach(function (s) {
      if (!s || !s.lines || !s.lines.length) return;
      sectionsHtml += '<div style="margin-bottom:14px;">'
        + '<div style="font-weight:600;font-size:12px;'
        + 'color:var(--text-soft);text-transform:uppercase;'
        + 'letter-spacing:.04em;margin-bottom:4px;">'
        + esc(s.label || 'Itens') + '</div>'
        + '<pre style="background:var(--surface-2);'
        + 'border:1px solid var(--border);border-radius:6px;'
        + 'padding:8px 10px;max-height:240px;overflow:auto;'
        + 'font-family:var(--font-mono, monospace);font-size:11.5px;'
        + 'white-space:pre-wrap;margin:0;color:var(--text);">'
        + s.lines.map(function (l) { return esc(l); }).join('\n')
        + '</pre></div>';
    });
    if (!sectionsHtml) {
      sectionsHtml = '<div style="padding:12px;color:var(--text-soft);'
        + 'font-style:italic;">Sem detalhes adicionais.</div>';
    }
    body.innerHTML = logPathHtml + summaryHtml + sectionsHtml;
    inner.appendChild(body);

    var footer = document.createElement('div');
    footer.className = 'modal-footer';
    footer.style.cssText = 'padding:12px 18px;border-top:1px solid '
      + 'var(--border);display:flex;gap:8px;'
      + 'justify-content:flex-end;flex-wrap:wrap;';
    footer.innerHTML =
      '<button type="button" class="btn ghost" data-act="copy">'
        + 'Copiar tudo</button>'
      + '<button type="button" class="btn ghost" data-act="folder">'
        + 'Abrir pasta de logs</button>'
      + '<button type="button" class="btn primary" data-act="save">'
        + 'Salvar TXT...</button>'
      + '<button type="button" class="btn" data-close>Fechar</button>';
    inner.appendChild(footer);

    document.body.appendChild(modal);
    __activeModal = modal;
    document.addEventListener('keydown', escClose, true);

    modal.addEventListener('click', function (e) {
      if (e.target === modal) {
        close(modal); __activeModal = null;
      }
    });
    modal.querySelectorAll('[data-close]').forEach(function (b) {
      b.addEventListener('click', function () {
        close(modal); __activeModal = null;
      });
    });

    var api = window.pywebview && window.pywebview.api;
    footer.querySelector('[data-act="copy"]').addEventListener('click', function () {
      var ok = false;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(fullText).then(function () {
          toast('Conteudo copiado para a area de transferencia',
                'info');
        }).catch(function () { fallback(); });
      } else {
        fallback();
      }
      function fallback() {
        try {
          var ta = document.createElement('textarea');
          ta.value = fullText;
          ta.style.position = 'fixed'; ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select(); document.execCommand('copy');
          document.body.removeChild(ta);
          toast('Conteudo copiado', 'info');
          ok = true;
        } catch (e) {
          toast('Falha ao copiar', 'error');
        }
      }
    });
    footer.querySelector('[data-act="folder"]').addEventListener('click', function () {
      if (!(api && api.open_logs_folder)) {
        return toast('API indisponivel', 'error');
      }
      api.open_logs_folder().then(function (r) {
        if (r && r.ok) toast('Pasta: ' + r.path, 'info');
        else toast('Falha: ' + (r && r.error || '?'), 'error');
      }).catch(function (err) {
        console.warn('[coplan] open_logs_folder falhou:', err);
        toast('Falha ao abrir pasta de logs: '
          + (err && (err.message || err) || '?'), 'error');
        if (typeof window.coplanReportError === 'function') {
          window.coplanReportError('Abrir pasta de logs',
            'open_logs_folder', { error: String(err && (err.message || err) || '?') });
        }
      });
    });
    footer.querySelector('[data-act="save"]').addEventListener('click', function () {
      if (!(api && api.save_log_txt)) {
        return toast('API indisponivel', 'error');
      }
      var defaultName = op + '_' + ts() + '.txt';
      api.save_log_txt(fullText, defaultName).then(function (r) {
        if (r && r.ok) {
          toast('Log salvo: ' + r.path, 'info');
        } else if (r && r.error === 'cancelado') {
          // silencioso
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        console.warn('[coplan] save_log_txt falhou:', err);
        toast('Falha ao salvar log: '
          + (err && (err.message || err) || '?'), 'error');
        if (typeof window.coplanReportError === 'function') {
          window.coplanReportError('Salvar log',
            'save_log_txt', { error: String(err && (err.message || err) || '?') });
        }
      });
    });
  };

  // Helper para call sites: monta seções a partir do shape do result
  // (campos comuns: error, errors[], falhas[], chaves_inexistentes[],
  // duplicadas[]) e abre o modal. Use depois de exibir o toast de
  // erro. Mostra o modal SO quando ha de fato itens para mostrar.
  window.coplanReportError = function (title, op, r, extra) {
    if (typeof window.coplanShowErrorDetails !== 'function') return;
    var sections = [];
    if (r && r.error) {
      sections.push({ label: 'Erro', lines: [String(r.error)] });
    }
    if (r && Array.isArray(r.errors) && r.errors.length) {
      sections.push({
        label: 'Erros (' + r.errors.length + ')',
        lines: r.errors.slice(),
      });
    }
    if (r && Array.isArray(r.falhas) && r.falhas.length) {
      sections.push({
        label: 'Falhas (' + (r.falhas_total || r.falhas.length) + ')',
        lines: r.falhas.slice(),
      });
    }
    if (r && Array.isArray(r.chaves_inexistentes)
        && r.chaves_inexistentes.length) {
      sections.push({
        label: 'Chaves inexistentes (' + r.chaves_inexistentes.length + ')',
        lines: r.chaves_inexistentes.slice(),
      });
    }
    if (r && Array.isArray(r.duplicadas) && r.duplicadas.length) {
      var dupLines = r.duplicadas.map(function (d) {
        return 'linha ' + (d.linha || '?') + ' - COD excel='
          + (d.cod_excel || '?') + ' / dup COD=' + (d.dup_cod || '?');
      });
      sections.push({
        label: 'Duplicadas (' + r.duplicadas.length + ')',
        lines: dupLines,
      });
    }
    if (r && Array.isArray(r.missing_columns) && r.missing_columns.length) {
      sections.push({
        label: 'Colunas faltantes (' + r.missing_columns.length + ')',
        lines: r.missing_columns.slice(),
      });
    }
    if (extra) sections = sections.concat(extra);
    if (!sections.length && !(r && r.log_path)) {
      // Nada para mostrar -- nao incomoda o usuario com modal vazio.
      return;
    }
    window.coplanShowErrorDetails({
      title: title,
      summary: (r && (r.ok ? 'Operacao concluida com avisos'
                            : 'Operacao nao concluida com sucesso')) || '',
      sections: sections,
      op: op || 'log',
      logPath: (r && r.log_path) || '',
    });
  };
})();
</script>
<script>
(function () {
  'use strict';
  // ---- Secoes colapsaveis no Cadastro ----
  // Clique no cabecalho do card expande/comprime o corpo (esconde como
  // se estivesse "dentro" do titulo). Estado persistido por titulo em
  // localStorage. Ignora cliques em controles do header (ex.: botao
  // "Salvar como NOVA", pills, inputs) para nao colapsar sem querer.
  var STORE_PREFIX = 'coplan:card-collapsed:';

  function cardKey(card) {
    var t = card.querySelector('.card-title');
    return t ? t.textContent.replace(/\s+/g, ' ').trim() : '';
  }
  function loadCollapsed(key) {
    try { return !!key && localStorage.getItem(STORE_PREFIX + key) === '1'; }
    catch (e) { return false; }
  }
  function saveCollapsed(key, collapsed) {
    if (!key) return;
    try { localStorage.setItem(STORE_PREFIX + key, collapsed ? '1' : '0'); }
    catch (e) { /* localStorage indisponivel: ignora */ }
  }

  function setupCard(card) {
    if (card.__collapsibleBound) return;
    var header = card.querySelector(':scope > .card-header');
    if (!header) return;
    card.__collapsibleBound = true;
    header.classList.add('collapsible');
    var key = cardKey(card);
    if (loadCollapsed(key)) card.classList.add('collapsed');
    header.addEventListener('click', function (ev) {
      if (ev.target.closest(
          'button, input, select, textarea, a, label, .pill, .badge')) {
        return;
      }
      card.classList.toggle('collapsed');
      saveCollapsed(key, card.classList.contains('collapsed'));
    });
  }

  function setupAll() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return;
    scope.querySelectorAll('.card').forEach(setupCard);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupAll);
  } else {
    setupAll();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'cadastro') {
      setTimeout(setupAll, 50);
    }
  });
})();
</script>
