<script>
// =====================================================================
// LEVA 4 - Atualizar Projeto (navbar) — M090, M091, M092.
//   M090 -> state machine no JS (coplanCadastroProjeto): start, next,
//           prev, cancelar, finalizar. Carrega lote via projeto_iniciar
//           e salva via projeto_finalizar.
//   M091 -> bind dos 4 botoes da navbar (#cad-projeto-nav-prev/next/
//           cancelar/finalizar) + listener custom event externo
//           coplan:atualizar-projeto-start.
//   M092 -> reuso do motivo entre obras: primeiro motivo digitado pelo
//           user em qualquer obra do lote eh propagado para todas as
//           seguintes via projeto_finalizar(payloads, motivo).
// =====================================================================
(function () {
  'use strict';
  if (!window.coplanCadastro) return;
  var C = window.coplanCadastro;
  var $ = function (id) { return document.getElementById(id); };
  var api = function () { return (window.pywebview && window.pywebview.api) || null; };

  var P = {
    active: false,
    nome_projeto: '',
    tipo_pacote: '',
    obras: [],
    columns: [],
    idx: 0,
    pending: {},   // idx -> payload coletado da UI
    motivo: ''     // M092: motivo capturado da primeira obra critica
  };
  C.projeto = P;

  function navBar() { return $('cad-projeto-nav-bar'); }
  function showNav() { var b = navBar(); if (b) b.style.display = 'flex'; }
  function hideNav() { var b = navBar(); if (b) b.style.display = 'none'; }

  function setInfo() {
    var info = $('cad-projeto-nav-info');
    if (!info) return;
    if (!P.active || !P.obras.length) { info.textContent = '—'; return; }
    info.textContent = (P.idx + 1) + ' de ' + P.obras.length
      + (P.nome_projeto ? '  ·  ' + P.nome_projeto : '');
  }

  function updateButtons() {
    var prev = $('cad-projeto-nav-prev');
    var next = $('cad-projeto-nav-next');
    var fin  = $('cad-projeto-nav-finalizar');
    if (prev) prev.disabled = !P.active || P.idx <= 0;
    if (next) next.disabled = !P.active || P.idx >= P.obras.length - 1;
    if (fin)  fin.style.display = (P.active && P.idx >= P.obras.length - 1) ? '' : 'none';
  }

  function captureCurrent() {
    if (!P.active) return;
    var snap = C.serializeForm();
    P.pending[P.idx] = snap;
    // M092: captura motivo da primeira obra que tiver motivo nao-vazio.
    if (snap.motivo_alteracao && !P.motivo) {
      P.motivo = String(snap.motivo_alteracao).trim();
      if (P.motivo) {
        C.toast('Motivo capturado: sera reusado em todo o lote', 'info');
      }
    }
  }

  function showCurrent() {
    if (!P.active) return;
    var obra = P.obras[P.idx];
    if (!obra) return;
    var saved = P.pending[P.idx];
    // Aplica saved (se ja editou) ou obra original.
    C.applyObra(saved || obra);
    // Em modo "Atualizar Projeto" sempre estamos em UPDATE de obra
    // existente, entao garante state.obraEmEdicao = cod da obra atual.
    C.state.obraEmEdicao = (saved && saved.cod) || obra.cod || null;
    setInfo();
    updateButtons();
  }

  function start(nome_projeto, tipo_pacote) {
    var a = api();
    if (!a || !a.projeto_iniciar) {
      C.toast('API projeto_iniciar indisponivel', 'error');
      return Promise.resolve(false);
    }
    var nome = String(nome_projeto || '').trim();
    if (!nome) {
      C.toast('Nome do projeto vazio', 'warn');
      return Promise.resolve(false);
    }
    return a.projeto_iniciar(nome, tipo_pacote || '').then(function (r) {
      if (!r || !r.ok) {
        C.toast('Falha ao iniciar projeto: ' + ((r && r.error) || '?'), 'error');
        return false;
      }
      if (!Array.isArray(r.obras) || r.obras.length === 0) {
        C.toast(C.MSG.aviso.nenhuma_obra_no_projeto, 'warn');
        return false;
      }
      P.active = true;
      P.nome_projeto = nome;
      P.tipo_pacote = tipo_pacote || '';
      P.obras = r.obras.slice();
      P.columns = Array.isArray(r.columns) ? r.columns.slice() : [];
      P.idx = 0;
      P.pending = {};
      P.motivo = '';
      // Vai para aba Cadastro se nao estiver.
      if (typeof window.coplanSetTab === 'function') {
        window.coplanSetTab('cadastro');
      }
      showNav();
      showCurrent();
      C.toast('Atualizar Projeto: "' + nome + '" (' + r.obras.length + ' obras)', 'info');
      return true;
    }).catch(function (err) {
      C.toast('Erro ao iniciar projeto: ' + (err && err.message || err), 'error');
      return false;
    });
  }

  function next() {
    if (!P.active) return;
    captureCurrent();
    if (P.idx < P.obras.length - 1) {
      P.idx++;
      showCurrent();
    } else {
      // Ja na ultima — botao "Finalizar" assume.
      updateButtons();
    }
  }

  function prev() {
    if (!P.active) return;
    captureCurrent();
    if (P.idx > 0) {
      P.idx--;
      showCurrent();
    }
  }

  function cancelar() {
    if (!P.active) return;
    if (!window.confirm('Descartar todas as alteracoes do projeto "'
        + (P.nome_projeto || '?') + '"?')) return;
    P.active = false;
    P.obras = [];
    P.pending = {};
    P.idx = 0;
    P.motivo = '';
    P.nome_projeto = '';
    P.tipo_pacote = '';
    hideNav();
    C.clearForm();
    C.toast('Atualizar Projeto cancelado', 'info');
  }

  function finalizar() {
    if (!P.active) return;
    captureCurrent();
    var a = api();
    if (!a || !a.projeto_finalizar) {
      C.toast('API projeto_finalizar indisponivel', 'error');
      return;
    }
    // Monta payloads ordenados por idx; obras nao tocadas vao com snap
    // sintetico da obra original (sem motivo).
    var payloads = [];
    for (var i = 0; i < P.obras.length; i++) {
      var p = P.pending[i];
      if (!p) {
        // Sintetiza a partir da obra original.
        var orig = P.obras[i] || {};
        p = Object.assign({}, orig, { motivo_alteracao: '' });
      }
      // Garante cod definido (parity com modo update).
      if (!p.cod && P.obras[i] && P.obras[i].cod) {
        p.cod = P.obras[i].cod;
      }
      payloads.push(p);
    }
    a.projeto_finalizar(payloads, P.motivo || '').then(function (r) {
      if (!r) {
        C.toast(C.MSG.erro.salvar + 'sem resposta', 'error');
        return;
      }
      var salvos = r.salvos || 0;
      var falhas = (r.falhas || []).length;
      if (r.ok) {
        C.toast(salvos + ' obra(s) salvas com sucesso', 'success');
      } else {
        // Detalha falhas em console + toast resumo.
        console.warn('[coplan/cadastro] projeto_finalizar falhas:', r.falhas);
        var msg = salvos + ' OK, ' + falhas + ' falha(s)';
        var bloqDesp = (r.falhas || []).some(function (f) {
          return (f.blocked === 'despachada');
        });
        var pendMot = (r.falhas || []).some(function (f) {
          return f.requires_motivo;
        });
        if (bloqDesp) msg += ' (alguma DESPACHADA — marque CORRECAO antes)';
        if (pendMot)  msg += ' (alguma exige motivo — preencha textarea)';
        C.toast(msg, falhas ? 'error' : 'warn');
      }
      // Sempre reseta state e fecha navbar; refresh aba Visualizar.
      P.active = false;
      P.obras = [];
      P.pending = {};
      P.idx = 0;
      P.motivo = '';
      P.nome_projeto = '';
      P.tipo_pacote = '';
      hideNav();
      if (r.ok) {
        C.clearForm();
      }
      document.dispatchEvent(new CustomEvent('coplan:obras-changed', {
        detail: { source: 'cadastro:projeto-finalizar', salvos: salvos }
      }));
    }).catch(function (err) {
      C.toast(C.MSG.erro.salvar + (err && err.message || err), 'error');
    });
  }

  // M091: bind dos botoes da navbar.
  [
    ['cad-projeto-nav-prev',      prev],
    ['cad-projeto-nav-next',      next],
    ['cad-projeto-nav-cancelar',  cancelar],
    ['cad-projeto-nav-finalizar', finalizar]
  ].forEach(function (kv) {
    var b = $(kv[0]);
    if (!b || b.__cadastroProjBound) return;
    b.__cadastroProjBound = true;
    b.addEventListener('click', kv[1]);
  });

  // Custom event externo: aba Visualizar (futura) dispara este evento
  // para entrar em modo "Atualizar Projeto" sem couple direto.
  document.addEventListener('coplan:atualizar-projeto-start', function (ev) {
    var d = (ev && ev.detail) || {};
    if (d.nome_projeto) start(d.nome_projeto, d.tipo_pacote || '');
  });

  // Expose helpers para uso programatico/console.
  window.coplanCadastroProjeto = {
    state: P,
    start: start,
    next: next,
    prev: prev,
    cancelar: cancelar,
    finalizar: finalizar
  };
})();
</script>
<script>
// =====================================================================
// LEVA C da migracao Ganhos: helper window.coplanGanhos + sincronia
// de alimentador ativo + labels live (Planejamento/Postergacao) +
// modal "Ganhos em Massa" + habilitacao por pre-requisitos.
//   G040 -> window.coplanGanhos IIFE (state + utilities + MSG)
//   G041 -> popular <span id="ganhos-alim-atual"> + ganhos_form_state(cod)
//           ao entrar na aba ou ao trocar obra ativa do Cadastro
//   G046 -> labels Planejamento/Postergacao debounced 250ms ao mudar
//           inputs DEPOIS (ler do form do Cadastro pois aba Ganhos
//           web nao tem campos editaveis Antes/Depois individuais)
//   G049 -> modal Ganhos em Massa: intercepta #btn-ganhos-massa.click
//           ANTES do handler antigo (capture phase) para abrir o modal
//   G050 -> disable de botoes Antes/Depois/Atual/Massa quando faltam
//           os 3 arquivos .TXT (validate_tecnico_files)
// G042/G043/G044/G045/G047/G048 ja sao cobertos por blocos existentes:
//   - clickAntes/Depois/Atual/Massa em ~16131 (Passo 5.5)
//   - bindGanhosCard pasta+recarregar em ~15585 (Passo 5.1)
//   - applyCriterios na tabela em ~16282 (Passo 5.3 wrap)
// =====================================================================
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var api = function () { return (window.pywebview && window.pywebview.api) || null; };

  var MSG = {
    aviso: {
      pasta_invalida:        'Selecione uma pasta valida para os arquivos.',
      pasta_nao_encontrada:  'Pasta nao encontrada. Selecione uma nova pasta.',
      txt_ausentes:          'Arquivos tecnicos obrigatorios ausentes: ',
      sem_alim:              'Selecione ao menos um alimentador para preencher os ganhos.',
      sem_match_alim:        'Nenhum dos alimentadores informados foi encontrado nos arquivos.',
      sem_opcao_massa:       'Nenhuma opcao de ganho selecionada.',
      sem_cods_massa:        'Nenhuma obra selecionada na aba Visualizar.'
    },
    erro: {
      ler_arquivo: 'Erro ao ler arquivos tecnicos: ',
      gerar_txt:   'Erro ao gerar o TXT: '
    },
    sucesso: {
      antes:  "Ganhos 'Antes' inseridos com sucesso!",
      depois: "Ganhos 'Depois' inseridos com sucesso!"
    },
    pergunta: {
      massa_executar: 'Deseja prosseguir com a execucao?'
    }
  };

  var state = {
    cod: '',
    alim_principal: '',
    alim_beneficiados: [],
    pasta: '',
    txt_validos: false,
    selectedCods: []  // populados via custom event coplan:ganhos:massa-cods
  };

  function toast(msg, lvl) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, lvl || 'info');
    } else {
      console.log('[coplan/ganhos]', lvl || 'info', msg);
    }
  }

  function setLabel(which, st, text) {
    var id = (which === 'planejamento')
      ? 'ganhos-label-planejamento' : 'ganhos-label-posterga';
    var el = $(id);
    if (!el) return;
    el.setAttribute('data-state', st);
    var icone = 'circle', cor = 'var(--text-soft)', bg = 'var(--surface-2)';
    if (st === 'ok')   { icone = 'check';            cor = 'var(--success)'; bg = 'oklch(0.95 0.06 155)'; }
    if (st === 'warn') { icone = 'alert-triangle';   cor = 'var(--warning)'; bg = 'oklch(0.95 0.06 85)';  }
    if (st === 'err')  { icone = 'x-circle';         cor = 'var(--danger)';  bg = 'oklch(0.95 0.06 25)';  }
    el.style.background = bg;
    el.innerHTML =
      '<i data-lucide="' + icone + '" style="width:13px;height:13px;'
      + 'display:inline-block;vertical-align:-2px;color:' + cor + ';"></i> '
      + String(text || '');
    if (window.lucide) window.lucide.createIcons();
  }

  function setCriterio(key, st, text) {
    var row = document.querySelector(
      '#ganhos-criterios-list [data-criterio="' + key + '"]'
    );
    if (!row) return;
    row.setAttribute('data-state', st);
    var badge = row.querySelector('.badge');
    if (!badge) return;
    badge.classList.remove('success', 'warning', 'danger');
    if (st === 'ok')   badge.classList.add('success');
    if (st === 'warn') badge.classList.add('warning');
    if (st === 'err')  badge.classList.add('danger');
    badge.textContent = text || '—';
  }

  function showModal(id) {
    var m = $(id);
    if (m) m.style.display = 'grid';
  }
  function hideModal(id) {
    var m = $(id);
    if (m) m.style.display = 'none';
  }

  // ---------- G041: sincronia de alim ativo + load do form_state ----------
  function readDepoisFromCadastro() {
    // Os campos DEPOIS vivem no form do Cadastro (espelhado no banco).
    // Aqui lemos diretamente via coplanCadastro.serializeForm().
    if (!window.coplanCadastro || typeof window.coplanCadastro.serializeForm !== 'function') {
      return null;
    }
    var p = window.coplanCadastro.serializeForm();
    return {
      tensao_min:   p.nivel_tensao_obra,    // proxy enquanto nao ha campo dedicado
      tensao_max:   p.nivel_tensao_obra,    // idem
      carregamento: '',                      // sem dado individual — virá de futuras edicoes inline (G004)
      contas:       '',
      manobra:      p.manobra,
      // Dados crus para evolucao futura:
      _payload: p
    };
  }

  function refreshAlimAtual() {
    var span = $('ganhos-alim-atual');
    if (!span) return;
    var alim = state.alim_principal || '';
    span.textContent = alim || '—';
  }

  function loadFormState() {
    var a = api();
    if (!a || !a.ganhos_form_state) return;
    a.ganhos_form_state(state.cod || '').then(function (r) {
      if (!r) return;
      // Atualiza alim ativo (alguns metodos do CoplanApi populam alim).
      var alim = (r.alim && r.alim.principal) || '';
      if (alim) {
        state.alim_principal = alim;
        state.alim_beneficiados = (r.alim && r.alim.beneficiados) || [];
        refreshAlimAtual();
      }
      // Renderiza criterios na sidebar.
      var crit = (r.criterios && r.criterios.criterios) || {};
      var c = function (key) {
        var v = crit[key];
        return (v == null) ? '—' : String(v);
      };
      // Por default mostra valores de configuracao; estado fica "pending"
      // ate o usuario digitar valores DEPOIS para avaliacao.
      setCriterio('tensao_min',   'pending', '≥ ' + c('tensao_min'));
      setCriterio('tensao_max',   'pending', '≤ ' + c('tensao_max'));
      setCriterio('carregamento', 'pending',
        '≤ ' + c('carregamento_limite_sim_ou_vazio') + ' / '
        + c('carregamento_limite_nao') + '%');
      setCriterio('clientes',     'pending', '< ' + c('clientes_maximo'));
      // Valores Atuais (registrados) podem aterrissar nos 3 inputs do card
      // Ganhos Atuais — bloco antigo Passo 5.4 ja faz isso; aqui apenas
      // disparamos o evento para re-disparar quando alim muda.
      if (alim) {
        document.dispatchEvent(new CustomEvent('coplan:ganhos:alim-changed', {
          detail: { alim: alim, beneficiados: state.alim_beneficiados }
        }));
      }
    }).catch(function (err) {
      console.warn('[coplan/ganhos] ganhos_form_state catch:', err);
    });
  }

  // ---------- G046: labels Planejamento/Postergacao live ----------
  function recalcLabels() {
    var a = api();
    if (!a) return;
    var depois = readDepoisFromCadastro();
    if (!depois) {
      setLabel('planejamento', 'pending', 'Aguardando dados para avaliar Planejamento');
      setLabel('posterga',     'pending', 'Aguardando dados para avaliar Postergacao');
      return;
    }
    var payload = {
      tensao_min:   depois.tensao_min,
      tensao_max:   depois.tensao_max,
      carregamento: depois.carregamento,
      contas:       depois.contas,
      manobra:      depois.manobra
    };
    if (a.avaliar_ganhos_planejamento) {
      a.avaliar_ganhos_planejamento(payload).then(function (r) {
        if (!r || !r.ok) return;
        if (r.atende === true) {
          setLabel('planejamento', 'ok', 'Atendeu aos criterios de Planejamento');
        } else if (r.atende === false) {
          var det = (r.motivos || []).join(', ') || 'criterios nao atendidos';
          setLabel('planejamento', 'err', 'Nao atendeu (' + det + ')');
        } else {
          setLabel('planejamento', 'warn', 'Dados insuficientes para avaliar Planejamento');
        }
      }).catch(function () { /* silencioso */ });
    }
    if (a.avaliar_ganhos_postergacao) {
      a.avaliar_ganhos_postergacao(payload).then(function (r) {
        if (!r || !r.ok) return;
        if (r.suficiente === true) {
          setLabel('posterga', 'ok',
            'Obra planejada suficiente (' + r.anos_alcancados + ' anos)');
        } else if (r.suficiente === false) {
          var det = (r.motivos || []).join(', ') || 'falha na projecao';
          setLabel('posterga', 'err',
            'Obra planejada insuficiente apos ' + r.anos_alcancados + ' ano(s) (' + det + ')');
        } else {
          setLabel('posterga', 'warn', 'Dados insuficientes para avaliar Postergacao');
        }
      }).catch(function () { /* silencioso */ });
    }
  }
  function debounce(fn, ms) {
    var t = null;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }
  var recalcLabelsDebounced = debounce(recalcLabels, 250);

  // ---------- G050: pre-requisitos (3 .TXT) ----------
  function applyPrereqState(ok, motivo) {
    ['btn-ganhos-antes', 'btn-ganhos-depois', 'btn-ganhos-atual',
     'btn-ganhos-massa'].forEach(function (id) {
      var b = $(id);
      if (!b) return;
      b.disabled = !ok;
      b.title = ok ? (b.title || '') : (motivo || 'Arquivos tecnicos ausentes');
    });
  }

  function refreshPrereq() {
    var a = api();
    if (!a || !a.validate_tecnico_files) return;
    a.validate_tecnico_files('').then(function (r) {
      var ok = !!(r && r.ok);
      state.txt_validos = ok;
      var motivo = (r && r.error) || (ok ? '' : (MSG.aviso.txt_ausentes
        + ((r && r.faltantes) || []).join(', ')));
      applyPrereqState(ok, motivo);
    }).catch(function () {
      applyPrereqState(false, MSG.aviso.pasta_invalida);
    });
  }

  // ---------- G049: modal Ganhos em Massa ----------
  function openMassaModal() {
    // Atualiza contador e preview com state.selectedCods.
    var cods = state.selectedCods || [];
    var ct = $('ganhos-massa-cods-count');
    if (ct) ct.textContent = String(cods.length);
    var pv = $('ganhos-massa-cods-preview');
    if (pv) {
      var prev = cods.slice(0, 5).join(', ');
      if (cods.length > 5) prev += ', ...';
      pv.textContent = prev || '(nenhuma)';
    }
    // Limpa checks
    ['ganhos-massa-chk-antes', 'ganhos-massa-chk-depois',
     'ganhos-massa-chk-atual'].forEach(function (id) {
      var c = $(id); if (c) c.checked = false;
    });
    var btnOk = $('ganhos-massa-btn-ok');
    if (btnOk) btnOk.disabled = true;
    showModal('modal-ganhos-massa');
  }

  function aplicarMassa() {
    var a = api();
    if (!a || !a.ganhos_apply_massa) {
      toast('API ganhos_apply_massa indisponivel', 'error');
      return;
    }
    var cods = state.selectedCods || [];
    if (!cods.length) {
      toast(MSG.aviso.sem_cods_massa, 'warn');
      return;
    }
    var etapas = [];
    if ($('ganhos-massa-chk-antes')  && $('ganhos-massa-chk-antes').checked)  etapas.push('antes');
    if ($('ganhos-massa-chk-depois') && $('ganhos-massa-chk-depois').checked) etapas.push('depois');
    if ($('ganhos-massa-chk-atual')  && $('ganhos-massa-chk-atual').checked)  etapas.push('atual');
    if (!etapas.length) {
      toast(MSG.aviso.sem_opcao_massa, 'info');
      return;
    }
    if (!window.confirm(MSG.pergunta.massa_executar)) return;
    hideModal('modal-ganhos-massa');
    // Aplica em serie por etapa.
    var i = 0;
    var resumos = [];
    function step() {
      if (i >= etapas.length) {
        var msg = resumos.join(' | ');
        toast(msg || 'Concluido', 'info');
        if (typeof window.coplanLoadObras === 'function') window.coplanLoadObras();
        return;
      }
      var etapa = etapas[i++];
      a.ganhos_apply_massa(cods, etapa, '').then(function (r) {
        if (!r) {
          resumos.push(etapa + ': sem resposta');
        } else {
          var sucesso = r.sucesso || 0;
          var falhas  = (r.falhas || []).length;
          var ign     = (r.ignoradas_sem_alim || []).length;
          resumos.push(etapa + ': ' + sucesso + ' OK'
            + (falhas ? ', ' + falhas + ' falha(s)' : '')
            + (ign ? ', ' + ign + ' sem alim' : ''));
        }
        step();
      }).catch(function (err) {
        resumos.push(etapa + ': erro ' + (err && err.message || err));
        step();
      });
    }
    step();
  }

  // Captura cods externos (aba Visualizar pode disparar este evento).
  document.addEventListener('coplan:ganhos:massa-cods', function (ev) {
    var d = (ev && ev.detail) || {};
    if (Array.isArray(d.cods)) state.selectedCods = d.cods.slice();
  });

  // Bind do modal Ganhos em Massa (captura ANTES do handler antigo).
  var btnMassaOuter = $('btn-ganhos-massa');
  if (btnMassaOuter && !btnMassaOuter.__massaModalBound) {
    btnMassaOuter.__massaModalBound = true;
    btnMassaOuter.addEventListener('click', function (ev) {
      // Se ja houver cods coletados, abrir o modal antes do handler antigo
      // tomar a decisao. Stop propagation para nao disparar clickMassa.
      if (state.selectedCods && state.selectedCods.length) {
        ev.stopPropagation();
        ev.stopImmediatePropagation && ev.stopImmediatePropagation();
        openMassaModal();
      } else {
        // Sem cods coletados: fluxo antigo (clickMassa) tenta usar todas
        // as obras visiveis. Vamos avisar e tambem abrir o modal vazio
        // (pra UX previsivel).
        toast(MSG.aviso.sem_cods_massa, 'warn');
        ev.stopPropagation();
        ev.stopImmediatePropagation && ev.stopImmediatePropagation();
        openMassaModal();
      }
    }, true); // capture
  }

  var btnMassaOk = $('ganhos-massa-btn-ok');
  if (btnMassaOk && !btnMassaOk.__cadBound) {
    btnMassaOk.__cadBound = true;
    btnMassaOk.addEventListener('click', aplicarMassa);
  }
  // Habilita OK quando ao menos 1 checkbox marcado.
  ['ganhos-massa-chk-antes', 'ganhos-massa-chk-depois',
   'ganhos-massa-chk-atual'].forEach(function (id) {
    var c = $(id);
    if (!c || c.__cadBound) return;
    c.__cadBound = true;
    c.addEventListener('change', function () {
      var any = ['ganhos-massa-chk-antes','ganhos-massa-chk-depois',
                 'ganhos-massa-chk-atual'].some(function (k) {
        var cb = $(k); return cb && cb.checked;
      });
      var btn = $('ganhos-massa-btn-ok');
      if (btn) btn.disabled = !any || !(state.selectedCods || []).length;
    });
  });
  var btnMassaHelp = $('ganhos-massa-btn-help');
  if (btnMassaHelp && !btnMassaHelp.__cadBound) {
    btnMassaHelp.__cadBound = true;
    btnMassaHelp.addEventListener('click', function () {
      toast('Selecione obras na aba Visualizar (col. checkbox), depois clique '
        + 'em Ganhos em Massa para aplicar etapas em lote.', 'info');
    });
  }

  // ---------- Listeners de aba e sincronia ----------
  document.addEventListener('coplan:tab', function (ev) {
    var name = ev && ev.detail && ev.detail.name;
    if (name !== 'ganhos') return;
    // Pega cod ativo do Cadastro se existir.
    if (window.coplanCadastro && window.coplanCadastro.state) {
      state.cod = window.coplanCadastro.state.obraEmEdicao || '';
    }
    refreshPrereq();
    loadFormState();
    recalcLabelsDebounced();
    // [FIX] Outro IIFE (Passo 5.2) tambem ouve coplan:tab='ganhos' e
    // chama renderGanhosTbody([]) — apaga a tabela. Aqui re-populamos
    // depois (setTimeout 50ms para rodar APOS aquele handler).
    setTimeout(function () {
      if (state.lastObra) populateTbodyFromObra(state.lastObra);
    }, 50);
  });

  // [FIX] Wrap window.coplanRenderGanhosTbody para que cada celula vire
  // <input data-row=... data-ganhos-input=...> — isso permite ao codigo
  // antigo (clickAntes/Depois -> applyMetricasAntes -> setRowVal) achar
  // os inputs e atualizar valores. Tambem permite edicao manual (G004).
  var LABEL_TO_KEY = {
    'contas contratos':              'contas',
    'carregamento (%)':              'carregamento',
    'perdas kw':                     'perdas',
    'tensao media (pu)':             'tensao_media',
    'tensao min. (pu)':              'tensao_min',
    'tensao linha min. (pu)':        'tensao_min_linha',
    'chi':                           'chi',
    'ci':                            'ci',
    'tensao maxima':                 'tensao_max',
    'ganhos totais':                 'ganhos_totais',
    'contas contratos beneficiadas': 'contas_benef',
    'cc_benef_chi_ci':               'cc_benef_chi_ci'
  };
  function _normLab(s) {
    return String(s || '').trim().toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }
  function injectRowInputs() {
    var tbody = $('ganhos-tbody');
    if (!tbody) return;
    var trs = tbody.querySelectorAll('tr');
    Array.prototype.forEach.call(trs, function (tr) {
      var cells = tr.querySelectorAll('td');
      if (cells.length < 3) return;  // ignora row "Selecione um arquivo"
      var label = (cells[0].textContent || '').trim();
      var key = LABEL_TO_KEY[_normLab(label)] || _normLab(label).replace(/\W+/g, '_');
      tr.setAttribute('data-row', key);
      // Para celulas Antes/Depois (1 e 2): substitui texto por <input>.
      [['antes', cells[1]], ['depois', cells[2]]].forEach(function (slot) {
        var slotName = slot[0], cell = slot[1];
        if (!cell) return;
        // Se ja tem input data-ganhos-input, pula.
        if (cell.querySelector('input[data-ganhos-input]')) return;
        var v = (cell.textContent || '').trim();
        // Preserva colspan (caso da row "single").
        var hasColspan = cell.hasAttribute('colspan');
        cell.innerHTML = '';
        var inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input mono';
        inp.style.cssText = 'width:100%;padding:2px 4px;border:1px solid transparent;'
          + 'background:transparent;font-size:inherit;color:inherit;';
        inp.setAttribute('data-ganhos-input', slotName);
        inp.value = v;
        cell.appendChild(inp);
        if (hasColspan) {
          // single-value: so o slot 'antes' importa.
          if (slotName !== 'antes') cell.style.display = 'none';
        }
      });
    });
  }
  if (typeof window.coplanRenderGanhosTbody === 'function'
      && !window.coplanRenderGanhosTbody.__ganhosInputWrap) {
    var __origRender = window.coplanRenderGanhosTbody;
    window.coplanRenderGanhosTbody = function () {
      var r = __origRender.apply(this, arguments);
      try { injectRowInputs(); } catch (e) { /* swallow */ }
      // Re-aplica delta + criterios (wrap antigo do Passo 5.3 espera
      // inputs ou tds — vamos garantir que delta seja recalculado).
      return r;
    };
    window.coplanRenderGanhosTbody.__ganhosInputWrap = true;
    window.coplanRenderGanhosTbody.__inner = __origRender;
  }

  // Sempre que o Cadastro carregar/limpar uma obra, sincroniza.
  document.addEventListener('coplan:obra-active', function (ev) {
    var d = (ev && ev.detail) || {};
    state.cod = d.cod || '';
    state.alim_principal = d.alim_principal || '';
    state.alim_beneficiados = d.alim_beneficiados || [];
    state.lastObra = d.obra || null;  // [FIX] memo p/ re-popular ao re-entrar
    refreshAlimAtual();
    loadFormState();
    recalcLabelsDebounced();
    // [FIX] Popula a tabela #ganhos-tbody com os parametros JA SALVOS
    // da obra (10 pares antes/depois). Sem isso, a tabela fica vazia
    // ate o user clicar em "Inserir Antes/Depois" — o que apaga o
    // historico salvo. Origem: ganhos_mixin.py:154-178 (10 pares de
    // QLineEdit) + cadastro_mixin.py:843-867 (mapping coluna_db ->
    // widget). Aqui montamos a list parametros[{label,a,d}] no formato
    // que coplanRenderGanhosTbody espera.
    populateTbodyFromObra(d.obra);
  });

  function populateTbodyFromObra(obra) {
    if (!obra || typeof obra !== 'object') return;
    if (typeof window.coplanRenderGanhosTbody !== 'function') return;
    // Mapeamento: 10 pares (label visivel, col_antes, col_depois)
    // copiado da grade do ganhos_mixin.py:154-178.
    var pares = [
      ['Contas Contratos',     'contas_contratos_previos',   'contas_contratos_posteriores'],
      ['Carregamento (%)',     'carregamento_inicial',       'carregamento_final'],
      ['Perdas kW',            'perdas_iniciais',            'perdas_finais'],
      ['Tensao Media (pu)',    'tensao_media_inicial',       'tensao_media_final'],
      ['Tensao Min. (pu)',     'tensao_min_inicial',         'tensao_min_final'],
      ['Tensao Linha Min.',    'tensao_min_linha_inicial',   'tensao_min_linha_final'],
      ['CHI',                  'chi_inicial',                'chi_final'],
      ['CI',                   'ci_inicial',                 'ci_final'],
      ['Tensao Maxima',        'tensao_max_inicial',         'tensao_max_final'],
      ['Ganhos Totais',        'ganhos_totais_antes',        'ganhos_totais_depois']
    ];
    function _v(k) {
      var v = obra[k];
      if (v == null) return '';
      var s = String(v).trim();
      return s;
    }
    var parametros = pares.map(function (p) {
      return { label: p[0], a: _v(p[1]), d: _v(p[2]) };
    });
    // Quando TODOS estao vazios, mostra placeholder ([]) — coplanRender
    // ja sabe lidar com vazio.
    var anyData = parametros.some(function (p) { return p.a || p.d; });
    window.coplanRenderGanhosTbody(anyData ? parametros : []);
  }
  // [FIX] populateTbodyFromObra exposto via window.coplanGanhos abaixo
  // (no bloco coplanGanhos = {...}). Antes 'C.populateTbodyFromObra'
  // aqui — 'C' nao existe neste IIFE (so em IIFEs subsequentes).

  // Recalc labels quando user editar campos que influenciam a avaliacao.
  // Como os ganhos DEPOIS no web ainda nao tem inputs proprios, observamos
  // o form do Cadastro (alimentador, tensao, manobra) como proxy.
  ['cad-input-tensao', 'cad-input-tensao-oper', 'cad-sel-manobra'].forEach(function (id) {
    var el = $(id);
    if (!el || el.__ganhosObs) return;
    el.__ganhosObs = true;
    var ev = el.tagName === 'SELECT' ? 'change' : 'input';
    el.addEventListener(ev, recalcLabelsDebounced);
  });

  // ---------- G061: tecnico_dirty=SIM ao editar ganhos ----------
  state.tecnico_dirty_local = false;
  function markTecnicoDirty() {
    state.tecnico_dirty_local = true;
  }
  function clearTecnicoDirty() {
    state.tecnico_dirty_local = false;
  }
  // Marca dirty quando user clicar nos botoes de calculo de ganhos.
  ['btn-ganhos-antes', 'btn-ganhos-depois', 'btn-ganhos-atual',
   'btn-ganhos-massa'].forEach(function (id) {
    var b = $(id);
    if (!b || b.__ganhosDirtyBound) return;
    b.__ganhosDirtyBound = true;
    b.addEventListener('click', markTecnicoDirty);
  });
  // Tambem quando user editar inputs do card "Ganhos Atuais".
  ['ganhos-atual-tensao-reg', 'ganhos-atual-carreg', 'ganhos-atual-totais'
  ].forEach(function (id) {
    var inp = $(id);
    if (!inp || inp.__ganhosDirtyBound) return;
    inp.__ganhosDirtyBound = true;
    inp.addEventListener('input', markTecnicoDirty);
  });
  // Wrap coplanCadastro.serializeForm para refletir o dirty no payload.
  if (window.coplanCadastro && typeof window.coplanCadastro.serializeForm === 'function'
      && !window.coplanCadastro.__ganhosDirtyWrap) {
    window.coplanCadastro.__ganhosDirtyWrap = true;
    var origSerialize = window.coplanCadastro.serializeForm;
    window.coplanCadastro.serializeForm = function () {
      var p = origSerialize.apply(this, arguments) || {};
      if (state.tecnico_dirty_local) {
        p.tecnico_dirty = 'SIM';
      }
      return p;
    };
    // Apos save bem-sucedido, limpa dirty.
    document.addEventListener('coplan:obras-changed', function (ev) {
      var d = ev && ev.detail;
      if (d && d.source === 'cadastro:save') clearTecnicoDirty();
    });
  }

  // ---------- Expose ----------
  window.coplanGanhos = {
    state: state,
    MSG: MSG,
    setLabel: setLabel,
    setCriterio: setCriterio,
    showModal: showModal,
    hideModal: hideModal,
    refreshAlimAtual: refreshAlimAtual,
    loadFormState: loadFormState,
    recalcLabels: recalcLabelsDebounced,
    refreshPrereq: refreshPrereq,
    openMassaModal: openMassaModal,
    setSelectedCods: function (cods) {
      state.selectedCods = Array.isArray(cods) ? cods.slice() : [];
    },
    markTecnicoDirty: markTecnicoDirty,
    clearTecnicoDirty: clearTecnicoDirty,
    populateTbodyFromObra: populateTbodyFromObra,
    toast: toast
  };

  // Init: se ja estamos na aba ganhos no boot, dispara loadFormState.
  function _initIfActive() {
    var active = document.querySelector('.tab-panel.active');
    if (active && active.id === 'tab-ganhos') {
      window.coplanReady && window.coplanReady(function () {
        if (window.coplanCadastro && window.coplanCadastro.state) {
          state.cod = window.coplanCadastro.state.obraEmEdicao || '';
        }
        refreshPrereq();
        loadFormState();
      });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initIfActive);
  } else {
    _initIfActive();
  }
})();
</script>
