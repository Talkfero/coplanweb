<script>
(function () {
  // ---- Section 6 / Passo 6.1 (Resumo / KPIs) ----
  // Substitui os 5 KPIs hardcoded do mock por dados agregados via
  // resumo_kpis(ano). KPIs por posicao em #tab-resumo .kpi-row .kpi:
  //   0=CAPEX | 1=Obras planejadas | 2=Km de rede | 3=Contas | 4=Postergacoes
  function fmtBR(n) {
    return Number(n || 0).toLocaleString('pt-BR');
  }
  // Diretriz Resumo: TODO valor monetario (R$) na aba Resumo e exibido
  // SEMPRE em milhoes (R$ mi), nunca em K/B nem em valor cheio. Helper
  // unico e compartilhado entre os IIFEs do Resumo.
  window.coplanFmtMi = window.coplanFmtMi || function (v, dec) {
    var n = Number(v || 0) / 1e6;
    var d = (dec == null) ? 1 : dec;
    return n.toLocaleString('pt-BR', {
      minimumFractionDigits: d, maximumFractionDigits: d,
    });
  };
  function fmtKm(v) {
    var n = Number(v || 0);
    if (n >= 1000) return n.toLocaleString('pt-BR', {maximumFractionDigits:0});
    return n.toLocaleString('pt-BR', {maximumFractionDigits:1});
  }
  function fmtContas(v) {
    var n = Number(v || 0);
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace('.', ',') + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace('.', ',') + 'K';
    return fmtBR(n);
  }
  function setKpi(grid, idx, label, value, unit) {
    if (!grid) return;
    var card = grid.children[idx];
    if (!card) return;
    var labelEl = card.querySelector('.kpi-label');
    var valueEl = card.querySelector('.kpi-value');
    var unitEl = card.querySelector('.kpi-unit');
    if (labelEl && label != null) labelEl.textContent = label;
    if (valueEl) {
      // Preserva o <span class="kpi-unit"> dentro do .kpi-value
      // se ja existir.
      if (unitEl) {
        valueEl.firstChild && (valueEl.firstChild.nodeValue = value + ' ');
        unitEl.textContent = unit || '';
      } else if (unit) {
        valueEl.innerHTML = value + ' <span class="kpi-unit">' + unit + '</span>';
      } else {
        valueEl.textContent = value;
      }
    }
  }
  window.coplanRenderKpis = function (s) {
    if (!s || !s.ok) return;
    var grid = document.querySelector('#tab-resumo .kpi-row');
    if (!grid) return;
    var anoLbl = s.ano || s.ano_dominante || '';
    setKpi(grid, 0, 'CAPEX' + (anoLbl ? ' ' + anoLbl : ''),
           window.coplanFmtMi(s.capex_total), 'M R$');
    setKpi(grid, 1, 'Obras planejadas', fmtBR(s.obras_total), '');
    setKpi(grid, 2, 'Km de rede', fmtKm(s.km_total), 'km');
    setKpi(grid, 3, 'Contas beneficiadas', fmtContas(s.contas_beneficiadas), '');
    setKpi(grid, 4, 'Postergacoes', fmtBR(s.postergacoes), '');
  };
  window.coplanLoadKpis = function (ano) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.resumo_kpis)) return Promise.resolve();
    var cods = (typeof window.coplanFilteredCods === 'function')
      ? window.coplanFilteredCods() : null;
    return api.resumo_kpis(ano || '', cods).then(function (s) {
      window.__coplanResumoKpis = s;
      window.coplanRenderKpis(s);
    }).catch(function (e) {
      console.warn('[coplan] resumo_kpis catch:', e);
    });
  };

  // Lazy load ao entrar em Resumo + recarrega depois de save/delete.
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') {
      window.coplanLoadKpis('');
    }
  });
  document.addEventListener('coplan:obras', function () {
    var resumo = document.getElementById('tab-resumo');
    if (resumo && resumo.classList.contains('active')) {
      window.coplanLoadKpis('');
    }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      var resumo = document.getElementById('tab-resumo');
      if (resumo && resumo.classList.contains('active')) {
        window.coplanLoadKpis('');
      }
    });
  } else {
    var resumo = document.getElementById('tab-resumo');
    if (resumo && resumo.classList.contains('active')) {
      window.coplanLoadKpis('');
    }
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 6.2 (Resumo / Volumetria por Regional) ----
  // Substitui a const VOL e o renderBar() do mock por dados reais
  // vindos de resumo_volumetria_regional. Mantem o mesmo template de
  // .bar-item / .bar-track / .bar-fill / .bar-value usado pelo CSS.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  window.coplanRenderBar = function (state) {
    var box = document.getElementById('bar-chart');
    if (!box || !state || !state.ok) return;
    var items = state.items || [];
    if (!items.length) {
      box.innerHTML = '<div style="padding:12px;color:var(--text-soft);font-size:12.5px;">'
                    + 'Sem dados regionais para exibir.</div>';
      return;
    }
    // Compartilhamos o cache para Passo 6.4 (tabela completa).
    window.__coplanResumoVol = items;
    var max = Math.max.apply(null, items.map(function (it) {
      return Number(it.valor || 0);
    }));
    if (!max || max <= 0) max = 1;
    box.innerHTML = items.map(function (v) {
      var pct = (Number(v.valor || 0) / max * 100).toFixed(1);
      return '<div class="bar-item">'
           +   '<span style="font-weight:500;">' + esc(v.regional) + '</span>'
           +   '<div class="bar-track"><div class="bar-fill" style="width:'
           +     pct + '%"></div></div>'
           +   '<span class="bar-value">R$ ' + esc(window.coplanFmtMi(v.valor)) + ' mi</span>'
           + '</div>';
    }).join('');
    document.dispatchEvent(new CustomEvent('coplan:resumo:vol',
      { detail: items }));
  };
  window.coplanLoadVol = function (ano) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.resumo_volumetria_regional)) return Promise.resolve();
    var cods = (typeof window.coplanFilteredCods === 'function')
      ? window.coplanFilteredCods() : null;
    return api.resumo_volumetria_regional(ano || '', cods).then(function (s) {
      window.coplanRenderBar(s);
    }).catch(function (e) {
      console.warn('[coplan] resumo_volumetria_regional catch:', e);
    });
  };

  // Wire no botao Exportar do card (mock tinha texto "Exportar").
  function bindExport() {
    var box = document.getElementById('bar-chart');
    if (!box) return;
    var card = box.closest('.card');
    if (!card) return;
    var btns = card.querySelectorAll('.card-header .btn');
    for (var i = 0; i < btns.length; i++) {
      var t = btns[i].textContent.trim().toLowerCase();
      if (t.indexOf('exportar') === 0 && !btns[i].__pivoted) {
        btns[i].__pivoted = true;
        btns[i].addEventListener('click', function () {
          // Reusa export_detalhamento que ja gera xlsx.
          var api = window.pywebview && window.pywebview.api;
          if (!(api && api.export_detalhamento)) {
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('API indisponivel', 'error');
            }
            return;
          }
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Exportando volumetria...', 'info');
          }
          api.export_detalhamento([]).then(function (r) {
            if (r && r.ok && typeof window.coplanToast === 'function') {
              window.coplanToast('XLSX salvo: ' + r.path, 'info');
            } else if (r && typeof window.coplanToast === 'function') {
              window.coplanToast('Falha: ' + (r.error || '?'), 'error');
            }
          }).catch(function (err) {
            if (typeof window.coplanToast === 'function') {
              window.coplanToast(
                'Falha: ' + (err && err.message || err || '?'), 'error');
            }
          });
        });
      }
    }
  }

  function maybeLoadVol() {
    var resumo = document.getElementById('tab-resumo');
    if (resumo && resumo.classList.contains('active')) {
      window.coplanLoadVol('');
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') {
      window.coplanLoadVol('');
    }
  });
  document.addEventListener('coplan:obras', function () {
    maybeLoadVol();
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      bindExport();
      maybeLoadVol();
    });
  } else {
    bindExport();
    maybeLoadVol();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 6.3 (Resumo / Pacotes) ----
  // Substitui as 6 linhas hardcoded do card "Pacotes" por dados reais
  // de pacotes_distribution. Mantem o template .legend-dot + label +
  // .mono "X% · R$ YM".
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function findPacotesCard() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return null;
    var titles = scope.querySelectorAll('.card .card-title');
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf('pacotes') === 0) {
        return titles[i].closest('.card');
      }
    }
    return null;
  }
  window.coplanRenderPacotes = function (state) {
    var card = findPacotesCard();
    if (!card || !state || !state.ok) return;
    var body = card.querySelector('.card-body');
    if (!body) return;
    var items = state.items || [];
    if (!items.length) {
      body.innerHTML = '<div style="padding:6px 4px;color:var(--text-soft);font-size:12.5px;">'
                     + 'Nenhum pacote computado.</div>';
      return;
    }
    var html = '<div style="display:flex;flex-direction:column;gap:10px;">';
    items.forEach(function (it) {
      var pct = (it.pct == null ? 0 : Number(it.pct)).toFixed(0);
      html += '<div class="row" style="justify-content:space-between;font-size:12.5px;">'
            +   '<span><span class="legend-dot" style="color:'
            +     esc(it.color || 'var(--text-soft)') + ';"></span> '
            +     esc(it.label) + '</span>'
            +   '<span class="mono">' + pct + '% · R$ '
            +     esc(window.coplanFmtMi(it.valor)) + ' mi</span>'
            + '</div>';
    });
    html += '</div>';
    body.innerHTML = html;
  };
  window.coplanLoadPacotes = function (ano) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.pacotes_distribution)) return Promise.resolve();
    var cods = (typeof window.coplanFilteredCods === 'function')
      ? window.coplanFilteredCods() : null;
    return api.pacotes_distribution(ano || '', cods).then(function (s) {
      window.__coplanResumoPacotes = s;
      window.coplanRenderPacotes(s);
    }).catch(function (e) {
      console.warn('[coplan] pacotes_distribution catch:', e);
    });
  };

  function maybeLoad() {
    var resumo = document.getElementById('tab-resumo');
    if (resumo && resumo.classList.contains('active')) {
      window.coplanLoadPacotes('');
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') {
      window.coplanLoadPacotes('');
    }
  });
  document.addEventListener('coplan:obras', maybeLoad);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', maybeLoad);
  } else {
    maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 6.4 (Resumo / Quadro de Volumetria & Financeiro) ----
  // Substitui o renderVol() do mock (#vol-tbody) por dados reais e
  // tambem reescreve o <tfoot> com a linha TOTAL agregada via medias
  // ponderadas no servidor.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function fmt(n, dec) {
    var v = Number(n || 0);
    if (isNaN(v)) return '--';
    return v.toLocaleString('pt-BR', {
      minimumFractionDigits: dec == null ? 0 : dec,
      maximumFractionDigits: dec == null ? 0 : dec,
    });
  }
  function rowHtml(it) {
    return '<tr>'
      +   '<td>' + esc(it.regional || '') + '</td>'
      +   '<td class="num mono">' + fmt(it.obras) + '</td>'
      +   '<td class="num mono">' + fmt(it.km, 0) + '</td>'
      +   '<td class="num mono">' + fmt(it.tensao, 3) + '</td>'
      +   '<td class="num mono">' + fmt(it.chi, 2) + '</td>'
      +   '<td class="num mono">' + fmt(it.ci, 2) + '</td>'
      +   '<td class="num mono">' + fmt(it.carreg, 1) + '</td>'
      +   '<td class="num mono">' + fmt(it.contas) + '</td>'
      +   '<td class="num mono">' + window.coplanFmtMi(it.valor) + '</td>'
      + '</tr>';
  }
  function findVolTable() {
    var tbody = document.getElementById('vol-tbody');
    return tbody ? tbody.closest('table') : null;
  }
  window.coplanRenderVolTable = function (state) {
    var tbody = document.getElementById('vol-tbody');
    if (!tbody || !state || !state.ok) return;
    var items = state.items || [];
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="padding:18px;text-align:center;color:var(--text-soft);">'
                      + 'Sem dados regionais.</td></tr>';
    } else {
      tbody.innerHTML = items.map(rowHtml).join('');
    }
    // Substitui o tfoot por TOTAL real.
    var table = findVolTable();
    if (table) {
      var foot = table.querySelector('tfoot');
      var totalHtml = '';
      if (state.total) {
        var t = state.total;
        totalHtml = '<tr style="background:var(--surface-2);font-weight:600;">'
          +   '<td>Total</td>'
          +   '<td class="num mono">' + fmt(t.obras) + '</td>'
          +   '<td class="num mono">' + fmt(t.km, 0) + '</td>'
          +   '<td class="num mono">' + fmt(t.tensao, 3) + '</td>'
          +   '<td class="num mono">' + fmt(t.chi, 2) + '</td>'
          +   '<td class="num mono">' + fmt(t.ci, 2) + '</td>'
          +   '<td class="num mono">' + fmt(t.carreg, 1) + '</td>'
          +   '<td class="num mono">' + fmt(t.contas) + '</td>'
          +   '<td class="num mono">' + window.coplanFmtMi(t.valor) + '</td>'
          + '</tr>';
      }
      if (foot) foot.innerHTML = totalHtml;
    }
    // Atualiza tambem o card-sub "Atualizado em ..." com timestamp atual.
    var card = (tbody.closest('.card'));
    if (card) {
      var sub = card.querySelector('.card-sub');
      if (sub) {
        var d = new Date();
        var pad = function (n) { return String(n).padStart(2, '0'); };
        sub.textContent = 'Atualizado em ' + pad(d.getDate()) + '/'
          + pad(d.getMonth() + 1) + '/' + d.getFullYear() + ' '
          + pad(d.getHours()) + ':' + pad(d.getMinutes());
      }
    }
  };
  window.coplanLoadVolTable = function (ano) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.resumo_regional_table)) return Promise.resolve();
    var cods = (typeof window.coplanFilteredCods === 'function')
      ? window.coplanFilteredCods() : null;
    return api.resumo_regional_table(ano || '', cods).then(function (s) {
      window.__coplanResumoTable = s;
      window.coplanRenderVolTable(s);
    }).catch(function (e) {
      console.warn('[coplan] resumo_regional_table catch:', e);
    });
  };

  function maybeLoad() {
    var resumo = document.getElementById('tab-resumo');
    if (resumo && resumo.classList.contains('active')) {
      window.coplanLoadVolTable('');
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') {
      window.coplanLoadVolTable('');
    }
  });
  document.addEventListener('coplan:obras', maybeLoad);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', maybeLoad);
  } else {
    maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Fase A7 (Resumo / Detalhamento -- botao Exportar Resumo) ----
  // Adiciona um botao "Exportar Resumo Detalhamento" na subnav
  // "Detalhamento" do Resumo. Chama export_resumo_detalhamento que
  // delega 100% para core.services.resumo_service.montar_resumo_detalhamento
  // e gera um XLSX agrupado por (nome_projeto, ano, pacote) com
  // antes/depois por alimentador.
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function ensureBar() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return null;
    var bar = document.getElementById('coplan-detalhamento-bar');
    if (bar) return bar;
    bar = document.createElement('div');
    bar.id = 'coplan-detalhamento-bar';
    bar.className = 'row';
    bar.style.cssText = 'gap:8px;align-items:center;margin:8px 0;';
    bar.innerHTML =
      '<span style="color:var(--text-soft);font-size:12px;">'
    +   'Exporta XLSX agrupado por projeto/ano/pacote com'
    +   ' antes/depois por alimentador.'
    + '</span>'
    + '<button id="coplan-btn-exp-resumo-det" class="btn" '
    +         'style="margin-left:auto;">'
    +   '<i data-lucide="file-spreadsheet"></i> Exportar Resumo Detalhamento'
    + '</button>';
    // Insere antes da tableCard "Quadro de Volumetria".
    var anchor = null;
    scope.querySelectorAll('.card').forEach(function (c) {
      var t = c.querySelector('.card-title');
      if (!t) return;
      var n = norm(t.textContent);
      if (n.indexOf('quadro de volumetria') === 0 && !anchor) anchor = c;
    });
    if (anchor && anchor.parentElement) {
      anchor.parentElement.insertBefore(bar, anchor);
    } else {
      scope.appendChild(bar);
    }
    if (window.lucide) lucide.createIcons();
    return bar;
  }
  function isDetView() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return false;
    var act = scope.querySelector('.subnav .subnav-tab.active');
    if (!act) return false;
    return norm(act.textContent).indexOf('detalhamento') === 0;
  }
  function applyVisibility() {
    var bar = document.getElementById('coplan-detalhamento-bar');
    if (!bar) return;
    bar.style.display = isDetView() ? 'flex' : 'none';
  }
  function bind() {
    var bar = ensureBar();
    if (!bar) return false;
    var btn = bar.querySelector('#coplan-btn-exp-resumo-det');
    if (btn && !btn.__bound) {
      btn.__bound = true;
      btn.addEventListener('click', function () {
        var api = window.pywebview && window.pywebview.api;
        if (!(api && api.export_resumo_detalhamento)) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('API indisponivel', 'error');
          }
          return;
        }
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Gerando resumo de detalhamento...', 'info');
        }
        api.export_resumo_detalhamento(null).then(function (r) {
          if (r && r.ok) {
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('XLSX salvo: ' + r.path
                                 + ' (' + r.count + ' linhas)', 'info');
            }
          } else {
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Falhou: '
                + (r && r.error || '?'), 'error');
            }
          }
        });
      });
    }
    applyVisibility();
    return true;
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') bind();
  });
  document.addEventListener('click', function (ev) {
    var t = ev.target;
    if (t && t.classList && t.classList.contains('subnav-tab')) {
      setTimeout(applyVisibility, 0);
    }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
</script>
<script>
(function () {
  // ---- Fase A4 (Resumo / Volumetria por PI x Ano) ----
  // Injeta uma card "Volumetria por PI x Ano" no tab-resumo e a popula
  // via api.resumo_volumetria_financeiro (delega pro core via
  // resumo_service.montar_volumetria_financeiro). So fica visivel na
  // subnav "Volumetria & Financeiro".
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({
        '<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'
      })[c];
    });
  }
  // Reverte o pt-BR ('1.234,56') de volta a Number para reexibir em milhoes.
  function parseBR(s) {
    var t = String(s == null ? '' : s).trim();
    if (!t || t === '-') return 0;
    return parseFloat(t.replace(/\./g, '').replace(',', '.')) || 0;
  }
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function ensureCard() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return null;
    var card = document.getElementById('coplan-vol-pi-card');
    if (card) return card;
    card = document.createElement('div');
    card.id = 'coplan-vol-pi-card';
    card.className = 'card';
    card.innerHTML =
      '<div class="card-header">'
    +   '<div class="card-title"><i data-lucide="layers"></i> Volumetria por PI x Ano</div>'
    + '</div>'
    + '<div class="card-body">'
    +   '<div class="table-scroll" style="max-height:360px;overflow:auto;">'
    +     '<table class="data-table" id="coplan-vol-pi-table">'
    +       '<thead><tr><th>PI</th></tr></thead>'
    +       '<tbody id="coplan-vol-pi-tbody"></tbody>'
    +     '</table>'
    +   '</div>'
    + '</div>';
    // Injeta antes do primeiro card existente para ficar visivel acima.
    // Se houver tableCard "Quadro de Volumetria", injeta logo antes dele.
    var anchor = null;
    var cards = scope.querySelectorAll('.card');
    cards.forEach(function (c) {
      var t = c.querySelector('.card-title');
      if (!t) return;
      var n = norm(t.textContent);
      if (n.indexOf('quadro de volumetria') === 0 && !anchor) anchor = c;
    });
    if (anchor && anchor.parentElement) {
      anchor.parentElement.insertBefore(card, anchor);
    } else {
      scope.appendChild(card);
    }
    if (window.lucide) lucide.createIcons();
    return card;
  }
  function render(state) {
    var card = ensureCard();
    if (!card || !state) return;
    var thead = card.querySelector('thead');
    var tbody = card.querySelector('tbody');
    if (!thead || !tbody) return;
    if (!state.ok) {
      thead.innerHTML = '<tr><th>PI</th></tr>';
      tbody.innerHTML = '<tr><td style="padding:14px;color:var(--danger);">'
                      + esc(state.error || 'Falha ao carregar volumetria')
                      + '</td></tr>';
      return;
    }
    var heads = state.cabecalhos || ['PI'];
    // Colunas 'Valor' sao monetarias -> exibidas em milhoes (R$ mi).
    // 'Fisico' (km) nao se converte.
    var isValor = heads.map(function (h) {
      return String(h).indexOf('Valor') >= 0;
    });
    var theadHtml = '<tr>';
    heads.forEach(function (h, i) {
      var cls = (i === 0) ? '' : 'class="num"';
      var htxt = isValor[i]
        ? String(h).replace('Valor', 'Valor (R$ mi)') : h;
      var label = esc(htxt).replace(new RegExp("\n", "g"), '<br>');
      theadHtml += '<th ' + cls + '>' + label + '</th>';
    });
    theadHtml += '</tr>';
    thead.innerHTML = theadHtml;
    var linhas = state.linhas || [];
    if (!linhas.length) {
      tbody.innerHTML = '<tr><td colspan="' + heads.length
                      + '" style="padding:18px;text-align:center;color:var(--text-soft);">'
                      + 'Sem dados para este ano.</td></tr>';
      return;
    }
    tbody.innerHTML = linhas.map(function (linha) {
      return '<tr>' + linha.map(function (cel, i) {
        var cls = (i === 0) ? '' : 'class="num mono"';
        var out = isValor[i] ? window.coplanFmtMi(parseBR(cel)) : cel;
        return '<td ' + cls + '>' + esc(out) + '</td>';
      }).join('') + '</tr>';
    }).join('');
  }
  function isVolView() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return false;
    var act = scope.querySelector('.subnav .subnav-tab.active');
    if (!act) return true;  // sem subnav: assume volumetria
    return norm(act.textContent).indexOf('volumetria') === 0;
  }
  function applyVisibility() {
    var card = document.getElementById('coplan-vol-pi-card');
    if (!card) return;
    card.style.display = isVolView() ? '' : 'none';
  }
  window.coplanLoadVolPi = function (ano) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.resumo_volumetria_financeiro)) return Promise.resolve();
    var cods = (typeof window.coplanFilteredCods === 'function')
      ? window.coplanFilteredCods() : null;
    return api.resumo_volumetria_financeiro(ano || '', cods).then(function (s) {
      window.__coplanResumoVolPi = s;
      render(s);
      applyVisibility();
    }).catch(function (e) {
      console.warn('[coplan] resumo_volumetria_financeiro catch:', e);
    });
  };
  function maybeLoad() {
    var resumo = document.getElementById('tab-resumo');
    if (resumo && resumo.classList.contains('active')) {
      window.coplanLoadVolPi('');
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') {
      window.coplanLoadVolPi('');
    }
  });
  document.addEventListener('coplan:obras', maybeLoad);
  // Re-aplica visibilidade quando subnav muda (Passo 6.5 dispara via click).
  document.addEventListener('click', function (ev) {
    var t = ev.target;
    if (t && t.classList && t.classList.contains('subnav-tab')) {
      setTimeout(applyVisibility, 0);
    }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', maybeLoad);
  } else {
    maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Fase A6 (Resumo / Resumo de Ganhos por Projeto) ----
  // Injeta uma card "Resumo de Ganhos por Projeto" no tab-resumo,
  // com select de nome_projeto + tabela por alimentador. Visivel
  // apenas na subnav "Resumo Regional".
  // Usa resumo_ganhos_projeto + list_projetos (delega 100% para
  // core.services.resumo_service.montar_resumo_ganhos_projeto).
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function ensureCard() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return null;
    var card = document.getElementById('coplan-resumo-projeto-card');
    if (card) return card;
    card = document.createElement('div');
    card.id = 'coplan-resumo-projeto-card';
    card.className = 'card';
    card.innerHTML =
      '<div class="card-header">'
    +   '<div class="card-title">'
    +     '<i data-lucide="folder-tree"></i>'
    +     ' Resumo de Ganhos por Projeto'
    +   '</div>'
    + '</div>'
    + '<div class="card-body">'
    +   '<div class="row" style="gap:8px;align-items:center;">'
    +     '<label style="min-width:130px;color:var(--text-soft);font-size:12px;">'
    +       'Nome do Projeto'
    +     '</label>'
    +     '<select id="coplan-resumo-projeto-sel" '
    +             'style="flex:1;min-width:220px;"></select>'
    +     '<span id="coplan-resumo-projeto-sub" '
    +           'style="color:var(--text-soft);font-size:12px;"></span>'
    +   '</div>'
    +   '<div class="table-scroll" style="max-height:300px;overflow:auto;margin-top:8px;">'
    +     '<table class="data-table">'
    +       '<thead><tr>'
    +         '<th>Alimentador</th>'
    +         '<th class="num">Carregamento</th>'
    +         '<th class="num">Tensao Min | Max</th>'
    +         '<th class="num">Clientes</th>'
    +       '</tr></thead>'
    +       '<tbody id="coplan-resumo-projeto-tbody">'
    +         '<tr><td colspan="4" style="padding:14px;text-align:center;color:var(--text-soft);">'
    +         'Selecione um projeto.</td></tr>'
    +       '</tbody>'
    +     '</table>'
    +   '</div>'
    + '</div>';
    // Insere antes do "Quadro de Volumetria" se existir.
    var anchor = null;
    scope.querySelectorAll('.card').forEach(function (c) {
      var t = c.querySelector('.card-title');
      if (!t) return;
      var n = norm(t.textContent);
      if (n.indexOf('quadro de volumetria') === 0 && !anchor) anchor = c;
    });
    if (anchor && anchor.parentElement) {
      anchor.parentElement.insertBefore(card, anchor);
    } else {
      scope.appendChild(card);
    }
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
    var tbody = card.querySelector('#coplan-resumo-projeto-tbody');
    var sub = card.querySelector('#coplan-resumo-projeto-sub');
    if (!tbody) return;
    if (!state || !state.ok) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding:14px;color:var(--danger);">'
                      + esc((state && state.error) || 'Sem dados')
                      + '</td></tr>';
      if (sub) sub.textContent = '';
      return;
    }
    var linhas = state.linhas || [];
    if (!linhas.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding:18px;text-align:center;color:var(--text-soft);">'
                      + 'Sem alimentadores neste projeto.</td></tr>';
    } else {
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
    }
    if (sub) {
      sub.textContent = (state.obras_count || 0) + ' obra(s) / '
                      + linhas.length + ' alim';
    }
  }
  function loadProjetos() {
    var card = ensureCard();
    if (!card) return Promise.resolve();
    var sel = card.querySelector('#coplan-resumo-projeto-sel');
    var api = window.pywebview && window.pywebview.api;
    if (!(sel && api && api.list_projetos)) return Promise.resolve();
    return api.list_projetos().then(function (r) {
      var items = (r && r.items) || [];
      var html = '<option value="">— selecione —</option>';
      items.forEach(function (n) {
        html += '<option value="' + esc(n) + '">' + esc(n) + '</option>';
      });
      var prev = sel.value;
      sel.innerHTML = html;
      if (prev) sel.value = prev;
    }).catch(function (e) {
      console.warn('[coplan] list_projetos:', e);
    });
  }
  function isRegionalView() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return false;
    var act = scope.querySelector('.subnav .subnav-tab.active');
    if (!act) return false;
    return norm(act.textContent).indexOf('regional') === 0;
  }
  function applyVisibility() {
    var card = document.getElementById('coplan-resumo-projeto-card');
    if (!card) return;
    card.style.display = isRegionalView() ? '' : 'none';
  }
  function bind() {
    var card = ensureCard();
    if (!card) return false;
    var sel = card.querySelector('#coplan-resumo-projeto-sel');
    if (sel && !sel.__bound) {
      sel.__bound = true;
      sel.addEventListener('change', function () {
        var nome = sel.value;
        if (!nome) {
          render({ok: true, linhas: [], obras_count: 0});
          return;
        }
        var api = window.pywebview && window.pywebview.api;
        if (!(api && api.resumo_ganhos_projeto)) return;
        api.resumo_ganhos_projeto(nome).then(render).catch(function (err) {
          console.warn('[coplan] resumo_ganhos_projeto falhou:', err);
          var msg = 'Falha ao carregar resumo do projeto: '
            + ((err && err.message) || err || '?');
          if (typeof window.coplanToast === 'function') {
            window.coplanToast(msg, 'error');
          }
          if (window.coplanReportError) {
            window.coplanReportError(
              'Resumo de Ganhos por Projeto', 'resumo_ganhos_projeto',
              { projeto: nome,
                error: String((err && err.message) || err || '?') });
          }
          render({ok: false,
                  error: (err && err.message) || String(err) || 'Falha ao carregar'});
        });
      });
    }
    return true;
  }
  function maybeLoad() {
    var resumo = document.getElementById('tab-resumo');
    if (resumo && resumo.classList.contains('active')) {
      loadProjetos().then(applyVisibility);
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') {
      ensureCard();
      bind();
      loadProjetos().then(applyVisibility);
    }
  });
  document.addEventListener('coplan:obras', function () {
    if (document.getElementById('tab-resumo')
        && document.getElementById('tab-resumo').classList.contains('active')) {
      loadProjetos().then(applyVisibility);
    }
  });
  document.addEventListener('click', function (ev) {
    var t = ev.target;
    if (t && t.classList && t.classList.contains('subnav-tab')) {
      setTimeout(applyVisibility, 0);
    }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { ensureCard(); bind(); maybeLoad(); });
  } else {
    ensureCard(); bind(); maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 6.5 (Resumo / subnav) ----
  // 3 abas no .subnav do Resumo: ['Volumetria & Financeiro',
  // 'Resumo Regional', 'Detalhamento']. Como o mock so renderizou
  // conteudo para a 1a, alternamos a visibilidade dos blocos existentes:
  //   * Volumetria : KPIs + bar chart + Pacotes + Tabela completa
  //   * Regional   : bar chart + Tabela completa (sem KPIs e Pacotes)
  //   * Detalhamento : so a Tabela completa (modo expansivo)
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  // Resolve elementos uma vez (cache).
  function findResumoBlocks() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return null;
    var kpiRow = scope.querySelector('.kpi-row');
    var volGrid = null, pacotesCard = null, barCard = null, tableCard = null;
    var cards = scope.querySelectorAll('.card');
    cards.forEach(function (c) {
      var t = c.querySelector('.card-title');
      if (!t) return;
      var n = norm(t.textContent);
      if (n.indexOf('volumetria por regional') === 0) barCard = c;
      else if (n.indexOf('pacotes') === 0) pacotesCard = c;
      else if (n.indexOf('quadro de volumetria') === 0) tableCard = c;
    });
    // .vol-grid no mock e' o container que abraca bar+pacotes (2 colunas).
    if (barCard) volGrid = barCard.parentElement;
    return {
      scope: scope, kpiRow: kpiRow, volGrid: volGrid,
      barCard: barCard, pacotesCard: pacotesCard, tableCard: tableCard,
    };
  }
  function setVisible(node, visible) {
    if (!node) return;
    if (visible) {
      // Restaura display original (remove inline none).
      if (node.style.display === 'none') node.style.display = '';
    } else {
      node.style.display = 'none';
    }
  }
  function applyView(view) {
    var b = findResumoBlocks();
    if (!b) return;
    var v = norm(view);
    var showKpis = v.indexOf('volumetria') === 0;
    var showVolGrid = (v.indexOf('volumetria') === 0
                    || v.indexOf('regional') === 0);
    var showPacotes = v.indexOf('volumetria') === 0;
    var showBar = (v.indexOf('volumetria') === 0
                || v.indexOf('regional') === 0);
    var showTable = true;  // sempre

    setVisible(b.kpiRow, showKpis);
    // Se temos volGrid (container das 2 cards bar+pacotes) e NEnhuma
    // for visivel, escondemos o grid inteiro. Caso contrario, garantimos
    // visibilidade individual dos cards filhos.
    if (b.volGrid && !showBar && !showPacotes) {
      setVisible(b.volGrid, false);
    } else if (b.volGrid) {
      setVisible(b.volGrid, true);
      setVisible(b.barCard, showBar);
      setVisible(b.pacotesCard, showPacotes);
    }
    setVisible(b.tableCard, showTable);

    // Modo Detalhamento: aumenta max-height da tabela para uso completo
    // (mock tem max-height: 360px na .table-scroll).
    if (b.tableCard) {
      var scroll = b.tableCard.querySelector('.table-scroll');
      if (scroll) {
        scroll.style.maxHeight = (v.indexOf('detalhamento') === 0)
          ? 'calc(100vh - 220px)' : '';
      }
    }
    // Atualiza titulo do tableCard pra refletir a aba ativa (UX hint).
    if (b.tableCard) {
      var title = b.tableCard.querySelector('.card-title');
      if (title) {
        var iconHtml = title.querySelector('i') ? title.querySelector('i').outerHTML : '';
        var label = (v.indexOf('detalhamento') === 0)
          ? 'Detalhamento por Regional'
          : (v.indexOf('regional') === 0
              ? 'Resumo Regional'
              : 'Quadro de Volumetria & Financeiro');
        title.innerHTML = iconHtml + ' ' + label;
      }
    }
  }

  function bindSubnav() {
    var scope = document.getElementById('tab-resumo');
    if (!scope) return false;
    var subnav = scope.querySelector('.subnav');
    if (!subnav) return false;
    var tabs = subnav.querySelectorAll('.subnav-tab');
    if (!tabs.length) return false;
    tabs.forEach(function (t) {
      if (t.__pivoted) return;
      t.__pivoted = true;
      t.addEventListener('click', function () {
        tabs.forEach(function (o) { o.classList.remove('active'); });
        t.classList.add('active');
        applyView(t.textContent);
      });
    });
    // Aplica a aba inicial ja marcada como .active no mock.
    var active = subnav.querySelector('.subnav-tab.active') || tabs[0];
    if (active) applyView(active.textContent);
    return true;
  }

  // Tambem aplica quando entra na aba Resumo (caso ja tenha alterado
  // antes e voltado). Garante consistencia visual.
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'resumo') {
      var scope = document.getElementById('tab-resumo');
      if (!scope) return;
      var active = scope.querySelector('.subnav-tab.active');
      if (active) applyView(active.textContent);
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindSubnav);
  } else {
    if (!bindSubnav()) setTimeout(bindSubnav, 50);
  }
})();
</script>
