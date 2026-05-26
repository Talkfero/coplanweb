<script>
(function () {
  // ---- Fase F: Painel "Analise Tecnica por Alimentador" no Cadastro
  // Wireia 12 APIs calc_*: tensoes/min/max, linha_min, carregamento,
  // perdas, demanda_maxima, chi_ci, contas_contratos, contas_beneficiadas,
  // nota_carregamento/min/max. Le os arquivos tecnicos via _read_tecnico_files
  // (ja embutido no _ensure_calc_manager do backend).
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function fmtN(v, dec) {
    if (v == null) return '—';
    var n = Number(v);
    if (isNaN(n)) return '—';
    return n.toLocaleString('pt-BR', {
      minimumFractionDigits: dec == null ? 2 : dec,
      maximumFractionDigits: dec == null ? 2 : dec,
    });
  }
  function toast(msg, level) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, level || 'info');
    }
  }
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
  function getAlimentadores(scope) {
    var alims = [];
    var alimPrincipal = (findFieldByLabel(scope, 'alimentador obra') || {}).value || '';
    if (alimPrincipal) alims.push(String(alimPrincipal).trim());
    // Beneficiados (chips no card "Alimentadores e Subestações...")
    var cards = scope.querySelectorAll('.card');
    cards.forEach(function (c) {
      var t = c.querySelector('.card-title');
      if (!t) return;
      if (norm(t.textContent).indexOf('alimentadores e subesta') !== 0) return;
      var lists = c.querySelectorAll('.chip-list');
      if (!lists.length) return;
      lists[0].querySelectorAll('.chip').forEach(function (chip) {
        var v = (chip.dataset && chip.dataset.alim)
          ? chip.dataset.alim
          : (chip.firstChild && chip.firstChild.nodeType === 3
              ? chip.firstChild.textContent.trim()
              : chip.textContent.trim());
        if (v && alims.indexOf(v) === -1) alims.push(v);
      });
    });
    return alims;
  }
  function ensureAnalisePanel() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return null;
    var card = document.getElementById('coplan-analise-tecnica-card');
    if (card) return card;
    card = document.createElement('div');
    card.id = 'coplan-analise-tecnica-card';
    card.className = 'card';
    card.style.marginTop = '12px';
    card.innerHTML =
      '<div class="card-header">'
    +   '<div class="card-title">'
    +     '<i data-lucide="zap"></i>'
    +     ' Analise Tecnica por Alimentador</div>'
    +   '<span style="margin-left:auto;display:flex;gap:6px;">'
    +     '<button id="coplan-btn-analise-run" class="btn">'
    +       '<i data-lucide="play"></i> Calcular tudo</button>'
    +     '<button id="coplan-btn-analise-clear" class="btn">'
    +       '<i data-lucide="x"></i> Limpar</button>'
    +   '</span>'
    + '</div>'
    + '<div class="card-body" style="display:flex;flex-direction:column;gap:10px;">'
    +   '<div id="coplan-analise-alims" style="font-size:12px;color:var(--text-soft);">'
    +     'Alimentadores serao lidos do form ao clicar Calcular.</div>'
    +   '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">'
    +     '<div id="coplan-analise-tensao" class="analise-block"></div>'
    +     '<div id="coplan-analise-carreg" class="analise-block"></div>'
    +     '<div id="coplan-analise-perdas" class="analise-block"></div>'
    +     '<div id="coplan-analise-demanda" class="analise-block"></div>'
    +     '<div id="coplan-analise-chi-ci" class="analise-block"></div>'
    +     '<div id="coplan-analise-contas" class="analise-block"></div>'
    +   '</div>'
    +   '<div style="border-top:1px solid var(--border);padding-top:8px;">'
    +     '<div style="font-weight:600;margin-bottom:6px;font-size:12px;">'
    +       '<i data-lucide="award" style="width:13px;height:13px;"></i>'
    +       ' Notas calculadas (a partir dos valores acima + form)</div>'
    +     '<div id="coplan-analise-notas" style="display:grid;'
    +          'grid-template-columns:repeat(3,1fr);gap:8px;font-size:12px;">'
    +     '</div>'
    +   '</div>'
    + '</div>';
    scope.appendChild(card);
    if (window.lucide) lucide.createIcons();
    return card;
  }
  function renderBlock(id, title, lines) {
    var el = document.getElementById(id);
    if (!el) return;
    var html = '<div style="font-weight:600;font-size:12px;margin-bottom:4px;'
             + 'color:var(--text);">' + esc(title) + '</div>';
    if (!lines.length) {
      html += '<div style="font-size:11px;color:var(--text-soft);">—</div>';
    } else {
      html += '<div style="font-size:12px;line-height:1.5;font-family:monospace;">'
            + lines.map(function (l) {
                return l.label
                  ? '<span style="color:var(--text-soft);">' + esc(l.label) + ':</span> '
                    + esc(l.value)
                  : esc(l.value);
              }).join('<br>')
            + '</div>';
    }
    el.innerHTML = html;
  }
  function renderNota(id, label, nota, criterio) {
    var n = (nota == null) ? '—' : String(nota);
    var color = (nota == null) ? 'var(--text-soft)'
              : (nota >= 7) ? 'var(--danger,#dc2626)'
              : (nota >= 4) ? 'var(--warning,#f59e0b)'
              : 'var(--success,#16a34a)';
    return '<div style="padding:6px 10px;background:var(--surface-2,#f8fafc);'
         + 'border:1px solid var(--border);border-radius:6px;">'
         + '<div style="font-size:11px;color:var(--text-soft);">' + esc(label) + '</div>'
         + '<div style="font-size:18px;font-weight:700;color:' + color + ';">'
         + n + '</div>'
         + '<div style="font-size:10px;color:var(--text-soft);">'
         + esc(criterio || '') + '</div>'
         + '</div>';
  }
  function clearResults() {
    ['coplan-analise-tensao','coplan-analise-carreg','coplan-analise-perdas',
     'coplan-analise-demanda','coplan-analise-chi-ci','coplan-analise-contas']
    .forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = '';
    });
    var notas = document.getElementById('coplan-analise-notas');
    if (notas) notas.innerHTML = '';
  }
  function runAnalise() {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return;
    var api = window.pywebview && window.pywebview.api;
    if (!api) { toast('API indisponivel', 'error'); return; }
    var alims = getAlimentadores(scope);
    var alimsBox = document.getElementById('coplan-analise-alims');
    if (!alims.length) {
      if (alimsBox) {
        alimsBox.innerHTML = '<i data-lucide="alert-triangle" '
          + 'style="width:13px;height:13px;color:var(--warning);"></i> '
          + 'Sem alimentadores -- preencha "Alimentador Obra" + beneficiados.';
        if (window.lucide) lucide.createIcons();
      }
      return;
    }
    if (alimsBox) {
      alimsBox.innerHTML = '<i data-lucide="check-circle-2" '
        + 'style="width:13px;height:13px;color:var(--success);"></i> '
        + 'Calculando para: <strong>' + esc(alims.join(', ')) + '</strong>';
      if (window.lucide) lucide.createIcons();
    }

    // Recolhe valores do form pra calcular notas
    var carregInicialStr = (findFieldByLabel(scope, 'carregamento') || {}).value || '';
    var tensaoMinStr = (findFieldByLabel(scope, 'tensao min') || {}).value || '';
    var tensaoMaxStr = (findFieldByLabel(scope, 'tensao max') || {}).value || '';
    function num(s) {
      var v = parseFloat(String(s || '').replace(',', '.'));
      return isNaN(v) ? 0 : v;
    }
    var carregInicial = num(carregInicialStr);
    var tmin_ini = num(tensaoMinStr);
    var tmax_ini = num(tensaoMaxStr);

    var pi = (findFieldByLabel(scope, 'projeto de investimento') || {}).value || '';

    // Dispara as 9 calculos em paralelo
    Promise.all([
      api.calc_tensoes(alims).catch(function (e) { return null; }),
      api.calc_tensao_linha_minima(alims).catch(function (e) { return null; }),
      api.calc_tensoes_max(alims).catch(function (e) { return null; }),
      api.calc_carregamento(alims).catch(function (e) { return null; }),
      api.calc_perdas(alims).catch(function (e) { return null; }),
      api.calc_demanda_maxima(alims).catch(function (e) { return null; }),
      api.calc_chi_ci(alims).catch(function (e) { return null; }),
      api.calc_contas_contratos(alims).catch(function (e) { return null; }),
      pi ? api.calc_contas_contratos_beneficiadas(alims, pi)
              .catch(function (e) { return null; })
         : Promise.resolve(null),
    ]).then(function (R) {
      var tensoes = R[0], linhaMin = R[1], tensoesMax = R[2];
      var carreg = R[3], perdas = R[4], demanda = R[5];
      var chici = R[6], contas = R[7], beneficiadas = R[8];

      // ---- Bloco Tensao ----
      var tLines = [];
      if (tensoes && tensoes.ok) {
        tLines.push({label: 'Tensao min',         value: fmtN(tensoes.tensao_min, 4)});
        tLines.push({label: 'Tensao media min',   value: fmtN(tensoes.tensao_media_min, 4)});
      }
      if (tensoesMax && tensoesMax.ok) {
        tLines.push({label: 'Tensao max',         value: fmtN(tensoesMax.tensao_max, 4)});
      }
      if (linhaMin && linhaMin.ok) {
        tLines.push({label: 'Tensao linha min',   value: fmtN(linhaMin.tensao_min_linha, 4)});
      }
      renderBlock('coplan-analise-tensao', 'Tensao (pu)', tLines);

      // ---- Bloco Carregamento ----
      var cLines = [];
      if (carreg && carreg.ok) {
        cLines.push({label: 'Pior trecho', value: fmtN(carreg.carregamento, 1) + '%'});
      }
      renderBlock('coplan-analise-carreg', 'Carregamento', cLines);

      // ---- Bloco Perdas ----
      var pLines = [];
      if (perdas && perdas.ok) {
        var pp = perdas.perdas_por_patamar || {};
        Object.keys(pp).forEach(function (k) {
          pLines.push({label: k, value: fmtN(pp[k], 2) + ' kW'});
        });
        pLines.push({label: 'Maior',  value: fmtN(perdas.maior_perda, 2) + ' kW'});
      }
      renderBlock('coplan-analise-perdas', 'Perdas (kW)', pLines);

      // ---- Bloco Demanda ----
      var dLines = [];
      if (demanda && demanda.ok) {
        var dpa = demanda.demanda_por_alim || {};
        Object.keys(dpa).forEach(function (k) {
          dLines.push({label: k, value: fmtN(dpa[k], 2) + ' MW'});
        });
      }
      renderBlock('coplan-analise-demanda', 'Demanda max coincidente', dLines);

      // ---- Bloco CHI/CI ----
      var ccLines = [];
      if (chici && chici.ok) {
        ccLines.push({label: 'CHI', value: fmtN(chici.chi, 4)});
        ccLines.push({label: 'CI',  value: fmtN(chici.ci, 4)});
      }
      renderBlock('coplan-analise-chi-ci', 'Confiabilidade', ccLines);

      // ---- Bloco Contas ----
      var ctLines = [];
      if (contas && contas.ok) {
        ctLines.push({label: 'Antes',  value: String(contas.antes)});
        ctLines.push({label: 'Depois', value: String(contas.depois)});
      }
      if (beneficiadas && beneficiadas.ok) {
        ctLines.push({label: 'Beneficiadas (PI)', value: String(beneficiadas.total)});
      }
      renderBlock('coplan-analise-contas', 'Contas/Contratos', ctLines);

      // ---- Notas calculadas (usa valores do form + do calc) ----
      var carregMax = (carreg && carreg.ok && carreg.carregamento) || 0;
      var tminAtual = (tensoes && tensoes.ok && tensoes.tensao_min) || 0;
      var tmaxAtual = (tensoesMax && tensoesMax.ok && tensoesMax.tensao_max) || 0;

      Promise.all([
        api.calc_nota_carregamento(carregInicial, carregMax)
           .catch(function () { return null; }),
        api.calc_nota_tensao_min(tminAtual, tmin_ini)
           .catch(function () { return null; }),
        api.calc_nota_tensao_max(tmaxAtual, tmax_ini)
           .catch(function () { return null; }),
      ]).then(function (notasR) {
        var box = document.getElementById('coplan-analise-notas');
        if (!box) return;
        var html = '';
        var n0 = notasR[0], n1 = notasR[1], n2 = notasR[2];
        html += renderNota('nc', 'Carregamento',
          (n0 && n0.ok) ? n0.nota : null,
          (n0 && n0.ok) ? n0.criterio : '');
        html += renderNota('nt', 'Tensao Min',
          (n1 && n1.ok) ? n1.nota : null,
          (n1 && n1.ok) ? n1.criterio : '');
        html += renderNota('nv', 'Tensao Max',
          (n2 && n2.ok) ? n2.nota : null,
          (n2 && n2.ok) ? n2.criterio : '');
        box.innerHTML = html;
      });

      toast('Analise tecnica concluida', 'info');
    });
  }
  function bindAnalise() {
    var card = ensureAnalisePanel();
    if (!card) return false;
    var btnRun = card.querySelector('#coplan-btn-analise-run');
    var btnClr = card.querySelector('#coplan-btn-analise-clear');
    if (btnRun && !btnRun.__bound) {
      btnRun.__bound = true;
      btnRun.addEventListener('click', runAnalise);
    }
    if (btnClr && !btnClr.__bound) {
      btnClr.__bound = true;
      btnClr.addEventListener('click', clearResults);
    }
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAnalise);
  } else {
    bindAnalise() || setTimeout(bindAnalise, 250);
  }
  // [FIX] Expose para outros scripts dispararem (auto-run ao carregar
  // obra). Tambem listener em coplan:obra-active: se ha obra ativa,
  // tenta rodar a analise automaticamente. Sem alimentadores, runAnalise
  // ja exibe a mensagem amigavel "Sem alimentadores...".
  window.coplanRunAnalise = runAnalise;
  window.coplanClearAnalise = clearResults;
  if (!window.__coplanAnaliseObsBound) {
    window.__coplanAnaliseObsBound = true;
    document.addEventListener('coplan:obra-active', function (ev) {
      var d = (ev && ev.detail) || {};
      if (d.cod) {
        // Garante que o card existe antes de rodar.
        if (bindAnalise()) {
          // Pequeno delay para o form do Cadastro ja estar preenchido
          // (applyObra/fillCadastroForm rodam antes do dispatch deste
          // evento, mas o input tipo SELECT pode demorar a refletir).
          setTimeout(runAnalise, 80);
        }
      } else {
        clearResults();
      }
    });
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 4.6 (Cadastro / validacao + Ctrl+B) ----
  // Validacao client-side antes do save:
  //   * Campos com <span class="req">*</span> sao obrigatorios
  //   * Valor da Obra: numero pt-BR (1.234,56)
  //   * Projeto nao pode iniciar com "Obra" (regra do mock helper)
  //   * Quantidade: numero >= 0
  // Coordenadas: NAO valida formato. O desktop aceita string livre
  // (field_coord_inicio = QLineEdit puro, sem validator) e na pratica os
  // dados vem como UTM "xxxx;yyyy" e nao lat/lng. Validar aqui rejeitava
  // entries validas do banco.
  // Mostra toast com 1a mensagem de erro e foca o campo problemico.
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
  function fieldByReq(scope) {
    // Retorna lista de objetos {label, node} dos campos marcados com .req
    // [FIX] Ignora .req com display:none (asterisco condicional como
    // "Projeto" so obrigatorio quando PI=DISTRIBUICAO). Antes, qualquer
    // .req no label fazia o campo obrigatorio mesmo com asterisco oculto.
    var out = [];
    scope.querySelectorAll('.field').forEach(function (f) {
      var reqSpan = f.querySelector('label .req');
      if (!reqSpan) return;
      // Verifica se o asterisco esta visivel (display !== 'none').
      var st = window.getComputedStyle(reqSpan);
      if (st && st.display === 'none') return;
      var lab = f.querySelector('label');
      var clone = lab.cloneNode(true);
      clone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var node = f.querySelector('input, select, textarea');
      out.push({ label: clone.textContent.trim(), node: node });
    });
    return out;
  }

  // (Removido) validCoord/COORD_RE: o desktop aceita string livre em
  // field_coord_inicio/field_coord_fim (QLineEdit sem validator). Os
  // dados reais vem em UTM "easting;northing" (ex.: "284513;9087342"),
  // nao lat/lng. Manter regex aqui rejeitava entries validas vindas do
  // banco. Se quiser validar UTM no futuro, adicionar regex nova
  // permitindo separadores ";" ou ",".
  function validValor(v) {
    if (!v) return true;
    // Aceita "1.234,56" pt-BR, "1234.56" en, "1234,56" simples ou "1234"
    var s = String(v).replace(/[.]/g, '').replace(',', '.');
    var n = parseFloat(s);
    return !isNaN(n) && n >= 0;
  }
  function validQuantidade(v) {
    if (!v) return true;
    var s = String(v).replace(',', '.');
    var n = parseFloat(s);
    return !isNaN(n) && n >= 0;
  }

  function flashInvalid(node) {
    if (!node) return;
    var prev = node.style.borderColor;
    var prevBs = node.style.boxShadow;
    node.style.borderColor = 'var(--danger)';
    node.style.boxShadow = '0 0 0 3px oklch(0.58 0.18 25 / 0.18)';
    setTimeout(function () {
      node.style.borderColor = prev;
      node.style.boxShadow = prevBs;
    }, 1800);
    try { node.focus(); node.select && node.select(); } catch (e) {}
  }

  window.coplanValidateCadastro = function () {
    var scope = document.getElementById('tab-cadastro');
    if (!scope) return { ok: true, errors: [] };

    var errors = [];

    // 1. Campos obrigatorios (com .req no label).
    fieldByReq(scope).forEach(function (it) {
      if (!it.node) return;
      var v = String(it.node.value || '').trim();
      if (!v) {
        errors.push({
          message: 'Campo obrigatorio: ' + it.label,
          node: it.node,
        });
      }
    });

    // 2. Coordenadas De / Para: sem validacao de formato.
    // O desktop aceita string livre (UTM "easting;northing", lat/lng,
    // texto, etc) e o banco grava do jeito que veio.

    // 3. Valor da Obra.
    var valorNode = findFieldByLabel(scope, 'Valor da Obra');
    if (valorNode && !validValor(valorNode.value)) {
      errors.push({
        message: 'Valor da Obra: numero invalido (use formato pt-BR, ex.: 2.487.500,00)',
        node: valorNode,
      });
    }

    // 4. Projeto nao pode iniciar com "Obra" (regra do mock helper).
    var projNode = findFieldByLabel(scope, 'Projeto');
    if (projNode) {
      var pv = String(projNode.value || '').trim();
      if (pv && pv.toLowerCase().indexOf('obra') === 0) {
        errors.push({
          message: 'Campo Projeto nao pode iniciar com "Obra".',
          node: projNode,
        });
      }
    }

    // 5. Quantidade >= 0.
    var qtdNode = findFieldByLabel(scope, 'Quantidade');
    if (qtdNode && !validQuantidade(qtdNode.value)) {
      errors.push({
        message: 'Quantidade: numero invalido (use ponto ou virgula como separador decimal)',
        node: qtdNode,
      });
    }

    // 6. Item: deve ser numerico (3 digitos preferencial).
    var itemNode = findFieldByLabel(scope, 'Item');
    if (itemNode) {
      var iv = String(itemNode.value || '').trim();
      if (iv && !/^[0-9]+$/.test(iv)) {
        errors.push({
          message: 'Item: aceita apenas digitos (ex.: 047)',
          node: itemNode,
        });
      }
    }

    return { ok: errors.length === 0, errors: errors };
  };

  // Wraps coplanSaveObra (Passo 4.2) para validar antes.
  if (typeof window.coplanSaveObra === 'function' &&
      !window.coplanSaveObra.__validated) {
    var origSave = window.coplanSaveObra;
    var wrapped = function () {
      var v = window.coplanValidateCadastro();
      if (!v.ok) {
        var first = v.errors[0];
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(first.message, 'error');
        }
        flashInvalid(first.node);
        return Promise.resolve({
          ok: false, error: first.message, validation: v.errors,
        });
      }
      return origSave.apply(this, arguments);
    };
    wrapped.__validated = true;
    window.coplanSaveObra = wrapped;
  }

  // Atalho Ctrl+B (e Cmd+B no Mac) para salvar -- so quando aba Cadastro
  // esta ativa. Tambem dispara o button Salvar para que outros wrappers
  // (futuros) sejam acionados consistentemente.
  document.addEventListener('keydown', function (e) {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key !== 'b' && e.key !== 'B') return;
    var cad = document.getElementById('tab-cadastro');
    if (!cad || !cad.classList.contains('active')) return;
    e.preventDefault();
    if (typeof window.coplanSaveObra === 'function') {
      window.coplanSaveObra();
    }
  });
})();
</script>
<script>
(function () {
  // ---- Atalhos Cadastro: Nova SE / Novo AL / Reconfig / Alivio / Flex ----
  // Replica nova_se/novo_al/reconfiguracao/alivio_se/flexibilizacao do
  // CadastroMixin. Cada um pre-enche o campo Projeto com um prefixo
  // padrao; novo_al ainda seta Novo Bay = SIM (preencher_novo_al do
  // ApoioMixin).
  function api() { return window.pywebview && window.pywebview.api; }
  function toast(msg, lvl) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, lvl || 'info');
    }
  }
  function setProjeto(prefix) {
    var inp = document.getElementById('cad-input-projeto');
    if (!inp) return false;
    inp.value = prefix;
    inp.focus();
    // Posiciona cursor no fim para o user complementar o nome
    try { inp.setSelectionRange(prefix.length, prefix.length); } catch (e) {}
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  }
  function setNovoBay(value) {
    var sel = document.getElementById('cad-sel-novo-bay');
    if (!sel) return;
    var target = String(value || '').toUpperCase();
    for (var i = 0; i < sel.options.length; i++) {
      var t = String(sel.options[i].text || sel.options[i].value || '')
        .toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
      var want = target.normalize('NFD').replace(/[̀-ͯ]/g, '');
      if (t === want) { sel.selectedIndex = i; sel.dispatchEvent(new Event('change')); return; }
    }
  }
  function bindAtalhos() {
    var binds = [
      ['cad-btn-nova-se',  function () { if (setProjeto('Nova_SE_')) toast('Prefixo "Nova_SE_" aplicado'); }],
      ['cad-btn-novo-al',  function () {
          if (setProjeto('AL_Novo_')) {
            setNovoBay('SIM');
            toast('Prefixo "AL_Novo_" + Novo Bay = SIM');
          }
      }],
      ['cad-btn-reconf',   function () { if (setProjeto('Reconfiguração_')) toast('Prefixo "Reconfiguração_" aplicado'); }],
      ['cad-btn-alivio',   function () { if (setProjeto('Alívio_SE_')) toast('Prefixo "Alívio_SE_" aplicado'); }],
      ['cad-btn-flex',     function () { if (setProjeto('Flexibilização_AL_')) toast('Prefixo "Flexibilização_AL_" aplicado'); }],
    ];
    binds.forEach(function (b) {
      var el = document.getElementById(b[0]);
      if (el && !el.__bound) { el.__bound = true; el.addEventListener('click', b[1]); }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAtalhos);
  } else {
    bindAtalhos();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'cadastro') {
      setTimeout(bindAtalhos, 50);
    }
  });
})();
</script>
<script>
(function () {
  // ---- Multi-PI dialog (replica selecionar_pis do desktop) ----
  // Modal com lista de PIs (vem de get_pi_options). Multi-selecao com
  // checkboxes; o resultado e' salvo em window.__coplanSelectedPis e
  // (TODO no futuro) emitido pra save_obra como alimentadores extra.
  function api() { return window.pywebview && window.pywebview.api; }
  function buildModal(pis, preSelected) {
    var existing = document.getElementById('coplan-multipi-modal');
    if (existing) existing.remove();
    var dlg = document.createElement('dialog');
    dlg.id = 'coplan-multipi-modal';
    dlg.style.cssText =
      'border:none;border-radius:12px;padding:0;min-width:420px;'
      + 'max-width:540px;max-height:80vh;'
      + 'box-shadow:0 8px 24px rgba(0,0,0,.15);';
    var checks = pis.map(function (pi, idx) {
      var chk = preSelected.indexOf(pi) >= 0 ? ' checked' : '';
      var safe = String(pi).replace(/[<>&"]/g,
        function (c) { return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'})[c]; });
      return '<label style="display:flex;align-items:center;gap:8px;'
           + 'padding:6px 10px;border-bottom:1px solid #f1f5f9;cursor:pointer">'
           + '<input type="checkbox" data-pi="' + safe + '"' + chk + '/>'
           + '<span>' + safe + '</span></label>';
    }).join('');
    dlg.innerHTML =
      '<div style="padding:14px 18px;border-bottom:1px solid #e2e8f0;'
      + 'display:flex;align-items:center;gap:8px">'
      + '<i data-lucide="list-checks"></i>'
      + '<strong>Selecionar Multiplos PIs</strong>'
      + '<span style="margin-left:auto;color:#64748b;font-size:12px">'
      + pis.length + ' opcao(oes)</span></div>'
      + '<div style="overflow:auto;max-height:55vh;padding:6px 0">'
      + (checks || '<em style="padding:14px;display:block;color:#94a3b8">'
                  + 'Nenhum PI configurado.</em>')
      + '</div>'
      + '<div style="padding:12px 18px;border-top:1px solid #e2e8f0;'
      + 'display:flex;gap:8px;justify-content:flex-end">'
      + '<button class="btn" type="button" data-act="cancel">Cancelar</button>'
      + '<button class="btn primary" type="button" data-act="ok">OK</button>'
      + '</div>';
    document.body.appendChild(dlg);
    if (window.lucide) lucide.createIcons();
    return dlg;
  }
  function openMultiPi() {
    var a = api();
    if (!(a && a.get_pi_options)) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast('API get_pi_options indisponivel', 'error');
      }
      return;
    }
    a.get_pi_options().then(function (r) {
      var items = (r && r.ok && r.items) || [];
      // get_pi_options retorna [{nome, base}]; pegamos so o nome longo.
      var pis = items.map(function (it) {
        if (typeof it === 'string') return it;
        return it && (it.nome || it.label || it.name) || '';
      }).filter(function (n) { return !!n; });
      var pre = window.__coplanSelectedPis || [];
      var dlg = buildModal(pis, pre);
      dlg.addEventListener('click', function (ev) {
        var btn = ev.target.closest('button[data-act]');
        if (!btn) return;
        if (btn.dataset.act === 'cancel') {
          dlg.close(); dlg.remove(); return;
        }
        if (btn.dataset.act === 'ok') {
          var sel = [];
          dlg.querySelectorAll('input[type=checkbox]:checked').forEach(function (cb) {
            sel.push(cb.dataset.pi);
          });
          window.__coplanSelectedPis = sel;
          dlg.close(); dlg.remove();
          if (typeof window.coplanToast === 'function') {
            window.coplanToast(sel.length + ' PI(s) selecionado(s)', 'info');
          }
          // Dispatch para outros consumidores (save_obra futuramente
          // pode pegar isso e gravar como alimentadores_beneficiados ou
          // num campo extra).
          document.dispatchEvent(new CustomEvent('coplan:multi-pi',
            { detail: { pis: sel } }));
        }
      });
      if (typeof dlg.showModal === 'function') dlg.showModal();
    }).catch(function (e) {
      if (typeof window.coplanToast === 'function') {
        window.coplanToast('Falha get_pi_options: ' + e, 'error');
      }
    });
  }
  function bindMultiPi() {
    var btn = document.getElementById('cad-btn-multi-pi');
    if (btn && !btn.__bound) {
      btn.__bound = true;
      btn.addEventListener('click', openMultiPi);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindMultiPi);
  } else {
    bindMultiPi();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'cadastro') {
      setTimeout(bindMultiPi, 50);
    }
  });
})();
</script>
<script>
(function () {
  // ---- Auto-fill SE quando alimentador principal muda ----
  // Replica update_subestacoes_list do ApoioMixin: ao trocar o select
  // "Alimentador Obra", busca dados_alimentador no apoio e preenche
  // SE + Regional + Superintendencia + Tensao automaticamente.
  function api() { return window.pywebview && window.pywebview.api; }
  function setFieldValueByLabel(prefix, value) {
    if (!value) return;
    var fields = document.querySelectorAll('#tab-cadastro .field');
    var pNorm = String(prefix || '').trim().toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      var clone = lab.cloneNode(true);
      clone.querySelectorAll('span,i').forEach(function (n) { n.remove(); });
      var t = clone.textContent.trim().toLowerCase()
        .normalize('NFD').replace(/[̀-ͯ]/g, '');
      if (t === pNorm || t.indexOf(pNorm) === 0) {
        var inp = fields[i].querySelector('input, select, textarea');
        if (!inp) continue;
        if (inp.tagName === 'SELECT') {
          var found = false;
          for (var j = 0; j < inp.options.length; j++) {
            if (String(inp.options[j].text).trim().toUpperCase()
                === String(value).trim().toUpperCase()) {
              inp.selectedIndex = j; found = true; break;
            }
          }
          if (!found) {
            var opt = document.createElement('option');
            opt.value = value; opt.text = value;
            inp.appendChild(opt);
            inp.value = value;
          }
        } else {
          inp.value = value;
        }
        inp.dispatchEvent(new Event('change', { bubbles: true }));
        return;
      }
    }
  }
  function applyAlimDetails(r) {
    if (!r || !r.ok) return;
    setFieldValueByLabel('SE', r.se);
    setFieldValueByLabel('Regional', r.regional);
    setFieldValueByLabel('Superintend', r.superintendencia);
    if (r.tensao) {
      setFieldValueByLabel('Tensão Obra', r.tensao);
      setFieldValueByLabel('Tensão Operação', r.tensao);
    }
  }
  function onAlimChange() {
    var sel = document.getElementById('cad-sel-alim-principal');
    if (!sel) return;
    var alim = '';
    if (sel.tagName === 'SELECT') {
      var opt = sel.options[sel.selectedIndex];
      alim = (opt && (opt.text || opt.value) || '').trim();
    } else {
      alim = (sel.value || '').trim();
    }
    if (!alim) return;
    var a = api();
    if (!(a && a.get_alimentador_details)) return;
    a.get_alimentador_details(alim).then(applyAlimDetails);
  }
  function bindAutoFill() {
    var sel = document.getElementById('cad-sel-alim-principal');
    if (sel && !sel.__autoFillBound) {
      sel.__autoFillBound = true;
      sel.addEventListener('change', onAlimChange);
      // Tambem reage a 'input' (caso seja convertido em datalist no futuro)
      sel.addEventListener('input', onAlimChange);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAutoFill);
  } else {
    bindAutoFill();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'cadastro') {
      setTimeout(bindAutoFill, 50);
    }
  });
})();
</script>
<script>
(function () {
  // ---- Helpers de dialog generico (Passos 5/6/7/8) ----
  // Usado por: configurar colunas, choose_packages, prompt export columns
  // mode, prompt scope relatorio criterios.
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function api() { return window.pywebview && window.pywebview.api; }
  function toast(msg, lvl) {
    if (typeof window.coplanToast === 'function') {
      window.coplanToast(msg, lvl || 'info');
    }
  }
  // Dialog reutilizavel: titulo, html_body (string), botoes
  // [{label, primary, act}]. Resolve com a string `act` clicada (ou
  // null se fechou).
  function openDialog(opts) {
    return new Promise(function (resolve) {
      var existing = document.getElementById('coplan-generic-dialog');
      if (existing) existing.remove();
      var dlg = document.createElement('dialog');
      dlg.id = 'coplan-generic-dialog';
      dlg.style.cssText =
        'border:none;border-radius:12px;padding:0;min-width:'
        + (opts.minWidth || '480px') + ';max-width:'
        + (opts.maxWidth || '640px') + ';max-height:80vh;'
        + 'box-shadow:0 8px 24px rgba(0,0,0,.15);overflow:hidden;';
      var btns = (opts.buttons || [
        { label: 'Fechar', act: 'close' }
      ]).map(function (b) {
        var cls = 'btn' + (b.primary ? ' primary' : ' ghost');
        return '<button class="' + cls + '" type="button" data-act="'
             + escHtml(b.act) + '">' + escHtml(b.label) + '</button>';
      }).join('');
      dlg.innerHTML =
        '<div style="padding:14px 18px;border-bottom:1px solid #e2e8f0;'
        + 'display:flex;align-items:center;gap:8px"><strong>'
        + escHtml(opts.title || 'Dialog') + '</strong>'
        + '<button class="btn ghost" type="button" data-act="close" '
        + 'style="margin-left:auto;padding:4px 8px"><i data-lucide="x"></i>'
        + '</button></div>'
        + '<div style="overflow:auto;max-height:55vh">'
        + (opts.html || '') + '</div>'
        + '<div style="padding:12px 18px;border-top:1px solid #e2e8f0;'
        + 'display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap">'
        + btns + '</div>';
      document.body.appendChild(dlg);
      if (window.lucide) lucide.createIcons();
      function close(act) {
        try { dlg.close(); } catch (e) {}
        dlg.remove();
        resolve(act || null);
      }
      dlg.addEventListener('click', function (ev) {
        var btn = ev.target.closest('button[data-act]');
        if (!btn) return;
        if (opts.beforeClose) {
          var keep = opts.beforeClose(btn.dataset.act, dlg);
          if (keep === false) return;
        }
        close(btn.dataset.act);
      });
      if (typeof dlg.showModal === 'function') dlg.showModal();
      else dlg.setAttribute('open', '');
    });
  }
  window.coplanOpenDialog = openDialog;

  // ============ Pass 5 / Configurar Colunas Visualizar ============
  function openConfigColunasDialog() {
    var a = api();
    if (!(a && a.visualizar_columns_get_config)) {
      return toast('API indisponivel', 'error');
    }
    a.visualizar_columns_get_config().then(function (r) {
      if (!r || !r.ok) {
        return toast('Falha: ' + (r && r.error || '?'), 'error');
      }
      var all = r.all || [];
      var visible = new Set(r.visible || []);
      // Se visible vazio (primeiro acesso), considera todas visiveis
      if (!r.visible || !r.visible.length) {
        all.forEach(function (c) { visible.add(c); });
      }
      var order = (r.order && r.order.length)
        ? r.order : all.slice();
      // Reordena 'all' segundo o order persistido
      var orderSet = new Set(order);
      var ordered = order.filter(function (c) { return all.indexOf(c) >= 0; })
        .concat(all.filter(function (c) { return !orderSet.has(c); }));
      var rows = ordered.map(function (col, idx) {
        var checked = visible.has(col) ? ' checked' : '';
        return '<li data-col="' + escHtml(col)
             + '" draggable="true" style="display:flex;align-items:center;'
             + 'gap:8px;padding:6px 12px;border-bottom:1px solid #f1f5f9;'
             + 'cursor:grab" data-idx="' + idx + '">'
             + '<i data-lucide="grip-vertical" style="color:#94a3b8"></i>'
             + '<input type="checkbox" data-col-chk="' + escHtml(col) + '"'
             + checked + '/>'
             + '<span style="flex:1">' + escHtml(col) + '</span></li>';
      }).join('');
      var html =
        '<p style="margin:12px 18px 8px;color:#64748b;font-size:12.5px">'
        + 'Marque para mostrar; arraste pra reordenar. Padrao = todas. '
        + 'Salva em config.json (ui_state.visualizar).</p>'
        + '<ul id="cad-cols-list" style="margin:0;padding:0;list-style:none">'
        + rows + '</ul>';
      openDialog({
        title: 'Configurar Colunas (Visualizar)',
        html: html,
        minWidth: '420px',
        buttons: [
          { label: 'Resetar', act: 'reset' },
          { label: 'Cancelar', act: 'close' },
          { label: 'Salvar', primary: true, act: 'save' },
        ],
        beforeClose: function (act, dlg) {
          if (act === 'save') {
            var visibleOut = [];
            var orderOut = [];
            dlg.querySelectorAll('li[data-col]').forEach(function (li) {
              var col = li.dataset.col;
              orderOut.push(col);
              var chk = li.querySelector('input[type=checkbox]');
              if (chk && chk.checked) visibleOut.push(col);
            });
            a.visualizar_columns_save_config({
              visible: visibleOut, order: orderOut,
            }).then(function (s) {
              if (s && s.ok) {
                toast('Configuracao salva ('
                      + visibleOut.length + ' colunas visiveis)', 'info');
                document.dispatchEvent(
                  new CustomEvent('coplan:colunas-saved'));
                if (typeof window.coplanLoadObras === 'function') {
                  window.coplanLoadObras();
                }
              } else {
                toast('Falha ao salvar: ' + (s && s.error || '?'), 'error');
              }
            });
            return true;
          }
          if (act === 'reset') {
            if (!window.confirm(
              'Resetar config de colunas? Volta ao default (todas '
              + 'visiveis na ordem original).')) {
              return false;
            }
            a.visualizar_columns_reset().then(function (s) {
              if (s && s.ok) {
                toast('Config resetada', 'info');
                document.dispatchEvent(
                  new CustomEvent('coplan:colunas-saved'));
                if (typeof window.coplanLoadObras === 'function') {
                  window.coplanLoadObras();
                }
              }
            });
            return true;
          }
          return true;
        }
      }).then(function () { /* fechado */ });

      // Drag-drop reorder
      setTimeout(function () {
        var list = document.getElementById('cad-cols-list');
        if (!list) return;
        var draggingEl = null;
        list.addEventListener('dragstart', function (ev) {
          var li = ev.target.closest('li');
          if (!li) return;
          draggingEl = li;
          ev.dataTransfer.effectAllowed = 'move';
          li.style.opacity = '0.4';
        });
        list.addEventListener('dragend', function () {
          if (draggingEl) draggingEl.style.opacity = '';
          draggingEl = null;
        });
        list.addEventListener('dragover', function (ev) {
          ev.preventDefault();
          var li = ev.target.closest('li');
          if (!li || li === draggingEl) return;
          var rect = li.getBoundingClientRect();
          var after = (ev.clientY - rect.top) > rect.height / 2;
          li.parentNode.insertBefore(draggingEl,
            after ? li.nextSibling : li);
        });
      }, 50);
    });
  }
  window.coplanOpenConfigColunas = openConfigColunasDialog;

  // ============ Pass 6 / Choose Packages dialog ============
  // Replica visualizar_mixin.choose_packages: lista pacotes via
  // get_pacotes(), permite selecionar varios, e seta
  // window.coplanFilters.pacote (consumido por search_obras).
  function openChoosePackagesDialog() {
    var a = api();
    if (!(a && a.get_pacotes)) {
      return toast('API indisponivel', 'error');
    }
    a.get_pacotes().then(function (r) {
      var pacotes = (r && r.ok && r.items) || [];
      var current = ((window.coplanFilters || {}).pacote || []);
      if (typeof current === 'string') current = current.split('|');
      var sel = new Set(current.filter(function (p) { return !!p; }));
      var rows = pacotes.map(function (p) {
        var safe = escHtml(p);
        var chk = sel.has(p) ? ' checked' : '';
        return '<label style="display:flex;align-items:center;gap:8px;'
             + 'padding:6px 12px;border-bottom:1px solid #f1f5f9;cursor:pointer">'
             + '<input type="checkbox" data-pkg="' + safe + '"' + chk + '/>'
             + '<span>' + safe + '</span></label>';
      }).join('');
      openDialog({
        title: 'Filtrar por Pacotes',
        html: rows
          ? rows
          : '<p style="padding:14px;color:#94a3b8">Sem pacotes.</p>',
        buttons: [
          { label: 'Limpar', act: 'clear' },
          { label: 'Cancelar', act: 'close' },
          { label: 'Aplicar', primary: true, act: 'apply' },
        ],
        beforeClose: function (act, dlg) {
          if (act === 'apply') {
            var picked = [];
            dlg.querySelectorAll('input[data-pkg]:checked').forEach(function (cb) {
              picked.push(cb.dataset.pkg);
            });
            window.coplanFilters = window.coplanFilters || {};
            window.coplanFilters.pacote = picked.join('|');
            if (typeof window.coplanApplySearch === 'function') {
              window.coplanApplySearch();
            }
            toast(picked.length
              ? picked.length + ' pacote(s) selecionado(s)'
              : 'Filtro de pacote limpo', 'info');
          } else if (act === 'clear') {
            window.coplanFilters = window.coplanFilters || {};
            delete window.coplanFilters.pacote;
            if (typeof window.coplanApplySearch === 'function') {
              window.coplanApplySearch();
            }
            toast('Filtro de pacote limpo', 'info');
          }
          return true;
        },
      });
    });
  }
  window.coplanOpenChoosePackages = openChoosePackagesDialog;

  // ============ Pass 7 / Prompt Export Columns Mode ============
  // Replica _prompt_export_columns_mode do desktop: pergunta se exporta
  // todas as colunas, so as visiveis, ou cancela. Wrapper acima do
  // export_detalhamento existente.
  window.coplanPromptExportMode = function () {
    return new Promise(function (resolve) {
      openDialog({
        title: 'Exportar Excel',
        html:
          '<div style="padding:18px;line-height:1.5">'
          + '<p>Como deseja exportar as colunas?</p>'
          + '<ul style="margin:6px 0 0;padding-left:20px;color:#475569">'
          + '<li><strong>Todas</strong>: inclui as 60+ colunas do banco</li>'
          + '<li><strong>Visiveis</strong>: apenas as configuradas em '
          + '"Configurar colunas" (Visualizar)</li>'
          + '</ul></div>',
        buttons: [
          { label: 'Cancelar', act: 'close' },
          { label: 'Visiveis', act: 'visible' },
          { label: 'Todas', primary: true, act: 'all' },
        ],
      }).then(function (act) {
        resolve(act === 'all' ? 'all' : (act === 'visible' ? 'visible' : null));
      });
    });
  };

  // ============ Pass 8 / Prompt Scope Relatorio Criterios ============
  // Replica _prompt_relatorio_criterios_scope: pergunta se o relatorio
  // cobre todas obras, so as filtradas, ou as selecionadas.
  window.coplanPromptCriteriosScope = function () {
    return new Promise(function (resolve) {
      openDialog({
        title: 'Escopo do Relatorio de Criterios',
        html:
          '<div style="padding:18px;line-height:1.5">'
          + '<p>Sobre quais obras o relatorio deve ser gerado?</p>'
          + '<ul style="margin:6px 0 0;padding-left:20px;color:#475569">'
          + '<li><strong>Todas</strong>: tudo no banco</li>'
          + '<li><strong>Filtradas</strong>: apenas o que esta em '
          + 'Visualizar com os filtros atuais</li>'
          + '<li><strong>Selecionadas</strong>: apenas as obras com'
          + ' checkbox marcado</li>'
          + '</ul></div>',
        buttons: [
          { label: 'Cancelar', act: 'close' },
          { label: 'Selecionadas', act: 'selected' },
          { label: 'Filtradas', act: 'filtered' },
          { label: 'Todas', primary: true, act: 'all' },
        ],
      }).then(function (act) {
        if (act === 'all' || act === 'filtered' || act === 'selected') {
          resolve(act);
        } else {
          resolve(null);
        }
      });
    });
  };

  // ============ Pass 10 / Piora de Mercado dialog ============
  // Replica open_piora_dialog do RelatorioCriteriosMixin: edita 3
  // parametros (carregamento_percentual, tensao_delta, anos_horizonte)
  // e persiste em config['piora_mercado']. Usa get_criterios/
  // save_criterios (aceitam piora_mercado embutido no payload).
  function openPioraDialog() {
    var a = api();
    if (!(a && a.get_criterios && a.save_criterios)) {
      return toast('API indisponivel', 'error');
    }
    a.get_criterios().then(function (r) {
      if (!r || !r.ok) {
        return toast('Falha get_criterios: ' + (r && r.error || '?'), 'error');
      }
      var piora = r.piora_mercado || {};
      var carreg = piora.carregamento_percentual;
      var tensao = piora.tensao_delta;
      var anos = piora.anos_horizonte;
      var html =
        '<div style="padding:14px 18px;display:flex;flex-direction:column;'
        + 'gap:14px">'
        + '<div>'
        + '<label style="font-size:12px;color:#475569;display:block;'
        + 'margin-bottom:4px">Crescimento de Carregamento (%/ano)</label>'
        + '<input id="piora-carreg" class="input mono" type="number" '
        + 'step="0.1" value="' + escHtml(carreg == null ? '' : carreg) + '"/>'
        + '<small style="color:#94a3b8">Aplica composto sobre o '
        + 'carregamento atual a cada ano de horizonte.</small></div>'
        + '<div>'
        + '<label style="font-size:12px;color:#475569;display:block;'
        + 'margin-bottom:4px">Delta de Tensao (pu/ano)</label>'
        + '<input id="piora-tensao" class="input mono" type="number" '
        + 'step="0.001" value="'
        + escHtml(tensao == null ? '' : tensao) + '"/>'
        + '<small style="color:#94a3b8">Subtrai da tensao minima a cada '
        + 'ano de horizonte.</small></div>'
        + '<div>'
        + '<label style="font-size:12px;color:#475569;display:block;'
        + 'margin-bottom:4px">Anos de Horizonte</label>'
        + '<input id="piora-anos" class="input mono" type="number" '
        + 'step="1" min="0" value="'
        + escHtml(anos == null ? '' : anos) + '"/>'
        + '<small style="color:#94a3b8">Quantos anos a frente projetar '
        + '(0 = nao projeta).</small></div>'
        + '</div>';
      openDialog({
        title: 'Configurar Piora de Mercado',
        html: html,
        minWidth: '420px',
        buttons: [
          { label: 'Cancelar', act: 'close' },
          { label: 'Salvar', primary: true, act: 'save' },
        ],
        beforeClose: function (act, dlg) {
          if (act !== 'save') return true;
          var get = function (id) {
            var el = dlg.querySelector('#' + id);
            return el ? String(el.value || '').trim().replace(',', '.') : '';
          };
          var newPiora = {
            carregamento_percentual: parseFloat(get('piora-carreg')),
            tensao_delta: parseFloat(get('piora-tensao')),
            anos_horizonte: parseInt(get('piora-anos'), 10),
          };
          if (isNaN(newPiora.carregamento_percentual)
              || isNaN(newPiora.tensao_delta)
              || isNaN(newPiora.anos_horizonte)) {
            toast('Valores invalidos. Use numeros decimais.', 'error');
            return false;  // mantem dialog aberto
          }
          // save_criterios aceita {criterios: {...}, piora_mercado: {...}}
          a.save_criterios({
            piora_mercado: newPiora,
          }).then(function (s) {
            if (s && s.ok) {
              toast('Piora de mercado salva', 'info');
              if (typeof window.coplanLoadObras === 'function') {
                window.coplanLoadObras();
              }
            } else {
              toast('Falha: ' + (s && s.error || '?'), 'error');
            }
          });
          return true;
        }
      });
    });
  }
  window.coplanOpenPioraDialog = openPioraDialog;

  // Adiciona botao "Configurar Colunas" no toolbar Visualizar.
  function bindToolbarColunas() {
    var bar = document.querySelector('#tab-visualizar .toolbar')
      || document.querySelector('#tab-visualizar .filter-bar');
    if (!bar || bar.querySelector('#coplan-btn-config-cols')) return;
    var btn = document.createElement('button');
    btn.id = 'coplan-btn-config-cols';
    btn.className = 'btn';
    btn.innerHTML = '<i data-lucide="columns-3"></i> Colunas';
    btn.title = ('Configurar colunas visiveis e ordem na tabela '
                + '(persistido em config.json).');
    btn.addEventListener('click', openConfigColunasDialog);
    bar.appendChild(btn);
    if (window.lucide) lucide.createIcons();
  }
  function bindToolbarPacotes() {
    var bar = document.querySelector('#tab-visualizar .toolbar')
      || document.querySelector('#tab-visualizar .filter-bar');
    if (!bar || bar.querySelector('#coplan-btn-pkg')) return;
    var btn = document.createElement('button');
    btn.id = 'coplan-btn-pkg';
    btn.className = 'btn ghost';  // [B10] visual mais discreto
    btn.innerHTML = '<i data-lucide="package"></i> Pacotes';
    btn.title = ('[Atalho] Filtra obras por um conjunto de pacotes. '
               + 'Mesmo filtro do modal "Filtros avancados" -> '
               + 'campo Pacote, mas em 1 clique. '
               + 'Equivalente a choose_packages do desktop.');
    btn.addEventListener('click', function () {
      openChoosePackagesDialog();
      // [B10] Apos fechar o atalho, dispara evento para o modal
      // re-sincronizar o select Pacote (caso esteja aberto).
      setTimeout(function () {
        document.dispatchEvent(new CustomEvent('coplan:filters-changed', {
          detail: { source: 'btn-pkg' },
        }));
      }, 200);
    });
    bar.appendChild(btn);
    if (window.lucide) lucide.createIcons();
  }
  function bindToolbarPiora() {
    var bar = document.querySelector('#tab-visualizar .toolbar')
      || document.querySelector('#tab-visualizar .filter-bar');
    if (!bar || bar.querySelector('#coplan-btn-piora')) return;
    var btn = document.createElement('button');
    btn.id = 'coplan-btn-piora';
    btn.className = 'btn';
    btn.innerHTML = '<i data-lucide="trending-up"></i> Piora Mercado';
    btn.title = ('Configura crescimento de carregamento + delta de '
               + 'tensao + anos de horizonte (afeta criterios V2).');
    btn.addEventListener('click', openPioraDialog);
    bar.appendChild(btn);
    if (window.lucide) lucide.createIcons();
  }

  // ============ Pass 11 / Menu contextual de linha (Visualizar) ============
  // Replica visualizar_mixin.mostrar_menu_linha do desktop. Right-click
  // numa <tr> abre menu com: Editar Obra, Copiar COD, Atualizar valor,
  // Calc nota colapso, Marcar correcao, Excluir.
  function showRowContextMenu(ev, tr) {
    ev.preventDefault();
    var cod = tr.dataset.cod || '';
    if (!cod) return;
    // Remove menu anterior
    var prev = document.getElementById('coplan-row-ctx-menu');
    if (prev) prev.remove();
    var menu = document.createElement('ul');
    menu.id = 'coplan-row-ctx-menu';
    menu.style.cssText =
      'position:fixed;background:#fff;border:1px solid #e2e8f0;'
      + 'border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.12);'
      + 'list-style:none;padding:4px 0;margin:0;min-width:200px;'
      + 'z-index:99999;font-size:13px';
    var items = [
      { act: 'edit',     icon: 'edit-3',         label: 'Editar Obra' },
      { act: 'projeto',  icon: 'layers',         label: 'Atualizar Projeto' },
      { act: 'copy',     icon: 'clipboard',      label: 'Copiar COD' },
      { act: 'detalhe',  icon: 'file-spreadsheet', label: 'Exportar Detalhamento' },
      { act: 'val',      icon: 'calculator',     label: 'Atualizar Valor' },
      { act: 'nota',     icon: 'alert-triangle', label: 'Calcular Nota Colapso' },
      { act: 'cor',      icon: 'edit',           label: 'Marcar Correcao' },
      { act: 'sep',      sep: true },
      { act: 'del',      icon: 'trash-2',        label: 'Excluir', danger: true },
    ];
    menu.innerHTML = items.map(function (it) {
      if (it.sep) {
        return '<li style="height:1px;background:#e2e8f0;margin:4px 0">'
             + '</li>';
      }
      var color = it.danger ? 'color:var(--danger);' : '';
      return '<li data-act="' + escHtml(it.act) + '" style="padding:6px 14px;'
           + 'cursor:pointer;display:flex;align-items:center;gap:8px;'
           + color + '" onmouseover="this.style.background=\'#f1f5f9\'"'
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
      var a = api();
      switch (act) {
        case 'edit':
          // Replica abrir_editar_obra: troca aba pra Cadastro + load
          var sb = document.querySelector('.sb-item[data-tab="cadastro"]');
          if (sb) sb.click();
          if (typeof window.coplanLoadObraIntoForm === 'function') {
            window.coplanLoadObraIntoForm(cod);
          } else {
            window.__coplanEditingCod = cod;
            if (a && a.get_obra) a.get_obra(cod);
          }
          break;
        case 'projeto':
          // [F16] Atualizar Projeto navegacional - lista todas obras do
          // mesmo nome_projeto + tipo_pacote, mostra barra prev/next.
          if (typeof window.coplanIniciarAtualizacaoProjetoByCod
              === 'function') {
            window.coplanIniciarAtualizacaoProjetoByCod(cod);
          } else {
            toast('Funcao indisponivel', 'error');
          }
          break;
        case 'copy':
          (function () {
            function fb() {
              try {
                var ta = document.createElement('textarea');
                ta.value = cod;
                document.body.appendChild(ta);
                ta.select();
                var ok = document.execCommand('copy');
                document.body.removeChild(ta);
                return !!ok;
              } catch (e) { return false; }
            }
            function done(ok) {
              toast(ok ? ('COD ' + cod + ' copiado') : 'Falha ao copiar',
                    ok ? 'info' : 'error');
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(cod).then(function () {
                done(true);
              }, function () { done(fb()); });
            } else {
              done(fb());
            }
          })();
          break;
        case 'detalhe':
          if (a && a.export_detalhamento) {
            toast('Exportando ' + cod + '...', 'info');
            a.export_detalhamento([cod]).then(function (r) {
              if (r && r.ok) toast('XLSX salvo: ' + r.path, 'info');
              else toast('Falhou: ' + (r && r.error || '?'), 'error');
            }).catch(function (err) {
              toast('Falhou: ' + (err && err.message || err || '?'), 'error');
            });
          }
          break;
        case 'val':
          // Roteia pelo helper bulk (mesmo toast + progress + modal
          // de detalhes quando ha falhas/chaves inexistentes).
          if (typeof window.coplanAtualizarBulk === 'function') {
            window.coplanAtualizarBulk([cod]);
          } else if (a && a.atualizar_obras_valores) {
            toast('Atualizando valor...', 'info');
            a.atualizar_obras_valores([cod]).then(function (r) {
              toast(r && r.ok
                ? (r.atualizadas || 0) + ' obra(s) atualizada(s)'
                : 'Falhou: ' + (r && r.error || '?'),
                r && r.ok ? 'info' : 'error');
              if (typeof window.coplanLoadObras === 'function') {
                window.coplanLoadObras();
              }
            });
          }
          break;
        case 'nota':
          if (a && a.calc_nota_colapso_obra) {
            a.calc_nota_colapso_obra(cod).then(function (r) {
              if (r && r.ok) {
                toast('Nota colapso: ' + (r.nota || '?'), 'info');
              } else {
                toast('Falhou: ' + (r && r.error || '?'), 'error');
              }
            });
          }
          break;
        case 'cor':
          var motivo = window.prompt('Motivo da correcao para ' + cod + ':');
          if (!motivo || !motivo.trim()) {
            return toast('Cancelado', 'warn');
          }
          if (a && a.marcar_obras_correcao) {
            a.marcar_obras_correcao([cod], motivo.trim()).then(function (r) {
              if (r && r.ok) toast('Marcado como CORRECAO', 'info');
              else toast('Falhou: '
                + (r && r.error || (r && r.falhas || []).slice(0, 3).join(';')
                   || '?'), 'error');
              if (typeof window.coplanLoadObras === 'function') {
                window.coplanLoadObras();
              }
            });
          }
          break;
        case 'del':
          if (!window.confirm('Excluir obra ' + cod + '?')) return;
          if (a && a.delete_obras) {
            a.delete_obras([cod]).then(function (r) {
              if (r && r.ok) {
                toast('Excluida', 'info');
                if (window.coplanReportError && r && r.errors && r.errors.length) {
                  window.coplanReportError(
                    'Excluir obra ' + cod, 'delete_obras', r);
                }
              } else {
                toast('Falha', 'error');
                if (window.coplanReportError) {
                  window.coplanReportError(
                    'Excluir obra ' + cod, 'delete_obras', r);
                }
              }
              if (typeof window.coplanLoadObras === 'function') {
                window.coplanLoadObras();
              }
            }).catch(function (err) {
              toast('Falhou: ' + (err && err.message || err || '?'), 'error');
              if (window.coplanReportError) {
                window.coplanReportError(
                  'Excluir obra ' + cod, 'delete_obras',
                  { error: String(err && err.message || err || '?') });
              }
            });
          }
          break;
      }
    });
  }
  function bindRowContextMenu() {
    // [FIX] Desabilitado: redundante com bindContextMenu() (~linha 11207)
    // que ja tem TODAS estas acoes (Editar, Copiar, Recalcular, Nota
    // Colapso, Verificar Criterios, Persistir, CORREÇÃO, Despacho VT,
    // Detalhamento, COD_PEP lote, Excluir) + outras. Manter ambos
    // causava 2 menus aparecerem sobrepostos no mesmo right-click.
    return;
  }

  // [FIX Plano de Obras] 1-click numa obra QUANDO o Plano de Obras esta
  // ativo (alguma linha tem classe .plano-cinza ou .plano-verde) abre
  // o modo "Atualizar Projeto" para a obra clicada. Sem plano ativo, o
  // click simples nao faz nada (paridade com comportamento atual).
  function bindPlanoOneClick() {
    var tbody = document.getElementById('obras-tbody');
    if (!tbody || tbody.__planoClickBound) return;
    tbody.__planoClickBound = true;
    tbody.addEventListener('click', function (ev) {
      // Ignora clicks em checkbox / botoes da linha — o usuario quer
      // selecionar/abrir context menu, nao iniciar projeto.
      var t = ev.target;
      if (t && t.closest && (t.closest('input[type="checkbox"]')
          || t.closest('button'))) return;
      var tr = t && t.closest && t.closest('tr[data-cod]');
      if (!tr) return;
      // So dispara se HA plano ativo na tabela (qualquer linha com
      // .plano-cinza ou .plano-verde).
      var hasPlano = tbody.querySelector('.plano-cinza, .plano-verde');
      if (!hasPlano) return;
      // E se a linha clicada esta no plano (verde) — cinza geralmente
      // sao obras bloqueadas/fora do escopo, nao queremos abrir.
      if (!tr.classList.contains('plano-verde')) return;
      var cod = tr.getAttribute('data-cod');
      if (!cod) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (typeof window.coplanIniciarAtualizacaoProjetoByCod === 'function') {
        window.coplanIniciarAtualizacaoProjetoByCod(cod);
      }
    });
  }
  document.addEventListener('coplan:obras', function () {
    var tbody = document.getElementById('obras-tbody');
    if (tbody) tbody.__planoClickBound = false;
    setTimeout(bindPlanoOneClick, 50);
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindPlanoOneClick);
  } else {
    bindPlanoOneClick();
  }
  document.addEventListener('coplan:obras', function () {
    // No-op por causa do return acima — bindRowContextMenu nao mais
    // faz bind. Mantemos a chamada caso o handler antigo seja
    // re-habilitado no futuro.
    var tbody = document.getElementById('obras-tbody');
    if (tbody) tbody.__ctxMenuBound = false;
    setTimeout(bindRowContextMenu, 50);
  });

  // ============ Pass 12 / Helps contextuais ============
  // Replica show_help_main / show_help_cadastro / show_help_ganhos
  // do AjudaMixin (e GanhosMixin.show_help_ganhos). Texto e' static
  // (era hardcoded no desktop tambem).
  var HELP_TEXT = {
    main:
      '<h3 style="margin:0 0 10px">Visualizar</h3>'
      + '<ul style="padding-left:20px;line-height:1.6">'
      + '<li><strong>Buscar</strong>: digite no campo de pesquisa para'
      + ' filtrar por COD, projeto, alimentador, regional, etc.</li>'
      + '<li><strong>Filtros avancados</strong>: clique em "Filtros" '
      + 'para abrir o modal com selects multi-valor.</li>'
      + '<li><strong>Plano Obras</strong>: pinta linhas com '
      + 'data_modificacao no intervalo selecionado.</li>'
      + '<li><strong>Verificar Criterios</strong>: roda criterios V2 '
      + '(novo padrao). Shift+click persiste status no banco.</li>'
      + '<li><strong>Right-click</strong> numa linha: menu com Editar/'
      + 'Copiar/Atualizar/Excluir.</li>'
      + '<li><strong>Right-click</strong> num cabecalho: recolhe '
      + 'coluna a 120px.</li>'
      + '<li><strong>Atalhos</strong>: Ctrl+F (busca), Ctrl+B '
      + '(salvar Cadastro).</li>'
      + '</ul>',
    cadastro:
      '<h3 style="margin:0 0 10px">Cadastro</h3>'
      + '<ul style="padding-left:20px;line-height:1.6">'
      + '<li><strong>Atalhos de tipo</strong>: Nova SE, Novo AL, '
      + 'Reconfiguracao, Alivio, Flexibilizacao, Multi-PI - cada um '
      + 'pre-enche prefixo no campo Projeto.</li>'
      + '<li><strong>Auto-fill SE</strong>: ao escolher Alimentador, '
      + 'a SE/Regional/Superintendencia/Tensao sao preenchidas '
      + 'automaticamente do apoio.xlsx.</li>'
      + '<li><strong>COD_PEP</strong>: gerado a partir de '
      + 'Sigla+Ano+PI+Item (ex.: MA-26-DI-047).</li>'
      + '<li><strong>Coordenadas</strong>: aceita string livre - '
      + 'formato real e UTM "easting;northing".</li>'
      + '<li><strong>Salvar</strong>: Ctrl+B ou clique no botao Salvar.</li>'
      + '<li><strong>Validacao</strong>: campos com * sao obrigatorios.'
      + ' Projeto nao pode iniciar com "Obra".</li>'
      + '</ul>',
    ganhos:
      '<h3 style="margin:0 0 10px">Ganhos</h3>'
      + '<ul style="padding-left:20px;line-height:1.6">'
      + '<li><strong>Pasta de arquivos</strong>: deve conter '
      + 'FlowMT.TXT, Topologia.TXT, Confiabilidade.TXT.</li>'
      + '<li><strong>Inserir Ganhos Antes</strong>: calcula tensoes/'
      + 'carregamento/perdas/contas/CHI/CI a partir dos arquivos '
      + 'tecnicos da pasta + alimentadores selecionados no Cadastro.</li>'
      + '<li><strong>Inserir Ganhos Depois</strong>: idem, mas para o '
      + 'cenario pos-obra (contas_depois, sem beneficiadas).</li>'
      + '<li><strong>Preencher parametros atuais</strong>: tensao_min/'
      + 'max e carregamento atuais (sem contexto de obra).</li>'
      + '<li><strong>Ganhos em Massa</strong>: aplica os calculos em '
      + 'todas as obras selecionadas em Visualizar.</li>'
      + '<li><strong>Criterios</strong>: o card lateral mostra OK/'
      + 'Falhou para cada parametro vs limites configurados.</li>'
      + '</ul>',
  };
  function openHelp(kind) {
    var html = HELP_TEXT[kind] || '<em>Help indisponivel.</em>';
    openDialog({
      title: 'Ajuda',
      html: '<div style="padding:18px">' + html + '</div>',
      minWidth: '520px',
      buttons: [{ label: 'OK', primary: true, act: 'close' }],
    });
  }
  window.coplanShowHelp = openHelp;

  function bindHelpFloating() {
    if (document.getElementById('coplan-help-fab')) return;
    var fab = document.createElement('button');
    fab.id = 'coplan-help-fab';
    fab.type = 'button';
    fab.title = 'Ajuda contextual (depende da aba ativa)';
    // [FIX] Movido para top:bottom:auto para nao sobrepor os toasts.
    // Antes ficava em right:18px;bottom:48px conflitando com #toast.
    fab.style.cssText =
      'position:fixed;right:18px;top:64px;width:32px;height:32px;'
      + 'border-radius:50%;border:1px solid #e2e8f0;background:#fff;'
      + 'box-shadow:0 2px 8px rgba(0,0,0,.10);cursor:pointer;opacity:0.6;'
      + 'display:flex;align-items:center;justify-content:center;'
      + 'z-index:50;color:#0f172a;transition:opacity .15s;';
    fab.addEventListener('mouseenter', function () { fab.style.opacity = '1'; });
    fab.addEventListener('mouseleave', function () { fab.style.opacity = '0.6'; });
    fab.innerHTML = '<i data-lucide="help-circle"></i>';
    fab.addEventListener('click', function () {
      // Detecta aba ativa
      var active = document.querySelector('.tab-panel.active');
      var id = active ? active.id : '';
      if (id === 'tab-cadastro') openHelp('cadastro');
      else if (id === 'tab-ganhos') openHelp('ganhos');
      else openHelp('main');
    });
    document.body.appendChild(fab);
    if (window.lucide) lucide.createIcons();
  }

  // ============ Pass 13 / Footer overflow + persist compact ============
  // Replica StatusBarChromeMixin.set_statusbar_height + persist:
  // toggle classe `compact` no <footer.status>, salva em
  // config.ui_state.statusbar_compact.
  function applyStatusbarCompact(on) {
    var bar = document.querySelector('footer.status');
    if (!bar) return;
    if (on) bar.classList.add('compact');
    else bar.classList.remove('compact');
    // Adiciona regras CSS minimas se ainda nao existirem
    if (!document.getElementById('coplan-statusbar-compact-css')) {
      var s = document.createElement('style');
      s.id = 'coplan-statusbar-compact-css';
      s.textContent =
        'footer.status.compact { font-size: 11px; padding-top: 2px; '
        + 'padding-bottom: 2px; }'
        + 'footer.status.compact .status-item { padding: 0 6px; }';
      document.head.appendChild(s);
    }
  }
  function bindCompactToggle() {
    var bar = document.querySelector('footer.status');
    if (!bar || bar.__compactBound) return;
    bar.__compactBound = true;
    // Carrega estado persistido
    var a = api();
    if (a && a.get_app_state) {
      a.get_app_state().then(function (st) {
        var ui = (st && st.config && st.config.ui_state) || {};
        var on = !!ui.statusbar_compact;
        applyStatusbarCompact(on);
      }).catch(function () {});
    }
    // Double-click no footer alterna compacto
    bar.addEventListener('dblclick', function () {
      var was = bar.classList.contains('compact');
      applyStatusbarCompact(!was);
      // Persiste via save_config_empresa (que mescla)
      if (a && a.save_config_empresa) {
        a.save_config_empresa({
          ui_state: { statusbar_compact: !was },
        });
      }
      toast('Status bar ' + (!was ? 'compacta' : 'expandida'), 'info');
    });
  }

  // [A1] Botao "Carregar BD + Apoio" no toolbar Visualizar.
  // Atalho equivalente a btn_load_db_apoio do desktop
  // (top_actions linha superior do setup_tab_visualizar).
  // Executa header_connect_db (file dialog .db) e em seguida
  // pick_and_load_apoio (file dialog .xlsx). Se um for cancelado
  // mas o outro ok, ainda assim reportamos sucesso parcial.
  function bindToolbarLoadBdApoio() {
    var bar = document.querySelector('#tab-visualizar .toolbar')
      || document.querySelector('#tab-visualizar .filter-bar');
    if (!bar || bar.querySelector('#coplan-btn-load-db-apoio')) return;
    var btn = document.createElement('button');
    btn.id = 'coplan-btn-load-db-apoio';
    btn.className = 'btn primary';
    btn.innerHTML = '<i data-lucide="database"></i> '
                  + '<i data-lucide="folder-open"></i> Carregar BD + Apoio';
    btn.title = ('[Atalho] Conecta um banco .db e em seguida carrega '
               + 'a planilha de apoio .xlsx. Equivalente a "Carregar '
               + 'Banco e Apoio" do desktop.');
    btn.addEventListener('click', function () {
      var a = window.pywebview && window.pywebview.api;
      if (!(a && a.header_connect_db && a.pick_and_load_apoio)) {
        return toast('API indisponivel', 'error');
      }
      toast('Selecione o banco de dados (.db)...', 'info');
      a.header_connect_db().then(function (r1) {
        var dbOk = r1 && r1.ok;
        if (!dbOk && r1 && r1.error
            && r1.error !== 'cancelado') {
          toast('Falha ao conectar BD: ' + r1.error, 'error');
          return;
        }
        if (dbOk) {
          toast('BD conectado: ' + r1.path, 'info');
          if (typeof window.coplanLoadObras === 'function') {
            window.coplanLoadObras();
          }
          if (typeof window.coplanRefreshChips === 'function') {
            window.coplanRefreshChips();
          }
        }
        // Sequencia: agora pede o apoio
        toast('Selecione a planilha de apoio (.xlsx)...', 'info');
        a.pick_and_load_apoio().then(function (r2) {
          var apOk = r2 && r2.ok;
          if (!apOk && r2 && r2.error
              && r2.error !== 'cancelado') {
            toast('Falha ao carregar apoio: ' + r2.error, 'error');
            return;
          }
          if (apOk) {
            toast('Apoio carregado: '
                  + (r2.alimentadores_count || 0) + ' alimentador(es)',
                  'info');
            // Dispara evento custom para outros consumidores
            // (combo Nome Projeto, etc) re-popularem.
            document.dispatchEvent(new CustomEvent('coplan:apoio-loaded',
              { detail: r2 }));
            if (typeof window.coplanRefreshChips === 'function') {
              window.coplanRefreshChips();
            }
          }
          // Resumo
          if (dbOk && apOk) {
            toast('BD + Apoio carregados com sucesso', 'info');
          } else if (dbOk || apOk) {
            toast('Carregamento parcial (' + (dbOk ? 'BD ok' : 'BD pulado')
                  + ' / ' + (apOk ? 'Apoio ok' : 'Apoio pulado')
                  + ')', 'warn');
          }
        });
      });
    });
    bar.appendChild(btn);
    if (window.lucide) lucide.createIcons();
  }

  function bindAll() {
    // [REMOVIDO] bindToolbarLoadBdApoio(): botao "Carregar BD + Apoio"
    // foi considerado desnecessario na aba Visualizar (conexao do banco
    // ja' acontece no header e o apoio e' carregado pela aba Config).
    bindToolbarColunas();
    bindToolbarPacotes();
    bindToolbarPiora();
    bindRowContextMenu();
    bindHelpFloating();
    bindCompactToggle();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAll);
  } else {
    bindAll();
  }
  document.addEventListener('coplan:tab', function (ev) {
    if (ev && ev.detail && ev.detail.name === 'visualizar') {
      setTimeout(bindAll, 100);
    }
  });
  document.addEventListener('coplan:obras', function () {
    setTimeout(bindAll, 100);
  });
})();
</script>
