<script>
(function () {
  // ---- Section 6 / Passo 3.6 (Visualizar / toolbar de ações) ----
  // Conecta os botoes da .table-toolbar:
  //   Atualizar      -> API.atualizar_obras_valores(cods) (exige selecao)
  //   Detalhamento   -> API.export_detalhamento(cods_selecionados)
  //   Relat. Crit.   -> API.export_relatorio_criterios()
  //   Nota Colapso   -> API.export_nota_colapso(cods)  (stub)
  //   Excluir        -> confirma + API.delete_obras(cods) + reload
  // Reusa o #toast existente do mock para feedback.

  function toast(msg, type) {
    var t = document.getElementById('toast');
    if (!t) { console.log('[coplan toast]', msg); return; }
    var color = (type === 'error') ? 'var(--danger)'
              : (type === 'warn')  ? 'var(--warning)'
              : 'var(--success)';
    var icon = (type === 'error') ? 'alert-octagon'
             : (type === 'warn')  ? 'alert-triangle'
             : 'check-circle-2';
    t.innerHTML = '<i data-lucide="' + icon + '"'
                + ' style="width:14px;height:14px;color:' + color + ';"></i> '
                + String(msg).replace(/[<>&]/g, function (c) {
                    return ({'<':'&lt;','>':'&gt;','&':'&amp;'})[c];
                  });
    t.classList.add('show');
    if (window.lucide) lucide.createIcons();
    clearTimeout(window.__toastT);
    window.__toastT = setTimeout(function () { t.classList.remove('show'); }, 2400);
  }
  window.coplanToast = toast;

  function getSelectedCods() {
    var rows = document.querySelectorAll('#obras-tbody tr[data-cod]');
    var out = [];
    rows.forEach(function (r) {
      var c = r.querySelector('input[type="checkbox"]');
      if (c && c.checked) out.push(r.getAttribute('data-cod'));
    });
    return out;
  }
  function updateSelectionCount() {
    var rows = document.querySelectorAll('#obras-tbody tr[data-cod]');
    var sel = 0;
    rows.forEach(function (r) {
      var c = r.querySelector('input[type="checkbox"]');
      if (c && c.checked) {
        sel++;
        r.classList.add('selected');
      } else {
        r.classList.remove('selected');
      }
    });
    var total = Number(window.__coplanFullCount) || rows.length;
    if (typeof window.coplanSetSelectionCount === 'function') {
      window.coplanSetSelectionCount(sel, total);
    }
    var badge = document.querySelector('#tab-visualizar .table-header .badge');
    if (badge) {
      badge.textContent = total + ' resultados · ' + sel + ' selecionadas';
    }
  }
  // Re-bind selection on every render (coplan:obras dispara apos renderObras).
  document.addEventListener('coplan:obras', function () {
    var tbody = document.getElementById('obras-tbody');
    if (!tbody) return;
    tbody.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
      cb.addEventListener('change', updateSelectionCount);
    });
    var ckAll = document.getElementById('check-all');
    if (ckAll) {
      ckAll.checked = false;
      ckAll.onchange = function () {
        tbody.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
          cb.checked = ckAll.checked;
        });
        updateSelectionCount();
      };
    }
    // [C2] Shift+click range: rastreia ultimo checkbox clicado (anchor)
    // e marca todos entre anchor e checkbox atual quando user segura Shift.
    // Replica QAbstractItemView.ExtendedSelection do desktop.
    var anchor = null;
    tbody.addEventListener('click', function (ev) {
      var cb = ev.target;
      if (!cb || cb.type !== 'checkbox') return;
      var allCbs = Array.prototype.slice.call(
        tbody.querySelectorAll('input[type="checkbox"]'));
      if (ev.shiftKey && anchor && allCbs.indexOf(anchor) >= 0) {
        var i1 = allCbs.indexOf(anchor);
        var i2 = allCbs.indexOf(cb);
        if (i1 >= 0 && i2 >= 0) {
          var lo = Math.min(i1, i2), hi = Math.max(i1, i2);
          for (var j = lo; j <= hi; j++) {
            allCbs[j].checked = cb.checked;
          }
          updateSelectionCount();
        }
      }
      anchor = cb;
    });
    updateSelectionCount();
  });

  function findToolbarBtn(label) {
    var bar = document.querySelector('#tab-visualizar .table-toolbar');
    if (!bar) return null;
    var btns = bar.querySelectorAll('.btn');
    var lower = label.toLowerCase();
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].textContent.trim().toLowerCase().indexOf(lower) === 0) {
        return btns[i];
      }
    }
    return null;
  }

  function bindToolbar() {
    var bar = document.querySelector('#tab-visualizar .table-toolbar');
    if (!bar) return false;
    // Idempotente: bindToolbar e' chamado em coplan:tab + coplan:obras +
    // boot. Sem este guard, cada rebind empilhava um novo listener no
    // mesmo botao -> clicar em "Atualizar" mostrava N confirms em fila,
    // e ao confirmar todos disparava N chamadas de
    // atualizar_obras_valores_async (a 1a iniciava, as demais batiam no
    // guard "ja ha uma operacao em andamento").
    if (bar.__coplanToolbarBound) return true;
    var api = window.pywebview && window.pywebview.api;
    // Se a API ainda nao foi injetada pelo pywebview (race no boot),
    // NAO marca como bound -- senao todos os clicks subsequentes batem
    // em "API indisponivel". Deixa os triggers (coplan:tab, coplan:obras)
    // re-tentarem ate api estar pronta. handlers leem api via closure,
    // entao precisa ja existir aqui.
    if (!api || typeof api.atualizar_obras_valores !== 'function') {
      return false;
    }
    bar.__coplanToolbarBound = true;

    // Atualizar: replica legado (atualizar_obra_mixin.py:34-36).
    // Exige selecao; com COD selecionados, recalcula valor_obra via
    // atualizar_obras_valores -> processar_atualizacao (qtd x modulo +
    // modulos_extras configurados por PI).
    var btnRefresh = findToolbarBtn('Atualizar');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', function () {
        var cods = getSelectedCods();
        if (cods.length === 0) {
          return toast(
            'Selecione pelo menos uma obra visivel para atualizar.',
            'warn'
          );
        }
        if (!api || !api.atualizar_obras_valores) {
          return toast('API indisponivel', 'error');
        }
        // [F13] Plano de Obras: filtra cods bloqueados (linha cinza)
        if (window.coplanPlanoCheck) {
          cods = window.coplanPlanoCheck(cods, 'Recalcular valor');
          if (!cods.length) return;
        }
        var msg = 'Recalcular valor_obra para ' + cods.length
                + ' obra(s) selecionada(s)? Os valores sao buscados na'
                + ' planilha de apoio (aba MODULO) e gravados no banco.';
        if (!window.confirm(msg)) return;
        window.coplanAtualizarBulk(cods);
      });
    }

    // Detalhamento
    var btnDet = findToolbarBtn('Detalhamento');
    if (btnDet) {
      btnDet.addEventListener('click', function () {
        if (!api || !api.export_detalhamento) return toast('API indisponivel', 'error');
        var cods = getSelectedCods();
        var label = cods.length ? cods.length + ' obras selecionadas' : 'todas as obras';
        var presets = (window.coplanRequirePresets || {});
        var guard = window.coplanGuard || function (a, r, fn) { return Promise.resolve(fn()); };
        guard('Exportar Detalhamento', presets.db_only, function () {
          toast('Exportando ' + label + '...', 'info');
          return api.export_detalhamento(cods).then(function (r) {
            if (r && r.ok) toast('XLSX salvo: ' + r.path, 'info');
            else {
              toast('Falhou: ' + (r && r.error || '?'), 'error');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Exportar Detalhamento', 'export_detalhamento', r);
              }
            }
          }).catch(function (err) {
            toast('Falhou: ' + (err && err.message || err || '?'), 'error');
            if (window.coplanReportError) {
              window.coplanReportError(
                'Exportar Detalhamento', 'export_detalhamento',
                { error: String(err && err.message || err || '?') });
            }
          });
        });
      });
    }

    // Relatorio Criterios -- 2 modos:
    //   Click direto: relatorio "raw failures" (verificar_criterios_v2).
    //   Shift+click ou Alt+click: Fase A12 -- relatorio detalhado por
    //   projeto (montar_relatorio_criterios_por_projeto, 2 sheets).
    var btnRel = findToolbarBtn('Relat');
    if (btnRel) {
      btnRel.title = ('Click: falhas brutas. Shift/Alt+click: relatorio'
                    + ' detalhado por projeto.');
      btnRel.addEventListener('click', function (ev) {
        var detalhado = ev.shiftKey || ev.altKey;
        var presets = (window.coplanRequirePresets || {});
        var guard = window.coplanGuard || function (a, r, fn) { return Promise.resolve(fn()); };
        if (detalhado) {
          if (!api || !api.export_relatorio_criterios_projeto) {
            return toast('API indisponivel', 'error');
          }
          guard('Relatorio detalhado por projeto', presets.export_full, function () {
            toast('Gerando relatorio detalhado por projeto...', 'info');
            return api.export_relatorio_criterios_projeto(null).then(function (r) {
              if (!r) {
                toast('Sem resposta', 'error');
                if (window.coplanReportError) {
                  window.coplanReportError(
                    'Relatorio detalhado por projeto',
                    'export_relatorio_criterios_projeto',
                    { error: 'Sem resposta da API' });
                }
                return;
              }
              if (r.ok) {
                toast(r.count_projetos + ' projeto(s) / '
                      + r.count_alimentadores + ' alim em '
                      + r.path, 'info');
              } else {
                toast('Falhou: ' + (r.error || '?'), 'error');
                if (window.coplanReportError) {
                  window.coplanReportError(
                    'Relatorio detalhado por projeto',
                    'export_relatorio_criterios_projeto', r);
                }
              }
            }).catch(function (err) {
              toast('Falhou: ' + (err && err.message || err || '?'), 'error');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Relatorio detalhado por projeto',
                  'export_relatorio_criterios_projeto',
                  { error: String(err && err.message || err || '?') });
              }
            });
          });
          return;
        }
        if (!api || !api.export_relatorio_criterios) return toast('API indisponivel', 'error');
        // Visualizar Sprint 1 (Auditoria #5): pergunta escopo antes de
        // gerar (Todas / Filtradas / Selecionadas). Backend export_relatorio_criterios
        // aceita lista de cods opcional.
        var scopeFn = window.coplanPromptCriteriosScope
          || function () { return Promise.resolve('all'); };
        scopeFn().then(function (scope) {
          if (!scope) return; // cancelado
          var cods = null;
          if (scope === 'filtered') {
            cods = (typeof window.coplanFilteredCods === 'function')
              ? window.coplanFilteredCods() : null;
            if (cods === null) {
              // Sem filtros ativos: 'filtered' equivale a 'all'
              toast('Sem filtros ativos - gerando para todas as obras',
                    'info');
            } else if (!cods.length) {
              return toast('Nenhuma obra apos os filtros atuais', 'warn');
            }
          } else if (scope === 'selected') {
            cods = (typeof getSelectedCods === 'function')
              ? getSelectedCods() : [];
            if (!cods || !cods.length) {
              return toast('Nenhuma obra selecionada', 'warn');
            }
          }
          guard('Relatorio de criterios', presets.export_full, function () {
            toast('Gerando relatorio de criterios (' + scope + ')...', 'info');
            return api.export_relatorio_criterios(cods).then(function (r) {
              if (!r) {
                toast('Sem resposta', 'error');
                if (window.coplanReportError) {
                  window.coplanReportError(
                    'Relatorio de criterios',
                    'export_relatorio_criterios',
                    { error: 'Sem resposta da API' });
                }
                return;
              }
              if (r.ok && r.count) toast(r.count + ' falhas em ' + r.path, 'warn');
              else if (r.ok && !r.count) toast(r.error || 'Tudo atendeu', 'info');
              else {
                toast('Falhou: ' + (r.error || '?'), 'error');
                if (window.coplanReportError) {
                  window.coplanReportError(
                    'Relatorio de criterios',
                    'export_relatorio_criterios', r);
                }
              }
            }).catch(function (err) {
              toast('Falhou: ' + (err && err.message || err || '?'), 'error');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Relatorio de criterios',
                  'export_relatorio_criterios',
                  { error: String(err && err.message || err || '?') });
              }
            });
          });
        });
      });
    }

    // Nota de Colapso (stub)
    var btnNota = findToolbarBtn('Nota');
    if (btnNota) {
      btnNota.addEventListener('click', function () {
        if (!api || !api.export_nota_colapso) return toast('API indisponivel', 'error');
        var cods = getSelectedCods();
        var presets = (window.coplanRequirePresets || {});
        var guard = window.coplanGuard || function (a, r, fn) { return Promise.resolve(fn()); };
        guard('Nota de Colapso', presets.export_full, function () {
          return api.export_nota_colapso(cods).then(function (r) {
            if (r && r.ok) toast('Nota gerada: ' + r.path, 'info');
            else {
              toast(r && r.error || 'TODO', 'warn');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Nota de Colapso', 'export_nota_colapso', r);
              }
            }
          }).catch(function (err) {
            toast('Falhou: ' + (err && err.message || err || '?'), 'error');
            if (window.coplanReportError) {
              window.coplanReportError(
                'Nota de Colapso', 'export_nota_colapso',
                { error: String(err && err.message || err || '?') });
            }
          });
        });
      });
    }

    // Excluir
    var btnDel = findToolbarBtn('Excluir');
    if (btnDel) {
      btnDel.addEventListener('click', function () {
        if (!api || !api.delete_obras) return toast('API indisponivel', 'error');
        var cods = getSelectedCods();
        if (!cods.length) return toast('Selecione ao menos uma obra', 'warn');
        // [F13] Plano de Obras: filtra cods bloqueados (linha cinza)
        if (window.coplanPlanoCheck) {
          cods = window.coplanPlanoCheck(cods, 'Excluir');
          if (!cods.length) return;
        }
        // Gating aprovadas: replica _gate_aprovadas_for_action do desktop.
        // Antes de prosseguir, descobre quais obras estao aprovadas e exige
        // confirmacao excepcional + auditoria pra cada uma.
        var doDelete = function (cleanCods) {
          var msg = 'Excluir ' + cleanCods.length + ' obra(s)?\n\n'
                  + cleanCods.join(', ');
          if (!window.confirm(msg)) return;
          toast('Excluindo...', 'info');
          api.delete_obras(cleanCods).then(function (r) {
            if (r && r.ok) {
              toast(r.deleted + ' obra(s) excluida(s)', 'info');
              // Mesmo com ok=true, pode haver erros por linha
              if (window.coplanReportError && r && r.errors && r.errors.length) {
                window.coplanReportError(
                  'Excluir obras', 'delete_obras', r);
              }
            } else {
              toast('Erros: ' + ((r && r.errors || []).slice(0, 3).join('; ')),
                    'error');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Excluir obras', 'delete_obras', r);
              }
            }
            if (typeof window.coplanLoadObras === 'function') {
              window.coplanLoadObras();
            }
          }).catch(function (err) {
            toast('Falhou: ' + (err && err.message || err || '?'), 'error');
            if (window.coplanReportError) {
              window.coplanReportError(
                'Excluir obras', 'delete_obras',
                { error: String(err && err.message || err || '?') });
            }
          });
        };
        if (!api.gate_aprovadas_for_action) {
          // Sem gating disponivel, segue fluxo antigo.
          return doDelete(cods);
        }
        // [E11] Checkbox "Incluir aprovadas" controla include_aprovadas
        // do gate. Quando ON: aprovadas entram em targets normalmente
        // (sem prompt excepcional, sem gating); quando OFF: aprovadas
        // viram aviso e exigem confirmacao excepcional.
        var includeAprov = !!(document.getElementById(
          'coplan-chk-incluir-aprovadas') || {}).checked;
        api.gate_aprovadas_for_action(cods, includeAprov).then(function (g) {
          if (!g || !g.ok) {
            return toast('Falha ao validar aprovadas: '
                         + (g && g.error || '?'), 'error');
          }
          var aprov = g.aprovadas || [];
          // Se "Incluir aprovadas" estava ON, todas (aprov+nao) ja estao
          // em targets; deleta direto sem prompt excepcional.
          if (includeAprov || !aprov.length) {
            return doDelete(g.targets || cods);
          }
          // Tem aprovadas. Pergunta se quer prosseguir excepcionalmente.
          var aviso = aprov.length + ' obra(s) APROVADA(S) na selecao:\n'
                    + aprov.slice(0, 5).join(', ')
                    + (aprov.length > 5 ? ', ...' : '')
                    + '\n\nDeseja excluir apenas as '
                    + (g.targets.length || 0)
                    + ' nao aprovada(s)? (Cancelar = exclusao excepcional'
                    + ' das aprovadas com auditoria)';
          if (window.confirm(aviso)) {
            // Apenas as nao-aprovadas
            if (!g.targets || !g.targets.length) {
              return toast('Nenhuma obra nao-aprovada na selecao', 'warn');
            }
            return doDelete(g.targets);
          }
          // Exclusao excepcional: exige digitar "EXCLUIR" + motivo
          var typed = window.prompt(
            'EXCLUSAO EXCEPCIONAL.\nDigite EXCLUIR para confirmar:', '');
          if (!typed || typed.trim().toUpperCase() !== 'EXCLUIR') {
            return toast('Cancelado: confirmacao invalida', 'warn');
          }
          var motivo = window.prompt(
            'Motivo da exclusao excepcional (obrigatorio):', '');
          if (!motivo || !motivo.trim()) {
            return toast('Cancelado: motivo obrigatorio', 'warn');
          }
          // Registra auditoria pra cada aprovada antes de deletar
          var promises = aprov.map(function (cod) {
            return api.register_exclusao_excepcional
              ? api.register_exclusao_excepcional(cod, motivo.trim())
              : Promise.resolve(null);
          });
          Promise.all(promises).then(function () {
            // Deleta TODAS as cods originais (incluindo aprovadas)
            doDelete(cods);
          });
        });
      });
    }

    // Botao "Correcao" (toolbar) removido a pedido do usuario.
    // Funcao continua disponivel via menu contextual de linha
    // (right-click -> "Marcar Correcao") em showRowContextMenu.
    // Botao "Atualizar Snapshot" para os selecionados (Pass 3 da auditoria).
    // Replica atualizar_snapshot_tecnico_selecionados do desktop:
    // limpa tecnico_dirty + grava token + timestamp/src para cada cod.
    if (!bar.querySelector('#coplan-btn-snap-tecnico')) {
      var btnSnap = document.createElement('button');
      btnSnap.id = 'coplan-btn-snap-tecnico';
      btnSnap.className = 'btn';
      btnSnap.innerHTML = '<i data-lucide="refresh-cw"></i> Snapshot Tec.';
      btnSnap.title = ('Atualiza snapshot tecnico das obras selecionadas '
                     + '(limpa tecnico_dirty + grava token novo dos 3 .TXT).');
      bar.appendChild(btnSnap);
      btnSnap.addEventListener('click', function () {
        if (!api || !api.tecnico_snapshot_update) {
          return toast('API indisponivel', 'error');
        }
        var cods = getSelectedCods();
        if (!cods.length) {
          return toast('Selecione ao menos uma obra', 'warn');
        }
        // [F13] Plano de Obras: filtra cods bloqueados (linha cinza)
        if (window.coplanPlanoCheck) {
          cods = window.coplanPlanoCheck(cods, 'Snapshot tecnico');
          if (!cods.length) return;
        }
        var presets = (window.coplanRequirePresets || {});
        var guard = window.coplanGuard
          || function (a, r, fn) { return Promise.resolve(fn()); };
        guard('Atualizar snapshot tecnico',
              presets.db_ganhos_tecnico || presets.export_full,
              function () {
          toast('Atualizando snapshot tecnico de ' + cods.length
                + ' obra(s)...', 'info');
          return api.tecnico_snapshot_update(cods).then(function (r) {
            if (!(r && r.ok)) {
              return toast('Falhou: ' + (r && r.error || '?'), 'error');
            }
            toast(r.atualizadas + ' obra(s) com snapshot atualizado', 'info');
            if (typeof window.coplanLoadObras === 'function') {
              window.coplanLoadObras();
            }
            if (typeof window.coplanRefreshChips === 'function') {
              window.coplanRefreshChips();
            }
          });
        });
      });
    }
    // [E5] Botao "Salvar BD" -- copia o banco corrente para outro arquivo
    // (backup manual). Equivalente a salvar_banco_dados do desktop.
    if (!bar.querySelector('#coplan-btn-save-bd')) {
      var btnSaveBd = document.createElement('button');
      btnSaveBd.id = 'coplan-btn-save-bd';
      btnSaveBd.className = 'btn';
      btnSaveBd.innerHTML = '<i data-lucide="save"></i> Salvar BD';
      btnSaveBd.title = ('Salva uma copia do banco corrente em outro '
                       + 'caminho (backup manual com nome escolhido).');
      bar.appendChild(btnSaveBd);
      btnSaveBd.addEventListener('click', function () {
        if (!api || !api.db_save_as) return toast('API indisponivel', 'error');
        var presets = (window.coplanRequirePresets || {});
        var guard = window.coplanGuard
          || function (a, r, fn) { return Promise.resolve(fn()); };
        guard('Salvar BD', presets.db_only, function () {
          toast('Abrindo file dialog...', 'info');
          return api.db_save_as('').then(function (r) {
            if (!r) return toast('Sem resposta', 'error');
            if (r.ok) {
              toast('Banco salvo: ' + r.path, 'info');
              if (api.open_path_in_os) {
                if (window.confirm('Abrir pasta do banco salvo?')) {
                  api.open_path_in_os(r.path);
                }
              }
            } else if (r.error !== 'cancelado') {
              toast('Falha: ' + (r.error || '?'), 'error');
            }
          });
        });
      });
    }

    // [E6] Botao "Exportar p/ Banco" -- exporta obras (selecionadas ou
    // visiveis) para um banco .db destino. Equivalente a
    // exportar_para_banco do desktop, com gating de aprovadas.
    if (!bar.querySelector('#coplan-btn-export-bd')) {
      var btnExpBd = document.createElement('button');
      btnExpBd.id = 'coplan-btn-export-bd';
      btnExpBd.className = 'btn';
      btnExpBd.innerHTML = '<i data-lucide="database"></i> Exportar BD';
      btnExpBd.title = ('Exporta as obras selecionadas (ou todas as '
                      + 'visiveis) para outro banco .db. Gating aprovadas '
                      + 'depende do checkbox "Incluir aprovadas".');
      bar.appendChild(btnExpBd);
      btnExpBd.addEventListener('click', function () {
        if (!api || !api.db_export_to) return toast('API indisponivel', 'error');
        var cods = getSelectedCods();
        if (!cods.length) {
          // Sem selecao explicita: usa todos os cods visiveis (filtrados)
          var rawRows = window.coplanObrasRaw || [];
          var cols = window.coplanObrasColumns || [];
          var iCod = cols.indexOf('cod');
          if (iCod < 0) return toast('Coluna cod indisponivel', 'error');
          cods = rawRows.map(function (r) {
            return String(r[iCod] || '').trim();
          }).filter(function (c) { return !!c; });
          if (!cods.length) {
            return toast('Nenhuma obra para exportar', 'warn');
          }
          if (!window.confirm('Nenhuma obra selecionada. Exportar TODAS '
                              + 'as ' + cods.length
                              + ' obras visiveis?')) {
            return;
          }
        }
        // [F13] Plano de Obras: filtra cods bloqueados
        if (window.coplanPlanoCheck) {
          cods = window.coplanPlanoCheck(cods, 'Exportar p/ Banco');
          if (!cods.length) return;
        }
        var includeAprov = !!(document.getElementById(
          'coplan-chk-incluir-aprovadas') || {}).checked;
        var presets = (window.coplanRequirePresets || {});
        var guard = window.coplanGuard
          || function (a, r, fn) { return Promise.resolve(fn()); };
        guard('Exportar p/ Banco', presets.db_only, function () {
          toast('Exportando ' + cods.length + ' obra(s)...', 'info');
          return api.db_export_to(cods, '', includeAprov).then(function (r) {
            if (!r) return toast('Sem resposta', 'error');
            if (r.ok) {
              var partes = [r.exported + ' exportada(s)'];
              if (r.ignoradas_aprovadas) {
                partes.push(r.ignoradas_aprovadas + ' aprovada(s) ignorada(s)');
              }
              if (r.errors && r.errors.length) {
                partes.push(r.errors.length + ' erro(s)');
              }
              var lvl = (r.errors && r.errors.length) ? 'warn' : 'info';
              toast(partes.join(' / ') + ' -> ' + r.path, lvl);
              if (api.open_path_in_os
                  && window.confirm('Abrir pasta do banco exportado?')) {
                api.open_path_in_os(r.path);
              }
            } else {
              var errs = (r.errors || []).slice(0, 3).join('; ')
                       || r.error || '?';
              toast('Falhou: ' + errs, 'error');
            }
          });
        });
      });
    }

    // [E11] Checkbox "Incluir aprovadas" persistente.
    // Replica chk_incluir_aprovadas do footer desktop. Estado persistido
    // em localStorage (chave 'coplan.incluir_aprovadas'). Lido pelos
    // handlers de Excluir/Exportar BD/etc para passar include_aprovadas.
    if (!bar.querySelector('#coplan-chk-incluir-aprovadas-wrap')) {
      var wrap = document.createElement('label');
      wrap.id = 'coplan-chk-incluir-aprovadas-wrap';
      wrap.style.cssText = ('display:inline-flex;align-items:center;gap:6px;'
                          + 'padding:0 10px;font-size:12.5px;cursor:pointer;'
                          + 'color:var(--text-soft)');
      wrap.title = ('Quando marcado, acoes destrutivas (Excluir, '
                  + 'Exportar BD) consideram tambem obras APROVADAS. '
                  + 'Quando desmarcado, sao ignoradas com aviso.');
      var chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.id = 'coplan-chk-incluir-aprovadas';
      try {
        chk.checked = (localStorage.getItem('coplan.incluir_aprovadas')
                       === '1');
      } catch (e) { chk.checked = false; }
      chk.addEventListener('change', function () {
        try {
          localStorage.setItem('coplan.incluir_aprovadas',
                               chk.checked ? '1' : '0');
        } catch (e) {}
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(chk.checked
            ? 'Incluir aprovadas: ATIVO'
            : 'Incluir aprovadas: desativado',
            chk.checked ? 'warn' : 'info');
        }
      });
      wrap.appendChild(chk);
      var span = document.createElement('span');
      span.textContent = 'Incluir aprovadas';
      wrap.appendChild(span);
      bar.appendChild(wrap);
    }
    if (!bar.querySelector('#coplan-btn-copiar')) {
      var btnCop = document.createElement('button');
      btnCop.id = 'coplan-btn-copiar';
      btnCop.className = 'btn';
      btnCop.innerHTML = '<i data-lucide="clipboard"></i> Copiar';
      btnCop.title = 'Copia COD selecionados para o clipboard';
      bar.appendChild(btnCop);
      btnCop.addEventListener('click', function () {
        var cods = getSelectedCods();
        if (!cods.length) return toast('Selecione ao menos uma obra', 'warn');
        var txt = cods.join('\n');
        var ok = false;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(txt).then(function () {
              toast(cods.length + ' COD copiado(s)', 'info');
            }, function () {
              if (fallbackCopy(txt)) {
                toast(cods.length + ' COD copiado(s)', 'info');
              } else {
                toast('Falha ao copiar', 'error');
              }
            });
            return;
          }
          ok = fallbackCopy(txt);
        } catch (e) {
          ok = fallbackCopy(txt);
        }
        if (ok) toast(cods.length + ' COD copiado(s)', 'info');
        else toast('Falha ao copiar', 'error');
      });
    }
    function fallbackCopy(txt) {
      try {
        var ta = document.createElement('textarea');
        ta.value = txt;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        return ok;
      } catch (e) {
        return false;
      }
    }

    // Fase D: botao "Verificar Criterios" -- chama criterios_verificar_v2
    // (regra moderna: cor unica por projeto). Se ha selecao, atua sobre
    // ela; senao, sobre tudo. Persiste status via criterios_persistir_status.
    if (!bar.querySelector('#coplan-btn-verifica-crit')) {
      var btnVer = document.createElement('button');
      btnVer.id = 'coplan-btn-verifica-crit';
      btnVer.className = 'btn';
      btnVer.innerHTML = '<i data-lucide="check-square"></i> Verificar Criterios';
      btnVer.title = ('Verifica criterios V2 (cor unica por projeto). '
                    + 'Shift+click: tambem persiste o status na tabela.');
      bar.appendChild(btnVer);
      btnVer.addEventListener('click', function (ev) {
        if (!api || !api.criterios_verificar_v2) {
          return toast('API indisponivel', 'error');
        }
        var cods = getSelectedCods();
        var label = cods.length ? (cods.length + ' obras') : 'todas as obras';
        var persist = ev.shiftKey || ev.altKey;
        var presets = (window.coplanRequirePresets || {});
        var guard = window.coplanGuard || function (a, r, fn) { return Promise.resolve(fn()); };
        guard('Verificar criterios V2', presets.export_full, function () {
        toast('Verificando criterios em ' + label + '...', 'info');
        return api.criterios_verificar_v2(cods).then(function (r) {
          if (!(r && r.ok)) {
            return toast('Falha: ' + (r && r.error || '?'), 'error');
          }
          var atende = 0, nao = 0, indef = 0;
          (r.results || []).forEach(function (it) {
            if (it.atende === true) atende++;
            else if (it.atende === false) nao++;
            else indef++;
          });
          var msg = atende + ' atende / ' + nao + ' NAO atende'
                  + (indef ? ' / ' + indef + ' indefinido' : '');
          var lvl = (nao > 0) ? 'warn' : 'info';
          toast(msg, lvl);
          if (persist && api.criterios_persistir_status) {
            toast('Persistindo status...', 'info');
            api.criterios_persistir_status(cods).then(function (rp) {
              if (rp && rp.ok) {
                toast(rp.atualizadas + ' status atualizado(s)', 'info');
                if (window.coplanLoadObras) window.coplanLoadObras();
              } else {
                toast('Falha persist: ' + (rp && rp.error || '?'), 'error');
              }
            });
          }
        });
        });  // close guard wrapper
      });
    }

    // Botao "Verificar V1" removido a pedido do usuario (algoritmo legado).
    // Use "Verificar Criterios" (V2) para o padrao atual: cor unica por
    // projeto + persistencia opcional via Shift+click.

    // ---- Atualizar Plano de Obras (equivalente PlanoObrasDialog desktop) ----
    // Modal com Pacote + Data Inicial + Data Final. Aplica destacamento
    // visual nas linhas baseado em data_modificacao:
    //   - mod < data_inicial: nao destaca
    //   - data_inicial <= mod < data_final: cinza claro
    //   - mod >= data_final: verde claro
    if (!bar.querySelector('#coplan-btn-plano-obras')) {
      var btnPlano = document.createElement('button');
      btnPlano.id = 'coplan-btn-plano-obras';
      btnPlano.className = 'btn';
      btnPlano.innerHTML = '<i data-lucide="calendar-check"></i> Plano Obras';
      btnPlano.title = ('Atualizar plano de obras: marca obras visualmente '
                      + 'baseado em data_modificacao (cinza/verde).');
      bar.appendChild(btnPlano);
      btnPlano.addEventListener('click', function () {
        openPlanoObrasModal();
      });
    }
    if (window.lucide) lucide.createIcons();

    function parseDataMod(s) {
      // data_modificacao do banco vem em formato "dd/MM/yy HH:mm".
      // Retorna timestamp ms ou null. Sem regex pra evitar escape do
      // Python triple-string -- parse manual.
      if (!s) return null;
      var t = String(s).trim();
      // Tenta primeiro split "dd/MM/yy HH:mm"
      var sp1 = t.split(' ');
      if (sp1.length === 2) {
        var d_parts = sp1[0].split('/');
        var h_parts = sp1[1].split(':');
        if (d_parts.length === 3 && h_parts.length >= 2) {
          var dd = parseInt(d_parts[0], 10);
          var mm = parseInt(d_parts[1], 10) - 1;
          var yy = parseInt(d_parts[2], 10);
          var hh = parseInt(h_parts[0], 10);
          var mi = parseInt(h_parts[1], 10);
          if (!isNaN(dd) && !isNaN(mm) && !isNaN(yy)
              && !isNaN(hh) && !isNaN(mi)) {
            if (yy < 100) yy += 2000;
            var d2 = new Date(yy, mm, dd, hh, mi);
            if (!isNaN(d2.getTime())) return d2.getTime();
          }
        }
      }
      // Fallback ISO
      var d = new Date(t);
      return isNaN(d.getTime()) ? null : d.getTime();
    }
    function localISOForInput(d) {
      // Retorna 'YYYY-MM-DDTHH:MM' (input datetime-local)
      var pad = function (n) { return String(n).padStart(2, '0'); };
      return d.getFullYear() + '-'
        + pad(d.getMonth()+1) + '-' + pad(d.getDate())
        + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    }
    function applyHighlight(pacoteFiltro, tIni, tFim) {
      // Itera linhas do tbody e aplica cores. Usa raw_rows + columns
      // pra encontrar tipo_pacote + data_modificacao.
      var cols = window.coplanObrasColumns || [];
      var raw = window.coplanObrasRaw || [];
      var iPac = cols.indexOf('tipo_pacote');
      var iMod = cols.indexOf('data_modificacao');
      var iCod = cols.indexOf('cod');
      if (iCod < 0) {
        toast('coluna cod nao disponivel', 'error');
        return 0;
      }
      // Mapa cod -> linha bruta
      var byCod = {};
      raw.forEach(function (r) {
        var c = String(r[iCod] || '').trim();
        if (c) byCod[c] = r;
      });
      var tbody = document.getElementById('obras-tbody');
      if (!tbody) return 0;
      var trs = tbody.querySelectorAll('tr[data-cod]');
      var cinza = 0, verde = 0, normal = 0;
      var blockedCods = [];  // [F13] cods cinza = janela bloqueada
      var pacFilterUpper = String(pacoteFiltro || '').trim().toUpperCase();
      trs.forEach(function (tr) {
        var cod = tr.getAttribute('data-cod');
        var row = byCod[cod];
        // Limpa estilo previo
        tr.style.background = '';
        tr.classList.remove('plano-cinza', 'plano-verde');
        if (!row) return;
        if (pacFilterUpper) {
          var pac = String(iPac >= 0 ? row[iPac] : '').trim().toUpperCase();
          if (pac !== pacFilterUpper) {
            tr.style.opacity = '0.4';
            return;
          }
        }
        tr.style.opacity = '';
        var mod = parseDataMod(iMod >= 0 ? row[iMod] : '');
        if (mod === null) return;
        if (mod < tIni) {
          // nao destaca
          normal++;
        } else if (mod < tFim) {
          tr.style.background = 'rgba(148, 163, 184, .25)';  // cinza
          tr.classList.add('plano-cinza');
          cinza++;
          blockedCods.push(cod);  // [F13] bloqueada para acoes
        } else {
          tr.style.background = 'rgba(34, 197, 94, .20)';  // verde
          tr.classList.add('plano-verde');
          verde++;
        }
      });
      // [F13] Persiste lista de cods bloqueados em __coplanPlanoActive
      // para coplanPlanoBlocks(cod) consultar antes de cada acao.
      if (window.__coplanPlanoActive) {
        window.__coplanPlanoActive.blocked_cods = blockedCods;
      }
      return {cinza: cinza, verde: verde, normal: normal,
              blocked_cods: blockedCods};
    }
    function clearHighlight() {
      var tbody = document.getElementById('obras-tbody');
      if (!tbody) return;
      tbody.querySelectorAll('tr[data-cod]').forEach(function (tr) {
        tr.style.background = '';
        tr.style.opacity = '';
        tr.classList.remove('plano-cinza', 'plano-verde');
      });
      // [F13] Limpa lista de bloqueados ao remover highlight
      if (window.__coplanPlanoActive) {
        window.__coplanPlanoActive.blocked_cods = [];
      }
    }

    function openPlanoObrasModal() {
      // Carrega lista de pacotes via API. Pegamos `api` fresco aqui --
      // quando o botao foi montado em bindToolbar(), window.pywebview.api
      // podia ainda nao estar exposto, e o closure travaria undefined.
      var apiNow = window.pywebview && window.pywebview.api;
      var pacotesP = (apiNow && apiNow.get_pacotes)
        ? apiNow.get_pacotes()
        : Promise.resolve({ok: true, items: []});
      pacotesP.then(function (rp) {
        var pacotes = (rp && rp.ok && rp.items) || [];
        if (!pacotes.length) {
          // Fallback local: pelo menos os defaults conhecidos do core
          pacotes = ['Confiabilidade', 'Interligação UDE',
            'Interligação de UDE', 'Mercado', 'Orçamento de Conexão',
            'PLPT', 'Solicitação Regional'];
        }
        var modal = document.createElement('div');
        modal.id = 'coplan-plano-modal';
        modal.style.cssText = (
          'position:fixed;inset:0;background:rgba(0,0,0,.5);'
          + 'z-index:100000;display:flex;align-items:center;'
          + 'justify-content:center;padding:24px;'
        );
        modal.addEventListener('click', function (e) {
          if (e.target === modal) document.body.removeChild(modal);
        });
        // Defaults: data_inicial = agora, data_final = agora
        var now = new Date();
        var defStr = localISOForInput(now);
        var pacOpts = '<option value="">— qualquer pacote —</option>'
          + pacotes.map(function (p) {
              return '<option value="' + p + '">' + p + '</option>';
            }).join('');
        var box = document.createElement('div');
        box.style.cssText = (
          'background:var(--surface,#fff);'
          + 'border-radius:8px;padding:20px;'
          + 'max-width:520px;width:100%;'
          + 'display:flex;flex-direction:column;gap:12px;'
          + 'box-shadow:0 10px 40px rgba(0,0,0,.3);'
        );
        box.innerHTML =
          '<div style="display:flex;align-items:center;gap:8px;">'
        +   '<i data-lucide="calendar-check"></i>'
        +   '<strong>Atualizar Plano de Obras</strong>'
        +   '<button id="coplan-plano-close" class="btn"'
        +          ' style="margin-left:auto;">Fechar</button>'
        + '</div>'
        + '<div class="field">'
        +   '<label style="font-size:12px;">Pacote</label>'
        +   '<select id="coplan-plano-pacote" class="select">' + pacOpts + '</select>'
        + '</div>'
        + '<div class="field">'
        +   '<label style="font-size:12px;">Data/Hora Inicial</label>'
        +   '<input id="coplan-plano-ini" type="datetime-local" '
        +          'class="input mono" value="' + defStr + '"/>'
        + '</div>'
        + '<div class="field">'
        +   '<label style="font-size:12px;">Data/Hora Final</label>'
        +   '<input id="coplan-plano-fim" type="datetime-local" '
        +          'class="input mono" value="' + defStr + '"/>'
        + '</div>'
        + '<div style="font-size:11px;color:var(--text-soft);'
        +      'background:var(--surface-2,#f1f5f9);padding:8px 12px;'
        +      'border-radius:6px;line-height:1.5;">'
        +   '<strong>Como funciona:</strong><br>'
        +   '• Obras com <em>data_modificacao</em> antes da Data Inicial '
        +     'nao sao destacadas.<br>'
        +   '• Entre Data Inicial e Final: <span style="background:rgba(148,163,184,.4);'
        +     'padding:1px 4px;border-radius:3px;">cinza</span>.<br>'
        +   '• Apos Data Final: <span style="background:rgba(34,197,94,.4);'
        +     'padding:1px 4px;border-radius:3px;">verde</span>.<br>'
        +   '• Pacote em branco = todos.'
        + '</div>'
        + '<div class="row" style="display:flex;justify-content:flex-end;gap:6px;">'
        +   '<button id="coplan-plano-clear" class="btn">'
        +     '<i data-lucide="x"></i> Cancelar destaque</button>'
        +   '<button id="coplan-plano-apply" class="btn primary">'
        +     '<i data-lucide="check"></i> Aplicar</button>'
        + '</div>';
        modal.appendChild(box);
        document.body.appendChild(modal);
        if (window.lucide) lucide.createIcons();
        var byId = function (i) { return document.getElementById(i); };
        byId('coplan-plano-close').onclick = function () {
          document.body.removeChild(modal);
        };
        byId('coplan-plano-clear').onclick = function () {
          clearHighlight();
          toast('Destaque removido', 'info');
        };
        byId('coplan-plano-apply').onclick = function () {
          var pac = byId('coplan-plano-pacote').value;
          var ini = byId('coplan-plano-ini').value;
          var fim = byId('coplan-plano-fim').value;
          if (!ini || !fim) {
            return toast('Informe as duas datas', 'warn');
          }
          var tIni = new Date(ini).getTime();
          var tFim = new Date(fim).getTime();
          if (isNaN(tIni) || isNaN(tFim)) {
            return toast('Datas invalidas', 'error');
          }
          if (tFim < tIni) {
            return toast('Data Final < Data Inicial', 'warn');
          }
          // Gate por estado de fonte: plano de obras precisa de banco
          // conectado (le data_modificacao + tipo_pacote da tabela obras).
          var presets = (window.coplanRequirePresets || {});
          var guard = window.coplanGuard
            || function (a, r, fn) { return Promise.resolve(fn()); };
          guard('Atualizar Plano de Obras', presets.db_only, function () {
            // [F13] Pre-cria __coplanPlanoActive vazio antes de
            // applyHighlight para que o registro de blocked_cods
            // funcione (applyHighlight grava em
            // window.__coplanPlanoActive.blocked_cods).
            window.__coplanPlanoActive = {
              pacote: pac, tIni: tIni, tFim: tFim,
              blocked_cods: [],
            };
            var R = applyHighlight(pac, tIni, tFim);
            if (R) {
              toast('Plano aplicado: ' + R.cinza + ' cinza / '
                    + R.verde + ' verde'
                    + (R.cinza ? ' (acoes bloqueadas em '
                                + R.cinza + ' obras)' : ''), 'info');
              window.__coplanPlanoActive.R = R;
              // Mostra botao de cancelar persistente
              var btnCancel = document.getElementById(
                'coplan-btn-plano-cancel');
              if (btnCancel) btnCancel.style.display = '';
            }
            document.body.removeChild(modal);
            return null;
          });
        };
      });
    }
    // Botao "Cancelar Plano" persistente: aparece somente apos Aplicar
    // e limpa o highlight em qualquer momento (vs ter que reabrir o modal).
    if (!bar.querySelector('#coplan-btn-plano-cancel')) {
      var btnPlanoCancel = document.createElement('button');
      btnPlanoCancel.id = 'coplan-btn-plano-cancel';
      btnPlanoCancel.className = 'btn';
      btnPlanoCancel.innerHTML = '<i data-lucide="x-circle"></i> Cancelar Plano';
      btnPlanoCancel.title = ('Limpa o destaque cinza/verde aplicado pelo'
                            + ' "Plano Obras". Equivalente a'
                            + ' cancelar_atualizacao_plano_obras do desktop.');
      btnPlanoCancel.style.display = 'none';
      bar.appendChild(btnPlanoCancel);
      btnPlanoCancel.addEventListener('click', function () {
        clearHighlight();
        window.__coplanPlanoActive = null;
        btnPlanoCancel.style.display = 'none';
        toast('Plano cancelado', 'info');
      });
    }

    if (window.lucide) lucide.createIcons();
    // Diagnostico: log no console pra confirmar injecao
    try {
      console.log('[coplan] toolbar Visualizar bound; botoes:',
        Array.from(bar.querySelectorAll('.btn')).map(function (b) {
          var t = String(b.textContent || '').replace(new RegExp("[ \t\n\r]+", "g"), ' ').trim();
          return t.substring(0, 30);
        }));
    } catch (e) {}

    return true;
  }

  // Visualizar Sprint 1 (Auditoria #3): re-aplica highlight do Plano
  // de Obras quando a tabela e' re-renderizada. Chamado por
  // coplanRenderObras no fim do render. Idempotente (skip se nao ha
  // estado ativo).
  window.coplanReplayPlanoState = function () {
    var a = window.__coplanPlanoActive;
    if (!a || !a.pacote) return;
    if (typeof applyHighlight !== 'function') return;
    try {
      var R = applyHighlight(a.pacote, a.tIni, a.tFim);
      if (R) a.R = R;
    } catch (_e) { /* swallow */ }
  };

  // [F13] Helpers globais para outros handlers consultarem blocked_cods
  // antes de operar (delete/correcao/snapshot/atualizar valor/etc).
  // Replica plano_update_active + blocked_rows do desktop.
  window.coplanPlanoBlocks = function (cod) {
    var a = window.__coplanPlanoActive;
    if (!a || !a.blocked_cods || !a.blocked_cods.length) return false;
    return a.blocked_cods.indexOf(String(cod || '')) >= 0;
  };
  window.coplanPlanoFilterCods = function (cods) {
    // Recebe lista de cods, devolve {permitidos, bloqueados}.
    // Caller decide se aborta, ignora ou pergunta.
    var a = window.__coplanPlanoActive;
    if (!a || !a.blocked_cods || !a.blocked_cods.length) {
      return { permitidos: cods.slice(), bloqueados: [] };
    }
    var bs = new Set(a.blocked_cods);
    var permitidos = [];
    var bloqueados = [];
    cods.forEach(function (c) {
      if (bs.has(String(c))) bloqueados.push(c);
      else permitidos.push(c);
    });
    return { permitidos: permitidos, bloqueados: bloqueados };
  };
  // Wrapper opcional: alerta + filtra. Retorna lista de cods permitidos
  // (vazia = aborte). Mostra confirm se houver bloqueadas.
  window.coplanPlanoCheck = function (cods, acao) {
    var f = window.coplanPlanoFilterCods(cods);
    if (!f.bloqueados.length) return f.permitidos;
    var ok = window.confirm(
      f.bloqueados.length + ' obra(s) estao na janela do '
      + 'Plano de Obras (cinza) e ficarao FORA desta acao "'
      + (acao || '?') + '".\n\nContinuar com '
      + f.permitidos.length + ' obra(s) permitida(s)?');
    if (!ok) return [];
    if (typeof window.coplanToast === 'function' && f.bloqueados.length) {
      window.coplanToast(f.bloqueados.length
        + ' obra(s) ignorada(s) (Plano de Obras bloqueia)', 'warn');
    }
    return f.permitidos;
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindToolbar);
  } else {
    if (!bindToolbar()) setTimeout(bindToolbar, 50);
  }
  // Re-bind sempre que entrar na aba Visualizar OU quando a tabela for
  // re-renderizada (garante que botoes injetados nao se percam).
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'visualizar') {
      setTimeout(bindToolbar, 50);
    }
  });
  document.addEventListener('coplan:obras', function () {
    setTimeout(bindToolbar, 50);
  });
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 3.7 (Visualizar / paginacao real) ----
  // Equivalente JS de visualizar_pagination.paginate_visualizar_rows:
  // mantem coplanObras como a lista filtrada COMPLETA e fatia em paginas
  // antes de renderizar. Default 300 itens (mesma constante do desktop em
  // codigo5_coplan: self._visualizar_page_size = 300).
  window.coplanPage = 1;
  window.coplanPageSize = 300;
  window.__coplanFullCount = 0;

  function clamp(n, lo, hi) {
    return Math.max(lo, Math.min(hi, n));
  }
  function getPaginationBox() {
    return document.querySelector('#tab-visualizar .pagination');
  }
  function updatePaginationUI(page, totalPages, totalItems) {
    var box = getPaginationBox();
    if (!box) return;
    var label = box.querySelector('.page-btns .mono');
    if (label) {
      // [D2/D6] Usa format_pagination_label da API (formato compartilhado
      // com desktop: "Página X/Y • N resultado(s)"). Fallback para versao
      // simples se API indisponivel ou erro.
      var fallback = page + ' / ' + totalPages
                   + (totalItems ? ' (' + totalItems + ')' : '');
      var a = window.pywebview && window.pywebview.api;
      if (a && a.format_pagination_label) {
        a.format_pagination_label(page, totalPages, totalItems)
          .then(function (r) {
            if (r && r.ok) label.textContent = r.label;
            else label.textContent = fallback;
          }).catch(function () { label.textContent = fallback; });
      } else {
        label.textContent = fallback;
      }
    }
    var btns = box.querySelectorAll('.page-btns .btn');
    if (btns.length >= 2) {
      btns[0].disabled = (page <= 1);
      btns[1].disabled = (page >= totalPages);
      btns[0].style.opacity = btns[0].disabled ? '0.4' : '';
      btns[1].style.opacity = btns[1].disabled ? '0.4' : '';
    }
    // Atualiza tambem o badge "X resultados · Y selecionadas" para usar
    // o total filtrado, nao apenas a pagina atual.
    var badge = document.querySelector('#tab-visualizar .table-header .badge');
    if (badge) {
      var sel = document.querySelectorAll(
        '#obras-tbody input[type="checkbox"]:checked'
      ).length;
      badge.textContent = totalItems + ' resultados · ' + sel + ' selecionadas';
    }
    if (typeof window.coplanSetSelectionCount === 'function') {
      var selAll = document.querySelectorAll(
        '#obras-tbody input[type="checkbox"]:checked'
      ).length;
      window.coplanSetSelectionCount(selAll, totalItems);
    }
  }

  // Wraps coplanRenderObras para fatiar em paginas antes de renderizar.
  // Fatia tambem os arrays paralelos (raw_rows, passou_per_row) para
  // que o renderer fiel mostre apenas a pagina atual com TODAS as
  // colunas do banco.
  if (typeof window.coplanRenderObras === 'function') {
    var __origRender = window.coplanRenderObras;
    window.coplanRenderObras = function () {
      var full = window.coplanObras || [];
      var fullRaw = window.coplanObrasRaw || [];
      var fullPassou = window.coplanObrasPassou || [];
      // Total de itens = comprimento maximo entre os tres arrays
      // (em caso de inconsistencia nunca crashar).
      var totalCount = Math.max(full.length, fullRaw.length, fullPassou.length);
      window.__coplanFullCount = totalCount;
      var size = Math.max(1, parseInt(window.coplanPageSize, 10) || 300);
      var totalPages = Math.max(1, Math.ceil(totalCount / size));
      window.coplanPage = clamp(window.coplanPage || 1, 1, totalPages);
      var start = (window.coplanPage - 1) * size;
      var end = start + size;
      // Troca temporaria de TODOS os arrays paralelos.
      var saved = full, savedRaw = fullRaw, savedPassou = fullPassou;
      window.coplanObras = full.slice(start, end);
      window.coplanObrasRaw = fullRaw.slice(start, end);
      window.coplanObrasPassou = fullPassou.slice(start, end);
      try { __origRender(); }
      finally {
        window.coplanObras = saved;
        window.coplanObrasRaw = savedRaw;
        window.coplanObrasPassou = savedPassou;
      }
      updatePaginationUI(window.coplanPage, totalPages, totalCount);
    };
  }

  // Reset de pagina sempre que a lista filtrada muda (search/refresh).
  // coplan:obras dispara DENTRO do render original, ja com slice; usamos
  // um wrapper em coplanLoadObras/applySearch para resetar antes do load.
  function resetToFirstPage() { window.coplanPage = 1; }
  if (typeof window.coplanLoadObras === 'function') {
    var __origLoad = window.coplanLoadObras;
    window.coplanLoadObras = function () {
      resetToFirstPage();
      return __origLoad.apply(this, arguments);
    };
  }
  if (typeof window.coplanApplySearch === 'function') {
    var __origApply = window.coplanApplySearch;
    window.coplanApplySearch = function () {
      resetToFirstPage();
      return __origApply.apply(this, arguments);
    };
  }

  function bindPagination() {
    var box = getPaginationBox();
    if (!box) return false;
    var sel = box.querySelector('.page-btns select');
    if (sel) {
      // Sincroniza state inicial com o select (mock vem com 300 selected).
      var v = parseInt(sel.value, 10);
      if (v > 0) window.coplanPageSize = v;
      sel.addEventListener('change', function () {
        var n = parseInt(sel.value, 10);
        if (n > 0) {
          window.coplanPageSize = n;
          window.coplanPage = 1;
          if (typeof window.coplanRenderObras === 'function') {
            window.coplanRenderObras();
          }
        }
      });
    }
    var btns = box.querySelectorAll('.page-btns .btn');
    if (btns.length >= 2) {
      btns[0].addEventListener('click', function () {
        if (window.coplanPage > 1) {
          window.coplanPage--;
          if (typeof window.coplanRenderObras === 'function') {
            window.coplanRenderObras();
          }
        }
      });
      btns[1].addEventListener('click', function () {
        var size = window.coplanPageSize || 300;
        var total = (window.coplanObras || []).length;
        var maxP = Math.max(1, Math.ceil(total / size));
        if (window.coplanPage < maxP) {
          window.coplanPage++;
          if (typeof window.coplanRenderObras === 'function') {
            window.coplanRenderObras();
          }
        }
      });
    }
    // PageUp/PageDown navegam paginas quando aba Visualizar esta ativa.
    document.addEventListener('keydown', function (e) {
      var visTab = document.getElementById('tab-visualizar');
      if (!visTab || !visTab.classList.contains('active')) return;
      if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
      if (e.key === 'PageDown' && btns[1] && !btns[1].disabled) {
        e.preventDefault(); btns[1].click();
      } else if (e.key === 'PageUp' && btns[0] && !btns[0].disabled) {
        e.preventDefault(); btns[0].click();
      }
    });
    return true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindPagination);
  } else {
    if (!bindPagination()) setTimeout(bindPagination, 50);
  }
})();
</script>
