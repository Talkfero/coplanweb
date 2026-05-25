# -*- coding: utf-8 -*-
"""Mixin de dominio "valor" da CoplanApi (extraido de main_web.py).

Nao instanciar diretamente: compoe backend.api.CoplanApi via heranca.
"""
from __future__ import annotations

import getpass  # noqa: F401
import hashlib  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import sys  # noqa: F401
import threading  # noqa: F401
from datetime import datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any, Callable  # noqa: F401

from backend._state import (  # noqa: F401
    APP_VERSION,
    HERE,
    _OP_LOCK,
    _OP_STATE,
    _op_check_cancel,
    _op_finish,
    _op_reset,
    _op_set_progress,
    _op_snapshot,
)


class ValorMixin:

    # ------------------------------------------------------------------
    # Fase A1 (core/services/atualizar_obra_service):
    # calcular_valor_obra -- usa a funcao PURA do core (sem QMessageBox).
    # Retorna {ok, valor (float), valor_formatado (str pt-BR), chave,
    #          motivos_falha, chaves_inexistentes, error}.
    # ------------------------------------------------------------------
    def _load_modulos_df(self) -> tuple[Any, str, str, str]:
        """Le tabela apoio_modulo do banco (DB-backed apoio).
        Retorna ``(df, col_chave, col_valor, error)``.
        Substitui leitura xlsx -- agora 100% via banco. Use
        'Atualizar apoio' nas Configuracoes para repopular as tabelas."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return None, "", "", err or "db indisponivel"
        # Verifica meta antes (apoio_modulo so existe se importacao rodou)
        meta = self._apoio_meta_dict(db)
        if not meta or not meta.get("last_path"):
            return None, "", "", (
                "apoio nao importado: use 'Atualizar apoio' em"
                " Configuracoes > Geral")
        modulo_tab = self._apoio_table_name("modulo")
        conn, err_open = self._open_aux_conn(db)
        if conn is None:
            return None, "", "", err_open or "conn indisponivel"
        try:
            import pandas as pd  # type: ignore[import-not-found]
            df = pd.read_sql_query(
                f'SELECT * FROM {self._apoio_quote_ident(modulo_tab)}',
                conn,
            )
        except Exception as exc:  # noqa: BLE001
            return None, "", "", f"leitura {modulo_tab}: {exc}"
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        cols_lower = {c.lower(): c for c in df.columns}
        col_chave = cols_lower.get("carac+modulo_regional", "")
        col_valor = cols_lower.get("valor_item", "")
        if not col_chave or not col_valor:
            return None, "", "", ("tabela 'apoio_modulo' sem colunas "
                                  "'CARAC+MODULO_REGIONAL'/'VALOR_ITEM'"
                                  " (reimporte o apoio)")
        return df, col_chave, col_valor, ""

    def calcular_valor_obra(
        self,
        projeto_investimento: Any = "",
        pi_base: Any = "",
        nivel_tensao: Any = "",
        caracteristicas_material: Any = "",
        nome_regional: Any = "",
        quantidade: Any = "",
        cod: Any = "",
    ) -> dict[str, Any]:
        df, col_chave, col_valor, err = self._load_modulos_df()
        if err:
            return {"ok": False, "error": err, "valor": None,
                    "valor_formatado": "", "chave": "",
                    "motivos_falha": [], "chaves_inexistentes": []}

        try:
            from core.services.atualizar_obra_service import (  # type: ignore[import-not-found]
                AtualizarObraInput, calcular_valor_obra as _core_calc,
            )
            # Fase A11: usa obter_modulos_extras direto do core (em vez
            # de passar pelo wrapper legacy get_pi_extra_module_keys).
            from core.services.pi_metadata_service import (  # type: ignore[import-not-found]
                obter_modulos_extras,
            )
            from runtime.config import REGIONAL_MAP, ConfigManager  # noqa: PLC0415
            from runtime.pi_base import get_pi_base  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}",
                    "valor": None, "valor_formatado": "", "chave": "",
                    "motivos_falha": [], "chaves_inexistentes": []}

        # Normaliza inputs (mesma regra do extrair_obra_input do core).
        proj = str(projeto_investimento or "").strip().upper()
        pi = str(pi_base or "").strip().upper()
        if not pi and proj:
            try:
                pi = (get_pi_base(proj, prompt_user=False) or "").strip().upper()
            except Exception:  # noqa: BLE001
                pi = proj
        tensao = str(nivel_tensao or "").strip().replace(",", ".").upper()
        carac = str(caracteristicas_material or "").strip().upper()
        regional = str(nome_regional or "").strip().upper()
        # [FIX] Normaliza virgula -> ponto pra aceitar "6,4" e "6.4".
        # O core.validar_quantidade faz float(qtd_str) direto, entao se
        # vier "6,4" da UI pt-BR ele explode com "quantidade invalida".
        qtd_raw = str(quantidade or "1").strip().replace(",", ".")

        inp = AtualizarObraInput(
            cod=str(cod or ""),
            projeto_investimento=proj,
            pi_base=pi,
            nivel_tensao=tensao,
            tensao_op=tensao,
            caracteristicas_material=carac,
            nome_regional=regional,
            quantidade_material=qtd_raw,
            obra_data_map={},
        )

        # Fase A11: extras do PI vigente via core (modulo_extra do PI +
        # ATERRAMENTO se exige_aterramento + last_pi_extra_map salvo).
        try:
            cfg = ConfigManager.load_config() or {}
            extras = list(obter_modulos_extras(pi, cfg) or [])
        except Exception:  # noqa: BLE001
            extras = []

        try:
            res = _core_calc(
                inp, df,
                col_chave=col_chave,
                col_valor=col_valor,
                regional_map=REGIONAL_MAP,
                extra_keys_for_pi=extras,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"calcular_valor_obra: {exc}",
                    "valor": None, "valor_formatado": "", "chave": "",
                    "motivos_falha": [], "chaves_inexistentes": []}

        # Convert valor formatado pt-BR -> float pra UI tambem mostrar.
        valor_num = None
        if res.valor_obra_formatado:
            try:
                valor_num = float(str(res.valor_obra_formatado).replace(",", "."))
            except (TypeError, ValueError):
                valor_num = None
        return {
            "ok": bool(res.sucesso_base),
            "error": "" if res.sucesso_base else "; ".join(res.motivos_falha),
            "valor": valor_num,
            "valor_formatado": res.valor_obra_formatado or "",
            "chave": res.chave_completa or "",
            "motivos_falha": list(res.motivos_falha),
            "chaves_inexistentes": list(res.chaves_inexistentes),
        }

    # ------------------------------------------------------------------
    # Fase A2 (atualizar_obra_service.processar_atualizacao):
    # bulk recalculo de valor_obra para um conjunto de COD (ou todas).
    # Para cada obra: extrai input via extrair_obra_input, processa via
    # processar_atualizacao (delega 100% pro core), e onde sucesso_base
    # for True, faz db.update_obra({"valor_obra": valor_formatado}).
    # Retorna o agregado com processadas_ok/falhas_total/falhas/
    # chaves_inexistentes -- mesmo formato do legado MainWindow.atualizar_obras.
    # ------------------------------------------------------------------
    def atualizar_obras_valores(self, cods: Any = None) -> dict[str, Any]:
        return self._run_atualizar_obras_valores(cods, progress_cb=None)

    # ------------------------------------------------------------------
    # atualizar_obras_valores_async (Bloco 5): versao com worker thread +
    # progress modal. JS dispara, recebe op_id, abre coplanProgress e polla
    # progress_state ate finished=True. Usado para bulk (toolbar + context
    # menu multi-cods). Per-row "Atualizar Valor" usa o sync acima (1 obra,
    # rapido).
    # ------------------------------------------------------------------
    def atualizar_obras_valores_async(
        self, cods: Any = None,
    ) -> dict[str, Any]:
        with _OP_LOCK:
            if not _OP_STATE.get("finished"):
                return {
                    "ok": False, "started": False,
                    "error": ("ja ha uma operacao em andamento: "
                              + str(_OP_STATE.get("label") or "")),
                }
        # Conta cods up-front (label da barra). Validacoes reais (cenario,
        # db, planilha apoio) ficam dentro do _run_*; se falharem, terminamos
        # a operacao imediatamente com ok=False.
        cods_list: list[str] = []
        if isinstance(cods, (list, tuple)):
            cods_list = [str(c).strip() for c in cods if str(c or "").strip()]
        n = len(cods_list) if cods_list else 0
        label = (f"Recalculando {n} obra(s)..." if n
                 else "Recalculando todas as obras...")
        op_id = _op_reset(label)

        def _worker():
            try:
                def _cb(processed: int, total: int, sub_label: str) -> bool:
                    _op_set_progress(processed, total, sub_label)
                    return _op_check_cancel()
                result = self._run_atualizar_obras_valores(
                    cods, progress_cb=_cb,
                )
                _op_finish(result=result, error="")
            except Exception as exc:  # noqa: BLE001
                _op_finish(result=None, error=f"worker: {exc}")

        t = threading.Thread(
            target=_worker, daemon=True,
            name=f"coplan-atualizar-{op_id}",
        )
        t.start()
        return {"ok": True, "started": True, "op_id": op_id, "error": ""}

    def _run_atualizar_obras_valores(
        self,
        cods: Any = None,
        *,
        progress_cb: Callable[[int, int, str], bool] | None = None,
    ) -> dict[str, Any]:
        cen_nome = self._cenario_active_name()
        if cen_nome:
            return {
                "ok": False, "error":
                (f"Operacao bloqueada: cenario '{cen_nome}' ativo."
                 f" Atualizacao em massa de valores nao e' suportada"
                 f" com cenario ativo. Saia do cenario primeiro."),
                "blocked": "cenario_active",
                "processadas_ok": 0, "falhas_total": 0,
                "atualizadas": 0, "falhas": [],
                "chaves_inexistentes": [], "total": 0,
            }
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "processadas_ok": 0, "falhas_total": 0,
                    "atualizadas": 0, "falhas": [],
                    "chaves_inexistentes": [], "total": 0}

        df, col_chave, col_valor, err_mod = self._load_modulos_df()
        if err_mod:
            return {"ok": False, "error": err_mod,
                    "processadas_ok": 0, "falhas_total": 0,
                    "atualizadas": 0, "falhas": [],
                    "chaves_inexistentes": [], "total": 0}

        try:
            from core.services.atualizar_obra_service import (  # type: ignore[import-not-found]
                _resolver_extra_keys, calcular_valor_obra, extrair_obra_input,
            )
            # Fase A11: usa obter_modulos_extras direto do core.
            from core.services.pi_metadata_service import (  # type: ignore[import-not-found]
                obter_modulos_extras,
            )
            from runtime.config import REGIONAL_MAP, ConfigManager  # noqa: PLC0415
            from runtime.pi_base import get_pi_base  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}",
                    "processadas_ok": 0, "falhas_total": 0,
                    "atualizadas": 0, "falhas": [],
                    "chaves_inexistentes": [], "total": 0}

        def _emit(processed: int, total: int, label: str) -> bool:
            """Reporta progresso e devolve True se o user pediu cancel."""
            if progress_cb is None:
                return False
            try:
                return bool(progress_cb(processed, total, label))
            except Exception:  # noqa: BLE001
                return False

        # Carrega config 1x para o pi_extra_module_keys_fn.
        try:
            cfg = ConfigManager.load_config() or {}
        except Exception:  # noqa: BLE001
            cfg = {}

        # Resolve a lista de COD a processar.
        cods_list: list[str] = []
        if isinstance(cods, (list, tuple)):
            cods_list = [str(c).strip() for c in cods if str(c or "").strip()]

        try:
            cols = list(db.get_column_names() or [])
            if cods_list:
                rows = db.fetch_by_cods(cods_list) or []
            else:
                rows = db.fetch_all() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"fetch: {exc}",
                    "processadas_ok": 0, "falhas_total": 0,
                    "atualizadas": 0, "falhas": [],
                    "chaves_inexistentes": [], "total": 0}

        # Constroi inputs via extrair_obra_input (mesma normalizacao do legado).
        def _pi_base_fallback(pi: str) -> str:
            try:
                return get_pi_base(pi, prompt_user=False) or pi
            except Exception:  # noqa: BLE001
                return pi

        inputs: list[Any] = []
        extracao_falhas: list[str] = []
        cod_idx = cols.index("cod") if "cod" in cols else -1
        for r in rows:
            row_cod = ""
            try:
                row_cod = str(r[cod_idx]) if cod_idx >= 0 else ""
            except Exception:  # noqa: BLE001
                row_cod = ""
            try:
                inp = extrair_obra_input(
                    r, cols, pi_base_fallback_fn=_pi_base_fallback,
                )
                inputs.append(inp)
            except Exception as exc:  # noqa: BLE001
                # Erro de extracao -- nao bloqueia; conta como falha.
                msg = f"COD={row_cod or 'N/D'}: extrair_obra_input: {exc}"
                extracao_falhas.append(msg)
                print(f"[main_web] {msg}", file=sys.stderr)

        # Snapshot do last_pi_extra_map para o log -- ajuda a detectar
        # key mismatch entre o que o Cadastro/Configuracoes salvou e o
        # que o Atualizar consulta.
        try:
            _pi_extra_map_snapshot = dict(cfg.get("last_pi_extra_map", {}) or {})
        except Exception:  # noqa: BLE001
            _pi_extra_map_snapshot = {}

        def _pi_extras(pi: str) -> list[str]:
            try:
                return list(obter_modulos_extras(pi, cfg) or [])
            except Exception:  # noqa: BLE001
                return []

        # Fase 1 (calculo): loop equivalente a processar_atualizacao, mas
        # com hooks de progresso/cancel por obra. Reproduz a mesma
        # contabilidade (falhas_max=5, set de chaves_inexistentes).
        # Fase 1 (calculo): loop equivalente a processar_atualizacao, mas
        # com hooks de progresso/cancel por obra. Reproduz a mesma
        # contabilidade (falhas_max=5, set de chaves_inexistentes).
        # Tambem coleta diagnostico por obra para o log (input values +
        # chave tentada) -- ajuda a entender por que uma obra falhou.
        total_calc = len(inputs)
        results: list[Any] = []
        processadas_ok = 0
        falhas_total = 0
        falhas: list[str] = []
        chaves_inex: set[str] = set()
        diag_failed: list[str] = []  # diagnostico por obra que falhou
        diag_all: list[str] = []  # breakdown completo por obra (success+fail)
        cancelled = False
        if _emit(0, max(total_calc, 1),
                 f"Calculando valor de {total_calc} obra(s)..."):
            cancelled = True
        if not cancelled:
            for i, inp in enumerate(inputs, 1):
                try:
                    extras = _resolver_extra_keys(
                        inp.pi_base,
                        extra_key_map={},
                        pi_extra_module_keys_fn=_pi_extras,
                    )
                    result = calcular_valor_obra(
                        inp, df,
                        col_chave=col_chave,
                        col_valor=col_valor,
                        regional_map=REGIONAL_MAP,
                        extra_keys_for_pi=extras,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"[main_web] calcular_valor_obra cod={inp.cod}: "
                          f"{exc}", file=sys.stderr)
                    falhas_total += 1
                    if len(falhas) < 5:
                        falhas.append(f"COD={inp.cod or 'N/D'}: {exc}")
                    diag_failed.append(
                        f"COD={inp.cod or 'N/D'} EXC={exc} "
                        f"pi_base={inp.pi_base!r} "
                        f"projeto={inp.projeto_investimento!r} "
                        f"nivel_tensao={inp.nivel_tensao!r} "
                        f"carac={inp.caracteristicas_material!r} "
                        f"regional={inp.nome_regional!r} "
                        f"qtd={inp.quantidade_material!r}"
                    )
                    continue
                # Diagnostico completo (todas obras): inputs + chave +
                # extras + valor_obra_formatado. Permite comparar com o
                # que o Cadastro/Calcular usou e identificar divergencias.
                diag_all.append(
                    f"COD={inp.cod or 'N/D'} "
                    f"chave={result.chave_completa or '(falhou)'} "
                    f"extras_resolvidos={list(extras)} "
                    f"valor_calc={result.valor_obra_formatado or '(falhou)'} "
                    f"sucesso_base={result.sucesso_base} "
                    f"pi_base={inp.pi_base!r} "
                    f"projeto={inp.projeto_investimento!r} "
                    f"nivel_tensao={inp.nivel_tensao!r} "
                    f"carac={inp.caracteristicas_material!r} "
                    f"regional={inp.nome_regional!r} "
                    f"qtd={inp.quantidade_material!r}"
                )
                results.append(result)
                if result.sucesso_base:
                    processadas_ok += 1
                else:
                    # Falha bloqueante (regional/chave/qtd invalida etc.):
                    # registra diagnostico completo para o log.
                    diag_failed.append(
                        f"COD={inp.cod or 'N/D'} "
                        f"chave_tentada={result.chave_completa or '(nao montou)'} "
                        f"motivos={list(result.motivos_falha)} "
                        f"pi_base={inp.pi_base!r} "
                        f"projeto={inp.projeto_investimento!r} "
                        f"nivel_tensao={inp.nivel_tensao!r} "
                        f"carac={inp.caracteristicas_material!r} "
                        f"regional={inp.nome_regional!r} "
                        f"qtd={inp.quantidade_material!r} "
                        f"extras={list(extras)}"
                    )
                for motivo in result.motivos_falha:
                    falhas_total += 1
                    if len(falhas) < 5:
                        falhas.append(
                            f"COD={result.cod or 'N/D'}: {motivo}")
                for ch in result.chaves_inexistentes:
                    chaves_inex.add(ch)
                if (i % 10) == 0 or i == total_calc:
                    if _emit(
                        i, total_calc,
                        f"Calculando valor... ({i}/{total_calc})",
                    ):
                        cancelled = True
                        break

        # Fase 2 (escrita): UPDATE no banco para cada result valido. A
        # descricao_obra fica fora -- depende de dialog Y/N do legado.
        to_write = [
            r for r in results
            if r.sucesso_base and r.valor_obra_formatado and str(r.cod or "").strip()
        ]
        # Index inputs por COD para conseguir ler o valor_obra atual
        # do banco antes de decidir sobrescrever (regra de preservacao
        # abaixo).
        input_by_cod = {}
        for _inp in inputs:
            _c = str(getattr(_inp, "cod", "") or "").strip()
            if _c:
                input_by_cod[_c] = _inp
        total_write = len(to_write)
        atualizadas = 0
        preservadas = 0
        preservadas_msgs: list[str] = []
        update_falhas: list[str] = []
        busy_msg = ""
        if not cancelled and total_write > 0:
            if _emit(0, total_write,
                     f"Salvando {total_write} obra(s) no banco..."):
                cancelled = True
        if not cancelled:
            for i, r_obra in enumerate(to_write, 1):
                cod_s = str(r_obra.cod or "").strip()

                # Regra de preservacao: se a calculo teve motivos_falha
                # (chave extra ausente OU valor invalido em alguma extra)
                # e a obra ja tem valor_obra gravado no DB, NAO sobrescreve
                # com o calculo parcial. Loga preservacao. Quando obra NAO
                # tem valor_obra, segue update normal (nao ha o que perder).
                motivos_problema = list(r_obra.motivos_falha or [])
                if motivos_problema:
                    inp_cur = input_by_cod.get(cod_s)
                    existing_val = ""
                    if inp_cur is not None:
                        try:
                            existing_val = str(
                                inp_cur.obra_data_map.get("valor_obra", "")
                                or ""
                            ).strip()
                        except Exception:  # noqa: BLE001
                            existing_val = ""
                    if existing_val:
                        msg = (
                            f"COD={cod_s}: valor preservado "
                            f"(DB={existing_val}, calc_parcial="
                            f"{r_obra.valor_obra_formatado}) - motivos: "
                            f"{'; '.join(motivos_problema)}"
                        )
                        preservadas += 1
                        preservadas_msgs.append(msg)
                        print(f"[main_web] {msg}", file=sys.stderr)
                        if (i % 5) == 0 or i == total_write:
                            if _emit(
                                i, total_write,
                                f"Salvando... ({i}/{total_write})",
                            ):
                                cancelled = True
                                break
                        continue

                try:
                    db.update_obra(
                        {"valor_obra": r_obra.valor_obra_formatado},
                        cod_s, skip_blank=True,
                    )
                    atualizadas += 1
                except Exception as exc:  # noqa: BLE001
                    friendly = self._friendly_busy_error(exc)
                    if friendly:
                        # Banco ocupado: aborta o loop (outros usuarios
                        # estao escrevendo). Mensagem amigavel pro JS.
                        busy_msg = friendly
                        update_falhas.append(f"COD={cod_s}: {friendly}")
                        print(
                            f"[main_web] db busy em "
                            f"atualizar_obras_valores: {friendly}",
                            file=sys.stderr,
                        )
                        break
                    msg = f"COD={cod_s}: update_obra: {exc}"
                    update_falhas.append(msg)
                    print(f"[main_web] {msg}", file=sys.stderr)
                if (i % 5) == 0 or i == total_write:
                    if _emit(
                        i, total_write,
                        f"Salvando... ({i}/{total_write})",
                    ):
                        cancelled = True
                        break

        falhas_full = list(falhas) + update_falhas + extracao_falhas
        falhas_total += len(extracao_falhas)
        ok_flag = not busy_msg and not cancelled
        err_str = busy_msg or ("cancelado" if cancelled else "")
        out: dict[str, Any] = {
            "ok": ok_flag, "error": err_str,
            "total": len(inputs),
            "processadas_ok": processadas_ok,
            "atualizadas": atualizadas,
            "preservadas": preservadas,
            "preservadas_msgs": preservadas_msgs,
            "falhas_total": falhas_total + len(update_falhas),
            "falhas": falhas_full,
            "chaves_inexistentes": sorted(chaves_inex),
            "diagnostico": diag_failed,
            "diagnostico_todas": diag_all,
            "last_pi_extra_map": _pi_extra_map_snapshot,
        }
        if busy_msg:
            out["blocked"] = "db_busy"
        if cancelled:
            out["cancelled"] = True
        # Auto-log em <HERE>/logs SEMPRE que processar 1+ obra (sucesso
        # ou erro). Mesmo "1 atualizada(s)" pode estar com valor errado
        # se algum extra nao foi resolvido -- o breakdown do log mostra
        # exatamente quais extras foram aplicados para CADA obra.
        if len(inputs) > 0 or self._result_has_errors(out) or preservadas > 0:
            out["log_path"] = self._write_op_log(
                "atualizar", out,
                meta={
                    "cods_solicitados": (len(cods_list) if cods_list
                                         else "todos"),
                    "preservadas": preservadas,
                },
            )
        return out
