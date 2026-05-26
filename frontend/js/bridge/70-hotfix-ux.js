<script>
// =====================================================================
// HOTFIX UX: ESC fecha modais + "Limpar filtros" para multi-selects.
// (1) Mock fecha modal por click [data-close] ou click fora; falta ESC.
// (2) modal.querySelectorAll('select').selectedIndex=0 NAO limpa multi-
//     select — apenas seleciona o primeiro item. Para limpar de verdade
//     precisamos desmarcar TODAS as opcoes.
// =====================================================================
(function () {
  'use strict';

  // ---------- A11y: amarra <label> ao <input> adjacente ----------
  // O mock usa <label>texto</label><input/> sem for/id em ~54 campos.
  // Aqui geramos id auto e setamos label.for, sem mexer no HTML disco.
  // Cobertura ampliada (passo 2): todo <label> do documento, nao so
  // dentro de .field; inputs sem id NEM name ganham um name auto.
  function _autoId() {
    return 'auto-field-' + (Date.now().toString(36).slice(-4))
      + '-' + Math.random().toString(36).slice(2, 7);
  }
  function _findControlNear(lab) {
    // Estrategia em 5 etapas — cobre os layouts do mock:
    // 1) input/select/textarea aninhado dentro do label
    // 2) sibling imediato (label + input)
    // 3) primeiro irmao do mesmo pai
    // 4) primeiro descendente do parentElement (pula nodes de texto)
    // 5) qualquer descendente do .field/parent ate 2 niveis acima
    var direct = lab.querySelector('input, select, textarea');
    if (direct) return direct;
    var sib = lab.nextElementSibling;
    while (sib) {
      if (/^(INPUT|SELECT|TEXTAREA)$/.test(sib.tagName)) return sib;
      var inner = sib.querySelector && sib.querySelector('input, select, textarea');
      if (inner) return inner;
      sib = sib.nextElementSibling;
    }
    var parent = lab.parentElement;
    if (parent) {
      var ctrl = parent.querySelector('input, select, textarea');
      if (ctrl) return ctrl;
      var gp = parent.parentElement;
      if (gp) {
        var g = gp.querySelector('input, select, textarea');
        if (g) return g;
      }
    }
    return null;
  }
  function bindLabelsAuto() {
    // 1. Amarrar todos os labels (sem mexer nos que ja tem for).
    var labels = document.querySelectorAll('label');
    Array.prototype.forEach.call(labels, function (lab) {
      if (lab.htmlFor && document.getElementById(lab.htmlFor)) return;
      var ctrl = _findControlNear(lab);
      if (!ctrl) return;
      if (!ctrl.id) ctrl.id = _autoId();
      lab.htmlFor = ctrl.id;
    });
    // 2. Garantir id OU name em TODOS os inputs/selects/textareas.
    //    DevTools alerta se faltar ambos — autofill precisa de pelo
    //    menos um. Skipa <input type="hidden"> (geralmente intencional).
    var ctrls = document.querySelectorAll('input, select, textarea');
    Array.prototype.forEach.call(ctrls, function (c) {
      if (c.id || c.name) return;
      if (c.type === 'hidden') return;
      // Tenta inferir nome a partir de label associado (placeholder?).
      var hint = (c.getAttribute('placeholder') || c.getAttribute('aria-label')
                  || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')
                  .replace(/^-+|-+$/g, '').slice(0, 24);
      c.name = (hint ? 'auto-' + hint + '-' : 'auto-') + _autoId();
    });
  }
  if (!window.__coplanA11yLabelsBound) {
    window.__coplanA11yLabelsBound = true;
    // Debounce para nao spammar quando MutationObserver disparar muito.
    var _bindTimer = null;
    function bindLabelsDebounced() {
      if (_bindTimer) clearTimeout(_bindTimer);
      _bindTimer = setTimeout(function () {
        bindLabelsAuto();
        _bindTimer = null;
      }, 60);
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        bindLabelsAuto();
        setTimeout(bindLabelsAuto, 200);
        installMutationObserver();
      });
    } else {
      bindLabelsAuto();
      setTimeout(bindLabelsAuto, 200);
      installMutationObserver();
    }
    document.addEventListener('coplan:obras', bindLabelsDebounced);
    document.addEventListener('coplan:tab', bindLabelsDebounced);
    // [FIX] Cards dinamicos (Analise Tecnica, Resumo Ganhos, modais
    // populados por JS) escapavam dos hooks pontuais. MutationObserver
    // varre <body> e dispara bindLabelsAuto sempre que <input>/<select>/
    // <textarea> sao injetados em qualquer parte do DOM.
    function installMutationObserver() {
      if (window.__coplanA11yMOInstalled) return;
      window.__coplanA11yMOInstalled = true;
      try {
        var mo = new MutationObserver(function (mutList) {
          for (var i = 0; i < mutList.length; i++) {
            var m = mutList[i];
            if (m.addedNodes && m.addedNodes.length) {
              for (var j = 0; j < m.addedNodes.length; j++) {
                var n = m.addedNodes[j];
                if (n.nodeType !== 1) continue;
                // Bind se for input/select/textarea OU contiver um.
                if (/^(INPUT|SELECT|TEXTAREA|LABEL)$/.test(n.tagName)
                    || (n.querySelector && n.querySelector('input, select, textarea, label'))) {
                  bindLabelsDebounced();
                  return;
                }
              }
            }
          }
        });
        mo.observe(document.body, { childList: true, subtree: true });
      } catch (e) { /* swallow */ }
    }
  }

  // ---------- Hotfix Sidebar / Header (badge dinamico, user real) ----------
  if (!window.__coplanSbBadgeBound) {
    window.__coplanSbBadgeBound = true;

    // [FIX 1] Badge da sidebar "Visualizar Obras" — atualiza com total
    // do banco. Antes "2.481" hardcoded.
    function updateSidebarBadge() {
      var stats = window.__coplanStats || {};
      var total = stats.total;
      // Se ha filtros ativos, prefere total nao-filtrado salvo no FIX
      // de page-title.
      if (typeof total !== 'number') return;
      var badge = document.querySelector(
        '.sb-item[data-tab="visualizar"] .sb-item-badge'
      );
      if (!badge) return;
      var raw = Number(window.__coplanTotalSemFiltro || total);
      badge.textContent = raw.toLocaleString('pt-BR');
    }
    document.addEventListener('coplan:obras', function () {
      setTimeout(updateSidebarBadge, 50);
    });
    setTimeout(updateSidebarBadge, 500);

    // Nome do usuario via get_user_info() (port da logica do
    // cadastro_viabilidades): override config -> Active Directory Windows
    // -> fallback Title Case. Iniciais derivadas do display_name (avatar
    // mostra "AS" mesmo se username for matricula tipo "12345").
    // Sigla da empresa vem de get_config_empresa().sigla.
    function applyUserAndCompany() {
      var a = window.pywebview && window.pywebview.api;
      if (!a) {
        console.warn('[coplan] applyUserAndCompany: pywebview.api ausente');
        return;
      }
      if (typeof a.get_user_info !== 'function') {
        console.warn('[coplan] applyUserAndCompany: get_user_info nao exposto');
        return;
      }
      var pUser = a.get_user_info();
      var pCfg = (a.get_config_empresa
        ? a.get_config_empresa() : Promise.resolve(null));
      Promise.all([pUser, pCfg]).then(function (rs) {
        var u = rs[0] || {};
        var cfg = rs[1] || {};
        var displayName = u.display_name || u.username || '?';
        var initials = u.initials
          || (displayName.substring(0, 2).toUpperCase())
          || '?';
        var sigla = (cfg.sigla || '').toUpperCase();
        var role = sigla
          ? ('Planejamento • ' + sigla)
          : 'Planejamento';
        console.log('[coplan] applyUserAndCompany:',
          {displayName: displayName, initials: initials, source: u.source});

        // Sidebar
        var elName = document.querySelector('.sb-user-name');
        var elRole = document.querySelector('.sb-user-role');
        var elAv = document.querySelector('.sb-user-avatar');
        if (elName) elName.textContent = displayName;
        if (elRole) elRole.textContent = role;
        if (elAv) elAv.textContent = initials;

        // Status bar - elemento com id estavel apos limpeza do mock.
        var elStatusUser = document.getElementById('status-user');
        if (!elStatusUser) {
          // Fallback para mocks legados sem id (busca por icon user).
          var items = document.querySelectorAll('.status .item');
          for (var i = 0; i < items.length; i++) {
            if (items[i].querySelector(
                'svg[data-lucide="user"], i[data-lucide="user"]')) {
              elStatusUser = items[i];
              break;
            }
          }
        }
        if (elStatusUser) {
          // Mantem icone (svg ou i tag) e injeta texto ao lado.
          var iconHtml = elStatusUser.innerHTML.match(
            /<(svg|i)[^>]*<\/\1>/);
          elStatusUser.innerHTML = (iconHtml ? iconHtml[0] : '')
            + ' ' + displayName;
          if (window.lucide) window.lucide.createIcons();
        }
      }).catch(function (e) {
        console.warn('[coplan] applyUserAndCompany falhou:', e);
      });
    }
    // Boot: aguarda pywebviewready via coplanReady (helper interno).
    if (typeof window.coplanReady === 'function') {
      window.coplanReady(applyUserAndCompany);
    } else if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        setTimeout(applyUserAndCompany, 100);
      });
    } else {
      setTimeout(applyUserAndCompany, 100);
    }
    // Re-aplica quando empresa for salva (sigla muda) ou quando user
    // editar display_name em Configuracoes (paridade com viab:user-changed).
    document.addEventListener('coplan:config-empresa-saved',
      applyUserAndCompany);
    document.addEventListener('coplan:user-changed', applyUserAndCompany);
    window.coplanRefreshUserCompany = applyUserAndCompany;

    // [FIX 4] Botao "Conectar Banco" (icon plug-zap no header).
    // [REMOVIDO] o handler completo migrou para bindHeaderButtons
    // (Conectar Banco) que ja' faz OK=selecionar / Cancelar=criar via
    // db_create_new + auto-connect. Mantemos o stub que so' marca o
    // botao como "bound" para garantir que nao haja duplo-bind em
    // re-runs deste IIFE.
    function bindConectarBanco() {
      var btns = document.querySelectorAll('.header .btn-icon');
      for (var i = 0; i < btns.length; i++) {
        if ((btns[i].title || '').toLowerCase().indexOf('conectar') === 0) {
          btns[i].__coplanBound = true;
          break;
        }
      }
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bindConectarBanco);
    } else {
      bindConectarBanco();
    }
  }

  // ---------- PI Extra na aba Configuracoes ----------
  // Lista PI_BASE do config + chaves extras configuradas
  // (set_modulos_extras / get_modulos_extras). Edicao via prompt
  // simples — chaves separadas por virgula.
  if (!window.__coplanPiExtraBound) {
    window.__coplanPiExtraBound = true;

    function _esc(s) {
      return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
        return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
      });
    }
    function _toast(msg, lvl) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(msg, lvl || 'info');
      }
    }

    function loadPiExtra() {
      var tbody = document.getElementById('config-pi-extra-tbody');
      if (!tbody) return;
      var a = window.pywebview && window.pywebview.api;
      if (!a || !a.get_pi_options || !a.get_modulos_extras) {
        tbody.innerHTML = '<tr><td colspan="4" style="padding:14px;'
          + 'text-align:center;color:var(--danger);">'
          + 'API indisponivel.</td></tr>';
        return;
      }
      tbody.innerHTML = '<tr><td colspan="4" style="padding:18px;'
        + 'text-align:center;color:var(--text-soft);">Carregando...</td></tr>';
      // [FIX] Usa get_pi_options() que ja agrega TODOS os PI_BASE builtin
      // (DEFAULT_PI_METADATA: DIS, MEL, TRF, ...) + customizados do
      // pi_base_map. Antes usava so get_pi_base_map (vazio quando nao
      // ha custom), parecia que os PIs "tinham sumido".
      Promise.all([
        a.get_pi_options(),
        a.get_pi_base_map ? a.get_pi_base_map() : Promise.resolve({items: {}})
      ]).then(function (rs) {
        var opts = rs[0] || {};
        var map = (rs[1] && rs[1].items) || {};
        var bases = (opts.bases || []).slice();   // builtin PI_BASE
        var longs = (opts.long_names || []).slice();  // nomes longos
        if (!bases.length) {
          tbody.innerHTML = '<tr><td colspan="4" style="padding:18px;'
            + 'text-align:center;color:var(--text-soft);">'
            + 'Nenhum PI_BASE disponivel.</td></tr>';
          return;
        }
        // Para cada PI_BASE, lista os PIs longos que o usam (do map +
        // builtin matches por prefixo do tipo_base).
        var pisPorBase = {};
        bases.forEach(function (b) { pisPorBase[b] = []; });
        // Map customizado: PI_LONGO -> PI_BASE
        Object.keys(map).forEach(function (piLongo) {
          var b = String(map[piLongo] || '').trim().toUpperCase();
          if (!b) return;
          if (!pisPorBase[b]) pisPorBase[b] = [];
          pisPorBase[b].push(piLongo);
        });
        // Builtin: cada base associa-se ao seu nome longo correspondente
        // (DI -> DISTRIBUIÇÃO, etc.). Heuristica simples: nome longo
        // que comeca com a base ou e identico.
        bases.forEach(function (b) {
          longs.forEach(function (n) {
            var nU = String(n).toUpperCase();
            if (nU === b || nU.indexOf(b) === 0) {
              if (pisPorBase[b].indexOf(n) < 0) pisPorBase[b].push(n);
            }
          });
        });
        // Para cada PI_BASE, busca extras em paralelo.
        var promises = bases.map(function (b) {
          return a.get_modulos_extras(b).then(function (r) {
            return { base: b, extras: (r && r.extras) || [],
                     pis: pisPorBase[b] || [] };
          }).catch(function () {
            return { base: b, extras: [], pis: pisPorBase[b] || [] };
          });
        });
        Promise.all(promises).then(function (resp) {
          tbody.innerHTML = resp.map(function (row) {
            var extrasStr = row.extras.length
              ? row.extras.join(', ')
              : '<span style="color:var(--text-soft);font-style:italic;">'
              + '(nenhuma — Aterramento sera adicionado se exige_aterramento)</span>';
            var pisStr = row.pis.length
              ? row.pis.slice(0, 3).join(', ')
                + (row.pis.length > 3 ? ' +' + (row.pis.length - 3) : '')
              : '<span style="color:var(--text-soft);font-style:italic;">(builtin)</span>';
            return '<tr data-pi-base="' + _esc(row.base) + '">'
              + '<td class="mono"><strong>' + _esc(row.base) + '</strong></td>'
              + '<td style="font-size:12px;color:var(--text-soft);">'
              +   pisStr + '</td>'
              + '<td class="mono">' + extrasStr + '</td>'
              + '<td><button class="btn ghost sm" data-pi-extra-act="edit" '
              + 'type="button" title="Editar chaves extras">'
              + '<i data-lucide="pencil"></i></button></td>'
              + '</tr>';
          }).join('');
          if (window.lucide) window.lucide.createIcons();
        });
      }).catch(function (err) {
        tbody.innerHTML = '<tr><td colspan="4" style="padding:14px;'
          + 'color:var(--danger);">Erro: '
          + _esc(err && err.message || err) + '</td></tr>';
      });
    }

    function editPiExtra(piBase, extrasAtuais) {
      var atual = (extrasAtuais || []).join(', ');
      var entrada = window.prompt(
        'Chaves extras para PI_BASE "' + piBase + '":\n'
        + '(separadas por virgula; deixe vazio para apenas defaults)\n\n'
        + 'Ex.: ATERRAMENTO, MODULO_AUX_X',
        atual
      );
      if (entrada == null) return;
      var novas = String(entrada).split(/[,;]+/)
        .map(function (s) { return s.trim().toUpperCase(); })
        .filter(Boolean);
      var a = window.pywebview && window.pywebview.api;
      if (!a || !a.set_modulos_extras) {
        _toast('API set_modulos_extras indisponivel', 'error');
        return;
      }
      a.set_modulos_extras(piBase, novas).then(function (r) {
        if (r && r.ok) {
          _toast('Chaves extras de ' + piBase + ' atualizadas: '
                 + (novas.length ? novas.join(', ') : '(vazio)'), 'success');
          loadPiExtra();
        } else {
          _toast('Falha: ' + ((r && r.error) || '?'), 'error');
        }
      }).catch(function (err) {
        _toast('Erro: ' + (err && err.message || err), 'error');
      });
    }

    // Delegacao: click em [data-pi-extra-act="edit"] dentro da tabela
    document.addEventListener('click', function (ev) {
      var btn = ev.target && ev.target.closest
        && ev.target.closest('[data-pi-extra-act="edit"]');
      if (!btn) return;
      var tr = btn.closest('tr[data-pi-base]');
      if (!tr) return;
      var piBase = tr.getAttribute('data-pi-base');
      // Extrai extras atuais do td.mono (3o td)
      var tds = tr.querySelectorAll('td');
      var atualText = (tds[2] && tds[2].textContent || '').trim();
      var atual = atualText.indexOf('(nenhuma') === 0
        ? []
        : atualText.split(/[,;]+/).map(function (s) {
            return s.trim().toUpperCase();
          }).filter(Boolean);
      editPiExtra(piBase, atual);
    });

    // Botao Recarregar
    var btnReload = document.getElementById('config-pi-extra-reload');
    if (btnReload && !btnReload.__bound) {
      btnReload.__bound = true;
      btnReload.addEventListener('click', loadPiExtra);
    }

    // Auto-load quando entra na aba Configuracoes
    document.addEventListener('coplan:tab', function (ev) {
      if (ev && ev.detail && ev.detail.name === 'config') {
        setTimeout(loadPiExtra, 30);
      }
    });
    // Tambem ao boot se ja na aba.
    if (document.readyState !== 'loading') {
      var active = document.querySelector('.tab-panel.active');
      if (active && active.id === 'tab-config') {
        setTimeout(loadPiExtra, 200);
      }
    }
    window.coplanLoadPiExtra = loadPiExtra;
  }

  // ---------- HOTFIX UX (botoes + obra ativa + asterisco condicional) ----------
  if (!window.__coplanCadHotfixBound) {
    window.__coplanCadHotfixBound = true;

    // [FIX 1] Botoes "Escolher" e "Templates" via delegacao no body —
    // funciona mesmo que o bind direto tenha falhado por timing.
    document.addEventListener('click', function (ev) {
      var t = ev.target && ev.target.closest && ev.target.closest('button');
      if (!t) return;
      var id = t.id;
      var C = window.coplanCadastro;
      if (id === 'cad-btn-escolher') {
        // Re-dispara via API list_projetos (M056). O handler interno
        // pode nao ter sido bindado se IIFE rodou antes do botao existir.
        if (window.coplanCadastroAbrirProjeto) {
          window.coplanCadastroAbrirProjeto();
        } else if (window.pywebview && window.pywebview.api
                   && window.pywebview.api.list_projetos) {
          window.pywebview.api.list_projetos().then(function (r) {
            var modal = document.getElementById('modal-projeto-busca');
            if (modal) modal.style.display = 'grid';
            var tbody = document.getElementById('projeto-busca-tbody');
            var items = (r && r.ok && r.items) ? r.items : [];
            function render(filtro) {
              if (!tbody) return;
              var termo = String(filtro || '').trim().toLowerCase();
              tbody.innerHTML = items.filter(function (n) {
                return !termo || String(n).toLowerCase().indexOf(termo) !== -1;
              }).map(function (n) {
                var safe = String(n).replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;').replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;');
                return '<tr data-projeto="' + safe + '" style="cursor:pointer;">'
                  + '<td style="padding:6px 10px;">' + safe + '</td>'
                  + '<td>—</td><td style="text-align:right;">—</td></tr>';
              }).join('');
            }
            render('');
            var filtroInp = document.getElementById('projeto-busca-filtro');
            if (filtroInp) {
              filtroInp.value = '';
              filtroInp.oninput = function () { render(filtroInp.value); };
            }
          });
        }
      }
      if (id === 'cad-btn-templates') {
        if (typeof window.coplanSetTab === 'function') {
          window.coplanSetTab('config');
        }
        document.dispatchEvent(new CustomEvent('coplan:focus-config-tab', {
          detail: { tab: 'templates' }
        }));
      }
    });

    // [FIX 2] Sincroniza state.obraEmEdicao do coplanCadastro quando
    // o evento coplan:obra-active dispara (fluxo do double-click via
    // fillCadastroForm — que NAO chama applyObra). Sem isso, salvar
    // depois disto ainda trata como nova obra (insert) em vez de update.
    document.addEventListener('coplan:obra-active', function (ev) {
      var d = (ev && ev.detail) || {};
      var C = window.coplanCadastro;
      if (!C || !C.state) return;
      C.state.obraEmEdicao = d.cod || null;
      // [NOVO] Reseta flag de "salvar como nova" sempre que obra muda.
      C.state.modoCriarNova = false;
      // Ano editavel mesmo em modo edicao (paridade com legado desktop).
      var ano = document.getElementById('cad-sel-ano');
      if (ano) ano.disabled = false;
      // [NOVO] Atualiza apenas o badge — o botao "Salvar como NOVA"
      // agora fica SEMPRE visivel (HTML default), permitindo que o user
      // duplique uma obra existente OU crie uma nova "modelo" sem ter
      // que carregar uma primeiro.
      var badge = document.getElementById('cad-badge-modo');
      if (d.cod) {
        if (badge) {
          badge.textContent = 'Editando ' + d.cod;
          badge.classList.remove('info');
          badge.classList.add('warning');
        }
      } else {
        if (badge) {
          badge.textContent = 'Nova obra';
          badge.classList.remove('warning');
          badge.classList.add('info');
        }
      }
      // Motivo de alteracao critica removido: o painel cad-row-motivo
      // permanece sempre escondido e o sidebar check 'motivo-correcao'
      // fica oculto, sem dependencia do status DESPACHADA/CORRECAO.
      try {
        var motivoRow = document.getElementById('cad-row-motivo');
        if (motivoRow) motivoRow.style.display = 'none';
        var checkRow = document.querySelector(
          '[data-check="motivo-correcao"]');
        if (checkRow) checkRow.style.display = 'none';
      } catch (e) { /* swallow */ }
    });

    // [NOVO] Botao "Salvar como NOVA": delegacao no body para garantir
    // bind mesmo se o botao for re-renderizado ou se o lookup pontual
    // tiver falhado por timing.
    if (!window.__coplanModoNovaDelegBound) {
      window.__coplanModoNovaDelegBound = true;
      document.addEventListener('click', function (ev) {
        var t = ev.target && ev.target.closest
          && ev.target.closest('#cad-btn-modo-nova');
        if (!t) return;
        var C = window.coplanCadastro;
        if (!C || !C.state) return;
        var jaAtivo = C.state.modoCriarNova;
        if (jaAtivo) {
          C.state.modoCriarNova = false;
          t.classList.remove('primary');
          t.classList.add('ghost');
          t.innerHTML = '<i data-lucide="copy-plus"></i> Salvar como NOVA';
          var badge = document.getElementById('cad-badge-modo');
          if (badge && C.state.obraEmEdicao) {
            badge.textContent = 'Editando ' + C.state.obraEmEdicao;
            badge.classList.remove('success');
            badge.classList.add('warning');
          }
          if (window.coplanToast) {
            window.coplanToast('Modo: Atualizar obra existente', 'info');
          }
        } else {
          C.state.modoCriarNova = true;
          t.classList.remove('ghost');
          t.classList.add('primary');
          t.innerHTML = '<i data-lucide="check"></i> Salvar como NOVA (ativo)';
          var badge2 = document.getElementById('cad-badge-modo');
          if (badge2) {
            badge2.textContent = 'NOVA OBRA (a partir de '
              + (C.state.obraEmEdicao || '?') + ')';
            badge2.classList.remove('warning', 'info');
            badge2.classList.add('success');
          }
          if (window.coplanToast) {
            window.coplanToast(
              'Modo: Criar NOVA obra (aproveitando dados). Ajuste o '
              + 'que precisar e clique Salvar.',
              'info');
          }
        }
        if (window.lucide) window.lucide.createIcons();
      });
    }
    // [NOVO] Check de boot: se ja ha obra carregada (state.obraEmEdicao
    // setado por iteração anterior), atualiza o badge.
    setTimeout(function () {
      var C = window.coplanCadastro;
      if (!C || !C.state || !C.state.obraEmEdicao) return;
      var badge = document.getElementById('cad-badge-modo');
      if (badge) {
        badge.textContent = 'Editando ' + C.state.obraEmEdicao;
        badge.classList.remove('info');
        badge.classList.add('warning');
      }
    }, 500);

    // [FIX 3] Asterisco condicional do Projeto: aparece SOMENTE quando
    // PI = DISTRIBUIÇÃO ou DISTRIBUIÇÃO LD 34,5 KV ([RB-DISTRIBUIÇÃO]).
    // Antes o <span class="req">*</span> era fixo, sugerindo que Projeto
    // sempre era obrigatorio — incorreto.
    function updateProjetoReq() {
      var pi = document.getElementById('cad-sel-pi');
      var req = document.querySelector(
        '[data-req-conditional="distribuicao"]'
      );
      if (!req) return;
      var v = pi ? String(pi.value || '').toUpperCase() : '';
      var match = (v.indexOf('DISTRIBUI') === 0);  // pega ambas variantes
      req.style.display = match ? '' : 'none';
    }
    var piSel = document.getElementById('cad-sel-pi');
    if (piSel && !piSel.__reqHook) {
      piSel.__reqHook = true;
      piSel.addEventListener('change', updateProjetoReq);
    }
    // Roda no boot e quando obras chegam (re-render pode trocar PI).
    document.addEventListener('coplan:obra-active', function () {
      setTimeout(updateProjetoReq, 30);
    });
    setTimeout(updateProjetoReq, 200);

    // [FIX 4] Forca loadOptions ao boot (nao depende do user trocar
    // para a aba Cadastro). Combo de Ano (range current..+10) deve
    // estar populado mesmo se a primeira interacao for via "Escolher".
    if (window.coplanCadastro && typeof window.coplanCadastro.loadOptions === 'function') {
      window.coplanReady && window.coplanReady(function () {
        window.coplanCadastro.loadOptions(true).catch(function () {});
      });
    }

  }

  // ---------- ESC global em modais ----------
  if (!window.__coplanEscModalsBound) {
    window.__coplanEscModalsBound = true;
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' && e.keyCode !== 27) return;
      var visible = Array.prototype.slice.call(
        document.querySelectorAll('.modal-backdrop')
      ).filter(function (m) {
        var st = window.getComputedStyle(m);
        return st && st.display !== 'none';
      });
      if (!visible.length) return;
      // Fecha o ultimo (mais "no topo" da pilha visual).
      var top = visible[visible.length - 1];
      top.style.display = 'none';
      e.preventDefault();
      e.stopPropagation();
    });
  }

  // ---------- Limpar de verdade multi-selects no Limpar filtros ----------
  // Hooka botoes "Limpar" do modal-filtros para chamar tambem
  // option.selected = false em CADA option de qualquer <select multiple>.
  function clearAllMultiSelects(scope) {
    if (!scope) return;
    var sels = scope.querySelectorAll('select');
    Array.prototype.forEach.call(sels, function (sel) {
      if (sel.hasAttribute('multiple')) {
        for (var i = 0; i < sel.options.length; i++) {
          sel.options[i].selected = false;
        }
      } else {
        // Para single select, volta para a opcao vazia (qualquer) se
        // existir, senao indice 0.
        var emptyIdx = -1;
        for (var j = 0; j < sel.options.length; j++) {
          if (!sel.options[j].value) { emptyIdx = j; break; }
        }
        sel.selectedIndex = (emptyIdx >= 0 ? emptyIdx : 0);
      }
    });
  }
  function bindLimparFix() {
    var modal = document.getElementById('modal-filtros');
    if (!modal || modal.__coplanLimparFix) return;
    modal.__coplanLimparFix = true;
    var btns = modal.querySelectorAll('.modal-footer .btn');
    Array.prototype.forEach.call(btns, function (b) {
      var t = (b.textContent || '').trim().toLowerCase();
      if (t.indexOf('limpar') === 0) {
        // Listener em fase de captura para rodar ANTES do handler antigo
        // (que faria selectedIndex=0). Apos rodarmos o clear correto,
        // o handler antigo nao tem efeito visivel — multi ja zerado.
        b.addEventListener('click', function () {
          clearAllMultiSelects(modal);
        }, true);
      }
    });
    // Idem para o botao "Limpar" da filter-bar principal (fora do modal).
    var visTab = document.getElementById('tab-visualizar');
    if (visTab && !visTab.__coplanLimparFix) {
      visTab.__coplanLimparFix = true;
      var topBtns = visTab.querySelectorAll('.filter-bar .btn');
      Array.prototype.forEach.call(topBtns, function (b) {
        var t = (b.textContent || '').trim().toLowerCase();
        if (t === 'limpar') {
          b.addEventListener('click', function () {
            clearAllMultiSelects(modal);
          }, true);
        }
      });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindLimparFix);
  } else {
    bindLimparFix();
  }
  // Re-bind quando o modal de filtros for repopulado (cada open/refresh).
  var btnOpen = document.getElementById('btn-modal-filtros');
  if (btnOpen && !btnOpen.__coplanLimparFixHook) {
    btnOpen.__coplanLimparFixHook = true;
    btnOpen.addEventListener('click', function () {
      setTimeout(bindLimparFix, 0);
    });
  }
})();

