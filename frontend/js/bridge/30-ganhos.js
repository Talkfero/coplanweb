<script>
(function () {
  // ---- F16 - Atualizar Projeto navegacional ----
  // Replica iniciar_atualizacao_projeto + prev/next/finalizar/cancelar
  // do desktop (AtualizarObraMixin).
  // Estado em window.__coplanProjetoMode = {
  //   nome, pacote, obras: [...], cods: [...], index, edited: {cod:dict},
  //   columns: [...], total
  // }
  // Fluxo:
  //   1. coplanIniciarAtualizacaoProjeto(nome, pacote) -> chama API,
  //      mostra barra, troca aba, carrega 1a obra no form
  //   2. Anterior/Proxima salvam snapshot do form em edited[cod] e
  //      navegam (carregando obra do index novo via coplanLoadObraIntoForm)
  //   3. Finalizar percorre edited e chama save_obra para cada cod
  //   4. Cancelar descarta edited e some
  function api() { return window.pywebview && window.pywebview.api; }
  function toast(msg, lvl) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, lvl || 'info');
    } else {
      console.log('[F16]', lvl, msg);
    }
  }
  function $(id) { return document.getElementById(id); }
  function setBar(state) {
    var bar = $('cad-projeto-nav-bar');
    if (!bar) return;
    if (!state) {
      bar.style.display = 'none';
      return;
    }
    bar.style.display = 'flex';
    var info = $('cad-projeto-nav-info');
    if (info) {
      var cod = state.cods[state.index] || '?';
      var editCount = Object.keys(state.edited || {}).length;
      info.innerHTML = '<strong>' + escHtml(state.nome) + '</strong>'
        + (state.pacote ? ' / ' + escHtml(state.pacote) : '')
        + ' &nbsp;|&nbsp; Obra <strong>' + (state.index + 1)
        + '</strong> de ' + state.total
        + ' &nbsp;|&nbsp; COD: <code>' + escHtml(cod) + '</code>'
        + ' &nbsp;|&nbsp; '
        + editCount + ' editada(s)';
    }
    var prev = $('cad-projeto-nav-prev');
    var next = $('cad-projeto-nav-next');
    var fin = $('cad-projeto-nav-finalizar');
    if (prev) prev.disabled = (state.index <= 0);
    if (next) next.disabled = (state.index >= state.total - 1);
    if (fin) {
      fin.style.display = (state.index === state.total - 1) ? '' : 'none';
    }
  }
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function snapshotForm() {
    // Captura valores atuais do form Cadastro como dict {col: value}.
    // Usa SAVE_FIELDS se exposto globalmente; caso contrario faz uma
    // varredura por .field > input/select com data-col ou label.
    if (typeof window.coplanReadCadastroForm === 'function') {
      return window.coplanReadCadastroForm();
    }
    // Fallback: captura via labels dos campos visiveis em #tab-cadastro
    var out = {};
    var fields = document.querySelectorAll('#tab-cadastro .field');
    fields.forEach(function (f) {
      var lab = f.querySelector('label');
      if (!lab) return;
      var clone = lab.cloneNode(true);
      clone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var key = clone.textContent.trim();
      var inp = f.querySelector('input, select, textarea');
      if (!inp || !key) return;
      var v = (inp.tagName === 'SELECT' && inp.options[inp.selectedIndex])
        ? inp.options[inp.selectedIndex].text
        : (inp.value || '');
      out[key] = String(v).trim();
    });
    return out;
  }
  function navigate(dir) {
    var s = window.__coplanProjetoMode;
    if (!s) return;
    // Salva snapshot da obra ATUAL antes de mover
    var curCod = s.cods[s.index];
    if (curCod) {
      s.edited[curCod] = snapshotForm();
    }
    var newIdx = s.index + (dir > 0 ? 1 : -1);
    if (newIdx < 0 || newIdx >= s.total) return;
    s.index = newIdx;
    setBar(s);
    var nextCod = s.cods[newIdx];
    // Carrega obra no form (reusa coplanLoadObraIntoForm do passo 4.1)
    if (typeof window.coplanLoadObraIntoForm === 'function') {
      window.coplanLoadObraIntoForm(nextCod);
    } else {
      window.__coplanEditingCod = nextCod;
      // Tenta via get_obra direto se loadObra nao existe
      var a = api();
      if (a && a.get_obra) {
        a.get_obra(nextCod).then(function (r) {
          if (r && r.ok && typeof window.coplanFillCadastroForm === 'function') {
            window.coplanFillCadastroForm(r.obra || {});
          }
        }).catch(function (e) {
          console.warn('[coplan/cadastro] get_obra navigation catch:', e);
          toast('Falha ao carregar obra do projeto: ' + (e && e.message || e), 'error');
        });
      }
    }
  }
  function finalizar() {
    var s = window.__coplanProjetoMode;
    if (!s) return;
    // Snapshot da obra atual
    var curCod = s.cods[s.index];
    if (curCod) {
      s.edited[curCod] = snapshotForm();
    }
    var keys = Object.keys(s.edited || {});
    if (!keys.length) {
      if (!window.confirm('Nenhuma obra foi editada. Finalizar mesmo assim'
                          + ' (sem salvar)?')) return;
      cleanup();
      return;
    }
    if (!window.confirm('Salvar ' + keys.length + ' obra(s) editada(s)?'
                        + '\n\n' + keys.join(', '))) return;
    var a = api();
    if (!(a && a.save_obra)) {
      toast('API save_obra indisponivel', 'error');
      return;
    }
    toast('Salvando ' + keys.length + ' obra(s)...', 'info');
    var ok = 0, falhas = [];
    var promises = keys.map(function (cod) {
      var dados = Object.assign({}, s.edited[cod]);
      // Garante que o COD esta no payload
      if (!dados.cod && !dados.COD) dados.cod = cod;
      return a.save_obra(dados).then(function (r) {
        if (r && r.ok) ok++;
        else falhas.push({ cod: cod, error: r && r.error || '?' });
      }).catch(function (e) {
        falhas.push({ cod: cod, error: String(e) });
      });
    });
    Promise.all(promises).then(function () {
      var lvl = falhas.length ? 'warn' : 'info';
      var msg = ok + ' salva(s)' + (falhas.length
        ? ' / ' + falhas.length + ' falha(s)' : '');
      toast(msg, lvl);
      if (falhas.length && window.coplanReportError) {
        window.coplanReportError(
          'Salvar projeto (lote)', 'save_obra',
          {
            ok: false,
            falhas: falhas.map(function (f) {
              return 'COD=' + (f.cod || '?') + ': ' + f.error;
            }),
            falhas_total: falhas.length,
          });
      }
      if (typeof window.coplanLoadObras === 'function') {
        window.coplanLoadObras();
      }
      cleanup();
    });
  }
  function cleanup() {
    window.__coplanProjetoMode = null;
    setBar(null);
    if (typeof window.coplanClearCadastroForm === 'function') {
      window.coplanClearCadastroForm();
    }
  }
  function cancelar() {
    var s = window.__coplanProjetoMode;
    if (!s) return;
    var n = Object.keys(s.edited || {}).length;
    if (n > 0 && !window.confirm(
      'Cancelar atualizacao? ' + n + ' edicao(oes) serao DESCARTADAS.')) {
      return;
    }
    cleanup();
    toast('Atualizacao cancelada', 'info');
  }

  // ---- Bind dos botoes da barra ----
  function bindNavBar() {
    var prev = $('cad-projeto-nav-prev');
    var next = $('cad-projeto-nav-next');
    var fin = $('cad-projeto-nav-finalizar');
    var can = $('cad-projeto-nav-cancelar');
    if (prev && !prev.__bound) { prev.__bound = true;
      prev.addEventListener('click', function () { navigate(-1); }); }
    if (next && !next.__bound) { next.__bound = true;
      next.addEventListener('click', function () { navigate(1); }); }
    if (fin && !fin.__bound) { fin.__bound = true;
      fin.addEventListener('click', finalizar); }
    if (can && !can.__bound) { can.__bound = true;
      can.addEventListener('click', cancelar); }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindNavBar);
  } else {
    bindNavBar();
  }

  // ---- API publica para context menu acionar o modo ----
  // Recebe COD da linha (do menu contextual) -- busca a obra para
  // descobrir nome_projeto + tipo_pacote, depois chama o backend
  // projeto_fetch_obras para listar todas obras do mesmo projeto.
  window.coplanIniciarAtualizacaoProjetoByCod = function (cod) {
    var a = api();
    if (!(a && a.get_obra && a.projeto_fetch_obras)) {
      return toast('API indisponivel', 'error');
    }
    a.get_obra(String(cod || '')).then(function (r) {
      if (!r || !r.ok || !r.obra) {
        return toast('Obra nao encontrada: ' + cod, 'error');
      }
      var nome = r.obra.nome_projeto || '';
      var pacote = r.obra.tipo_pacote || '';
      if (!nome) {
        // Sem nome_projeto: abre como Editar Obra normal
        if (typeof window.coplanLoadObraIntoForm === 'function') {
          var sb = document.querySelector('.sb-item[data-tab="cadastro"]');
          if (sb) sb.click();
          window.coplanLoadObraIntoForm(cod);
        }
        toast('Obra sem nome_projeto: aberta para edicao individual', 'info');
        return;
      }
      a.projeto_fetch_obras(nome, pacote).then(function (rp) {
        if (!rp || !rp.ok) {
          return toast('Falha ao listar obras: '
                       + (rp && rp.error || '?'), 'error');
        }
        if (!rp.total) {
          return toast('Nenhuma obra encontrada para o projeto', 'warn');
        }
        if (rp.ignoradas_outro_pacote) {
          toast(rp.ignoradas_outro_pacote
            + ' obra(s) com tipo_pacote diferente serao ignorada(s)', 'warn');
        }
        // Inicializa estado
        window.__coplanProjetoMode = {
          nome: nome,
          pacote: pacote,
          obras: rp.obras || [],
          cods: rp.cods || [],
          columns: rp.columns || [],
          index: 0,
          edited: {},
          total: rp.total,
        };
        // Troca aba para Cadastro
        var sb = document.querySelector('.sb-item[data-tab="cadastro"]');
        if (sb) sb.click();
        // Carrega primeira obra no form
        var firstCod = rp.cods[0];
        if (firstCod && typeof window.coplanLoadObraIntoForm === 'function') {
          window.coplanLoadObraIntoForm(firstCod);
        }
        setBar(window.__coplanProjetoMode);
        toast('Atualizar Projeto: ' + rp.total + ' obra(s) carregada(s)',
              'info');
      }).catch(function (e) {
        console.warn('[coplan/cadastro] projeto_fetch_obras catch:', e);
        toast('Falha ao listar obras do projeto: ' + (e && e.message || e),
              'error');
      });
    }).catch(function (e) {
      console.warn('[coplan/cadastro] get_obra projeto catch:', e);
      toast('Falha ao buscar obra para atualizar projeto: '
            + (e && e.message || e), 'error');
    });
  };
  window.coplanGetProjetoMode = function () { return window.__coplanProjetoMode; };
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 5.1 (Ganhos / pasta de arquivos) ----
  // Card "Pasta de arquivos do alimentador":
  //   * input mostra a pasta efetiva (base ou base/<ano>/<alim>)
  //   * badge "X arquivos lidos" reflete contagem real
  //   * Selecionar -> pick_ganhos_folder (folder dialog do pywebview)
  //   * Recarregar -> list_ganhos_files (re-scan)
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function getCard() {
    return document.getElementById('ganhos-card-pasta');
  }
  function getInputs(card) {
    if (!card) return {};
    return {
      input: card.querySelector('.input-row .input'),
      btnPick: (function () {
        var btns = card.querySelectorAll('.input-row .btn');
        for (var i = 0; i < btns.length; i++) {
          if (norm(btns[i].textContent).indexOf('selecionar') === 0) return btns[i];
        }
        return null;
      })(),
      btnReload: (function () {
        var btns = card.querySelectorAll('.input-row .btn');
        for (var i = 0; i < btns.length; i++) {
          if (norm(btns[i].textContent).indexOf('recarregar') === 0) return btns[i];
        }
        return null;
      })(),
      badge: card.querySelector('.card-header .badge'),
    };
  }
  function getCurrentAlimentador() {
    // Ordem de preferencia:
    //  1) state global (definido pela Visualizar quando uma obra ativa
    //     e selecionada -- futuro Passo 5.4)
    //  2) campo "Alimentador Obra" do Cadastro (current value)
    if (window.__coplanCurrentAlim) return window.__coplanCurrentAlim;
    var cad = document.getElementById('tab-cadastro');
    if (!cad) return '';
    var fields = cad.querySelectorAll('.field');
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      if (norm(lab.textContent).indexOf('alimentador obra') === 0) {
        var n = fields[i].querySelector('input, select');
        return n ? String(n.value || '').trim().toUpperCase() : '';
      }
    }
    return '';
  }
  function setBadge(badge, count, ok) {
    if (!badge) return;
    badge.className = 'badge ' + (ok ? 'success' : 'warning');
    badge.innerHTML = '<span class="dot"></span>' + count + ' arquivo'
                    + (count === 1 ? '' : 's') + ' lido' + (count === 1 ? '' : 's');
  }
  function applyState(state) {
    var card = getCard();
    if (!card || !state) return;
    var ui = getInputs(card);
    if (ui.input) {
      // Mostra a pasta efetiva (com sufixo de alim se aplicavel).
      ui.input.value = state.folder || state.base || '';
      ui.input.title = state.error || '';
    }
    var n = (state.files || []).length;
    setBadge(ui.badge, n, !!state.ok);
    // Atualiza tambem o titulo "Parametros de Ganhos -- ATB-204"
    var scope = document.getElementById('tab-ganhos');
    if (scope) {
      var titles = scope.querySelectorAll('.card .card-title');
      for (var i = 0; i < titles.length; i++) {
        var t = titles[i];
        if (norm(t.textContent).indexOf('parametros de ganhos') === 0) {
          // Mantem o icone (firstChild) e troca o text node final.
          var alim = state.alim || '';
          var icon = t.querySelector('i');
          t.innerHTML = (icon ? icon.outerHTML : '') + ' Parametros de Ganhos'
                      + (alim ? ' -- ' + String(alim).replace(/[<>&]/g, function (c) {
                          return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
                        }) : '');
        }
      }
    }
    // Cache para 5.2 (read_ganhos_file) consumir.
    window.__coplanGanhosState = state;
    document.dispatchEvent(new CustomEvent('coplan:ganhos:files', { detail: state }));
  }
  function loadGanhos() {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.list_ganhos_files)) return;
    var alim = getCurrentAlimentador();
    api.list_ganhos_files(alim).then(applyState).catch(function (e) {
      console.warn('[coplan] list_ganhos_files catch:', e);
    });
  }
  window.coplanLoadGanhosFolder = loadGanhos;

  function bindGanhosCard() {
    var card = getCard();
    if (!card) return false;
    var ui = getInputs(card);

    if (ui.btnPick) {
      ui.btnPick.addEventListener('click', function () {
        var api = window.pywebview && window.pywebview.api;
        if (!(api && api.pick_ganhos_folder)) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('API indisponivel', 'error');
          }
          return;
        }
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Abrindo seletor de pasta...', 'info');
        }
        api.pick_ganhos_folder().then(function (state) {
          applyState(state);
          if (state && state.ok && typeof window.coplanToast === 'function') {
            window.coplanToast('Pasta de ganhos atualizada', 'info');
          } else if (state && state.error && typeof window.coplanToast === 'function') {
            window.coplanToast('Erro: ' + state.error, 'error');
          }
        });
      });
    }

    if (ui.btnReload) {
      ui.btnReload.addEventListener('click', function () {
        loadGanhos();
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Re-escaneando pasta', 'info');
        }
      });
    }

    // Permite editar o input manualmente (Enter dispara reload).
    if (ui.input) {
      ui.input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') loadGanhos();
      });
    }

    return true;
  }

  // Lazy load quando entrar na aba Ganhos.
  function maybeLoad() {
    var ganhos = document.getElementById('tab-ganhos');
    if (ganhos && ganhos.classList.contains('active')) loadGanhos();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'ganhos') loadGanhos();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      bindGanhosCard();
      maybeLoad();
    });
  } else {
    if (!bindGanhosCard()) setTimeout(bindGanhosCard, 50);
    maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 5.2 (Ganhos / read_ganhos_file) ----
  // Adiciona uma lista de arquivos abaixo do card de pasta; clicar
  // dispara read_ganhos_file -> popula a tabela "Parametros de Ganhos"
  // (ganhos-tbody). Substitui a versao mock do renderGanhos do mock.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function fmtSize(bytes) {
    if (!bytes) return '';
    var kb = bytes / 1024, mb = kb / 1024;
    if (mb >= 1) return mb.toFixed(1).replace('.', ',') + ' MB';
    if (kb >= 1) return kb.toFixed(0) + ' KB';
    return bytes + ' B';
  }
  function findGanhosFolderCard() {
    return document.getElementById('ganhos-card-pasta');
  }
  function ensureFileListBox(card) {
    if (!card) return null;
    var body = card.querySelector('.card-body');
    if (!body) return null;
    var box = body.querySelector('.coplan-file-list');
    if (!box) {
      box = document.createElement('div');
      box.className = 'coplan-file-list';
      box.style.cssText = 'margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;';
      body.appendChild(box);
    }
    return box;
  }
  function renderFileList(state) {
    var card = findGanhosFolderCard();
    var box = ensureFileListBox(card);
    if (!box) return;
    var files = (state && state.files) || [];
    if (!files.length) {
      box.innerHTML = '<span style="font-size:11.5px;color:var(--text-soft)">'
                    + 'Nenhum arquivo .xlsx/.csv/.txt encontrado.</span>';
      return;
    }
    box.innerHTML = files.map(function (f) {
      return '<button class="btn sm" data-path="' + esc(f.path) + '"'
           + ' title="' + esc(f.path) + '" style="font-family:JetBrains Mono,monospace;">'
           + '<i data-lucide="file-text"></i>' + esc(f.name)
           + (f.size ? ' <span style="opacity:.6;font-weight:400;">'
                     + esc(fmtSize(f.size)) + '</span>' : '')
           + '</button>';
    }).join('');
    box.querySelectorAll('button[data-path]').forEach(function (b) {
      b.addEventListener('click', function () {
        loadGanhosFile(b.getAttribute('data-path'));
      });
    });
    if (window.lucide) lucide.createIcons();
  }

  // Linhas padrao -- usa EXATAMENTE os labels do desktop
  // (ganhos_mixin.py: setup_tab_ganhos, lista `pares` + 2 extras).
  // Mock so define visual (cols: Parametro/Antes/Depois/Delta/Criterio);
  // dados/labels seguem o desktop, fonte da verdade.
  var GANHOS_DEFAULT_ROWS = [
    {label: 'Contas Contratos',              single: false},
    {label: 'Carregamento (%)',              single: false},
    {label: 'Perdas kW',                     single: false},
    {label: 'Tensao Media (pu)',             single: false},
    {label: 'Tensao Min. (pu)',              single: false},
    {label: 'Tensao Linha Min. (pu)',        single: false},
    {label: 'CHI',                           single: false},
    {label: 'CI',                            single: false},
    {label: 'Tensao Maxima',                 single: false},
    {label: 'Ganhos Totais',                 single: false},
    // Campos extras single-value (nao tem Antes/Depois)
    {label: 'Contas Contratos Beneficiadas', single: true},
    {label: 'CC_benef_CHI_CI',               single: true},
  ];
  var GANHOS_DEFAULT_LABELS = GANHOS_DEFAULT_ROWS.map(function (r) {
    return r.label;
  });
  function normLabel(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function mergeWithDefaults(parametros) {
    // Indexa parametros (do arquivo) por label normalizado.
    var byLabel = {};
    (parametros || []).forEach(function (p) {
      var k = normLabel(p.label);
      if (k) byLabel[k] = p;
    });
    var seen = {};
    var rows = GANHOS_DEFAULT_ROWS.map(function (def) {
      var k = normLabel(def.label);
      seen[k] = 1;
      var src = byLabel[k];
      // Prefix matching (ex.: "Tensao Min. (pu)" casa com "Tensao Min").
      if (!src) {
        var keys = Object.keys(byLabel);
        for (var i = 0; i < keys.length; i++) {
          if (keys[i].indexOf(k.split(' ')[0]) === 0
              || k.indexOf(keys[i].split(' ')[0]) === 0) {
            src = byLabel[keys[i]]; seen[keys[i]] = 1; break;
          }
        }
      }
      return {
        label: def.label,
        single: !!def.single,
        a: src ? (src.a || '') : '',
        d: src ? (src.d || '') : '',
      };
    });
    // Anexa parametros nao reconhecidos no fim (sem perder dado).
    (parametros || []).forEach(function (p) {
      var k = normLabel(p.label);
      if (k && !seen[k]) rows.push(Object.assign({single: false}, p));
    });
    return rows;
  }

  // Tabela "Parametros de Ganhos" (#ganhos-tbody): renderizador real.
  function renderGanhosTbody(parametros) {
    var tbody = document.getElementById('ganhos-tbody');
    if (!tbody) return;
    // Sempre exibe as 10 linhas padrao (mesmo sem arquivo carregado),
    // alinhado com o mock. Quando ha parametros vindos de arquivo,
    // mescla os valores nas linhas correspondentes.
    parametros = mergeWithDefaults(parametros);
    if (!parametros.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="padding:18px;text-align:center;color:var(--text-soft);">'
                      + 'Selecione um arquivo na lista acima para carregar os parametros.</td></tr>';
      return;
    }
    // Calcula delta numerico quando possivel (Antes -> Depois).
    function parseNum(v) {
      if (v == null) return null;
      var s = String(v).trim().replace(/[.](?=[0-9]{3}([^0-9]|$))/g, '')
                              .replace(',', '.');
      var n = parseFloat(s);
      return isNaN(n) ? null : n;
    }
    function fmtDelta(a, d) {
      var na = parseNum(a), nd = parseNum(d);
      if (na == null || nd == null) return '';
      var diff = nd - na;
      var sign = diff > 0 ? '+' : (diff < 0 ? '' : '');
      var abs = Math.abs(diff);
      var fixed = abs < 1 ? abs.toFixed(3) : abs.toFixed(2);
      return sign + (diff < 0 ? '-' : '') + fixed.replace('.', ',');
    }
    tbody.innerHTML = parametros.map(function (g) {
      // Single-value (Contas Contratos Beneficiadas / CC_benef_CHI_CI):
      // valor unico ocupando Antes+Depois (colspan=2), sem Delta nem
      // Criterio. Reflete fielmente o desktop (campo unico que abrange
      // 2 colunas no QGridLayout).
      if (g.single) {
        var v = (g.a !== '' && g.a != null) ? g.a : (g.d || '');
        return ''
          + '<tr>'
          +   '<td>' + esc(g.label) + '</td>'
          +   '<td class="mono" colspan="2">' + esc(v) + '</td>'
          +   '<td></td>'
          +   '<td></td>'
          + '</tr>';
      }
      var delta = fmtDelta(g.a, g.d);
      var deltaCls = '';
      if (delta && delta.charAt(0) === '+') deltaCls = 'up';
      else if (delta && delta.charAt(0) === '-') deltaCls = 'down';
      return ''
        + '<tr>'
        +   '<td>' + esc(g.label) + '</td>'
        +   '<td class="col-antes mono">' + esc(g.a) + '</td>'
        +   '<td class="col-depois mono">' + esc(g.d) + '</td>'
        +   '<td class="mono ' + deltaCls + '">' + esc(delta) + '</td>'
        +   '<td>' + esc(g.crit_label || g.critTxt || '') + '</td>'
        + '</tr>';
    }).join('');
  }
  // Expoe global para Passo 5.3 reutilizar.
  window.coplanRenderGanhosTbody = renderGanhosTbody;
  window.coplanMergeGanhosDefaults = mergeWithDefaults;
  window.coplanGanhosDefaultLabels = GANHOS_DEFAULT_LABELS.slice();
  window.coplanGanhosDefaultRows = GANHOS_DEFAULT_ROWS.slice();

  function loadGanhosFile(path) {
    if (!path) return;
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.read_ganhos_file)) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast('API indisponivel', 'error');
      }
      return;
    }
    if (typeof window.coplanToast === 'function') {
      window.coplanToast('Lendo ' + path.split(new RegExp("[\\/]")).pop(), 'info');
    }
    api.read_ganhos_file(path, 200).then(function (r) {
      if (!r || !r.ok) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Falha: ' + (r && r.error || '?'), 'error');
        }
        return;
      }
      window.__coplanGanhosLastFile = r;
      renderGanhosTbody(r.parametros || []);
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(r.total_rows + ' linhas lidas', 'info');
      }
      document.dispatchEvent(new CustomEvent('coplan:ganhos:loaded',
        { detail: r }));
    }).catch(function (e) {
      console.warn('[coplan] read_ganhos_file catch:', e);
    });
  }
  window.coplanLoadGanhosFile = loadGanhosFile;

  // Sempre que a lista de arquivos muda (Passo 5.1 dispara o evento),
  // re-renderiza a lista clicavel abaixo do input.
  document.addEventListener('coplan:ganhos:files', function (ev) {
    renderFileList(ev.detail);
    // Tambem reseta tabela para 10 linhas padrao quando muda de pasta.
    renderGanhosTbody([]);
  });
  // Render imediato das 10 linhas padrao ao entrar na aba Ganhos
  // (independente da API responder). Garante que o usuario sempre veja
  // a estrutura do mock, mesmo sem banco conectado.
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'ganhos') {
      renderGanhosTbody([]);
    }
  });
  // Render inicial -- substitui imediatamente o que o mock JS deixou.
  function _initialRender() { renderGanhosTbody([]); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initialRender);
  } else {
    _initialRender();
  }
  // E reforca depois que o resto dos scripts injetados terminar de
  // carregar (ex.: Passo 5.3 que adiciona o wrap com criterios).
  setTimeout(function () {
    if (typeof window.coplanRenderGanhosTbody === 'function') {
      window.coplanRenderGanhosTbody([]);
    }
  }, 100);
})();
</script>
<script>
(function () {
  // ---- Ganhos UI: Inserir Antes/Depois, Atual, Em Massa ----
  // Replica preencher_campos_antes/depois/parametros_atuais/preencher_ganhos_massa
  // do GanhosMixin do desktop. Liga os 4 botoes da aba Ganhos as APIs:
  //   * btn-ganhos-antes -> ganhos_compute_antes
  //   * btn-ganhos-depois -> ganhos_compute_depois
  //   * btn-ganhos-atual -> ganhos_compute_atual
  //   * btn-ganhos-massa -> ganhos_apply_massa (em todas as obras
  //                         selecionadas em Visualizar)

  function api() { return window.pywebview && window.pywebview.api; }
  function toast(msg, lvl) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, lvl || 'info');
    } else {
      console.log('[ganhos]', lvl, msg);
    }
  }
  function fmt(n, d) {
    if (n == null || (typeof n === 'number' && isNaN(n))) return '';
    var v = Number(n);
    if (isNaN(v)) return String(n);
    return v.toFixed(d == null ? 4 : d);
  }
  function normLabel(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  // Le o estado atual da tabela #ganhos-tbody (celulas de texto) num mapa
  // por label normalizado, para preservar a coluna que nao esta sendo
  // recalculada (ex.: ao clicar "Depois" nao perde os valores "Antes").
  // Le os valores ATUAIS exibidos na tabela #ganhos-tbody. As celulas
  // podem ser <input data-ganhos-input="antes|depois"> (wrap da leva2) OU
  // texto (.col-antes/.col-depois). Le os inputs PRIMEIRO -- sao a fonte
  // real do que esta na tela (inclui edicao manual e obra carregada).
  // Cada coluna e lida de forma independente: NUNCA cruza antes<->depois.
  function readDisplayedRows() {
    var model = {};
    var tbody = document.getElementById('ganhos-tbody');
    if (!tbody) return model;
    var singleByKey = {};
    (window.coplanGanhosDefaultRows || []).forEach(function (def) {
      singleByKey[normLabel(def.label)] = !!def.single;
    });
    tbody.querySelectorAll('tr').forEach(function (tr) {
      if (tr.children.length < 2) return;  // ignora linha placeholder
      var label = (tr.children[0].textContent || '').trim();
      if (!label) return;
      var k = normLabel(label);
      var single = singleByKey[k];
      var aInp = tr.querySelector('input[data-ganhos-input="antes"]');
      var dInp = tr.querySelector('input[data-ganhos-input="depois"]');
      var ca = tr.querySelector('.col-antes');
      var cd = tr.querySelector('.col-depois');
      var a = aInp ? String(aInp.value || '').trim()
            : ca ? ca.textContent.trim()
            : (single && tr.children[1] ? tr.children[1].textContent.trim() : '');
      var d = single ? ''
            : dInp ? String(dInp.value || '').trim()
            : cd ? cd.textContent.trim() : '';
      model[k] = { label: label, single: !!single, a: a, d: d };
    });
    return model;
  }
  // Aplica os valores calculados na coluna 'a' ou 'd' SEM tocar na outra:
  // parte do que esta visivel (readDisplayedRows), seta apenas o slot
  // pedido, persiste no estado canonico (para a recalc de criterios ficar
  // consistente) e re-renderiza.
  function applyColumn(vals, slot) {
    var byKey = readDisplayedRows();
    (window.coplanGanhosDefaultRows || []).forEach(function (def) {
      var k = normLabel(def.label);
      if (!byKey[k]) {
        byKey[k] = { label: def.label, single: !!def.single, a: '', d: '' };
      }
    });
    Object.keys(vals).forEach(function (label) {
      var k = normLabel(label);
      if (!byKey[k]) byKey[k] = { label: label, single: false, a: '', d: '' };
      var s = (vals[label] == null ? '' : String(vals[label]));
      if (byKey[k].single) byKey[k].a = s;
      else byKey[k][slot] = s;
    });
    var rows = [];
    var used = {};
    (window.coplanGanhosDefaultRows || []).forEach(function (def) {
      var k = normLabel(def.label);
      used[k] = 1;
      rows.push(byKey[k]);
    });
    Object.keys(byKey).forEach(function (k) {
      if (!used[k]) rows.push(byKey[k]);
    });
    var store = window.__coplanGanhosLastFile || {};
    store.parametros = rows;
    window.__coplanGanhosLastFile = store;
    if (typeof window.coplanRenderGanhosTbody === 'function') {
      window.coplanRenderGanhosTbody(rows);
    }
  }
  function getCadastroFieldByLabel(prefix) {
    // Replica o lookup de cadastro_mixin: <div class="field"> com <label>
    // cujo texto comeca por prefix. Devolve o input/select dentro.
    var fields = document.querySelectorAll('.field');
    var pNorm = String(prefix || '').trim().toLowerCase();
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      var txt = lab.textContent.trim().toLowerCase();
      if (txt.indexOf(pNorm) === 0) {
        return fields[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }
  function getAlimentadores() {
    // Alimentador principal + lista de beneficiados (replica
    // ApoioMixin.get_alimentadores). O principal esta no form de Cadastro;
    // os beneficiados sao os chips em #cad-list-alim-benef (mesma fonte
    // usada no save via coplanCadastro.getChips).
    var alims = [];
    var inpPrincipal = getCadastroFieldByLabel('Alimentador');
    if (inpPrincipal) {
      var v = (inpPrincipal.value || '').trim();
      if (v) alims.push(v);
    }
    var benef = [];
    if (window.coplanCadastro
        && typeof window.coplanCadastro.getChips === 'function') {
      benef = window.coplanCadastro.getChips() || [];
    } else {
      var box = document.getElementById('cad-list-alim-benef');
      if (box) {
        box.querySelectorAll('.chip').forEach(function (c) {
          benef.push((c.textContent || '').replace(/\s+/g, ' ').trim());
        });
      }
    }
    benef.forEach(function (b) {
      var t = String(b || '').trim();
      if (t && alims.indexOf(t) === -1) alims.push(t);
    });
    return alims;
  }
  function getProjetoInvestimento() {
    var sel = getCadastroFieldByLabel('Projeto de Investimento');
    if (sel) {
      if (sel.tagName === 'SELECT') {
        return (sel.options[sel.selectedIndex] || {}).text || sel.value || '';
      }
      return (sel.value || '').trim();
    }
    return '';
  }
  function getAnoObra() {
    var el = document.getElementById('cad-sel-ano');
    return el ? String(el.value || '').trim() : '';
  }
  // Trata divergencia de ano (arquivos do Interplan x ano da obra):
  // avisa de forma bloqueante e impede a insercao. Retorna true se houve
  // mismatch (chamador deve abortar).
  function handleAnoMismatch(r) {
    if (!r || !r.ano_mismatch) return false;
    var msg = r.error || 'O ano dos arquivos do Interplan e diferente do ano da obra.';
    if (typeof window.alert === 'function') window.alert(msg);
    toast(msg, 'error');
    return true;
  }
  function applyMetricasAntes(r) {
    if (!r || !r.ok) return;
    applyColumn({
      'Contas Contratos':       r.contas_antes,
      'Carregamento (%)':       fmt(r.carregamento, 2),
      'Perdas kW':              fmt(r.perdas, 2),
      'Tensao Media (pu)':      fmt(r.tensao_media, 4),
      'Tensao Min. (pu)':       fmt(r.tensao_min, 4),
      'Tensao Linha Min. (pu)': fmt(r.tensao_min_linha, 4),
      'CHI':                    fmt(r.chi, 4),
      'CI':                     fmt(r.ci, 4),
      'Tensao Maxima':          fmt(r.tensao_max, 4),
      'Ganhos Totais':          r.ganhos_totais || '',
      'Contas Contratos Beneficiadas': (r.contas_benef == null ? '' : r.contas_benef)
    }, 'a');
  }
  function applyMetricasDepois(r) {
    if (!r || !r.ok) return;
    applyColumn({
      'Contas Contratos':       r.contas_depois,
      'Carregamento (%)':       fmt(r.carregamento, 2),
      'Perdas kW':              fmt(r.perdas, 2),
      'Tensao Media (pu)':      fmt(r.tensao_media, 4),
      'Tensao Min. (pu)':       fmt(r.tensao_min, 4),
      'Tensao Linha Min. (pu)': fmt(r.tensao_min_linha, 4),
      'CHI':                    fmt(r.chi, 4),
      'CI':                     fmt(r.ci, 4),
      'Tensao Maxima':          fmt(r.tensao_max, 4),
      'Ganhos Totais':          r.ganhos_totais || ''
    }, 'd');
  }

  function clickAntes() {
    var a = api();
    if (!a || !a.ganhos_compute_antes) return toast('API indisponivel', 'error');
    var alims = getAlimentadores();
    if (!alims.length) {
      return toast('Selecione ao menos 1 alimentador no Cadastro', 'warn');
    }
    var pi = getProjetoInvestimento();
    var ano = getAnoObra();
    var presets = (window.coplanRequirePresets || {});
    var guard = window.coplanGuard
      || function (act, req, fn) { return Promise.resolve(fn()); };
    guard('Inserir ganhos Antes', presets.export_full, function () {
      toast('Calculando ganhos antes...', 'info');
      return a.ganhos_compute_antes(alims, pi, '', ano).then(function (r) {
        if (handleAnoMismatch(r)) return;
        if (!r || !r.ok) return toast('Falha: ' + (r && r.error || '?'), 'error');
        applyMetricasAntes(r);
        var ign = (r.alimentadores_ignorados || []).length;
        var msg = 'Ganhos antes preenchidos ('
                + (r.alimentadores_validos || []).length + ' alim';
        if (ign) msg += ', ' + ign + ' ignorado(s)';
        msg += ')';
        toast(msg, ign ? 'warn' : 'info');
      });
    });
  }
  function clickDepois() {
    var a = api();
    if (!a || !a.ganhos_compute_depois) return toast('API indisponivel', 'error');
    var alims = getAlimentadores();
    if (!alims.length) {
      return toast('Selecione ao menos 1 alimentador no Cadastro', 'warn');
    }
    var pi = getProjetoInvestimento();
    var ano = getAnoObra();
    var presets = (window.coplanRequirePresets || {});
    var guard = window.coplanGuard
      || function (act, req, fn) { return Promise.resolve(fn()); };
    guard('Inserir ganhos Depois', presets.export_full, function () {
      toast('Calculando ganhos depois...', 'info');
      return a.ganhos_compute_depois(alims, pi, '', ano).then(function (r) {
        if (handleAnoMismatch(r)) return;
        if (!r || !r.ok) return toast('Falha: ' + (r && r.error || '?'), 'error');
        applyMetricasDepois(r);
        var ign = (r.alimentadores_ignorados || []).length;
        var msg = 'Ganhos depois preenchidos ('
                + (r.alimentadores_validos || []).length + ' alim';
        if (ign) msg += ', ' + ign + ' ignorado(s)';
        msg += ')';
        toast(msg, ign ? 'warn' : 'info');
      });
    });
  }
  function clickAtual() {
    var a = api();
    if (!a || !a.ganhos_compute_atual) return toast('API indisponivel', 'error');
    var alims = getAlimentadores();
    if (!alims.length) {
      return toast('Selecione ao menos 1 alimentador no Cadastro', 'warn');
    }
    var ano = getAnoObra();
    var presets = (window.coplanRequirePresets || {});
    var guard = window.coplanGuard
      || function (act, req, fn) { return Promise.resolve(fn()); };
    guard('Preencher parametros atuais', presets.export_full, function () {
      toast('Calculando atuais...', 'info');
      return a.ganhos_compute_atual(alims, '', ano).then(function (r) {
        if (handleAnoMismatch(r)) return;
        if (!r || !r.ok) return toast('Falha: ' + (r && r.error || '?'), 'error');
        var iTr = document.getElementById('ganhos-atual-tensao-reg');
        var iCr = document.getElementById('ganhos-atual-carreg');
        var iGt = document.getElementById('ganhos-atual-totais');
        if (iTr) iTr.value = r.tensao_reg_atual || '';
        if (iCr) iCr.value = fmt(r.carregamento, 4);
        if (iGt) iGt.value = r.ganhos_atual || '';
        toast('Parametros atuais preenchidos', 'info');
      });
    });
  }
  function clickMassa() {
    var a = api();
    if (!a || !a.ganhos_apply_massa) return toast('API indisponivel', 'error');
    // Coletor de cods selecionados em Visualizar (mesmo padrao usado por
    // export_detalhamento, marcar_obras_correcao, etc).
    var cods = (typeof window.coplanGetSelectedCods === 'function')
      ? window.coplanGetSelectedCods() : [];
    if (!cods || !cods.length) {
      var inputs = document.querySelectorAll(
        '#obras-tbody input[type="checkbox"]:checked');
      cods = Array.prototype.map.call(inputs, function (cb) {
        var tr = cb.closest('tr');
        return tr ? (tr.dataset.cod || '') : '';
      }).filter(function (c) { return !!c; });
    }
    if (!cods.length) {
      return toast('Selecione obras em Visualizar primeiro', 'warn');
    }
    var etapa = window.confirm(
      'Aplicar ganhos em massa para ' + cods.length + ' obra(s)?\n\n'
    + 'OK = Antes (calcula contas iniciais + beneficiadas)\n'
    + 'Cancelar = Depois (calcula contas finais)') ? 'antes' : 'depois';
    var presets = (window.coplanRequirePresets || {});
    var guard = window.coplanGuard
      || function (act, req, fn) { return Promise.resolve(fn()); };
    guard('Ganhos em massa (' + etapa + ')', presets.export_full, function () {
      toast('Aplicando ganhos ' + etapa + ' em ' + cods.length + ' obra(s)...',
            'info');
      return a.ganhos_apply_massa(cods, etapa, '').then(function (r) {
        if (!r || !r.ok) return toast('Falha: ' + (r && r.error || '?'), 'error');
        var falhas = (r.falhas || []).length;
        var ign = (r.ignoradas_sem_alim || []).length;
        var partes = [r.sucesso + ' aplicada(s)'];
        if (falhas) partes.push(falhas + ' falha(s)');
        if (ign) partes.push(ign + ' sem alim');
        var lvl = (falhas || ign) ? 'warn' : 'info';
        toast(partes.join(' / '), lvl);
        if (typeof window.coplanLoadObras === 'function') window.coplanLoadObras();
      });
    });
  }

  function bindBtns() {
    var b1 = document.getElementById('btn-ganhos-antes');
    var b2 = document.getElementById('btn-ganhos-depois');
    var b3 = document.getElementById('btn-ganhos-atual');
    var b4 = document.getElementById('btn-ganhos-massa');
    if (b1 && !b1.__bound) { b1.__bound = true; b1.addEventListener('click', clickAntes); }
    if (b2 && !b2.__bound) { b2.__bound = true; b2.addEventListener('click', clickDepois); }
    if (b3 && !b3.__bound) { b3.__bound = true; b3.addEventListener('click', clickAtual); }
    if (b4 && !b4.__bound) { b4.__bound = true; b4.addEventListener('click', clickMassa); }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindBtns);
  } else {
    bindBtns();
  }
  // Re-bind quando a aba ganhos for ativada (mock pode recriar nodes).
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'ganhos') {
      setTimeout(bindBtns, 50);
    }
  });
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 5.3 (Ganhos / criterios + status) ----
  // Le criterios via API, popula card lateral "Criterios de Planejamento"
  // e re-renderiza a tabela #ganhos-tbody adicionando badge OK/Falhou e
  // texto do criterio na coluna correspondente. Tambem expoe avaliador
  // global usado por outros passos.
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function parseNum(v) {
    if (v == null || v === '') return null;
    var s = String(v).trim().replace(/[.](?=[0-9]{3}([^0-9]|$))/g, '')
                            .replace(',', '.');
    var n = parseFloat(s);
    return isNaN(n) ? null : n;
  }
  function fmtRule(rule, value) {
    if (value == null) return '';
    var label = String(rule.label || '');
    if (label.indexOf('%') === -1) return label;
    try { return label.replace('%.2f', value.toFixed(2))
                       .replace('%.0f', value.toFixed(0))
                       .replace('%f',   String(value)); }
    catch (e) { return label; }
  }

  // Aplica regras a uma lista de parametros {label, a, d}; retorna
  // copia com {crit_label, status: 'ok'|'fail'|null}.
  function applyCriterios(parametros) {
    var c = window.__coplanCriterios;
    if (!c || !c.ok) return parametros || [];
    var crit = c.criterios || {};
    var regras = c.regras || [];
    return (parametros || []).map(function (p) {
      var labelN = norm(p.label);
      var rule = null;
      for (var i = 0; i < regras.length; i++) {
        if (labelN.indexOf(norm(regras[i].label_match)) === 0) {
          rule = regras[i]; break;
        }
      }
      if (!rule) return Object.assign({}, p, { crit_label: '', status: null });
      var thr = crit[rule.key];
      if (thr == null) return Object.assign({}, p, { crit_label: '', status: null });
      var nv = parseNum(p.d);
      var status = null;
      if (nv != null) {
        if (rule.op === 'ge') status = nv >= thr ? 'ok' : 'fail';
        else if (rule.op === 'le') status = nv <= thr ? 'ok' : 'fail';
      }
      return Object.assign({}, p, {
        crit_label: fmtRule(rule, thr),
        status: status,
      });
    });
  }

  // Renderizador customizado: coluna Criterio recebe badge + texto.
  function renderRich(parametros) {
    var tbody = document.getElementById('ganhos-tbody');
    if (!tbody) return;
    // Mescla com as 10 linhas padrao do mock (Passo 5.2 expoe o helper)
    // antes de aplicar os criterios -- assim a tabela sempre exibe os
    // 10 parametros conhecidos, com valores em branco quando nao ha
    // arquivo carregado.
    var withDefaults = (typeof window.coplanMergeGanhosDefaults === 'function')
      ? window.coplanMergeGanhosDefaults(parametros || [])
      : (parametros || []);
    var enriched = applyCriterios(withDefaults);
    if (!enriched.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="padding:18px;text-align:center;color:var(--text-soft);">'
                      + 'Selecione um arquivo na lista acima para carregar os parametros.</td></tr>';
      return;
    }
    function fmtDelta(a, d) {
      var na = parseNum(a), nd = parseNum(d);
      if (na == null || nd == null) return '';
      var diff = nd - na;
      var abs = Math.abs(diff);
      var fixed = abs < 1 ? abs.toFixed(3) : abs.toFixed(2);
      return (diff < 0 ? '-' : (diff > 0 ? '+' : '')) + fixed.replace('.', ',');
    }
    function esc(s) {
      return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
        return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
      });
    }
    tbody.innerHTML = enriched.map(function (g) {
      // Single-value: ocupa Antes+Depois (colspan=2), sem Delta/Criterio.
      if (g.single) {
        var v = (g.a !== '' && g.a != null) ? g.a : (g.d || '');
        return ''
          + '<tr>'
          +   '<td>' + esc(g.label) + '</td>'
          +   '<td class="mono" colspan="2">' + esc(v) + '</td>'
          +   '<td></td>'
          +   '<td></td>'
          + '</tr>';
      }
      var delta = fmtDelta(g.a, g.d);
      var deltaCls = delta && delta.charAt(0) === '+' ? 'up'
                   : delta && delta.charAt(0) === '-' ? 'down' : '';
      var critCell = '';
      if (g.crit_label) {
        var badge = '';
        if (g.status === 'ok') {
          badge = '<span class="badge success">OK</span> ';
        } else if (g.status === 'fail') {
          badge = '<span class="badge danger">Falhou</span> ';
        }
        critCell = badge + '<span style="color:var(--text-soft);font-size:11.5px;">'
                 + esc(g.crit_label) + '</span>';
      }
      return ''
        + '<tr>'
        +   '<td>' + esc(g.label) + '</td>'
        +   '<td class="col-antes mono">' + esc(g.a) + '</td>'
        +   '<td class="col-depois mono">' + esc(g.d) + '</td>'
        +   '<td class="mono ' + deltaCls + '">' + esc(delta) + '</td>'
        +   '<td>' + critCell + '</td>'
        + '</tr>';
    }).join('');
  }

  // Wrap idempotente do renderizador definido em 5.2 para sempre aplicar
  // os criterios.
  if (typeof window.coplanRenderGanhosTbody === 'function' &&
      !window.coplanRenderGanhosTbody.__crit) {
    var orig = window.coplanRenderGanhosTbody;
    var wrapped = function (parametros) {
      // Se ja temos criterios, render rico; senao, fallback ao original.
      if (window.__coplanCriterios && window.__coplanCriterios.ok) {
        renderRich(parametros);
      } else {
        orig.call(this, parametros);
      }
    };
    wrapped.__crit = true;
    wrapped.__inner = renderRich;
    window.coplanRenderGanhosTbody = wrapped;
  }

  // Card lateral "Criterios de Planejamento"
  function findRightCard() {
    return document.getElementById('ganhos-card-criterios');
  }
  function renderRightCard() {
    var card = findRightCard();
    if (!card) return;
    var c = window.__coplanCriterios;
    if (!c || !c.ok) return;
    var crit = c.criterios || {};
    var rows = [
      ['Tensao minima',           crit.tensao_min,    '≥', 'pu'],
      ['Tensao maxima',           crit.tensao_max,    '≤', 'pu'],
      ['Carregamento (aprov)',    crit.carregamento_limite_sim_ou_vazio, '≤', '%'],
      ['Carregamento (nao aprov)',crit.carregamento_limite_nao,          '≤', '%'],
      ['Clientes maximo',         crit.clientes_maximo,                  '≤', ''],
    ];
    var html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    rows.forEach(function (r) {
      var label = r[0], val = r[1], op = r[2], unit = r[3];
      if (val == null) return;
      var fmt = (typeof val === 'number')
        ? (val < 10 ? val.toFixed(2) : val.toString())
        : String(val);
      html += '<div class="row" style="justify-content:space-between;font-size:12.5px;">'
            +   '<span>' + label + '</span>'
            +   '<span class="mono" style="color:var(--text-soft)">'
            +     op + ' ' + fmt + (unit ? ' ' + unit : '')
            +   '</span>'
            + '</div>';
    });
    html += '</div>';
    // Mensagem informativa abaixo
    html += '<div class="mt-3" style="padding:10px 12px;background:var(--info-soft);'
          + 'border-radius:6px;font-size:11.5px;color:oklch(0.4 0.13 230);">'
          + '<i data-lucide="info" style="width:13px;height:13px;display:inline-block;'
          + 'vertical-align:-2px;"></i> Criterios atuais carregados de '
          + '<span class="mono">config.json</span>. Edite em Configuracoes.'
          + '</div>';
    var body = card.querySelector('.card-body');
    if (body) body.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  }
  window.coplanRenderCriteriosCard = renderRightCard;

  function loadCriterios() {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_criterios)) return;
    api.get_criterios().then(function (r) {
      window.__coplanCriterios = r;
      renderRightCard();
      // Re-render tabela se ja tem dados carregados (Passo 5.2).
      if (window.__coplanGanhosLastFile) {
        var inner = (window.coplanRenderGanhosTbody.__inner)
          || window.coplanRenderGanhosTbody;
        try { inner(window.__coplanGanhosLastFile.parametros || []); }
        catch (e) { /* noop */ }
      }
    }).catch(function (e) {
      console.warn('[coplan] get_criterios catch:', e);
    });
  }
  window.coplanLoadCriterios = loadCriterios;

  // Lazy load quando entra na aba Ganhos.
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'ganhos') loadCriterios();
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      var ganhos = document.getElementById('tab-ganhos');
      if (ganhos && ganhos.classList.contains('active')) loadCriterios();
    });
  } else {
    var g = document.getElementById('tab-ganhos');
    if (g && g.classList.contains('active')) loadCriterios();
  }
  // Tambem recarrega quando um novo arquivo de ganhos foi parseado
  // (5.2 dispara este evento), garantindo aplicacao consistente.
  document.addEventListener('coplan:ganhos:loaded', function () {
    if (!window.__coplanCriterios) loadCriterios();
  });
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 5.4 (Ganhos / card Ganhos Atuais) ----
  // Atualiza os 3 inputs do card "Ganhos Atuais (registrados)" com
  // dados agregados do banco para o alimentador atualmente em foco
  // (definido em window.__coplanCurrentAlim ou pelo Cadastro).
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function fmtNum(v, dec) {
    if (v == null) return '--';
    var n = Number(v);
    if (isNaN(n)) return '--';
    var s = n.toFixed(dec == null ? 2 : dec);
    return s.replace('.', ',');
  }
  function getAtualCard() {
    var scope = document.getElementById('tab-ganhos');
    if (!scope) return null;
    var titles = scope.querySelectorAll('.card .card-title');
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf('ganhos atuais') === 0) {
        return titles[i].closest('.card');
      }
    }
    return null;
  }
  function fieldByLabel(card, prefix) {
    if (!card) return null;
    var fs = card.querySelectorAll('.field');
    var target = norm(prefix);
    for (var i = 0; i < fs.length; i++) {
      var lab = fs[i].querySelector('label');
      if (!lab) continue;
      if (norm(lab.textContent).indexOf(target) === 0) {
        return fs[i].querySelector('input, textarea');
      }
    }
    return null;
  }
  function applyAtual(state) {
    var card = getAtualCard();
    if (!card || !state || !state.ok) return;
    var minMax = (state.tensao_min == null && state.tensao_max == null)
      ? '-- / -- pu'
      : (fmtNum(state.tensao_min) + ' / ' + fmtNum(state.tensao_max) + ' pu');
    var carreg = state.carregamento_max == null ? '--%'
                                                 : fmtNum(state.carregamento_max, 1) + '%';
    var totais = state.ganhos_totais_atual || '--';

    var n1 = fieldByLabel(card, 'min/max tensao');
    if (n1) n1.value = minMax;
    var n2 = fieldByLabel(card, 'carregamento registrado');
    if (n2) n2.value = carreg;
    var n3 = fieldByLabel(card, 'ganhos totais');
    if (n3) n3.value = totais;

    // Anota o badge do header do card com a contagem de obras consideradas.
    var hdr = card.querySelector('.card-header');
    if (hdr) {
      var sub = hdr.querySelector('.card-sub, .badge.info');
      if (!sub) {
        sub = document.createElement('span');
        sub.className = 'card-sub';
        sub.style.cssText = 'margin-left:auto;color:var(--text-soft);';
        hdr.appendChild(sub);
      }
      sub.textContent = state.obras_count
        ? state.obras_count + ' obra' + (state.obras_count === 1 ? '' : 's')
        : '0 obras';
    }
  }
  window.coplanApplyGanhosAtuais = applyAtual;

  function loadAtuais(alim) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_ganhos_atuais)) return;
    var a = String(alim == null ? '' : alim).trim().toUpperCase();
    api.get_ganhos_atuais(a).then(applyAtual).catch(function (e) {
      console.warn('[coplan] get_ganhos_atuais catch:', e);
    });
  }
  window.coplanLoadGanhosAtuais = loadAtuais;

  // Pipeline de "qual alimentador exibir":
  //  1) state global window.__coplanCurrentAlim
  //  2) campo "Alimentador Obra" do Cadastro (current value)
  //  3) primeiro alimentador da lista (se houver)
  function currentAlim() {
    if (window.__coplanCurrentAlim) return window.__coplanCurrentAlim;
    var cad = document.getElementById('tab-cadastro');
    if (cad) {
      var fields = cad.querySelectorAll('.field');
      for (var i = 0; i < fields.length; i++) {
        var lab = fields[i].querySelector('label');
        if (lab && norm(lab.textContent).indexOf('alimentador obra') === 0) {
          var n = fields[i].querySelector('input, select');
          if (n && n.value) return String(n.value).trim().toUpperCase();
        }
      }
    }
    return '';
  }

  // Triggers:
  //  * Entrada na aba Ganhos (com mesmo alim do Cadastro)
  //  * Mudanca de pasta (Passo 5.1) - recarrega tambem os atuais
  //  * Save bem sucedido em Cadastro (coplan:obras dispara) - re-agrega
  function refresh() { loadAtuais(currentAlim()); }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'ganhos') refresh();
  });
  document.addEventListener('coplan:ganhos:files', refresh);
  document.addEventListener('coplan:obras', refresh);
  // API publica para o Passo 5.5 trocar o alim em foco.
  window.coplanSetCurrentAlim = function (alim) {
    window.__coplanCurrentAlim = String(alim || '').trim().toUpperCase();
    refresh();
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refresh);
  } else {
    refresh();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 5.5 (Ganhos / acoes Inserir + Massa + Atuais) ----
  // Wires nos 3 botoes do header da tabela "Parametros de Ganhos" e no
  // botao "Preencher parametros atuais" do card Ganhos Atuais.
  // Estrategia:
  //   * Inserir Antes/Depois -> pick_ganhos_file -> aplica em
  //     window.__coplanGanhosLastFile.parametros (slot a/d) + re-render
  //     da tabela. Se houver __coplanCurrentObraCod, persiste tambem
  //     via apply_ganhos_to_obra. Caso contrario apenas preview local.
  //   * Ganhos em Massa -> abre modal nativo prompt para pedir cods e
  //     aplica.
  //   * Preencher parametros atuais -> recarrega card Ganhos Atuais
  //     (forca refresh sem cache).
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findGanhosTableCard() {
    var scope = document.getElementById('tab-ganhos');
    if (!scope) return null;
    var titles = scope.querySelectorAll('.card .card-title');
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf('parametros de ganhos') === 0) {
        return titles[i].closest('.card');
      }
    }
    return null;
  }
  function findAtualCard() {
    var scope = document.getElementById('tab-ganhos');
    if (!scope) return null;
    var titles = scope.querySelectorAll('.card .card-title');
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf('ganhos atuais') === 0) {
        return titles[i].closest('.card');
      }
    }
    return null;
  }
  function getButton(card, prefix) {
    if (!card) return null;
    var btns = card.querySelectorAll('.btn');
    for (var i = 0; i < btns.length; i++) {
      if (norm(btns[i].textContent).indexOf(norm(prefix)) === 0) return btns[i];
    }
    return null;
  }

  function mergeIntoCurrent(slot, parametros) {
    // Se ja temos um arquivo carregado (5.2), faz merge por label
    // mantendo entradas que nao casam (preserva ordem original).
    var current = (window.__coplanGanhosLastFile && window.__coplanGanhosLastFile.parametros) || [];
    var byLabel = {};
    parametros.forEach(function (p) {
      var k = norm(p.label || '');
      if (k) byLabel[k] = p;
    });
    if (current.length) {
      var merged = current.map(function (c) {
        var k = norm(c.label || '');
        if (!byLabel[k]) return c;
        var src = byLabel[k];
        var copy = Object.assign({}, c);
        if (slot === 'antes') copy.a = src.a || src.d || '';
        else if (slot === 'depois') copy.d = src.d || src.a || '';
        return copy;
      });
      // adiciona parametros novos que nao existiam.
      var existingKeys = current.reduce(function (acc, c) {
        acc[norm(c.label || '')] = 1; return acc;
      }, {});
      parametros.forEach(function (p) {
        var k = norm(p.label || '');
        if (!existingKeys[k] && k) merged.push(p);
      });
      return merged;
    }
    return parametros.slice();
  }

  function inserirGanhos(slot) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.pick_ganhos_file)) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast('API indisponivel', 'error');
      }
      return;
    }
    if (typeof window.coplanToast === 'function') {
      window.coplanToast('Selecione um arquivo de ganhos...', 'info');
    }
    api.pick_ganhos_file().then(function (r) {
      if (!r) return;
      if (!r.ok) {
        if (r.error !== 'cancelado' && typeof window.coplanToast === 'function') {
          window.coplanToast('Falha: ' + (r.error || '?'), 'error');
        }
        return;
      }
      var parametros = r.parametros || [];
      if (!parametros.length) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Arquivo sem parametros reconheciveis', 'warn');
        }
        return;
      }
      // Merge no estado local + re-render da tabela.
      var merged = mergeIntoCurrent(slot, parametros);
      window.__coplanGanhosLastFile = window.__coplanGanhosLastFile || {};
      window.__coplanGanhosLastFile.parametros = merged;
      if (typeof window.coplanRenderGanhosTbody === 'function') {
        window.coplanRenderGanhosTbody(merged);
      }
      // Persiste se ha obra em foco.
      var cod = window.__coplanEditingCod || window.__coplanCurrentObraCod || '';
      if (cod && api.apply_ganhos_to_obra) {
        api.apply_ganhos_to_obra(cod, slot, parametros).then(function (resp) {
          if (resp && resp.ok && typeof window.coplanToast === 'function') {
            window.coplanToast('Ganhos ' + slot + ' salvos em ' + cod
                             + ' (' + resp.applied + ' campos)', 'info');
          } else if (resp && resp.error && typeof window.coplanToast === 'function') {
            window.coplanToast('Erro: ' + resp.error, 'error');
          }
        }).catch(function (err) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast(
              'Falha ao aplicar Ganhos na obra: '
              + ((err && err.message) || err || '?'),
              'error');
          }
          if (window.coplanReportError) {
            window.coplanReportError(
              'Aplicar Ganhos na obra', 'apply_ganhos_to_obra',
              { error: String((err && err.message) || err || '?') });
          }
        });
      } else {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(parametros.length + ' parametros carregados (preview); '
                           + 'sem obra em foco para persistir.', 'warn');
        }
      }
    }).catch(function (err) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao carregar arquivo de Ganhos: '
          + ((err && err.message) || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Carregar arquivo de Ganhos', 'pick_ganhos_file',
          { error: String((err && err.message) || err || '?') });
      }
    });
  }

  function ganhosMassa() {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.pick_ganhos_file && api.ganhos_em_massa)) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast('API indisponivel', 'error');
      }
      return;
    }
    var raw = window.prompt(
      'Aplicar Ganhos em Massa\n\nInforme os COD das obras separados por ; ou ,'
      + '\n(ex.: MA-26-DI-047; MA-26-DI-048):'
    );
    if (!raw) return;
    var cods = raw.split(new RegExp("[;,\n]+")).map(function (c) { return c.trim(); })
                 .filter(function (c) { return c.length; });
    if (!cods.length) return;
    var slotChoice = window.prompt('Slot? Digite "antes" ou "depois":', 'depois');
    if (!slotChoice) return;
    var slot = norm(slotChoice).indexOf('antes') === 0 ? 'antes' : 'depois';
    if (typeof window.coplanToast === 'function') {
      window.coplanToast('Selecione o arquivo de ganhos para ' + cods.length
                       + ' obras...', 'info');
    }
    api.pick_ganhos_file().then(function (r) {
      if (!r || !r.ok) {
        if (r && r.error !== 'cancelado' && typeof window.coplanToast === 'function') {
          window.coplanToast('Falha: ' + (r.error || '?'), 'error');
        }
        return;
      }
      var params = r.parametros || [];
      api.ganhos_em_massa(cods, slot, params).then(function (resp) {
        if (resp && resp.ok && typeof window.coplanToast === 'function') {
          window.coplanToast('Massa: ' + resp.applied + '/' + resp.total
                           + ' obras atualizadas', 'info');
        } else if (typeof window.coplanToast === 'function') {
          window.coplanToast('Massa falhou: ' + (resp && resp.error || '?'), 'error');
        }
        // Recarrega lista da Visualizar para refletir mudancas.
        if (typeof window.coplanLoadObras === 'function') window.coplanLoadObras();
      }).catch(function (err) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(
            'Falha ao aplicar Ganhos em massa: '
            + ((err && err.message) || err || '?'),
            'error');
        }
        if (window.coplanReportError) {
          window.coplanReportError(
            'Aplicar Ganhos em massa', 'ganhos_em_massa',
            { error: String((err && err.message) || err || '?') });
        }
      });
    }).catch(function (err) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao carregar arquivo de Ganhos (massa): '
          + ((err && err.message) || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Carregar arquivo de Ganhos (massa)', 'pick_ganhos_file',
          { error: String((err && err.message) || err || '?') });
      }
    });
  }

  function preencherAtuais() {
    if (typeof window.coplanLoadGanhosAtuais !== 'function') return;
    // Forca um refresh do alimentador atual.
    window.coplanLoadGanhosAtuais(window.__coplanCurrentAlim || '');
    if (typeof window.coplanToast === 'function') {
      window.coplanToast('Atualizando ganhos atuais...', 'info');
    }
  }

  function bindGanhosActions() {
    var tableCard = findGanhosTableCard();
    if (tableCard) {
      var btnAntes = getButton(tableCard, 'inserir ganhos antes');
      if (btnAntes) btnAntes.addEventListener('click', function () { inserirGanhos('antes'); });
      var btnDepois = getButton(tableCard, 'inserir ganhos depois');
      if (btnDepois) btnDepois.addEventListener('click', function () { inserirGanhos('depois'); });
      var btnMassa = getButton(tableCard, 'ganhos em massa');
      if (btnMassa) btnMassa.addEventListener('click', ganhosMassa);
    }
    var atualCard = findAtualCard();
    if (atualCard) {
      var btnAtuais = getButton(atualCard, 'preencher parametros atuais');
      if (btnAtuais) btnAtuais.addEventListener('click', preencherAtuais);
    }
    return !!(tableCard || atualCard);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindGanhosActions);
  } else {
    if (!bindGanhosActions()) setTimeout(bindGanhosActions, 50);
  }
})();
</script>
