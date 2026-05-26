<script>
(function () {
  // ---- Section 6 / Passo 4.4 (Cadastro / Alimentadores Beneficiados) ----
  // Popula o <select> com lista real de alimentadores existentes no
  // banco; gerencia chips de "Alimentadores Beneficiados" + lista
  // derivada de SEs (prefixo do alimentador). Substitui as 3 chips
  // hardcoded do mock.
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function getCard() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return null;
    var cards = scope.querySelectorAll('.card');
    for (var i = 0; i < cards.length; i++) {
      var t = cards[i].querySelector('.card-title');
      if (t && norm(t.textContent).indexOf('alimentadores e subesta') === 0) {
        return cards[i];
      }
    }
    return null;
  }
  function getSelect(card) {
    return card ? card.querySelector('.input-row select') : null;
  }
  function getAddBtn(card) {
    if (!card) return null;
    var btns = card.querySelectorAll('.input-row .btn');
    for (var i = 0; i < btns.length; i++) {
      if (norm(btns[i].textContent).indexOf('adicionar') === 0) return btns[i];
    }
    return null;
  }
  function getChipsBox(card) {
    if (!card) return null;
    var lists = card.querySelectorAll('.chip-list');
    return lists.length ? lists[0] : null;
  }
  function getSesBox(card) {
    if (!card) return null;
    var lists = card.querySelectorAll('.chip-list');
    return lists.length >= 2 ? lists[1] : null;
  }
  function getSubTitle(card) {
    return card ? card.querySelector('.card-sub') : null;
  }
  function chipsToList(box) {
    var out = [];
    if (!box) return out;
    box.querySelectorAll('.chip').forEach(function (c) {
      var v = c.dataset.alim || (c.firstChild && c.firstChild.nodeType === 3
        ? c.firstChild.textContent.trim() : c.textContent.trim());
      if (v) out.push(v.toUpperCase());
    });
    return out;
  }
  function refreshDerived(card) {
    var box = getChipsBox(card);
    var sesBox = getSesBox(card);
    var sub = getSubTitle(card);
    var alims = chipsToList(box);
    var ses = [];
    alims.forEach(function (a) {
      var pref = String(a).split(/[-_/]/)[0].toUpperCase();
      if (pref && ses.indexOf(pref) === -1) ses.push(pref);
    });
    if (sesBox) {
      sesBox.innerHTML = ses.map(function (s) {
        return '<span class="chip">' + String(s).replace(/[<>&]/g, function (c) {
          return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
        }) + '</span>';
      }).join('');
    }
    if (sub) sub.textContent = alims.length + ' alimentadores · ' + ses.length + ' SEs';
  }
  function buildChip(value) {
    var span = document.createElement('span');
    span.className = 'chip';
    span.dataset.alim = String(value || '').toUpperCase();
    span.innerHTML = String(value || '').toUpperCase().replace(/[<>&]/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
    }) + '<i data-lucide="x" class="x"></i>';
    return span;
  }
  function attachChipRemoveHandler(card, chip) {
    var x = chip.querySelector('.x');
    if (!x) return;
    x.addEventListener('click', function (e) {
      e.stopPropagation();
      chip.remove();
      refreshDerived(card);
      if (window.lucide) lucide.createIcons();
    });
  }
  function addAlim(card, value) {
    var v = String(value || '').trim().toUpperCase();
    if (!v) return false;
    var box = getChipsBox(card);
    if (!box) return false;
    // Evita duplicado (case-insensitive).
    var existing = chipsToList(box);
    if (existing.indexOf(v) !== -1) return false;
    var chip = buildChip(v);
    box.appendChild(chip);
    attachChipRemoveHandler(card, chip);
    refreshDerived(card);
    if (window.lucide) lucide.createIcons();
    return true;
  }
  // Recompoe handlers em chips ja renderizados (ex.: apos
  // coplanFillCadastro do Passo 4.1 que usa innerHTML).
  function rebindExistingChips(card) {
    var box = getChipsBox(card);
    if (!box) return;
    box.querySelectorAll('.chip').forEach(function (chip) {
      attachChipRemoveHandler(card, chip);
    });
    refreshDerived(card);
  }

  function loadAlimentadoresIntoSelect() {
    var card = getCard();
    var sel = getSelect(card);
    if (!sel) return Promise.resolve();
    if (!(window.pywebview && window.pywebview.api &&
          window.pywebview.api.list_alimentadores)) {
      return Promise.resolve();
    }
    return window.pywebview.api.list_alimentadores().then(function (r) {
      if (!r || !r.ok) return;
      // Mantem opcao placeholder "—" + lista alfabetica.
      var prevValue = sel.value;
      var html = '<option value="">—</option>';
      (r.items || []).forEach(function (a) {
        var safe = String(a).replace(/[<>&"]/g, function (c) {
          return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'})[c];
        });
        html += '<option value="' + safe + '">' + safe + '</option>';
      });
      sel.innerHTML = html;
      if (prevValue) {
        // Tenta restaurar selecao anterior.
        for (var i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value === prevValue) { sel.selectedIndex = i; break; }
        }
      }
    });
  }

  function bindAlimUI() {
    var card = getCard();
    if (!card) return false;
    var sel = getSelect(card);
    var btn = getAddBtn(card);
    if (!btn) return false;

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var v = sel ? sel.value : '';
      if (!v) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Escolha um alimentador antes de adicionar', 'warn');
        }
        return;
      }
      if (!addAlim(card, v)) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Alimentador ja adicionado', 'warn');
        }
      } else if (sel) {
        sel.selectedIndex = 0;  // reseta para placeholder
      }
    });

    // Re-bind handlers de X em chips ja existentes (mock vem com 3
    // chips fake; serao substituidos quando coplanFillCadastro rodar).
    rebindExistingChips(card);

    // Quando uma obra e' carregada para edicao (Passo 4.1), os chips
    // sao re-renderizados via setChipList: precisamos religar handlers.
    var origFill = window.coplanFillCadastro;
    if (typeof origFill === 'function' && !origFill.__pivoted) {
      var wrapped = function (payload) {
        var r = origFill(payload);
        var c2 = getCard();
        if (c2) rebindExistingChips(c2);
        return r;
      };
      wrapped.__pivoted = true;
      window.coplanFillCadastro = wrapped;
    }

    // Carrega alimentadores ao entrar na aba Cadastro pela 1a vez.
    var loaded = false;
    function ensureLoaded() {
      if (loaded) return;
      loaded = true;
      var p = loadAlimentadoresIntoSelect();
      if (p && typeof p.catch === 'function') {
        p.catch(function (e) {
          loaded = false;
          console.warn('[coplan/cadastro] list_alimentadores catch:', e);
          if (typeof window.coplanToast === 'function') {
            window.coplanToast(
              'Falha ao carregar alimentadores: '
              + (e && e.message || e), 'error');
          }
        });
      }
    }
    document.addEventListener('coplan:tab', function (ev) {
      if (ev && ev.detail && ev.detail.name === 'cadastro') ensureLoaded();
    });
    // Caso o usuario inicie ja na aba Cadastro.
    var cad = document.getElementById('tab-cadastro');
    if (cad && cad.classList.contains('active')) ensureLoaded();

    // Sempre que a lista de obras e' atualizada, e' provavel que tenham
    // entrado novos alimentadores: invalida o cache e recarrega.
    document.addEventListener('coplan:obras', function () {
      loaded = false;
      if (cad && cad.classList.contains('active')) ensureLoaded();
    });

    return true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAlimUI);
  } else {
    bindAlimUI() || setTimeout(bindAlimUI, 50);
  }
})();
</script>
<script>
(function () {
  // ---- Fase A5 (Cadastro / Resumo dos Ganhos por Alimentador) ----
  // Injeta uma card abaixo da Cadastro com a tabela "Resumo dos Ganhos
  // por Alimentador" (carregamento, tensao, clientes) -- equivalente
  // ao MainWindow.popular_quadro_resumo_from_ganhos_depois do desktop.
  // Usa quadro_resumo_ganhos(cod=...) que delega 100% para
  // core.services.resumo_service.montar_quadro_resumo_from_ganhos.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function ensureCard() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return null;
    var card = document.getElementById('coplan-resumo-ganhos-card');
    if (card) return card;
    card = document.createElement('div');
    card.id = 'coplan-resumo-ganhos-card';
    card.className = 'card';
    card.style.marginTop = '12px';
    card.innerHTML =
      '<div class="card-header">'
    +   '<div class="card-title">'
    +     '<i data-lucide="bar-chart-2"></i>'
    +     ' Resumo dos Ganhos por Alimentador'
    +   '</div>'
    +   '<span class="card-sub" id="coplan-resumo-ganhos-sub" '
    +         'style="margin-left:auto;color:var(--text-soft);font-size:12px;"></span>'
    + '</div>'
    + '<div class="card-body">'
    +   '<div class="table-scroll" style="max-height:240px;overflow:auto;">'
    +     '<table class="data-table">'
    +       '<thead><tr>'
    +         '<th>Alimentador</th>'
    +         '<th class="num">Carregamento</th>'
    +         '<th class="num">Tensao Min | Max</th>'
    +         '<th class="num">Clientes</th>'
    +       '</tr></thead>'
    +       '<tbody id="coplan-resumo-ganhos-tbody"></tbody>'
    +     '</table>'
    +   '</div>'
    + '</div>';
    scope.appendChild(card);
    if (window.lucide) lucide.createIcons();
    return card;
  }
  function colorFor(ok) {
    if (ok === true)  return 'color:var(--success);';
    if (ok === false) return 'color:var(--danger);';
    return '';
  }
  function render(state) {
    var card = ensureCard();
    if (!card) return;
    var tbody = card.querySelector('#coplan-resumo-ganhos-tbody');
    var sub = card.querySelector('#coplan-resumo-ganhos-sub');
    if (!tbody) return;
    if (!state || !state.ok) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding:14px;color:var(--danger);">'
                      + esc((state && state.error) || 'Sem dados de ganhos')
                      + '</td></tr>';
      if (sub) sub.textContent = '';
      return;
    }
    var linhas = state.linhas || [];
    if (!linhas.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding:18px;text-align:center;color:var(--text-soft);">'
                      + 'Sem alimentadores no campo Ganhos Totais Depois.</td></tr>';
      if (sub) sub.textContent = '';
      return;
    }
    tbody.innerHTML = linhas.map(function (ln) {
      var c = ln.carregamento || {};
      var t = ln.tensao || {};
      return '<tr>'
        +   '<td>' + esc(ln.alimentador) + '</td>'
        +   '<td class="num mono" style="' + colorFor(c.ok) + '">' + esc(c.text || '-') + '</td>'
        +   '<td class="num mono" style="' + colorFor(t.ok) + '">' + esc(t.text || '-') + '</td>'
        +   '<td class="num mono">' + esc(ln.clientes_text || '-') + '</td>'
        + '</tr>';
    }).join('');
    if (sub) sub.textContent = linhas.length + ' alimentador(es)';
  }
  window.coplanLoadResumoGanhos = function (cod) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.quadro_resumo_ganhos)) return Promise.resolve();
    return api.quadro_resumo_ganhos(cod || '').then(function (s) {
      window.__coplanResumoGanhos = s;
      render(s);
    }).catch(function (e) {
      console.warn('[coplan] quadro_resumo_ganhos catch:', e);
    });
  };
  // Hook em coplanFillCadastro: ao carregar uma obra, popula o resumo.
  function hookFill() {
    var orig = window.coplanFillCadastro;
    if (typeof orig !== 'function' || orig.__a5_pivoted) return;
    var wrapped = function (payload) {
      var r = orig(payload);
      try {
        var cod = (payload && payload.obra && payload.obra.cod) || '';
        if (cod) window.coplanLoadResumoGanhos(cod);
      } catch (e) {}
      return r;
    };
    wrapped.__a5_pivoted = true;
    window.coplanFillCadastro = wrapped;
  }
  // Hook em coplanLimparCampos / "Limpar campos": esvazia o resumo.
  function clearOnLimpar() {
    var card = ensureCard();
    if (!card) return;
    var tbody = card.querySelector('#coplan-resumo-ganhos-tbody');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding:18px;text-align:center;color:var(--text-soft);">'
                      + 'Carregue uma obra para ver o resumo.</td></tr>';
    }
    var sub = card.querySelector('#coplan-resumo-ganhos-sub');
    if (sub) sub.textContent = '';
  }
  function bindLimpar() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    var btns = scope.querySelectorAll('.btn');
    for (var i = 0; i < btns.length; i++) {
      var t = String(btns[i].textContent || '').trim().toLowerCase();
      if (t.indexOf('limpar') === 0) {
        btns[i].addEventListener('click', function () { setTimeout(clearOnLimpar, 0); });
      }
    }
    return true;
  }
  function init() {
    ensureCard();
    clearOnLimpar();  // estado inicial
    hookFill();
    bindLimpar();
    // [FIX] Hook real: window.coplanFillCadastro nao existe (funcao
    // interna ao IIFE). Em vez disso, ouve coplan:obra-active disparado
    // por fillCadastroForm + applyObra. Carrega o resumo com o cod
    // da obra ativa.
    if (!window.__coplanResumoGanhosObsBound) {
      window.__coplanResumoGanhosObsBound = true;
      document.addEventListener('coplan:obra-active', function (ev) {
        var d = (ev && ev.detail) || {};
        if (d.cod && typeof window.coplanLoadResumoGanhos === 'function') {
          window.coplanLoadResumoGanhos(d.cod);
        } else if (!d.cod) {
          // obra desativada (clearForm) — esvazia o resumo.
          clearOnLimpar();
        }
      });
    }
  }
  // Tenta hookar varias vezes (coplanFillCadastro pode chegar tarde).
  var tries = 0;
  function tryHook() {
    if (typeof window.coplanFillCadastro === 'function'
        && !window.coplanFillCadastro.__a5_pivoted) {
      hookFill();
    }
    tries++;
    if (tries < 30 && (typeof window.coplanFillCadastro !== 'function'
        || !window.coplanFillCadastro.__a5_pivoted)) {
      setTimeout(tryHook, 200);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(); tryHook(); });
  } else {
    init(); tryHook();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 4.5 (Cadastro / metadata para selects) ----
  // Popula os 3 selects do form de Cadastro com dados reais:
  //   * Projeto de Investimento -> get_pi_options()
  //   * Pacote                   -> get_pacotes()
  //   * Regional (input)         -> datalist com get_regionais()
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findFieldByLabel(scope, prefix) {
    var fields = scope.querySelectorAll('.field');
    var target = norm(prefix);
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      var clone = lab.cloneNode(true);
      clone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(clone.textContent);
      if (t === target || t.indexOf(target) === 0) {
        return fields[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }
  function escAttr(v) {
    return String(v == null ? '' : v).replace(/[<>&"]/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'})[c];
    });
  }
  function fillSelect(node, items, options) {
    if (!node || node.tagName !== 'SELECT') return;
    options = options || {};
    var prevValue = node.value;
    var html = '';
    if (options.placeholder !== false) {
      html += '<option value="">' + escAttr(options.placeholder || '—') + '</option>';
    }
    items.forEach(function (v) {
      var s = escAttr(v);
      html += '<option value="' + s + '">' + s + '</option>';
    });
    node.innerHTML = html;
    if (prevValue) {
      for (var i = 0; i < node.options.length; i++) {
        if (node.options[i].value === prevValue) { node.selectedIndex = i; return; }
      }
    }
    if (options.preferred) {
      for (var j = 0; j < node.options.length; j++) {
        if (node.options[j].value === options.preferred) { node.selectedIndex = j; return; }
      }
    }
  }

  function ensureDatalist(input, listId) {
    if (!input) return null;
    var existing = document.getElementById(listId);
    if (!existing) {
      existing = document.createElement('datalist');
      existing.id = listId;
      input.parentNode.appendChild(existing);
      input.setAttribute('list', listId);
    }
    return existing;
  }
  function fillDatalist(dlist, items) {
    if (!dlist) return;
    dlist.innerHTML = items.map(function (v) {
      return '<option value="' + escAttr(v) + '"></option>';
    }).join('');
  }

  function applyMetadata(meta) {
    var scope = document.getElementById('tab-cadastro');
    if (!scope || !meta) return;

    // 1. Projeto de Investimento (select)
    var pi = meta.pi || {};
    var piSel = findFieldByLabel(scope, 'Projeto de Investimento');
    if (piSel && piSel.tagName === 'SELECT' && pi.ok) {
      // Junta long_names (do banco) + bases curtas (do config), priorizando
      // os longos (eles que vao para coluna projeto_investimento).
      var pool = [];
      var seen = {};
      (pi.long_names || []).concat(pi.bases || []).forEach(function (v) {
        var k = norm(v);
        if (k && !seen[k]) { seen[k] = 1; pool.push(v); }
      });
      if (pool.length) {
        fillSelect(piSel, pool, { placeholder: false });
        // Re-dispara COD_PEP refresh (Passo 4.3) que depende do PI.
        if (typeof window.coplanRefreshCodPep === 'function') {
          window.coplanRefreshCodPep();
        }
      }
    }

    // 2. Pacote (select)
    var pacotes = meta.pacotes || {};
    var pacSel = findFieldByLabel(scope, 'Pacote');
    if (pacSel && pacSel.tagName === 'SELECT' && pacotes.ok) {
      fillSelect(pacSel, pacotes.items || [], { placeholder: false });
    }

    // 3. Regional (input livre + datalist para autocomplete)
    var regs = meta.regionais || {};
    var regNode = findFieldByLabel(scope, 'Regional');
    if (regNode && regNode.tagName === 'INPUT' && regs.ok) {
      var dl = ensureDatalist(regNode, 'coplan-regionais-datalist');
      fillDatalist(dl, regs.items || []);
    }

    // 4. Alimentador Obra (select) -- usa list_alimentadores (banco + apoio).
    // Sem isso, o mock so traz "ATB-204" como opcao e setNodeValue
    // tem que injetar dinamicamente toda obra.
    var alim = meta.alimentadores || {};
    var alimNode = findFieldByLabel(scope, 'Alimentador Obra');
    if (alimNode && alimNode.tagName === 'SELECT' && alim.ok) {
      fillSelect(alimNode, alim.items || [], { placeholder: '—' });
    }

    // 5. Caracteristicas (select) -- usa apoio.caracteristicas.
    var carac = meta.caracteristicas || {};
    var caracNode = findFieldByLabel(scope, 'Caracteristicas');
    if (caracNode && caracNode.tagName === 'SELECT' && carac.ok) {
      fillSelect(caracNode, carac.items || [], { placeholder: '—' });
    }
  }

  function loadMetadata() {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_form_metadata)) return;
    api.get_form_metadata().then(function (meta) {
      window.__coplanFormMeta = meta;
      applyMetadata(meta);
    }).catch(function (e) {
      console.warn('[coplan] get_form_metadata catch:', e);
    });
  }

  function bindMetadataLoader() {
    var loaded = false;
    function ensure() {
      if (loaded) return;
      loaded = true;
      loadMetadata();
    }
    document.addEventListener('coplan:tab', function (ev) {
      if (ev && ev.detail && ev.detail.name === 'cadastro') ensure();
    });
    var cad = document.getElementById('tab-cadastro');
    if (cad && cad.classList.contains('active')) ensure();
    // Apos save_obra (insert/update), pode haver novos pacotes /
    // projetos_investimento -> invalida cache.
    document.addEventListener('coplan:obras', function () {
      loaded = false;
      if (cad && cad.classList.contains('active')) ensure();
    });
    // Apos novo apoio carregado (Procurar... no card Empresa) ->
    // invalida cache de metadata para que selects (alimentadores,
    // PI, caracteristicas) reflitam imediatamente.
    document.addEventListener('coplan:apoio:loaded', function () {
      loaded = false;
      // Recarrega ja se estiver na aba cadastro.
      if (cad && cad.classList.contains('active')) ensure();
    });
    return true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindMetadataLoader);
  } else {
    bindMetadataLoader();
  }
})();
</script>
<script>
(function () {
  // ---- Apoio / auto-fill do Cadastro ----
  // Replica apoio_mixin.alimentador_selecionado do desktop:
  // ao trocar o "Alimentador Obra" no Cadastro, busca details
  // (TENSAO/REGIONAL/SUPERINTENDENCIA/SE) no apoio carregado e
  // preenche os 4 campos automaticamente.
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findFieldByLabel(scope, prefix) {
    var fs = scope.querySelectorAll('.field');
    var target = norm(prefix);
    for (var i = 0; i < fs.length; i++) {
      var lab = fs[i].querySelector('label');
      if (!lab) continue;
      var clone = lab.cloneNode(true);
      clone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(clone.textContent);
      if (t === target || t.indexOf(target) === 0) {
        return fs[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }
  function setNodeValueIfEmpty(node, value, force) {
    if (!node || (node.value && !force)) return;
    if (node.tagName === 'SELECT') {
      var opts = node.options;
      for (var i = 0; i < opts.length; i++) {
        if (String(opts[i].value) === String(value)
            || String(opts[i].textContent).trim() === String(value)) {
          node.selectedIndex = i;
          return;
        }
      }
    }
    node.value = String(value || '');
  }
  function applyAlimDetails(d) {
    if (!d || !d.ok) return;
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return;
    var nT  = findFieldByLabel(scope, 'tensao obra');
    var nTo = findFieldByLabel(scope, 'tensao operacao');
    var nR  = findFieldByLabel(scope, 'regional');
    var nS  = findFieldByLabel(scope, 'superintendencia');
    var nSE = findFieldByLabel(scope, 'se');
    // 'force=true' so quando o user efetivamente trocou o alim
    // (handler de change). Em outros gatilhos respeitamos valor
    // existente.
    setNodeValueIfEmpty(nT,  d.tensao,           true);
    setNodeValueIfEmpty(nTo, d.tensao,           true);
    setNodeValueIfEmpty(nR,  d.regional,         true);
    setNodeValueIfEmpty(nS,  d.superintendencia, true);
    setNodeValueIfEmpty(nSE, d.se,               true);
    if (typeof window.coplanToast === 'function') {
      window.coplanToast('Apoio: ' + d.alim
        + ' (' + (d.regional || '?') + '/' + (d.se || '?') + ')', 'info');
    }
  }
  window.coplanLoadAlimDetails = function (alim) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_alimentador_details)) return Promise.resolve();
    return api.get_alimentador_details(String(alim || '')).then(applyAlimDetails);
  };

  function bindAlimChange() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    var node = findFieldByLabel(scope, 'alimentador obra');
    if (!node || node.__alimDetailsBound) return !!node;
    node.__alimDetailsBound = true;
    function onChange() {
      var v = String(node.value || '').trim();
      if (!v) return;
      window.coplanLoadAlimDetails(v);
      // Atualiza tambem o "alim em foco" para Ganhos (Passo 5.4).
      if (typeof window.coplanSetCurrentAlim === 'function') {
        window.coplanSetCurrentAlim(v);
      }
    }
    node.addEventListener('change', onChange);
    node.addEventListener('blur', onChange);
    return true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAlimChange);
  } else {
    if (!bindAlimChange()) setTimeout(bindAlimChange, 50);
  }
})();
</script>
<script>
(function () {
  // ---- Fase A1: botão "Calcular" valor da obra ----
  // Wira o botão ao lado do campo "Valor da Obra" no card Dados
  // Financeiros. Le campos do form (PI, Tensão, Características,
  // Regional, Quantidade) e chama calcular_valor_obra (delega 100%
  // pro core.services.atualizar_obra_service).
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findFieldByLabel(scope, prefix) {
    var fs = scope.querySelectorAll('.field');
    var target = norm(prefix);
    for (var i = 0; i < fs.length; i++) {
      var lab = fs[i].querySelector('label');
      if (!lab) continue;
      var clone = lab.cloneNode(true);
      clone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(clone.textContent);
      if (t === target || t.indexOf(target) === 0) {
        return fs[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }
  function fmtMoneyBRL(v) {
    if (v == null) return '';
    var n = Number(v);
    if (isNaN(n)) return '';
    return n.toLocaleString('pt-BR', {
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
  }
  function findCalcularBtn(scope) {
    var btns = scope.querySelectorAll('.btn');
    for (var i = 0; i < btns.length; i++) {
      var t = norm(btns[i].textContent);
      if (t.indexOf('calcular') === 0) return btns[i];
    }
    return null;
  }
  function bindCalcular() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    var btn = findCalcularBtn(scope);
    if (!btn || btn.__pivoted) return !!btn;
    btn.__pivoted = true;
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var api = window.pywebview && window.pywebview.api;
      if (!(api && api.calcular_valor_obra)) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('API indisponivel', 'error');
        }
        return;
      }
      var pi = (findFieldByLabel(scope, 'projeto de investimento') || {}).value || '';
      var tensao = (findFieldByLabel(scope, 'tensao obra') || {}).value || '';
      var carac = (findFieldByLabel(scope, 'caracteristicas') || {}).value || '';
      var regional = (findFieldByLabel(scope, 'regional') || {}).value || '';
      var qtd = (findFieldByLabel(scope, 'quantidade') || {}).value || '';
      var cod = window.__coplanEditingCod || '';
      if (typeof window.coplanToast === 'function') {
        window.coplanToast('Calculando valor...', 'info');
      }
      api.calcular_valor_obra(pi, '', tensao, carac, regional, qtd, cod)
        .then(function (r) {
          if (!r) return;
          if (r.ok && r.valor != null) {
            var valorNode = findFieldByLabel(scope, 'valor da obra');
            if (valorNode) valorNode.value = fmtMoneyBRL(r.valor);
            if (typeof window.coplanToast === 'function') {
              var extra = (r.chaves_inexistentes && r.chaves_inexistentes.length)
                ? ' (chaves extras nao encontradas: '
                  + r.chaves_inexistentes.length + ')' : '';
              window.coplanToast('Valor: R$ ' + fmtMoneyBRL(r.valor)
                                 + extra,
                                 r.chaves_inexistentes && r.chaves_inexistentes.length
                                   ? 'warn' : 'info');
            }
            // Mesmo com sucesso, se houve chaves inexistentes ou
            // motivos de falha (extras), mostra o modal pro usuario
            // ver QUAIS chaves nao foram encontradas.
            if (window.coplanReportError
                && ((r.chaves_inexistentes && r.chaves_inexistentes.length)
                    || (r.motivos_falha && r.motivos_falha.length))) {
              window.coplanReportError(
                'Calcular Valor da Obra', 'calcular_valor_obra',
                {
                  ok: true,
                  chaves_inexistentes: r.chaves_inexistentes || [],
                  falhas: (r.motivos_falha || []).map(function (m) {
                    return String(m);
                  }),
                  falhas_total: (r.motivos_falha || []).length,
                });
            }
          } else {
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Falha: '
                + (r.error || (r.motivos_falha || []).join('; ') || '?'),
                'error');
            }
            if (window.coplanReportError) {
              window.coplanReportError(
                'Calcular Valor da Obra', 'calcular_valor_obra',
                {
                  ok: false,
                  error: r && r.error,
                  chaves_inexistentes: (r && r.chaves_inexistentes) || [],
                  falhas: ((r && r.motivos_falha) || []).map(String),
                  falhas_total: ((r && r.motivos_falha) || []).length,
                });
            }
          }
        });
    });
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindCalcular);
  } else {
    if (!bindCalcular()) setTimeout(bindCalcular, 50);
  }
})();
</script>
<script>
(function () {
  // ---- Fase G: Preview da chave de modulo (calc_gerar_cod + calc_build_module_key)
  // Adiciona botao "Chave de Módulo" ao lado do botao "Calcular" no card
  // Dados Financeiros. Click -> modal mostrando a chave de calculo + a
  // chave de modulo usada (util pra debug quando o calc falha por chave nao
  // achada na planilha de apoio).
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function findFieldByLabel(scope, prefix) {
    var fs = scope.querySelectorAll('.field');
    var target = norm(prefix);
    for (var i = 0; i < fs.length; i++) {
      var lab = fs[i].querySelector('label');
      if (!lab) continue;
      var c = lab.cloneNode(true);
      c.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(c.textContent);
      if (t === target || t.indexOf(target) === 0) {
        return fs[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }
  function showPreviewModal(cod, key, error) {
    var modal = document.createElement('div');
    modal.style.cssText = (
      'position:fixed;inset:0;background:rgba(0,0,0,.5);'
      + 'z-index:100000;display:flex;align-items:center;'
      + 'justify-content:center;padding:24px;'
    );
    modal.addEventListener('click', function (e) {
      if (e.target === modal) document.body.removeChild(modal);
    });
    var box = document.createElement('div');
    box.style.cssText = (
      'background:var(--surface,#fff);'
      + 'border-radius:8px;padding:20px;'
      + 'max-width:680px;width:100%;max-height:80vh;'
      + 'display:flex;flex-direction:column;gap:14px;'
      + 'box-shadow:0 10px 40px rgba(0,0,0,.3);'
    );
    var content = '<div style="display:flex;align-items:center;gap:8px;">'
      + '<i data-lucide="hash"></i>'
      + '<strong>Preview da chave de módulo</strong>'
      + '<button id="coplan-preview-cod-close" class="btn"'
      + ' style="margin-left:auto;">Fechar</button></div>';
    if (error) {
      content += '<div style="color:var(--danger,#dc2626);padding:10px 14px;'
        + 'background:rgba(220,38,38,.08);border-radius:6px;'
        + 'border:1px solid rgba(220,38,38,.2);">'
        + '<i data-lucide="alert-octagon" style="width:14px;height:14px;"></i> '
        + esc(error) + '</div>';
    }
    if (cod) {
      content += '<div>'
        + '<div style="font-size:11px;color:var(--text-soft);margin-bottom:4px;">'
        + 'Chave de cálculo (CalculationManager.gerar_cod) -- composto PCT|ALIM|TIPO|QTDxCARAC|COORD</div>'
        + '<div style="font-family:monospace;font-size:14px;'
        + 'padding:10px 14px;background:var(--surface-2,#f1f5f9);'
        + 'border-radius:6px;border:1px solid var(--border,#cbd5e1);'
        + 'word-break:break-all;">' + esc(cod) + '</div>'
        + '<button id="coplan-preview-cod-copy-cod" class="btn"'
        + ' style="margin-top:6px;font-size:11px;">'
        + '<i data-lucide="clipboard"></i> Copiar chave de cálculo</button></div>';
    }
    if (key) {
      content += '<div>'
        + '<div style="font-size:11px;color:var(--text-soft);margin-bottom:4px;">'
        + 'Chave de modulo (build_module_key) -- usada pro lookup na planilha apoio</div>'
        + '<div style="font-family:monospace;font-size:13px;'
        + 'padding:10px 14px;background:var(--surface-2,#f1f5f9);'
        + 'border-radius:6px;border:1px solid var(--border,#cbd5e1);'
        + 'word-break:break-all;">' + esc(key) + '</div>'
        + '<button id="coplan-preview-cod-copy-key" class="btn"'
        + ' style="margin-top:6px;font-size:11px;">'
        + '<i data-lucide="clipboard"></i> Copiar chave</button></div>';
    }
    content += '<div style="font-size:11px;color:var(--text-soft);'
      + 'border-top:1px solid var(--border);padding-top:8px;">'
      + 'Dica: se o "Calcular" falha por "chave nao encontrada", '
      + 'verifique se essa chave existe na aba MODULO do apoio xlsx.</div>';
    box.innerHTML = content;
    modal.appendChild(box);
    document.body.appendChild(modal);
    var byId = function (i) { return document.getElementById(i); };
    byId('coplan-preview-cod-close').onclick = function () {
      document.body.removeChild(modal);
    };
    function copyTo(text, label) {
      function toastMsg(msg, lvl) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(msg, lvl);
        }
      }
      function fb() {
        try {
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed'; ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          var ok = document.execCommand('copy');
          document.body.removeChild(ta);
          return !!ok;
        } catch (e) { return false; }
      }
      function done(ok) {
        toastMsg(ok ? (label + ' copiado') : ('Falha ao copiar ' + label),
                 ok ? 'info' : 'error');
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          done(true);
        }, function () { done(fb()); });
      } else {
        done(fb());
      }
    }
    var bC = byId('coplan-preview-cod-copy-cod');
    if (bC) bC.onclick = function () { copyTo(cod, 'COD'); };
    var bK = byId('coplan-preview-cod-copy-key');
    if (bK) bK.onclick = function () { copyTo(key, 'Chave'); };
    if (window.lucide) lucide.createIcons();
  }
  function findPreviewBtnHost(scope) {
    var btns = scope.querySelectorAll('.btn');
    for (var i = 0; i < btns.length; i++) {
      if (norm(btns[i].textContent).indexOf('calcular') === 0) {
        return btns[i];
      }
    }
    return null;
  }
  function bindPreviewCod() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    if (scope.querySelector('#coplan-btn-preview-cod')) return true;
    var calcBtn = findPreviewBtnHost(scope);
    if (!calcBtn || !calcBtn.parentNode) return false;
    var btn = document.createElement('button');
    btn.id = 'coplan-btn-preview-cod';
    btn.className = calcBtn.className || 'btn';
    btn.title = 'Mostra a chave de calculo + a chave de modulo usadas no lookup de precos (debug)';
    btn.innerHTML = '<i data-lucide="hash"></i> Chave de Módulo';
    calcBtn.parentNode.insertBefore(btn, calcBtn.nextSibling);
    if (window.lucide) lucide.createIcons();
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var api = window.pywebview && window.pywebview.api;
      if (!(api && api.calc_gerar_cod && api.calc_build_module_key)) {
        return window.coplanToast && window.coplanToast('API indisponivel', 'error');
      }
      // Coleta valores do form
      var pacote = (findFieldByLabel(scope, 'pacote') || {}).value || '';
      var alim = (findFieldByLabel(scope, 'alimentador obra') || {}).value || '';
      var pi = (findFieldByLabel(scope, 'projeto de investimento') || {}).value || '';
      var qtd = (findFieldByLabel(scope, 'quantidade') || {}).value || '';
      var carac = (findFieldByLabel(scope, 'caracteristicas') || {}).value || '';
      var coordF = (findFieldByLabel(scope, 'coordenadas para') || {}).value || '';
      var tensao = (findFieldByLabel(scope, 'tensao obra') || {}).value || '';

      // Resolve PI base + regional para a chave
      var regNode = findFieldByLabel(scope, 'regional');
      var regional = regNode ? (regNode.value || '') : '';

      // Mostra um modal "loading" simples? Nao -- promises curtas, ok.
      Promise.all([
        api.calc_gerar_cod(pacote, alim, pi, qtd, carac, coordF, '')
          .catch(function () { return null; }),
        api.resolve_pi_base(pi, false).catch(function () { return null; }),
      ]).then(function (results) {
        var rCod = results[0];
        var rPi = results[1];
        var piBase = (rPi && rPi.ok) ? rPi.pi_base : pi;
        // Resolve regional codigo (REG-XXXX) via REGIONAL_MAP do banco
        // Como nao temos endpoint pra isso, usa o nome direto (best-effort).
        var regCod = regional;
        // Tenta obter codigo regional se houver
        var apiCfg = window.pywebview && window.pywebview.api;
        var cleanup = function () {
          api.calc_build_module_key(piBase, tensao, carac, regCod || regional)
            .then(function (rKey) {
              var cod = (rCod && rCod.ok) ? rCod.cod : '';
              var err = (rCod && !rCod.ok) ? rCod.error : '';
              var key = (rKey && rKey.ok) ? rKey.key : '';
              if (!cod && !key && !err) err = 'Falha ao gerar preview';
              showPreviewModal(cod, key, err);
            });
        };
        // Buscar regional code via get_regional_map_full se disponivel
        if (apiCfg && apiCfg.get_regional_map_full && regional) {
          apiCfg.get_regional_map_full().then(function (rm) {
            if (rm && rm.ok && rm.entries) {
              var entry = rm.entries.find(function (e) {
                return (e.nome || '').toUpperCase().trim()
                       === regional.toUpperCase().trim();
              });
              if (entry) regCod = entry.codigo || regional;
            }
            cleanup();
          });
        } else {
          cleanup();
        }
      });
    });
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindPreviewCod);
  } else {
    bindPreviewCod() || setTimeout(bindPreviewCod, 200);
  }
})();
</script>
<script>
(function () {
  // ---- Limpa resquicios de mockup do Cadastro no boot ----
  // O HTML mock veio com varios valores hardcoded ("ATIBAIA - REC. 2025",
  // "13.8", "ATB-204", coordenadas, valor 2.487.500,00, COD_PEP fake,
  // 3 chips, etc.). Isso roda 1 unica vez (DOMContentLoaded) e zera tudo
  // se NAO ha obra em edicao. Quando o usuario double-clica numa obra,
  // coplanFillCadastro preenche depois disso com dados reais.
  function _norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function _wipeFieldByLabel(scope, prefix) {
    var fs = scope.querySelectorAll('.field');
    var target = _norm(prefix);
    for (var i = 0; i < fs.length; i++) {
      var lab = fs[i].querySelector('label');
      if (!lab) continue;
      var c = lab.cloneNode(true);
      c.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = _norm(c.textContent);
      if (t === target || t.indexOf(target) === 0) {
        var node = fs[i].querySelector('input, select, textarea');
        if (node) {
          if (node.tagName === 'SELECT') {
            // Reset pra primeira opcao (sera repopulado por applyMetadata)
            node.selectedIndex = 0;
          } else {
            node.value = '';
          }
        }
        return;
      }
    }
  }
  function _wipeChipsInCard(scope, cardTitlePrefix) {
    var cards = scope.querySelectorAll('.card');
    for (var i = 0; i < cards.length; i++) {
      var t = cards[i].querySelector('.card-title');
      if (!t) continue;
      if (_norm(t.textContent).indexOf(_norm(cardTitlePrefix)) !== 0) continue;
      cards[i].querySelectorAll('.chip-list').forEach(function (lst) {
        lst.innerHTML = '';
      });
      var sub = cards[i].querySelector('.card-sub');
      if (sub) sub.textContent = '0 alimentadores · 0 SEs';
      return;
    }
  }
  function wipeMockCadastro() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    if (scope.__mockWiped) return true;
    // So limpa se nao ha obra em edicao (preserva fluxo de edit)
    if (window.__coplanEditingCod) { scope.__mockWiped = true; return true; }
    scope.__mockWiped = true;

    // Identificacao
    _wipeFieldByLabel(scope, 'item');
    _wipeFieldByLabel(scope, 'projeto');         // "Projeto *" (input)
    _wipeFieldByLabel(scope, 'observac');        // "Observações" (textarea)
    // PI (select), Nome do Projeto (select) -- repopulados pelo backend

    // Informacoes Tecnicas
    _wipeFieldByLabel(scope, 'tensao obra');
    _wipeFieldByLabel(scope, 'tensao operac');
    _wipeFieldByLabel(scope, 'regional');
    _wipeFieldByLabel(scope, 'superinten');
    _wipeFieldByLabel(scope, 'se');
    _wipeFieldByLabel(scope, 'coordenadas de');
    _wipeFieldByLabel(scope, 'coordenadas para');
    _wipeFieldByLabel(scope, 'quantidade');
    // Selects: caracteristicas/manobra/novo bay/criticidade/pacote
    // ficam com primeiro item; metadados reais sobrescrevem depois.
    _wipeFieldByLabel(scope, 'caracteristicas');
    _wipeFieldByLabel(scope, 'manobra');
    _wipeFieldByLabel(scope, 'novo bay');
    _wipeFieldByLabel(scope, 'criticidade');
    _wipeFieldByLabel(scope, 'pacote');
    _wipeFieldByLabel(scope, 'alimentador obra');

    // Dados Financeiros
    _wipeFieldByLabel(scope, 'valor da obra');
    _wipeFieldByLabel(scope, 'cod_pep');
    // Pill "Obra Aprovada": garante NAO ativo
    var pillCards = scope.querySelectorAll('.field');
    pillCards.forEach(function (f) {
      var lab = f.querySelector('label');
      if (!lab) return;
      if (_norm(lab.textContent).indexOf('obra aprovada') !== 0) return;
      f.querySelectorAll('.pill').forEach(function (p) {
        p.classList.remove('active');
      });
      var pills = f.querySelectorAll('.pill');
      // O 1o eh "NÃO" no mock
      if (pills.length) pills[0].classList.add('active');
    });

    // Card "Alimentadores e Subestações Beneficiadas" -- limpa chips
    _wipeChipsInCard(scope, 'alimentadores e subesta');

    // Card "Validação" da sidebar -- substitui o conteudo hardcoded
    // (5 status fake) por um placeholder + botao que aciona o painel
    // "Validar obra (preview)" da Fase E.
    var cards = scope.querySelectorAll('.card');
    cards.forEach(function (c) {
      var t = c.querySelector('.card-title');
      if (!t) return;
      if (_norm(t.textContent).indexOf('valida') !== 0) return;
      var body = c.querySelector('.card-body');
      if (!body) return;
      body.innerHTML =
        '<div style="display:flex;flex-direction:column;gap:8px;'
      +      'padding:8px;font-size:12px;color:var(--text-soft);">'
      +   '<div>Os checks de validacao sao calculados sob demanda.</div>'
      +   '<button id="coplan-sidebar-val-trigger" class="btn"'
      +          ' style="font-size:12px;">'
      +     '<i data-lucide="play"></i> Rodar agora</button>'
      +   '<div style="font-size:11px;opacity:.8;">'
      +     'Atalho: ver tambem o card "Validar obra (preview)" abaixo do form.'
      +   '</div>'
      + '</div>';
      var btn = body.querySelector('#coplan-sidebar-val-trigger');
      if (btn) {
        btn.addEventListener('click', function () {
          var run = document.getElementById('coplan-btn-val-run');
          if (run) run.click();
          var bar = document.getElementById('coplan-validar-bar');
          if (bar && bar.scrollIntoView) {
            bar.scrollIntoView({behavior: 'smooth', block: 'center'});
          }
        });
      }
    });

    // Card "Resumo dos Ganhos por Alimentador" comeca com "Carregue uma
    // obra para ver o resumo." (Fase A5 ja faz isso). OK.

    // Badge "Editando" -> "Nova obra"
    var badge = scope.querySelector('.card-header .badge');
    if (badge) {
      badge.className = 'badge info';
      badge.textContent = 'Nova obra';
    }

    if (window.lucide) lucide.createIcons();
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wipeMockCadastro);
  } else {
    wipeMockCadastro() || setTimeout(wipeMockCadastro, 100);
  }
})();
</script>
<script>
(function () {
  // ---- Limpa resquicios de mockup tambem em Visualizar + Ganhos ----
  // Visualizar: 4 KPI cards no topo com valores fake (2.481, 1.847, 412, R$ 487M).
  // Ganhos: card "Ganhos Atuais (registrados)" com 3 inputs fake.
  // Tudo isso e' sobrescrito pelas APIs (get_obras_stats / get_ganhos_atuais)
  // mas se o backend tarda, o usuario ve numero fake. Limpa no boot.
  function wipeMockOutras() {
    var wipedAll = true;

    // ---- Visualizar: KPIs do topo ----
    var vis = document.getElementById('tab-visualizar');
    if (vis) {
      vis.querySelectorAll('.stat').forEach(function (st) {
        var v = st.querySelector('.stat-value');
        var d = st.querySelector('.stat-delta');
        // So zera se ainda esta com valor fake (nao foi sobrescrito por API)
        if (v && !st.__wiped) {
          v.textContent = '—';
          if (d) d.textContent = '';
          st.__wiped = true;
        }
      });

      // ---- Visualizar: filter-chips fake "Filtros ativos" ----
      // Barra hardcoded com chips: Ano:2026, Regional:Centro;Leste,
      // Pacote:Mercado, Aprovada:NAO + badge "412 obras encontradas".
      // Limpa para que so apareca o que esta de fato filtrado.
      vis.querySelectorAll('.filter-bar').forEach(function (bar) {
        // Identifica a barra de "Filtros ativos:" pela 1a label
        var span = bar.querySelector('span');
        var txt = span ? String(span.textContent || '').trim().toLowerCase() : '';
        if (txt.indexOf('filtros ativos') !== 0) return;
        if (bar.__wiped) return;
        bar.__wiped = true;
        // Remove os filter-chip mockados
        bar.querySelectorAll('.filter-chip').forEach(function (c) {
          c.remove();
        });
        // Zera badge "412 obras encontradas" (sera sobrescrito pelo
        // updateSelectionCount apos coplan:obras carregar)
        bar.querySelectorAll('.badge').forEach(function (b) {
          b.textContent = 'aguardando dados...';
          b.classList.remove('info');
          b.classList.add('ghost');
        });
      });

      // ---- Visualizar: badge "412 resultados · 8 selecionadas" ----
      // (no .table-header) -- tambem sera sobrescrito pelo
      // updateSelectionCount; mas no boot mostra fake. Zera ja.
      vis.querySelectorAll('.table-header .badge').forEach(function (b) {
        if (b.__wiped) return;
        b.__wiped = true;
        b.textContent = '— resultados';
      });

      // ---- Visualizar: paginacao "1 / 14" ----
      vis.querySelectorAll('.pagination .mono').forEach(function (m) {
        if (m.__wiped) return;
        m.__wiped = true;
        // Detecta padrao "N / N" (paginacao). Sem regex pra evitar
        // warning de escape no Python triple-quoted string.
        var s = String(m.textContent || '').trim();
        if (s.indexOf('/') >= 0) {
          var parts = s.split('/');
          if (parts.length === 2
              && !isNaN(parseInt(parts[0].trim(), 10))
              && !isNaN(parseInt(parts[1].trim(), 10))) {
            m.textContent = '— / —';
          }
        }
      });
    } else {
      wipedAll = false;
    }

    // ---- Ganhos: card "Ganhos Atuais (registrados)" ----
    var ganhos = document.getElementById('tab-ganhos');
    if (ganhos) {
      ganhos.querySelectorAll('.card').forEach(function (c) {
        var t = c.querySelector('.card-title');
        if (!t) return;
        var label = String(t.textContent || '').trim().toLowerCase()
                       .normalize('NFD').replace(/[̀-ͯ]/g, '');
        if (label.indexOf('ganhos atuais') !== 0) return;
        // Limpa os 3 inputs do card (mas so 1 vez)
        if (c.__wiped) return;
        c.__wiped = true;
        c.querySelectorAll('input').forEach(function (n) {
          n.value = '';
          n.placeholder = n.placeholder || '—';
        });
      });
    }

    return wipedAll;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wipeMockOutras);
  } else {
    wipeMockOutras() || setTimeout(wipeMockOutras, 100);
  }
})();
</script>
<script>
(function () {
  // ---- Fase H: Right-click nos chips (alimentadores beneficiados / SEs)
  // Equivalente desktop: mostrar_menu_contexto_alimentadores /
  // mostrar_menu_contexto_subestacoes. Adiciona menu de contexto:
  //   - Copiar este
  //   - Copiar todos
  //   - Remover este (ja existe via X mas reforça)
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function toast(msg, level) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, level || 'info');
    }
  }
  function ensureMenu() {
    var existing = document.getElementById('coplan-chip-ctx-menu');
    if (existing) return existing;
    var el = document.createElement('div');
    el.id = 'coplan-chip-ctx-menu';
    el.style.cssText = (
      'position:fixed;display:none;z-index:99999;'
      + 'background:var(--surface,#fff);'
      + 'border:1px solid var(--border,#cbd5e1);'
      + 'border-radius:6px;'
      + 'box-shadow:0 6px 24px rgba(0,0,0,.18);'
      + 'min-width:200px;padding:4px 0;font-size:13px;'
      + 'user-select:none;'
    );
    document.body.appendChild(el);
    document.addEventListener('click', function (ev) {
      if (!el.contains(ev.target)) el.style.display = 'none';
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') el.style.display = 'none';
    });
    return el;
  }
  function openMenu(x, y, items) {
    var menu = ensureMenu();
    menu.innerHTML = '';
    items.forEach(function (item) {
      var row = document.createElement('div');
      row.style.cssText = (
        'padding:7px 14px;cursor:pointer;'
        + 'display:flex;align-items:center;gap:8px;'
      );
      row.addEventListener('mouseenter', function () {
        row.style.background = 'var(--surface-2,#f1f5f9)';
      });
      row.addEventListener('mouseleave', function () {
        row.style.background = '';
      });
      var icon = item.icon
        ? '<i data-lucide="' + esc(item.icon)
          + '" style="width:13px;height:13px;flex-shrink:0;"></i>' : '';
      row.innerHTML = icon + '<span>' + esc(item.label) + '</span>';
      row.addEventListener('click', function () {
        menu.style.display = 'none';
        try { item.action(); } catch (e) { console.warn('[chip-ctx]', e); }
      });
      menu.appendChild(row);
    });
    if (window.lucide) lucide.createIcons();
    menu.style.display = 'block';
    var rect = menu.getBoundingClientRect();
    var W = window.innerWidth, H = window.innerHeight;
    menu.style.left = Math.max(8, Math.min(x, W - rect.width - 8)) + 'px';
    menu.style.top = Math.max(8, Math.min(y, H - rect.height - 8)) + 'px';
  }
  function copyText(txt, label) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(function () {
        toast(label + ' copiado', 'info');
      }, function () { toast('Falha ao copiar', 'error'); });
    } else {
      var ta = document.createElement('textarea');
      ta.value = txt;
      ta.style.position = 'fixed';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); toast(label + ' copiado', 'info'); }
      catch (e) { toast('Falha ao copiar', 'error'); }
      document.body.removeChild(ta);
    }
  }
  function getChipText(chip) {
    if (chip.dataset && chip.dataset.alim) return chip.dataset.alim;
    var t = '';
    if (chip.firstChild && chip.firstChild.nodeType === 3) {
      t = chip.firstChild.textContent.trim();
    } else {
      t = chip.textContent.trim();
    }
    return t;
  }
  function getAllChipTexts(chipList) {
    var arr = [];
    chipList.querySelectorAll('.chip').forEach(function (c) {
      var t = getChipText(c);
      if (t) arr.push(t);
    });
    return arr;
  }
  function bindChipMenus() {
    // Hookar todas as .chip-list dentro de tab-cadastro com contextmenu
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    if (scope.__chipCtxBound) return true;
    scope.__chipCtxBound = true;
    scope.addEventListener('contextmenu', function (ev) {
      var chip = ev.target.closest('.chip');
      if (!chip) return;
      var chipList = chip.closest('.chip-list');
      if (!chipList) return;
      ev.preventDefault();
      var texto = getChipText(chip);
      var todos = getAllChipTexts(chipList);
      var items = [];
      if (texto) {
        items.push({
          label: 'Copiar "' + texto + '"',
          icon: 'clipboard',
          action: function () { copyText(texto, texto); },
        });
      }
      if (todos.length > 1) {
        items.push({
          label: 'Copiar todos (' + todos.length + ')',
          icon: 'copy',
          action: function () {
            copyText(todos.join('\n'), todos.length + ' itens');
          },
        });
        items.push({
          label: 'Copiar como CSV (linha unica ;)',
          icon: 'file-text',
          action: function () {
            copyText(todos.join(';'), 'CSV');
          },
        });
      }
      // Remover este chip (clicar no X simula)
      var xBtn = chip.querySelector('.x, [data-lucide="x"]');
      if (xBtn) {
        items.push({
          label: 'Remover "' + texto + '"',
          icon: 'x',
          action: function () {
            var clickTarget = xBtn.closest('i') || xBtn;
            clickTarget.click();
            toast('Removido: ' + texto, 'info');
          },
        });
      }
      // Fase I: avalia este alimentador via criterios_check_alim_por_ganhos.
      // Usa as metricas calculadas pela analise tecnica do proprio backend.
      var api = window.pywebview && window.pywebview.api;
      if (api && api.calc_tensoes && api.calc_carregamento
          && api.calc_contas_contratos && api.criterios_check_alim_por_ganhos) {
        items.push({
          label: 'Avaliar criterios deste alimentador',
          icon: 'check-square',
          action: function () {
            toast('Avaliando ' + texto + '...', 'info');
            // Coleta tensoes/carreg/contas para SO esse alim
            Promise.all([
              api.calc_tensoes([texto]).catch(function () { return null; }),
              api.calc_tensoes_max([texto]).catch(function () { return null; }),
              api.calc_carregamento([texto]).catch(function () { return null; }),
              api.calc_contas_contratos([texto]).catch(function () { return null; }),
            ]).then(function (R) {
              var t = R[0], tx = R[1], c = R[2], cc = R[3];
              var metrics = {
                tensaominima: (t && t.ok && t.tensao_min) || 0,
                tensaomax:    (tx && tx.ok && tx.tensao_max) || 0,
                carregamento: (c && c.ok && c.carregamento) || 0,
                contas:       (cc && cc.ok) ? Math.max(cc.antes||0, cc.depois||0) : 0,
              };
              // Manobra do form (SIM/NAO)
              var scope2 = document.getElementById('tab-cadastro');
              var manFld = scope2 && scope2.querySelectorAll('.field');
              var manobra = '';
              if (manFld) {
                for (var i = 0; i < manFld.length; i++) {
                  var lab = manFld[i].querySelector('label');
                  if (lab && lab.textContent.trim().toLowerCase().indexOf('manobra') === 0) {
                    var n = manFld[i].querySelector('input,select,textarea');
                    if (n) manobra = n.value || '';
                    break;
                  }
                }
              }
              api.criterios_check_alim_por_ganhos(metrics, manobra).then(function (r) {
                if (!(r && r.ok)) {
                  return toast('Falha: ' + (r && r.error || '?'), 'error');
                }
                var label = (r.atende === true) ? 'ATENDE'
                           : (r.atende === false ? 'NAO ATENDE' : 'INSUFICIENTE');
                var lvl = (r.atende === true) ? 'info'
                         : (r.atende === false ? 'error' : 'warn');
                var motivos = (r.motivos || []).join(', ');
                toast(texto + ': ' + label
                      + (motivos ? ' (' + motivos + ')' : ''), lvl);
              });
            });
          },
        });
      }
      if (items.length) openMenu(ev.clientX, ev.clientY, items);
    });
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindChipMenus);
  } else {
    bindChipMenus() || setTimeout(bindChipMenus, 250);
  }
})();
</script>