// ============================================================
// Toolbar Visualizar: condensar em "Mais acoes" (2026-05-08)
// Mantem apenas Atualizar / Excluir / Plano Obras visiveis. Demais
// botoes (Detalhamento / Relatorio / Nota / Snapshot / Salvar BD /
// Exportar BD / Copiar / Verificar / Incluir aprovadas) sao movidos
// para um dropdown "Mais acoes". Cancelar Plano fica visivel apenas
// quando o Plano esta ativo (ja tem display:none por default).
// ============================================================
(function () {
  if (window.__coplanToolbarMoreIIFE) return;
  window.__coplanToolbarMoreIIFE = true;

  // Texto exato (lowercase, trimmed) ou prefixo dos botoes que ficam
  // VISIVEIS na toolbar. Os demais vao pro "Mais acoes".
  var KEEP_VISIBLE_TEXTS = [
    'atualizar',
    'excluir',
    'plano obras',
    'cancelar plano',
  ];

  function btnText(btn) {
    return String(btn.textContent || '').replace(/\s+/g, ' ')
      .trim().toLowerCase();
  }

  function shouldKeep(btn) {
    var t = btnText(btn);
    if (!t) return false;
    for (var i = 0; i < KEEP_VISIBLE_TEXTS.length; i++) {
      var kw = KEEP_VISIBLE_TEXTS[i];
      // Atualiza Snapshot tem 'snapshot' antes de 'tec' — match
      // exato ou prefixo de 'atualizar' bate em 'atualizar' SEM
      // bater em 'atualizar valor' (que nao existe na toolbar).
      if (t === kw || t.indexOf(kw) === 0) {
        // Excecao: 'atualizar' NAO deve casar 'atualizar projeto'
        // (esse esta no menu contextual, nao na toolbar).
        if (kw === 'atualizar' && t.indexOf('atualizar projeto') === 0) {
          return false;
        }
        return true;
      }
    }
    return false;
  }

  function ensureMoreButton(toolbar) {
    var existing = toolbar.querySelector('#coplan-btn-toolbar-more');
    if (existing) return existing;
    var btn = document.createElement('button');
    btn.id = 'coplan-btn-toolbar-more';
    btn.className = 'btn sm';
    btn.type = 'button';
    btn.title = 'Mais acoes';
    btn.style.cssText = 'position:relative;';
    btn.innerHTML =
      '<i data-lucide="more-horizontal" style="width:14px;height:14px;"></i>'
      + ' Mais';
    toolbar.appendChild(btn);
    if (window.lucide && window.lucide.createIcons) {
      try { window.lucide.createIcons(); } catch (_e) {}
    }
    return btn;
  }

  function ensureDropdown() {
    var dd = document.getElementById('coplan-toolbar-dropdown');
    if (dd) return dd;
    dd = document.createElement('div');
    dd.id = 'coplan-toolbar-dropdown';
    dd.style.cssText =
      'position:fixed;display:none;flex-direction:column;gap:4px;'
      + 'background:white;border:1px solid var(--border);'
      + 'border-radius:8px;box-shadow:0 8px 24px rgba(15,23,42,.12);'
      + 'padding:6px;min-width:220px;z-index:99999;';
    document.body.appendChild(dd);
    // Click fora -> fecha
    document.addEventListener('click', function (ev) {
      if (dd.style.display === 'none') return;
      if (dd.contains(ev.target)) return;
      var moreBtn = document.getElementById('coplan-btn-toolbar-more');
      if (moreBtn && moreBtn.contains(ev.target)) return;
      dd.style.display = 'none';
    }, true);
    return dd;
  }

  function moveExtrasToDropdown(toolbar) {
    var dd = ensureDropdown();
    // Pega TODOS os filhos do .table-toolbar (botoes + label de checkbox)
    var nodes = Array.prototype.slice.call(toolbar.children);
    nodes.forEach(function (n) {
      if (n.id === 'coplan-btn-toolbar-more') return;
      // Buttons: filtra por texto. Outros nodes (label do checkbox):
      // sempre move pro dropdown.
      if (n.tagName === 'BUTTON') {
        if (shouldKeep(n)) return;
      }
      // Marca origem para conseguir devolver se necessario
      if (!n.dataset.toolbarMoved) {
        n.dataset.toolbarMoved = '1';
        // Estilo dentro do dropdown: stretch full-width, alinhado
        n.style.justifyContent = 'flex-start';
        n.style.width = '100%';
        n.style.textAlign = 'left';
        dd.appendChild(n);
      }
    });
  }

  function positionDropdown(btn, dd) {
    var rect = btn.getBoundingClientRect();
    var ddW = dd.offsetWidth || 220;
    var left = rect.right - ddW;
    if (left < 8) left = 8;
    if (left + ddW > window.innerWidth - 8) {
      left = window.innerWidth - ddW - 8;
    }
    dd.style.left = left + 'px';
    dd.style.top = (rect.bottom + 4) + 'px';
  }

  function reorganize() {
    var toolbar = document.querySelector(
      '#tab-visualizar .table-toolbar');
    if (!toolbar) return;
    // Cria dropdown se nao existe
    var dd = ensureDropdown();
    // Move extras
    moveExtrasToDropdown(toolbar);
    // Garante "Mais" no fim
    var more = ensureMoreButton(toolbar);
    // Move pro fim (caso outros injets tenham vindo depois)
    toolbar.appendChild(more);
    if (!more.__coplanBound) {
      more.__coplanBound = true;
      more.addEventListener('click', function (ev) {
        ev.stopPropagation();
        if (dd.style.display === 'flex') {
          dd.style.display = 'none';
          return;
        }
        dd.style.display = 'flex';
        positionDropdown(more, dd);
      });
    }
  }

  // Reorganiza apos cada render (botoes injetados via bindToolbar
  // podem aparecer depois do bootstrap)
  var lastRun = 0;
  function scheduleReorganize() {
    var now = Date.now();
    if (now - lastRun < 200) return;
    lastRun = now;
    setTimeout(reorganize, 60);
  }
  document.addEventListener('coplan:obras', scheduleReorganize);
  if (typeof window.coplanReady === 'function') {
    window.coplanReady(function () {
      // Tenta varias vezes para esperar todos os bindToolbar callbacks
      setTimeout(reorganize, 200);
      setTimeout(reorganize, 600);
      setTimeout(reorganize, 1500);
    });
  }
  if (document.readyState !== 'loading') {
    setTimeout(reorganize, 300);
  } else {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(reorganize, 300);
    });
  }
  window.coplanReorganizeToolbar = reorganize;
})();

