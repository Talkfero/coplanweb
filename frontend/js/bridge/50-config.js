<script>
(function () {
  // ---- Section 6 / Passo 7.1 (Config / Empresa) ----
  // Carrega valores reais nos 4 campos do card "Empresa", debounce
  // de save por blur/Enter. Tambem injeta um pequeno "Procurar..."
  // ao lado dos paths (DB e Apoio) que dispara file dialog.
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findEmpresaCard() {
    var scope = document.getElementById('tab-config');
    if (!scope) return null;
    var titles = scope.querySelectorAll('.card .card-title');
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf('empresa') === 0) {
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
        return fs[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }

  function applyEmpresa(state) {
    var card = findEmpresaCard();
    if (!card || !state || !state.ok) return;
    var s = fieldByLabel(card, 'sigla');
    if (s) s.value = state.sigla || '';
    var rz = fieldByLabel(card, 'razao social');
    if (rz) rz.value = state.razao_social || '';
    var db = fieldByLabel(card, 'caminho do banco');
    if (db) db.value = state.caminho_db || '';
    document.dispatchEvent(new CustomEvent('coplan:config:empresa',
      { detail: state }));
  }
  window.coplanLoadConfigEmpresa = function () {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_config_empresa)) return Promise.resolve();
    return api.get_config_empresa().then(function (s) {
      window.__coplanConfigEmpresa = s;
      applyEmpresa(s);
    }).catch(function (err) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao carregar Empresa: '
          + ((err && err.message) || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Carregar Empresa', 'get_config_empresa',
          { error: String((err && err.message) || err || '?') });
      }
    });
  };

  function gather(card) {
    return {
      sigla:         (fieldByLabel(card, 'sigla') || {}).value || '',
      razao_social:  (fieldByLabel(card, 'razao social') || {}).value || '',
      caminho_db:    (fieldByLabel(card, 'caminho do banco') || {}).value || '',
    };
  }
  function saveEmpresa() {
    var card = findEmpresaCard();
    if (!card) return;
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.save_config_empresa)) return;
    var payload = gather(card);
    api.save_config_empresa(payload).then(function (r) {
      if (r && r.ok) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Empresa salva ('
            + (r.saved || []).length + ' campos)', 'info');
        }
        // Atualiza header pills/status (caminhos podem ter mudado).
        if (api.get_app_state) {
          api.get_app_state().then(function (st) {
            window.__coplanState = st;
            document.dispatchEvent(new CustomEvent('coplan:state',
              { detail: st }));
          }).catch(function () {});
        }
      } else if (r && r.error) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Erro: ' + r.error, 'error');
        }
      }
    }).catch(function (err) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao salvar Empresa: '
          + ((err && err.message) || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Salvar Empresa', 'save_config_empresa',
          { error: String((err && err.message) || err || '?') });
      }
    });
  }
  window.coplanSaveConfigEmpresa = saveEmpresa;

  function injectBrowseButton(card, labelPrefix, apiMethod) {
    var node = fieldByLabel(card, labelPrefix);
    if (!node) return;
    var field = node.closest('.field');
    if (!field || field.dataset.browseInjected) return;
    field.dataset.browseInjected = '1';
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;gap:6px;align-items:stretch;';
    node.parentNode.insertBefore(wrap, node);
    wrap.appendChild(node);
    var btn = document.createElement('button');
    btn.className = 'btn';
    btn.type = 'button';
    btn.style.cssText = 'flex:0 0 auto;';
    btn.innerHTML = '<i data-lucide="folder-search"></i> Procurar';
    wrap.appendChild(btn);
    btn.addEventListener('click', function () {
      var api = window.pywebview && window.pywebview.api;
      if (!(api && api[apiMethod])) return;
      api[apiMethod]().then(function (r) {
        if (r && r.ok && r.path) {
          node.value = r.path;
          saveEmpresa();
          // Se a resposta veio do pick_and_load_apoio (tem o campo
          // 'alimentadores'), avisa quem depende do apoio: metadata
          // do Cadastro, list_alimentadores, etc.
          if (r.alimentadores !== undefined) {
            document.dispatchEvent(new CustomEvent('coplan:apoio:loaded',
              { detail: r }));
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Apoio carregado: '
                + (r.alimentadores || []).length + ' alimentadores, '
                + (r.projetos_investimento || []).length + ' PIs', 'info');
            }
          }
        } else if (r && r.error && r.error !== 'cancelado'
                   && typeof window.coplanToast === 'function') {
          window.coplanToast('Erro: ' + r.error, 'error');
        }
      }).catch(function (err) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(
            'Falha ao abrir seletor: '
            + ((err && err.message) || err || '?'),
            'error');
        }
        if (window.coplanReportError) {
          window.coplanReportError(
            'Procurar (' + labelPrefix + ')', apiMethod,
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    if (window.lucide) lucide.createIcons();
  }

  function bindEmpresa() {
    var card = findEmpresaCard();
    if (!card) return false;
    injectBrowseButton(card, 'caminho do banco', 'pick_db_file');
    // Apoio (planilha) nao tem mais campo aqui: use o botao
    // "Atualizar apoio" injetado no proprio card pela IIFE
    // coplanApoioReloadIIFE, que importa o xlsx para tabelas
    // apoio_* dentro do banco e mostra o status de importacao.
    // Save por blur/Enter nos 3 campos restantes.
    ['sigla', 'razao social', 'caminho do banco'].forEach(function (lab) {
      var n = fieldByLabel(card, lab);
      if (!n) return;
      n.addEventListener('blur', saveEmpresa);
      n.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          n.blur();
        }
      });
    });
    return true;
  }

  function maybeLoad() {
    var t = document.getElementById('tab-config');
    if (t && t.classList.contains('active')) {
      window.coplanLoadConfigEmpresa();
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'config') {
      window.coplanLoadConfigEmpresa();
    }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      bindEmpresa();
      maybeLoad();
    });
  } else {
    if (!bindEmpresa()) setTimeout(bindEmpresa, 50);
    maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Painel Admin/Manutencao na aba Config ----
  // Injeta um novo card "Manutencao / Admin" depois do card Empresa
  // expondo as APIs db_*, cod_pep_preencher_pendentes, apoio_clear que
  // antes so existiam no backend.
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
  function ensureAdminCard() {
    var scope = document.getElementById('tab-config');
    if (!scope) return null;
    var existing = document.getElementById('coplan-admin-card');
    if (existing) return existing;
    var card = document.createElement('div');
    card.id = 'coplan-admin-card';
    card.className = 'card';
    card.style.marginTop = '12px';
    card.innerHTML =
      '<div class="card-header">'
    +   '<div class="card-title">'
    +     '<i data-lucide="wrench"></i>'
    +     ' Manutencao / Admin'
    +   '</div>'
    + '</div>'
    + '<div class="card-body" style="display:flex;flex-direction:column;gap:14px;">'

    + '<div>'
    +   '<div style="font-weight:600;margin-bottom:6px;">'
    +     '<i data-lucide="hard-drive"></i> Backup do banco</div>'
    +   '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
    +     '<button id="coplan-btn-db-backup" class="btn">'
    +       '<i data-lucide="save"></i> Backup agora</button>'
    +     '<button id="coplan-btn-db-weekly" class="btn">'
    +       '<i data-lucide="calendar"></i> Backup semanal</button>'
    +   '</div>'
    + '</div>'

    + '<div>'
    +   '<div style="font-weight:600;margin-bottom:6px;">'
    +     '<i data-lucide="database"></i> Dados</div>'
    +   '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
    +     '<button id="coplan-btn-db-norm-decimal" class="btn">'
    +       '<i data-lucide="hash"></i> Normalizar decimais (.->,)</button>'
    +     '<button id="coplan-btn-db-last-mod" class="btn">'
    +       '<i data-lucide="clock"></i> Ultima modificacao</button>'
    +   '</div>'
    + '</div>'

    + '<div>'
    +   '<div style="font-weight:600;margin-bottom:6px;">'
    +     '<i data-lucide="git-merge"></i> Snapshot tecnico</div>'
    +   '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">'
    +     '<button id="coplan-btn-tecnico-count" class="btn">'
    +       '<i data-lucide="list-checks"></i> Contar pendentes</button>'
    +     '<button id="coplan-btn-tecnico-mark-all" class="btn">'
    +       '<i data-lucide="alert-triangle"></i> Marcar TODAS dirty</button>'
    +     '<span id="coplan-admin-tecnico-count" '
    +           'style="color:var(--text-soft);font-size:12px;margin-left:auto;">'
    +     '</span>'
    +   '</div>'
    + '</div>'

    + '<div>'
    +   '<div style="font-weight:600;margin-bottom:6px;">'
    +     '<i data-lucide="hash"></i> COD_PEP</div>'
    +   '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
    +     '<button id="coplan-btn-cod-pep-pendentes" class="btn">'
    +       '<i data-lucide="play-circle"></i> Preencher pendentes</button>'
    +     '<button id="coplan-btn-cod-pep-zerar" class="btn danger">'
    +       '<i data-lucide="trash-2"></i> Zerar base</button>'
    +   '</div>'
    + '</div>'

    + '<div>'
    +   '<div style="font-weight:600;margin-bottom:6px;">'
    +     '<i data-lucide="folder-open"></i> Apoio (xlsx)</div>'
    +   '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
    +     '<button id="coplan-btn-apoio-clear" class="btn">'
    +       '<i data-lucide="trash"></i> Limpar cache em memoria</button>'
    +   '</div>'
    + '</div>'

    + '</div>';
    scope.appendChild(card);
    if (window.lucide) lucide.createIcons();
    return card;
  }
  function bindAdminButtons() {
    var card = ensureAdminCard();
    if (!card) return false;
    var api = window.pywebview && window.pywebview.api;

    function bind(id, fn) {
      var btn = card.querySelector('#' + id);
      if (btn && !btn.__bound) {
        btn.__bound = true;
        btn.addEventListener('click', fn);
      }
    }

    bind('coplan-btn-db-backup', function () {
      if (!(api && api.db_backup)) return toast('API indisponivel', 'error');
      toast('Criando backup...', 'info');
      api.db_backup('manual').then(function (r) {
        if (r && r.ok) {
          toast('Backup salvo: ' + r.path, 'info');
          if (api.open_path_in_os) api.open_path_in_os(r.path);
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao criar backup: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Backup do banco', 'db_backup',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-db-weekly', function () {
      if (!(api && api.db_weekly_backup)) return toast('API indisponivel', 'error');
      toast('Backup semanal...', 'info');
      api.db_weekly_backup().then(function (r) {
        if (r && r.ok) {
          toast('Backup semanal salvo: ' + r.path, 'info');
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao criar backup semanal: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Backup semanal do banco', 'db_weekly_backup',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-db-norm-decimal', function () {
      if (!(api && api.db_normalize_decimal)) return toast('API indisponivel', 'error');
      if (!window.confirm('Normalizar TODOS os decimais (. -> ,) no banco?\n'
        + 'Operacao demorada e nao reversivel.')) return;
      toast('Normalizando decimais...', 'info');
      api.db_normalize_decimal().then(function (r) {
        if (r && r.ok) {
          toast('Decimais normalizados', 'info');
          if (window.coplanLoadObras) window.coplanLoadObras();
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao normalizar decimais: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Normalizar decimais', 'db_normalize_decimal',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-db-last-mod', function () {
      if (!(api && api.db_last_modification_info)) return toast('API indisponivel', 'error');
      api.db_last_modification_info().then(function (r) {
        if (r && r.ok) {
          var msg = (r.data || '?') + ' por ' + (r.usuario || '?');
          window.alert('Ultima modificacao no banco:\n\n' + msg);
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao consultar ultima modificacao: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Ultima modificacao do banco', 'db_last_modification_info',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-tecnico-count', function () {
      if (!(api && api.db_count_tecnico_dirty)) return toast('API indisponivel', 'error');
      api.db_count_tecnico_dirty().then(function (r) {
        var lbl = card.querySelector('#coplan-admin-tecnico-count');
        if (r && r.ok) {
          if (lbl) lbl.textContent = r.count + ' obra(s) com snapshot pendente';
          toast(r.count + ' obra(s) tecnico_dirty', 'info');
        } else {
          if (lbl) lbl.textContent = '';
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        var lbl = card.querySelector('#coplan-admin-tecnico-count');
        if (lbl) lbl.textContent = '';
        toast('Falha ao contar tecnico_dirty: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Contar tecnico_dirty', 'db_count_tecnico_dirty',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-tecnico-mark-all', function () {
      if (!(api && api.db_mark_tecnico_dirty_all)) return toast('API indisponivel', 'error');
      if (!window.confirm('Marcar TODAS as obras como tecnico_dirty=SIM?\n'
        + 'Acao manutencao -- forca refresh do snapshot tecnico em todas.')) return;
      toast('Marcando todas...', 'info');
      api.db_mark_tecnico_dirty_all().then(function (r) {
        if (r && r.ok) {
          toast('Todas marcadas como dirty', 'info');
          if (window.coplanLoadObras) window.coplanLoadObras();
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao marcar tecnico_dirty em todas: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Marcar todas tecnico_dirty', 'db_mark_tecnico_dirty_all',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-cod-pep-pendentes', function () {
      if (!(api && api.cod_pep_preencher_pendentes)) return toast('API indisponivel', 'error');
      if (!window.confirm('Preencher COD_PEP de todas as obras pendentes\n'
        + '(usa empresa_sigla do config + numeracao global)?')) return;
      toast('Preenchendo COD_PEP pendentes...', 'info');
      api.cod_pep_preencher_pendentes().then(function (r) {
        if (r && r.ok) {
          toast(r.preenchidos + ' COD_PEP preenchido(s)', 'info');
          if (window.coplanLoadObras) window.coplanLoadObras();
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao preencher COD_PEP pendentes: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Preencher COD_PEP pendentes', 'cod_pep_preencher_pendentes',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-cod-pep-zerar', function () {
      if (!(api && api.cod_pep_zerar)) return toast('API indisponivel', 'error');
      var typed = window.prompt(
        'ZERAR COD_PEP DE TODA A BASE.\n'
        + 'Esta acao apaga o COD_PEP de TODAS as obras (inclusive '
        + 'despachadas) e nao pode ser desfeita.\n\n'
        + 'Digite ZERAR para confirmar:', '');
      if (!typed || typed.trim().toUpperCase() !== 'ZERAR') {
        return toast('Cancelado (confirmacao invalida)', 'warn');
      }
      toast('Zerando COD_PEP da base...', 'info');
      api.cod_pep_zerar('ZERAR').then(function (r) {
        if (r && r.ok) {
          toast(r.zerados + ' COD_PEP zerado(s)', 'info');
          if (window.coplanLoadObras) window.coplanLoadObras();
        } else {
          toast('Falha: ' + (r && r.error || '?'), 'error');
        }
      }).catch(function (err) {
        toast('Falha ao zerar COD_PEP: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Zerar COD_PEP', 'cod_pep_zerar',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    bind('coplan-btn-apoio-clear', function () {
      if (!(api && api.apoio_clear)) return toast('API indisponivel', 'error');
      if (!window.confirm('Limpar cache do apoio em memoria?\n'
        + '(Os caminhos do config sao preservados; precisa recarregar o apoio depois.)')) return;
      api.apoio_clear().then(function (r) {
        if (r && r.ok) toast('Cache do apoio limpo', 'info');
        else toast('Falha: ' + (r && r.error || '?'), 'error');
      }).catch(function (err) {
        toast('Falha ao limpar cache do apoio: '
              + ((err && err.message) || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Limpar cache do apoio', 'apoio_clear',
            { error: String((err && err.message) || err || '?') });
        }
      });
    });
    return true;
  }
  function maybeBind() {
    var t = document.getElementById('tab-config');
    if (t && t.classList.contains('active')) bindAdminButtons();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'config') bindAdminButtons();
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', maybeBind);
  } else {
    maybeBind() || setTimeout(bindAdminButtons, 200);
  }
})();
</script>
<script>
(function () {
  // ---- Fase J: Card "Diagnostico (devtools)" na aba Config ----
  // Expoe os helpers utility (parse_cod_pep, resolve_pi_base, get_dup_key,
  // get_scope_key, is_obra_aprovada) para inspecao/teste pelo usuario.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function ensureDevCard() {
    var scope = document.getElementById('tab-config');
    if (!scope) return null;
    var existing = document.getElementById('coplan-devtools-card');
    if (existing) return existing;
    var card = document.createElement('div');
    card.id = 'coplan-devtools-card';
    card.className = 'card';
    card.style.marginTop = '12px';
    card.innerHTML =
      '<div class="card-header">'
    +   '<div class="card-title">'
    +     '<i data-lucide="terminal"></i>'
    +     ' Diagnostico (devtools)</div>'
    +   '<span class="card-sub" style="margin-left:auto;color:var(--text-soft);'
    +         'font-size:11px;">Helpers de inspecao para debug</span>'
    + '</div>'
    + '<div class="card-body" style="display:flex;flex-direction:column;gap:14px;">'

    // Parse COD_PEP
    + '<div>'
    +   '<div style="font-weight:600;font-size:12px;margin-bottom:4px;">'
    +     'Parse COD_PEP <span style="color:var(--text-soft);font-weight:400;">'
    +     '(formato MA-26-CEN-001-0001-A)</span></div>'
    +   '<div style="display:flex;gap:8px;">'
    +     '<input id="coplan-dev-cod-input" class="input mono" '
    +            'style="flex:1;" placeholder="MA-26-CEN-001-0001-A"/>'
    +     '<button id="coplan-dev-cod-btn" class="btn">'
    +       '<i data-lucide="search"></i> Parse</button>'
    +   '</div>'
    +   '<pre id="coplan-dev-cod-out" style="margin-top:6px;font-size:11px;'
    +        'background:var(--surface-2);padding:8px;border-radius:6px;'
    +        'max-height:120px;overflow:auto;color:var(--text-soft);">'
    +     '(resultado aqui)</pre>'
    + '</div>'

    // Resolve PI base
    + '<div>'
    +   '<div style="font-weight:600;font-size:12px;margin-bottom:4px;">'
    +     'Resolve PI -> PI base <span style="color:var(--text-soft);'
    +     'font-weight:400;">(silencioso, sem prompt Qt)</span></div>'
    +   '<div style="display:flex;gap:8px;">'
    +     '<input id="coplan-dev-pi-input" class="input" '
    +            'style="flex:1;" placeholder="DISTRIBUICAO"/>'
    +     '<button id="coplan-dev-pi-btn" class="btn">'
    +       '<i data-lucide="git-merge"></i> Resolve</button>'
    +   '</div>'
    +   '<div id="coplan-dev-pi-out" style="margin-top:6px;font-size:12px;'
    +        'color:var(--text-soft);">(PI base aqui)</div>'
    + '</div>'

    // Inspecionar obra
    + '<div>'
    +   '<div style="font-weight:600;font-size:12px;margin-bottom:4px;">'
    +     'Inspecionar obra (cole COD)</div>'
    +   '<div style="display:flex;gap:8px;">'
    +     '<input id="coplan-dev-obra-input" class="input mono" '
    +            'style="flex:1;" placeholder="MA-26-DI-047"/>'
    +     '<button id="coplan-dev-obra-btn" class="btn">'
    +       '<i data-lucide="zoom-in"></i> Inspecionar</button>'
    +   '</div>'
    +   '<pre id="coplan-dev-obra-out" style="margin-top:6px;font-size:11px;'
    +        'background:var(--surface-2);padding:8px;border-radius:6px;'
    +        'max-height:200px;overflow:auto;color:var(--text-soft);">'
    +     '(scope_key, dup_key, aprovada -- aqui)</pre>'
    + '</div>'

    + '</div>';
    scope.appendChild(card);
    if (window.lucide) lucide.createIcons();
    return card;
  }
  function bindDevButtons() {
    var card = ensureDevCard();
    if (!card) return false;
    var api = window.pywebview && window.pywebview.api;

    // Parse COD_PEP
    var btnCod = card.querySelector('#coplan-dev-cod-btn');
    if (btnCod && !btnCod.__bound) {
      btnCod.__bound = true;
      btnCod.addEventListener('click', function () {
        var input = card.querySelector('#coplan-dev-cod-input');
        var out = card.querySelector('#coplan-dev-cod-out');
        if (!api || !api.parse_cod_pep) {
          out.textContent = 'API indisponivel'; return;
        }
        var v = (input.value || '').trim();
        if (!v) { out.textContent = '(vazio)'; return; }
        api.parse_cod_pep(v).then(function (r) {
          if (r && r.ok && r.parsed) {
            out.textContent = JSON.stringify(r.parsed, null, 2);
          } else {
            out.textContent = 'Erro: ' + (r && r.error || 'invalido');
          }
        }).catch(function (err) {
          console.warn('[coplan/devtools] parse_cod_pep:', err);
          out.textContent = 'Erro: ' + (err && err.message || err);
        });
      });
    }

    // Resolve PI
    var btnPi = card.querySelector('#coplan-dev-pi-btn');
    if (btnPi && !btnPi.__bound) {
      btnPi.__bound = true;
      btnPi.addEventListener('click', function () {
        var input = card.querySelector('#coplan-dev-pi-input');
        var out = card.querySelector('#coplan-dev-pi-out');
        if (!api || !api.resolve_pi_base) {
          out.textContent = 'API indisponivel'; return;
        }
        var v = (input.value || '').trim();
        if (!v) { out.textContent = '(vazio)'; return; }
        api.resolve_pi_base(v, false).then(function (r) {
          if (r && r.ok) {
            out.innerHTML = '<strong style="color:var(--success);">'
                          + esc(r.pi_base) + '</strong>';
          } else {
            out.textContent = 'Erro: ' + (r && r.error || '?');
          }
        }).catch(function (err) {
          console.warn('[coplan/devtools] resolve_pi_base:', err);
          out.textContent = 'Erro: ' + (err && err.message || err);
        });
      });
    }

    // Inspecionar obra (3 calls em paralelo: get_obra + dup_key + scope_key + aprovada)
    var btnObra = card.querySelector('#coplan-dev-obra-btn');
    if (btnObra && !btnObra.__bound) {
      btnObra.__bound = true;
      btnObra.addEventListener('click', function () {
        var input = card.querySelector('#coplan-dev-obra-input');
        var out = card.querySelector('#coplan-dev-obra-out');
        if (!api || !api.get_obra) {
          out.textContent = 'API indisponivel'; return;
        }
        var cod = (input.value || '').trim();
        if (!cod) { out.textContent = '(vazio)'; return; }
        out.textContent = 'Buscando ' + cod + '...';
        api.get_obra(cod).then(function (r) {
          if (!(r && r.ok && r.obra)) {
            out.textContent = 'Erro: ' + (r && r.error || 'nao encontrado');
            return;
          }
          var obra = r.obra;
          // Dispara helpers em paralelo
          Promise.all([
            (api.get_dup_key ? api.get_dup_key(obra) : Promise.resolve(null)),
            (api.get_scope_key ? api.get_scope_key(obra) : Promise.resolve(null)),
            (api.is_obra_aprovada ? api.is_obra_aprovada(obra) : Promise.resolve(null)),
          ]).then(function (R) {
            var d = R[0], s = R[1], a = R[2];
            var summary = {
              cod: obra.cod,
              ano: obra.ano_,
              projeto_investimento: obra.projeto_investimento,
              pi_base: obra.pi_base,
              nome_projeto: obra.nome_projeto,
              alimentador_principal: obra.alimentador_principal,
              tipo_pacote: obra.tipo_pacote,
              obra_aprovada: obra.obra_aprovada,
              despacho_status: obra.despacho_status,
              tecnico_dirty: obra.tecnico_dirty,
              dup_key: (d && d.ok) ? d.key : '?',
              scope_key: (s && s.ok) ? s.key : '?',
              aprovada_helper: (a && a.ok) ? a.aprovada : '?',
            };
            out.textContent = JSON.stringify(summary, null, 2);
          }).catch(function (err) {
            console.warn('[coplan/devtools] obra helpers:', err);
            out.textContent = 'Erro: ' + (err && err.message || err);
          });
        }).catch(function (err) {
          console.warn('[coplan/devtools] get_obra:', err);
          out.textContent = 'Erro: ' + (err && err.message || err);
        });
      });
    }
    return true;
  }
  function maybeBindDev() {
    var t = document.getElementById('tab-config');
    if (t && t.classList.contains('active')) bindDevButtons();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'config') bindDevButtons();
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', maybeBindDev);
  } else {
    maybeBindDev() || setTimeout(bindDevButtons, 250);
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 7.2 (Config / Criterios de Planejamento) ----
  // Popula os 8 inputs do card "Criterios de Planejamento (vigentes)"
  // a partir do get_criterios (5.3) e salva em blur/Enter via
  // save_criterios. Botao "Restaurar padroes" chama
  // restore_criterios_defaults.
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findCard() {
    var scope = document.getElementById('tab-config');
    if (!scope) return null;
    var titles = scope.querySelectorAll('.card .card-title');
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf('criterios de planejamento') === 0) {
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
        return fs[i].querySelector('input, select, textarea');
      }
    }
    return null;
  }

  // (label_prefix_no_mock, payload_key_para_save, getter(state) -> value)
  var FIELDS = [
    ['tensao min',          'tensao_min',
      function (st) { return (st.criterios || {}).tensao_min; }],
    ['tensao max',          'tensao_max',
      function (st) { return (st.criterios || {}).tensao_max; }],
    ['carregamento max',    'carregamento_max',
      function (st) { return (st.criterios || {}).carregamento_limite_sim_ou_vazio; }],
    ['chi minimo',          'chi_min',
      function (st) { return (st.criterios || {}).chi_min; }],
    ['ci minimo',           'ci_min',
      function (st) { return (st.criterios || {}).ci_min; }],
    ['piora mercado',       'piora_mercado',
      function (st) { return (st.piora_mercado || {}).carregamento_percentual; }],
    ['anos de horizonte',   'anos_horizonte',
      function (st) { return (st.piora_mercado || {}).anos_horizonte; }],
    ['postergacao max',     'postergacao_max_anos',
      function (st) { return (st.piora_mercado || {}).postergacao_max_anos; }],
  ];
  function fmtVal(v) {
    if (v == null) return '';
    var n = Number(v);
    if (isNaN(n)) return String(v);
    // Inteiros sem decimais; floats com 2-3 decimais.
    if (n === Math.round(n) && Math.abs(n) >= 1) return String(n);
    var s = n.toString();
    if (s.indexOf('.') === -1) return s;
    // Limita a 3 decimais maximo.
    return n.toFixed(Math.min(3, s.split('.')[1].length));
  }

  function applyCriterios(state) {
    var card = findCard();
    if (!card || !state || !state.ok) return;
    FIELDS.forEach(function (f) {
      var node = fieldByLabel(card, f[0]);
      if (!node) return;
      var v = f[2](state);
      node.value = fmtVal(v);
    });
  }

  function gather(card) {
    var payload = {};
    FIELDS.forEach(function (f) {
      var node = fieldByLabel(card, f[0]);
      if (!node) return;
      payload[f[1]] = String(node.value || '').trim();
    });
    return payload;
  }
  function saveCriterios() {
    var card = findCard();
    if (!card) return;
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.save_criterios)) return;
    var payload = gather(card);
    api.save_criterios(payload).then(function (r) {
      if (r && r.ok) {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Criterios salvos', 'info');
        }
        // Re-aplica nos passos consumidores: card lateral em Ganhos
        // (5.3) e badges/passou na Visualizar (5.3 + 3.5).
        if (typeof window.coplanLoadCriterios === 'function') {
          window.coplanLoadCriterios();
        }
        if (typeof window.coplanLoadObras === 'function') {
          window.coplanLoadObras();
        }
      } else if (r && r.error && typeof window.coplanToast === 'function') {
        window.coplanToast('Erro: ' + r.error, 'error');
      }
    }).catch(function (err) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao salvar Criterios: '
          + ((err && err.message) || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Salvar Criterios', 'save_criterios',
          { error: String((err && err.message) || err || '?') });
      }
    });
  }
  window.coplanSaveCriterios = saveCriterios;

  function applyAndCache(state) {
    window.__coplanCriterios = state;
    applyCriterios(state);
  }
  window.coplanLoadConfigCriterios = function () {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_criterios)) return Promise.resolve();
    return api.get_criterios().then(applyAndCache).catch(function (err) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao carregar Criterios: '
          + ((err && err.message) || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Carregar Criterios', 'get_criterios',
          { error: String((err && err.message) || err || '?') });
      }
    });
  };

  function bindRestore(card) {
    var btns = card.querySelectorAll('.card-header .btn');
    for (var i = 0; i < btns.length; i++) {
      var t = norm(btns[i].textContent);
      if (t.indexOf('restaurar padr') === 0 && !btns[i].__pivoted) {
        btns[i].__pivoted = true;
        btns[i].addEventListener('click', function () {
          if (!window.confirm('Restaurar criterios aos valores padrao?')) return;
          var api = window.pywebview && window.pywebview.api;
          if (!(api && api.restore_criterios_defaults)) return;
          api.restore_criterios_defaults().then(function (state) {
            applyAndCache(state);
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Criterios restaurados', 'info');
            }
            if (typeof window.coplanLoadObras === 'function') {
              window.coplanLoadObras();
            }
          }).catch(function (err) {
            if (typeof window.coplanToast === 'function') {
              window.coplanToast(
                'Falha ao restaurar Criterios: '
                + ((err && err.message) || err || '?'),
                'error');
            }
            if (window.coplanReportError) {
              window.coplanReportError(
                'Restaurar Criterios', 'restore_criterios_defaults',
                { error: String((err && err.message) || err || '?') });
            }
          });
        });
      }
    }
  }

  function bindCard() {
    var card = findCard();
    if (!card) return false;
    bindRestore(card);
    FIELDS.forEach(function (f) {
      var node = fieldByLabel(card, f[0]);
      if (!node) return;
      node.addEventListener('blur', saveCriterios);
      node.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); node.blur(); }
      });
    });
    return true;
  }

  function maybeLoad() {
    var t = document.getElementById('tab-config');
    if (t && t.classList.contains('active')) {
      window.coplanLoadConfigCriterios();
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'config') {
      window.coplanLoadConfigCriterios();
    }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      bindCard();
      maybeLoad();
    });
  } else {
    if (!bindCard()) setTimeout(bindCard, 50);
    maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 7.3 (Config / Templates + PI_BASE) ----
  // DESABILITADO: este renderer alvejava um seletor DOM legado
  // (box.querySelectorAll('div')[1]) que nao corresponde a estrutura
  // atual (<ul id="pi-list">), e o doAdd local concorria com o M080
  // dobrando o handler do botao Adicionar (gerava window.prompt
  // duplicado). Toda a logica de listar/adicionar/remover PI_BASE
  // ficou no bloco M080 (procure por "Modal Gerenciar PI_BASE" neste
  // arquivo). Mantenho o IIFE so para nao quebrar referencias antigas
  // a window.coplanRenderPiList/window.coplanLoadPiList -- redirecio
  // estes para o equivalente do M080 (registrado abaixo do M080).
  return;
  // eslint-disable-next-line no-unreachable
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function findPiModal() {
    return document.getElementById('modal-pi');
  }
  function findPiList(modal) {
    if (!modal) return null;
    // Container das rows (pai dos .row com PI mock).
    var body = modal.querySelector('.modal-body');
    if (!body) return null;
    var box = body.querySelector('div[style*="border:1px solid var(--border)"]');
    if (!box) return null;
    var list = box.querySelectorAll('div')[1]; // 2o div: lista
    return list || null;
  }
  function piRowHtml(name) {
    var safe = esc(name);
    return '<div class="row coplan-pi-row" style="padding:8px 12px;'
      + 'border-bottom:1px solid var(--border);" data-pi="' + safe + '">'
      +   '<span class="mono grow">' + safe + '</span>'
      +   '<button class="btn ghost sm" data-pi-remove="1" title="Remover">'
      +     '<i data-lucide="trash-2"></i></button>'
      + '</div>';
  }
  function renderPiList(state) {
    var modal = findPiModal();
    var list = findPiList(modal);
    if (!modal || !list) return;
    // Apenas substitui o conteudo da lista PRESERVANDO o header
    // "PIs configurados".
    var custom = (state && state.custom) || [];
    var defaults = ((state && state.all) || []).filter(function (a) {
      return custom.indexOf(a) === -1
          && custom.map(function (c) { return c.toUpperCase(); })
                   .indexOf(String(a).toUpperCase()) === -1;
    });
    var html = '';
    // Defaults primeiro (read-only, sem botao remover).
    defaults.forEach(function (n) {
      html += '<div class="row" style="padding:8px 12px;'
            + 'border-bottom:1px solid var(--border);opacity:0.7;">'
            +   '<span class="mono grow">' + esc(n) + '</span>'
            +   '<span style="font-size:10px;color:var(--text-soft);'
            +         'background:var(--surface-3);padding:2px 6px;'
            +         'border-radius:3px;">default</span>'
            + '</div>';
    });
    custom.forEach(function (n) { html += piRowHtml(n); });
    list.innerHTML = html;
    // Bind dos botoes remover.
    list.querySelectorAll('button[data-pi-remove]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.preventDefault();
        var row = b.closest('[data-pi]');
        if (!row) return;
        var pi = row.getAttribute('data-pi');
        if (!window.confirm('Remover PI_BASE "' + pi + '"?')) return;
        var api = window.pywebview && window.pywebview.api;
        if (!(api && api.remove_pi_base_custom)) return;
        api.remove_pi_base_custom(pi).then(function (st) {
          if (st && st.ok) {
            renderPiList(st);
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Removido: ' + pi, 'info');
            }
          } else if (st && st.error && typeof window.coplanToast === 'function') {
            window.coplanToast(st.error, 'error');
          }
        });
      });
    });
    if (window.lucide) lucide.createIcons();
  }
  window.coplanRenderPiList = renderPiList;
  window.coplanLoadPiList = function () {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.list_pi_base_custom)) return Promise.resolve();
    return api.list_pi_base_custom().then(renderPiList);
  };

  function bindAdd() {
    var modal = findPiModal();
    if (!modal) return false;
    var body = modal.querySelector('.modal-body');
    if (!body) return false;
    var input = body.querySelector('.row .input');
    var btns = body.querySelectorAll('.row .btn');
    var addBtn = null;
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].textContent.trim().toLowerCase().indexOf('adicionar') === 0) {
        addBtn = btns[i]; break;
      }
    }
    if (!input || !addBtn || addBtn.__pivoted) return false;
    addBtn.__pivoted = true;
    function doAdd() {
      var v = String(input.value || '').trim();
      if (!v) return;
      var api = window.pywebview && window.pywebview.api;
      if (!(api && api.add_pi_base_custom)) return;
      api.add_pi_base_custom(v).then(function (st) {
        if (st && st.ok) {
          renderPiList(st);
          input.value = '';
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Adicionado: ' + v, 'info');
          }
        } else if (st && st.error && typeof window.coplanToast === 'function') {
          window.coplanToast(st.error, 'error');
        }
      });
    }
    addBtn.addEventListener('click', function (e) {
      e.preventDefault();
      doAdd();
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); doAdd(); }
    });
    return true;
  }
  function bindRestore() {
    var modal = findPiModal();
    if (!modal) return;
    var btns = modal.querySelectorAll('.modal-footer .btn');
    for (var i = 0; i < btns.length; i++) {
      var t = btns[i].textContent.trim().toLowerCase();
      if (t.indexOf('restaurar') === 0 && !btns[i].__pivoted) {
        btns[i].__pivoted = true;
        btns[i].addEventListener('click', function () {
          if (!window.confirm('Limpar PI_BASE_CUSTOM e voltar aos defaults?')) return;
          var api = window.pywebview && window.pywebview.api;
          if (!(api && api.list_pi_base_custom)) return;
          // Estrategia: lista atual e remove um por um.
          api.list_pi_base_custom().then(function (st) {
            var custom = (st && st.custom) || [];
            var promises = custom.map(function (n) {
              return api.remove_pi_base_custom ? api.remove_pi_base_custom(n)
                                                : Promise.resolve();
            });
            Promise.all(promises).then(function () {
              window.coplanLoadPiList();
              if (typeof window.coplanToast === 'function') {
                window.coplanToast('PI_BASE restaurado aos defaults', 'info');
              }
            });
          });
        });
      }
    }
  }

  // Carrega lista quando o modal abrir. O mock tem
  //   document.getElementById('btn-modal-pi').addEventListener('click', () => openModal('modal-pi'));
  // Adicionamos um listener extra para popular ao mostrar.
  function bindOpen() {
    var btnSidebar = document.getElementById('btn-modal-pi');
    if (btnSidebar && !btnSidebar.__pivoted) {
      btnSidebar.__pivoted = true;
      btnSidebar.addEventListener('click', function () {
        // Carrega depois do mock abrir o modal.
        setTimeout(window.coplanLoadPiList, 0);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      bindAdd(); bindRestore(); bindOpen();
    });
  } else {
    bindAdd(); bindRestore(); bindOpen();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 7.4 (Config / Mapa Regional) ----
  // Substitui as 4 linhas hardcoded da tabela "Mapa Regional" por
  // dados de get_regional_map_full + edicao inline. Cores limitadas
  // a 5 opcoes pre-definidas (info/success/warning/danger/violet).
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function findCard() {
    var scope = document.getElementById('tab-config');
    if (!scope) return null;
    var titles = scope.querySelectorAll('.card .card-title');
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf('mapa regional') === 0) {
        return titles[i].closest('.card');
      }
    }
    return null;
  }
  function findTable(card) {
    return card ? card.querySelector('table.data') : null;
  }
  var COR_OPTS = ['info', 'success', 'warning', 'danger', 'violet'];
  function corLabel(cor) {
    var labels = {info: 'Azul', success: 'Verde', warning: 'Ambar',
                  danger: 'Vermelho', violet: 'Violeta'};
    return labels[cor] || cor;
  }

  function rowReadHtml(nome, e) {
    return '<tr data-nome="' + esc(nome) + '" data-source="'
      + esc(e.source || 'config') + '">'
      +   '<td>' + esc(nome) + '</td>'
      +   '<td>' + esc(e.superintendencia || '') + '</td>'
      +   '<td class="mono">' + esc(e.se_prefixos || '') + '</td>'
      +   '<td><span class="badge ' + esc(e.cor || 'info') + '">'
      +     '<span class="dot"></span>' + esc(corLabel(e.cor || 'info'))
      +   '</span></td>'
      +   '<td style="display:flex;gap:4px;">'
      +     '<button class="btn ghost sm" data-act="edit" title="Editar">'
      +       '<i data-lucide="pencil"></i></button>'
      + (e.source === 'default'
          ? ''
          : '<button class="btn ghost sm" data-act="delete" title="Remover">'
            + '<i data-lucide="trash-2"></i></button>')
      +   '</td>'
      + '</tr>';
  }
  function rowEditHtml(nome, e, isNew) {
    var corOpts = COR_OPTS.map(function (c) {
      var sel = (c === (e.cor || 'info')) ? ' selected' : '';
      return '<option value="' + c + '"' + sel + '>' + corLabel(c) + '</option>';
    }).join('');
    var nomeCell = isNew
      ? '<input class="input mono" data-f="nome" placeholder="NOME" '
        + 'style="padding:4px 6px;width:140px;" value="' + esc(nome || '') + '"/>'
      : '<span class="mono">' + esc(nome) + '</span>';
    return '<tr data-nome="' + esc(nome || '') + '" data-edit="1">'
      +   '<td>' + nomeCell + '</td>'
      +   '<td><input class="input" data-f="superintendencia" '
      +     'style="padding:4px 6px;width:130px;" value="'
      +     esc(e.superintendencia || '') + '"/></td>'
      +   '<td><input class="input mono" data-f="se_prefixos" '
      +     'style="padding:4px 6px;width:170px;" value="'
      +     esc(e.se_prefixos || '') + '"/></td>'
      +   '<td><select class="select" data-f="cor" '
      +     'style="padding:4px 6px;width:110px;">' + corOpts + '</select></td>'
      +   '<td style="display:flex;gap:4px;">'
      +     '<button class="btn primary sm" data-act="save" title="Salvar">'
      +       '<i data-lucide="check"></i></button>'
      +     '<button class="btn ghost sm" data-act="cancel" title="Cancelar">'
      +       '<i data-lucide="x"></i></button>'
      +   '</td>'
      + '</tr>';
  }
  function readRowEdits(tr) {
    var get = function (f) {
      var n = tr.querySelector('[data-f="' + f + '"]');
      return n ? String(n.value || '').trim() : '';
    };
    return {
      nome:             get('nome') || tr.getAttribute('data-nome'),
      superintendencia: get('superintendencia'),
      se_prefixos:      get('se_prefixos'),
      cor:              get('cor') || 'info',
    };
  }

  window.coplanRenderRegionais = function (state) {
    var card = findCard();
    var table = findTable(card);
    if (!table || !state || !state.ok) return;
    var tbody = table.querySelector('tbody');
    if (!tbody) {
      tbody = document.createElement('tbody');
      table.appendChild(tbody);
    }
    var items = state.items || {};
    var keys = Object.keys(items).sort();
    if (!keys.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="padding:14px;text-align:center;color:var(--text-soft);">'
                      + 'Nenhuma regional configurada.</td></tr>';
      return;
    }
    tbody.innerHTML = keys.map(function (k) {
      return rowReadHtml(k, items[k]);
    }).join('');
    if (window.lucide) lucide.createIcons();
  };

  function bindRowActions(tbody) {
    if (!tbody) return;
    tbody.addEventListener('click', function (ev) {
      var btn = ev.target.closest && ev.target.closest('button[data-act]');
      if (!btn) return;
      var act = btn.getAttribute('data-act');
      var tr = btn.closest('tr');
      if (!tr) return;
      var nome = tr.getAttribute('data-nome');
      var api = window.pywebview && window.pywebview.api;
      if (act === 'edit') {
        var state = window.__coplanRegionais;
        if (!state) return;
        var e = state.items[nome] || {};
        var html = rowEditHtml(nome, e, false);
        tr.outerHTML = html;
        if (window.lucide) lucide.createIcons();
      } else if (act === 'cancel') {
        if (!window.__coplanRegionais) return;
        var state2 = window.__coplanRegionais;
        var e2 = state2.items[nome] || {
          superintendencia: '', se_prefixos: '', cor: 'info', source: 'config',
        };
        if (nome) {
          tr.outerHTML = rowReadHtml(nome, e2);
        } else {
          tr.remove();
        }
        if (window.lucide) lucide.createIcons();
      } else if (act === 'save') {
        if (!(api && api.save_regional_entry)) return;
        var data = readRowEdits(tr);
        if (!data.nome) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Informe o nome da regional', 'warn');
          }
          return;
        }
        api.save_regional_entry(data.nome, {
          codigo:           '',  // codigo gerado automaticamente / preservado
          superintendencia: data.superintendencia,
          se_prefixos:      data.se_prefixos,
          cor:              data.cor,
        }).then(function (st) {
          if (st && st.ok) {
            window.__coplanRegionais = st;
            window.coplanRenderRegionais(st);
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Regional ' + data.nome + ' salva', 'info');
            }
          } else if (st && st.error && typeof window.coplanToast === 'function') {
            window.coplanToast(st.error, 'error');
          }
        });
      } else if (act === 'delete') {
        if (!(api && api.delete_regional_entry)) return;
        if (!window.confirm('Remover a regional "' + nome + '" do config?')) return;
        api.delete_regional_entry(nome).then(function (st) {
          if (st && st.ok) {
            window.__coplanRegionais = st;
            window.coplanRenderRegionais(st);
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('Regional ' + nome + ' removida', 'info');
            }
          } else if (st && st.error && typeof window.coplanToast === 'function') {
            window.coplanToast(st.error, 'error');
          }
        });
      }
    });
  }

  function bindAdd(card) {
    if (!card) return;
    var btns = card.querySelectorAll('.card-header .btn');
    for (var i = 0; i < btns.length; i++) {
      var t = norm(btns[i].textContent);
      if (t.indexOf('adicionar regional') === 0 && !btns[i].__pivoted) {
        btns[i].__pivoted = true;
        btns[i].addEventListener('click', function () {
          var table = findTable(card);
          if (!table) return;
          var tbody = table.querySelector('tbody');
          if (!tbody) return;
          // Insere uma row de edicao no topo (nova regional).
          var html = rowEditHtml('', {cor: 'info'}, true);
          tbody.insertAdjacentHTML('afterbegin', html);
          if (window.lucide) lucide.createIcons();
          var firstInput = tbody.querySelector('tr[data-edit] input[data-f="nome"]');
          if (firstInput) firstInput.focus();
        });
      }
    }
  }

  window.coplanLoadRegionais = function () {
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_regional_map_full)) return Promise.resolve();
    return api.get_regional_map_full().then(function (st) {
      window.__coplanRegionais = st;
      window.coplanRenderRegionais(st);
    });
  };

  function bindCard() {
    var card = findCard();
    if (!card) return false;
    bindAdd(card);
    var table = findTable(card);
    if (table) bindRowActions(table.querySelector('tbody') || table);
    return true;
  }

  function maybeLoad() {
    var t = document.getElementById('tab-config');
    if (t && t.classList.contains('active')) {
      window.coplanLoadRegionais();
    }
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'config') {
      window.coplanLoadRegionais();
    }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      bindCard();
      maybeLoad();
    });
  } else {
    if (!bindCard()) setTimeout(bindCard, 50);
    maybeLoad();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 7.5 (Config / subnav) ----
  // 5 abas: Geral / Criterios / Templates / PI_BASE / Regional Map.
  // O mock renderiza todos os cards juntos; aqui filtramos visibilidade
  // por aba ativa. Para Templates e PI_BASE (sem cards proprios)
  // injetamos um placeholder com link/CTA quando ativos.
  function norm(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function findCardByTitle(scope, prefix) {
    var titles = scope.querySelectorAll('.card .card-title');
    var target = norm(prefix);
    for (var i = 0; i < titles.length; i++) {
      if (norm(titles[i].textContent).indexOf(target) === 0) {
        return titles[i].closest('.card');
      }
    }
    return null;
  }
  function ensurePlaceholder(scope, id, title, body) {
    var el = document.getElementById(id);
    if (!el) {
      el = document.createElement('div');
      el.id = id;
      el.className = 'card';
      el.style.gridColumn = 'span 12';
      // Insere depois da subnav (mas dentro do .form-grid).
      var grid = scope.querySelector('.form-grid');
      if (grid) grid.appendChild(el);
      else scope.appendChild(el);
    }
    el.innerHTML = '<div class="card-header">'
      + '<div class="card-title">' + title + '</div>'
      + '</div><div class="card-body">' + body + '</div>';
    if (window.lucide) lucide.createIcons();
    return el;
  }
  function setVisible(node, visible) {
    if (!node) return;
    if (visible) { if (node.style.display === 'none') node.style.display = ''; }
    else { node.style.display = 'none'; }
  }
  // Tabs -> cards visiveis.
  var TAB_VIEWS = {
    'geral': {
      cards: ['empresa', 'preferencias de ui'],
      placeholders: [],
    },
    'criterios': {
      cards: ['criterios de planejamento'],
      placeholders: [],
    },
    'templates': {
      // Bloco 2 (Auditoria #11): card real #tpl-card substitui o placeholder.
      cards: ['templates de descricao'],
      placeholders: [],
    },
    'pi_base': {
      cards: [],
      placeholders: ['pi_base'],
    },
    'regional': {
      cards: ['mapa regional'],
      placeholders: [],
    },
  };
  function tabKeyOf(label) {
    var n = norm(label);
    if (n.indexOf('geral') === 0) return 'geral';
    if (n.indexOf('criterios') === 0 || n.indexOf('crit') === 0) return 'criterios';
    if (n.indexOf('template') === 0) return 'templates';
    if (n.indexOf('pi_base') === 0 || n.indexOf('pi base') === 0
        || n.indexOf('pi') === 0) return 'pi_base';
    if (n.indexOf('regional') === 0 || n.indexOf('mapa') === 0) return 'regional';
    return 'geral';
  }
  function applyView(label) {
    var scope = document.getElementById('tab-config');
    if (!scope) return;
    var key = tabKeyOf(label);
    var view = TAB_VIEWS[key] || TAB_VIEWS.geral;
    // Cards "reais": visivel se em view.cards, escondido caso contrario.
    var allCardKeys = ['empresa', 'preferencias de ui',
                       'criterios de planejamento', 'mapa regional',
                       'templates de descricao'];
    allCardKeys.forEach(function (k) {
      var card = findCardByTitle(scope, k);
      setVisible(card, view.cards.indexOf(k) >= 0);
    });
    // Placeholders sintetizados:
    // Bloco 2 removeu placeholder de templates (substituido por #tpl-card).
    // Esconde residual caso tenha sido criado por execucao anterior.
    var phTemplatesOld = document.getElementById('coplan-ph-templates');
    setVisible(phTemplatesOld, false);
    var phPi = document.getElementById('coplan-ph-pi');

    if (view.placeholders.indexOf('pi_base') >= 0) {
      ensurePlaceholder(scope, 'coplan-ph-pi',
        '<i data-lucide="hash"></i> PI_BASE',
        '<p style="margin:0 0 12px;color:var(--text-soft);font-size:12.5px;">'
        + 'Lista de PI_BASE customizados (DI/ME/TR/RT + adicionais). '
        + 'Use o modal "Gerenciar PI_BASE" da sidebar.</p>'
        + '<button class="btn primary" id="coplan-open-pi-modal">'
        + '<i data-lucide="settings"></i>Abrir Gerenciador</button>');
      var btn = document.getElementById('coplan-open-pi-modal');
      if (btn && !btn.__pivoted) {
        btn.__pivoted = true;
        btn.addEventListener('click', function () {
          var modalBtn = document.getElementById('btn-modal-pi');
          if (modalBtn) modalBtn.click();
        });
      }
      setVisible(document.getElementById('coplan-ph-pi'), true);
    } else {
      setVisible(phPi, false);
    }

    // Bloco 2: emite evento para coplanTemplates fazer bootstrap quando
    // sub-aba ativa for 'templates'. Outros consumers podem reagir tambem.
    try {
      document.dispatchEvent(
        new CustomEvent('coplan:config-subview', {detail: {view: key}})
      );
    } catch (_e) {}
  }

  // Render simples da lista de templates dentro do placeholder.
  window.coplanRenderTemplatesList = function () {
    var box = document.getElementById('coplan-templates-list');
    if (!box) return;
    var api = window.pywebview && window.pywebview.api;
    if (!(api && api.get_templates)) {
      box.innerHTML = '<span style="color:var(--text-soft)">API indisponivel.</span>';
      return;
    }
    api.get_templates().then(function (r) {
      var items = (r && r.items) || {};
      var keys = Object.keys(items);
      if (!keys.length) {
        box.innerHTML = '<span style="color:var(--text-soft)">'
                      + 'Nenhum template configurado.</span>';
        return;
      }
      box.innerHTML = keys.sort().map(function (k) {
        var safeK = String(k).replace(/[<>&]/g, function (c) {
          return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
        });
        var preview = String(items[k] || '').slice(0, 80).replace(/[<>&]/g, function (c) {
          return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
        });
        return '<div class="row" style="padding:8px 12px;border:1px solid var(--border);'
             + 'border-radius:6px;justify-content:space-between;">'
             +   '<span class="mono" style="font-weight:500;">' + safeK + '</span>'
             +   '<span style="color:var(--text-soft);font-size:11.5px;">' + preview
             +     (items[k].length > 80 ? '...' : '') + '</span>'
             + '</div>';
      }).join('');
    });
  };

  function bindSubnav() {
    var scope = document.getElementById('tab-config');
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
    var active = subnav.querySelector('.subnav-tab.active') || tabs[0];
    if (active) applyView(active.textContent);
    return true;
  }

  // Re-aplica ao entrar na aba Config.
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'config') {
      var scope = document.getElementById('tab-config');
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
<script>
(function () {
  // ---- Header global / botoes orfaos do mock ----
  // O Coplan UI.html tem 3 botoes icon-only no header:
  //   [plug-zap]   Conectar Banco
  //   [download]   Importar Excel
  //   [upload]     Exportar Excel
  // Mais o botao Ajuda da sidebar (#btn-help). Conectamos cada um.
  function findHeaderBtnByTitle(title) {
    var hdr = document.querySelector('.header');
    if (!hdr) return null;
    var btns = hdr.querySelectorAll('.btn');
    for (var i = 0; i < btns.length; i++) {
      var t = (btns[i].getAttribute('title') || '').toLowerCase();
      if (t.indexOf(String(title).toLowerCase()) >= 0) return btns[i];
    }
    return null;
  }
  function reloadEverything() {
    // Refresh em todos os passos que dependem de DB.
    if (typeof window.coplanLoadObras === 'function') window.coplanLoadObras();
    if (typeof window.coplanLoadStats === 'function') window.coplanLoadStats();
    var api = window.pywebview && window.pywebview.api;
    if (api && api.get_app_state) {
      api.get_app_state().then(function (st) {
        window.__coplanState = st;
        document.dispatchEvent(new CustomEvent('coplan:state',
          { detail: st }));
      });
    }
  }

  function bindHeaderButtons() {
    var api = window.pywebview && window.pywebview.api;

    // Conectar Banco
    // OK = selecionar .db existente (header_connect_db, com validacao)
    // Cancelar = criar novo banco (db_create_new, com SAVE dialog
    //            ou prompt de caminho). Ambos os caminhos terminam com
    //            o banco conectado e reloadEverything() disparado.
    var btnConn = findHeaderBtnByTitle('conectar banco');
    if (btnConn && !btnConn.__pivoted) {
      btnConn.__pivoted = true;
      btnConn.addEventListener('click', function () {
        if (!api) return;
        var msg = 'Conectar Banco:\n\n'
          + '  OK = SELECIONAR banco existente (.db)\n'
          + '  Cancelar = CRIAR novo banco';
        var existente = window.confirm(msg);

        var onConnected = function (path) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Conectado: ' + path, 'info');
          }
          document.dispatchEvent(new CustomEvent('coplan:config-empresa-saved'));
          reloadEverything();
          // [F1] Auto-prompt choose_packages na 1a conexao com este
          // banco (replica desktop load_last_obras). localStorage guarda
          // paths ja vistos para nao perguntar de novo.
          try {
            var seen = JSON.parse(
              localStorage.getItem('coplan.connected_paths') || '[]');
            if (!Array.isArray(seen)) seen = [];
            if (seen.indexOf(path) < 0) {
              seen.push(path);
              if (seen.length > 20) seen = seen.slice(-20);
              localStorage.setItem('coplan.connected_paths',
                                   JSON.stringify(seen));
              setTimeout(function () {
                if (typeof window.coplanOpenChoosePackages === 'function') {
                  window.coplanOpenChoosePackages();
                }
              }, 500);
            }
          } catch (e) { /* sem localStorage / JSON erro */ }
        };

        if (existente) {
          if (!api.header_connect_db) return;
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Selecione o arquivo .db...', 'info');
          }
          api.header_connect_db().then(function (r) {
            if (r && r.ok) {
              onConnected(r.path);
            } else if (r && r.error && r.error !== 'cancelado'
                       && typeof window.coplanToast === 'function') {
              window.coplanToast('Falha: ' + r.error, 'error');
            }
          });
        } else {
          if (!api.db_create_new) {
            if (typeof window.coplanToast === 'function') {
              window.coplanToast('API db_create_new indisponivel', 'error');
            }
            return;
          }
          // path vazio -> backend abre SAVE dialog
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Selecione o caminho do novo banco...', 'info');
          }
          api.db_create_new('').then(function (r) {
            if (r && r.ok) {
              if (typeof window.coplanToast === 'function') {
                window.coplanToast('Novo banco criado: ' + r.path, 'info');
              }
              onConnected(r.path);
            } else if (r && r.error && r.error !== 'cancelado'
                       && typeof window.coplanToast === 'function') {
              window.coplanToast('Falha: ' + r.error, 'error');
            }
          });
        }
      });
    }

    // Importar Excel
    var btnImp = findHeaderBtnByTitle('importar excel');
    if (btnImp && !btnImp.__pivoted) {
      btnImp.__pivoted = true;
      btnImp.addEventListener('click', function () {
        if (!(api && api.header_import_excel)) return;
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Selecione o arquivo de origem...', 'info');
        }
        api.header_import_excel('ask').then(function (r) {
          if (!r) return;
          // Resultado simples (sem duplicadas) ou erro
          var handleFinal = function (res) {
            if (res.ok) {
              if (typeof window.coplanToast === 'function') {
                var partes = [(res.imported || 0) + ' inserida(s)'];
                if (res.merged) partes.push(res.merged + ' mesclada(s)');
                if (res.skipped) partes.push(res.skipped + ' pulada(s)');
                if (res.errors && res.errors.length) {
                  partes.push(res.errors.length + ' erro(s)');
                }
                window.coplanToast(partes.join(' / ') + ' (de '
                  + (res.total || res.imported || 0) + ')',
                  res.errors && res.errors.length ? 'warn' : 'info');
              }
              // Mesmo com ok=true, mostra modal se houver erros/duplicadas
              if (window.coplanReportError
                  && ((res.errors && res.errors.length)
                      || (res.duplicadas && res.duplicadas.length))) {
                window.coplanReportError(
                  'Importacao Excel', 'import_excel', res);
              }
              if (typeof reloadEverything === 'function') reloadEverything();
            } else if (res.error && res.error !== 'cancelado'
                       && typeof window.coplanToast === 'function') {
              window.coplanToast('Falha: ' + res.error, 'error');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Importacao Excel', 'import_excel', res);
              }
            }
          };
          if (r.need_user_action && r.duplicadas_count) {
            // Replica _prompt_duplicate_action do desktop, agora em
            // batch (decisao para todas duplicadas de uma vez).
            var preview = (r.duplicadas || []).slice(0, 5).map(function (d) {
              return 'L' + d.linha + ' -> existe COD ' + (d.dup_cod || '?');
            }).join('\n');
            var openFn = window.coplanOpenDialog
              || function () { return Promise.resolve(null); };
            openFn({
              title: r.duplicadas_count + ' duplicada(s) detectada(s)',
              html:
                '<div style="padding:14px 18px;line-height:1.5">'
                + '<p>Foram encontrados <strong>'
                + r.duplicadas_count + '</strong> registro(s) ja existentes'
                + ' no banco (de ' + r.total + ' linhas).</p>'
                + '<pre style="background:#f1f5f9;padding:8px 12px;'
                + 'border-radius:4px;font-size:11.5px;white-space:pre-wrap">'
                + preview + (r.duplicadas_count > 5
                             ? '\n... +' + (r.duplicadas_count - 5)
                             : '')
                + '</pre>'
                + '<p style="margin-top:12px"><strong>Como tratar?</strong></p>'
                + '<ul style="margin:6px 0 0;padding-left:20px;color:#475569">'
                + '<li><strong>Mesclar</strong>: atualiza a obra existente '
                + 'com os valores do Excel (sobrescreve colunas preenchidas '
                + 'quando diferem, ex.: ano)</li>'
                + '<li><strong>Criar</strong>: insere mesmo assim '
                + '(pode falhar se houver unique-index)</li>'
                + '<li><strong>Pular</strong>: ignora as duplicadas e '
                + 'importa so as novas</li>'
                + '</ul></div>',
              buttons: [
                { label: 'Cancelar', act: 'close' },
                { label: 'Pular', act: 'skip' },
                { label: 'Criar', act: 'create' },
                { label: 'Mesclar', primary: true, act: 'merge' },
              ],
            }).then(function (act) {
              if (!act || act === 'close') {
                if (typeof window.coplanToast === 'function') {
                  window.coplanToast('Importacao cancelada', 'warn');
                }
                return;
              }
              // Bloco 5: usa import_excel_async + modal de progresso
              // se disponivel; fallback para chamada sincrona antiga.
              if (api.import_excel_async && window.coplanProgress
                  && window.coplanProgress.start) {
                window.coplanProgress.start(
                  'Importando Excel (' + act + ')...',
                  function (result, errorStr, cancelled) {
                    if (cancelled && typeof window.coplanToast === 'function') {
                      window.coplanToast('Importacao cancelada pelo usuario',
                        'warn');
                      return;
                    }
                    if (errorStr && typeof window.coplanToast === 'function') {
                      window.coplanToast('Falha: ' + errorStr, 'error');
                      return;
                    }
                    if (result) handleFinal(result);
                  }
                );
                api.import_excel_async(r.path, act).then(function (st) {
                  if (st && !st.started) {
                    if (window.coplanProgress && window.coplanProgress.close) {
                      window.coplanProgress.close();
                    }
                    if (typeof window.coplanToast === 'function') {
                      window.coplanToast(
                        'Falha ao iniciar: ' + (st.error || '?'), 'error');
                    }
                  }
                }).catch(function (err) {
                  if (window.coplanProgress && window.coplanProgress.close) {
                    window.coplanProgress.close();
                  }
                  if (typeof window.coplanToast === 'function') {
                    window.coplanToast(
                      'Falha ao importar: '
                      + ((err && err.message) || err || '?'),
                      'error');
                  }
                });
              } else {
                if (typeof window.coplanToast === 'function') {
                  window.coplanToast('Aplicando ' + act + '...', 'info');
                }
                api.import_excel_apply(r.path, act).then(handleFinal)
                  .catch(function (err) {
                    if (typeof window.coplanToast === 'function') {
                      window.coplanToast(
                        'Falha ao importar: '
                        + ((err && err.message) || err || '?'),
                        'error');
                    }
                  });
              }
            });
            return;
          }
          // Sem duplicadas: tambem usa async se disponivel.
          if (api.import_excel_async && window.coplanProgress
              && window.coplanProgress.start) {
            window.coplanProgress.start(
              'Importando Excel...',
              function (result, errorStr, cancelled) {
                if (cancelled && typeof window.coplanToast === 'function') {
                  window.coplanToast('Importacao cancelada pelo usuario',
                    'warn');
                  return;
                }
                if (errorStr && typeof window.coplanToast === 'function') {
                  window.coplanToast('Falha: ' + errorStr, 'error');
                  return;
                }
                if (result) handleFinal(result);
              }
            );
            api.import_excel_async(r.path, 'create').then(function (st) {
              if (st && !st.started) {
                if (window.coplanProgress && window.coplanProgress.close) {
                  window.coplanProgress.close();
                }
                if (typeof window.coplanToast === 'function') {
                  window.coplanToast(
                    'Falha ao iniciar: ' + (st.error || '?'), 'error');
                }
              }
            }).catch(function (err) {
              if (window.coplanProgress && window.coplanProgress.close) {
                window.coplanProgress.close();
              }
              if (typeof window.coplanToast === 'function') {
                window.coplanToast(
                  'Falha ao importar: '
                  + ((err && err.message) || err || '?'),
                  'error');
              }
            });
            return;
          }
          handleFinal(r);
        }).catch(function (err) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast(
              'Falha ao importar: '
              + ((err && err.message) || err || '?'),
              'error');
          }
        });
      });
    }

    // Exportar Excel
    // Respeita o escopo do filtro ativo em Visualizar: se ha' filtros
    // aplicados (busca ou chips), exporta apenas os cods visiveis via
    // export_detalhamento(cods). Caso contrario, exporta tudo.
    var btnExp = findHeaderBtnByTitle('exportar excel');
    if (btnExp && !btnExp.__pivoted) {
      btnExp.__pivoted = true;
      btnExp.addEventListener('click', function () {
        if (!api) return;
        var filtered = (typeof window.coplanFilteredCods === 'function')
          ? window.coplanFilteredCods()
          : null;
        var hasFilter = Array.isArray(filtered);
        if (hasFilter && filtered.length === 0) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Filtro atual nao retornou obras', 'warn');
          }
          return;
        }
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(
            hasFilter
              ? ('Exportando ' + filtered.length + ' obra(s) filtrada(s)...')
              : 'Exportando todas as obras...',
            'info');
        }
        var prom;
        if (hasFilter && api.export_detalhamento) {
          prom = api.export_detalhamento(filtered);
        } else if (api.header_export_excel) {
          prom = api.header_export_excel();
        } else {
          return;
        }
        prom.then(function (r) {
          if (r && r.ok && typeof window.coplanToast === 'function') {
            var msg = 'XLSX salvo (' + (r.count || 0) + ' obras';
            if (r.cenario) {
              msg += ', cenario=' + r.cenario;
            } else {
              msg += ', sem cenario';
            }
            msg += '): ' + r.path;
            window.coplanToast(msg, 'info');
          } else if (r && typeof window.coplanToast === 'function') {
            window.coplanToast('Falha: ' + (r.error || '?'), 'error');
          }
        }).catch(function (err) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast(
              'Falha ao exportar: ' + ((err && err.message) || err || '?'),
              'error');
          }
        });
      });
    }

    // [FIX] Botoes CSV (Importar + Exportar) REMOVIDOS por feedback do
    // usuario: funcionalidade duplicada com Excel — os botoes Excel ja
    // cobrem o caso de uso (xlsx eh o formato canonico). Manter so
    // 2 botoes: Importar Excel + Exportar Excel.

    // Botao Ajuda da sidebar (#btn-help) -- abre uma janela explicativa
    // simples (mostrar atalhos de teclado e referenciar o HANDOFF).
    var btnHelp = document.getElementById('btn-help');
    if (btnHelp && !btnHelp.__pivoted) {
      btnHelp.__pivoted = true;
      btnHelp.addEventListener('click', function () {
        var msg = 'COPLAN -- atalhos:'
          + '\n  Ctrl+1..5: Visualizar/Cadastro/Ganhos/Resumo/Config'
          + '\n  Ctrl+F: focar busca da Visualizar'
          + '\n  Ctrl+B: salvar obra (na aba Cadastro)'
          + '\n  PageUp/PageDown: paginas da tabela Visualizar'
          + '\n  Esc no campo de busca: limpar filtro'
          + '\n\nConfiguracoes -> caminhos do banco/apoio/ganhos.';
        try { window.alert(msg); }
        catch (e) {
          if (typeof window.coplanToast === 'function') {
            window.coplanToast('Atalhos: Ctrl+1..5, Ctrl+F, Ctrl+B', 'info');
          }
        }
      });
    }
  }

  // bindHeaderButtons captura `api` em closure -- precisamos garantir que
  // window.pywebview.api JA existe antes de bindar, senao todos os clicks
  // (Conectar Banco, Importar/Exportar Excel, CSV) caem silenciosamente.
  var _bindHeaderWhenReady = function () {
    if (typeof window.coplanReady === 'function') {
      window.coplanReady(bindHeaderButtons);
    } else {
      bindHeaderButtons();
    }
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _bindHeaderWhenReady);
  } else {
    _bindHeaderWhenReady();
  }
})();
</script>
