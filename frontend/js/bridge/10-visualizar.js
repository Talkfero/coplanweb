<script>
(function () {
  // ---- Section 6 / Passo 3.1 (Visualizar / list_obras) ----
  // Substitui o array fake do mock (`const obras = generateObras(60)`)
  // por dados reais vindos do banco. Como `obras` esta no escopo do
  // <script> do mock, nao podemos reatribuir; sobrescrevemos o
  // window.renderObras por uma versao que le de window.coplanObras.
  window.coplanObras = [];

  function fmtNum(n) {
    if (typeof window.fmt === 'function') return window.fmt(n);
    var v = Number(n) || 0;
    return v.toLocaleString('pt-BR');
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function pacoteBadge(p) {
    if (p === 'Mercado') return 'info';
    if (p === 'Confiabilidade') return 'success';
    if (p === 'PLPT') return 'violet';
    return '';
  }
  function rowHtml(o, i) {
    return ''
      + '<tr class="' + (!o.passou ? 'failed' : '') + '" data-row="' + i + '" data-cod="' + esc(o.cod) + '">'
      +   '<td class="check"><input type="checkbox" onclick="event.stopPropagation()"/></td>'
      +   '<td class="cod mono">' + esc(o.cod) + '</td>'
      +   '<td>' + esc(o.ano) + '</td>'
      +   '<td class="mono">' + esc(o.pi) + '</td>'
      +   '<td class="projeto" title="' + esc(o.projeto) + '">' + esc(o.projeto) + '</td>'
      +   '<td class="mono">' + esc(o.alim) + '</td>'
      +   '<td class="mono">' + esc(o.se) + '</td>'
      +   '<td>' + esc(o.regional) + '</td>'
      +   '<td><span class="badge ' + pacoteBadge(o.pacote) + '">' + esc(o.pacote) + '</span></td>'
      +   '<td class="num">' + fmtNum(o.valor) + '</td>'
      +   '<td>' + (o.passou
            ? '<span class="badge success"><span class="dot"></span>Atendeu</span>'
            : '<span class="badge danger"><span class="dot"></span>Falhou</span>') + '</td>'
      +   '<td>' + (o.aprovada
            ? '<span class="badge success">SIM</span>'
            : '<span class="badge">NAO</span>') + '</td>'
      +   '<td>' + (o.tecAtual
            ? '<i data-lucide="check" style="width:14px;height:14px;color:var(--success);"></i>'
            : '<i data-lucide="alert-triangle" style="width:14px;height:14px;color:var(--warning);"></i>') + '</td>'
      +   '<td><button class="btn ghost sm" onclick="event.stopPropagation()"><i data-lucide="more-vertical"></i></button></td>'
      + '</tr>';
  }
  // Reescreve <thead> dinamicamente com TODAS as colunas do banco
  // (igual MainWindow.load_obras_into_table do desktop:
  //   setColumnCount(len(columns))
  //   setHorizontalHeaderLabels([col.replace("_"," ").title() for col in columns])
  // ). Mantem uma coluna inicial de checkbox.
  function humanize(col) {
    return String(col || '').replace(/_/g, ' ').split(' ').map(function (w) {
      return w ? w.charAt(0).toUpperCase() + w.slice(1) : '';
    }).join(' ');
  }
  function rebuildThead(cols) {
    var thead = document.querySelector('#obras-table thead tr');
    if (!thead) return;
    var html = '<th class="check"><input type="checkbox" id="check-all" /></th>';
    cols.forEach(function (c) {
      // [C8] data-col guarda o nome da coluna do DB para mapear largura.
      // .col-resizer e' o handle de drag-to-resize (JS abaixo).
      html += '<th data-col="' + esc(c) + '">'
           +    '<span class="th-label">' + esc(humanize(c)) + '</span>'
           +    '<div class="col-resizer" data-resize-col="' + esc(c) + '"></div>'
           +  '</th>';
    });
    thead.innerHTML = html;
    // [C9] Aplica widths salvos imediatamente apos rebuild thead
    if (typeof window.coplanApplyColWidths === 'function') {
      window.coplanApplyColWidths();
    }
  }
  function fmtCell(v) {
    if (v == null) return '';
    if (typeof v === 'number') return fmtNum(v);
    return esc(v);
  }
  function fmtMoneyBr(v) {
    if (v == null || v === '') return '';
    var n = parseFloat(String(v).replace(/\./g, '').replace(',', '.'));
    if (!isFinite(n)) {
      n = parseFloat(String(v));
    }
    if (!isFinite(n)) return esc(v);
    return n.toLocaleString('pt-BR',
      {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }
  function fmtKm(v) {
    if (v == null || v === '') return '';
    var n = parseFloat(String(v).replace(',', '.'));
    if (!isFinite(n)) return esc(v);
    return n.toLocaleString('pt-BR',
      {minimumFractionDigits: 1, maximumFractionDigits: 2});
  }
  function pacoteBadgeCls(p) {
    var s = String(p || '').trim().toUpperCase();
    if (s === 'MERCADO') return 'info';
    if (s === 'CONFIABILIDADE') return 'success';
    if (s === 'PLPT') return 'violet';
    if (s.indexOf('UDE') >= 0) return 'warning';
    return '';
  }
  // Renderer rico de celula: detecta tipo da coluna e formata.
  // Mantem comportamento legado pra colunas desconhecidas.
  function fmtCellRich(colName, v) {
    var s = (v == null || v === '') ? '' : String(v).trim();
    switch (String(colName || '').toLowerCase()) {
      case 'cod':
        return '<td class="mono" style="font-weight:600;letter-spacing:.02em;">'
          + esc(s) + '</td>';
      case 'ano_':
      case 'ano':
        return '<td style="text-align:center;font-weight:500;">'
          + esc(s) + '</td>';
      case 'pi_base':
      case 'codigo_item':
        return '<td class="mono" style="color:var(--text-soft);font-size:11.5px;">'
          + esc(s) + '</td>';
      case 'nome_projeto':
        var maxLen = 50;
        var truncated = s.length > maxLen
          ? s.substring(0, maxLen) + '...' : s;
        return '<td title="' + esc(s) + '" style="max-width:280px;'
          + 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
          + esc(truncated) + '</td>';
      case 'alimentador_principal':
        return '<td class="mono" style="font-weight:500;">'
          + esc(s.toUpperCase()) + '</td>';
      case 'alimentadores_beneficiados':
        return '<td class="mono" style="color:var(--text-soft);'
          + 'font-size:11px;max-width:140px;overflow:hidden;'
          + 'text-overflow:ellipsis;white-space:nowrap;" title="'
          + esc(s) + '">' + esc(s) + '</td>';
      case 'subestacao':
      case 'se':
        return '<td>' + (s
          ? '<span class="badge" style="background:var(--surface-3);'
            + 'font-family:var(--font-mono);font-weight:600;">'
            + esc(s.toUpperCase()) + '</span>'
          : '') + '</td>';
      case 'nome_regional':
        return '<td style="font-size:11.5px;">' + esc(s) + '</td>';
      case 'nome_superintendencia':
        return '<td style="font-size:11.5px;color:var(--text-soft);">'
          + esc(s) + '</td>';
      case 'tipo_pacote':
        return '<td>' + (s
          ? '<span class="badge ' + pacoteBadgeCls(s) + '">'
            + esc(s) + '</span>'
          : '') + '</td>';
      case 'quantidade_material':
        return '<td class="num mono" style="text-align:right;">'
          + fmtKm(s) + (s ? ' <span style="color:var(--text-soft);'
          + 'font-size:10.5px;">km</span>' : '') + '</td>';
      case 'valor_obra':
        return '<td class="num mono" style="text-align:right;">'
          + (s ? '<span style="color:var(--text-soft);font-size:10px;">'
          + 'R$</span> ' + fmtMoneyBr(s) : '') + '</td>';
      case 'obra_aprovada':
        var up = s.toUpperCase();
        if (up === 'SIM') {
          return '<td style="text-align:center;">'
            + '<span class="badge success">SIM</span></td>';
        }
        if (up === 'NÃO' || up === 'NAO') {
          return '<td style="text-align:center;">'
            + '<span class="badge" style="background:var(--surface-3);">'
            + 'NÃO</span></td>';
        }
        return '<td style="text-align:center;">' + esc(s) + '</td>';
      case 'tecnico_dirty':
        var dirty = s.toUpperCase();
        if (dirty === 'SIM') {
          return '<td style="text-align:center;" title="Snapshot tecnico'
            + ' desatualizado">'
            + '<i data-lucide="alert-triangle"'
            + ' style="width:14px;height:14px;color:var(--warning);"></i>'
            + '</td>';
        }
        if (dirty === 'NÃO' || dirty === 'NAO') {
          return '<td style="text-align:center;" title="Snapshot tecnico OK">'
            + '<i data-lucide="check"'
            + ' style="width:14px;height:14px;color:var(--success);"></i>'
            + '</td>';
        }
        return '<td style="text-align:center;color:var(--text-soft);">'
          + esc(s) + '</td>';
      case 'despacho_status':
        var ds = s.toUpperCase();
        if (ds === 'DESPACHADA') {
          return '<td style="text-align:center;">'
            + '<span class="badge" style="background:oklch(0.72 0.20 55);'
            + 'color:white;font-size:10px;">DESPACHADA</span></td>';
        }
        if (ds === 'CORRECAO' || ds === 'CORREÇÃO') {
          return '<td style="text-align:center;">'
            + '<span class="badge warning" style="font-size:10px;">'
            + 'CORREÇÃO</span></td>';
        }
        return '<td></td>';
      case 'manobra':
      case 'novo_bay':
        var b = s.toUpperCase();
        return '<td style="text-align:center;">' + (b
          ? '<span style="color:' + (b === 'SIM' ? 'var(--success)'
            : 'var(--text-soft)') + ';font-weight:600;font-size:11px;">'
            + esc(b) + '</span>' : '') + '</td>';
      case 'data_modificacao':
      case 'data_criacao':
      case 'despacho_em':
        return '<td class="mono" style="font-size:11px;'
          + 'color:var(--text-soft);">' + esc(s) + '</td>';
      default:
        // Coluna nao mapeada: comportamento legado
        return '<td class="mono">' + fmtCell(v) + '</td>';
    }
  }
  function rawRowHtml(rawRow, atende, codIdx, cols) {
    // [C10/H1] 3 estados de cor (replica desktop QColor):
    //   true  -> preto (sem classe extra) "atendeu criterios"
    //   false -> vermelho via .failed
    //   null/undefined -> cinza via .indef ("dados insuficientes")
    var cod = (codIdx >= 0 && rawRow[codIdx] != null) ? String(rawRow[codIdx]) : '';
    var rowCls = '';
    if (atende === false) rowCls = 'failed';
    else if (atende === null || atende === undefined) rowCls = 'indef';
    var html = '<tr class="' + rowCls
             + '" data-cod="' + esc(cod) + '">'
             + '<td class="check"><input type="checkbox" onclick="event.stopPropagation()"/></td>';
    var colsArr = Array.isArray(cols) ? cols : [];
    rawRow.forEach(function (v, idx) {
      var colName = colsArr[idx] || '';
      html += fmtCellRich(colName, v);
    });
    return html + '</tr>';
  }

  // Aplica filtro de colunas visiveis (config.ui_state.visualizar
  // .visible_columns) sobre cols + rawRows. Quando ha config (mascara
  // padrao ou customizada do user), so renderiza as colunas listadas
  // na ordem indicada por columns_order.
  function _applyVisibleColsFilter(cols, rawRows) {
    var cfg = window.__coplanColsCfg || null;
    if (!cfg) return { cols: cols, rawRows: rawRows };
    var visible = cfg.visible || [];
    if (!visible.length) return { cols: cols, rawRows: rawRows };
    var order = (cfg.order && cfg.order.length) ? cfg.order : visible;
    // Indices das colunas visiveis em cols, na ordem especificada
    var visSet = {};
    visible.forEach(function (c) { visSet[c] = true; });
    var ordered = [];
    order.forEach(function (c) {
      if (visSet[c] && cols.indexOf(c) >= 0
          && ordered.indexOf(c) < 0) {
        ordered.push(c);
      }
    });
    // Inclui visiveis nao listadas em order (defensivo)
    visible.forEach(function (c) {
      if (cols.indexOf(c) >= 0 && ordered.indexOf(c) < 0) {
        ordered.push(c);
      }
    });
    if (!ordered.length) return { cols: cols, rawRows: rawRows };
    var idxMap = ordered.map(function (c) {
      return cols.indexOf(c);
    });
    var newRaw = rawRows.map(function (r) {
      return idxMap.map(function (i) {
        return (i >= 0 && i < r.length) ? r[i] : '';
      });
    });
    return { cols: ordered, rawRows: newRaw };
  }

  // Carrega config de colunas visiveis no boot e atualiza quando
  // user salva no dialog "Configurar Colunas".
  function _loadColsCfg() {
    var a = window.pywebview && window.pywebview.api;
    if (!(a && a.visualizar_columns_get_config)) return Promise.resolve();
    return a.visualizar_columns_get_config().then(function (r) {
      if (r && r.ok) {
        window.__coplanColsCfg = {
          visible: r.visible || [],
          order:   r.order || [],
          all:     r.all || [],
          using_default: !!r.using_default,
        };
        // Se carregou DEPOIS do primeiro render, re-renderiza
        if (window.coplanObrasRaw && window.coplanObrasRaw.length
            && typeof window.coplanRenderObras === 'function') {
          window.coplanRenderObras();
        }
      }
    }).catch(function () {});
  }
  if (typeof window.coplanReady === 'function') {
    window.coplanReady(_loadColsCfg);
  }
  document.addEventListener('coplan:colunas-saved', _loadColsCfg);

  window.coplanRenderObras = function () {
    var tbody = document.getElementById('obras-tbody');
    if (!tbody) return;
    var rawCols = window.coplanObrasColumns || [];
    var rawRowsAll = window.coplanObrasRaw || [];
    var passouList = window.coplanObrasPassou || [];

    // Aplica mascara/config de colunas visiveis
    var filtered = _applyVisibleColsFilter(rawCols, rawRowsAll);
    var cols = filtered.cols;
    var rawRows = filtered.rawRows;

    // Header dinamico com colunas visiveis + col de checkbox.
    if (cols.length) rebuildThead(cols);

    if (!rawRows.length) {
      var n = (cols.length || 0) + 1;
      tbody.innerHTML = '<tr><td colspan="' + n + '" '
        + 'style="padding:24px;text-align:center;color:var(--text-soft)">'
        + (cols.length
            ? 'Nenhuma obra encontrada no banco.'
            : 'Banco nao conectado. Va em Configuracoes -> Empresa para apontar o caminho.')
        + '</td></tr>';
    } else {
      var codIdx = cols.indexOf('cod');
      tbody.innerHTML = rawRows.map(function (r, i) {
        // [C10] passa atende cru (true/false/null) para rawRowHtml
        // diferenciar 3 cores. Default null se nao houver entry.
        // cols passado p/ rawRowHtml usar fmtCellRich(colName, v).
        var atende = (i < passouList.length) ? passouList[i] : null;
        return rawRowHtml(r, atende, codIdx, cols);
      }).join('');
    }
    if (window.lucide) lucide.createIcons();
    if (typeof window.coplanSetSelectionCount === 'function') {
      window.coplanSetSelectionCount(0, rawRows.length);
    }
    document.dispatchEvent(new CustomEvent('coplan:obras', {
      detail: { rows: window.coplanObras || [] },
    }));
    // Visualizar Sprint 1 (Auditoria #3): re-aplica highlight do Plano
    // de Obras se ativo. Sem isso, paginar/filtrar/recarregar perde as
    // celulas cinza/verde. Paridade com aplicar_atualizacao_plano em
    // load_obras_into_table do desktop.
    if (typeof window.coplanReplayPlanoState === 'function') {
      try { window.coplanReplayPlanoState(); } catch (_e) {}
    }
  };

  window.coplanLoadObras = function () {
    if (!(window.pywebview && window.pywebview.api && window.pywebview.api.list_obras)) {
      return Promise.resolve();
    }
    return window.pywebview.api.list_obras(null).then(function (resp) {
      if (!resp || resp.error) {
        console.warn('[coplan] list_obras erro:', resp && resp.error);
        window.coplanObras = [];
        window.coplanObrasRaw = [];
        window.coplanObrasColumns = [];
        window.coplanObrasPassou = [];
      } else {
        window.coplanObras = resp.rows || [];           // curado (compat)
        window.coplanObrasRaw = resp.raw_rows || [];    // todas as colunas
        window.coplanObrasColumns = resp.columns || []; // nomes das colunas
        window.coplanObrasPassou = resp.passou_per_row || [];
      }
      window.coplanRenderObras();
    }).catch(function (e) {
      console.warn('[coplan] list_obras catch:', e);
      window.coplanObras = [];
      window.coplanObrasRaw = [];
      window.coplanObrasColumns = [];
      window.coplanObrasPassou = [];
      window.coplanRenderObras();
    });
  };

  // Carrega no boot (depois que o mock ja renderizou a versao fake).
  window.coplanReady(function () { setTimeout(window.coplanLoadObras, 0); });
  // Recarrega ao voltar para a aba Visualizar.
  // [FIX] Se ha filtros ou query ativa, preserva o estado: usa
  // coplanApplySearch (que aplica window.coplanFilters + coplanQuery).
  // Antes: chamava sempre coplanLoadObras(null) que zera os filtros.
  document.addEventListener('coplan:tab', function (e) {
    if (!(e && e.detail && e.detail.name === 'visualizar')) return;
    var f = window.coplanFilters || {};
    var hasFilters = Object.keys(f).some(function (k) {
      var v = f[k];
      if (v == null || v === '') return false;
      if (Array.isArray(v)) return v.length > 0;
      return true;
    });
    var hasQuery = !!(window.coplanQuery && String(window.coplanQuery).trim());
    if ((hasFilters || hasQuery) && typeof window.coplanApplySearch === 'function') {
      window.coplanApplySearch();
    } else {
      window.coplanLoadObras();
    }
  });
})();
</script>
<script>
(function () {
  // ---- C8/C9 - Persistencia de larguras de coluna (Visualizar) ----
  // Replica visualizar_colunas_mixin._on_visualizar_section_resized +
  // _flush_visualizar_column_widths do desktop. Captura mouseup em
  // <th> com resize:horizontal nativo do CSS, debounce + envia para
  // visualizar_columns_save_config({widths: {col: px}}).
  //
  // Apply: ao rebuildThead (chamado por coplanRenderObras), aplica
  // o style.width gravado em window.__coplanColWidths.
  var SAVE_DEBOUNCE_MS = 600;
  var saveTimer = null;
  var pendingWidths = {};
  function getCachedWidths() {
    return window.__coplanColWidths || null;
  }
  function setCachedWidths(w) {
    window.__coplanColWidths = w || {};
  }
  // [C9] Aplica widths salvos a cada <th data-col=...>
  window.coplanApplyColWidths = function () {
    var widths = getCachedWidths();
    if (!widths) return;
    var ths = document.querySelectorAll(
      '#obras-table thead th[data-col]');
    ths.forEach(function (th) {
      var c = th.getAttribute('data-col');
      var px = widths[c];
      if (px && Number.isFinite(Number(px))) {
        // Em table-layout:fixed, width no <th> da primeira linha
        // determina a coluna toda. min/max reforcam contra recalc.
        th.style.width = px + 'px';
        th.style.minWidth = px + 'px';
        th.style.maxWidth = px + 'px';
      }
    });
  };

  // [H6] Auto-fit colunas: para cada <th data-col> SEM largura
  // persistida em __coplanColWidths, calcula largura otima baseado
  // no conteudo das primeiras N celulas. Replica
  // resizeColumnsToContents do desktop (Qt). Limite [80, 360] px.
  window.coplanAutoFitColumns = function () {
    var ths = document.querySelectorAll(
      '#obras-table thead th[data-col]');
    if (!ths.length) return;
    var widths = getCachedWidths() || {};
    var tbody = document.getElementById('obras-tbody');
    if (!tbody) return;
    // Sample primeiras 30 linhas para nao varrer 1000+
    var SAMPLE = 30;
    var rows = tbody.querySelectorAll('tr[data-cod]');
    var sampleRows = Array.prototype.slice.call(rows, 0, SAMPLE);
    // Helper: usa canvas para medir texto sem reflow expensive
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    // Pega font do primeiro <th> para mesma metrica
    var bodyFont = window.getComputedStyle(rows[0] || ths[0]).font
                || '12.5px Inter, sans-serif';
    ctx.font = bodyFont;
    var headFont = ths[0]
      ? window.getComputedStyle(ths[0]).font
      : bodyFont;
    ths.forEach(function (th) {
      var col = th.getAttribute('data-col');
      if (!col) return;
      // Se ja tem width persistido, NAO sobrescreve (user decidiu)
      if (widths[col] && Number.isFinite(Number(widths[col]))) return;
      // Mede header
      ctx.font = headFont;
      var maxPx = ctx.measureText(th.textContent.trim()).width + 28;
      // Mede conteudo das celulas sample
      ctx.font = bodyFont;
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      sampleRows.forEach(function (tr) {
        var td = tr.children[idx];
        if (!td) return;
        var w = ctx.measureText(td.textContent.trim()).width + 24;
        if (w > maxPx) maxPx = w;
      });
      // Clamp [80, 360]
      maxPx = Math.max(80, Math.min(360, Math.round(maxPx)));
      th.style.width = maxPx + 'px';
    });
  };
  function loadColWidthsFromBackend() {
    var a = window.pywebview && window.pywebview.api;
    if (!(a && a.visualizar_columns_get_config)) return;
    a.visualizar_columns_get_config().then(function (r) {
      if (r && r.ok && r.widths && typeof r.widths === 'object') {
        setCachedWidths(r.widths);
        // Aplica imediatamente se thead ja existe
        window.coplanApplyColWidths();
      } else {
        setCachedWidths({});
      }
    }).catch(function () {});
  }
  function flushSave() {
    saveTimer = null;
    if (Object.keys(pendingWidths).length === 0) return;
    var a = window.pywebview && window.pywebview.api;
    if (!(a && a.visualizar_columns_save_config)) {
      console.warn('[coplan-resize] save_config indisponivel');
      pendingWidths = {};
      return;
    }
    var widths = Object.assign({}, getCachedWidths() || {}, pendingWidths);
    setCachedWidths(widths);
    var sent = pendingWidths;
    pendingWidths = {};
    console.log('[coplan-resize] flushSave', sent, '-> total', widths);
    a.visualizar_columns_save_config({ widths: widths }).then(function (r) {
      console.log('[coplan-resize] save result', r);
      if (!(r && r.ok) && typeof window.coplanToast === 'function') {
        window.coplanToast('Falha ao salvar larguras: '
                           + (r && r.error || '?'), 'warn');
      }
    }).catch(function (e) {
      console.warn('[coplan-resize] save catch', e);
    });
  }
  function bumpSave(col, px) {
    if (!col) return;
    console.log('[coplan-resize] bumpSave', col, px);
    pendingWidths[col] = px;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(flushSave, SAVE_DEBOUNCE_MS);
  }
  // Drag-to-resize via handle .col-resizer customizado.
  // mousedown captura largura inicial + clientX; mousemove ajusta;
  // mouseup persiste via bumpSave (debounced 300ms).
  var _resizing = null;  // {th, col, startX, startW}
  document.addEventListener('mousedown', function (ev) {
    var handle = ev.target && ev.target.classList
                 && ev.target.classList.contains('col-resizer')
                 ? ev.target : null;
    if (!handle) return;
    var th = handle.closest('th');
    if (!th) return;
    var col = handle.getAttribute('data-resize-col')
              || th.getAttribute('data-col');
    if (!col) return;
    ev.preventDefault();
    ev.stopPropagation();
    handle.classList.add('resizing');
    document.body.classList.add('coplan-resizing');
    _resizing = {
      th: th,
      col: col,
      handle: handle,
      startX: ev.clientX,
      startW: th.offsetWidth,
    };
  }, true);
  document.addEventListener('mousemove', function (ev) {
    if (!_resizing) return;
    var dx = ev.clientX - _resizing.startX;
    var newW = Math.max(60, Math.min(800, _resizing.startW + dx));
    _resizing.th.style.width = newW + 'px';
    _resizing.th.style.maxWidth = newW + 'px';
    _resizing.th.style.minWidth = newW + 'px';
  }, true);
  document.addEventListener('mouseup', function (ev) {
    if (!_resizing) return;
    var r = _resizing;
    _resizing = null;
    if (r.handle) r.handle.classList.remove('resizing');
    document.body.classList.remove('coplan-resizing');
    var finalW = r.th.offsetWidth;
    if (Math.abs(finalW - r.startW) < 2) return;  // sem mudanca real
    bumpSave(r.col, finalW);
  }, true);
  // Boot: carrega widths e dispara primeiro apply
  window.coplanReady && window.coplanReady(function () {
    loadColWidthsFromBackend();
  });
  // Recarregar config quando user trocar config via dialog Colunas
  document.addEventListener('coplan:colunas-saved', function () {
    loadColWidthsFromBackend();
  });
  // Re-aplicar widths apos render de obras (rebuildThead chama
  // coplanApplyColWidths inline; este listener cobre casos
  // alternativos/race onde rebuildThead nao foi chamado).
  document.addEventListener('coplan:obras', function () {
    setTimeout(function () {
      // [H6] Primeiro auto-fit colunas sem largura persistida,
      // depois aplica widths persistidos por cima (para sobrescrever
      // o auto-fit nas que o user customizou).
      if (typeof window.coplanAutoFitColumns === 'function') {
        window.coplanAutoFitColumns();
      }
      window.coplanApplyColWidths();
    }, 30);
  });
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 3.2 (Visualizar / stat cards) ----
  // Atualiza os 4 cards do topo de Visualizar (.stats-grid > .stat).
  // Como o mock nao deu ids aos cards, identificamos por posicao:
  //   0 = Obras no banco | 1 = Aprovadas | 2 = Pendentes | 3 = Valor planejado.
  function fmtBR(n) {
    return Number(n || 0).toLocaleString('pt-BR');
  }
  function fmtMoney(v) {
    var n = Number(v || 0);
    if (n >= 1e9) return 'R$ ' + (n / 1e9).toFixed(1).replace('.', ',') + 'B';
    if (n >= 1e6) return 'R$ ' + (n / 1e6).toFixed(0) + 'M';
    if (n >= 1e3) return 'R$ ' + (n / 1e3).toFixed(0) + 'K';
    return 'R$ ' + fmtBR(Math.round(n));
  }
  function setCard(grid, idx, value, deltaText, deltaCls) {
    var card = grid.children[idx];
    if (!card) return;
    var v = card.querySelector('.stat-value');
    var d = card.querySelector('.stat-delta');
    if (v) v.textContent = value;
    if (d && deltaText !== undefined) {
      d.textContent = deltaText;
      d.classList.remove('up', 'down');
      if (deltaCls) d.classList.add(deltaCls);
    }
  }
  window.coplanRenderStats = function (stats) {
    var grid = document.querySelector('#tab-visualizar .stats-grid');
    if (!grid || !stats || !stats.ok) return;
    var total = stats.total || 0;
    var aprovadas = stats.aprovadas || 0;
    var pendentes = stats.pendentes || 0;
    var valor = stats.valor_total || 0;
    var pct = total > 0 ? (aprovadas * 100 / total) : 0;
    // [FIX] CAPEX usa o ANO CORRENTE (previsivel e atualiza sozinho a
    // cada virada de ano), em vez do ano_dominante do banco — que
    // dependia do conteudo das obras e parecia "congelado" pra o user.
    var anoCorrente = (new Date()).getFullYear();
    setCard(grid, 0, fmtBR(total),
            stats._filtered ? 'apos filtros' : 'no banco', '');
    setCard(grid, 1, fmtBR(aprovadas),
            pct.toFixed(1).replace('.', ',') + '% do total', 'up');
    setCard(grid, 2, fmtBR(pendentes),
            pendentes ? 'aguardando aprovacao' : 'tudo aprovado',
            pendentes ? 'down' : 'up');
    setCard(grid, 3, fmtMoney(valor),
            'CAPEX ' + anoCorrente, 'up');
    // [FIX] Page-title dinamico: "Visualizar Obras (N filtradas / total)"
    // Quando ha filtro, mostra "X de Y"; sem filtro, "X obras".
    try {
      var pt = document.getElementById('page-title');
      if (pt && pt.textContent.indexOf('Visualizar') === 0) {
        var sufixo;
        if (stats._filtered) {
          var totalRaw = (window.__coplanTotalSemFiltro || total);
          sufixo = ' (' + fmtBR(total) + ' de ' + fmtBR(totalRaw) + ')';
        } else {
          sufixo = ' (' + fmtBR(total) + ')';
          window.__coplanTotalSemFiltro = total;
        }
        pt.textContent = 'Visualizar Obras' + sufixo;
      }
    } catch (e) { /* swallow */ }
  };
  window.coplanLoadStats = function () {
    if (!(window.pywebview && window.pywebview.api && window.pywebview.api.get_obras_stats)) {
      return Promise.resolve();
    }
    return window.pywebview.api.get_obras_stats().then(function (s) {
      window.__coplanStats = s;
      window.coplanRenderStats(s);
    }).catch(function (e) {
      console.warn('[coplan] get_obras_stats catch:', e);
    });
  };
  // [G5] Stats reagem a filtros: quando ha filtros ativos
  // (coplanQuery OU coplanFilters), calcula stats localmente a partir
  // de coplanObrasRaw + colunas conhecidas. Sem filtros: chama API.
  function hasActiveFilter() {
    var q = String(window.coplanQuery || '').trim();
    var f = window.coplanFilters || {};
    var hasF = Object.keys(f).some(function (k) {
      return f[k] != null && String(f[k]).trim() !== '';
    });
    return !!q || hasF;
  }
  function statsFromFiltered() {
    var raw = window.coplanObrasRaw || [];
    var cols = window.coplanObrasColumns || [];
    if (!cols.length) return null;
    var i_aprov = cols.indexOf('obra_aprovada');
    var i_valor = cols.indexOf('valor_obra');
    var total = raw.length;
    var aprovadas = 0;
    var valor = 0;
    for (var i = 0; i < raw.length; i++) {
      var r = raw[i];
      if (i_aprov >= 0
          && String(r[i_aprov] || '').trim().toUpperCase() === 'SIM') {
        aprovadas++;
      }
      if (i_valor >= 0) {
        var v = parseFloat(String(r[i_valor] || '0').replace(',', '.'));
        if (!isNaN(v)) valor += v;
      }
    }
    return {
      total: total,
      aprovadas: aprovadas,
      pendentes: total - aprovadas,
      valor_total: valor,
      _filtered: true,
    };
  }
  window.coplanLoadStatsFiltered = function () {
    if (!hasActiveFilter()) {
      return window.coplanLoadStats();
    }
    var s = statsFromFiltered();
    if (s) {
      window.__coplanStats = s;
      window.coplanRenderStats(s);
    }
    return Promise.resolve(s);
  };
  // Sempre que a lista de obras for recarregada, refresca tambem os stats
  // (depois de save/delete o list_obras dispara coplan:obras).
  // [G5] Usa versao filtered-aware se ha filtros ativos.
  document.addEventListener('coplan:obras', function () {
    window.coplanLoadStatsFiltered();
  });
  // Boot inicial.
  window.coplanReady(function () { setTimeout(window.coplanLoadStats, 0); });
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 3.3 (Visualizar / search + filtros) ----
  // Conecta a busca textual e o modal de filtros avancados a API
  // search_obras. Usa debounce na busca (200ms) para nao chamar Python
  // a cada tecla.
  window.coplanQuery = '';
  window.coplanFilters = {};

  // Visualizar Sprint 1 (Auditoria #1): expoe lista de cods atualmente
  // filtrados em Visualizar para os cards do Resumo respeitarem o
  // mesmo escopo. Retorna null quando NAO ha filtros ativos (banco
  // inteiro), retorna [] quando filtros zerarem o resultado.
  window.coplanFilteredCods = function () {
    var q = String(window.coplanQuery || '').trim();
    var f = window.coplanFilters || {};
    var hasFilter = !!q;
    if (!hasFilter) {
      for (var k in f) {
        if (!Object.prototype.hasOwnProperty.call(f, k)) continue;
        var v = f[k];
        if (v === null || v === undefined) continue;
        if (Array.isArray(v) && v.length === 0) continue;
        if (String(v).trim() === '') continue;
        hasFilter = true;
        break;
      }
    }
    if (!hasFilter) return null;
    var rows = window.coplanObras || [];
    var out = [];
    for (var i = 0; i < rows.length; i++) {
      var c = rows[i] && rows[i].cod;
      if (c) out.push(String(c));
    }
    return out;
  };

  function debounce(fn, ms) {
    var t = null;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }
  function byLabel(modal, labelText) {
    // Cada .field tem [label, input/select]. Procura pelo label cujo texto
    // comece com labelText (case-insensitive).
    var fields = modal.querySelectorAll('.field');
    var lower = labelText.toLowerCase();
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      if (lab.textContent.trim().toLowerCase().indexOf(lower) === 0) {
        return fields[i].querySelector('input, select');
      }
    }
    return null;
  }
  function activePillText(field) {
    var p = field && field.querySelector('.pill.active');
    return p ? p.textContent.trim() : '';
  }

  window.coplanApplySearch = function () {
    if (!(window.pywebview && window.pywebview.api && window.pywebview.api.search_obras)) {
      return Promise.resolve();
    }
    return window.pywebview.api.search_obras(
      window.coplanQuery, window.coplanFilters
    ).then(function (resp) {
      if (resp && resp.ok) {
        window.coplanObras = resp.rows || [];
        // Mantem os arrays paralelos sincronizados com o filtro
        // (renderer fiel mostra todas as colunas via raw_rows).
        window.coplanObrasRaw = resp.raw_rows || [];
        window.coplanObrasPassou = resp.passou_per_row || [];
        if (resp.columns && resp.columns.length) {
          window.coplanObrasColumns = resp.columns;
        }
        if (typeof window.coplanRenderObras === 'function') window.coplanRenderObras();
        // stats refletem total geral, nao filtrado: mantemos coplanLoadStats
        // separado (event coplan:obras o re-dispara). Aqui nao chamamos.
      } else {
        console.warn('[coplan] search_obras erro:', resp && resp.error);
      }
    }).catch(function (err) {
      console.warn('[coplan] search_obras catch:', err);
      if (typeof window.coplanToast === 'function') {
        window.coplanToast(
          'Falha ao pesquisar obras: '
          + ((err && err.message) || err || '?'),
          'error');
      }
      if (window.coplanReportError) {
        window.coplanReportError(
          'Pesquisar obras', 'search_obras',
          { error: String((err && err.message) || err || '?') });
      }
    });
  };

  function readModalFilters() {
    var modal = document.getElementById('modal-filtros');
    if (!modal) return {};
    var f = {};
    var pairs = [
      ['cod', 'COD'], ['ano', 'Ano'], ['pi', 'PI'],
      ['projeto', 'Projeto'], ['alim', 'Alimentador'],
      ['alim_benef', 'Alimentadores Beneficiados'],
      ['regional', 'Regional'], ['superintendencia', 'Superintend'],
      ['se', 'Subesta'], ['pacote', 'Pacote'],
      ['tecnico', 'Tecnico Atualizado'],
    ];
    pairs.forEach(function (kv) {
      // Tenta chave acentuada e nao acentuada (HTML usa acento).
      var node = byLabel(modal, kv[1]);
      if (!node) {
        // Normaliza acentos para casar (ex.: Subestacao vs Subestação).
        var labels = modal.querySelectorAll('.field label');
        for (var i = 0; i < labels.length; i++) {
          var t = labels[i].textContent.trim().toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '');
          if (t.indexOf(kv[1].toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')) === 0) {
            node = labels[i].parentElement.querySelector('input, select');
            break;
          }
        }
      }
      if (node) {
        // Multi-select: junta selecoes por ; (search_obras split por isso).
        if (node.tagName === 'SELECT' && node.hasAttribute('multiple')
            && typeof window.coplanReadMultiSelect === 'function') {
          f[kv[0]] = window.coplanReadMultiSelect(node);
        } else {
          f[kv[0]] = String(node.value || '').trim();
        }
      }
    });
    // Aprovada e Criterios vivem no pill-row "Criterios" do modal.
    var critField = null;
    var allFields = modal.querySelectorAll('.field');
    for (var j = 0; j < allFields.length; j++) {
      var lab = allFields[j].querySelector('label');
      if (lab && lab.textContent.trim().toLowerCase().indexOf('crit') === 0) {
        critField = allFields[j];
        break;
      }
    }
    var critTxt = activePillText(critField);
    if (critTxt && critTxt.toLowerCase() !== 'todas') {
      // "Aprovadas" / "Nao aprovadas" -> mapeia para filter aprovada SIM/NAO.
      var lower = critTxt.toLowerCase();
      if (lower === 'aprovadas') f.aprovada = 'SIM';
      else if (lower.indexOf('apro') === 0) f.aprovada = 'NAO';
      else f.criterios = critTxt;
    }
    return f;
  }

  function bindFilterBar() {
    var visTab = document.getElementById('tab-visualizar');
    if (!visTab) return false;

    // ---- 1. Busca textual ----
    var input = visTab.querySelector('.search-input input');
    if (input) {
      var apply = debounce(function () {
        window.coplanApplySearch();
      }, 200);
      input.addEventListener('input', function (e) {
        window.coplanQuery = String(e.target.value || '');
        apply();
      });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          input.value = '';
          window.coplanQuery = '';
          apply();
        }
      });
    }

    // ---- 2. Botao Limpar ----
    // Identificamos o botao pelo label "Limpar" no .filter-bar principal.
    var btns = visTab.querySelectorAll('.filter-bar .btn');
    btns.forEach(function (b) {
      var t = b.textContent.trim().toLowerCase();
      if (t === 'limpar') {
        b.addEventListener('click', function () {
          window.coplanQuery = '';
          window.coplanFilters = {};
          if (input) input.value = '';
          // Limpa tambem inputs do modal.
          var modal = document.getElementById('modal-filtros');
          if (modal) {
            modal.querySelectorAll('input').forEach(function (i) { i.value = ''; });
            modal.querySelectorAll('select').forEach(function (s) { s.selectedIndex = 0; });
            modal.querySelectorAll('.pill').forEach(function (p) { p.classList.remove('active'); });
            var first = modal.querySelector('.pill');
            if (first) first.classList.add('active');
          }
          window.coplanApplySearch();
        });
      }
    });

    // ---- 3. Modal "Aplicar filtros" ----
    var modal = document.getElementById('modal-filtros');
    if (modal) {
      var footerBtns = modal.querySelectorAll('.modal-footer .btn');
      footerBtns.forEach(function (b) {
        var t = b.textContent.trim().toLowerCase();
        if (t.indexOf('aplicar') === 0) {
          b.addEventListener('click', function () {
            window.coplanFilters = readModalFilters();
            window.coplanApplySearch();
          });
        } else if (t.indexOf('limpar') === 0) {
          b.addEventListener('click', function () {
            window.coplanFilters = {};
            modal.querySelectorAll('input').forEach(function (i) { i.value = ''; });
            modal.querySelectorAll('select').forEach(function (s) { s.selectedIndex = 0; });
            modal.querySelectorAll('.pill').forEach(function (p) { p.classList.remove('active'); });
            var first = modal.querySelector('.pill');
            if (first) first.classList.add('active');
            window.coplanApplySearch();
          });
        }
      });
    }

    // ---- 4. Atalho Ctrl+F + [I2] Ctrl+L (alias) (preventDefault para
    // nao abrir busca do browser nem barra de URL) ----
    document.addEventListener('keydown', function (e) {
      if (!(e.ctrlKey || e.metaKey)) return;
      var k = e.key;
      // Ctrl+F = busca; Ctrl+L = mesma coisa (replica desktop
      // shortcut_focus_filter_global Ctrl+L do visualizar_mixin)
      var isFind = (k === 'f' || k === 'F'
                  || k === 'l' || k === 'L');
      if (!isFind) return;
      if (!visTab.classList.contains('active')) return;
      e.preventDefault();
      if (input) { input.focus(); input.select(); }
    });

    // ---- [I4] Ctrl+C copia CODs selecionados quando Visualizar
    // esta ativa E foco NAO esta em input/textarea (deixa Ctrl+C
    // nativo funcionar para texto selecionado). Replica desktop
    // _visualizar_copy_shortcut do visualizar_mixin. ----
    document.addEventListener('keydown', function (e) {
      if (!((e.ctrlKey || e.metaKey)
          && (e.key === 'c' || e.key === 'C'))) return;
      if (!visTab.classList.contains('active')) return;
      var t = e.target;
      // Se foco em input/textarea/select, deixa Ctrl+C nativo funcionar
      var tag = t && t.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
          || (t && t.isContentEditable)) return;
      // Se ha selecao de texto na pagina (ranges), deixa Ctrl+C nativo
      var sel = window.getSelection && window.getSelection();
      if (sel && String(sel) && String(sel).length > 0) return;
      // Visualizar Sprint 1 (Auditoria #6): formato planilha TSV das
      // linhas selecionadas (todas as colunas exceto checkbox). Paridade
      // com _copy_visualizar_selection_to_clipboard do desktop.
      // Pega rows com checkbox marcado.
      var rows = Array.prototype.filter.call(
        document.querySelectorAll('#obras-tbody tr[data-cod]'),
        function (tr) {
          var cb = tr.querySelector('input[type="checkbox"]');
          return cb && cb.checked;
        }
      );
      if (!rows.length) return;
      e.preventDefault();
      // Cabecalho a partir do thead (skip checkbox col).
      var headers = [];
      var thead = document.querySelector('#obras-table thead tr');
      if (thead) {
        var ths = thead.querySelectorAll('th');
        for (var hi = 0; hi < ths.length; hi++) {
          var th = ths[hi];
          if (th.classList.contains('check')) continue;
          // Skip ultima coluna que costuma ser actions (sem texto)
          var txt = (th.textContent || '').trim();
          if (txt) headers.push(txt);
        }
      }
      // Linhas: extrai textContent de cada <td> exceto a checkbox.
      var tsvLines = [];
      if (headers.length) tsvLines.push(headers.join('\t'));
      rows.forEach(function (tr) {
        var tds = tr.querySelectorAll('td');
        var cells = [];
        for (var ci = 0; ci < tds.length; ci++) {
          var td = tds[ci];
          if (td.classList.contains('check')) continue;
          // Limpa whitespace interno (badges/icones)
          var t = (td.textContent || '').replace(/\s+/g, ' ').trim();
          cells.push(t);
        }
        // Remove ultima coluna se for vazia (botao actions)
        while (cells.length && cells[cells.length - 1] === '') cells.pop();
        tsvLines.push(cells.join('\t'));
      });
      var txt = tsvLines.join('\n');
      function visCopyOk() {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast(rows.length + ' linha(s) copiada(s)'
            + ' (TSV)', 'info');
        }
      }
      function visCopyErr() {
        if (typeof window.coplanToast === 'function') {
          window.coplanToast('Falha ao copiar para a area de'
            + ' transferencia', 'error');
        }
      }
      function visCopyExec() {
        try {
          var ta = document.createElement('textarea');
          ta.value = txt;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          var ok = document.execCommand('copy');
          document.body.removeChild(ta);
          return !!ok;
        } catch (_e) { return false; }
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(visCopyOk, function () {
          if (visCopyExec()) visCopyOk(); else visCopyErr();
        });
      } else {
        if (visCopyExec()) visCopyOk(); else visCopyErr();
      }
    });

    return true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindFilterBar);
  } else {
    if (!bindFilterBar()) setTimeout(bindFilterBar, 50);
  }
})();
</script>
<script>
(function () {
  // ---- Modal Filtros: popular selects do banco + multi-selecao ----
  // O HTML mock vem com <option> hardcoded ('CENTRO/LESTE/...', 'Mercado/
  // Confiabilidade'). Aqui:
  //   1) Substituimos por valores reais derivados de window.coplanObrasRaw
  //      (e tambem das APIs get_pacotes / get_regionais como fallback).
  //   2) Convertimos os selects de 1 valor para <select multiple> para
  //      permitir filtrar por mais de um.
  //   3) Trocamos o input "Ano" para aceitar varios anos (placeholder
  //      explicando) -- search_obras ja split por ; , espaco.
  //
  // Funciona sem reload: re-roda em coplan:obras (quando dados chegam) e
  // tambem ao abrir o modal (#btn-modal-filtros).
  // [FIX] PI tambem vira multi-select (com distincts de
  // projeto_investimento). Ano ja era tratado a parte abaixo.
  var MULTI_LABELS = ['PI', 'Regional', 'Superintend', 'Subesta', 'Pacote',
                      'Tecnico Atualizado'];
  // Mapeia label do modal -> nome de coluna em window.coplanObrasRaw.
  // [FIX] Usa nomes REAIS de coluna SQLite (nome_regional, nome_super-
  // intendencia, subestacao) — antes usava aliases que nao existem em
  // coplanObrasColumns, fazendo distinctFromRaw() retornar [] e o
  // fallback get_regionais()/get_pacotes() poluir o select com TUDO
  // do config em vez de mostrar so o que esta no banco.
  var COL_FOR_LABEL = {
    'pi':                 'projeto_investimento',
    'regional':           'nome_regional',
    'superintend':        'nome_superintendencia',
    'subesta':            'subestacao',
    'pacote':             'tipo_pacote',
    'tecnico atualizado': 'tecnico_dirty'
  };
  function deAccent(s) {
    return String(s || '').toLowerCase().normalize('NFD')
      .replace(/[̀-ͯ]/g, '');
  }
  function findFieldByLabelStartsWith(modal, prefix) {
    var fields = modal.querySelectorAll('.field');
    var pref = deAccent(prefix);
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      if (deAccent(lab.textContent.trim()).indexOf(pref) === 0) {
        return fields[i];
      }
    }
    return null;
  }
  function distinctFromRaw(colName) {
    var cols = window.coplanObrasColumns || [];
    var raw = window.coplanObrasRaw || [];
    var idx = cols.indexOf(colName);
    if (idx < 0 || !raw.length) return [];
    var seen = {};
    var out = [];
    for (var i = 0; i < raw.length; i++) {
      var v = raw[i][idx];
      if (v === null || typeof v === 'undefined') continue;
      var s = String(v).trim();
      if (!s) continue;
      var k = s.toUpperCase();
      if (!seen[k]) { seen[k] = true; out.push(s); }
    }
    out.sort();
    return out;
  }
  function ensureMulti(sel, label) {
    if (!sel || sel.tagName !== 'SELECT') return;
    if (!sel.hasAttribute('multiple')) {
      sel.setAttribute('multiple', 'multiple');
      sel.setAttribute('size', '5');
      sel.style.minHeight = '110px';
      sel.title = 'Segure Ctrl (ou Cmd) para selecionar varios';
    }
  }
  function rebuildOptions(sel, items, allowEmpty) {
    if (!sel) return;
    // Preserva selecao atual.
    var sel_now = [];
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].selected && sel.options[i].value) {
        sel_now.push(sel.options[i].value);
      }
    }
    // [FIX] Se o select foi recem-convertido de input, herda o valor
    // que o user havia digitado (separado por ; , ou espaco).
    if (!sel_now.length && sel.__pendingPreselect) {
      var pending = String(sel.__pendingPreselect).split(/[;,\s]+/);
      pending.forEach(function (v) {
        var s = String(v || '').trim();
        if (s) sel_now.push(s);
      });
      sel.__pendingPreselect = null;
    }
    sel.innerHTML = '';
    // Em modo multiple nao precisa de placeholder -- vazio = sem filtro.
    // Em single, mantem a primeira opcao vazia para "qualquer".
    if (allowEmpty && !sel.hasAttribute('multiple')) {
      var optAll = document.createElement('option');
      optAll.value = ''; optAll.textContent = '— qualquer —';
      sel.appendChild(optAll);
    }
    items.forEach(function (it) {
      var o = document.createElement('option');
      // [B19] Aceita string OU par [value, label] para casos onde
      // o label exibido difere do value enviado ao backend.
      if (Array.isArray(it) && it.length >= 2) {
        o.value = it[0]; o.textContent = it[1];
      } else {
        o.value = it; o.textContent = it;
      }
      if (sel_now.indexOf(o.value) >= 0) o.selected = true;
      sel.appendChild(o);
    });
  }
  // Converte um <input> para <select multiple> in-place (Ano/PI/etc.).
  function inputToMultiSelect(currentEl, hint) {
    if (!currentEl || currentEl.tagName !== 'INPUT') return currentEl;
    var newSel = document.createElement('select');
    newSel.className = currentEl.className || 'select';
    newSel.setAttribute('multiple', 'multiple');
    newSel.setAttribute('size', '5');
    newSel.style.minHeight = '110px';
    newSel.title = 'Segure Ctrl (ou Cmd) para selecionar varios '
      + (hint || 'itens');
    // Preserva qualquer valor digitado: vira pre-selecao quando vier
    // como option distinta (ex.: "2026" digitado vira selected:true).
    var prev = String(currentEl.value || '').trim();
    currentEl.parentNode.replaceChild(newSel, currentEl);
    if (prev) newSel.__pendingPreselect = prev;
    return newSel;
  }

  function populateFilterModal() {
    var modal = document.getElementById('modal-filtros');
    if (!modal) return;
    // 1. Converte selects relevantes em multi + popula com distintos.
    MULTI_LABELS.forEach(function (lbl) {
      var fld = findFieldByLabelStartsWith(modal, lbl);
      if (!fld) return;
      var sel = fld.querySelector('select, input');
      if (!sel) return;
      // [FIX] Se ainda e <input> (caso de PI no mock), converte agora.
      if (sel.tagName === 'INPUT') {
        sel = inputToMultiSelect(sel, lbl.toLowerCase());
      }
      ensureMulti(sel, lbl);
      var col = COL_FOR_LABEL[deAccent(lbl)];
      var items = col ? distinctFromRaw(col) : [];
      // Tecnico/Aprovada sao SIM/NAO -- nao vem de raw, hardcode.
      if (lbl.indexOf('Tecnico') === 0) {
        // [B19] Para "Tecnico Atualizado" usamos labels descritivos
        // mas mantemos values SIM/NAO para o backend continuar
        // mapeando bool(tecAtual) == (val === "SIM"). Items aqui sao
        // pares [value, label].
        items = [
          ['SIM', 'Atualizado (SIM)'],
          ['NAO', 'Desatualizado (NÃO)'],
        ];
      }
      rebuildOptions(sel, items, true);
    });
    // 2. Ano: vira <select multiple> tambem (anos sao poucos e enumeraveis).
    var anoFld = findFieldByLabelStartsWith(modal, 'Ano');
    if (anoFld) {
      var anoCur = anoFld.querySelector('input, select');
      var anos = distinctFromRaw('ano_');
      if (!anos.length) anos = distinctFromRaw('ano');
      if (anos.length) {
        // Substitui o input por um select multiple no mesmo lugar.
        if (anoCur && anoCur.tagName === 'INPUT') {
          anoCur = inputToMultiSelect(anoCur, 'anos');
        } else if (anoCur && anoCur.tagName === 'SELECT') {
          ensureMulti(anoCur, 'Ano');
        }
        rebuildOptions(anoCur, anos, true);
      }
    }
    // 3. Fallback assincrono: get_pacotes / get_regionais SOMENTE quando
    //    nao ha banco carregado (raw vazio). Quando ha obras carregadas,
    //    a lista deve refletir SO o que existe no banco — feedback do
    //    usuario: "ler somente o que existe no banco e nao todas as
    //    opcoes de regional e superintendencia cadastradas".
    var apiNow = window.pywebview && window.pywebview.api;
    var rawHasRows = (window.coplanObrasRaw || []).length > 0;
    if (!rawHasRows && apiNow && apiNow.get_pacotes) {
      apiNow.get_pacotes().then(function (r) {
        if (!r || !r.ok || !r.items) return;
        var fld = findFieldByLabelStartsWith(modal, 'Pacote');
        if (!fld) return;
        var sel = fld.querySelector('select');
        if (!sel) return;
        var hasReal = false;
        for (var i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value) { hasReal = true; break; }
        }
        if (!hasReal) rebuildOptions(sel, r.items, true);
      });
    }
    // Regional + Superintendencia: NUNCA cair no fallback do config.
    // Se nao ha obras no banco, o select fica vazio (intencional).
  }
  window.coplanPopulateFilterModal = populateFilterModal;
  // Expoe getter de selecao multi para readModalFilters consumir.
  window.coplanReadMultiSelect = function (sel) {
    if (!sel || sel.tagName !== 'SELECT') return '';
    if (!sel.hasAttribute('multiple')) return String(sel.value || '');
    var arr = [];
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].selected && sel.options[i].value) {
        arr.push(sel.options[i].value);
      }
    }
    return arr.join(';');
  };
  // [NOVO] Re-aplica window.coplanFilters aos selects/inputs do modal
  // quando ele abre — assim o usuario VE o que esta filtrando hoje.
  function applyFiltersToModalUI() {
    var modal = document.getElementById('modal-filtros');
    if (!modal) return;
    var f = window.coplanFilters || {};
    // Mapeia chave -> label do modal (mesma de COL_FOR_LABEL invertido).
    var KEY_TO_LABEL = {
      cod: 'COD', ano: 'Ano', pi: 'PI',
      projeto: 'Projeto', alim: 'Alimentador',
      alim_benef: 'Alimentadores Beneficiados',
      se: 'Subesta', regional: 'Regional',
      superintendencia: 'Superintend',
      pacote: 'Pacote', tecnico: 'Tecnico Atualizado'
    };
    Object.keys(KEY_TO_LABEL).forEach(function (key) {
      var lbl = KEY_TO_LABEL[key];
      var fld = findFieldByLabelStartsWith(modal, lbl);
      if (!fld) return;
      var node = fld.querySelector('select, input');
      if (!node) return;
      var raw = f[key];
      if (raw == null || raw === '') return;
      // raw pode ser string com ; ou array.
      var values = Array.isArray(raw)
        ? raw.slice()
        : String(raw).split(/[;]+/).map(function (s) { return s.trim(); })
            .filter(Boolean);
      if (node.tagName === 'SELECT') {
        for (var i = 0; i < node.options.length; i++) {
          var opt = node.options[i];
          var match = false;
          values.forEach(function (v) {
            if (String(opt.value).toUpperCase() === String(v).toUpperCase()
                || String(opt.textContent).toUpperCase() === String(v).toUpperCase()) {
              match = true;
            }
          });
          opt.selected = match;
        }
        if (!node.hasAttribute('multiple') && values.length) {
          // single-select fica com o primeiro match.
          for (var j = 0; j < node.options.length; j++) {
            if (node.options[j].selected) { node.selectedIndex = j; break; }
          }
        }
      } else {
        node.value = values.join('; ');
      }
    });
    // Pill row "Criterios" / Aprovada
    if (f.aprovada || f.criterios) {
      var critFld = null;
      var allFlds = modal.querySelectorAll('.field');
      for (var k = 0; k < allFlds.length; k++) {
        var lab = allFlds[k].querySelector('label');
        if (lab && lab.textContent.trim().toLowerCase().indexOf('crit') === 0) {
          critFld = allFlds[k]; break;
        }
      }
      if (critFld) {
        var pills = critFld.querySelectorAll('.pill');
        Array.prototype.forEach.call(pills, function (p) { p.classList.remove('active'); });
        var target = (f.aprovada === 'SIM' ? 'aprovadas'
                    : f.aprovada === 'NAO' ? 'nao'
                    : (f.criterios || '').toLowerCase());
        var matched = false;
        Array.prototype.forEach.call(pills, function (p) {
          var t = (p.textContent || '').trim().toLowerCase();
          if (!matched && t.indexOf(target) === 0) {
            p.classList.add('active');
            matched = true;
          }
        });
        if (!matched && pills.length) pills[0].classList.add('active');
      }
    }
  }
  window.coplanApplyFiltersToModalUI = applyFiltersToModalUI;

  function init() {
    populateFilterModal();
    // Quando o user clica "Filtros avancados" -- repopula antes do modal abrir.
    var btn = document.getElementById('btn-modal-filtros');
    if (btn && !btn.__coplan_pop) {
      btn.__coplan_pop = true;
      btn.addEventListener('click', function () {
        populateFilterModal();
        // Apos popular, marca as selecoes salvas.
        setTimeout(applyFiltersToModalUI, 0);
      }, true);
    }
    // Quando obras chegam, refresca distincts.
    window.addEventListener('coplan:obras', function () {
      populateFilterModal();
      // Tambem re-aplica filtros (sem isso, options recriados perdem
      // a marcacao quando o user volta para a aba).
      setTimeout(applyFiltersToModalUI, 0);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>
<script>
(function () {
  // ---- Section 6 / Passo 3.4 (Visualizar / chips de filtros ativos) ----
  // Substitui os chips hardcoded do mock pela representacao dinamica de
  // window.coplanFilters + window.coplanQuery. Cada X remove o filtro
  // (limpa input do modal correspondente) e re-aplica a busca.
  var FILTER_LABELS = {
    cod: 'COD', ano: 'Ano', pi: 'PI',
    projeto: 'Projeto', alim: 'Alim',
    alim_benef: 'Alim. Benef',
    se: 'SE', regional: 'Regional',
    superintendencia: 'Superint',
    pacote: 'Pacote', aprovada: 'Aprovada',
    tecnico: 'Tecnico', criterios: 'Criterios',
  };
  // Mapeia chave -> rotulo do label do modal (para encontrar o input
  // correspondente e limpar quando o chip e removido).
  var FILTER_MODAL_LABEL = {
    cod: 'COD', ano: 'Ano', pi: 'PI',
    projeto: 'Projeto', alim: 'Alimentador',
    alim_benef: 'Alimentadores Beneficiados',
    se: 'Subesta', regional: 'Regional',
    superintendencia: 'Superint',
    pacote: 'Pacote', tecnico: 'Tecnico Atualizado',
  };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, function (c) {
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function findChipBar() {
    // No mock ha 2 .filter-bar dentro de #tab-visualizar:
    //   [0] = busca + botoes  | [1] = chips ativos
    var bars = document.querySelectorAll('#tab-visualizar .filter-bar');
    return bars.length >= 2 ? bars[1] : null;
  }
  function clearModalInputForKey(key) {
    var modal = document.getElementById('modal-filtros');
    if (!modal) return;
    var labelText = FILTER_MODAL_LABEL[key];
    if (!labelText) {
      // Nao mapeado (aprovada/criterios): trata o pill row.
      if (key === 'aprovada' || key === 'criterios') {
        var fields = modal.querySelectorAll('.field');
        for (var i = 0; i < fields.length; i++) {
          var lab = fields[i].querySelector('label');
          if (lab && lab.textContent.trim().toLowerCase().indexOf('crit') === 0) {
            fields[i].querySelectorAll('.pill').forEach(function (p) {
              p.classList.remove('active');
            });
            var first = fields[i].querySelector('.pill');
            if (first) first.classList.add('active');
            break;
          }
        }
      }
      return;
    }
    var fields = modal.querySelectorAll('.field');
    var target = labelText.toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
    for (var i = 0; i < fields.length; i++) {
      var lab = fields[i].querySelector('label');
      if (!lab) continue;
      var t = lab.textContent.trim().toLowerCase()
        .normalize('NFD').replace(/[̀-ͯ]/g, '');
      if (t.indexOf(target) === 0) {
        var node = fields[i].querySelector('input, select');
        if (node) {
          if (node.tagName === 'SELECT') {
            if (node.multiple) {
              // selectedIndex=0 num multi-select SELECIONA a primeira
              // option em vez de limpar; precisamos desmarcar todas.
              for (var oi = 0; oi < node.options.length; oi++) {
                node.options[oi].selected = false;
              }
            } else {
              node.selectedIndex = 0;
            }
          } else {
            node.value = '';
          }
        }
        return;
      }
    }
  }
  function removeFilter(key) {
    if (key === '__query') {
      window.coplanQuery = '';
      var input = document.querySelector('#tab-visualizar .search-input input');
      if (input) input.value = '';
    } else {
      delete window.coplanFilters[key];
      clearModalInputForKey(key);
    }
    if (typeof window.coplanApplySearch === 'function') {
      window.coplanApplySearch();
    } else {
      coplanRenderChips();
    }
  }
  function buildChipNode(key, label, value) {
    var span = document.createElement('span');
    span.className = 'filter-chip';
    span.dataset.key = key;
    span.style.cursor = 'pointer';
    span.title = 'Clique no X para remover este filtro';
    span.innerHTML = esc(label) + ': ' + esc(value)
                   + ' <i data-lucide="x" class="x"></i>';
    // [FIX] lucide.createIcons() substitui o <i> por <svg>, perdendo
    // listeners. Usar delegacao no span — funciona tanto no <i> quanto
    // no <svg> resultante (e seus paths internos).
    span.addEventListener('click', function (e) {
      var t = e.target;
      var hitX = t && t.closest && (t.closest('.x') || t.closest('[data-lucide="x"]')
                 || (t.tagName && t.tagName.toLowerCase() === 'path'));
      if (hitX) {
        e.stopPropagation();
        removeFilter(key);
      }
    });
    return span;
  }
  function coplanRenderChips() {
    var bar = findChipBar();
    if (!bar) return;
    // Preserva o label "Filtros ativos:" (primeiro span no mock) e o
    // .grow no final; remove apenas chips entre eles.
    var nodes = Array.prototype.slice.call(bar.children);
    nodes.forEach(function (n) {
      if (n.classList && n.classList.contains('filter-chip')) {
        bar.removeChild(n);
      }
    });
    var growEl = bar.querySelector('.grow');
    var anchor = growEl || null;
    var chips = [];
    if (window.coplanQuery && String(window.coplanQuery).trim()) {
      chips.push(buildChipNode('__query', 'Busca', window.coplanQuery.trim()));
    }
    var f = window.coplanFilters || {};
    Object.keys(f).forEach(function (k) {
      var v = f[k];
      if (v == null || String(v).trim() === '') return;
      var label = FILTER_LABELS[k] || k;
      chips.push(buildChipNode(k, label, v));
    });
    chips.forEach(function (c) {
      if (anchor) bar.insertBefore(c, anchor);
      else bar.appendChild(c);
    });
    bar.style.display = chips.length ? '' : 'none';
    if (window.lucide) lucide.createIcons();
  }
  window.coplanRenderChips = coplanRenderChips;
  // Wraps coplanApplySearch para sempre re-renderizar chips depois.
  // (definido em Passo 3.3, ja existe no momento que este script roda.)
  if (typeof window.coplanApplySearch === 'function') {
    var __origApply = window.coplanApplySearch;
    window.coplanApplySearch = function () {
      var p = __origApply.apply(this, arguments);
      try { coplanRenderChips(); } catch (e) { /* noop */ }
      return p;
    };
  }
  // Render inicial (esconde a barra se nao ha filtros).
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', coplanRenderChips);
  } else {
    coplanRenderChips();
  }
  // [B18] Re-render quando outros sources atualizam coplanFilters
  // (ex.: atalho de Pacote dispara coplan:filters-changed em B10).
  document.addEventListener('coplan:filters-changed', function () {
    setTimeout(coplanRenderChips, 50);
  });
})();
</script>