// ============================================================
// Cenarios: branch marks na Visualizar (2026-05-08)
// Adiciona icone git-branch + tooltip nas linhas que tem override
// em algum cenario, MAS APENAS no modo banco principal (sem cenario
// ativo). No modo cenario ativo, a obra ja e' mostrada com os valores
// do cenario aplicados — nao precisa marcar.
// ============================================================
(function () {
  if (window.__coplanCenarioBranchesIIFE) return;
  window.__coplanCenarioBranchesIIFE = true;

  function api() { return window.pywebview && window.pywebview.api; }

  function escapeAttr(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function clearMarks() {
    var marks = document.querySelectorAll(
      '#obras-tbody .cenario-branch-mark');
    Array.prototype.forEach.call(marks, function (el) { el.remove(); });
  }

  function buildTooltip(branches) {
    // Tooltip multilinha (browsers respeitam newline no atributo title).
    if (!branches || !branches.length) return '';
    var lines = ['Versionamento em cenario(s):'];
    branches.forEach(function (b) {
      var em = b.atualizado_em ? ' · ' + b.atualizado_em : '';
      var por = b.atualizado_por ? ' · @' + b.atualizado_por : '';
      var qtd = (b.campos || []).length;
      lines.push(
        '\n• ' + (b.cenario || '?') + ' ('
        + qtd + ' alteracao' + (qtd === 1 ? '' : 'oes') + em + por + ')'
      );
      // Detalhe especial pra ano (mostrar X -> Y)
      if (b.ano_origem != null && b.ano_final != null
          && b.ano_origem !== b.ano_final) {
        lines.push('   - ano_ : ' + b.ano_origem + ' -> ' + b.ano_final);
      }
      // Outros campos (exceto ano_, que ja mostramos com seta)
      var outros = (b.campos || []).filter(function (c) {
        return c !== 'ano_';
      });
      outros.slice(0, 12).forEach(function (c) {
        lines.push('   - ' + c);
      });
      if (outros.length > 12) {
        lines.push('   ... +' + (outros.length - 12) + ' campo(s)');
      }
    });
    return lines.join('\n');
  }

  function applyMarks(itemsMap) {
    var tbody = document.getElementById('obras-tbody');
    if (!tbody) return;
    // Posicao da celula COD no <tr>: depende do codIdx + 1 (offset
    // do td.check do checkbox). rawRowHtml em main_web.py:10122 monta
    // <tr><td.check><td.mono x N> sem usar class="cod" — entao buscar
    // por classe nao funciona; usar posicao via codIdx.
    var cols = window.coplanObrasColumns || [];
    var codIdx = cols.indexOf('cod');
    if (codIdx < 0) {
      console.warn('[coplan] branches: cod nao esta em columns');
      return;
    }
    var trs = tbody.querySelectorAll('tr[data-cod]');
    Array.prototype.forEach.call(trs, function (tr) {
      var cod = tr.getAttribute('data-cod') || '';
      var existing = tr.querySelector('.cenario-branch-mark');
      if (existing) existing.remove();
      var branches = itemsMap[cod];
      if (!branches || !branches.length) return;
      // Posicao: tr.children[0] = checkbox; cells de dados comecam em 1
      var tdCod = tr.children[codIdx + 1];
      if (!tdCod) return;
      var span = document.createElement('span');
      span.className = 'cenario-branch-mark';
      span.style.cssText =
        'display:inline-flex;align-items:center;justify-content:center;'
        + 'padding:1px 5px;border-radius:3px;'
        + 'background:oklch(0.72 0.20 55);color:white;'
        + 'margin-left:6px;cursor:help;vertical-align:middle;'
        + 'font-size:9px;font-weight:700;gap:2px;line-height:1;';
      span.title = buildTooltip(branches);
      span.innerHTML =
        '<i data-lucide="git-branch" style="width:10px;height:10px;"></i>'
        + branches.length;
      tdCod.appendChild(span);
    });
    if (window.lucide && window.lucide.createIcons) {
      try { window.lucide.createIcons(); } catch (_e) {}
    }
  }

  function refresh() {
    // Suprime marks quando cenario ativo (a obra ja vem com overrides
    // aplicados, nao precisa marcar).
    var sel = document.getElementById('header-cenario');
    var ativo = sel && sel.value ? sel.value : '';
    if (ativo) {
      clearMarks();
      return;
    }
    var a = api();
    if (!(a && a.cenario_obras_branches)) return;
    var tbody = document.getElementById('obras-tbody');
    if (!tbody) return;
    var trs = tbody.querySelectorAll('tr[data-cod]');
    if (!trs.length) {
      clearMarks();
      return;
    }
    var cods = [];
    Array.prototype.forEach.call(trs, function (tr) {
      var cod = tr.getAttribute('data-cod') || '';
      if (cod) cods.push(cod);
    });
    if (!cods.length) return;
    a.cenario_obras_branches(cods).then(function (r) {
      if (!r || !r.ok) return;
      applyMarks(r.items || {});
    }).catch(function (e) {
      console.warn('[coplan] cenario_obras_branches:', e);
    });
  }

  // Aplica marks quando obras sao re-renderizadas
  document.addEventListener('coplan:obras', function () {
    setTimeout(refresh, 50);
  });
  // Tambem ao trocar cenario (quando saimos do cenario, marks reaparecem)
  document.addEventListener('coplan:cenario-changed', function () {
    setTimeout(refresh, 200);  // delay pra coplanLoadObras terminar
  });
  // Apos save (obras-changed), recalcula marks
  document.addEventListener('coplan:obras-changed', function () {
    setTimeout(refresh, 200);
  });

  window.coplanCenarioBranchesRefresh = refresh;
})();

// ============================================================
// Cenarios DB-backed (Sprint A, 2026-05-08)
// Combo no header + banner de cenario ativo + redirecionamento de
// save para overrides. Backend faz todo o trabalho pesado; este
// IIFE so cuida da UI: popular combo, troca, banner, refresh.
// ============================================================
(function () {
  if (window.__coplanCenarioIIFE) return;
  window.__coplanCenarioIIFE = true;

  function api() { return window.pywebview && window.pywebview.api; }
  function $(id) { return document.getElementById(id); }
  function toast(msg, lvl) {
    if (window.coplanToast) window.coplanToast(msg, lvl || 'info');
    else console.log('[' + (lvl || 'info') + ']', msg);
  }
  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'})[c];
    });
  }

  var loaded = false;

  function setBannerVisibility(_visible) {
    // No-op: banner full-width foi removido em 2026-05-08; badge
    // permanente vive no footer da sidebar agora. Mantemos a funcao
    // como stub para nao quebrar callers antigos.
  }

  function applySaveButtonStyle(active) {
    var btn = $('cad-btn-salvar');
    if (!btn) return;
    if (active) {
      btn.classList.add('warn');
      btn.style.background = 'oklch(0.65 0.18 60)';
      btn.style.borderColor = 'oklch(0.55 0.18 60)';
      btn.title = 'Salvar no cenario (alteracoes ficam isoladas)';
      // Substitui o texto "Salvar Obra" por "Salvar no cenario"
      // Preserva o icone e o kbd. Identifica o text node entre eles.
      btn.dataset.cenarioActive = '1';
      var html = btn.innerHTML;
      if (!btn.dataset.savedDefaultHtml) {
        btn.dataset.savedDefaultHtml = html;
      }
      btn.innerHTML = '<i data-lucide="save"></i> Salvar no cenario'
        + '<kbd style="opacity:.7;font-size:10px;margin-left:6px;">Ctrl+B</kbd>';
      if (window.lucide && window.lucide.createIcons) {
        try { window.lucide.createIcons(); } catch (_e) {}
      }
    } else {
      btn.classList.remove('warn');
      btn.style.background = '';
      btn.style.borderColor = '';
      btn.title = 'Salvar obra (Ctrl+B)';
      delete btn.dataset.cenarioActive;
      if (btn.dataset.savedDefaultHtml) {
        btn.innerHTML = btn.dataset.savedDefaultHtml;
        delete btn.dataset.savedDefaultHtml;
        if (window.lucide && window.lucide.createIcons) {
          try { window.lucide.createIcons(); } catch (_e) {}
        }
      }
    }
  }

  function applyState(ativo, stats) {
    // 1. Combo no header
    var sel = $('header-cenario');
    if (sel) sel.value = ativo || '';

    // Texto consolidado de stats (mostrado no badge da sidebar)
    var statsTxt = '';
    if (ativo) {
      var parts = [];
      if (stats && stats.ano_final_count) {
        parts.push(stats.ano_final_count + ' obra(s)');
      }
      if (stats && stats.overrides_count) {
        parts.push(stats.overrides_count + ' override(s)');
      }
      statsTxt = parts.join(' · ');
    }

    // 2. Badge no footer da sidebar (acima do nome do user).
    //    SEMPRE visivel: verde "Banco principal" / laranja "Cenário ativo".
    //    Botao "Sair do cenario" so visivel quando cenario ativo.
    var sbBadge = $('sb-cenario-badge');
    var sbNome = $('sb-cenario-nome');
    var sbLabel = $('sb-cenario-label');
    var sbStats = $('sb-cenario-stats');
    var sbSair = $('sb-cenario-sair');
    if (sbBadge && sbNome && sbLabel) {
      if (ativo) {
        sbBadge.dataset.modo = 'cenario';
        sbBadge.style.background =
          'linear-gradient(180deg, oklch(0.78 0.20 60) 0%,'
          + ' oklch(0.72 0.20 55) 100%)';
        sbLabel.innerHTML =
          '<i data-lucide="alert-triangle" style="width:11px;height:11px;flex-shrink:0;"></i>'
          + '<span style="overflow:hidden;text-overflow:ellipsis;'
          + 'white-space:nowrap;">Cenário ativo</span>';
        sbNome.textContent = ativo;
        if (sbStats) {
          if (statsTxt) {
            sbStats.textContent = statsTxt;
            sbStats.style.display = 'block';
          } else {
            sbStats.style.display = 'none';
          }
        }
        if (sbSair) sbSair.style.display = 'inline-flex';
      } else {
        sbBadge.dataset.modo = 'banco';
        sbBadge.style.background =
          'linear-gradient(180deg, oklch(0.55 0.13 155) 0%,'
          + ' oklch(0.48 0.13 155) 100%)';
        sbLabel.innerHTML =
          '<i data-lucide="database" style="width:11px;height:11px;flex-shrink:0;"></i>'
          + '<span style="overflow:hidden;text-overflow:ellipsis;'
          + 'white-space:nowrap;">Banco principal</span>';
        sbNome.textContent = 'edição direta';
        if (sbStats) sbStats.style.display = 'none';
        if (sbSair) sbSair.style.display = 'none';
      }
    }

    // 4. Indicador na status bar (rodape, sempre visivel em qualquer aba)
    //    SEMPRE visivel: verde "Banco: principal" / laranja "Cenário: <nome>"
    var stCen = $('status-cenario');
    var stIcon = $('status-cenario-icon');
    var stCenLabel = $('status-cenario-label');
    var stNome = $('status-cenario-nome');
    if (stCen && stNome && stCenLabel) {
      if (ativo) {
        stCen.dataset.modo = 'cenario';
        stCen.style.background = 'oklch(0.72 0.20 55)';
        stCenLabel.textContent = 'Cenário:';
        stNome.textContent = ativo;
        if (stIcon) stIcon.setAttribute('data-lucide', 'alert-triangle');
      } else {
        stCen.dataset.modo = 'banco';
        stCen.style.background = 'oklch(0.55 0.13 155)';
        stCenLabel.textContent = 'Banco:';
        stNome.textContent = 'principal';
        if (stIcon) stIcon.setAttribute('data-lucide', 'database');
      }
    }

    // 5. Borda laranja no app inteiro + tint na sidebar
    var app = document.getElementById('app');
    if (app) {
      if (ativo) app.classList.add('cenario-ativo');
      else app.classList.remove('cenario-ativo');
    }

    // 6. Botao Salvar muda texto/cor
    applySaveButtonStyle(!!ativo);

    // Lucide: re-cria icones que foram inseridos dinamicamente
    if (window.lucide && window.lucide.createIcons) {
      try { window.lucide.createIcons(); } catch (_e) {}
    }

    // Notifica outros consumidores (Visualizar, Resumo) que o
    // estado de cenario mudou. Eles devem reler obras.
    document.dispatchEvent(new CustomEvent('coplan:cenario-changed', {
      detail: { ativo: ativo || '' },
    }));
  }

  function loadCombo() {
    var sel = $('header-cenario');
    if (!sel) return Promise.resolve();
    var a = api();
    if (!(a && a.cenario_list)) return Promise.resolve();
    return a.cenario_list().then(function (r) {
      var cenarios = (r && r.cenarios) || [];
      var nomes = cenarios.map(function (c) { return c.nome; });
      var html = '<option value="">— Sem cenário —</option>';
      cenarios.forEach(function (c) {
        var nome = escapeHtml(c.nome);
        var titulo = c.descricao
          ? escapeHtml(c.descricao) : '';
        html += '<option value="' + nome + '"'
          + (titulo ? ' title="' + titulo + '"' : '')
          + '>' + nome + ' (' + (c.total_obras || 0) + ')</option>';
      });
      sel.innerHTML = html;
      loaded = true;
      // Detecta cenario fantasma: config tem 'cenario_ativo' apontando
      // para nome que nao existe mais em cenarios_meta (deletado no
      // CAPEX, banco trocou, etc.). Avisa o user + limpa.
      if (a && a.cenario_active_get) {
        a.cenario_active_get().then(function (st) {
          if (!st || !st.ok) return;
          var ativo = st.ativo || '';
          if (ativo && nomes.indexOf(ativo) < 0) {
            console.warn(
              '[coplan] cenario fantasma:', ativo,
              '(nao existe em cenarios_meta — limpando)');
            toast(
              'Cenário "' + ativo + '" não foi encontrado no banco'
              + ' (foi deletado/recriado no CAPEX?). Voltando ao'
              + ' modo banco principal.', 'warn');
            if (a.cenario_active_set) {
              a.cenario_active_set('').then(function () {
                refreshActive();
              }).catch(function (err) {
                console.warn(
                  '[coplan] cenario_active_set vazio falhou:', err);
                if (typeof window.coplanToast === 'function') {
                  window.coplanToast(
                    'Falha ao limpar cenário fantasma: '
                    + ((err && err.message) || err || '?'),
                    'error');
                }
                if (window.coplanReportError) {
                  window.coplanReportError(
                    'Limpar cenário fantasma', 'cenario_active_set',
                    { error: String(
                      (err && err.message) || err || '?') });
                }
              });
            }
          } else {
            // Sincroniza UI com estado atual
            applyState(ativo, st);
          }
        }).catch(function (err) {
          console.warn('[coplan] cenario_active_get falhou:', err);
        });
      } else {
        return refreshActive();
      }
    }).catch(function (e) {
      console.warn('[coplan] cenario_list falhou:', e);
    });
  }

  function refreshActive() {
    var a = api();
    if (!(a && a.cenario_active_get)) return Promise.resolve();
    return a.cenario_active_get().then(function (r) {
      if (!r || !r.ok) return;
      applyState(r.ativo || '', r);
    }).catch(function (e) {
      console.warn('[coplan] cenario_active_get falhou:', e);
    });
  }

  function bindCombo() {
    var sel = $('header-cenario');
    if (!sel || sel.__coplanBound) return;
    sel.__coplanBound = true;
    // Auto-refresh ao focar (Tab ou primeiro click): garante que
    // cenarios criados no CAPEX depois do boot do COPLAN sejam
    // visiveis. NAO usa mousedown — Chrome reescreve innerHTML do
    // <select> enquanto o user clica e o dropdown nao abre.
    sel.addEventListener('focus', function () {
      // Throttle: nao chama mais de 1x por 1s (evita corrida com
      // outras chamadas a loadCombo e nao reescreve enquanto user
      // tem o dropdown aberto).
      var now = Date.now();
      if (sel.__lastReload && (now - sel.__lastReload) < 1000) return;
      sel.__lastReload = now;
      loadCombo();
    });
    sel.addEventListener('change', function () {
      var nome = sel.value || '';
      var a = api();
      if (!(a && a.cenario_active_set)) return;
      a.cenario_active_set(nome).then(function (r) {
        if (!r || !r.ok) {
          toast('Falha: ' + ((r && r.error) || '?'), 'error');
          // Se o cenario nao foi encontrado no banco (foi deletado
          // entre o load do combo e o click), recarrega o combo +
          // volta para "Sem cenario".
          if (r && r.error && r.error.indexOf('nao encontrado') >= 0) {
            sel.value = '';
            loadCombo();
          }
          return;
        }
        if (nome) {
          toast('Cenario ativado: ' + nome
            + ' (alteracoes ficam isoladas)', 'warn');
        } else {
          toast('Cenario desativado: voltando ao modo normal', 'info');
        }
        // Refresh state + dispara reload de obras
        refreshActive().then(function () {
          // Notifica Visualizar para recarregar obras
          if (typeof window.coplanLoadObras === 'function') {
            window.coplanLoadObras();
          }
          document.dispatchEvent(new CustomEvent('coplan:obras-changed', {
            detail: { source: 'cenario:active_set' },
          }));
        });
      }).catch(function (err) {
        console.warn('[coplan] cenario_active_set falhou:', err);
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(
            'Falha ao trocar cenário: '
            + ((err && err.message) || err || '?'),
            'error');
        }
        if (window.coplanReportError) {
          window.coplanReportError(
            'Trocar cenário ativo', 'cenario_active_set',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
  }

  function bindBannerExit() {
    // Botao "Sair do cenario" agora vive na sidebar (sb-cenario-sair).
    // Mantemos o ID antigo cenario-banner-sair como fallback caso
    // alguma version older do HTML ainda tenha.
    ['sb-cenario-sair', 'cenario-banner-sair'].forEach(function (id) {
      var btn = $(id);
      if (!btn || btn.__coplanBound) return;
      btn.__coplanBound = true;
      btn.addEventListener('click', function () {
        var sel = $('header-cenario');
        if (sel) {
          sel.value = '';
          sel.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
    });
  }

  function bootstrap() {
    bindCombo();
    bindBannerExit();
    loadCombo();
  }

  if (typeof window.coplanReady === 'function') {
    window.coplanReady(bootstrap);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }

  // Recarrega combo apos o CAPEX poder ter criado novos cenarios.
  // (sem evento direto, mas o user pode ter aberto o app no meio do
  // workflow; expomos refresh manual.)
  window.coplanCenarioReload = loadCombo;
  window.coplanCenarioRefreshActive = refreshActive;
})();

// ============================================================
// Apoio DB-backed (2026-05-07): botao "Atualizar apoio" + status
// Injetado no card Empresa de Configuracoes (sub-aba Geral). Mostra
// info da ultima importacao + botao para forcar reload do xlsx
// (reescreve tabelas apoio_* no banco). Reusa coplanProgress (Bloco 5).
// ============================================================
(function () {
  if (window.__coplanApoioReloadIIFE) return;
  window.__coplanApoioReloadIIFE = true;

  function api() { return window.pywebview && window.pywebview.api; }
  function toast(msg, lvl) {
    if (window.coplanToast) window.coplanToast(msg, lvl || 'info');
    else console.log('[' + (lvl || 'info') + ']', msg);
  }

  function fmtDateBr(iso) {
    if (!iso) return '—';
    // ISO -> dd/mm/aaaa hh:mm
    var m = String(iso).match(
      /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if (!m) return iso;
    return m[3] + '/' + m[2] + '/' + m[1] + ' ' + m[4] + ':' + m[5];
  }

  function findEmpresaCard() {
    // Card "Empresa" em Configuracoes > Geral
    var titles = document.querySelectorAll(
      '#tab-config .card .card-title');
    for (var i = 0; i < titles.length; i++) {
      var t = (titles[i].textContent || '').trim().toLowerCase();
      if (t.indexOf('empresa') >= 0) return titles[i].closest('.card');
    }
    return null;
  }

  function injectApoioBox() {
    var card = findEmpresaCard();
    if (!card) return;
    if (card.querySelector('#coplan-apoio-status-box')) return;
    var body = card.querySelector('.card-body');
    if (!body) return;
    var box = document.createElement('div');
    box.id = 'coplan-apoio-status-box';
    box.style.cssText =
      'margin-top:12px;padding:10px 12px;'
      + 'border:1px solid var(--border);border-radius:6px;'
      + 'background:var(--surface-2);font-size:12px;'
      + 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;';
    box.innerHTML =
      '<i data-lucide="database" style="width:14px;height:14px;'
      + 'color:var(--text-soft)"></i>'
      + '<span style="color:var(--text-soft);">Apoio (banco):</span>'
      + '<span class="mono" id="coplan-apoio-status-info">—</span>'
      + '<span class="grow" style="flex:1;"></span>'
      + '<button class="btn sm" id="coplan-apoio-btn-reload"'
      + ' type="button" title="Reimporta a planilha de apoio'
      + ' (reescreve tabelas apoio_* no banco)">'
      + '<i data-lucide="refresh-cw"></i> Atualizar apoio</button>';
    body.appendChild(box);
    if (window.lucide && window.lucide.createIcons) {
      try { window.lucide.createIcons(); } catch (_e) {}
    }
    bindReloadBtn();
    refreshStatus();
  }

  function refreshStatus() {
    var info = document.getElementById('coplan-apoio-status-info');
    if (!info) return;
    var a = api();
    if (!(a && a.apoio_meta)) {
      info.textContent = 'API indisponivel';
      return;
    }
    a.apoio_meta().then(function (m) {
      if (!m || !m.ok) {
        info.textContent = 'erro: ' + ((m && m.error) || '?');
        info.style.color = 'var(--danger)';
        return;
      }
      if (!m.last_imported_at) {
        info.textContent = 'nunca importado';
        info.style.color = 'var(--warning)';
        return;
      }
      var nome = (m.last_path || '').split(/[\\/]/).pop() || '?';
      info.textContent = nome + ' · ' + m.sheet_count
        + ' aba(s) · importado em ' + fmtDateBr(m.last_imported_at)
        + (m.last_user ? ' por ' + m.last_user : '');
      info.style.color = m.hidratado
        ? 'var(--success)' : 'var(--text-soft)';
      info.title = 'Path completo: ' + (m.last_path || '?');
    }).catch(function (e) {
      info.textContent = 'erro: ' + e;
      info.style.color = 'var(--danger)';
    });
  }

  function bindReloadBtn() {
    var btn = document.getElementById('coplan-apoio-btn-reload');
    if (!btn || btn.__bound) return;
    btn.__bound = true;
    btn.addEventListener('click', function () {
      var a = api();
      if (!(a && a.apoio_meta)) return toast('API indisponivel', 'error');
      a.apoio_meta().then(function (m) {
        var hasPath = !!(m && m.ok && m.last_path);
        var pickNew = false;
        if (hasPath) {
          // Pergunta: usar mesma planilha ou escolher nova?
          pickNew = !window.confirm(
            'Atualizar apoio usando a mesma planilha?\n\n'
            + (m.last_path || '')
            + '\n\nOK = usar mesma  /  Cancelar = escolher outra'
          );
        } else {
          pickNew = true;
        }
        if (pickNew) {
          if (!a.pick_apoio_file) {
            return toast('pick_apoio_file indisponivel', 'error');
          }
          return a.pick_apoio_file().then(function (r) {
            if (!r || !r.ok) {
              if (r && r.error && r.error !== 'cancelado') {
                toast('Falha: ' + r.error, 'error');
              }
              return;
            }
            startReload(r.path);
          }).catch(function (err) {
            console.warn('[coplan] pick_apoio_file falhou:', err);
            toast('Falha ao escolher planilha: '
              + ((err && err.message) || err || '?'), 'error');
            if (window.coplanReportError) {
              window.coplanReportError(
                'Escolher planilha de apoio', 'pick_apoio_file',
                { error: String((err && err.message) || err || '?') });
            }
          });
        }
        startReload('');  // usa last_path
      }).catch(function (err) {
        console.warn('[coplan] apoio_meta falhou:', err);
        toast('Falha ao consultar apoio: '
          + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Consultar metadados de apoio', 'apoio_meta',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
  }

  function startReload(path) {
    var a = api();
    if (!(a && a.apoio_reload_from_xlsx_async)) {
      return toast('apoio_reload_from_xlsx_async indisponivel', 'error');
    }
    if (window.coplanProgress && window.coplanProgress.start) {
      window.coplanProgress.start(
        'Atualizando apoio...',
        function (result, errorStr, _cancelled) {
          if (errorStr) {
            toast('Falha: ' + errorStr, 'error');
            return;
          }
          if (result && result.ok) {
            var nAlim = (result.alimentadores || []).length;
            var nSheets = result.import_sheets || 0;
            if (result.import_warning) {
              toast('Apoio em memoria, mas tabelas NAO gravadas: '
                + result.import_warning, 'error');
            } else {
              toast('Apoio atualizado: ' + nSheets
                + ' tabela(s) criadas no banco, '
                + nAlim + ' alim. em cache.', 'success');
            }
            refreshStatus();
            document.dispatchEvent(new CustomEvent('coplan:apoio-changed'));
          } else {
            toast('Falha: '
              + ((result && result.error) || 'desconhecida'), 'error');
          }
        }
      );
      a.apoio_reload_from_xlsx_async(path).then(function (st) {
        if (st && !st.started) {
          if (window.coplanProgress && window.coplanProgress.close) {
            window.coplanProgress.close();
          }
          toast('Falha ao iniciar: ' + (st.error || '?'), 'error');
        }
      }).catch(function (err) {
        console.warn('[coplan] apoio_reload_from_xlsx_async falhou:', err);
        if (window.coplanProgress && window.coplanProgress.close) {
          window.coplanProgress.close();
        }
        toast('Falha ao atualizar apoio: '
          + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Atualizar apoio', 'apoio_reload_from_xlsx_async',
            { error: String((err && err.message) || err || '?') });
        }
      });
    } else {
      // Fallback sem modal de progresso (sincrono)
      toast('Atualizando apoio...', 'info');
      a.apoio_reload_from_xlsx(path).then(function (r) {
        if (r && r.ok) {
          toast('Apoio atualizado', 'success');
          refreshStatus();
          document.dispatchEvent(new CustomEvent('coplan:apoio-changed'));
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        console.warn('[coplan] apoio_reload_from_xlsx falhou:', err);
        toast('Falha ao atualizar apoio: '
          + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Atualizar apoio', 'apoio_reload_from_xlsx',
            { error: String((err && err.message) || err || '?') });
        }
      });
    }
  }

  // Reage a mudanca de aba: ao abrir Configuracoes (sub-aba Geral),
  // injeta a box.
  document.addEventListener('coplan:tab', function (ev) {
    var name = (ev && ev.detail && ev.detail.name) || '';
    if (name === 'config') {
      setTimeout(injectApoioBox, 100);
    }
  });
  // Tambem injeta se Configuracoes ja esta ativa no boot.
  if (typeof window.coplanReady === 'function') {
    window.coplanReady(function () {
      var t = document.getElementById('tab-config');
      if (t && t.classList.contains('active')) {
        setTimeout(injectApoioBox, 100);
      }
    });
  }

  // Expose para integracoes manuais.
  window.coplanApoioRefreshStatus = refreshStatus;
  window.coplanApoioStartReload = startReload;
})();

// ============================================================
// Visualizar Sprint 1 - Atalhos globais (Auditoria M3 + M27)
//   M3:  Esc limpa busca global quando Visualizar ativa
//   M27: Ctrl+L foca busca global (texto da ajuda mencionava mas
//        nao tinha implementacao)
// ============================================================
(function () {
  if (window.__coplanVisShortcutsIIFE) return;
  window.__coplanVisShortcutsIIFE = true;

  function visTabActive() {
    var t = document.getElementById('tab-visualizar');
    return !!(t && t.classList.contains('active'));
  }
  function searchInput() {
    return document.getElementById('filter-input')
      || document.querySelector(
          '#tab-visualizar .filter-bar .search-input input');
  }

  document.addEventListener('keydown', function (e) {
    // Ctrl+L (ou Cmd+L) -> foca busca da Visualizar.
    if ((e.ctrlKey || e.metaKey) && (e.key === 'l' || e.key === 'L')) {
      // Se Visualizar nao esta ativa, troca pra ela primeiro.
      if (!visTabActive() && typeof window.coplanSetTab === 'function') {
        window.coplanSetTab('visualizar');
      }
      var inp = searchInput();
      if (inp) {
        e.preventDefault();
        inp.focus();
        inp.select();
      }
      return;
    }
    // Esc -> limpa busca da Visualizar (apenas quando Visualizar ativa
    // E foco NAO esta em outro input/textarea).
    if (e.key === 'Escape' && visTabActive()) {
      var t = e.target;
      var tag = t && t.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
          || (t && t.isContentEditable)) {
        // Se foco esta no proprio input de busca, limpa.
        if (t.id === 'filter-input') {
          if ((t.value || '').length > 0) {
            t.value = '';
            t.dispatchEvent(new Event('input', { bubbles: true }));
            e.preventDefault();
          }
        }
        return;
      }
      // Foco fora de inputs: limpa o filter-input se tiver texto.
      var inp2 = searchInput();
      if (inp2 && (inp2.value || '').length > 0) {
        inp2.value = '';
        inp2.dispatchEvent(new Event('input', { bubbles: true }));
        e.preventDefault();
      }
    }
  });
})();

// ============================================================
// Bloco 5 - UX longa-duracao (Auditoria #44 progress + #45 onerror)
// IIFE coplanProgress: gerencia modal de progresso para operacoes
// rodando em worker thread no Python. Polling 200ms de progress_state.
// Tambem: global error handlers (window.onerror + unhandledrejection).
// ============================================================
(function () {
  if (window.__coplanProgressIIFE) return;
  window.__coplanProgressIIFE = true;

  function $(id) { return document.getElementById(id); }
  function api() { return window.pywebview && window.pywebview.api; }

  var P = {
    pollTimer: null,
    onComplete: null,    // callback(result, error, cancelled)
    startMs: 0,
    opId: '',
    closing: false
  };

  function fmtElapsed(ms) {
    var s = Math.max(0, Math.floor(ms / 1000));
    if (s < 60) return s + 's';
    var m = Math.floor(s / 60);
    var rs = s - m * 60;
    return m + 'm ' + rs + 's';
  }

  function open(label) {
    var modal = $('coplan-progress-modal');
    if (!modal) return;
    var titleEl = $('coplan-progress-title');
    var labelEl = $('coplan-progress-label');
    var bar = $('coplan-progress-bar');
    var counter = $('coplan-progress-counter');
    var elapsed = $('coplan-progress-elapsed');
    var cancelBtn = $('coplan-progress-cancel');
    if (titleEl) titleEl.textContent = 'Operacao em andamento';
    if (labelEl) labelEl.textContent = label || 'Iniciando...';
    if (bar) bar.style.width = '0%';
    if (counter) counter.textContent = '0 / 0';
    if (elapsed) elapsed.textContent = '0s';
    if (cancelBtn) {
      cancelBtn.disabled = false;
      cancelBtn.textContent = '';
      cancelBtn.innerHTML = '<i data-lucide="x"></i> Cancelar';
    }
    modal.style.display = 'grid';
    if (window.lucide && window.lucide.createIcons) {
      try { window.lucide.createIcons(); } catch (_e) {}
    }
    P.startMs = Date.now();
    P.closing = false;
  }

  function close() {
    P.closing = true;
    if (P.pollTimer) {
      clearInterval(P.pollTimer);
      P.pollTimer = null;
    }
    var modal = $('coplan-progress-modal');
    if (modal) modal.style.display = 'none';
  }

  function applySnapshot(s) {
    var labelEl = $('coplan-progress-label');
    var bar = $('coplan-progress-bar');
    var counter = $('coplan-progress-counter');
    var elapsed = $('coplan-progress-elapsed');
    var processed = Number(s.processed) || 0;
    var total = Number(s.total) || 0;
    var pct = total > 0 ? Math.min(100, (processed / total) * 100) : 0;
    if (labelEl && s.label) labelEl.textContent = s.label;
    if (bar) bar.style.width = pct.toFixed(1) + '%';
    if (counter) counter.textContent = processed + ' / ' + total;
    if (elapsed) elapsed.textContent = fmtElapsed(Date.now() - P.startMs);
  }

  function startPolling() {
    if (P.pollTimer) clearInterval(P.pollTimer);
    var a = api();
    if (!(a && a.progress_state)) {
      console.warn('[coplan] progress_state nao disponivel');
      return;
    }
    P.pollTimer = setInterval(function () {
      a.progress_state().then(function (s) {
        if (!s || P.closing) return;
        applySnapshot(s);
        if (s.finished) {
          clearInterval(P.pollTimer);
          P.pollTimer = null;
          var cb = P.onComplete;
          P.onComplete = null;
          close();
          if (typeof cb === 'function') {
            try {
              cb(s.result, s.error, !!(s.result && s.result.cancelled));
            } catch (e) {
              console.warn('[coplan] progress onComplete erro:', e);
            }
          }
        }
      }).catch(function (e) {
        console.warn('[coplan] progress poll erro:', e);
      });
    }, 200);
  }

  // Cancel handler (bind 1x)
  document.addEventListener('DOMContentLoaded', function () {
    var btn = $('coplan-progress-cancel');
    if (btn && !btn.__coplanBound) {
      btn.__coplanBound = true;
      btn.addEventListener('click', function () {
        var a = api();
        if (!(a && a.progress_cancel)) return;
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="loader"></i> Cancelando...';
        if (window.lucide && window.lucide.createIcons) {
          try { window.lucide.createIcons(); } catch (_e) {}
        }
        a.progress_cancel().catch(function (e) {
          console.warn('[coplan] progress_cancel erro:', e);
        });
      });
    }
  });

  // Public API: open + start polling + onComplete
  // Uso: window.coplanProgress.run(label, onComplete)
  //   onComplete(result, errorStr, cancelled) chamado quando finished=true
  window.coplanProgress = {
    open: open,
    close: close,
    start: function (label, onComplete) {
      open(label);
      P.onComplete = onComplete || null;
      startPolling();
    }
  };
})();

// ============================================================
// coplanAtualizarBulk: rota bulk de "Atualizar Valor" pelo backend
// async (worker thread + coplanProgress). Usado pelo botao toolbar
// e pelo context menu multi-cods. Fallback para o sync se o async
// nao estiver disponivel (versao antiga do backend).
// ============================================================
(function () {
  if (window.coplanAtualizarBulk) return;

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

  function summarize(r) {
    if (!r) return 'Falha desconhecida';
    var falhas = r.falhas_total || 0;
    var inex = (r.chaves_inexistentes || []).length;
    var preserv = r.preservadas || 0;
    var partes = [(r.atualizadas || 0) + ' atualizada(s)'];
    if (preserv > 0) partes.push(preserv + ' preservada(s)');
    if (falhas > 0) partes.push(falhas + ' falha(s)');
    if (inex > 0) partes.push(inex + ' chave(s) inexistente(s)');
    return partes.join(' / ');
  }

  function level(r) {
    if (!r || !r.ok) return 'error';
    var falhas = r.falhas_total || 0;
    var inex = (r.chaves_inexistentes || []).length;
    return (falhas > 0 || inex > 0) ? 'warn' : 'info';
  }

  // Critério de "houve erro" = qualquer coisa diferente de sucesso pleno:
  // !ok, ou falhas_total>0, ou chaves_inexistentes nao vazio, ou cancelled.
  function hasErrors(r) {
    if (!r) return true;
    if (!r.ok) return true;
    if (r.cancelled) return true;
    if ((r.falhas_total || 0) > 0) return true;
    if ((r.chaves_inexistentes || []).length > 0) return true;
    if ((r.preservadas || 0) > 0) return true;
    return false;
  }

  function showDetailsModal(r, n) {
    if (typeof window.coplanShowErrorDetails !== 'function') return;
    var sections = [];
    if (r && r.falhas && r.falhas.length) {
      sections.push({
        label: 'Falhas (' + (r.falhas_total || r.falhas.length) + ')',
        lines: r.falhas.slice(),
      });
    }
    if (r && r.chaves_inexistentes && r.chaves_inexistentes.length) {
      sections.push({
        label: 'Chaves inexistentes (' + r.chaves_inexistentes.length + ')',
        lines: r.chaves_inexistentes.slice(),
      });
    }
    if (r && r.preservadas_msgs && r.preservadas_msgs.length) {
      sections.push({
        label: 'Valores preservados (' + r.preservadas_msgs.length + ')',
        lines: r.preservadas_msgs.slice(),
      });
    }
    if (r && r.error) {
      sections.push({ label: 'Erro', lines: [String(r.error)] });
    }
    window.coplanShowErrorDetails({
      title: 'Atualizar valor_obra ('
        + (n != null ? n + ' obra(s) selecionada(s)' : 'lote') + ')',
      summary: summarize(r),
      sections: sections,
      op: 'atualizar',
      logPath: (r && r.log_path) || '',
    });
    // Toast adicional com o caminho do log -- garante que o usuario
    // ve o path mesmo se fechar o modal antes de olhar.
    if (r && r.log_path && typeof window.coplanToast === 'function') {
      window.coplanToast('Log salvo: ' + r.log_path, 'info');
    }
  }

  window.coplanAtualizarBulk = function (cods) {
    var api = window.pywebview && window.pywebview.api;
    if (!api || !api.atualizar_obras_valores) {
      toast('API indisponivel', 'error');
      return;
    }
    var n = (cods && cods.length) || 0;
    var label = 'Recalculando ' + n + ' obra(s)...';

    var hasAsync = !!(api.atualizar_obras_valores_async
                      && window.coplanProgress
                      && window.coplanProgress.start);

    if (!hasAsync) {
      // Fallback sync: aviso porque pode travar com muitas obras.
      toast(label, 'info');
      api.atualizar_obras_valores(cods).then(function (r) {
        if (r && r.cancelled) {
          toast('Cancelado', 'warn');
        } else if (!r || !r.ok) {
          toast('Falhou: ' + (r && r.error || '?'), 'error');
        } else {
          toast(summarize(r), level(r));
        }
        if (hasErrors(r)) showDetailsModal(r, n);
        if (typeof window.coplanLoadObras === 'function') {
          window.coplanLoadObras();
        }
      }).catch(function (e) {
        toast('Erro: ' + (e && e.message || e), 'error');
      });
      return;
    }

    // Async: abre progress modal e dispara worker; polling cuida do resto.
    window.coplanProgress.start(label, function (result, errStr, cancelled) {
      var done = false;
      if (cancelled || (result && result.cancelled)) {
        toast(
          'Cancelado'
            + (result ? ' (' + (result.atualizadas || 0)
                + ' ja atualizada(s))' : ''),
          'warn'
        );
      } else if (errStr) {
        toast('Falhou: ' + errStr, 'error');
        // Sintetiza result minimo para o modal
        if (!result) result = { ok: false, error: errStr };
      } else if (!result || !result.ok) {
        toast('Falhou: ' + ((result && result.error) || '?'), 'error');
      } else {
        toast(summarize(result), level(result));
        done = true;
      }
      // Modal de detalhes quando nao foi pleno sucesso
      if (!done && hasErrors(result)) showDetailsModal(result, n);
      // [chaves inexistentes] Mesmo com ok=true, se houver chaves
      // inexistentes ou falhas, abre modal -- esse era exatamente o
      // caso que o usuario nao tinha como ver.
      else if (done && hasErrors(result)) showDetailsModal(result, n);
      if (typeof window.coplanLoadObras === 'function') {
        window.coplanLoadObras();
      }
    });
    api.atualizar_obras_valores_async(cods).then(function (r) {
      if (r && r.ok && r.started) return; // polling assume o controle
      // Falha ao iniciar: fecha modal e mostra erro
      if (window.coplanProgress && window.coplanProgress.close) {
        window.coplanProgress.close();
      }
      toast('Falha ao iniciar: ' + ((r && r.error) || '?'), 'error');
    }).catch(function (e) {
      if (window.coplanProgress && window.coplanProgress.close) {
        window.coplanProgress.close();
      }
      toast('Erro: ' + (e && e.message || e), 'error');
    });
  };
})();

// ============================================================
// Bloco 5 - Global error handlers (Auditoria #45)
// window.onerror + unhandledrejection capturam erros JS que de outra
// forma so apareciam no DevTools. Mostra toast generico + log com
// console.warn para debug.
// ============================================================
(function () {
  if (window.__coplanErrorHandlers) return;
  window.__coplanErrorHandlers = true;

  function showErr(msg, source) {
    if (window.coplanToast) {
      try {
        window.coplanToast(
          'Erro inesperado: ' + (msg || '(sem mensagem)'),
          'error'
        );
      } catch (_e) { /* nao recursar se toast falhar */ }
    }
    console.warn('[coplan] ' + source + ':', msg);
  }

  window.addEventListener('error', function (ev) {
    // Filtra ResizeObserver loop (ruido benigno comum em chrome)
    var msg = (ev && ev.message) || '';
    if (typeof msg === 'string'
        && msg.indexOf('ResizeObserver loop') === 0) return;
    showErr(msg || (ev && ev.error && ev.error.message) || 'erro JS',
            'window.onerror');
  });

  window.addEventListener('unhandledrejection', function (ev) {
    var reason = (ev && ev.reason) || {};
    var msg = (typeof reason === 'string')
      ? reason
      : (reason && (reason.message || reason.toString())) || 'promise rejeitada';
    showErr(msg, 'unhandledrejection');
  });
})();

// ============================================================
// Bloco 4 - Tecnico dirty automatico (Auditoria #41/#42)
// Hook no coplan:state event: chama tecnico_check_dirty para
// detectar mudanca nos paths (db/apoio/ganhos). Quando token mudar,
// backend marca obras como tecnico_dirty='SIM' automaticamente.
// Pill #pill-tecnico no header reflete contagem de obras dirty.
// ============================================================
(function () {
  if (window.__coplanTecnicoIIFE) return;
  window.__coplanTecnicoIIFE = true;

  function api() { return window.pywebview && window.pywebview.api; }
  function toast(msg, lvl) {
    if (window.coplanToast) window.coplanToast(msg, lvl || 'info');
    else console.log('[' + (lvl || 'info') + ']', msg);
  }

  function updateTecnicoPill(count) {
    var pill = document.getElementById('pill-tecnico');
    var name = document.getElementById('pill-tecnico-name');
    if (!pill) return;
    var n = Number(count) || 0;
    pill.classList.remove('ok', 'warn', 'err');
    if (n > 0) {
      pill.classList.add('warn');
      pill.title = 'Arquivos tecnicos (TXT) - '
                 + n + ' obra(s) com snapshot desatualizado';
      if (name) name.textContent = n + ' desatualizada(s)';
    } else {
      pill.classList.add('ok');
      pill.title = 'Arquivos tecnicos (TXT) - tudo sincronizado';
      if (name) name.textContent = 'sincronizado';
    }
  }

  var checkInFlight = false;
  function check(reason) {
    if (checkInFlight) return Promise.resolve();
    var a = api();
    if (!(a && a.tecnico_check_dirty)) return Promise.resolve();
    checkInFlight = true;
    return a.tecnico_check_dirty().then(function (r) {
      checkInFlight = false;
      if (!r || !r.ok) {
        if (r && r.error) {
          console.warn('[coplan] tecnico_check_dirty:', r.error);
        }
        return;
      }
      updateTecnicoPill(r.count);
      if (r.dirty_applied) {
        // Token mudou e obras viraram dirty - avisa o user.
        toast(
          'Fontes tecnicas mudaram - ' + (r.count || 0)
          + ' obra(s) marcadas como desatualizadas.'
          + ' Use "Atualizar snapshot tec." nas obras revisadas.',
          'warn'
        );
      }
    }).catch(function (e) {
      checkInFlight = false;
      console.warn('[coplan] tecnico_check_dirty falhou:', e);
    });
  }

  // Boot: checa logo apos pywebviewready.
  if (typeof window.coplanReady === 'function') {
    window.coplanReady(function () { check('boot'); });
  }

  // Reage a mudancas de fonte (db conectado, apoio carregado, ganhos
  // pasta selecionada, etc). coplan:state e' disparado em varios pontos
  // do main_web.py (banco_mixin, apoio_mixin, ganhos_card bind, etc).
  // Debounce 250ms p/ evitar burst quando varias fontes carregam juntas.
  var debounceTimer = null;
  document.addEventListener('coplan:state', function () {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      debounceTimer = null;
      check('coplan:state');
    }, 250);
  });

  // Apos save de obra (que zera o dirty da obra individual), recount.
  document.addEventListener('coplan:obras-changed', function () {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      debounceTimer = null;
      check('coplan:obras-changed');
    }, 250);
  });

  // Apos atualizar snapshot tecnico de obras selecionadas (limpa dirty
  // pra elas), recount.
  document.addEventListener('coplan:tecnico-snapshot-updated', function () {
    check('coplan:tecnico-snapshot-updated');
  });

  // Expose para debug/integracoes manuais.
  window.coplanTecnicoCheck = check;
  window.coplanTecnicoUpdatePill = updateTecnicoPill;
})();

// ============================================================
// Bloco 2 - Templates de Descricao (Auditoria #11/#12/#13)
// Substitui o placeholder coplan-ph-templates por UI funcional.
// ============================================================
(function () {
  if (window.__coplanTemplatesIIFE) return;
  window.__coplanTemplatesIIFE = true;

  function api() { return window.pywebview && window.pywebview.api; }
  function $(id) { return document.getElementById(id); }
  function toast(msg, lvl) {
    if (window.coplanToast) window.coplanToast(msg, lvl || 'info');
    else console.log('[' + (lvl || 'info') + ']', msg);
  }
  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
      return ({'<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;'})[c];
    });
  }

  var T = {
    state: {pi: '', bootstrapped: false},

    loadFields: function () {
      var box = $('tpl-fields');
      if (!box) return Promise.resolve();
      var a = api();
      if (!(a && a.get_template_field_candidates)) {
        box.innerHTML = '<div style="padding:12px;color:var(--text-soft);">API indisponivel.</div>';
        return Promise.resolve();
      }
      return a.get_template_field_candidates().then(function (r) {
        var items = (r && r.items) || [];
        if (!items.length) {
          box.innerHTML = '<div style="padding:12px;color:var(--text-soft);">'
                        + 'Nenhum campo (banco nao conectado?).</div>';
          return;
        }
        box.innerHTML = items.map(function (c) {
          var safe = escapeHtml(c);
          return '<div class="tpl-field" data-field="' + safe + '"'
              + ' style="padding:5px 10px;cursor:pointer;border-bottom:1px solid var(--border);"'
              + ' title="Clique para inserir {' + safe + '}">' + safe + '</div>';
        }).join('');
      }).catch(function (err) {
        box.innerHTML = '<div style="padding:12px;color:var(--text-soft);">'
                      + 'Falha ao carregar campos.</div>';
        toast('Falha ao carregar campos: '
              + (err && err.message || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Carregar campos de template', 'get_template_field_candidates',
            { error: String(err && err.message || err || '?') });
        }
      });
    },

    loadPiList: function () {
      var sel = $('tpl-sel-pi');
      if (!sel) return Promise.resolve();
      var a = api();
      if (!a) return Promise.resolve();
      var calls = [
        a.list_pi_base_custom ? a.list_pi_base_custom() : Promise.resolve({all: []}),
        a.get_pi_base_map ? a.get_pi_base_map() : Promise.resolve({items: {}}),
        a.get_templates ? a.get_templates() : Promise.resolve({items: {}})
      ];
      return Promise.all(calls).then(function (rs) {
        var bases = (rs[0] && rs[0].all) || [];
        var mapKeys = Object.keys((rs[1] && rs[1].items) || {});
        var tplKeys = Object.keys((rs[2] && rs[2].items) || {});
        var seen = {};
        var out = [];
        function add(name) {
          var s = String(name || '').trim();
          if (!s) return;
          var u = s.toUpperCase();
          if (seen[u]) return;
          seen[u] = 1;
          out.push(s);
        }
        bases.forEach(add);
        mapKeys.forEach(add);
        tplKeys.forEach(add);
        out.sort();
        var prev = sel.value;
        sel.innerHTML = out.map(function (k) {
          var safe = escapeHtml(k);
          return '<option value="' + safe + '">' + safe + '</option>';
        }).join('');
        if (prev && out.indexOf(prev) >= 0) sel.value = prev;
        else if (out.length) sel.value = out[0];
        T.state.pi = sel.value || '';
      }).catch(function (err) {
        toast('Falha ao carregar lista de PIs: '
              + (err && err.message || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Carregar lista de PIs (templates)', 'get_templates',
            { error: String(err && err.message || err || '?') });
        }
      });
    },

    loadTemplate: function (pi) {
      var ta = $('tpl-textarea');
      var pv = $('tpl-preview');
      if (!ta) return Promise.resolve();
      var p = String(pi || '').trim().toUpperCase();
      T.state.pi = p;
      if (pv) pv.value = '';
      var a = api();
      if (!(a && a.get_descricao_template) || !p) {
        ta.value = '';
        return Promise.resolve();
      }
      return a.get_descricao_template(p).then(function (r) {
        ta.value = (r && r.template) || '';
      }).catch(function (err) {
        ta.value = '';
        toast('Falha ao carregar template: '
              + (err && err.message || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Carregar template ' + p, 'get_descricao_template',
            { error: String(err && err.message || err || '?') });
        }
      });
    },

    insertField: function (name) {
      var ta = $('tpl-textarea');
      if (!ta || !name) return;
      var ph = '{' + name + '}';
      var s = ta.selectionStart || 0;
      var e = ta.selectionEnd || 0;
      ta.value = ta.value.substring(0, s) + ph + ta.value.substring(e);
      var newPos = s + ph.length;
      ta.selectionStart = ta.selectionEnd = newPos;
      ta.focus();
    },

    saveTemplate: function () {
      var ta = $('tpl-textarea');
      var sel = $('tpl-sel-pi');
      if (!ta || !sel) return;
      var pi = (sel.value || '').trim().toUpperCase();
      if (!pi) { toast('Selecione um PI Base.', 'warn'); return; }
      var a = api();
      if (!(a && a.save_templates && a.get_templates)) return;
      a.get_templates().then(function (r) {
        var items = (r && r.items) || {};
        items[pi] = ta.value;
        return a.save_templates(items);
      }).then(function (rr) {
        if (rr && rr.ok) toast('Template salvo para ' + pi + '.', 'success');
        else toast('Erro ao salvar: ' + ((rr && rr.error) || ''), 'error');
      }).catch(function (err) {
        toast('Falha ao salvar template: '
              + (err && err.message || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Salvar Template ' + pi, 'save_templates',
            { error: String(err && err.message || err || '?') });
        }
      });
    },

    restoreTemplate: function () {
      var sel = $('tpl-sel-pi');
      if (!sel) return;
      var pi = (sel.value || '').trim().toUpperCase();
      if (!pi) return;
      if (!window.confirm('Restaurar o template padrao de ' + pi + '?'
                        + ' O template personalizado sera removido.')) return;
      var a = api();
      if (!(a && a.delete_pi_template)) return;
      a.delete_pi_template(pi).then(function (r) {
        if (r && r.ok) {
          toast('Template de ' + pi + ' restaurado ao padrao.', 'info');
          T.loadTemplate(pi);
        } else {
          toast('Erro: ' + ((r && r.error) || ''), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao restaurar template: '
              + (err && err.message || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Restaurar Template ' + pi, 'delete_pi_template',
            { error: String(err && err.message || err || '?') });
        }
      });
    },

    restoreAll: function () {
      if (!window.confirm('Remover TODOS os templates personalizados?'
                        + ' Esta acao nao pode ser desfeita.')) return;
      if (!window.confirm('Tem certeza? Todos os PIs voltarao ao template padrao.')) return;
      var a = api();
      if (!(a && a.restore_all_templates)) return;
      a.restore_all_templates().then(function (r) {
        if (r && r.ok) {
          toast('Removidos ' + (r.removed || 0) + ' templates personalizados.', 'info');
          var sel = $('tpl-sel-pi');
          if (sel && sel.value) T.loadTemplate(sel.value);
        } else {
          toast('Erro: ' + ((r && r.error) || ''), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao restaurar todos os templates: '
              + (err && err.message || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Restaurar todos os templates', 'restore_all_templates',
            { error: String(err && err.message || err || '?') });
        }
      });
    },

    preview: function () {
      var ta = $('tpl-textarea');
      var sel = $('tpl-sel-pi');
      var pv = $('tpl-preview');
      if (!ta || !sel || !pv) return;
      var pi = (sel.value || '').trim().toUpperCase();
      if (!pi) return;
      var a = api();
      if (!(a && a.template_preview_render)) {
        pv.value = 'API template_preview_render indisponivel.';
        return;
      }
      pv.value = '(renderizando...)';
      a.template_preview_render(pi, ta.value || '').then(function (r) {
        if (r && r.ok) {
          var hint = r.obra_count
            ? ' [usando obra ' + (r.obra_cod || '?') + ']'
            : ' [sem obra real - placeholders vazios]';
          pv.value = (r.rendered || '(template vazio)') + '\n\n' + hint;
        } else {
          pv.value = 'Erro: ' + ((r && r.error) || '');
        }
      }).catch(function (err) {
        var msg = String(err && err.message || err || '?');
        pv.value = 'Falha ao renderizar preview: ' + msg;
        toast('Falha ao renderizar preview: ' + msg, 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Preview Template ' + pi, 'template_preview_render',
            { error: msg });
        }
      });
    }
  };

  function bind() {
    var card = $('tpl-card');
    if (!card || card.__coplanBound) return;
    card.__coplanBound = true;

    var sel = $('tpl-sel-pi');
    if (sel) {
      sel.addEventListener('change', function () {
        T.loadTemplate(sel.value);
      });
    }
    var btn;
    btn = $('tpl-btn-save');         if (btn) btn.addEventListener('click', T.saveTemplate.bind(T));
    btn = $('tpl-btn-restore-pi');   if (btn) btn.addEventListener('click', T.restoreTemplate.bind(T));
    btn = $('tpl-btn-restore-all');  if (btn) btn.addEventListener('click', T.restoreAll.bind(T));
    btn = $('tpl-btn-preview');      if (btn) btn.addEventListener('click', T.preview.bind(T));
    btn = $('tpl-btn-add-pi');
    if (btn) {
      btn.addEventListener('click', function () {
        var modalBtn = $('btn-modal-pi');
        if (modalBtn) modalBtn.click();
      });
    }

    // Delegacao de click na lista de campos -> insere {name}
    var fields = $('tpl-fields');
    if (fields && !fields.__coplanBound) {
      fields.__coplanBound = true;
      fields.addEventListener('click', function (ev) {
        var el = ev.target;
        while (el && el !== fields) {
          if (el.dataset && el.dataset.field) {
            T.insertField(el.dataset.field);
            return;
          }
          el = el.parentElement;
        }
      });
    }

    // Recarrega combo PI ao fechar o modal de PI_BASE (M080).
    var piClose = $('pi-btn-close');
    if (piClose && !piClose.__coplanTplReload) {
      piClose.__coplanTplReload = true;
      piClose.addEventListener('click', function () {
        setTimeout(function () { T.loadPiList(); }, 200);
      });
    }
  }

  function bootstrap() {
    bind();
    if (T.state.bootstrapped) return;
    T.state.bootstrapped = true;
    Promise.all([T.loadFields(), T.loadPiList()]).then(function () {
      var sel = $('tpl-sel-pi');
      if (sel && sel.value) T.loadTemplate(sel.value);
      if (window.lucide && window.lucide.createIcons) {
        try { window.lucide.createIcons(); } catch (_e) {}
      }
    });
  }

  // Bootstrap quando a sub-aba Templates de descricao ficar ativa.
  document.addEventListener('coplan:config-subview', function (ev) {
    var view = (ev.detail && ev.detail.view) || '';
    if (view === 'templates') bootstrap();
  });
  // Tambem atende quando aba Config eh ativada e a sub-aba ja esta em templates.
  document.addEventListener('coplan:tab', function (ev) {
    var name = (ev.detail && ev.detail.name) || '';
    if (name !== 'config') return;
    setTimeout(function () {
      var card = $('tpl-card');
      if (card && card.style.display !== 'none') bootstrap();
    }, 50);
  });

  window.coplanTemplates = T;
})();
</script>
