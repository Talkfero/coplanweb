<script>
(function () {
  // ---- Section 6 / Passo 4.1 (Cadastro / get_obra + fill form) ----
  // Localiza inputs do formulario por LABEL (HTML do mock nao tem ids
  // estaveis) e popula com os valores do dict retornado pela API.
  // Mapeamento label_no_modal -> coluna_db (subset de ORDERED_COLUMNS).
  var FIELD_MAP = [
    // [label prefix (case+acento insensitive), coluna db, tipo]
    // IMPORTANTE: precisa bater com SAVE_FIELDS (Passo 4.2) -- carregar
    // e salvar leem/escrevem nas MESMAS colunas. O select de "Projeto
    // de Investimento" e' populado com NOME LONGO (DISTRIBUICAO etc),
    // entao usamos `projeto_investimento` aqui (NAO `pi_base`, que e'
    // o codigo curto DI/ME/... derivado pelo backend via get_pi_base).
    ['Ano',                       'ano_',                    'select_or_input'],
    ['Projeto de Investimento',   'projeto_investimento',    'select_or_input'],
    ['Item',                      'codigo_item',             'input'],
    ['Projeto',                   'nome_projeto',            'input'], // primeiro col-7 com label "Projeto *"
    ['Nome do Projeto',           'nome_projeto',            'select_or_input'],
    ['Observacoes',               'observacoes_gerais',      'textarea'],
    ['Alimentador Obra',          'alimentador_principal',   'select_or_input'],
    ['Tensao Obra',               'nivel_tensao_obra',       'input'],
    ['Tensao Operacao',           'tensao_operacao',         'input'],
    ['Regional',                  'nome_regional',           'input'],
    ['Superintendencia',          'nome_superintendencia',   'input'],
    ['SE',                        'subestacao',              'input'],
    ['Coordenadas De',            'coordenada_inicio',       'input'],
    ['Coordenadas Para',          'coordenada_fim',          'input'],
    ['Quantidade',                'quantidade_material',     'input'],
    ['Manobra',                   'manobra',                 'select_or_input'],
    ['Caracteristicas',           'caracteristicas_material','select_or_input'],
    ['Novo Bay',                  'novo_bay',                'select_or_input'],
    ['Criticidade',               'nivel_criticidade',       'select_or_input'],
    ['Pacote',                    'tipo_pacote',             'select_or_input'],
    ['Valor da Obra',             'valor_obra',              'input'],
    ['COD_PEP',                   'cod_pep',                 'input'],   // COD_PEP sequencial real (coluna cod_pep)
  ];
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findFieldByLabel(scope, prefix) {
    var fields = scope.querySelectorAll('.field');
    var target = norm(prefix);
    // 2 passes: EXACT match primeiro (evita colisao "projeto" matchear
    // "projeto de investimento"), depois PREFIX (mantem "novo bay?" ->
    // "novo bay" e "cod_pep gerado" -> "cod_pep").
    var prefixHit = null;
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      var labClone = lab.cloneNode(true);
      labClone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(labClone.textContent);
      if (t === target) {
        return fields[i].querySelector('input, select, textarea');
      }
      if (prefixHit == null && t.indexOf(target) === 0) {
        prefixHit = fields[i].querySelector('input, select, textarea');
      }
    }
    return prefixHit;
  }
  function setNodeValue(node, value) {
    if (!node) return;
    var v = (value == null) ? '' : String(value);
    if (node.tagName === 'SELECT') {
      // 1) Tenta achar option exata (value ou textContent).
      var opts = node.options;
      var matched = -1;
      var vNorm = v.trim().toUpperCase();
      // Tambem tolera diferenca de caso/acento simples.
      function nrm(s) {
        return String(s || '').trim().toUpperCase()
          .normalize('NFD').replace(/[̀-ͯ]/g, '');
      }
      var vN = nrm(v);
      for (var i = 0; i < opts.length; i++) {
        if (String(opts[i].value) === v
            || String(opts[i].textContent).trim() === v
            || nrm(opts[i].value) === vN
            || nrm(opts[i].textContent) === vN) {
          matched = i;
          break;
        }
      }
      if (matched >= 0) {
        node.selectedIndex = matched;
        return;
      }
      // 2) Fallback: o select do mock pode ter so 1 option fake (ex.:
      // "ATB-204"). Se o valor real do banco nao bate, INJETAMOS uma
      // option nova e selecionamos -- senao a mock continua "vencendo".
      if (v) {
        var opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        opt.setAttribute('data-coplan-injected', '1');
        // Insere logo apos o placeholder (se houver) ou no inicio.
        if (opts.length && String(opts[0].value || '').trim() === '') {
          node.insertBefore(opt, opts[1] || null);
        } else {
          node.insertBefore(opt, opts[0] || null);
        }
        node.value = v;
      }
    } else {
      node.value = v;
    }
  }
  function setPillRow(scope, labelPrefix, value) {
    // Acha o .pill-row pelo label do .field; ativa o .pill cujo texto
    // bate com o value (ex.: NAO/SIM para Obra Aprovada).
    var fields = scope.querySelectorAll('.field');
    var target = norm(labelPrefix);
    var v = norm(value);
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      if (norm(lab.textContent).indexOf(target) !== 0) continue;
      var pills = fields[i].querySelectorAll('.pill');
      pills.forEach(function (p) { p.classList.remove('active'); });
      for (var j = 0; j < pills.length; j++) {
        if (norm(pills[j].textContent) === v) {
          pills[j].classList.add('active');
          return;
        }
      }
    }
  }
  function setChipList(scope, cardTitlePrefix, items) {
    // Renderiza chips de Alimentadores Beneficiados (1o card no titulo
    // "Alimentadores e Subestacoes...").
    var cards = scope.querySelectorAll('.card');
    for (var i = 0; i < cards.length; i++) {
      var t = cards[i].querySelector('.card-title');
      if (!t) continue;
      if (norm(t.textContent).indexOf(norm(cardTitlePrefix)) !== 0) continue;
      var lists = cards[i].querySelectorAll('.chip-list');
      if (!lists.length) return;
      var first = lists[0];
      first.innerHTML = '';
      (items || []).forEach(function (a) {
        var span = document.createElement('span');
        span.className = 'chip';
        span.dataset.alim = a;
        span.innerHTML = String(a).replace(/[<>&]/g, function (c) {
          return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
        }) + '<i data-lucide="x" class="x"></i>';
        first.appendChild(span);
      });
      // SEs derivadas (segunda lista).
      if (lists[1]) {
        var ses = [];
        (items || []).forEach(function (a) {
          var pref = String(a).split(/[-_/]/)[0].toUpperCase();
          if (pref && ses.indexOf(pref) === -1) ses.push(pref);
        });
        lists[1].innerHTML = ses.map(function (s) {
          return '<span class="chip">' + s + '</span>';
        }).join('');
      }
      // Atualiza o sub-titulo "X alimentadores · Y SEs"
      var sub = cards[i].querySelector('.card-sub');
      if (sub) {
        var nA = (items || []).length, nS = (lists[1] || {}).children
          ? lists[1].children.length : 0;
        sub.textContent = nA + ' alimentadores · ' + nS + ' SEs';
      }
      if (window.lucide) lucide.createIcons();
      return;
    }
  }
  function setBadgeNova(scope, isEdit, codTxt) {
    var badges = scope.querySelectorAll('.card-header .badge');
    if (!badges.length) return;
    badges[0].className = 'badge ' + (isEdit ? 'success' : 'info');
    badges[0].textContent = isEdit ? ('Editando ' + codTxt) : 'Nova obra';
  }

  function fillCadastroForm(payload) {
    var scope = document.getElementById('tab-cadastro');
    if (!scope || !payload || !payload.ok || !payload.obra) return;
    var o = payload.obra;
    FIELD_MAP.forEach(function (m) {
      var label = m[0], col = m[1];
      var v = (o[col] == null ? '' : o[col]);
      var node = findFieldByLabel(scope, label);
      if (node) setNodeValue(node, v);
    });
    // Pill: Obra Aprovada
    setPillRow(scope, 'Obra Aprovada', o.obra_aprovada || 'NAO');
    // Chips: Alimentadores Beneficiados + SEs derivadas
    setChipList(scope, 'Alimentadores e Subestacoes', payload.alim_benef || []);
    // Badge "Nova obra" -> "Editando <COD>"
    setBadgeNova(scope, true, o.cod || '');
    // Marca o estado global pra que Passo 4.2 (save) saiba se e' update.
    window.__coplanEditingCod = o.cod || '';
  }
  window.coplanFillCadastro = fillCadastroForm;

  // API publica chamada por outros passos (clique em obra, atalho, etc.)
  window.coplanEditObra = function (cod) {
    if (!cod) return;
    if (typeof window.coplanSetTab === 'function') window.coplanSetTab('cadastro');
    if (!(window.pywebview && window.pywebview.api && window.pywebview.api.get_obra)) {
      if (typeof window.coplanToast === 'function') window.coplanToast('API indisponivel', 'error');
      return;
    }
    window.pywebview.api.get_obra(String(cod)).then(function (resp) {
      if (resp && resp.ok) {
        fillCadastroForm(resp);
        // [FIX Ganhos] Dispara coplan:obra-active para que o helper
        // coplanGanhos popule a tabela de parametros + sidebar.
        // fillCadastroForm e' fluxo legado que nao passa por
        // coplanCadastro.applyObra (que ja faria o dispatch).
        try {
          var o = resp.obra || {};
          var benef = resp.alim_benef;
          if (!Array.isArray(benef)) {
            benef = String(o.alimentadores_beneficiados || '')
              .split(/[;,]/).map(function (s) { return s.trim(); })
              .filter(Boolean);
          }
          document.dispatchEvent(new CustomEvent('coplan:obra-active', {
            detail: {
              cod: o.cod || cod || '',
              alim_principal: o.alimentador_principal || o.alimentador || '',
              alim_beneficiados: benef,
              pi: o.projeto_investimento || '',
              pi_base: o.pi_base || '',
              obra: o
            }
          }));
        } catch (eDisp) { /* swallow */ }
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Obra ' + cod + ' carregada para edicao', 'info');
        }
      } else {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Falha: ' + (resp && resp.error || '?'), 'error');
        }
      }
    });
  };

  // Wire: clique no botao "..." (more-vertical) da linha abre edicao.
  // Tambem: double-click na linha abre edicao.
  document.addEventListener('coplan:obras', function () {
    var tbody = document.getElementById('obras-tbody');
    if (!tbody) return;
    tbody.querySelectorAll('tr[data-cod]').forEach(function (tr) {
      var cod = tr.getAttribute('data-cod');
      tr.addEventListener('dblclick', function () { window.coplanEditObra(cod); });
      var btn = tr.querySelector('button .lucide-more-vertical, button [data-lucide="more-vertical"]');
      var btnEl = btn ? btn.closest('button') : null;
      if (btnEl) {
        btnEl.addEventListener('click', function (e) {
          e.stopPropagation();
          window.coplanEditObra(cod);
        });
      }
    });
  });

  // Botao "Limpar campos" volta o form pra estado "Nova obra".
  function bindLimparCampos() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    var btns = scope.querySelectorAll('.row .btn');
    for (var i = 0; i < btns.length; i++) {
      if (norm(btns[i].textContent).indexOf('limpar') === 0) {
        btns[i].addEventListener('click', function () {
          window.__coplanEditingCod = '';
          scope.querySelectorAll('input, textarea').forEach(function (n) {
            if (!n.disabled) n.value = '';
          });
          scope.querySelectorAll('select').forEach(function (s) {
            s.selectedIndex = 0;
          });
          // Limpa pills e chips
          scope.querySelectorAll('.pill').forEach(function (p) {
            p.classList.remove('active');
          });
          var firstPill = scope.querySelector('.pill-row .pill');
          if (firstPill) firstPill.classList.add('active');
          scope.querySelectorAll('.chip-list').forEach(function (l) {
            l.innerHTML = '';
          });
          setBadgeNova(scope, false, '');
        });
        return true;
      }
    }
    return false;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindLimparCampos);
  } else {
    bindLimparCampos() || setTimeout(bindLimparCampos, 50);
  }
})();
</script>
<script>
(function () {
  // ---- Auto-fill codigo_item + alerta duplicidade no Cadastro ----
  // Quando o usuario digita "Nome do Projeto" e nao esta editando obra
  // existente, sugere o proximo codigo_item via API db_next_codigo_item.
  // Quando codigo_item + nome_projeto estao preenchidos, verifica se ja
  // existe obra com esse par via API db_exists_codigo_item e mostra
  // badge inline.
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
      if (t === target || t.indexOf(target) === 0) return fields[i];
    }
    return null;
  }
  function ensureBadge(field, id, label) {
    if (!field) return null;
    var b = field.querySelector('#' + id);
    if (b) return b;
    b = document.createElement('span');
    b.id = id;
    b.className = 'helper';
    b.style.cssText = 'display:none;font-size:11px;margin-top:4px;';
    b.textContent = label || '';
    field.appendChild(b);
    return b;
  }
  function setBadge(badge, msg, kind) {
    if (!badge) return;
    if (!msg) { badge.style.display = 'none'; return; }
    badge.textContent = msg;
    badge.style.display = '';
    var color = (kind === 'error') ? 'var(--danger,#dc2626)'
              : (kind === 'warn')  ? 'var(--warning,#f59e0b)'
              : 'var(--success,#16a34a)';
    badge.style.color = color;
  }
  function bindCadastroHelpers() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope || scope.__autoFillBound) return false;
    scope.__autoFillBound = true;
    var api = window.pywebview && window.pywebview.api;
    if (!api) return false;

    var fldNomeProj = findFieldByLabel(scope, 'projeto');  // "Projeto *"
    var nomeInput = fldNomeProj
      ? fldNomeProj.querySelector('input, select, textarea') : null;
    var fldItem = findFieldByLabel(scope, 'item');
    var itemInput = fldItem
      ? fldItem.querySelector('input, select, textarea') : null;

    if (!nomeInput || !itemInput) return false;

    // Badges para feedback inline
    var badgeNext = ensureBadge(fldItem, 'coplan-badge-next-item', '');
    var badgeDup = ensureBadge(fldItem, 'coplan-badge-dup-item', '');

    function isNewObra() {
      // Se nao ha COD em edicao, e' uma nova obra
      return !window.__coplanEditingCod;
    }

    function suggestNextItem() {
      if (!isNewObra()) return;
      var nome = String(nomeInput.value || '').trim();
      if (!nome) { setBadge(badgeNext, '', null); return; }
      if (!api.db_next_codigo_item) return;
      api.db_next_codigo_item(nome).then(function (r) {
        if (!(r && r.ok)) return;
        // Se item ja preenchido pelo usuario, apenas sugere
        var current = String(itemInput.value || '').trim();
        if (!current) {
          itemInput.value = String(r.next).padStart(3, '0');
          setBadge(badgeNext,
            'Sugerido: proximo item disponivel para este projeto', 'info');
        } else {
          setBadge(badgeNext,
            'Proximo disponivel para "' + nome + '": ' + r.next, 'info');
        }
        checkDuplicate();
      });
    }

    function checkDuplicate() {
      var nome = String(nomeInput.value || '').trim();
      var item = String(itemInput.value || '').trim();
      if (!nome || !item) { setBadge(badgeDup, '', null); return; }
      if (!api.db_exists_codigo_item) return;
      var excludeCod = window.__coplanEditingCod || '';
      api.db_exists_codigo_item(nome, item, excludeCod).then(function (r) {
        if (!(r && r.ok)) return;
        if (r.exists) {
          setBadge(badgeDup,
            'JA EXISTE obra com esse projeto + item! O save vai falhar.',
            'error');
        } else {
          setBadge(badgeDup, '', null);
        }
      });
    }

    // Triggers
    nomeInput.addEventListener('blur', suggestNextItem);
    nomeInput.addEventListener('change', suggestNextItem);
    itemInput.addEventListener('blur', checkDuplicate);
    itemInput.addEventListener('input', function () {
      // Debounce simples
      clearTimeout(window.__coplanDupT);
      window.__coplanDupT = setTimeout(checkDuplicate, 400);
    });

    return true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindCadastroHelpers);
  } else {
    bindCadastroHelpers() || setTimeout(bindCadastroHelpers, 200);
  }
})();
</script>
<script>
(function () {
  // ---- Badges de validacao inline + botao "Validar Obra" no Cadastro ----
  // Wireia validate_alimentadores, validate_obra_integridade, find_duplicate
  // e check_bloqueado_despachada como uma barra de status acima do botao
  // Salvar. O usuario clica "Validar Obra" pra rodar todos os checks
  // sem persistir.
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
  function ensureValidationBar() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return null;
    var bar = document.getElementById('coplan-validar-bar');
    if (bar) return bar;
    bar = document.createElement('div');
    bar.id = 'coplan-validar-bar';
    bar.className = 'card';
    bar.style.cssText = 'margin-top:10px;padding:10px 14px;'
                      + 'display:flex;flex-direction:column;gap:8px;';
    bar.innerHTML =
      '<div style="display:flex;align-items:center;gap:8px;">'
    +   '<i data-lucide="shield-check" style="width:16px;height:16px;"></i>'
    +   '<strong style="font-size:13px;">Validar obra (preview)</strong>'
    +   '<span style="margin-left:auto;display:flex;gap:6px;">'
    +     '<button id="coplan-btn-val-run" class="btn">'
    +       '<i data-lucide="play"></i> Rodar checks</button>'
    +   '</span>'
    + '</div>'
    + '<div id="coplan-val-results" '
    +      'style="display:flex;flex-direction:column;gap:4px;font-size:12px;'
    +      'color:var(--text-soft);">'
    +   'Clique "Rodar checks" pra validar a obra atual sem salvar.'
    + '</div>';
    scope.appendChild(bar);
    if (window.lucide) lucide.createIcons();
    return bar;
  }
  function rowResult(label, status, detalhe) {
    // status: 'ok' / 'warn' / 'error' / 'info'
    var color = (status === 'ok')    ? 'var(--success,#16a34a)'
              : (status === 'warn')  ? 'var(--warning,#f59e0b)'
              : (status === 'error') ? 'var(--danger,#dc2626)'
              : 'var(--text-soft)';
    var icon = (status === 'ok')    ? 'check-circle-2'
             : (status === 'warn')  ? 'alert-triangle'
             : (status === 'error') ? 'alert-octagon'
             : 'info';
    var det = detalhe ? ' <span style="color:var(--text-soft);">— '
                      + esc(detalhe) + '</span>' : '';
    return '<div style="display:flex;align-items:center;gap:6px;color:' + color + ';">'
         + '<i data-lucide="' + icon + '" style="width:13px;height:13px;"></i>'
         + '<span>' + esc(label) + '</span>' + det
         + '</div>';
  }
  function gatherFormDataLocal() {
    if (typeof window.coplanGatherCadastro === 'function') {
      try { return window.coplanGatherCadastro() || {}; } catch (e) { return {}; }
    }
    return {};
  }
  function runValidations() {
    var bar = ensureValidationBar();
    if (!bar) return;
    var box = bar.querySelector('#coplan-val-results');
    var api = window.pywebview && window.pywebview.api;
    if (!api) {
      box.innerHTML = rowResult('API indisponivel', 'error');
      if (window.lucide) lucide.createIcons();
      return;
    }
    var data = gatherFormDataLocal();
    var cod = window.__coplanEditingCod || '';
    box.innerHTML = rowResult('Rodando checks...', 'info');
    if (window.lucide) lucide.createIcons();

    var tasks = [];
    var lines = [];

    // 1) Alimentadores
    var alim = data.alimentador_principal || '';
    var benef = data.alimentadores_beneficiados || '';
    if (api.validate_alimentadores) {
      tasks.push(
        api.validate_alimentadores(alim, benef).then(function (r) {
          if (!r) return lines.push(rowResult('Alimentadores', 'error', 'sem resposta'));
          if (r.valido) {
            lines.push(rowResult('Alimentadores', 'ok', 'sem sublinhado'));
          } else {
            lines.push(rowResult('Alimentadores', 'error',
              (r.erros || []).join('; ')));
          }
        })
      );
    }

    // 2) Integridade minima
    if (api.validate_obra_integridade) {
      tasks.push(
        api.validate_obra_integridade(data).then(function (r) {
          if (!r) return lines.push(rowResult('Integridade', 'error', 'sem resposta'));
          if (r.valido) lines.push(rowResult('Integridade minima', 'ok'));
          else lines.push(rowResult('Integridade minima', 'error',
            (r.motivos || []).slice(0, 3).join('; ')));
        })
      );
    }

    // 3) Ganhos
    if (api.validate_ganhos) {
      tasks.push(
        api.validate_ganhos(data, null).then(function (r) {
          if (!r) return;
          if (r.valido) lines.push(rowResult('Ganhos consistentes', 'ok'));
          else lines.push(rowResult('Ganhos', 'warn',
            (r.motivos || []).slice(0, 2).join('; ')));
        })
      );
    }

    // 4) Duplicidade
    if (api.find_duplicate) {
      tasks.push(
        api.find_duplicate(data).then(function (r) {
          if (!r || !r.ok) return;
          if (r.duplicate) {
            var dupCod = (r.duplicate && r.duplicate.cod) || '?';
            if (dupCod === cod) {
              lines.push(rowResult('Duplicidade', 'ok',
                'apenas a propria obra (em edicao)'));
            } else {
              lines.push(rowResult('Duplicidade', 'warn',
                'ja existe COD ' + dupCod));
            }
          } else {
            lines.push(rowResult('Duplicidade', 'ok', 'sem duplicata'));
          }
        })
      );
    }

    // 5) Bloqueio por DESPACHADA (so faz sentido em update)
    if (api.check_bloqueado_despachada && cod) {
      tasks.push(
        api.check_bloqueado_despachada(cod, data).then(function (r) {
          if (!r || !r.ok) return;
          if (r.bloqueado) {
            lines.push(rowResult('DESPACHADA', 'error',
              'bloqueio ativo -- marque CORRECAO antes do save'));
          } else {
            lines.push(rowResult('DESPACHADA', 'ok',
              'sem bloqueio (ou nao DESPACHADA)'));
          }
        })
      );
    }

    // 6) Diff (preview do save)
    if (api.avaliar_diff_obra && cod) {
      tasks.push(
        api.avaliar_diff_obra(cod, data).then(function (r) {
          if (!r || !r.ok) return;
          var n = (r.campos_alterados || []).length;
          var nc = (r.campos_criticos_alterados || []).length;
          if (n === 0) {
            lines.push(rowResult('Diff', 'info', 'nenhuma mudanca'));
          } else {
            lines.push(rowResult('Diff (preview)', nc ? 'warn' : 'info',
              n + ' campo(s) alterado(s)' + (nc ? ' / ' + nc + ' criticos' : '')));
          }
        })
      );
    }

    Promise.all(tasks).then(function () {
      if (!lines.length) {
        box.innerHTML = rowResult('Sem checks aplicaveis', 'info');
      } else {
        box.innerHTML = lines.join('');
      }
      if (window.lucide) lucide.createIcons();
    });
  }
  function bindValidationBar() {
    var bar = ensureValidationBar();
    if (!bar) return false;
    var btn = bar.querySelector('#coplan-btn-val-run');
    if (btn && !btn.__bound) {
      btn.__bound = true;
      btn.addEventListener('click', runValidations);
    }
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindValidationBar);
  } else {
    bindValidationBar() || setTimeout(bindValidationBar, 250);
  }
})();
</script>
<script>
(function () {
  // ---- Context menu (right-click) na tabela de obras Visualizar ----
  // Equivalente ao menu desktop (visualizar_mixin.mostrar_menu_linha) +
  // expoe varias APIs novas (calc_*, criterios_*, validate_*, etc.) que
  // ate entao soh existiam no backend sem como o usuario acionar.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function toast(msg, level) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, level || 'info');
    } else {
      console.log('[coplan]', msg);
    }
  }
  function ensureMenuRoot() {
    var existing = document.getElementById('coplan-ctx-menu');
    if (existing) return existing;
    var el = document.createElement('div');
    el.id = 'coplan-ctx-menu';
    el.style.cssText = (
      'position:fixed;display:none;z-index:99999;'
      + 'background:var(--surface,#fff);'
      + 'border:1px solid var(--border,#cbd5e1);'
      + 'border-radius:6px;'
      + 'box-shadow:0 6px 24px rgba(0,0,0,.18);'
      + 'min-width:240px;padding:4px 0;font-size:13px;'
      + 'user-select:none;'
    );
    document.body.appendChild(el);
    // Esconde ao clicar fora
    document.addEventListener('click', function (ev) {
      if (!el.contains(ev.target)) el.style.display = 'none';
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') el.style.display = 'none';
    });
    document.addEventListener('contextmenu', function (ev) {
      // Se o context menu nativo estiver para abrir fora da nossa tabela,
      // esconde o nosso.
      if (!ev.target.closest('#tab-visualizar')) {
        el.style.display = 'none';
      }
    });
    return el;
  }
  function openMenu(x, y, items) {
    var menu = ensureMenuRoot();
    menu.innerHTML = '';
    items.forEach(function (item) {
      if (item === '-') {
        var sep = document.createElement('div');
        sep.style.cssText = 'border-top:1px solid var(--border,#e2e8f0);'
                          + 'margin:4px 0;';
        menu.appendChild(sep);
        return;
      }
      var row = document.createElement('div');
      row.style.cssText = (
        'padding:7px 14px;cursor:pointer;'
        + 'display:flex;align-items:center;gap:8px;'
      );
      if (item.disabled) {
        row.style.color = 'var(--text-soft,#94a3b8)';
        row.style.cursor = 'not-allowed';
      } else {
        row.addEventListener('mouseenter', function () {
          row.style.background = 'var(--surface-2,#f1f5f9)';
        });
        row.addEventListener('mouseleave', function () {
          row.style.background = '';
        });
      }
      var icon = '';
      if (item.icon) {
        icon = '<i data-lucide="' + esc(item.icon) + '" '
             + 'style="width:14px;height:14px;flex-shrink:0;"></i>';
      }
      var hint = '';
      if (item.hint) {
        hint = '<span style="margin-left:auto;color:var(--text-soft,#94a3b8);'
             + 'font-size:11px;">' + esc(item.hint) + '</span>';
      }
      row.innerHTML = icon + '<span>' + esc(item.label) + '</span>' + hint;
      if (!item.disabled) {
        row.addEventListener('click', function () {
          menu.style.display = 'none';
          try { item.action(); } catch (e) { console.warn('[ctx]', e); }
        });
      }
      menu.appendChild(row);
    });
    if (window.lucide) lucide.createIcons();
    menu.style.display = 'block';
    // Posicionar (clamp pra nao sair da viewport)
    var rect = menu.getBoundingClientRect();
    var W = window.innerWidth;
    var H = window.innerHeight;
    var px = Math.min(x, W - rect.width - 8);
    var py = Math.min(y, H - rect.height - 8);
    menu.style.left = Math.max(8, px) + 'px';
    menu.style.top = Math.max(8, py) + 'px';
  }
  function getRowCods(tr) {
    // Se a linha clicada estiver entre as selecionadas, age sobre a selecao.
    // Caso contrario, age sobre a linha clicada.
    var rows = document.querySelectorAll('#obras-tbody tr[data-cod]');
    var clickedCod = tr.getAttribute('data-cod') || '';
    var selected = [];
    rows.forEach(function (r) {
      var c = r.querySelector('input[type="checkbox"]');
      if (c && c.checked) selected.push(r.getAttribute('data-cod'));
    });
    if (selected.length && selected.indexOf(clickedCod) >= 0) return selected;
    return clickedCod ? [clickedCod] : [];
  }
  function bindContextMenu() {
    var tbody = document.getElementById('obras-tbody');
    if (!tbody) return false;
    if (tbody.__ctxBound) return true;
    tbody.__ctxBound = true;
    tbody.addEventListener('contextmenu', function (ev) {
      var tr = ev.target.closest('tr[data-cod]');
      if (!tr) return;
      ev.preventDefault();
      var cods = getRowCods(tr);
      if (!cods.length) return;
      var single = cods.length === 1;
      var cod = cods[0];
      var label_n = single ? cod : (cods.length + ' obras');
      var api = window.pywebview && window.pywebview.api;
      if (!api) {
        toast('API indisponivel', 'error');
        return;
      }

      var items = [];

      // ---- Edicao -----------------------------------------------
      items.push({
        label: 'Editar obra ' + (single ? cod : '(primeira)'),
        icon: 'edit-2',
        action: function () { window.coplanEditObra(cod); },
      });
      items.push({
        label: 'Copiar COD' + (single ? '' : 's (' + cods.length + ')'),
        icon: 'clipboard',
        action: function () {
          var txt = cods.join('\n');
          function fb() {
            try {
              var ta = document.createElement('textarea');
              ta.value = txt; document.body.appendChild(ta);
              ta.select();
              var ok = document.execCommand('copy');
              document.body.removeChild(ta);
              return !!ok;
            } catch (e) { return false; }
          }
          function done(ok) {
            toast(ok ? (cods.length + ' COD copiado(s)')
                     : 'Falha ao copiar',
                  ok ? 'info' : 'error');
          }
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(txt).then(function () {
              done(true);
            }, function () { done(fb()); });
          } else {
            done(fb());
          }
        },
      });

      items.push('-');

      // ---- Calculos -------------------------------------------
      items.push({
        label: 'Recalcular valor (' + label_n + ')',
        icon: 'calculator',
        action: function () {
          if (!api.atualizar_obras_valores) return toast('API indisponivel', 'error');
          if (!window.confirm('Recalcular valor_obra de ' + cods.length + ' obra(s)?')) return;
          window.coplanAtualizarBulk(cods);
        },
      });
      items.push({
        label: single ? 'Nota de Colapso' : 'Nota de Colapso (1a obra)',
        icon: 'activity',
        action: function () {
          if (!api.calc_nota_colapso_obra) return toast('API indisponivel', 'error');
          api.calc_nota_colapso_obra(cod).then(function (r) {
            if (r && r.ok) {
              toast('Nota: ' + (r.nota == null ? '?' : r.nota)
                    + ' (' + (r.criterio||'') + ')', 'info');
            } else {
              toast('Falha: ' + (r && r.error || '?'), 'error');
            }
          }).catch(function (err) {
            toast('Falha: ' + (err && err.message || err || '?'), 'error');
          });
        },
      });
      items.push({
        label: single ? 'Verifica criterios desta obra'
                       : 'Verifica criterios (1a obra)',
        icon: 'check-circle-2',
        action: function () {
          if (!api.criterios_check_obra) return toast('API indisponivel', 'error');
          api.criterios_check_obra(cod).then(function (r) {
            if (!r || !r.ok) return toast('Falha: ' + (r && r.error || '?'), 'error');
            var label = (r.atende === true) ? 'ATENDE'
                       : (r.atende === false ? 'NAO ATENDE' : 'INSUFICIENTE');
            var lvl = (r.atende === true) ? 'info'
                     : (r.atende === false ? 'error' : 'warn');
            var motivos = (r.motivos || []).join(', ');
            toast(label + (motivos ? ' (' + motivos + ')' : ''), lvl);
          }).catch(function (err) {
            toast('Falha: ' + (err && err.message || err || '?'), 'error');
          });
        },
      });
      items.push({
        label: 'Persistir status criterios (' + label_n + ')',
        icon: 'save',
        action: function () {
          if (!api.criterios_persistir_status) return toast('API indisponivel', 'error');
          if (!window.confirm('Recalcular e persistir status de criterios em '
                              + cods.length + ' obra(s)?')) return;
          toast('Persistindo criterios...', 'info');
          api.criterios_persistir_status(cods).then(function (r) {
            if (r && r.ok) {
              toast(r.atualizadas + ' obra(s) atualizadas', 'info');
              if (window.coplanLoadObras) window.coplanLoadObras();
            } else {
              toast('Falha: ' + (r && r.error || '?'), 'error');
            }
          }).catch(function (err) {
            toast('Falha: ' + (err && err.message || err || '?'), 'error');
          });
        },
      });

      items.push('-');

      // ---- Estado da obra ---------------------------------------
      items.push({
        label: 'Liberar para edicao (CORRECAO) (' + label_n + ')',
        icon: 'edit-3',
        action: function () {
          if (!api.marcar_obras_correcao) return toast('API indisponivel', 'error');
          // [FIX] Sem prompt de motivo aqui — o motivo real e' digitado
          // no painel cad-input-motivo da aba Cadastro ao salvar.
          toast('Liberando ' + cods.length + ' obra(s)...', 'info');
          api.marcar_obras_correcao(cods, '').then(function (r) {
            if (r && r.ok) {
              toast(r.marcadas + ' liberada(s). Edite e informe o motivo'
                + ' no salvamento.', 'info');
              if (window.coplanLoadObras) window.coplanLoadObras();
            } else {
              toast('Falha: ' + (r && r.error || '?'), 'error');
            }
          }).catch(function (err) {
            toast('Falha: ' + (err && err.message || err || '?'), 'error');
          });
        },
      });

      items.push('-');

      // ---- Despacho VT (so faz sentido com selecao) ---------------
      items.push({
        label: 'Gerar texto Despacho VT (' + label_n + ')',
        icon: 'file-text',
        action: function () {
          if (!api.calc_despacho_vt) return toast('API indisponivel', 'error');
          api.calc_despacho_vt(cods).then(function (r) {
            if (!r || !r.ok) return toast('Falha: ' + (r && r.error || '?'), 'error');
            // Mostra num modal simples (textarea)
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
              + 'border-radius:8px;padding:16px;'
              + 'max-width:760px;width:100%;max-height:80vh;'
              + 'display:flex;flex-direction:column;gap:12px;'
            );
            box.innerHTML = '<div style="display:flex;align-items:center;gap:8px;">'
              + '<i data-lucide="file-text"></i>'
              + '<strong>Despacho VT (' + cods.length + ' obras)</strong>'
              + '<button id="coplan-ctx-modal-close" class="btn"'
              + ' style="margin-left:auto;">Fechar</button></div>'
              + '<textarea id="coplan-ctx-modal-txt" readonly'
              + ' style="flex:1;min-height:400px;width:100%;'
              + ' font-family:monospace;font-size:12px;'
              + ' padding:8px;border:1px solid var(--border,#cbd5e1);'
              + ' border-radius:4px;"></textarea>'
              + '<div><button id="coplan-ctx-modal-copy" class="btn">'
              + '<i data-lucide="clipboard"></i> Copiar</button></div>';
            modal.appendChild(box);
            document.body.appendChild(modal);
            document.getElementById('coplan-ctx-modal-txt').value = r.texto || '';
            document.getElementById('coplan-ctx-modal-close').onclick = function () {
              document.body.removeChild(modal);
            };
            document.getElementById('coplan-ctx-modal-copy').onclick = function () {
              var t = document.getElementById('coplan-ctx-modal-txt');
              t.select();
              try { document.execCommand('copy'); toast('Copiado', 'info'); }
              catch (e) { toast('Falha ao copiar', 'error'); }
            };
            if (window.lucide) lucide.createIcons();
          }).catch(function (err) {
            toast('Falha: ' + (err && err.message || err || '?'), 'error');
          });
        },
      });
      items.push({
        label: 'Exportar Detalhamento (' + label_n + ')',
        icon: 'file-spreadsheet',
        action: function () {
          if (!api.export_detalhamento) return toast('API indisponivel', 'error');
          toast('Exportando ' + cods.length + ' obra(s)...', 'info');
          api.export_detalhamento(cods).then(function (r) {
            if (r && r.ok) {
              toast('XLSX salvo: ' + r.path, 'info');
              if (api.open_path_in_os) api.open_path_in_os(r.path);
            } else {
              toast('Falha: ' + (r && r.error || '?'), 'error');
            }
          }).catch(function (err) {
            toast('Falha: ' + (err && err.message || err || '?'), 'error');
          });
        },
      });

      items.push('-');

      // ---- COD_PEP ------------------------------------------------
      items.push({
        label: 'Gerar COD_PEP em lote (' + label_n + ')',
        icon: 'hash',
        action: function () {
          if (!api.cod_pep_gerar_lote) return toast('API indisponivel', 'error');
          if (!window.confirm('Gerar COD_PEP para ' + cods.length
                              + ' obra(s) (somente vazios)?')) return;
          toast('Gerando COD_PEP...', 'info');
          api.cod_pep_gerar_lote(cods, '', true, false).then(function (r) {
            if (r && r.ok) {
              toast(r.atualizados + ' atualizadas / '
                    + r.ignorados + ' ignoradas', 'info');
              if (window.coplanLoadObras) window.coplanLoadObras();
            } else {
              toast('Falha: ' + ((r && r.erros || ['?']).slice(0,2).join('; ')),
                    'error');
            }
          }).catch(function (err) {
            toast('Falha: ' + (err && err.message || err || '?'), 'error');
          });
        },
      });

      items.push('-');

      // ---- Exclusao (perigoso) ------------------------------------
      items.push({
        label: 'Excluir (' + label_n + ')',
        icon: 'trash-2',
        action: function () {
          if (!api.delete_obras) return toast('API indisponivel', 'error');
          if (!window.confirm('Excluir ' + cods.length + ' obra(s)?\n\n'
                              + cods.join(', '))) return;
          toast('Excluindo...', 'info');
          api.delete_obras(cods).then(function (r) {
            if (r && r.ok) {
              toast(r.deleted + ' obra(s) excluida(s)', 'info');
              if (window.coplanReportError && r && r.errors && r.errors.length) {
                window.coplanReportError(
                  'Excluir obras', 'delete_obras', r);
              }
            } else {
              toast('Erros: ' + ((r && r.errors || []).slice(0,3).join('; ')),
                       'error');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Excluir obras', 'delete_obras', r);
              }
            }
            if (window.coplanLoadObras) window.coplanLoadObras();
          }).catch(function (err) {
            toast('Falhou: ' + (err && err.message || err || '?'), 'error');
            if (window.coplanReportError) {
              window.coplanReportError(
                'Excluir obras', 'delete_obras',
                { error: String(err && err.message || err || '?') });
            }
          });
        },
      });

      openMenu(ev.clientX, ev.clientY, items);
    });
    // Re-bind quando o tbody for re-renderizado (coplan:obras event)
    return true;
  }
  document.addEventListener('coplan:obras', function () {
    var tbody = document.getElementById('obras-tbody');
    if (tbody) tbody.__ctxBound = false;
    bindContextMenu();
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindContextMenu);
  } else {
    bindContextMenu() || setTimeout(bindContextMenu, 100);
  }
})();
</script>
<script>
(function () {
  // ---- [C7] Menu contextual real do HEADER da tabela ----
  // Replica + estende mostrar_menu_cabecalho do desktop.
  // 5 acoes: Recolher (~15 chars), Restaurar largura, Esconder
  // coluna (persiste em config.ui_state.visualizar.visible_columns),
  // Ordenar A-Z, Ordenar Z-A.
  var COMPACT_PX = 120;  // ~15 chars na fonte da tabela
  function api() { return window.pywebview && window.pywebview.api; }
  function toast(msg, lvl) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, lvl || 'info');
    }
  }
  function findThead() {
    var tbl = document.querySelector('#obras-tbody');
    return tbl ? tbl.closest('table').querySelector('thead') : null;
  }
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function applyTdsForColumn(th, cssApply) {
    // Aplica CSS a todas as <td> da mesma coluna que o <th> dado.
    var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
    var tbody = document.getElementById('obras-tbody');
    if (!tbody || idx < 0) return;
    tbody.querySelectorAll('tr').forEach(function (tr) {
      var td = tr.children[idx];
      if (td) cssApply(td);
    });
  }
  function recolherTh(th) {
    th.style.width = COMPACT_PX + 'px';
    th.style.maxWidth = COMPACT_PX + 'px';
    th.style.overflow = 'hidden';
    th.style.textOverflow = 'ellipsis';
    th.style.whiteSpace = 'nowrap';
    applyTdsForColumn(th, function (td) {
      td.style.maxWidth = COMPACT_PX + 'px';
      td.style.overflow = 'hidden';
      td.style.textOverflow = 'ellipsis';
      td.style.whiteSpace = 'nowrap';
    });
    // Persiste largura via mesma API de visualizar_columns
    var col = th.getAttribute('data-col');
    if (col && api() && api().visualizar_columns_save_config) {
      api().visualizar_columns_save_config({
        widths: Object.assign({}, window.__coplanColWidths || {},
          (function () { var w = {}; w[col] = COMPACT_PX; return w; })()),
      }).catch(function () {});
      // Atualiza cache local
      if (!window.__coplanColWidths) window.__coplanColWidths = {};
      window.__coplanColWidths[col] = COMPACT_PX;
    }
  }
  function restaurarTh(th) {
    th.style.width = '';
    th.style.maxWidth = '';
    th.style.overflow = '';
    th.style.textOverflow = '';
    th.style.whiteSpace = 'nowrap';  // mantem nowrap padrao da tabela
    applyTdsForColumn(th, function (td) {
      td.style.maxWidth = '';
      td.style.overflow = '';
      td.style.textOverflow = '';
      // mantem whiteSpace default
    });
    // Remove width persistido
    var col = th.getAttribute('data-col');
    if (col && window.__coplanColWidths) {
      delete window.__coplanColWidths[col];
      if (api() && api().visualizar_columns_save_config) {
        api().visualizar_columns_save_config({
          widths: window.__coplanColWidths,
        }).catch(function () {});
      }
    }
  }
  function esconderTh(th) {
    var col = th.getAttribute('data-col');
    if (!col) return;
    var a = api();
    if (!(a && a.visualizar_columns_get_config
          && a.visualizar_columns_save_config)) {
      return toast('API indisponivel', 'error');
    }
    a.visualizar_columns_get_config().then(function (r) {
      if (!r || !r.ok) return toast('Falha get_config', 'error');
      var visible = (r.visible && r.visible.length)
        ? r.visible.slice() : (r.all || []).slice();
      var idx = visible.indexOf(col);
      if (idx >= 0) visible.splice(idx, 1);
      a.visualizar_columns_save_config({ visible: visible })
        .then(function (s) {
          if (s && s.ok) {
            toast('Coluna "' + col + '" escondida. Use o botao "Colunas" '
                  + 'para reexibir.', 'info');
            document.dispatchEvent(
              new CustomEvent('coplan:colunas-saved'));
            if (typeof window.coplanLoadObras === 'function') {
              window.coplanLoadObras();
            }
          }
        });
    });
  }
  function ordenarPor(th, dir) {
    // Ordena window.coplanObrasRaw + coplanObrasPassou pela coluna do
    // <th>. Reaplica render. dir: 'asc' | 'desc'.
    var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
    if (idx <= 0) return;  // 0 e o checkbox; pula
    var rawIdx = idx - 1;  // raw_rows nao tem checkbox
    var rawAll = window.coplanObrasRaw || [];
    var passouAll = window.coplanObrasPassou || [];
    if (!rawAll.length) return;
    // Cria pares para preservar passou alinhado a raw apos sort
    var pairs = rawAll.map(function (r, i) {
      return [r, passouAll[i] !== undefined ? passouAll[i] : null];
    });
    function keyOf(row) {
      var v = row[rawIdx];
      if (v == null) return '';
      // Tenta numero
      var n = Number(String(v).replace(',', '.'));
      if (!isNaN(n) && String(v).trim() !== '') return n;
      return String(v).toLowerCase();
    }
    pairs.sort(function (a, b) {
      var ka = keyOf(a[0]);
      var kb = keyOf(b[0]);
      if (ka < kb) return dir === 'desc' ? 1 : -1;
      if (ka > kb) return dir === 'desc' ? -1 : 1;
      return 0;
    });
    window.coplanObrasRaw = pairs.map(function (p) { return p[0]; });
    window.coplanObrasPassou = pairs.map(function (p) { return p[1]; });
    // Re-renderiza
    if (typeof window.coplanRenderObras === 'function') {
      window.coplanRenderObras();
    }
    var col = th.getAttribute('data-col') || '?';
    toast('Ordenado por "' + col + '" ('
          + (dir === 'desc' ? 'Z→A' : 'A→Z') + ')', 'info');
  }
  function showHeaderMenu(ev, th) {
    ev.preventDefault();
    // Remove menu anterior
    var prev = document.getElementById('coplan-header-ctx-menu');
    if (prev) prev.remove();
    var col = th.getAttribute('data-col') || '';
    var label = th.textContent.trim();
    var menu = document.createElement('ul');
    menu.id = 'coplan-header-ctx-menu';
    menu.style.cssText =
      'position:fixed;background:#fff;border:1px solid #e2e8f0;'
      + 'border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.12);'
      + 'list-style:none;padding:4px 0;margin:0;min-width:200px;'
      + 'z-index:99999;font-size:13px';
    var items = [
      { act: 'recolher', icon: 'minimize-2', label: 'Recolher (~15 chars)' },
      { act: 'restaurar', icon: 'maximize-2', label: 'Restaurar largura' },
      { act: 'sep1', sep: true },
      { act: 'sortAZ', icon: 'arrow-down-a-z', label: 'Ordenar A → Z' },
      { act: 'sortZA', icon: 'arrow-down-z-a', label: 'Ordenar Z → A' },
      { act: 'sep2', sep: true },
      { act: 'esconder', icon: 'eye-off', label: 'Esconder coluna' },
    ];
    if (!col) {
      // Coluna sem data-col (ex: checkbox): so mostra recolher/restaurar
      items = items.filter(function (it) {
        return it.sep || it.act === 'recolher' || it.act === 'restaurar';
      });
    }
    menu.innerHTML =
      '<li style="padding:6px 14px;color:#64748b;font-size:11.5px;'
      + 'border-bottom:1px solid #f1f5f9;font-weight:600;'
      + 'text-transform:uppercase;letter-spacing:.04em">'
      + escHtml(label || col || 'coluna') + '</li>'
      + items.map(function (it) {
        if (it.sep) {
          return '<li style="height:1px;background:#e2e8f0;margin:4px 0">'
               + '</li>';
        }
        return '<li data-act="' + escHtml(it.act) + '" style="padding:6px 14px;'
             + 'cursor:pointer;display:flex;align-items:center;gap:8px"'
             + ' onmouseover="this.style.background=\'#f1f5f9\'"'
             + ' onmouseout="this.style.background=\'\'">'
             + '<i data-lucide="' + escHtml(it.icon) + '" style="width:14px;'
             + 'height:14px"></i>' + escHtml(it.label) + '</li>';
      }).join('');
    document.body.appendChild(menu);
    if (window.lucide) lucide.createIcons();
    // Posiciona dentro da viewport
    var rect = menu.getBoundingClientRect();
    var x = ev.clientX, y = ev.clientY;
    if (x + rect.width > window.innerWidth) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight) y = window.innerHeight - rect.height - 8;
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
    function close() {
      menu.remove();
      document.removeEventListener('click', close, true);
      document.removeEventListener('contextmenu', closeOnOther, true);
    }
    function closeOnOther(e) {
      if (!menu.contains(e.target)) close();
    }
    setTimeout(function () {
      document.addEventListener('click', close, true);
      document.addEventListener('contextmenu', closeOnOther, true);
    }, 50);
    menu.addEventListener('click', function (e) {
      var li = e.target.closest('li[data-act]');
      if (!li) return;
      var act = li.dataset.act;
      close();
      switch (act) {
        case 'recolher': recolherTh(th); break;
        case 'restaurar': restaurarTh(th); break;
        case 'esconder': esconderTh(th); break;
        case 'sortAZ': ordenarPor(th, 'asc'); break;
        case 'sortZA': ordenarPor(th, 'desc'); break;
      }
    });
  }
  function bindHeaderMenu() {
    var thead = findThead();
    if (!thead || thead.__hdrCtxBound) return false;
    thead.__hdrCtxBound = true;
    thead.addEventListener('contextmenu', function (ev) {
      var th = ev.target.closest('th');
      if (!th) return;
      showHeaderMenu(ev, th);
    });
    return true;
  }
  document.addEventListener('coplan:obras', function () {
    var thead = findThead();
    if (thead) thead.__hdrCtxBound = false;
    bindHeaderMenu();
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindHeaderMenu);
  } else {
    bindHeaderMenu() || setTimeout(bindHeaderMenu, 100);
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 4.2 (Cadastro / save_obra) ----
  // Le os campos do form, monta o dict (chaveado por coluna do banco)
  // e chama save_obra. Se for INSERT precisa de COD nao vazio (Passo 4.3
  // gera COD_PEP); se for UPDATE usa window.__coplanEditingCod.
  // NOTA sobre Projeto de Investimento: o form mostra o NOME LONGO
  // ("DISTRIBUICAO", "MELHORAMENTOS", ...). Mandamos para a coluna
  // `projeto_investimento`. O `pi_base` (codigo curto DI/ME/TR/...) e'
  // derivado pelo insert_obra via get_pi_base() do legado.
  var SAVE_FIELDS = [
    ['Ano',                       'ano_'],
    ['Projeto de Investimento',   'projeto_investimento'],
    ['Item',                      'codigo_item'],
    ['Projeto',                   'nome_projeto'],
    ['Observacoes',               'observacoes_gerais'],
    ['Alimentador Obra',          'alimentador_principal'],
    ['Tensao Obra',               'nivel_tensao_obra'],
    ['Tensao Operacao',           'tensao_operacao'],
    ['Regional',                  'nome_regional'],
    ['Superintendencia',          'nome_superintendencia'],
    ['SE',                        'subestacao'],
    ['Coordenadas De',            'coordenada_inicio'],
    ['Coordenadas Para',          'coordenada_fim'],
    ['Quantidade',                'quantidade_material'],
    ['Manobra',                   'manobra'],
    ['Caracteristicas',           'caracteristicas_material'],
    ['Novo Bay',                  'novo_bay'],
    ['Criticidade',               'nivel_criticidade'],
    ['Pacote',                    'tipo_pacote'],
    ['Valor da Obra',             'valor_obra'],
  ];
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findFieldByLabel(scope, prefix) {
    var fields = scope.querySelectorAll('.field');
    var target = norm(prefix);
    // 2 passes: EXACT match primeiro (evita colisao "projeto" matchear
    // "projeto de investimento"), depois PREFIX.
    var prefixHit = null;
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      var labClone = lab.cloneNode(true);
      labClone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(labClone.textContent);
      if (t === target) {
        return fields[i].querySelector('input, select, textarea');
      }
      if (prefixHit == null && t.indexOf(target) === 0) {
        prefixHit = fields[i].querySelector('input, select, textarea');
      }
    }
    return prefixHit;
  }

  window.coplanGatherCadastro = function () {
    var scope = document.getElementById('tab-cadastro');
    var data = {};
    if (!scope) return data;
    SAVE_FIELDS.forEach(function (m) {
      var node = findFieldByLabel(scope, m[0]);
      if (!node) return;
      data[m[1]] = String(node.value || '').trim();
    });
    // Pill: Obra Aprovada -> coluna obra_aprovada
    var fields = scope.querySelectorAll('.field');
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (lab && norm(lab.textContent).indexOf('obra aprovada') === 0) {
        var act = fields[i].querySelector('.pill.active');
        if (act) data.obra_aprovada = act.textContent.trim().toUpperCase();
        break;
      }
    }
    if (!data.obra_aprovada) data.obra_aprovada = 'NÃO';
    // Chips: Alimentadores Beneficiados -> string ';'-separada
    var card = null;
    var cards = scope.querySelectorAll('.card');
    for (var c = 0; c < cards.length; c++) {
      var t = cards[c].querySelector('.card-title');
      if (t && norm(t.textContent).indexOf('alimentadores e subesta') === 0) {
        card = cards[c]; break;
      }
    }
    if (card) {
      var chips = card.querySelectorAll('.chip-list .chip');
      var arr = [];
      chips.forEach(function (ch) {
        // chip = textContent (incluindo o icone X). Pega so o text
        // do primeiro filho (text node) ou usa data-alim.
        var v = ch.dataset.alim
          ? ch.dataset.alim
          : (ch.firstChild && ch.firstChild.nodeType === 3
              ? ch.firstChild.textContent.trim()
              : ch.textContent.trim());
        if (v) arr.push(v);
      });
      data.alimentadores_beneficiados = arr.join(';');
    }
    // COD: em edicao usa o estado preservado; em insert deixa vazio,
    // o servidor (save_obra) auto-gera via CalculationManager.gerar_cod.
    if (window.__coplanEditingCod) {
      data.cod = window.__coplanEditingCod;
    } else {
      data.cod = '';
    }
    return data;
  };

  window.coplanSaveObra = function (motivo) {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.save_obra)) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast('API indisponivel', 'error');
      }
      return Promise.resolve(null);
    }
    var data = window.coplanGatherCadastro();
    // Fase A8: anexa motivo (se fornecido) no payload pra atravessar
    // o avaliar_diff/aplicar_historico_ao_dict no Python.
    if (motivo) data.motivo = String(motivo);
    if (typeof window.coplanToast === 'function') {
      window.coplanToast('Salvando obra...', 'info');
    }
    return api.save_obra(data).then(function (r) {
      // Fase A9: bloqueio por DESPACHADA -- nao tem como contornar
      // pela UI; toast vermelho e fim.
      if (r && !r.ok && r.blocked === 'despachada') {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(
            'Obra DESPACHADA: marque como CORRECAO antes de alterar '
            + '(' + (r.campos_criticos_alterados || []).join(', ') + ')',
            'error');
        }
        return r;
      }
      if (r && r.ok) {
        var msg2 = (r.mode === 'update')
          ? ('Obra ' + (r.cod || '') + ' atualizada')
          : ('Obra ' + (r.cod || '') + ' inserida');
        if (typeof window.coplanToast === 'function') {
          var detalhe2 = '';
          if (r.campos_alterados && r.campos_alterados.length) {
            detalhe2 = ' (' + r.campos_alterados.length + ' campo(s) alterado(s))';
          }
          window.coplanToast(msg2 + detalhe2, 'info');
        }
        // Marca como editing apos insert para que proximos saves virem update.
        window.__coplanEditingCod = r.cod || window.__coplanEditingCod;
        // Atualiza badge "Nova obra" -> "Editando <cod>"
        var scope = document.getElementById('tab-cadastro');
        if (scope) {
          var b = scope.querySelector('.card-header .badge');
          if (b) {
            b.className = 'badge success';
            b.textContent = 'Editando ' + (r.cod || '');
          }
        }
        // Atualiza status (mtime do banco) e a lista da Visualizar.
        if (typeof window.coplanLoadObras === 'function') window.coplanLoadObras();
        if (window.pywebview && window.pywebview.api &&
            window.pywebview.api.get_app_state) {
          window.pywebview.api.get_app_state().then(function (st) {
            window.__coplanState = st;
            document.dispatchEvent(new CustomEvent('coplan:state', { detail: st }));
          });
        }
      } else {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Falha: ' + (r && r.error || '?'), 'error');
        }
        if (window.coplanReportError) {
          window.coplanReportError('Salvar Obra', 'save_obra', r);
        }
      }
      return r;
    }).catch(function (err) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao salvar obra: ' + (err && err.message || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Salvar Obra', 'save_obra',
          { error: String(err && err.message || err || '?') });
      }
      return { ok: false, error: String(err && err.message || err || '?') };
    });
  };

  function bindSalvarBtns() {
    // 1) Botao "Salvar Obra" no card do Cadastro
    var scope = document.getElementById('tab-cadastro');
    var bound = false;
    if (scope) {
      var btns = scope.querySelectorAll('.btn');
      for (var i = 0; i < btns.length; i++) {
        if (norm(btns[i].textContent).indexOf('salvar obra') === 0) {
          btns[i].addEventListener('click', function (e) {
            e.preventDefault();
            window.coplanSaveObra();
          });
          bound = true;
        }
      }
    }
    // 2) Botao "Salvar" global do header (id=btn-salvar-global no mock)
    // Mock ja faz toast, mas substituimos pelo save real quando estamos
    // na aba Cadastro.
    var globalBtn = document.getElementById('btn-salvar-global');
    if (globalBtn) {
      globalBtn.addEventListener('click', function (e) {
        var cad = document.getElementById('tab-cadastro');
        if (cad && cad.classList.contains('active')) {
          // Save real (preventDefault para suprimir o toast generico do mock)
          e.stopImmediatePropagation();
          window.coplanSaveObra();
        }
      }, true);  // capture phase para rodar antes do handler do mock
    }
    return bound;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindSalvarBtns);
  } else {
    bindSalvarBtns() || setTimeout(bindSalvarBtns, 50);
  }
})();
</script>
<script>
(function () {
  // ---- Fase A10 (Cadastro / botao Templates de Descricao) ----
  // Adiciona botao "Templates" no card Descricao da Cadastro. Usa
  // pi_metadata_service.obter_descricao_template +
  // get_descricao_obra_from_template (ambos do core).
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
      var c = lab.cloneNode(true);
      c.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(c.textContent);
      if (t === target || t.indexOf(target) === 0) {
        return fs[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }
  function gatherFormData(scope) {
    if (typeof window.coplanGatherCadastro === 'function') {
      try { return window.coplanGatherCadastro() || {}; } catch (e) { return {}; }
    }
    return {};
  }
  function bindTemplatesBtn() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    if (scope.querySelector('#coplan-btn-templates')) return true;
    var cards = scope.querySelectorAll('.card');
    var descCard = null;
    cards.forEach(function (c) {
      var t = c.querySelector('.card-title');
      if (!t) return;
      var n = norm(t.textContent);
      if (n.indexOf('descric') === 0 || n.indexOf('descrição') === 0) {
        descCard = c;
      }
    });
    var hostHeader = (descCard && descCard.querySelector('.card-header'))
                  || descCard;
    if (!hostHeader) return false;
    var btn = document.createElement('button');
    btn.id = 'coplan-btn-templates';
    btn.className = 'btn';
    btn.style.marginLeft = 'auto';
    btn.innerHTML = '<i data-lucide="file-text"></i> Templates';
    hostHeader.appendChild(btn);
    if (window.lucide) lucide.createIcons();

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var api = window.pywebview && window.pywebview.api;
      if (!(api && api.aplicar_template_descricao)) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('API indisponivel', 'error');
        }
        return;
      }
      var pi = (findFieldByLabel(scope, 'projeto de investimento') || {}).value || '';
      if (!pi) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Selecione um Projeto de Investimento', 'warn');
        }
        return;
      }
      var dados = gatherFormData(scope);
      api.aplicar_template_descricao(pi, dados).then(function (r) {
        if (!r || !r.ok) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Falha: '
              + (r && r.error || 'sem template'), 'warn');
          }
          return;
        }
        var preview = String(r.descricao || '').trim();
        if (!preview) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Template renderizou vazio', 'warn');
          }
          return;
        }
        var msg = 'Template renderizado:\n\n' + preview
                + '\n\nAplicar no campo Descricao da Obra?';
        if (window.confirm(msg)) {
          var node = findFieldByLabel(scope, 'descric')
                  || scope.querySelector('textarea[name="descricao_obra"]');
          if (node) {
            node.value = preview;
            node.dispatchEvent(new Event('input', { bubbles: true }));
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Template aplicado', 'info');
            }
          } else if (typeof window.coplanToast === 'function') {
            window.coplanToast('Campo Descricao nao encontrado', 'warn');
          }
        }
      }).catch(function (err) {
        console.warn('[coplan/cadastro] aplicar_template_descricao:', err);
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Falha ao aplicar template: '
            + (err && err.message || err), 'error');
        }
        if (window.coplanReportError) {
          window.coplanReportError(
            'Templates', 'aplicar_template_descricao',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindTemplatesBtn);
  } else {
    bindTemplatesBtn() || setTimeout(bindTemplatesBtn, 100);
  }
})();
</script>
<script>
(function () {
  // ---- Fase A11 (Cadastro / chips de Modulos Extras do PI) ----
  // Quando o PI muda, lista as chaves extras (do PI + ATERRAMENTO se
  // exige_aterramento + last_pi_extra_map salvo) chamando
  // get_modulos_extras (delega 100% pro core).
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
      var c = lab.cloneNode(true);
      c.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = norm(c.textContent);
      if (t === target || t.indexOf(target) === 0) {
        return fs[i];
      }
    }
    return null;
  }
  function ensureChipRow(scope) {
    var existing = document.getElementById('coplan-modulos-extras-row');
    if (existing) return existing;
    var piField = findFieldByLabel(scope, 'projeto de investimento');
    if (!piField) return null;
    var row = document.createElement('div');
    row.id = 'coplan-modulos-extras-row';
    row.style.cssText = 'display:flex;gap:6px;align-items:center;'
                      + 'flex-wrap:wrap;margin-top:6px;font-size:11px;';
    row.innerHTML = '<span style="color:var(--text-soft);">Chaves extras:</span>'
                  + '<span id="coplan-modulos-extras-chips"></span>';
    piField.appendChild(row);
    return row;
  }
  function renderExtras(extras) {
    var wrap = document.getElementById('coplan-modulos-extras-chips');
    if (!wrap) return;
    if (!extras || !extras.length) {
      wrap.innerHTML = '<span style="color:var(--text-soft);">'
                     + '(nenhuma)</span>';
      return;
    }
    wrap.innerHTML = extras.map(function (k) {
      return '<span class="badge info" style="margin-right:4px;'
           + 'padding:2px 6px;font-size:10px;">'
           + String(k).replace(/[<>&]/g, function (c) {
               return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
             })
           + '</span>';
    }).join('');
  }
  function refresh(scope) {
    var node = (findFieldByLabel(scope, 'projeto de investimento') || {})
               .querySelector
               ? findFieldByLabel(scope, 'projeto de investimento')
                 .querySelector('input, select, textarea')
               : null;
    var pi = node ? node.value : '';
    if (!pi) { renderExtras([]); return; }
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_modulos_extras)) return;
    api.get_modulos_extras(pi).then(function (r) {
      renderExtras((r && r.extras) || []);
    }).catch(function (err) {
      console.warn('[coplan/cadastro] get_modulos_extras:', err);
      renderExtras([]);
      if (window.coplanReportError) {
        window.coplanReportError(
          'Chaves extras', 'get_modulos_extras',
          { error: String((err && err.message) || err || '?') });
      }
    });
  }
  function bind() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return false;
    if (!ensureChipRow(scope)) return false;
    var piField = findFieldByLabel(scope, 'projeto de investimento');
    var node = piField ? piField.querySelector('input, select, textarea') : null;
    if (node && !node.__a11_bound) {
      node.__a11_bound = true;
      node.addEventListener('change', function () { refresh(scope); });
      node.addEventListener('input', function () { refresh(scope); });
    }
    refresh(scope);
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind() || setTimeout(bind, 200);
  }
  // Re-bind apos coplanFillCadastro (carrega obra para edicao).
  document.addEventListener('coplan:obra:loaded', function () {
    bind();
  });
})();
</script>
<script>
(function () {
  // COD_PEP real-time generator removido: o COD da obra agora e' gerado
  // automaticamente no servidor (save_obra) via CalculationManager.gerar_cod
  // a partir dos campos do form, espelhando o legado desktop.
  // Mantemos um stub no-op para nao quebrar quem ainda referencia
  // window.coplanRefreshCodPep.
  window.coplanRefreshCodPep = function () {};
})();
</script>
