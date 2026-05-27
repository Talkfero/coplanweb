
<script>
(function () {
  // ---- Helper compartilhado entre passos ----
  // window.coplanReady(fn) -> chama fn() quando window.pywebview.api existir.
  var queue = [];
  var ready = false;
  function flush() {
    ready = true;
    while (queue.length) {
      try { (queue.shift())(); } catch (e) { console.warn('[coplan] cb erro:', e); }
    }
  }
  window.coplanReady = function (fn) {
    if (ready) { try { fn(); } catch (e) { console.warn('[coplan] cb erro:', e); } }
    else { queue.push(fn); }
  };
  if (window.pywebview && window.pywebview.api) flush();
  else window.addEventListener('pywebviewready', flush);
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 1 (Tokens e tema) ----
  // Tokens vem do CSS embutido no Coplan UI.html. Apenas confirmamos
  // que o bridge esta vivo logando o ping.
  window.coplanReady(function () {
    window.pywebview.api.ping().then(function (r) {
      console.log('[coplan] bridge ok:', r);
    });
  });
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 2.1 (Header / source pills) ----
  // Substitui as pills hardcoded do mock por dados reais vindos do
  // config.json (Banco/Apoio) e snapshot interno (Tecnico).
  function pillIcon(kind) {
    if (kind === 'db') return 'database';
    if (kind === 'apoio') return 'folder-open';
    return 'clock';
  }
  function pillTitle(kind) {
    if (kind === 'db') return 'Banco';
    if (kind === 'apoio') return 'Apoio';
    return 'Tecnico';
  }
  // IDs/sources estaveis (consumido por applyDataState abaixo).
  function pillId(kind) {
    if (kind === 'tecnico') return 'pill-tecnico';
    return 'pill-' + kind;
  }
  function pillSource(kind) {
    if (kind === 'tecnico') return 'tecnico_txt';
    return kind;
  }
  function renderPill(kind, info) {
    var cls = 'src-pill ' + (info && info.status ? info.status : 'err');
    var icon = pillIcon(kind);
    var title = pillTitle(kind);
    var detail = (info && (info.name || info.label)) || '';
    var detailCls = info && info.name ? 'mono' : '';
    var safeDetail = String(detail).replace(/[<>&"]/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'})[c];
    });
    var titleAttr = info && info.path
      ? ' title="' + String(info.path).replace(/"/g, '&quot;') + '"'
      : '';
    var idAttr = ' id="' + pillId(kind) + '" data-source="' + pillSource(kind) + '"';
    var nameSpanId = ' id="' + pillId(kind) + '-name"';
    return '<div class="' + cls + '"' + idAttr + titleAttr + '>'
         + '<i data-lucide="' + icon + '"></i>' + title
         + (safeDetail ? '<span class="' + detailCls + '" style="opacity:.7"'
                        + nameSpanId + '>' + safeDetail + '</span>' : '')
         + '</div>';
  }
  function applyAppState(state) {
    if (!state || !state.sources) return;
    var box = document.querySelector('.h-source-pills');
    if (!box) return;
    // Pill Apoio removida do header: status do apoio agora vive no
    // card "Empresa" de Configuracoes (apoio agora e DB-backed e nao
    // precisa de pill propria).
    var html = renderPill('db', state.sources.db)
             + renderPill('tecnico', state.sources.tecnico);
    box.innerHTML = html;
    if (window.lucide) lucide.createIcons();
    // Propaga estado pra outros passos (status bar etc.) via cache global.
    window.__coplanState = state;
    document.dispatchEvent(new CustomEvent('coplan:state', { detail: state }));
    // Apos pintar pills via _file_state (rapido), pede ao backend o
    // estado real (DataStateManager) pra refletir validado/invalidado
    // com timestamps. Nao bloqueia a renderizacao.
    refreshDataStateChips();
  }

  // ---- Estado de Fontes (RB-1.1 / RB-5 do desktop) ----
  // Sobrepoe a info de _file_state (so existencia) com o DataStateManager
  // (validado/invalidado por hook nas APIs). Gerencia ate 4 fontes:
  // db, apoio, ganhos (sem pill), tecnico_txt.
  function dsKindToPill(source) {
    if (source === 'db') return 'pill-db';
    if (source === 'apoio') return 'pill-apoio';
    if (source === 'tecnico_txt') return 'pill-tecnico';
    return null;
  }
  function dsStateClass(state) {
    if (state === 'CARREGADO_VALIDADO') return 'ok';
    if (state === 'CARREGADO_PARCIAL') return 'warn';
    if (state === 'INVALIDADO') return 'err';
    return 'warn';  // NAO_CARREGADO
  }
  function dsStateIcon(state) {
    if (state === 'CARREGADO_VALIDADO') return null;  // mantem default
    if (state === 'INVALIDADO') return 'alert-circle';
    if (state === 'CARREGADO_PARCIAL') return 'clock';
    return 'help-circle';  // NAO_CARREGADO
  }
  // [FIX] Catalogo de tooltips amigaveis por (source, state).
  // Antes o title era "TECNICO_TXT: NAO_CARREGADO" — incompreensivel
  // para o usuario final. Agora explica o que e e como resolver.
  var SOURCE_NAME = {
    db: 'Banco de Obras',
    apoio: 'Planilha de Apoio',
    tecnico_txt: 'Arquivos Tecnicos (FlowMT/Topologia/Confiabilidade)'
  };
  var SOURCE_FIX_HINT = {
    db: 'Configure em Configuracoes -> Empresa.',
    apoio: 'Configure em Configuracoes -> Empresa.',
    tecnico_txt: 'Selecione a pasta na aba Ganhos.'
  };
  function friendlyTip(source, info) {
    var name = SOURCE_NAME[source] || source.toUpperCase();
    var state = String(info.state || 'N/D');
    var lines = [name];
    if (state === 'CARREGADO_VALIDADO') {
      lines.push('Status: OK (operacional)');
    } else if (state === 'CARREGADO_PARCIAL') {
      lines.push('Status: Parcialmente carregado');
      if (info.error_last) lines.push('Detalhe: ' + info.error_last);
      lines.push(SOURCE_FIX_HINT[source] || '');
    } else if (state === 'INVALIDADO') {
      lines.push('Status: ERRO');
      if (info.error_last) lines.push('Detalhe: ' + info.error_last);
      lines.push(SOURCE_FIX_HINT[source] || '');
    } else if (state === 'NAO_CARREGADO') {
      lines.push('Status: Nao carregado');
      lines.push(SOURCE_FIX_HINT[source] || '');
    } else {
      lines.push('Status: ' + state);
    }
    if (info.validated_at) lines.push('Validado: ' + info.validated_at);
    if (info.path) lines.push('Caminho: ' + info.path);
    lines.push('--');
    lines.push('Clique para abrir a configuracao.');
    return lines.filter(Boolean).join('\n');
  }

  function applyDataState(ds) {
    if (!ds || !ds.sources) return;
    Object.keys(ds.sources).forEach(function (source) {
      var pillId = dsKindToPill(source);
      if (!pillId) return;  // ganhos nao tem pill no header
      var pill = document.getElementById(pillId);
      if (!pill) return;
      var info = ds.sources[source] || {};
      var stateCls = dsStateClass(info.state);
      // Substitui apenas a classe ok/warn/err mantendo src-pill e id
      pill.className = 'src-pill ' + stateCls;
      // [FIX] Tooltip amigavel multi-linha.
      pill.title = friendlyTip(source, info);
      pill.style.cursor = 'pointer';
      // [FIX] Click navega para a fonte de configuracao (db/apoio ->
      // aba Configuracoes; tecnico_txt -> aba Cadastro, secao Ganhos).
      // Idempotente.
      if (!pill.__coplanClickBound) {
        pill.__coplanClickBound = true;
        pill.addEventListener('click', function () {
          if (typeof window.coplanSetTab !== 'function') return;
          if (source === 'tecnico_txt') {
            window.coplanSetTab('cadastro');
          } else {
            window.coplanSetTab('config');
          }
        });
      }
      // Tecnico: anexa contagem dirty na label
      if (source === 'tecnico_txt') {
        var dirty = ds.tecnico_dirty_count || 0;
        var nameSpan = document.getElementById('pill-tecnico-name');
        if (nameSpan) {
          if (info.state === 'CARREGADO_VALIDADO' && dirty === 0) {
            nameSpan.textContent = 'OK';
          } else if (dirty > 0) {
            nameSpan.textContent = 'DIRTY (' + dirty + ')';
          } else if (info.state === 'INVALIDADO') {
            nameSpan.textContent = 'INVALIDADO';
          } else {
            nameSpan.textContent = info.state === 'CARREGADO_PARCIAL'
              ? 'PARCIAL' : 'N/D';
          }
        }
      }
    });
    window.__coplanDataState = ds;
    document.dispatchEvent(new CustomEvent('coplan:data_state', { detail: ds }));
  }
  function refreshDataStateChips() {
    if (!(window.pywebview && window.pywebview.api
          && window.pywebview.api.data_state_get)) return Promise.resolve();
    return window.pywebview.api.data_state_get().then(function (ds) {
      if (ds && ds.ok) applyDataState(ds);
      return ds;
    }).catch(function (e) {
      console.warn('[coplan] data_state_get falhou:', e);
    });
  }
  // Expoe globalmente pra outros scripts chamarem apos mutacoes.
  window.coplanRefreshChips = refreshDataStateChips;
  window.coplanGetDataState = function () { return window.__coplanDataState; };

  window.coplanReady(function () {
    window.pywebview.api.get_app_state().then(applyAppState).catch(function (e) {
      console.warn('[coplan] get_app_state falhou:', e);
    });
  });
})();
</script>
<script>
(function () {
  // ---- Estado de Fontes / require_state wrapper ----
  // Replica o EstadoFontesMixin.require_state do desktop: gateara qualquer
  // acao que dependa de db/apoio/ganhos/tecnico_txt validados, mostrando
  // um dialog com botoes "Ir para X" pra resolver a pendencia.
  //
  // Uso:
  //   coplanRequireState('Atualizar Plano',
  //                      { db: 'CARREGADO_VALIDADO', apoio: 'CARREGADO_VALIDADO' })
  //     .then(function (ok) { if (ok) doActualWork(); });
  //
  // Se ok=true a acao pode prosseguir; se false, o dialog ja foi mostrado
  // e o usuario foi redirecionado pra fonte que falta.
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function buildDialog(action, pendencias) {
    // Monta um <dialog> minimalista (mesmo estilo dos modais existentes).
    var existing = document.getElementById('coplan-require-dialog');
    if (existing) existing.remove();
    var dlg = document.createElement('dialog');
    dlg.id = 'coplan-require-dialog';
    dlg.className = 'modal';
    dlg.style.cssText =
      'border:none;border-radius:12px;padding:0;min-width:440px;'
      + 'max-width:560px;box-shadow:0 8px 24px rgba(0,0,0,.15);';
    var pendList = pendencias.map(function (p) {
      return '<li style="margin:.4em 0">'
           + '<strong>' + escHtml(p.label) + '</strong>'
           + ' <span style="color:#64748b">(' + escHtml(p.state) + ')</span>'
           + '<br><span style="color:#64748b;font-size:.92em">'
           + escHtml(p.hint) + '</span></li>';
    }).join('');
    var btnRow = pendencias.map(function (p) {
      return '<button class="btn primary" data-go="' + escHtml(p.source)
           + '" type="button" style="margin-right:.5em;margin-top:.5em">'
           + 'Ir para ' + escHtml(p.label) + '</button>';
    }).join('');
    dlg.innerHTML =
      '<div class="modal-header" style="padding:14px 18px;'
      + 'border-bottom:1px solid #e2e8f0">'
      + '<strong style="font-size:1.05em">Pre-requisitos nao atendidos</strong>'
      + '</div>'
      + '<div style="padding:18px">'
      + '<p style="margin:0 0 .5em">Acao bloqueada: '
      + '<em>' + escHtml(action) + '</em></p>'
      + '<p style="margin:0 0 .8em;color:#64748b">'
      + 'Resolva as pendencias abaixo antes de continuar:</p>'
      + '<ul style="margin:0;padding-left:1.2em">' + pendList + '</ul>'
      + '<div style="margin-top:14px">' + btnRow
      + '<button class="btn ghost" type="button" data-close="1" '
      + 'style="margin-top:.5em">Fechar</button></div>'
      + '</div>';
    document.body.appendChild(dlg);
    return dlg;
  }
  function goToSource(source) {
    // Equivalente a _go_to_required_source: troca aba e tenta abrir o
    // file picker (config) da fonte que falta.
    var sb = function (tab) {
      var btn = document.querySelector('.sb-item[data-tab="' + tab + '"]');
      if (btn) btn.click();
    };
    if (source === 'db') {
      sb('config');
      // Botao "Conectar Banco" -> header_connect_db
      setTimeout(function () {
        if (window.pywebview && window.pywebview.api
            && window.pywebview.api.header_connect_db) {
          window.pywebview.api.header_connect_db().then(function () {
            if (window.coplanRefreshChips) window.coplanRefreshChips();
          }).catch(function (err) {
            console.warn('goToSource(db) falhou:', err);
            if (typeof window.coplanToast === 'function') {
              window.coplanToast(
                'Falha ao conectar Banco: '
                + ((err && err.message) || err || '?'),
                'error');
            }
            if (window.coplanReportError) {
              window.coplanReportError(
                'Ir para Banco', 'header_connect_db',
                { error: String((err && err.message) || err || '?') });
            }
          });
        }
      }, 200);
      return;
    }
    if (source === 'apoio') {
      sb('config');
      setTimeout(function () {
        if (window.pywebview && window.pywebview.api
            && window.pywebview.api.pick_and_load_apoio) {
          window.pywebview.api.pick_and_load_apoio().then(function () {
            if (window.coplanRefreshChips) window.coplanRefreshChips();
          }).catch(function (err) {
            console.warn('goToSource(apoio) falhou:', err);
            if (typeof window.coplanToast === 'function') {
              window.coplanToast(
                'Falha ao carregar Apoio: '
                + ((err && err.message) || err || '?'),
                'error');
            }
            if (window.coplanReportError) {
              window.coplanReportError(
                'Ir para Apoio', 'pick_and_load_apoio',
                { error: String((err && err.message) || err || '?') });
            }
          });
        }
      }, 200);
      return;
    }
    if (source === 'ganhos' || source === 'tecnico_txt') {
      sb('ganhos');
      setTimeout(function () {
        if (window.pywebview && window.pywebview.api
            && window.pywebview.api.pick_ganhos_folder) {
          window.pywebview.api.pick_ganhos_folder().then(function () {
            if (window.coplanRefreshChips) window.coplanRefreshChips();
          }).catch(function (err) {
            console.warn('goToSource(ganhos) falhou:', err);
            if (typeof window.coplanToast === 'function') {
              window.coplanToast(
                'Falha ao carregar Ganhos: '
                + ((err && err.message) || err || '?'),
                'error');
            }
            if (window.coplanReportError) {
              window.coplanReportError(
                'Ir para Ganhos', 'pick_ganhos_folder',
                { error: String((err && err.message) || err || '?') });
            }
          });
        }
      }, 200);
      return;
    }
  }
  function showRequireDialog(action, pendencias) {
    return new Promise(function (resolve) {
      var dlg = buildDialog(action, pendencias);
      dlg.addEventListener('click', function (ev) {
        var btn = ev.target.closest('button');
        if (!btn) return;
        if (btn.dataset.close) {
          dlg.close();
          dlg.remove();
          resolve(false);
          return;
        }
        if (btn.dataset.go) {
          dlg.close();
          dlg.remove();
          goToSource(btn.dataset.go);
          resolve(false);  // acao original cancelada; usuario redirecionado
          return;
        }
      });
      if (typeof dlg.showModal === 'function') {
        dlg.showModal();
      } else {
        dlg.setAttribute('open', '');
      }
    });
  }
  window.coplanRequireState = function (action, required) {
    if (!(window.pywebview && window.pywebview.api
          && window.pywebview.api.data_state_require)) {
      // Sem backend: deixa passar (modo dev/preview).
      return Promise.resolve(true);
    }
    return window.pywebview.api.data_state_require(
      String(action || 'acao'), required || null
    ).then(function (r) {
      if (r && r.ok) return true;
      var pend = (r && r.pendencias) || [];
      if (!pend.length) return true;  // sem pendencias mas !ok = strange
      return showRequireDialog(action, pend);
    }).catch(function (e) {
      console.warn('[coplan] data_state_require falhou:', e);
      return true;  // fallback: nao bloqueia em caso de erro de transporte
    });
  };
  // Helper: gateara uma funcao com require_state. Se ok, executa fn();
  // se nao, cancela a acao (showRequireDialog ja foi exibido).
  window.coplanGuard = function (action, required, fn) {
    return window.coplanRequireState(action, required).then(function (ok) {
      if (!ok) return null;
      try { return fn(); } catch (e) {
        console.error('[coplan] coplanGuard fn() lancou:', e);
        return null;
      }
    });
  };
  // Presets prontos para os varios tipos de acao do desktop.
  // Replica require_export_sources e variantes do EstadoFontesMixin.
  window.coplanRequirePresets = {
    db_only: { db: 'CARREGADO_VALIDADO' },
    db_apoio: {
      db: 'CARREGADO_VALIDADO',
      apoio: 'CARREGADO_VALIDADO',
    },
    db_ganhos_tecnico: {
      db: 'CARREGADO_VALIDADO',
      ganhos: 'CARREGADO_VALIDADO',
      tecnico_txt: 'CARREGADO_VALIDADO',
    },
    export_full: {
      db: 'CARREGADO_VALIDADO',
      ganhos: 'CARREGADO_VALIDADO',
      tecnico_txt: 'CARREGADO_VALIDADO',
    },
  };

  // ---- External DB update warning (RB-5 do desktop) ----
  // Polling periodico a cada 30s checando se outro usuario gravou no
  // banco entre 2 pontos. Toast warn quando detecta + invalida db
  // localmente (forca o user a recarregar pra ver as mudancas).
  function checkExternalDbUpdate() {
    if (!(window.pywebview && window.pywebview.api
          && window.pywebview.api.db_check_external_update)) {
      return;
    }
    window.pywebview.api.db_check_external_update().then(function (r) {
      if (!r || !r.ok || !r.mudou || r.ja_avisado || r.first_call) {
        return;
      }
      var msg = 'Banco atualizado por '
              + (r.usuario || 'outro usuario')
              + ' em ' + (r.data || '?')
              + '. Recarregue para ver as mudancas.';
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(msg, 'warn');
      } else {
        console.warn('[coplan]', msg);
      }
    }).catch(function (e) {
      console.warn('[coplan] db_check_external_update falhou:', e);
    });
  }
  // Marca baseline assim que o JS estiver pronto + roda check periodico.
  window.coplanReady && window.coplanReady(function () {
    if (window.pywebview && window.pywebview.api
        && window.pywebview.api.db_mark_refresh_point) {
      window.pywebview.api.db_mark_refresh_point().catch(function () {});
    }
    setInterval(checkExternalDbUpdate, 30 * 1000);
  });
  window.coplanCheckExternalDb = checkExternalDbUpdate;
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 2.2 (Status bar) ----
  // Reage ao evento coplan:state (disparado em 2.1) para preencher itens
  // 2 (banco), 3 (apoio), 4 (user), 5 (ultima modif. = mtime do db),
  // 6 (selecionadas, placeholder ate Passo 3.x) e 7 (versao).
  function fmtSize(bytes) {
    if (!bytes || bytes <= 0) return '';
    var kb = bytes / 1024, mb = kb / 1024, gb = mb / 1024;
    if (gb >= 1) return gb.toFixed(1).replace('.', ',') + ' GB';
    if (mb >= 1) return mb.toFixed(1).replace('.', ',') + ' MB';
    if (kb >= 1) return kb.toFixed(1).replace('.', ',') + ' KB';
    return bytes + ' B';
  }
  function fmtMtime(epoch) {
    if (!epoch || epoch <= 0) return '';
    var d = new Date(epoch * 1000);
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + '/'
         + d.getFullYear() + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function applyStatus(state) {
    var bar = document.querySelector('footer.status');
    if (!bar) return;
    var src = (state && state.sources) || {};
    var db = src.db || {};
    var apoio = src.apoio || {};
    var app = (state && state.app) || {};

    var dbLabel = db.name || 'banco nao configurado';
    var dbSize = fmtSize(db.size);
    var dbCell = '<i data-lucide="database"></i>' + esc(dbLabel)
               + (dbSize ? ' (' + esc(dbSize) + ')' : '');
    var apoioLabel = apoio.name || 'apoio nao configurado';
    var apoioCell = '<i data-lucide="folder"></i>' + esc(apoioLabel);
    var userLabel = app.user || '?';
    var userCell = '<i data-lucide="user"></i>' + esc(userLabel);

    var mtimeStr = fmtMtime(db.mtime);
    var modCell = mtimeStr
      ? 'Ultima modificacao: <span class="mono">' + esc(mtimeStr) + '</span>'
      : 'Ultima modificacao: <span class="mono">--</span>';

    var selCell = '<span id="status-selection">-- selecionadas</span>';
    var verCell = esc(app.version || '');

    bar.innerHTML =
        '<span class="item"><span class="pulse"></span>'
      + (db.status === 'ok' ? 'Conectado' : 'Sem banco') + '</span>'
      + '<span class="sep"></span>'
      + '<span class="item mono" title="' + esc(db.path || '') + '">' + dbCell + '</span>'
      + '<span class="sep"></span>'
      + '<span class="item mono" title="' + esc(apoio.path || '') + '">' + apoioCell + '</span>'
      + '<span class="sep"></span>'
      + '<span class="item">' + userCell + '</span>'
      + '<span class="grow" style="flex:1;"></span>'
      + '<span class="item">' + modCell + '</span>'
      + '<span class="sep"></span>'
      + '<span class="item">' + selCell + '</span>'
      + '<span class="sep"></span>'
      + '<span class="item">' + verCell + '</span>';
    if (window.lucide) lucide.createIcons();
  }
  // Reage tanto a um state ja em cache (caso 2.1 ja tenha rodado) quanto
  // ao evento futuro.
  if (window.__coplanState) applyStatus(window.__coplanState);
  document.addEventListener('coplan:state', function (ev) {
    applyStatus(ev.detail);
  });
  // Helper publico pro Passo 3.x atualizar o contador sem refazer tudo.
  window.coplanSetSelectionCount = function (sel, total) {
    var node = document.getElementById('status-selection');
    if (!node) return;
    if (total == null) node.textContent = sel + ' selecionadas';
    else node.textContent = sel + ' selecionadas de ' + total;
  };
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 2.3 (Sidebar / navegacao) ----
  // O HTML mock ja tem setActiveTab/click handlers em .sb-item[data-tab]
  // (linha ~1641 do Coplan UI.html). Aqui apenas adicionamos um "after"
  // hook para que outros passos saibam quando a aba muda, e atalhos
  // Ctrl+1..5 para troca rapida.
  function fireTabEvent(name, source) {
    document.dispatchEvent(new CustomEvent('coplan:tab', {
      detail: { name: name, source: source || 'click' }
    }));
  }
  function bindNav() {
    var items = document.querySelectorAll('.sb-item[data-tab]');
    if (!items.length) return false;
    items.forEach(function (b) {
      // O handler do mock ja roda primeiro; adicionamos o nosso depois,
      // capturando o tab efetivamente ativado.
      b.addEventListener('click', function () {
        fireTabEvent(b.dataset.tab, 'click');
        // Ganhos foi integrado ao Cadastro (mesma pagina, abaixo). Como
        // nao ha mais aba/botao proprio de Ganhos, re-disparamos o evento
        // 'ganhos' ao abrir o Cadastro para inicializar os listeners que
        // ouvem coplan:tab name==='ganhos'.
        if (b.dataset.tab === 'cadastro') {
          fireTabEvent('ganhos', 'merged');
        }
      });
    });
    // Detecta a aba ativa inicial e dispara evento (passos posteriores
    // que carregam dados ao entrar na aba conseguem inicializar).
    var initial = document.querySelector('.sb-item.active[data-tab]');
    if (initial) fireTabEvent(initial.dataset.tab, 'init');

    // API publica para programaticamente trocar de aba
    // (passos 4.x usam apos salvar uma obra para voltar pra Visualizar).
    window.coplanSetTab = function (name) {
      var btn = document.querySelector('.sb-item[data-tab="' + name + '"]');
      if (btn) btn.click();
    };

    // Atalhos Ctrl+1..4 para Visualizar/Cadastro/Resumo/Config.
    // (Ganhos foi integrado ao Cadastro; nao tem mais atalho proprio.)
    var shortcuts = {
      '1': 'visualizar', '2': 'cadastro',
      '3': 'resumo',     '4': 'config',
    };
    document.addEventListener('keydown', function (e) {
      if (!(e.ctrlKey || e.metaKey)) return;
      var name = shortcuts[e.key];
      if (!name) return;
      // Evita conflito com Ctrl+1 do navegador (selecionar primeira aba).
      e.preventDefault();
      window.coplanSetTab(name);
    });
    return true;
  }
  // O mock JS roda inline na ordem do <script>; quando nosso codigo entra
  // ele ja existe. Mas como reforco, retentamos no DOMContentLoaded.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindNav);
  } else {
    if (!bindNav()) {
      // Fallback: 1 retry curto caso a sidebar ainda nao tenha sido
      // montada (improvavel, mas barato).
      setTimeout(bindNav, 50);
    }
  }
})();
</script>
