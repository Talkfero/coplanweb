<script>
// =====================================================================
// LEVA 3 da migracao Cadastro: helper window.coplanCadastro + catalogo
// MSG + auto-load das options ao entrar na aba.
//   M040 -> window.coplanCadastro IIFE com loadOptions/serializeForm/
//           applyObra/clearForm/setValidation/showModal/hideModal/getChips
//   M041 -> dispara loadOptions() no evento coplan:tab='cadastro'
//   M100 -> window.COPLAN_CADASTRO_MSG (espelho das mensagens do desktop)
//   M101 -> reaproveita window.coplanToast (definido em ~linha 8666)
// Nada aqui faz IO de campo (listeners de input/click vem em iteracoes
// posteriores: M042-M062, M080-M092).
// =====================================================================
(function () {
  'use strict';

  var MSG = {
    aviso: {
      dados_alim_nao_carregados: 'Os dados dos alimentadores ainda nao foram carregados!',
      alim_vazio_ou_duplicado:   'Alimentador vazio ou ja adicionado.',
      nenhuma_obra_no_projeto:   'Nenhuma obra encontrada para o projeto selecionado.',
      nenhum_valor_unitario:     'Nenhum valor unitario encontrado para os parametros selecionados.',
      despachada:                'Obra ja DESPACHADA. Para alterar, marque como CORRECAO primeiro.',
      nenhuma_atualizacao:       'Nenhuma atualizacao aplicavel foi encontrada.'
    },
    erro: {
      alim_underscore:   "Alimentador contem '_' (nao permitido).",
      calc_item:         'Erro ao calcular numero do item: ',
      calc_valor:        'Erro no calculo do valor da obra: ',
      carregar_projeto:  'Erro ao carregar dados do projeto: ',
      salvar:            'Erro ao salvar obra: ',
      cod_duplicado:     'Ja existe uma obra com este codigo.',
      cod_item_duplicado:'Ja existe uma obra com este codigo de item para o projeto informado.'
    },
    sucesso: {
      criada:    'Nova obra criada com sucesso!',
      atualizada:'Obra atualizada com sucesso!',
      merged:    'Registro existente atualizado com sucesso!'
    },
    pergunta: {
      gerar_descricao: 'Nenhuma descricao foi informada. Deseja gerar a descricao automaticamente?',
      cod_alterado:    'O codigo da obra foi alterado. Deseja criar uma nova obra ou atualizar a obra existente?'
    },
    prompt: {
      motivo: 'Mudanca critica: <campos>. Informe motivo (obrigatorio).'
    },
    tooltip: {
      sem_underscore: 'Nao use sublinhado (_) neste campo'
    },
    label: {
      nao_iniciar_obra: 'Nao pode iniciar com "Obra"'
    }
  };
  window.COPLAN_CADASTRO_MSG = MSG;

  function $(id) { return document.getElementById(id); }
  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }
  function api() { return (window.pywebview && window.pywebview.api) || null; }

  function valOf(id) {
    var el = $(id);
    if (!el) return '';
    if (el.type === 'checkbox') return el.checked ? '1' : '';
    return (el.value == null ? '' : String(el.value)).trim();
  }
  function setVal(id, v) {
    var el = $(id);
    if (!el) return;
    var s = v == null ? '' : String(v);
    if (el.tagName === 'SELECT') {
      var match = false;
      for (var i = 0; i < el.options.length; i++) {
        if (el.options[i].value === s || el.options[i].textContent.trim() === s) {
          el.selectedIndex = i;
          match = true;
          break;
        }
      }
      if (!match && s === '') el.selectedIndex = -1;
      return;
    }
    el.value = s;
  }

  function populateSelect(id, items, opts) {
    opts = opts || {};
    var sel = $(id);
    if (!sel || !Array.isArray(items)) return;
    // [FIX] Se o elemento e <input list="..."> (combobox editavel),
    // popula o <datalist> em vez de tentar usar .options. Permite
    // ao usuario DIGITAR alimentador novo que nao existe na lista.
    if (sel.tagName === 'INPUT') {
      var listId = sel.getAttribute('list');
      var dl = listId ? document.getElementById(listId) : null;
      if (dl) {
        while (dl.firstChild) dl.removeChild(dl.firstChild);
        items.forEach(function (it) {
          var o = document.createElement('option');
          o.value = String(it);
          dl.appendChild(o);
        });
      }
      return;
    }
    var prev = sel.value;
    while (sel.firstChild) sel.removeChild(sel.firstChild);
    if (opts.allowEmpty) {
      var opt0 = document.createElement('option');
      opt0.value = '';
      opt0.textContent = '';
      sel.appendChild(opt0);
    }
    items.forEach(function (it) {
      var o = document.createElement('option');
      o.value = String(it);
      o.textContent = String(it);
      sel.appendChild(o);
    });
    // Tenta preservar o valor anterior se ainda existe.
    var found = false;
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === prev) { sel.selectedIndex = i; found = true; break; }
    }
    if (!found) sel.selectedIndex = opts.allowEmpty ? 0 : (opts.keepFirst ? 0 : -1);
  }

  function getAprovada() {
    var btnSim = $('cad-pill-aprovada-sim');
    var btnNao = $('cad-pill-aprovada-nao');
    if (btnSim && btnSim.classList.contains('active')) return 'SIM';
    if (btnNao && btnNao.classList.contains('active')) return 'NÃO';
    return 'NÃO';
  }
  function setAprovada(v) {
    // Aceita 'SIM'/'NÃO'/'NAO' como input; estado interno usa o valor
    // canonico do desktop ('NÃO' com til) para serializar igual.
    var s = String(v || '').toUpperCase().replace('NAO', 'NÃO');
    var btnSim = $('cad-pill-aprovada-sim');
    var btnNao = $('cad-pill-aprovada-nao');
    if (!btnSim || !btnNao) return;
    btnSim.classList.toggle('active', s === 'SIM');
    btnNao.classList.toggle('active', s !== 'SIM');
  }

  function getChips() {
    return $all('#cad-list-alim-benef .chip').map(function (c) {
      var t = c.textContent || '';
      return t.replace(/\s+/g, ' ').trim();
    });
  }
  function clearChips() {
    var box = $('cad-list-alim-benef');
    if (box) box.innerHTML = '';
    var sub = $('cad-list-subestacoes');
    if (sub) sub.innerHTML = '';
  }

  var state = {
    optionsLoaded: false,
    obraEmEdicao: null,
    pendingPayloads: []
  };

  function loadOptions(force) {
    var a = api();
    if (!a || !a.cadastro_form_metadata) return Promise.resolve(false);
    if (state.optionsLoaded && !force) return Promise.resolve(true);
    return a.cadastro_form_metadata().then(function (meta) {
      if (!meta || !meta.ok) return false;
      populateSelect('cad-sel-ano', meta.ano_range || [], { keepFirst: true });
      var piItems = [];
      if (meta.pi && Array.isArray(meta.pi.long_names)) piItems = meta.pi.long_names.slice();
      if (meta.pi && Array.isArray(meta.pi.bases)) {
        meta.pi.bases.forEach(function (b) {
          if (piItems.indexOf(b) < 0) piItems.push(b);
        });
      }
      populateSelect('cad-sel-pi', piItems, { allowEmpty: true });
      populateSelect('cad-sel-pacote',          (meta.pacotes && meta.pacotes.items) || [], { allowEmpty: true });
      populateSelect('cad-sel-manobra',         meta.manobra || [], { allowEmpty: true });
      populateSelect('cad-sel-novo-bay',        meta.novo_bay || [], { allowEmpty: true });
      populateSelect('cad-sel-criticidade',     meta.criticidade || [], { allowEmpty: true });
      var alimItems = (meta.alimentadores && meta.alimentadores.items) || [];
      populateSelect('cad-sel-alim-principal', alimItems, { allowEmpty: true });
      // Mesma lista no select de "Alimentador Beneficiado" (M048).
      populateSelect('cad-input-alim-benef',   alimItems, { allowEmpty: true });
      populateSelect('cad-sel-caracteristicas', (meta.caracteristicas && meta.caracteristicas.items) || [], { allowEmpty: true });
      // Aprovada padrao = NÃO (replica desktop field_obra_aprovada index 0).
      setAprovada(state.obraEmEdicao ? getAprovada() : 'NÃO');
      state.optionsLoaded = true;
      return true;
    }).catch(function (err) {
      console.warn('[coplan/cadastro] loadOptions falhou:', err);
      return false;
    });
  }

  function serializeForm() {
    var benef = getChips();
    return {
      cod:                       state.obraEmEdicao || '',
      ano_:                      valOf('cad-sel-ano'),
      projeto_investimento:      valOf('cad-sel-pi'),
      codigo_item:               valOf('cad-input-item'),
      nome_projeto:              valOf('cad-input-projeto'),
      observacoes_gerais:        valOf('cad-input-observacoes'),
      alimentador_principal:     valOf('cad-sel-alim-principal'),
      nivel_tensao_obra:         valOf('cad-input-tensao'),
      tensao_operacao:           valOf('cad-input-tensao-oper'),
      nome_regional:             valOf('cad-input-regional'),
      nome_superintendencia:     valOf('cad-input-superintendencia'),
      subestacao:                valOf('cad-input-se'),
      coordenada_inicio:         valOf('cad-input-coord-inicio'),
      coordenada_fim:            valOf('cad-input-coord-fim'),
      quantidade_material:       valOf('cad-input-quantidade'),
      caracteristicas_material:  valOf('cad-sel-caracteristicas'),
      manobra:                   valOf('cad-sel-manobra'),
      novo_bay:                  valOf('cad-sel-novo-bay'),
      nivel_criticidade:         valOf('cad-sel-criticidade'),
      tipo_pacote:               valOf('cad-sel-pacote'),
      obra_aprovada:             getAprovada(),
      valor_obra:                valOf('cad-input-valor'),  // formato pt-BR mantido p/ backend (ja normaliza)
      alimentadores_beneficiados: benef.join(';'),
      tecnico_dirty:             'NÃO',
      motivo_alteracao:          valOf('cad-input-motivo')
    };
  }

  // [FIX] Formata valor_obra para pt-BR ao popular o campo (banco
  // pode trazer "2487500" ou "2487500.5" e queremos exibir como
  // "2.487.500,00"). Aceita string ou numero, retorna '' se nao parsear.
  function fmtValorBr(v) {
    if (v == null || v === '') return '';
    var s = String(v).trim();
    if (!s) return '';
    // Se ja vem formatado com virgula decimal e milhar com ponto,
    // mantem (caso o backend ja tenha formatado).
    if (/^\d{1,3}(\.\d{3})*,\d{2}$/.test(s)) return s;
    // Normaliza pt-BR -> en para parse: remove milhar (.) e troca ',' por '.'.
    var norm = s.replace(/\./g, '').replace(',', '.');
    var n = parseFloat(norm);
    if (isNaN(n)) return s;  // devolve cru se nao parsear
    try {
      return n.toLocaleString('pt-BR', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
      });
    } catch (e) {
      return n.toFixed(2).replace('.', ',');
    }
  }
  // [FIX] fmtValorBr exposto via window.coplanCadastro mais abaixo
  // (dentro do bloco window.coplanCadastro = {...}). Antes tentava
  // 'C.fmtValorBr = ...' aqui mas 'C' nao existe neste escopo.

  // Card "Status da Nota": informativo (sem bloqueio) que mostra
  // se a obra carregada esta DESPACHADA / CORRECAO / sem nota.
  // Operador fica ciente de que esta editando obra ja despachada.
  function applyNotaStatus(obra) {
    var card = $('cad-aside-nota');
    if (!card) return;
    var status = String((obra && obra.despacho_status) || '')
      .trim().toUpperCase();
    if (!status) {
      card.style.display = 'none';
      return;
    }
    card.style.display = '';
    var STYLES = {
      DESPACHADA: {bg: 'oklch(0.72 0.20 55)', fg: 'white', icon: 'send'},
      CORRECAO:   {bg: 'oklch(0.85 0.16 90)',
                   fg: 'oklch(0.30 0.13 80)', icon: 'edit-3'},
    };
    var s = STYLES[status]
      || {bg: 'var(--surface-2)', fg: 'var(--text)', icon: 'circle'};
    var pill = $('cad-nota-pill');
    if (pill) {
      pill.style.background = s.bg;
      pill.style.color = s.fg;
      pill.dataset.status = status;
    }
    var icon = $('cad-nota-icon');
    if (icon) icon.setAttribute('data-lucide', s.icon);
    var statusText = $('cad-nota-status-text');
    if (statusText) statusText.textContent = status;
    var ref = String((obra && obra.despacho_ref) || '').trim();
    var refRow = $('cad-nota-ref-row');
    var refEl = $('cad-nota-ref');
    if (refRow) refRow.style.display = ref ? '' : 'none';
    if (refEl && ref) refEl.textContent = ref;
    var em = String((obra && obra.despacho_em) || '').trim();
    var emRow = $('cad-nota-em-row');
    var emEl = $('cad-nota-em');
    if (emRow) emRow.style.display = em ? '' : 'none';
    if (emEl && em) emEl.textContent = em;
    var aviso = $('cad-nota-aviso');
    if (aviso) aviso.style.display = (status === 'DESPACHADA') ? '' : 'none';
    if (window.lucide && window.lucide.createIcons) {
      try { window.lucide.createIcons(); } catch (_e) {}
    }
  }

  function applyObra(obra) {
    if (!obra || typeof obra !== 'object') return;
    var fields = [
      ['cad-sel-ano',                 obra.ano_],
      ['cad-sel-pi',                  obra.projeto_investimento],
      ['cad-input-item',              obra.codigo_item],
      ['cad-input-projeto',           obra.nome_projeto],
      ['cad-input-observacoes',       obra.observacoes_gerais],
      ['cad-sel-alim-principal',      obra.alimentador_principal],
      ['cad-input-tensao',            obra.nivel_tensao_obra],
      ['cad-input-tensao-oper',       obra.tensao_operacao],
      ['cad-input-regional',          obra.nome_regional],
      ['cad-input-superintendencia',  obra.nome_superintendencia],
      ['cad-input-se',                obra.subestacao],
      ['cad-input-coord-inicio',      obra.coordenada_inicio],
      ['cad-input-coord-fim',         obra.coordenada_fim],
      ['cad-input-quantidade',        obra.quantidade_material],
      ['cad-sel-caracteristicas',     obra.caracteristicas_material],
      ['cad-sel-manobra',             obra.manobra],
      ['cad-sel-novo-bay',            obra.novo_bay],
      ['cad-sel-criticidade',         obra.nivel_criticidade],
      ['cad-sel-pacote',              obra.tipo_pacote],
      ['cad-input-valor',             fmtValorBr(obra.valor_obra)],
      ['cad-input-cod-pep',           obra.cod_pep]
    ];
    fields.forEach(function (kv) { setVal(kv[0], kv[1]); });
    setAprovada(obra.obra_aprovada || 'NÃO');
    state.obraEmEdicao = obra.cod || null;
    var ano = $('cad-sel-ano');
    if (ano) ano.disabled = false;
    var motivoRow = $('cad-row-motivo');
    if (motivoRow) motivoRow.style.display = 'none';
    applyNotaStatus(obra);
  }

  function clearForm() {
    state.obraEmEdicao = null;
    [
      'cad-input-item', 'cad-input-projeto', 'cad-input-observacoes',
      'cad-input-tensao', 'cad-input-tensao-oper', 'cad-input-regional',
      'cad-input-superintendencia', 'cad-input-se', 'cad-input-coord-inicio',
      'cad-input-coord-fim', 'cad-input-quantidade', 'cad-input-valor',
      'cad-input-cod-pep', 'cad-input-motivo'
    ].forEach(function (id) {
      var el = $(id); if (el) el.value = '';
    });
    [
      'cad-sel-pi', 'cad-sel-alim-principal', 'cad-sel-caracteristicas',
      'cad-sel-manobra', 'cad-sel-novo-bay', 'cad-sel-criticidade',
      'cad-sel-pacote'
    ].forEach(function (id) {
      var el = $(id); if (el) el.selectedIndex = -1;
    });
    var ano = $('cad-sel-ano');
    if (ano) { ano.selectedIndex = 0; ano.disabled = false; }
    setAprovada('NÃO');
    clearChips();
    var motivoRow = $('cad-row-motivo');
    if (motivoRow) motivoRow.style.display = 'none';
    applyNotaStatus({});
  }

  function setValidation(checks) {
    if (!checks || typeof checks !== 'object') return;
    Object.keys(checks).forEach(function (key) {
      var row = document.querySelector('[data-check="' + key + '"]');
      if (!row) return;
      var st = String(checks[key] || 'pending');
      row.setAttribute('data-state', st);
      // Atualiza o icone visualmente (lucide).
      var icon = row.querySelector('i[data-lucide]');
      if (icon) {
        var name = 'circle';
        if (st === 'ok')   name = 'check';
        if (st === 'warn') name = 'alert-triangle';
        if (st === 'err')  name = 'x-circle';
        icon.setAttribute('data-lucide', name);
        // Cor inline (sobrescreve o style do mock).
        if (st === 'ok')   icon.style.color = 'var(--success)';
        else if (st === 'warn') icon.style.color = 'var(--warning)';
        else if (st === 'err')  icon.style.color = 'var(--danger)';
        else                    icon.style.color = 'var(--text-soft)';
      }
    });
    if (window.lucide) window.lucide.createIcons();
  }

  function showModal(id) {
    var m = $(id);
    if (m) m.style.display = 'grid';
  }
  function hideModal(id) {
    var m = $(id);
    if (m) m.style.display = 'none';
  }

  // Expose
  window.coplanCadastro = {
    MSG: MSG,
    state: state,
    loadOptions: loadOptions,
    serializeForm: serializeForm,
    applyObra: applyObra,
    clearForm: clearForm,
    setValidation: setValidation,
    showModal: showModal,
    hideModal: hideModal,
    getChips: getChips,
    setAprovada: setAprovada,
    getAprovada: getAprovada,
    populateSelect: populateSelect,
    setVal: setVal,
    valOf: valOf,
    fmtValorBr: fmtValorBr,
    toast: function (msg, lvl) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(msg, lvl || 'info');
      } else {
        console.log('[coplan/cadastro]', lvl || 'info', msg);
      }
    }
  };

  // M041: dispara loadOptions quando aba Cadastro fica ativa.
  document.addEventListener('coplan:tab', function (ev) {
    var name = ev && ev.detail && ev.detail.tab;
    if (name === 'cadastro') {
      window.coplanReady(function () { loadOptions(false); });
    }
  });
  function _initIfActive() {
    var active = document.querySelector('.tab-panel.active');
    if (active && active.id === 'tab-cadastro') {
      window.coplanReady(function () { loadOptions(false); });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initIfActive);
  } else {
    _initIfActive();
  }
})();
</script>
<script>
// =====================================================================
// LEVA 3 - listeners de campo (M042-M046)
//   M042 -> Ano trava em modo edicao (applyObra/clearForm ja faz isso;
//           verificacao adicional aqui de seguranca).
//   M043 -> change em PI dispara resolver_pi_base; se nao conhecido,
//           prompt local + save_pi_base_map merge-friendly.
//   M044 -> change em Alimentador Obra dispara get_alimentador_details
//           (autofill tensao/regional/sup./SE) + caracteristicas_por_
//           alimentador (repopula combo) + recalc subestacoes.
//   M045 -> change em combo Nome do Projeto -> "Melhorias_AL_" quando
//           valor normalizado bater com "MELHORIAS AL".
//   M046 -> 6 botoes data-act="nome-projeto:*" via delegacao no body
//           (Nova SE / Novo AL / Reconfiguracao / Alivio SE / Flexi /
//           Multi-PI). Multi-PI por enquanto so abre o modal placeholder
//           (M047 vai popular checkboxes e processar OK).
// Inclui ainda recalcSubestacoes() reusada por M048 quando entrar.
// =====================================================================
(function () {
  'use strict';
  if (!window.coplanCadastro) {
    console.warn('[coplan/cadastro] coplanCadastro nao carregado; skip listeners');
    return;
  }
  var C = window.coplanCadastro;
  var $ = function (id) { return document.getElementById(id); };
  var api = function () { return (window.pywebview && window.pywebview.api) || null; };

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ---- pickPiBase: replica QInputDialog.getItem do desktop (pi_base.py).
  // Abre dialogo com <select> populado por list_pi_base_custom().all
  // + opcao "+ Criar novo PI_BASE...". Se o user criar novo, persiste
  // via add_pi_base_custom. Resolve com string (base escolhida) ou null
  // (cancelado).
  function pickPiBase(pi, sugestao) {
    var a = api();
    if (!a || typeof window.coplanOpenDialog !== 'function'
        || !a.list_pi_base_custom) {
      var raw = window.prompt(
        'PI "' + pi + '" nao tem PI_BASE conhecido.\nInforme o PI_BASE base:',
        sugestao || ''
      );
      if (raw == null) return Promise.resolve(null);
      var t = String(raw).trim();
      return Promise.resolve(t || null);
    }
    return a.list_pi_base_custom().then(function (st) {
      var all = (st && st.ok && Array.isArray(st.all)) ? st.all.slice() : [];
      var CRIAR = '+ Criar novo PI_BASE...';
      var opts = all.slice();
      opts.push(CRIAR);
      var sel = sugestao && all.indexOf(sugestao) >= 0 ? sugestao : all[0];
      var html = '<div style="padding:14px 18px;line-height:1.5">'
        + '<p>O PI <strong>' + escapeHtml(pi) + '</strong> nao pertence '
        + 'a lista padrao. Selecione o PI mais proximo como base:</p>'
        + '<select id="coplan-pi-base-pick" class="select" '
        + 'style="width:100%;margin-top:8px">'
        + opts.map(function (o) {
            var s = (o === sel) ? ' selected' : '';
            return '<option value="' + escapeHtml(o) + '"' + s + '>'
              + escapeHtml(o) + '</option>';
          }).join('')
        + '</select></div>';
      var chosen = null;
      return window.coplanOpenDialog({
        title: 'Selecionar PI_BASE',
        html: html,
        minWidth: '420px',
        buttons: [
          { label: 'Cancelar', act: 'cancel' },
          { label: 'OK', primary: true, act: 'ok' }
        ],
        beforeClose: function (act, dlg) {
          if (act !== 'ok') return true;
          var s = dlg.querySelector('#coplan-pi-base-pick');
          chosen = s ? String(s.value || '').trim() : '';
          return true;
        }
      }).then(function (act) {
        if (act !== 'ok' || !chosen) return null;
        if (chosen !== CRIAR) return chosen;
        return new Promise(function (resolve) {
          var name = window.prompt('Nome do novo PI_BASE:');
          if (name == null) return resolve(null);
          var trimmed = String(name).trim();
          if (!trimmed) return resolve(null);
          if (!a.add_pi_base_custom) {
            C.toast('API add_pi_base_custom indisponivel', 'error');
            return resolve(null);
          }
          a.add_pi_base_custom(trimmed).then(function (r) {
            if (r && r.ok) {
              C.toast('PI_BASE criado: ' + trimmed, 'success');
              resolve(trimmed);
            } else {
              C.toast('Falha ao criar PI_BASE: '
                + ((r && r.error) || '?'), 'error');
              resolve(null);
            }
          });
        });
      });
    });
  }
  C.pickPiBase = pickPiBase;

  function persistPiBaseMapEntry(pi, base) {
    var a = api();
    if (!a || !a.get_pi_base_map || !a.save_pi_base_map) {
      return Promise.resolve(false);
    }
    return a.get_pi_base_map().then(function (cur) {
      var items = (cur && cur.items && typeof cur.items === 'object')
        ? Object.assign({}, cur.items) : {};
      items[pi] = base;
      return a.save_pi_base_map(items);
    });
  }
  C.persistPiBaseMapEntry = persistPiBaseMapEntry;

  // --- helper: re-renderiza chip-list de subestacoes a partir de
  // [principal] + chips beneficiados. Cada SE eh resolvida via
  // get_alimentador_details(alim).se. Dedup case-insensitive, ordem
  // de insercao preservada.
  function recalcSubestacoes() {
    var principal = (C.valOf('cad-sel-alim-principal') || '').trim();
    var chips = (typeof C.getChips === 'function') ? C.getChips() : [];
    var alims = (principal ? [principal] : []).concat(chips);
    var box = $('cad-list-subestacoes');
    if (!box) return;
    if (alims.length === 0) {
      box.innerHTML = '';
      return;
    }
    var a = api();
    if (!a || !a.get_alimentador_details) {
      box.innerHTML = '';
      return;
    }
    var seen = {}; var ordem = []; var pendentes = alims.length;
    function flush() {
      box.innerHTML = ordem.map(function (se) {
        return '<span class="chip">' + escapeHtml(se) + '</span>';
      }).join('');
    }
    alims.forEach(function (al) {
      a.get_alimentador_details(al).then(function (r) {
        if (r && r.ok && r.se) {
          var key = String(r.se).toUpperCase();
          if (!seen[key]) { seen[key] = true; ordem.push(r.se); }
        }
      }).catch(function () { /* swallow */ }).then(function () {
        pendentes--;
        if (pendentes <= 0) flush();
      });
    });
  }
  C.recalcSubestacoes = recalcSubestacoes;

  // M042 removido: Ano editavel tambem em modo edicao (paridade com
  // legado desktop). applyObra/coplan:obra-active garantem disabled=false.

  // --- M043: change em PI -> resolver_pi_base + dialogo de selecao
  // (pickPiBase) se desconhecido. Espelha QInputDialog.getItem do
  // legado (pi_base.py:117) que mostra uma lista das bases ja conhecidas
  // + "+ Criar novo PI_BASE...".
  var pi = $('cad-sel-pi');
  if (pi && !pi.__cadastroBound) {
    pi.__cadastroBound = true;
    pi.addEventListener('change', function () {
      var v = (pi.value || '').trim();
      if (!v) return;
      var a = api();
      if (!a || !a.resolver_pi_base) return;
      a.resolver_pi_base(v).then(function (r) {
        if (!r || !r.ok || r.conhecido) return;
        return pickPiBase(v, r.pi_base || '').then(function (base) {
          if (!base) return;
          return persistPiBaseMapEntry(v, base).then(function (resp) {
            if (resp && resp.ok) {
              C.toast('PI_BASE de "' + v + '" salvo: ' + base, 'success');
            } else if (resp) {
              C.toast('Falha salvando PI_BASE: '
                + ((resp && resp.error) || '?'), 'error');
            }
          });
        });
      });
    });
  }

  // --- M044: change em Alimentador Obra -> autofill + caracteristicas
  // + recalc subestacoes.
  var alim = $('cad-sel-alim-principal');
  if (alim && !alim.__cadastroBound) {
    alim.__cadastroBound = true;
    alim.addEventListener('change', function () {
      var v = (alim.value || '').trim();
      if (!v) {
        recalcSubestacoes();
        return;
      }
      var a = api();
      if (!a) return;
      if (a.get_alimentador_details) {
        a.get_alimentador_details(v).then(function (r) {
          if (!r || !r.ok) {
            C.toast(C.MSG.aviso.dados_alim_nao_carregados, 'warn');
            recalcSubestacoes();
            return;
          }
          if (r.tensao) {
            C.setVal('cad-input-tensao', r.tensao);
            // Fallback: tensao_operacao = tensao quando vazio (parity
            // com salvar_obra_service do desktop).
            if (!C.valOf('cad-input-tensao-oper')) {
              C.setVal('cad-input-tensao-oper', r.tensao);
            }
          }
          if (r.regional)         C.setVal('cad-input-regional', r.regional);
          if (r.superintendencia) C.setVal('cad-input-superintendencia', r.superintendencia);
          if (r.se)               C.setVal('cad-input-se', r.se);
          recalcSubestacoes();
        }).catch(function (err) {
          console.warn('[coplan/cadastro] get_alimentador_details:', err);
          recalcSubestacoes();
        });
      }
      if (a.caracteristicas_por_alimentador) {
        a.caracteristicas_por_alimentador(v).then(function (r) {
          if (r && Array.isArray(r.items)) {
            C.populateSelect('cad-sel-caracteristicas', r.items, { allowEmpty: true });
          }
        }).catch(function () { /* silencioso */ });
      }
    });
  }

  // --- M046: 6 botoes data-act="nome-projeto:*" (delegacao no body).
  // Reproduz o menu "Nome de projetos" do desktop: pre-preenche o
  // campo Projeto com prefixo + (Novo AL) liga Novo Bay = SIM.
  var prefixes = {
    'nova-se':  { projeto: 'Nova_SE_',           novo_bay: null  },
    'novo-al':  { projeto: 'AL_Novo_',           novo_bay: 'SIM' },
    'reconf':   { projeto: 'Reconfiguração_',     novo_bay: null },
    'alivio':   { projeto: 'Alívio_SE_',              novo_bay: null },
    'flex':     { projeto: 'Flexibilização_AL_', novo_bay: null }
  };
  if (!document.body.__cadastroNomeProjBound) {
    document.body.__cadastroNomeProjBound = true;
    document.body.addEventListener('click', function (ev) {
      var btn = ev.target && ev.target.closest
        && ev.target.closest('[data-act^="nome-projeto:"]');
      if (!btn) return;
      var act = btn.getAttribute('data-act') || '';
      var key = act.split(':')[1];
      if (key === 'multi-pi') {
        // M047 (proxima leva) implementa o populate + processamento;
        // por ora, abrir o modal ja garante a UX minima.
        C.showModal('modal-multi-pi');
        return;
      }
      var spec = prefixes[key];
      if (!spec) return;
      C.setVal('cad-input-projeto', spec.projeto);
      if (spec.novo_bay) C.setVal('cad-sel-novo-bay', spec.novo_bay);
      var inp = $('cad-input-projeto');
      if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
    });
  }
})();
</script>
<script>
// =====================================================================
// LEVA 3 - mais listeners (M047, M048, M049, M051, M054, M055)
//   M047 -> Modal Multi-PI: popula checkboxes ao abrir; OK chama
//           resolver_pi_base() + prompt para PIs sem PI_BASE conhecido.
//   M048 -> Chips de Alimentadores Beneficiados: clique em "Adicionar"
//           valida (nao vazio, nao duplicado, sem '_'), insere chip;
//           clique no X (delegacao) remove. Recalcula subestacoes em
//           cada mudanca via coplanCadastro.recalcSubestacoes.
//   M049 -> Validador "sem _": aplicado quando o select e populado
//           via JS (filtra opcoes). Em chip add (M048) tambem rejeita.
//   M051 -> Botao "Calcular Valor da Obra": serializa form, chama
//           calcular_valor_obra, preenche valor_formatado.
//   M054 -> Botao "Limpar Campos": chama coplanCadastro.clearForm().
//   M055 -> Botoes "Configuracoes de Template" (no card Dados Basicos
//           e no rodape) navegam para aba Configuracoes via coplanSetTab.
// =====================================================================
(function () {
  'use strict';
  if (!window.coplanCadastro) return;
  var C = window.coplanCadastro;
  var $ = function (id) { return document.getElementById(id); };
  var api = function () { return (window.pywebview && window.pywebview.api) || null; };

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ---------- M048: chips Alimentadores Beneficiados ----------
  function addBeneficiadoChip(raw) {
    var v = String(raw || '').trim();
    if (!v) {
      C.toast(C.MSG.aviso.alim_vazio_ou_duplicado, 'warn');
      return false;
    }
    // M049: rejeita underscore.
    if (v.indexOf('_') >= 0) {
      C.toast(C.MSG.erro.alim_underscore, 'error');
      return false;
    }
    var box = $('cad-list-alim-benef');
    if (!box) return false;
    var existing = (typeof C.getChips === 'function') ? C.getChips() : [];
    var up = v.toUpperCase();
    for (var i = 0; i < existing.length; i++) {
      if (String(existing[i]).toUpperCase() === up) {
        C.toast(C.MSG.aviso.alim_vazio_ou_duplicado, 'warn');
        return false;
      }
    }
    var span = document.createElement('span');
    span.className = 'chip';
    span.appendChild(document.createTextNode(v));
    var x = document.createElement('i');
    x.setAttribute('data-lucide', 'x');
    x.className = 'x';
    x.style.cursor = 'pointer';
    x.title = 'Remover';
    span.appendChild(x);
    box.appendChild(span);
    if (window.lucide) window.lucide.createIcons();
    if (typeof C.recalcSubestacoes === 'function') C.recalcSubestacoes();
    return true;
  }

  var btnAdd = $('cad-btn-add-benef');
  if (btnAdd && !btnAdd.__cadastroBound) {
    btnAdd.__cadastroBound = true;
    btnAdd.addEventListener('click', function () {
      var sel = $('cad-input-alim-benef');
      var v = sel ? (sel.value || '').trim() : '';
      if (addBeneficiadoChip(v)) {
        if (sel) sel.selectedIndex = sel.options.length > 0 && sel.options[0].value === '' ? 0 : -1;
      }
    });
  }

  // Delegação do X dos chips (remove).
  var listBenef = $('cad-list-alim-benef');
  if (listBenef && !listBenef.__cadastroBound) {
    listBenef.__cadastroBound = true;
    listBenef.addEventListener('click', function (ev) {
      var x = ev.target && ev.target.closest && ev.target.closest('.chip .x, [data-lucide="x"]');
      if (!x) return;
      var chip = x.closest('.chip');
      if (!chip) return;
      chip.parentNode && chip.parentNode.removeChild(chip);
      if (typeof C.recalcSubestacoes === 'function') C.recalcSubestacoes();
    });
  }

  // ---------- M051: Calcular Valor da Obra ----------
  var btnCalc = $('cad-btn-calcular-valor');
  if (btnCalc && !btnCalc.__cadastroBound) {
    btnCalc.__cadastroBound = true;
    btnCalc.addEventListener('click', function () {
      var a = api();
      if (!a || !a.calcular_valor_obra) {
        C.toast('API calcular_valor_obra indisponivel', 'error');
        return;
      }
      // Tenta resolver pi_base server-side antes de chamar o calculo
      // (parity com cadastro_mixin.calcular_valor_obra_handler que
      // chama get_pi_base(prompt_user=False) primeiro).
      var pi = C.valOf('cad-sel-pi');
      var doCalc = function (pi_base) {
        var payload = {
          projeto_investimento:    pi,
          pi_base:                 pi_base || '',
          nivel_tensao:            C.valOf('cad-input-tensao'),
          caracteristicas_material:C.valOf('cad-sel-caracteristicas'),
          nome_regional:           C.valOf('cad-input-regional'),
          quantidade:              C.valOf('cad-input-quantidade'),
          cod:                     C.state.obraEmEdicao || ''
        };
        a.calcular_valor_obra(
          payload.projeto_investimento, payload.pi_base, payload.nivel_tensao,
          payload.caracteristicas_material, payload.nome_regional,
          payload.quantidade, payload.cod
        ).then(function (r) {
          if (r && r.ok) {
            // [FIX] Sempre formata em pt-BR (mesmo se vier como
            // "2487500.0" do backend ou "2.487.500,00" ja formatado).
            var raw = r.valor_formatado || (r.valor != null ? String(r.valor) : '');
            var fmt = (typeof C.fmtValorBr === 'function')
              ? C.fmtValorBr(raw) : raw;
            if (fmt) {
              C.setVal('cad-input-valor', fmt);
              C.toast('Valor calculado: R$ ' + fmt, 'success');
            } else {
              C.toast(C.MSG.aviso.nenhum_valor_unitario, 'warn');
            }
          } else {
            var msg = (r && r.error) ? r.error : C.MSG.aviso.nenhum_valor_unitario;
            C.toast(msg, 'warn');
            if (window.coplanReportError) {
              window.coplanReportError(
                'Calcular Valor (Cadastro)', 'calcular_valor_obra',
                {
                  ok: false,
                  error: r && r.error,
                  chaves_inexistentes: (r && r.chaves_inexistentes) || [],
                  falhas: ((r && r.motivos_falha) || []).map(String),
                  falhas_total: ((r && r.motivos_falha) || []).length,
                });
            }
          }
          // Sucesso com chaves inexistentes -> tambem mostra modal.
          if (r && r.ok && window.coplanReportError
              && ((r.chaves_inexistentes && r.chaves_inexistentes.length)
                  || (r.motivos_falha && r.motivos_falha.length))) {
            window.coplanReportError(
              'Calcular Valor (Cadastro)', 'calcular_valor_obra',
              {
                ok: true,
                chaves_inexistentes: r.chaves_inexistentes || [],
                falhas: (r.motivos_falha || []).map(String),
                falhas_total: (r.motivos_falha || []).length,
              });
          }
        }).catch(function (err) {
          C.toast(C.MSG.erro.calc_valor + (err && err.message || err), 'error');
          if (window.coplanReportError) {
            window.coplanReportError(
              'Calcular Valor (Cadastro)', 'calcular_valor_obra',
              { ok: false, error: String(err && err.message || err) });
          }
        });
      };
      if (a.resolver_pi_base && pi) {
        a.resolver_pi_base(pi).then(function (r) {
          doCalc(r && r.ok ? r.pi_base : '');
        }).catch(function () { doCalc(''); });
      } else {
        doCalc('');
      }
    });
  }

  // ---------- M054: Limpar Campos ----------
  var btnLimpar = $('cad-btn-limpar');
  if (btnLimpar && !btnLimpar.__cadastroBound) {
    btnLimpar.__cadastroBound = true;
    btnLimpar.addEventListener('click', function () {
      C.clearForm();
      C.toast('Campos limpos', 'info');
    });
  }

  // ---------- M055: Configuracoes de Template (2 botoes) ----------
  function gotoTemplates() {
    if (typeof window.coplanSetTab === 'function') {
      window.coplanSetTab('config');
    }
    document.dispatchEvent(new CustomEvent('coplan:focus-config-tab', {
      detail: { tab: 'templates' }
    }));
  }
  // Botao 'cad-btn-templates-bottom' (rodapé) removido a pedido do
  // usuario; sobra apenas 'cad-btn-templates' do card "Dados Basicos".
  ['cad-btn-templates'].forEach(function (id) {
    var b = $(id);
    if (b && !b.__cadastroBound) {
      b.__cadastroBound = true;
      b.addEventListener('click', gotoTemplates);
    }
  });

  // ---------- M047: Modal Multi-PI ----------
  function populateMultiPiList(items) {
    var list = $('multi-pi-list');
    if (!list) return;
    list.innerHTML = '';
    (items || []).forEach(function (pi, idx) {
      var label = document.createElement('label');
      label.style.display = 'flex';
      label.style.alignItems = 'center';
      label.style.gap = '8px';
      label.style.padding = '4px 6px';
      label.style.cursor = 'pointer';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = String(pi);
      cb.id = 'multi-pi-cb-' + idx;
      label.appendChild(cb);
      var sp = document.createElement('span');
      sp.textContent = String(pi);
      label.appendChild(sp);
      list.appendChild(label);
    });
  }

  function openMultiPiModal() {
    var a = api();
    var items = [];
    if (a && a.get_pi_options) {
      a.get_pi_options().then(function (r) {
        if (r && r.ok) {
          var longs = (r.long_names || []).slice();
          (r.bases || []).forEach(function (b) {
            if (longs.indexOf(b) < 0) longs.push(b);
          });
          items = longs;
        }
        populateMultiPiList(items);
      }).catch(function () {
        populateMultiPiList(items);
      });
    } else {
      populateMultiPiList(items);
    }
  }
  // Sobrescreve handler do M046 (que so abria o modal): agora popula.
  document.addEventListener('click', function (ev) {
    var btn = ev.target && ev.target.closest && ev.target.closest('[data-act="nome-projeto:multi-pi"]');
    if (!btn) return;
    setTimeout(openMultiPiModal, 0);
  }, true); // fase de captura para popular antes da delegacao do M046 abrir o modal

  var btnMultiPiOk = $('multi-pi-btn-ok');
  if (btnMultiPiOk && !btnMultiPiOk.__cadastroBound) {
    btnMultiPiOk.__cadastroBound = true;
    btnMultiPiOk.addEventListener('click', function () {
      var checks = Array.prototype.slice.call(
        document.querySelectorAll('#multi-pi-list input[type="checkbox"]:checked')
      );
      var pis = checks.map(function (c) { return c.value; });
      if (pis.length === 0) {
        C.toast('Selecione pelo menos um PI', 'warn');
        return;
      }
      var a = api();
      if (!a || !a.resolver_pi_base) {
        C.state.selectedPis = pis;
        C.hideModal('modal-multi-pi');
        return;
      }
      // Resolve cada PI: se desconhecido, prompt e salva no map.
      var i = 0;
      function step() {
        if (i >= pis.length) {
          C.state.selectedPis = pis.slice();
          C.toast(pis.length + ' PI(s) selecionado(s)', 'info');
          C.hideModal('modal-multi-pi');
          return;
        }
        var pi = pis[i++];
        a.resolver_pi_base(pi).then(function (r) {
          if (r && r.ok && r.conhecido) { step(); return; }
          var sugestao = (r && r.pi_base) || '';
          var entrada = window.prompt(
            'PI "' + pi + '" sem PI_BASE. Informe a sigla (ex: DI):',
            sugestao
          );
          if (entrada == null || !String(entrada).trim()) { step(); return; }
          var base = String(entrada).trim().toUpperCase();
          a.get_pi_base_map().then(function (cur) {
            var items = (cur && cur.items && typeof cur.items === 'object')
              ? Object.assign({}, cur.items) : {};
            items[pi] = base;
            a.save_pi_base_map(items).then(step).catch(step);
          }).catch(step);
        }).catch(step);
      }
      step();
    });
  }
})();
</script>
<script>
// =====================================================================
// LEVA 3 - Salvar Obra (M053) + Ctrl+B (M052) + modais associados
// (M058 Codigo Alterado / M059 Merge Similar / M060 Motivo critico).
// M057 (Gerar descricao) simplificado: auto-gera silenciosamente quando
// payload.descricao_obra esta vazio (registrar como desvio D003).
// =====================================================================
(function () {
  'use strict';
  if (!window.coplanCadastro) return;
  var C = window.coplanCadastro;
  var $ = function (id) { return document.getElementById(id); };
  var api = function () { return (window.pywebview && window.pywebview.api) || null; };

  // ---------- Modal helpers (Promise-based) ----------
  function modalChoice(modalId, buttons) {
    // buttons: { idDoBotao: 'valor' }
    return new Promise(function (resolve) {
      C.showModal(modalId);
      var cleanup = function () {
        Object.keys(buttons).forEach(function (id) {
          var b = $(id);
          if (b && b.__modalHandler) {
            b.removeEventListener('click', b.__modalHandler);
            b.__modalHandler = null;
          }
        });
        // fechamento por X tambem cancela
        var modal = $(modalId);
        if (modal) {
          var closes = modal.querySelectorAll('[data-close]');
          for (var i = 0; i < closes.length; i++) {
            if (closes[i].__modalHandler) {
              closes[i].removeEventListener('click', closes[i].__modalHandler);
              closes[i].__modalHandler = null;
            }
          }
        }
      };
      var pick = function (val) {
        cleanup();
        C.hideModal(modalId);
        resolve(val);
      };
      Object.keys(buttons).forEach(function (id) {
        var b = $(id);
        if (!b) return;
        b.__modalHandler = function () { pick(buttons[id]); };
        b.addEventListener('click', b.__modalHandler);
      });
      var modal = $(modalId);
      if (modal) {
        var closes = modal.querySelectorAll('[data-close]');
        for (var i = 0; i < closes.length; i++) {
          (function (el) {
            el.__modalHandler = function () { pick('cancel'); };
            el.addEventListener('click', el.__modalHandler);
          })(closes[i]);
        }
      }
    });
  }

  // M058 - Codigo Alterado: 'criar' | 'atualizar' | 'cancel'
  function askCodAlterado(antigo, novo) {
    var sa = $('cod-alterado-antigo'); if (sa) sa.textContent = antigo || '—';
    var sn = $('cod-alterado-novo');   if (sn) sn.textContent = novo  || '—';
    return modalChoice('modal-cod-alterado', {
      'cod-alt-btn-criar':     'criar',
      'cod-alt-btn-atualizar': 'atualizar',
      'cod-alt-btn-cancelar':  'cancel'
    });
  }

  // M059 - Merge Similar: 'merge' | 'criar' | 'cancel'
  // Usa #modal-cod-alterado como fallback se #modal-merge-similar nao
  // existir no HTML (PLAN previa M059 mas o HTML so tem #modal-cod-alterado).
  function askMergeSimilar(matches) {
    // Reusa cod-alterado como aviso visual ate o HTML ganhar modal proprio.
    var match = matches && matches[0];
    if (!match) return Promise.resolve('criar');
    var sa = $('cod-alterado-antigo'); if (sa) sa.textContent = (match.cod || '—');
    var sn = $('cod-alterado-novo');   if (sn) sn.textContent = '(novo)';
    return modalChoice('modal-cod-alterado', {
      'cod-alt-btn-atualizar': 'merge',
      'cod-alt-btn-criar':     'criar',
      'cod-alt-btn-cancelar':  'cancel'
    });
  }

  // ---------- M053: tentarSalvar (pipeline async) ----------
  function tentarSalvar(opts) {
    opts = opts || {};
    var a = api();
    if (!a || !a.save_obra) {
      C.toast('API save_obra indisponivel', 'error');
      return Promise.resolve(false);
    }
    var payload = C.serializeForm();

    // [NOVO] Modo "Salvar como NOVA": zera cod do payload e obraEmEdicao
    // para forcar INSERT. Backend vai gerar novo cod no fluxo gerar_cod_pep
    // (passo 4 abaixo). Limpa codigo_item para get_next_codigo_item recalcular.
    if (C.state && C.state.modoCriarNova) {
      payload.cod = '';
      payload.codigo_item = '';
      // Nao toca obraEmEdicao aqui — preserva info para o usuario; o
      // tentarSalvar so usa state.obraEmEdicao em ramo de edicao mais
      // abaixo (passo 4 / askCodAlterado). Tornamos modoCriarNova
      // mais forte na verificacao:
      C.state.__forceInsert = true;
    } else {
      C.state && (C.state.__forceInsert = false);
    }

    // 1) Validacao client/server
    return Promise.resolve()
      .then(function () {
        if (!a.validar_cadastro) return null;
        return a.validar_cadastro(payload);
      })
      .then(function (valid) {
        if (valid && Array.isArray(valid.faltantes) && valid.faltantes.length) {
          C.toast('Campos obrigatorios vazios: ' + valid.faltantes.join(', '), 'error');
          C.setValidation({ obrigatorios: 'err' });
          throw new Error('faltantes');
        }
        if (valid) {
          C.setValidation({ obrigatorios: 'ok' });
          if (Array.isArray(valid.avisos)) {
            valid.avisos.forEach(function (av) {
              if (av.indexOf("contem '_'") >= 0) {
                C.setValidation({ 'alimentadores-sem-underscore': 'err' });
              }
              if (av.indexOf("inicia com 'Obra'") >= 0) {
                C.setValidation({ 'projeto-prefix-obra': 'warn' });
              }
            });
            if (valid.avisos.length === 0) {
              C.setValidation({
                'alimentadores-sem-underscore': 'ok',
                'projeto-prefix-obra': 'ok'
              });
            }
          }
        }

        // 2) Resolver pi_base. Se o PI nao for conhecido, abre o
        // dialogo de selecao (pickPiBase) -- replica QInputDialog do
        // desktop. Usado como salvaguarda caso o change do select
        // cad-sel-pi (M043) nao tenha disparado antes do Salvar.
        if (!payload.pi_base && payload.projeto_investimento && a.resolver_pi_base) {
          return a.resolver_pi_base(payload.projeto_investimento).then(function (r) {
            if (!r || !r.ok) return;
            if (r.conhecido) {
              if (r.pi_base) payload.pi_base = r.pi_base;
              return;
            }
            var piVal = payload.projeto_investimento;
            var picker = (C.pickPiBase || (typeof pickPiBase === 'function' ? pickPiBase : null));
            if (!picker) {
              if (r.pi_base) payload.pi_base = r.pi_base;
              return;
            }
            return picker(piVal, r.pi_base || '').then(function (base) {
              if (!base) {
                if (r.pi_base) payload.pi_base = r.pi_base;
                return;
              }
              payload.pi_base = base;
              var persist = (C.persistPiBaseMapEntry
                || (typeof persistPiBaseMapEntry === 'function'
                    ? persistPiBaseMapEntry : null));
              if (persist) return persist(piVal, base);
            });
          });
        }
      })
      .then(function () {
        // 3) Codigo item se vazio
        if (!payload.codigo_item && payload.nome_projeto && a.db_next_codigo_item) {
          return a.db_next_codigo_item(payload.nome_projeto).then(function (r) {
            if (r && r.ok && r.next != null) {
              var n = String(r.next);
              while (n.length < 3) n = '0' + n;
              payload.codigo_item = n;
              C.setVal('cad-input-item', n);
            }
          });
        }
      })
      .then(function () {
        // 4) COD: em edicao usa o estado preservado; em insert deixa
        // vazio. O servidor (save_obra) auto-gera via
        // CalculationManager.gerar_cod a partir dos campos do form
        // (paridade com codigo5_coplan.py L1127).
        if (C.state.obraEmEdicao && !C.state.__forceInsert) {
          payload.cod = C.state.obraEmEdicao;
        } else {
          payload.cod = '';
        }
        C.setValidation({ 'cod-completo': 'ok' });
      })
      .then(function () {
        // 5) Verificar duplicada semantica (M027 + M059)
        if (C.state.obraEmEdicao || opts.modoMergeResolvido) return;
        if (!a.obras_por_codigo_semelhante) return;
        return a.obras_por_codigo_semelhante(payload).then(function (r) {
          if (!r || !r.ok || !r.matches || !r.matches.length) return;
          return askMergeSimilar(r.matches).then(function (esc) {
            if (esc === 'cancel') throw new Error('cancelled');
            if (esc === 'merge') {
              payload.cod = r.matches[0].cod;
              C.state.obraEmEdicao = r.matches[0].cod;
            }
            // 'criar' segue o fluxo
          });
        });
      })
      .then(function () {
        // 6) Auto-gerar descricao se vazia (M057 simplificado, D003).
        if (payload.descricao_obra) return;
        if (!a.aplicar_template_descricao || !payload.pi_base) return;
        return a.aplicar_template_descricao(payload.pi_base, payload).then(function (r) {
          if (r && r.ok && r.descricao) {
            payload.descricao_obra = r.descricao;
          }
        }).catch(function () { /* silencioso */ });
      })
      .then(function () {
        // 7) save_obra
        return a.save_obra(payload);
      })
      .then(function (resp) {
        if (!resp) {
          C.toast(C.MSG.erro.salvar + 'sem resposta', 'error');
          return false;
        }
        if (resp.ok) {
          var msg = resp.mode === 'update' ? C.MSG.sucesso.atualizada : C.MSG.sucesso.criada;
          C.toast(msg, 'success');
          C.clearForm();
          // Refresh aba Visualizar (se houver listener registrado).
          document.dispatchEvent(new CustomEvent('coplan:obras-changed', {
            detail: { source: 'cadastro:save', cod: resp.cod }
          }));
          return true;
        }
        // Tratamento de erros conhecidos.
        if (resp.blocked === 'despachada') {
          C.toast(C.MSG.aviso.despachada, 'warn');
          return false;
        }
        var err = String(resp.error || '');
        if (/duplicad/i.test(err) || /ja existe/i.test(err)) {
          // [FIX] Em vez de so toast erro, abre modal-cod-alterado
          // oferecendo "Atualizar existente" (vira UPDATE) ou "Cancelar".
          // Paridade com regra desktop: "Ja existe obra X. Atualizar?"
          var codDup = payload.cod || '';
          return askCodAlterado(codDup, codDup).then(function (esc) {
            if (esc === 'cancel') return false;
            if (esc === 'atualizar') {
              // Forca UPDATE: marca obra em edicao e tenta de novo.
              C.state.obraEmEdicao = codDup;
              opts.modoCodAlteradoResolvido = true;
              return tentarSalvar(opts);
            }
            // 'criar' nao faz sentido aqui (cod ja existe) — toast.
            C.toast('Use "Atualizar" ou cancele.', 'warn');
            return false;
          });
        }
        C.toast(C.MSG.erro.salvar + (err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Salvar Obra (Cadastro)', 'save_obra', resp);
        }
        return false;
      })
      .catch(function (err) {
        var msg = err && err.message;
        if (msg === 'cancelled') return false;
        if (msg === 'faltantes') return false;
        console.warn('[coplan/cadastro] tentarSalvar erro:', err);
        C.toast(C.MSG.erro.salvar + (msg || err || '?'), 'error');
        if (window.coplanReportError) {
          window.coplanReportError(
            'Salvar Obra (Cadastro)', 'save_obra',
            { ok: false, error: String(msg || err || '?') });
        }
        return false;
      });
  }
  C.tentarSalvar = tentarSalvar;

  // ---------- M053: bind do botao Salvar Obra ----------
  var btnSalvar = $('cad-btn-salvar');
  if (btnSalvar && !btnSalvar.__cadastroBound) {
    btnSalvar.__cadastroBound = true;
    btnSalvar.addEventListener('click', function () { tentarSalvar({}); });
  }

  // ---------- M052: atalho Ctrl+B ----------
  if (!window.__cadastroCtrlBBound) {
    window.__cadastroCtrlBBound = true;
    document.addEventListener('keydown', function (e) {
      var isB = (e.key === 'b' || e.key === 'B' || e.keyCode === 66);
      var mod = e.ctrlKey || e.metaKey;
      if (!isB || !mod) return;
      var active = document.querySelector('.tab-panel.active');
      if (!active || active.id !== 'tab-cadastro') return;
      e.preventDefault();
      e.stopPropagation();
      var b = $('cad-btn-salvar');
      if (b) b.click();
    });
  }
})();
</script>
<script>
// =====================================================================
// LEVA 3 - sidebar live + Escolher Projeto + COD preview + Modal PI_BASE
//   M056 -> #cad-btn-escolher abre #modal-projeto-busca; OK chama
//           projeto_fetch_obras e preenche Ano/Alim/Regional/Sup./
//           Tensao/SE/Item da PRIMEIRA obra do projeto.
//   M061 -> validacao ao vivo na sidebar (debounce 200ms): escuta
//           input/change em campos relevantes -> chama validar_cadastro
//           + regex local + gerar_cod_pep -> setValidation.
//   M062 -> sidebar "Ultima modificacao" preenchida quando applyObra
//           carrega obra com data_modificacao/usuario; oculta em modo
//           nova obra (clearForm).
//   M073 -> preview COD reativo: input em PI/Ano/Item -> debounce 300ms
//           -> gerar_cod_pep -> #cad-input-cod-pep + data-check
//           "cod-completo".
//   M080 -> modal Gerenciar PI_BASE: lista o map em <ul id="pi-list">,
//           botoes Adicionar/Renomear/Remover/Restaurar persistem via
//           save_pi_base_map (merge ou reset).
// =====================================================================
(function () {
  'use strict';
  if (!window.coplanCadastro) return;
  var C = window.coplanCadastro;
  var $ = function (id) { return document.getElementById(id); };
  var api = function () { return (window.pywebview && window.pywebview.api) || null; };

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function debounce(fn, ms) {
    var t = null;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  // ---------- M056: Escolher Projeto ----------
  var btnEscolher = $('cad-btn-escolher');
  var projetoBuscaSelecionado = null;

  function renderProjetosTbody(items, filtro) {
    var tbody = $('projeto-busca-tbody');
    if (!tbody) return;
    var rx = filtro ? new RegExp(filtro.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') : null;
    var filtrado = (items || []).filter(function (it) {
      if (!rx) return true;
      return rx.test(it);
    });
    tbody.innerHTML = filtrado.map(function (nome) {
      return '<tr data-projeto="' + escapeHtml(nome) + '" style="cursor:pointer;">'
        + '<td style="padding:6px 10px;">' + escapeHtml(nome) + '</td>'
        + '<td style="padding:6px 10px;color:var(--text-soft);">—</td>'
        + '<td style="padding:6px 10px;text-align:right;color:var(--text-soft);">—</td>'
        + '</tr>';
    }).join('');
    // Atualiza contadores assincronamente (1 call por linha — ok pra dezenas).
    var btnOk = $('projeto-busca-btn-ok');
    if (btnOk) btnOk.disabled = true;
    projetoBuscaSelecionado = null;
  }

  function abrirModalProjeto() {
    var a = api();
    if (!a || !a.list_projetos) {
      C.toast('API list_projetos indisponivel', 'error');
      return;
    }
    a.list_projetos().then(function (r) {
      var items = (r && r.ok && r.items) ? r.items : [];
      renderProjetosTbody(items, '');
      C.showModal('modal-projeto-busca');
      var filtroInp = $('projeto-busca-filtro');
      if (filtroInp) {
        filtroInp.value = '';
        filtroInp.oninput = function () {
          renderProjetosTbody(items, filtroInp.value || '');
        };
      }
      if (!items.length) {
        C.toast('Nenhum projeto encontrado no banco', 'warn');
      }
    }).catch(function (err) {
      C.toast('Falha ao listar projetos: ' + (err && err.message || err), 'error');
    });
  }
  // [FIX] Exposicao para o hotfix delegado (que tentava window.coplan-
  // CadastroAbrirProjeto e caia em fallback caseiro). Agora ambos
  // chamam o mesmo abrirModalProjeto consistente.
  window.coplanCadastroAbrirProjeto = abrirModalProjeto;

  if (btnEscolher && !btnEscolher.__cadastroBound) {
    btnEscolher.__cadastroBound = true;
    btnEscolher.addEventListener('click', abrirModalProjeto);
  }

  var tbodyProj = $('projeto-busca-tbody');
  if (tbodyProj && !tbodyProj.__cadastroBound) {
    tbodyProj.__cadastroBound = true;
    tbodyProj.addEventListener('click', function (ev) {
      var tr = ev.target && ev.target.closest && ev.target.closest('tr[data-projeto]');
      if (!tr) return;
      // visual select
      var prev = tbodyProj.querySelector('tr.selected');
      if (prev) prev.classList.remove('selected');
      tr.classList.add('selected');
      tr.style.background = 'var(--surface-2)';
      if (prev) prev.style.background = '';
      projetoBuscaSelecionado = tr.getAttribute('data-projeto') || '';
      var btnOk = $('projeto-busca-btn-ok');
      if (btnOk) btnOk.disabled = !projetoBuscaSelecionado;
    });
  }

  function carregarDadosProjeto(nomeProjeto) {
    var a = api();
    if (!a || !a.projeto_fetch_obras) return;
    a.projeto_fetch_obras(nomeProjeto).then(function (r) {
      if (!r || !r.ok || !Array.isArray(r.obras) || r.obras.length === 0) {
        C.toast(C.MSG.aviso.nenhuma_obra_no_projeto, 'warn');
        return;
      }
      var primeira = r.obras[0];
      C.setVal('cad-input-projeto', nomeProjeto);
      C.setVal('cad-sel-ano',                primeira.ano_);
      C.setVal('cad-sel-alim-principal',     primeira.alimentador_principal);
      C.setVal('cad-input-regional',         primeira.nome_regional);
      C.setVal('cad-input-superintendencia', primeira.nome_superintendencia);
      C.setVal('cad-input-tensao',           primeira.nivel_tensao_obra);
      C.setVal('cad-input-tensao-oper',
        primeira.tensao_operacao || primeira.nivel_tensao_obra);
      C.setVal('cad-input-se',               primeira.subestacao);
      // Proximo codigo_item
      if (a.db_next_codigo_item) {
        a.db_next_codigo_item(nomeProjeto).then(function (n) {
          if (n && n.ok && n.next != null) {
            var s = String(n.next);
            while (s.length < 3) s = '0' + s;
            C.setVal('cad-input-item', s);
          }
        });
      }
      C.toast('Projeto "' + nomeProjeto + '" carregado (' + r.obras.length + ' obras)', 'info');
    }).catch(function (err) {
      C.toast(C.MSG.erro.carregar_projeto + (err && err.message || err), 'error');
    });
  }

  var btnProjOk = $('projeto-busca-btn-ok');
  if (btnProjOk && !btnProjOk.__cadastroBound) {
    btnProjOk.__cadastroBound = true;
    btnProjOk.addEventListener('click', function () {
      if (!projetoBuscaSelecionado) return;
      C.hideModal('modal-projeto-busca');
      carregarDadosProjeto(projetoBuscaSelecionado);
      projetoBuscaSelecionado = null;
    });
  }

  // ---------- M061 + M073: validacao live + preview de COD ----------
  function recalcLive() {
    var a = api();
    var payload = C.serializeForm();
    // Validacao server (cobre RB-DISTRIBUICAO)
    if (a && a.validar_cadastro) {
      a.validar_cadastro(payload).then(function (v) {
        if (!v) return;
        C.setValidation({
          obrigatorios: (Array.isArray(v.faltantes) && v.faltantes.length) ? 'err' : 'ok'
        });
        var temUnderscore = (v.avisos || []).some(function (s) {
          return /contem '_'/.test(s);
        });
        var iniciaObra = (v.avisos || []).some(function (s) {
          return /inicia com 'Obra'/.test(s);
        });
        C.setValidation({
          'alimentadores-sem-underscore': temUnderscore ? 'err' : 'ok',
          'projeto-prefix-obra':          iniciaObra    ? 'warn' : 'ok'
        });
      }).catch(function () { /* silencioso */ });
    }
    // Preview de COD removido: o COD e' gerado automaticamente no
    // servidor (save_obra) via CalculationManager.gerar_cod, paridade
    // com o legado desktop. Sem preview live no campo.
    C.setValidation({ 'cod-completo': 'ok' });
    // Verificacao de alimentador encontrado no apoio
    if (a && a.get_alimentador_details) {
      var alim = payload.alimentador_principal;
      if (alim) {
        a.get_alimentador_details(alim).then(function (r) {
          C.setValidation({
            'alim-encontrado-apoio': (r && r.ok) ? 'ok' : 'warn'
          });
        }).catch(function () {
          C.setValidation({ 'alim-encontrado-apoio': 'warn' });
        });
      } else {
        C.setValidation({ 'alim-encontrado-apoio': 'pending' });
      }
    }
  }
  var recalcLiveDebounced = debounce(recalcLive, 250);
  C.recalcLive = recalcLiveDebounced;

  // Bind nos campos relevantes (idempotente).
  var liveTriggers = [
    'cad-sel-ano', 'cad-sel-pi', 'cad-input-item',
    'cad-input-projeto', 'cad-input-coord-fim', 'cad-input-quantidade',
    'cad-sel-pacote', 'cad-sel-caracteristicas', 'cad-sel-manobra',
    'cad-sel-alim-principal', 'cad-input-tensao', 'cad-input-regional'
  ];
  liveTriggers.forEach(function (id) {
    var el = $(id);
    if (!el || el.__liveBound) return;
    el.__liveBound = true;
    var ev = el.tagName === 'SELECT' ? 'change' : 'input';
    el.addEventListener(ev, recalcLiveDebounced);
    if (el.tagName !== 'SELECT') el.addEventListener('change', recalcLiveDebounced);
  });
  // Tambem dispara em mudanca dos chips (M048 ja chama recalcSubestacoes;
  // adicionamos chamada para a sidebar tambem).
  var listBenef = $('cad-list-alim-benef');
  if (listBenef && !listBenef.__liveObs) {
    listBenef.__liveObs = true;
    var mo = new MutationObserver(recalcLiveDebounced);
    mo.observe(listBenef, { childList: true });
  }

  // ---------- M062: Sidebar "Ultima modificacao" ----------
  function showModif(autor, data, desc) {
    var card = $('cad-aside-modif');
    if (!card) return;
    if (!autor && !data) {
      card.style.display = 'none';
      return;
    }
    var a = $('cad-modif-autor');
    var d = $('cad-modif-data');
    var x = $('cad-modif-desc');
    if (a) a.textContent = autor || '—';
    if (d) d.textContent = data || '—';
    if (x) x.textContent = desc || '';
    card.style.display = '';
  }
  function hideModif() {
    var card = $('cad-aside-modif');
    if (card) card.style.display = 'none';
  }
  C.showModif = showModif;
  C.hideModif = hideModif;

  // Wrap applyObra/clearForm para ligar/desligar a sidebar.
  if (typeof C.applyObra === 'function' && !C.__modifWrapped) {
    C.__modifWrapped = true;
    var origApply = C.applyObra;
    C.applyObra = function (obra) {
      var r = origApply.apply(this, arguments);
      try {
        if (obra) {
          var autor = obra.usuario_modificacao || obra.usuario || '';
          var dt    = obra.data_modificacao    || obra.data    || '';
          // Descricao opcional: ultima entrada do historico.
          var hist  = String(obra.historico || '');
          var desc  = '';
          if (hist) {
            var lines = hist.split(/\n|\r\n/);
            desc = (lines[lines.length - 1] || '').trim();
          }
          if (autor || dt) showModif(autor, dt, desc);
          else hideModif();
        } else {
          hideModif();
        }
      } catch (e) { /* swallow */ }
      // dispara recalc live para refletir o estado da obra carregada
      recalcLiveDebounced();
      // G060 (Ganhos): notifica outras abas que ha uma obra ativa.
      try {
        var benef = (obra && obra.alimentadores_beneficiados) || '';
        var benef_list = [];
        if (Array.isArray(benef)) benef_list = benef.slice();
        else if (benef) benef_list = String(benef).split(/[;,]/).map(function (s) {
          return s.trim();
        }).filter(Boolean);
        document.dispatchEvent(new CustomEvent('coplan:obra-active', {
          detail: {
            cod: (obra && obra.cod) || '',
            alim_principal: (obra && (obra.alimentador_principal || obra.alimentador)) || '',
            alim_beneficiados: benef_list,
            pi: (obra && obra.projeto_investimento) || '',
            pi_base: (obra && obra.pi_base) || '',
            // [FIX Ganhos] Anexa a obra completa para o listener da aba
            // Ganhos popular a tabela #ganhos-tbody com os parametros
            // ja salvos (carregamento_inicial, tensao_min_final, etc.).
            obra: obra || {}
          }
        }));
      } catch (e2) { /* swallow */ }
      return r;
    };
    var origClear = C.clearForm;
    C.clearForm = function () {
      var r = origClear.apply(this, arguments);
      hideModif();
      // Reset visual da sidebar para 'pending'.
      ['obrigatorios','alimentadores-sem-underscore','projeto-prefix-obra',
       'cod-completo','alim-encontrado-apoio'].forEach(function (k) {
        C.setValidation((function () { var o = {}; o[k] = 'pending'; return o; })());
      });
      // G060 (Ganhos): obra desativada — outras abas devem limpar state.
      try {
        document.dispatchEvent(new CustomEvent('coplan:obra-active', {
          detail: { cod: '', alim_principal: '', alim_beneficiados: [],
                    pi: '', pi_base: '' }
        }));
      } catch (e3) { /* swallow */ }
      return r;
    };
  }

  // ---------- M080: Modal Gerenciar PI_BASE ----------
  // Renderiza defaults (read-only, badge) + custom (com botao remover),
  // espelhando open_manage_pi_base_dialog do desktop (cadastro_mixin.py).
  // Persistencia via list_pi_base_custom/add_pi_base_custom/
  // remove_pi_base_custom -- nao mexe em pi_base_map (esse é mapping
  // PI->base, manipulado durante o prompt do cadastro).
  function renderPiList(state) {
    var ul = $('pi-list');
    if (!ul) return;
    var custom = (state && state.custom) || [];
    var all    = (state && state.all)    || [];
    var customUpper = custom.map(function (c) { return String(c).toUpperCase(); });
    var defaults = all.filter(function (a) {
      return customUpper.indexOf(String(a).toUpperCase()) === -1;
    });
    ul.innerHTML = '';
    defaults.forEach(function (n) {
      var li = document.createElement('li');
      li.className = 'row';
      li.setAttribute('data-pi-name', n);
      li.setAttribute('data-pi-default', '1');
      li.style.cssText = 'padding:8px 12px;border-bottom:1px solid var(--border);cursor:pointer;';
      li.innerHTML = '<span class="mono grow">' + escapeHtml(n) + '</span>'
        + '<span style="font-size:10px;color:var(--text-soft);'
        + 'background:var(--surface-2);padding:2px 6px;border-radius:3px;'
        + 'margin-right:8px;">default</span>'
        + '<button class="btn ghost sm" data-pi-act="remove" type="button" title="Ocultar este PI_BASE default"><i data-lucide="trash-2"></i></button>';
      ul.appendChild(li);
    });
    custom.forEach(function (n) {
      var li = document.createElement('li');
      li.className = 'row';
      li.setAttribute('data-pi-name', n);
      li.style.cssText = 'padding:8px 12px;border-bottom:1px solid var(--border);cursor:pointer;';
      li.innerHTML = '<span class="mono grow">' + escapeHtml(n) + '</span>'
        + '<button class="btn ghost sm" data-pi-act="remove" type="button" title="Remover PI_BASE"><i data-lucide="trash-2"></i></button>';
      ul.appendChild(li);
    });
    if (window.lucide) window.lucide.createIcons();
  }

  function loadPiList() {
    var a = api();
    if (!a || !a.list_pi_base_custom) return Promise.resolve({});
    return a.list_pi_base_custom().then(function (r) {
      var state = (r && r.ok) ? r : { custom: [], all: [] };
      renderPiList(state);
      return state;
    });
  }
  C.loadPiList = loadPiList;
  // Expor tambem com o nome usado por outros módulos.
  window.coplanLoadPiList = loadPiList;

  // Selecao + clique em botao remover por linha.
  var piSelected = null;
  var ulPi = $('pi-list');
  if (ulPi && !ulPi.__cadastroBound) {
    ulPi.__cadastroBound = true;
    ulPi.addEventListener('click', function (ev) {
      var btn = ev.target && ev.target.closest && ev.target.closest('button[data-pi-act]');
      var li  = ev.target && ev.target.closest && ev.target.closest('li[data-pi-name]');
      if (!li) {
        piSelected = null;
        if ($('pi-btn-remove')) $('pi-btn-remove').disabled = true;
        return;
      }
      Array.prototype.forEach.call(ulPi.querySelectorAll('li'), function (n) {
        n.style.background = '';
      });
      li.style.background = 'var(--surface-2)';
      piSelected = li.getAttribute('data-pi-name') || null;
      if ($('pi-btn-remove')) $('pi-btn-remove').disabled = !piSelected;
      // Rename nao tem API equivalente (legado tambem nao tinha um endpoint
      // unico -- remapeia pi_base_map + templates); deixa desabilitado.
      if ($('pi-btn-rename')) $('pi-btn-rename').disabled = true;
      if (btn) {
        var act = btn.getAttribute('data-pi-act');
        if (act === 'remove') doRemovePi(piSelected);
      }
    });
  }

  function doAddPi() {
    var input = $('pi-input-novo');
    var v = String((input && input.value) || '').trim();
    if (!v) {
      C.toast('Digite o nome do novo PI_BASE', 'warn');
      if (input) input.focus();
      return;
    }
    var a = api();
    if (!a || !a.add_pi_base_custom) {
      C.toast('API add_pi_base_custom indisponivel', 'error');
      return;
    }
    a.add_pi_base_custom(v).then(function (st) {
      if (st && st.ok) {
        renderPiList(st);
        if (input) input.value = '';
        C.toast('PI_BASE adicionado: ' + v, 'success');
      } else {
        C.toast('Falha: ' + ((st && st.error) || '?'), 'error');
      }
    });
  }

  function doRemovePi(pi) {
    if (!pi) return;
    // Defaults nao sao apagados; sao marcados como ocultos via
    // pi_base_hidden_defaults (re-exibiveis com Restaurar padroes ou
    // adicionando o nome de volta).
    var li = ulPi && ulPi.querySelector('li[data-pi-name="' + pi.replace(/"/g, '\"') + '"]');
    var isDefault = li && li.getAttribute('data-pi-default') === '1';
    var msg = isDefault
      ? 'Ocultar o PI_BASE default "' + pi + '"? '
        + 'Voce pode restaura-lo depois clicando em "Restaurar padroes" '
        + 'ou re-adicionando o mesmo nome.'
      : 'Remover PI_BASE "' + pi + '"?';
    if (!window.confirm(msg)) return;
    var a = api();
    if (!a || !a.remove_pi_base_custom) {
      C.toast('API remove_pi_base_custom indisponivel', 'error');
      return;
    }
    a.remove_pi_base_custom(pi).then(function (st) {
      if (st && st.ok) {
        renderPiList(st);
        C.toast('PI_BASE removido: ' + pi, 'success');
        piSelected = null;
        if ($('pi-btn-remove')) $('pi-btn-remove').disabled = true;
      } else {
        C.toast('Falha: ' + ((st && st.error) || '?'), 'error');
      }
    });
  }

  function doRestorePi() {
    if (!window.confirm('Restaurar padrões? Isso remove TODOS os PI_BASE customizados e reexibe quaisquer defaults ocultos.')) return;
    var a = api();
    if (!a || !a.list_pi_base_custom || !a.remove_pi_base_custom
        || !a.add_pi_base_custom) {
      C.toast('API indisponivel', 'error');
      return;
    }
    a.list_pi_base_custom().then(function (st) {
      var custom = (st && st.custom) || [];
      var hidden = (st && st.hidden_defaults) || [];
      if (!custom.length && !hidden.length) {
        C.toast('Nada para restaurar', 'info');
        return;
      }
      var seq = Promise.resolve();
      custom.forEach(function (n) {
        seq = seq.then(function () { return a.remove_pi_base_custom(n); });
      });
      // add_pi_base_custom no nome de um default oculto faz un-hide
      // (consome a entrada de pi_base_hidden_defaults e nao adiciona ao
      // pi_base_custom).
      hidden.forEach(function (n) {
        seq = seq.then(function () { return a.add_pi_base_custom(n); });
      });
      seq.then(loadPiList).then(function () {
        C.toast('PI_BASE restaurado aos padrões', 'success');
      });
    });
  }

  var btnAdd = $('pi-btn-add');
  if (btnAdd && !btnAdd.__cadastroBound) {
    btnAdd.__cadastroBound = true;
    btnAdd.addEventListener('click', doAddPi);
  }
  var btnRestore = $('pi-btn-restore');
  if (btnRestore && !btnRestore.__cadastroBound) {
    btnRestore.__cadastroBound = true;
    btnRestore.addEventListener('click', doRestorePi);
  }
  var btnRem = $('pi-btn-remove');
  if (btnRem && !btnRem.__cadastroBound) {
    btnRem.__cadastroBound = true;
    btnRem.addEventListener('click', function () { doRemovePi(piSelected); });
  }
  // Enter no input adiciona.
  var inpNovo = $('pi-input-novo');
  if (inpNovo && !inpNovo.__cadastroBound) {
    inpNovo.__cadastroBound = true;
    inpNovo.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); doAddPi(); }
    });
  }

  // Carrega lista quando o modal abrir.
  var btnAbrirModalPi = $('btn-modal-pi');
  if (btnAbrirModalPi && !btnAbrirModalPi.__cadastroPiLoad) {
    btnAbrirModalPi.__cadastroPiLoad = true;
    btnAbrirModalPi.addEventListener('click', function () {
      setTimeout(loadPiList, 0);
    });
  }
})();
</script>
