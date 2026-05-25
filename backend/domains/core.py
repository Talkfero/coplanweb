# -*- coding: utf-8 -*-
"""Mixin de dominio "core" da CoplanApi (extraido de main_web.py).

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


class CoreMixin:
    """API exposta ao JS via ``window.pywebview.api.<metodo>``.

    Os managers (DatabaseManager, SupportFileManager, CalculationManager)
    sao importados sob demanda na primeira chamada que precise deles, para
    nao pagar o custo de inicializar Qt/SQLite no boot do main_web.
    """

    def __init__(self) -> None:
        self._db_manager: Any = None
        self._support_manager: Any = None
        self._calc_manager: Any = None
        self._config: dict[str, Any] | None = None
        # Locks para serializar inicializacao e conexao quando o JS
        # dispara varias chamadas API em paralelo (caso contrario:
        # race em add_column_if_missing -> "duplicate column name").
        self._managers_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        # Cache do ultimo erro de conexao para o JS oferecer correcao
        # de path em Configuracoes sem repetir tentativas barulhentas.
        self._last_connect_error: str = ""
        self._last_connect_path: str = ""
        # Conjunto de paths ja inicializados (full migration + cache).
        # DatabaseManager fecha a conexao no final de cada `_with_connection`,
        # mas o `data_access_layer` continua valido para queries. Sem este
        # cache, cada API call do JS chamava `db.connect()` de novo (WAL +
        # migration + audit_columns + weekly_backup), ate 14x por boot.
        self._connected_paths: set[str] = set()
        # Cache do ultimo dict retornado por SupportFileManager.load_support_file
        # (alimentadores, dados_alimentador, projetos_investimento, etc.)
        # Populado por _load_apoio_into_manager.
        self._apoio_cache: dict[str, Any] = {}
        self._apoio_path_loaded: str = ""
        # Estado de fontes (RB-1.1 / RB-5 do desktop): rastreia se db,
        # apoio, ganhos e tecnico_txt estao VALIDADO/INVALIDADO/NAO_CARREGADO,
        # com timestamps + version_token. Usado por require_state pra gateara
        # acoes que dependem de fonte carregada e por update_reliability_labels
        # pra pintar chips no header. Lazy-init: instanciado na primeira vez
        # que algum hook ou API toca pra evitar custo de import no boot.
        self._data_state: Any = None
        # Marca do ultimo refresh do db (data_modificacao + usuario), pra
        # detectar updates externos (outro usuario gravou) entre 2 leituras.
        self._last_db_refresh_data: str = ""
        self._last_db_refresh_user: str = ""
        self._last_db_modification_warned: str = ""

    def _reload_config(self) -> None:
        """Recarrega self._config do disco. Chamado automaticamente
        sempre que algum save_* invalida o cache (self._config = None)."""
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            self._config = ConfigManager.load_config()
        except Exception as exc:  # noqa: BLE001
            print(f"[main_web] reload config falhou: {exc}", file=sys.stderr)
            if self._config is None:
                self._config = {}

    def _get_data_state(self) -> Any:
        """Lazy-init do DataStateManager. Importa do runtime/config.py."""
        if self._data_state is None:
            try:
                from runtime.config import DataStateManager  # noqa: PLC0415
                self._data_state = DataStateManager()
            except Exception as exc:  # noqa: BLE001
                print(f"[main_web] DataStateManager indisponivel: {exc}",
                      file=sys.stderr)
                return None
        return self._data_state

    def _data_state_set(
        self,
        source: str,
        state: str,
        path: str = "",
        error: str = "",
        version_token: str = "",
    ) -> None:
        """Atalho para chamar update_source com tolerancia a erros.
        Hooks chamam isto sem se preocupar se o manager esta disponivel."""
        ds = self._get_data_state()
        if ds is None:
            return
        try:
            ds.update_source(
                source,
                state,
                path=path or None,
                error=error or None,
                version_token=version_token or None,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[main_web] data_state.update_source falhou: {exc}",
                  file=sys.stderr)

    # ------------------------------------------------------------------
    # _write_op_log: persiste um TXT em <HERE>/logs/<op>_<ts>.txt com os
    # detalhes de uma operacao que NAO foi 100% bem-sucedida. Chamado
    # antes de retornar o result dict de operacoes (atualizar, export,
    # delete, etc.). Garante que o usuario sempre tem o arquivo mesmo
    # se nao clicar em "Salvar TXT" no modal de detalhes.
    #
    # Devolve o path ('' em caso de falha de escrita). NUNCA levanta.
    # ------------------------------------------------------------------
    def _write_op_log(
        self, op: str, result: dict[str, Any],
        meta: dict[str, Any] | None = None,
    ) -> str:
        try:
            logs_dir = HERE / "logs"
            try:
                logs_dir.mkdir(exist_ok=True)
            except Exception:  # noqa: BLE001
                pass
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            op_slug = (op or "log").lower()
            import re as _re_op
            op_slug = _re_op.sub(r"[^a-z0-9_-]+", "_", op_slug)
            fname = f"{op_slug}_{ts}.txt"
            path = logs_dir / fname
            lines: list[str] = []
            sep = "=" * 60
            lines.append(sep)
            lines.append(f"Operacao: {op}")
            lines.append(f"Data/hora: {datetime.now().isoformat()}")
            if meta:
                for k, v in meta.items():
                    lines.append(f"{k}: {v}")
            lines.append(sep)
            lines.append("")
            # Resumo dos contadores comuns.
            counters = []
            for k in ("ok", "total", "processadas_ok", "atualizadas",
                     "falhas_total", "deleted", "imported", "merged",
                     "skipped", "count", "blocked", "cancelled"):
                if k in result:
                    counters.append(f"{k}={result.get(k)}")
            if counters:
                lines.append("Contadores: " + " | ".join(counters))
                lines.append("")
            err = str(result.get("error") or "").strip()
            if err:
                lines.append("-- Erro --")
                lines.append(err)
                lines.append("")
            errors = result.get("errors") or []
            if errors:
                lines.append(f"-- Erros ({len(errors)}) --")
                for e in errors:
                    lines.append(str(e))
                lines.append("")
            falhas = result.get("falhas") or []
            if falhas:
                lines.append(
                    f"-- Falhas ({result.get('falhas_total', len(falhas))}) --"
                )
                for f in falhas:
                    lines.append(str(f))
                lines.append("")
            chaves = result.get("chaves_inexistentes") or []
            if chaves:
                lines.append(f"-- Chaves inexistentes ({len(chaves)}) --")
                for c in chaves:
                    lines.append(str(c))
                lines.append("")
            preservadas_msgs = result.get("preservadas_msgs") or []
            if preservadas_msgs:
                lines.append(
                    f"-- Valores preservados ({len(preservadas_msgs)}) --"
                )
                lines.append(
                    "Obras com calculo parcial (chave extra ausente ou "
                    "sem valor) que JA TINHAM valor no banco: o valor "
                    "antigo foi mantido."
                )
                for m in preservadas_msgs:
                    lines.append(str(m))
                lines.append("")
            diag = result.get("diagnostico") or []
            if diag:
                lines.append(
                    f"-- Diagnostico por obra falha ({len(diag)}) --"
                )
                lines.append(
                    "Listing input values + chave tentada para CADA obra "
                    "que falhou. Use isto para comparar com o calculo "
                    "feito na aba Cadastro (botao Calcular)."
                )
                for d in diag:
                    lines.append(str(d))
                lines.append("")
            diag_all_l = result.get("diagnostico_todas") or []
            if diag_all_l:
                lines.append(
                    f"-- Breakdown por obra ({len(diag_all_l)}) --"
                )
                lines.append(
                    "Para CADA obra processada (sucesso ou falha): "
                    "inputs, chave montada, extras resolvidos, valor "
                    "calculado. Compare 'extras_resolvidos' com o que o "
                    "Cadastro/Calcular usou para detectar key mismatch "
                    "no last_pi_extra_map."
                )
                for d in diag_all_l:
                    lines.append(str(d))
                lines.append("")
            extra_map_snap = result.get("last_pi_extra_map") or {}
            if extra_map_snap:
                lines.append(
                    f"-- Snapshot last_pi_extra_map ({len(extra_map_snap)} chaves) --"
                )
                lines.append(
                    "Conteudo de cfg['last_pi_extra_map'] no momento "
                    "do Atualizar. Compare a chave deste PI com o "
                    "pi_base que aparece no Breakdown acima -- se nao "
                    "for IDENTICA (case-sensitive, acentuacao), o "
                    "lookup falha e os extras manuais nao sao aplicados."
                )
                for k in sorted(extra_map_snap.keys()):
                    lines.append(f"  {k!r} -> {extra_map_snap[k]!r}")
                lines.append("")
            duplicadas = result.get("duplicadas") or []
            if duplicadas:
                lines.append(f"-- Duplicadas ({len(duplicadas)}) --")
                for d in duplicadas:
                    if isinstance(d, dict):
                        lines.append(
                            f"linha {d.get('linha', '?')} - "
                            f"COD excel={d.get('cod_excel', '?')} / "
                            f"dup COD={d.get('dup_cod', '?')}"
                        )
                    else:
                        lines.append(str(d))
                lines.append("")
            missing = result.get("missing_columns") or []
            if missing:
                lines.append(f"-- Colunas faltantes ({len(missing)}) --")
                for c in missing:
                    lines.append(str(c))
                lines.append("")
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write("\n".join(lines))
            print(f"[main_web] log salvo: {path}", file=sys.stderr)
            return str(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[main_web] _write_op_log falhou: {exc}",
                  file=sys.stderr)
            return ""

    @staticmethod
    def _result_has_errors(result: dict[str, Any]) -> bool:
        """True se o result indica qualquer coisa diferente de sucesso
        pleno: !ok, falhas_total>0, chaves_inexistentes nao vazio,
        errors nao vazio, duplicadas nao vazio, cancelled."""
        if not result:
            return True
        if not result.get("ok"):
            return True
        if result.get("cancelled"):
            return True
        if int(result.get("falhas_total") or 0) > 0:
            return True
        if (result.get("chaves_inexistentes") or []):
            return True
        if (result.get("errors") or []):
            return True
        if (result.get("duplicadas") or []):
            return True
        return False

    # ------------------------------------------------------------------
    # Paridade desktop: mensagem amigavel quando o banco esta ocupado
    # por outro usuario / processo. Substitui str(exc) cru por uma
    # mensagem com user/maquina/desde lida do .lock ao lado do .db.
    # ------------------------------------------------------------------
    def _friendly_busy_error(self, exc: Exception) -> str | None:
        """Se ``exc`` for busy/locked, devolve build_database_busy_message.
        Caso contrario, devolve None (chamador propaga str(exc)).
        """
        try:
            from runtime.database import (  # noqa: PLC0415
                DatabaseBusyError, DatabaseLockedError,
                build_database_busy_message, get_lock_info_path,
                is_sqlite_busy_error, read_lock_info,
            )
        except Exception:  # noqa: BLE001
            return None
        is_busy = isinstance(exc, (DatabaseBusyError, DatabaseLockedError))
        if not is_busy:
            try:
                import sqlite3 as _sq  # noqa: PLC0415
                if isinstance(exc, _sq.OperationalError) and \
                        is_sqlite_busy_error(exc):
                    is_busy = True
            except Exception:  # noqa: BLE001
                pass
        if not is_busy:
            return None
        lock_info: dict[str, Any] | None = None
        try:
            db_path = ""
            if self._db_manager is not None:
                db_path = str(
                    getattr(self._db_manager, "db_path", "") or "")
            if db_path:
                lock_info = read_lock_info(get_lock_info_path(db_path))
        except Exception:  # noqa: BLE001
            lock_info = None
        try:
            return build_database_busy_message(lock_info)
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Paridade desktop validar_campos_obrigatorios
    # (ui/main_window/cadastro_mixin.py:580):
    # campos obrigatorios no save de uma obra. JS ja valida no form,
    # mas duplicamos no backend como defense-in-depth (payload pode
    # vir incompleto se o front bypassar a validacao).
    # ------------------------------------------------------------------
    _CAMPOS_OBRIGATORIOS_SAVE = (
        # (coluna_db, label_amigavel)
        ("ano_",                    "Ano"),
        ("projeto_investimento",    "Projeto de Investimentos"),
        ("alimentador_principal",   "Alimentador Obra"),
        ("quantidade_material",     "Quantidade"),
        ("coordenada_fim",          "Coordenadas Para"),
        ("tipo_pacote",             "Pacote"),
        ("caracteristicas_material","Caracteristicas"),
        ("manobra",                 "Manobra"),
    )

    def _validar_campos_obrigatorios(
        self, cleaned: dict[str, Any],
    ) -> list[str]:
        """Retorna labels dos campos obrigatorios vazios. Vazio => OK."""
        faltam: list[str] = []
        for col, label in self._CAMPOS_OBRIGATORIOS_SAVE:
            val = cleaned.get(col)
            if val is None or str(val).strip() == "":
                faltam.append(label)
        # Para PI base = DISTRIBUICAO* o nome_projeto e' obrigatorio
        # (paridade: ver cadastro_mixin.py:602-606).
        try:
            from runtime.text_utils import normalize_key  # noqa: PLC0415
            from runtime.pi_base import get_pi_base  # noqa: PLC0415
        except Exception:  # noqa: BLE001
            normalize_key = lambda s: str(s or "").strip().upper()  # noqa: E731
            get_pi_base = lambda pi, prompt_user=False: ""  # noqa: E731
        pi = str(cleaned.get("projeto_investimento") or "")
        try:
            pi_base = get_pi_base(pi, prompt_user=False) or ""
        except Exception:  # noqa: BLE001
            pi_base = ""
        distrib = {"DISTRIBUICAO", "DISTRIBUICAO LD 34,5 KV"}
        if normalize_key(pi) in distrib or normalize_key(pi_base) in distrib:
            if not str(cleaned.get("nome_projeto") or "").strip():
                faltam.append("Projeto")
        return faltam

    def _ensure_managers(self) -> None:
        # Cache de config invalidado por save_config_empresa / save_criterios
        # / etc. Sem este reload, todo cfg = self._config or {} cai em {}
        # apos a primeira invalidacao -- causando "banco nao configurado"
        # mesmo com config.json correto no disco.
        if self._config is None:
            self._reload_config()
        if self._db_manager is not None:
            return
        # So uma thread inicializa os managers; as outras esperam
        # e veem self._db_manager preenchido na re-checagem.
        with self._managers_lock:
            if self._db_manager is not None:
                return
            try:
                from runtime.apoio import SupportFileManager  # noqa: PLC0415
                from runtime.calc import CalculationManager  # noqa: PLC0415
                from runtime.config import ConfigManager  # noqa: PLC0415
                from runtime.database import DatabaseManager  # noqa: PLC0415
                self._db_manager = DatabaseManager()
                self._support_manager = SupportFileManager()
                self._calc_manager = CalculationManager(
                    self._support_manager, prompt_pi_base=False
                )
                if self._config is None:
                    self._config = ConfigManager.load_config()
                # Auto-connect do banco no boot: se config['obras']
                # aponta para arquivo valido, conecta ja para a pill
                # ficar verde e bridges nao precisarem reconectar.
                try:
                    db_path_boot = str(
                        (self._config or {}).get("obras") or "").strip()
                    if db_path_boot and os.path.isfile(db_path_boot):
                        self._ensure_db_connected()
                except Exception as exc:  # noqa: BLE001
                    print(f"[main_web] auto-connect db falhou: {exc}",
                          file=sys.stderr)
                # Auto-load do apoio: DB-backed only. Hidrata
                # _apoio_cache lendo as tabelas apoio_* do banco.
                # Nao toca xlsx (use 'Atualizar apoio' nas Configuracoes
                # para reimportar).
                try:
                    self._load_apoio_into_manager("")
                except Exception as exc:  # noqa: BLE001
                    print(f"[main_web] auto-load apoio (db) falhou: {exc}",
                          file=sys.stderr)
                # [FIX] Auto-validate dos 3 .TXT se caminho_pasta_ganhos
                # esta no config (paridade com desktop: ao iniciar com
                # pasta conhecida, ja marca tecnico_txt = CARREGADO_VALIDADO
                # se FlowMT/Topologia/Confiabilidade existem). Sem isso,
                # a pill 'Tecnico' do header fica eternamente NAO_CARREGADO
                # ate o user clicar em Selecionar Pasta na aba Ganhos.
                ganhos_path = (self._config or {}).get("caminho_pasta_ganhos") or ""
                if ganhos_path and os.path.isdir(str(ganhos_path)):
                    try:
                        self.validate_tecnico_files(str(ganhos_path))
                        # Tambem marca ganhos como CARREGADO_VALIDADO para
                        # destravar os botoes da aba Ganhos (G050).
                        self._data_state_set(
                            "ganhos", "CARREGADO_VALIDADO",
                            path=str(ganhos_path))
                    except Exception as exc:  # noqa: BLE001
                        print(f"[main_web] auto-validate tecnico falhou: {exc}",
                              file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                # Nao deixa exception subir pro pywebview (apaga o app).
                # Marca como erro e devolve managers possivelmente parciais.
                print(f"[main_web] _ensure_managers falhou: {exc}",
                      file=sys.stderr)
                if self._config is None:
                    self._config = {}

    # ------------------------------------------------------------------
    # Passo 1 (Tokens e tema): nenhum API necessario -- o CSS do
    # Coplan UI.html ja carrega tudo (Inter, JetBrains Mono via Google
    # Fonts; oklch tokens nas variaveis :root). Mantemos um ping de
    # health check para validar o canal Python<->JS.
    # ------------------------------------------------------------------
    def ping(self) -> dict[str, Any]:
        return {"ok": True, "msg": "coplan-bridge-ativo"}

    # ------------------------------------------------------------------
    # Estado de Fontes (RB-1.1 / RB-5 do desktop, EstadoFontesMixin):
    # rastreia se db, apoio, ganhos, tecnico_txt estao
    # NAO_CARREGADO / CARREGADO_VALIDADO / INVALIDADO. APIs publicas
    # consumidas pelo header (chips de confiabilidade) e pelos botoes
    # de export/relatorio (gating com "Ir para X").
    # ------------------------------------------------------------------
    def data_state_get(self) -> dict[str, Any]:
        """Devolve o estado das 4 fontes (db, apoio, ganhos, tecnico_txt)
        + label/timestamp formatados para o header. JS usa isto para
        pintar os chips depois de cada API que muda fonte."""
        # Lazy-disparo do auto-connect: _ensure_managers contem o
        # auto-connect do banco a partir de config['obras'] no boot.
        # Sem isto, na 1a chamada vinda do JS (antes de list_obras),
        # o DataStateManager devolve NAO_CARREGADO para 'db' mesmo com
        # o banco corretamente configurado, fazendo o tooltip do chip
        # dizer "Status: Nao carregado" enquanto o nome do arquivo
        # aparece no chip (vem de get_app_state, que le config direto).
        try:
            self._ensure_managers()
        except Exception:  # noqa: BLE001
            pass
        ds = self._get_data_state()
        if ds is None:
            return {"ok": False, "sources": {}, "error": "manager indisponivel"}
        out: dict[str, Any] = {}
        for source, info in ds.sources.items():
            ts = info.validated_at or info.loaded_at
            ts_str = ts.strftime("%d/%m %H:%M") if ts else ""
            out[source] = {
                "state": info.state,
                "path": info.path,
                "validated_at": ts_str,
                "error_last": info.error_last,
                "version_token": info.version_token,
            }
        # tecnico_dirty count: vem do banco quando conectado
        dirty = 0
        try:
            if self._db_manager is not None and self._connected_paths:
                dirty = int(self._db_manager.count_tecnico_dirty() or 0)
        except Exception:  # noqa: BLE001
            dirty = 0
        out["tecnico_dirty_count"] = dirty
        return {"ok": True, "sources": out}

    def data_state_require(
        self, action_name: Any = "", required: Any = None
    ) -> dict[str, Any]:
        """Verifica pre-requisitos. ``required`` e dict como
        ``{"db": "CARREGADO_VALIDADO", "ganhos": "CARREGADO_VALIDADO"}``.
        Retorna ``{ok: bool, pendencias: [{source, label, hint, detail}]}``.
        Se ``ok=False``, JS mostra dialog com botoes 'Ir para X'."""
        ds = self._get_data_state()
        if ds is None:
            return {"ok": False, "pendencias": [],
                    "error": "manager indisponivel"}
        try:
            from runtime.config import DataStateManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "pendencias": [], "error": str(exc)}

        action = str(action_name or "")
        req = required if isinstance(required, dict) else {}
        if not req:
            req = {
                "db": DataStateManager.CARREGADO_VALIDADO,
            }

        labels = {
            "db": ("Banco de dados",
                   "Conecte ou crie um banco de dados."),
            "apoio": ("Planilha de apoio",
                      "Carregue a planilha de apoio."),
            "ganhos": ("Pasta de ganhos",
                       "Selecione a pasta dos arquivos de ganhos."),
            "tecnico_txt": ("Arquivos tecnicos (TXT)",
                            "Carregue os arquivos tecnicos."),
        }

        pendencias: list[dict[str, Any]] = []
        for source, min_state in req.items():
            if not ds.meets_required(source, min_state):
                info = ds.get_state(source)
                label, hint = labels.get(source, (source, ""))
                erro = f" Erro: {info.error_last}" if info.error_last else ""
                pendencias.append({
                    "source": source,
                    "label": label,
                    "hint": hint,
                    "state": info.state,
                    "detail": f"{label} ({info.state}).{erro} {hint}".strip(),
                })

        return {
            "ok": not pendencias,
            "action": action,
            "pendencias": pendencias,
        }

    def data_state_invalidate(self, source: Any, error: Any = "") -> dict[str, Any]:
        """Marca uma fonte como INVALIDADO. Usado quando o JS detecta
        condicao externa (arquivo apagado, banco fechado, etc.)."""
        try:
            from runtime.config import DataStateManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        src = str(source or "").strip()
        if not src:
            return {"ok": False, "error": "source vazio"}
        self._data_state_set(
            src,
            DataStateManager.INVALIDADO,
            error=str(error or ""),
        )
        return {"ok": True}

    # ------------------------------------------------------------------
    # Passo 2.1 (Shell/Header): estado das fontes (Banco, Apoio, Tecnico)
    # + identificacao do usuario/versao para popular as src-pill do header.
    # ------------------------------------------------------------------
    @staticmethod
    def _file_state(p: str) -> dict[str, Any]:
        """Classifica um caminho de arquivo como ok/warn/err para as pills.

        ok    arquivo existe e e' legivel
        warn  caminho configurado mas arquivo nao encontrado / sem acesso
        err   nao configurado

        Tambem retorna ``size`` (bytes, 0 se indisponivel) usado pela
        status bar do Passo 2.2.
        """
        path = (p or "").strip()
        if not path:
            return {
                "status": "err", "label": "nao configurado",
                "name": "", "size": 0, "mtime": 0,
            }
        name = os.path.basename(path) or path
        size = 0
        mtime = 0.0
        try:
            if not os.path.exists(path):
                return {
                    "status": "warn", "label": "nao encontrado",
                    "name": name, "size": 0, "mtime": 0,
                }
            if not os.access(path, os.R_OK):
                return {
                    "status": "warn", "label": "sem acesso",
                    "name": name, "size": 0, "mtime": 0,
                }
            try:
                stat = os.stat(path)
                size = int(stat.st_size)
                mtime = float(stat.st_mtime)
            except OSError:
                pass
        except OSError:
            return {
                "status": "warn", "label": "erro de IO",
                "name": name, "size": 0, "mtime": 0,
            }
        return {
            "status": "ok", "label": "",
            "name": name, "size": size, "mtime": mtime,
        }

    def _ensure_db_connected(self) -> tuple[Any, str]:
        """Garante que o DatabaseManager esteja conectado ao banco do
        config.json e retorna ``(db_manager, "")`` ou ``(None, motivo)``.

        Idempotente: nao reconecta se ja apontando para o mesmo arquivo.

        SERIALIZADO via _connect_lock para evitar race em
        add_column_if_missing quando varias chamadas API do JS chegam
        em paralelo no boot. Nunca propaga excecao -- erros viram
        ``(None, motivo)`` para o JS poder tratar e o usuario corrigir
        o caminho via Configuracoes."""
        try:
            self._ensure_managers()
        except Exception as exc:  # noqa: BLE001
            return None, f"managers indisponiveis: {exc}"

        cfg = self._config or {}
        db_path = (cfg.get("obras") or "").strip()
        if not db_path:
            self._data_state_set(
                "db", "NAO_CARREGADO", error="banco nao configurado")
            return None, "banco nao configurado em config.json (chave 'obras')"
        if not os.path.exists(db_path):
            self._data_state_set(
                "db", "INVALIDADO", path=db_path,
                error="banco nao encontrado")
            return None, f"banco nao encontrado: {db_path}"
        db = self._db_manager
        if db is None:
            self._data_state_set(
                "db", "INVALIDADO", path=db_path,
                error="DatabaseManager indisponivel")
            return None, "DatabaseManager indisponivel"

        # Cache de erro: se o caminho mudou, limpa o cache + lista de
        # paths ja inicializados (vai precisar reconectar).
        if self._last_connect_path != db_path:
            self._last_connect_error = ""
            self._last_connect_path = db_path
            self._connected_paths.discard(db_path)

        # Caminho rapido: ja inicializamos este db_path com sucesso antes.
        # DatabaseManager.data_access_layer continua valido para queries
        # mesmo apos `_with_connection` fechar a conn fisica.
        if db_path in self._connected_paths:
            return db, ""

        with self._connect_lock:
            # Re-checa apos lock (outra thread pode ter conectado
            # enquanto esperavamos).
            if db_path in self._connected_paths:
                return db, ""
            try:
                db.connect(db_path)
                self._connected_paths.add(db_path)
                self._last_connect_error = ""
                # Hook estado: db conectado e migrado com sucesso.
                self._data_state_set(
                    "db", "CARREGADO_VALIDADO", path=db_path,
                    version_token=str(int(os.path.getmtime(db_path))))
                return db, ""
            except Exception as exc:  # noqa: BLE001
                msg = f"falha ao conectar: {exc}"
                self._last_connect_error = msg
                self._data_state_set(
                    "db", "INVALIDADO", path=db_path, error=msg)
                # Nao deixa o app travar: log no stderr e devolve erro.
                print(f"[main_web] {msg}", file=sys.stderr)
                return None, msg

    # ------------------------------------------------------------------
    # Identificacao do usuario - port direto de
    # cadastro_viabilidades.main_web._ad_display_name + get_user_info +
    # set_display_name. Resolve display_name via:
    #   1. config['ui_preferences_por_usuario'][<username>]['display_name']
    #   2. Active Directory Windows (GetUserNameExW NameDisplay)
    #   3. Fallback: username tratado (split _.- + Title Case)
    # Iniciais derivadas do display_name final (avatar mostra "AS" mesmo
    # quando username e' uma matricula tipo "12345").
    # ------------------------------------------------------------------
    def _ad_display_name(self) -> str:
        """Tenta resolver o nome amigavel do usuario via Active Directory
        no Windows (secur32.GetUserNameExW com NameDisplay = 3). Retorna
        '' se nao estiver em dominio ou se falhar."""
        if not sys.platform.startswith("win"):
            return ""
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:  # noqa: BLE001
            return ""
        # EXTENDED_NAME_FORMAT.NameDisplay = 3
        NAME_DISPLAY = 3
        try:
            secur32 = ctypes.WinDLL("secur32", use_last_error=True)
            secur32.GetUserNameExW.argtypes = [
                wintypes.INT, wintypes.LPWSTR, ctypes.POINTER(wintypes.ULONG),
            ]
            secur32.GetUserNameExW.restype = wintypes.BOOLEAN
            size = wintypes.ULONG(256)
            buf = ctypes.create_unicode_buffer(size.value)
            ok = secur32.GetUserNameExW(NAME_DISPLAY, buf, ctypes.byref(size))
            if not ok:
                # Tenta com buffer maior se falhou por tamanho
                size_2 = wintypes.ULONG(size.value)
                buf = ctypes.create_unicode_buffer(size_2.value + 1)
                ok = secur32.GetUserNameExW(
                    NAME_DISPLAY, buf, ctypes.byref(size_2))
                if not ok:
                    return ""
            return (buf.value or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    def get_user_info(self) -> dict[str, Any]:
        """Identifica o usuario logado e resolve um nome amigavel.

        Ordem de resolucao do nome de exibicao (display_name):
            1. config['ui_preferences_por_usuario'][<username>]['display_name']
            2. Active Directory (Windows): GetUserNameEx(NameDisplay).
            3. Username tratado (split por . _ - + Title Case).

        Sempre retorna `username` cru (chave do config — preferencias usam
        esse valor, nao o display)."""
        # 1. Resolve username cru
        name = ""
        try:
            import getpass as _gp
            name = (_gp.getuser() or "").strip()
        except Exception:  # noqa: BLE001
            name = ""
        if not name:
            try:
                name = (os.getlogin() or "").strip()
            except Exception:  # noqa: BLE001
                name = ""
        if not name:
            name = (
                os.environ.get("USER")
                or os.environ.get("USERNAME")
                or os.environ.get("LOGNAME")
                or ""
            ).strip()
        username = name or "default"

        # 2. Override por config (precedencia maxima)
        display_name = ""
        source = "fallback"
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
            ui_prefs = cfg.get("ui_preferences_por_usuario") or {}
            if isinstance(ui_prefs, dict):
                bucket = ui_prefs.get(username) or {}
                if isinstance(bucket, dict):
                    manual = str(bucket.get("display_name") or "").strip()
                    if manual:
                        display_name = manual
                        source = "config"
        except Exception:  # noqa: BLE001
            pass

        # 3. Active Directory (so se nao tem override)
        ad_name = ""
        if not display_name:
            ad_name = self._ad_display_name()
            if ad_name:
                display_name = ad_name
                source = "ad"

        # 4. Fallback: username tratado
        if not display_name:
            base = username if username and username != "default" else "Usuário"
            parts = [p for p in re.split(r"[._\s-]+", base) if p]
            if parts:
                display_name = " ".join(p.capitalize() for p in parts)
            else:
                display_name = base
            source = "fallback"

        # Iniciais derivadas do display_name final
        parts = [p for p in re.split(r"[._\s-]+", display_name) if p]
        if parts:
            initials = "".join(p[0] for p in parts[:2]).upper()
        else:
            initials = (display_name[:2] or "US").upper()

        return {
            "ok": True,
            "username": username,
            "display_name": display_name,
            "initials": initials or "US",
            "source": source,
            "ad_suggestion": ad_name,
        }

    def set_display_name(self, name: Any = "") -> dict[str, Any]:
        """Override manual de display_name em
        config['ui_preferences_por_usuario'][<username>]['display_name'].
        ``name`` vazio remove o override (volta a usar AD ou fallback)."""
        info = self.get_user_info()
        username = info.get("username") or "default"
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}"}
        ui_prefs = cfg.get("ui_preferences_por_usuario") or {}
        if not isinstance(ui_prefs, dict):
            ui_prefs = {}
        bucket = ui_prefs.get(username) or {}
        if not isinstance(bucket, dict):
            bucket = {}
        clean = str(name or "").strip()
        if clean:
            bucket["display_name"] = clean
        else:
            bucket.pop("display_name", None)
        ui_prefs[username] = bucket
        try:
            ConfigManager.save_config({"ui_preferences_por_usuario": ui_prefs})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "user": self.get_user_info()}

    def get_app_state(self) -> dict[str, Any]:
        """Estado global para popular header (source pills) + status bar.

        Le caminhos do config.json (mesmo arquivo que o desktop usa),
        nao requer DatabaseManager inicializado para ser barato no boot.
        """
        # Carrega config sem instanciar managers (mais rapido no boot da UI).
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415

            cfg = ConfigManager.load_config()
        except Exception as exc:  # noqa: BLE001
            cfg = {}
            cfg_error = str(exc)
        else:
            cfg_error = ""

        # Caminho do banco: chave "obras" e' a usada pelo desktop atual.
        db_path = str(cfg.get("obras") or "").strip()
        # Apoio DB-backed (2026-05-07): pill "Apoio" reflete tabelas no
        # banco. last_path em apoio_meta indica de qual xlsx os dados
        # foram importados (sem precisar abrir xlsx para hidratar).
        apoio_path = ""
        apoio_db_state: dict[str, Any] | None = None
        try:
            db_for_meta = getattr(self, "_db_manager", None)
            if db_for_meta is not None and db_path:
                meta = self._apoio_meta_dict(db_for_meta)
                if meta:
                    apoio_path = str(meta.get("last_path") or "")
                    if meta.get("last_imported_at"):
                        apoio_db_state = {
                            "status": "ok",
                            "label": (
                                f"{meta.get('sheet_count') or 0} aba(s)"
                                f" · banco · "
                                f"{meta.get('last_imported_at') or ''}"),
                            "path": apoio_path,
                        }
        except Exception:  # noqa: BLE001
            apoio_db_state = None
        # [FIX] Tecnico_txt: agora le caminho_pasta_ganhos do config
        # e checa presenca dos 3 arquivos obrigatorios (paridade com
        # validate_tecnico_files). Antes mostrava warn so com base no
        # apoio_path, ignorando totalmente a pasta de ganhos configurada.
        ganhos_path = str(cfg.get("caminho_pasta_ganhos") or "").strip()
        tecnico_files = ("FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT")
        if ganhos_path and os.path.isdir(ganhos_path):
            faltantes = [
                f for f in tecnico_files
                if not any(
                    os.path.exists(os.path.join(ganhos_path, name))
                    for name in (f, f.lower(), f.upper())
                )
            ]
            if not faltantes:
                tecnico = {"status": "ok",
                           "label": "3 arquivos validados",
                           "path": ganhos_path}
            else:
                tecnico = {
                    "status": "warn",
                    "label": "Faltam: " + ", ".join(faltantes),
                    "path": ganhos_path,
                }
        else:
            tecnico = {"status": "warn",
                       "label": "Pasta de ganhos nao configurada"}

        # User: usa get_user_info() para resolver display_name amigavel
        # (override config -> Active Directory Windows -> fallback Title Case).
        # Port da logica de cadastro_viabilidades.
        try:
            uinfo = self.get_user_info()
            user = uinfo.get("display_name") or uinfo.get("username") or "?"
            user_initials = uinfo.get("initials") or "?"
        except Exception:  # noqa: BLE001
            try:
                user = getpass.getuser()
            except Exception:  # noqa: BLE001
                user = "?"
            user_initials = "?"

        # Apoio: prioriza DB-backed state; cai para arquivo so se ainda
        # nao houve importacao (banco virgem - mostra warn pedindo import).
        apoio_state = apoio_db_state or {
            "status": "warn",
            "label": "Apoio nao importado - use 'Atualizar apoio'",
            "path": "",
        }
        return {
            "app": {
                "version": APP_VERSION,
                "user": user,
                "user_initials": user_initials,
                "config_error": cfg_error,
            },
            "sources": {
                "db": self._file_state(db_path) | {"path": db_path},
                "apoio": apoio_state,
                "tecnico": tecnico,
            },
        }

    # ------------------------------------------------------------------
    # Passo 5.1 (Ganhos / pasta de arquivos): le caminho_pasta_ganhos do
    # config + (opcional) sub-pasta do alimentador, lista arquivos xlsx/csv
    # e expoe pick_ganhos_folder() para abrir o file dialog do pywebview.
    # ------------------------------------------------------------------
    GANHOS_EXTS = (".xlsx", ".xlsm", ".xls", ".csv", ".txt")

    # ------------------------------------------------------------------
    # Passo 5.5 (Ganhos / acoes Inserir Antes/Depois + em Massa + atuais):
    #   * pick_ganhos_file()    - file dialog (xlsx/csv/txt) e devolve
    #                             read_ganhos_file() do arquivo escolhido.
    #   * apply_ganhos_to_obra(cod, slot, parametros) - persiste valores
    #                             do parametros[] em colunas do banco
    #                             (slot='antes'|'depois'|'atual') usando
    #                             update_obra. Mapeia label -> coluna
    #                             via heuristica (mesma logica do
    #                             desktop, mas declarativa).
    #   * ganhos_em_massa(...)  - stub: aplica em N cods de uma vez.
    # ------------------------------------------------------------------
    GANHOS_LABEL_MAP = (
        # (substring do label normalizado, coluna_antes, coluna_depois)
        ("contas contratos",   "contas_contratos_previos",       "contas_contratos_posteriores"),
        ("contas",             "contas_contratos_previos",       "contas_contratos_posteriores"),
        ("carregamento",       "carregamento_inicial",            "carregamento_final"),
        ("perdas",             "perdas_iniciais",                 "perdas_finais"),
        ("tensao media",       "tensao_media_inicial",            "tensao_media_final"),
        ("tensao min linha",   "tensao_min_linha_inicial",        "tensao_min_linha_final"),
        ("tensao min",         "tensao_min_inicial",              "tensao_min_final"),
        ("tensao maxima",      "tensao_max_inicial",              "tensao_max_final"),
        ("tensao max",         "tensao_max_inicial",              "tensao_max_final"),
        ("chi",                "chi_inicial",                     "chi_final"),
        ("ci",                 "ci_inicial",                      "ci_final"),
        ("ganhos totais",      "ganhos_totais_antes",             "ganhos_totais_depois"),
    )

    # ------------------------------------------------------------------
    # Passo 6.3 (Resumo / distribuicao por Pacote): agrega valor_obra por
    # tipo_pacote, calcula percentual sobre o total e devolve ordenado
    # desc. Mantemos a categoria 'Outros' para pacotes vazios.
    # Filtro opcional ano_.
    # ------------------------------------------------------------------
    PACOTE_COLOR_MAP = {
        "MERCADO":              "oklch(0.55 0.13 250)",
        "CONFIABILIDADE":       "oklch(0.62 0.13 155)",
        "INTERLIGAÇÃO UDE":     "oklch(0.75 0.14 85)",
        "INTERLIGACAO UDE":     "oklch(0.75 0.14 85)",
        "INTERLIGAÇÃO DE UDE":  "oklch(0.75 0.14 85)",
        "INTERLIGACAO DE UDE":  "oklch(0.75 0.14 85)",
        "SOLICITAÇÃO REGIONAL": "oklch(0.6 0.13 230)",
        "SOLICITACAO REGIONAL": "oklch(0.6 0.13 230)",
        "PLPT":                 "oklch(0.5 0.18 290)",
        "OUTROS":               "var(--text-soft)",
    }

    # ------------------------------------------------------------------
    # Passo 7.4 (Config / Regional Map): CRUD do mapa de regionais.
    # Estrutura no config:
    #   regional_map: {
    #     <NOME>: <codigo str>           # legado simples
    #     OU
    #     <NOME>: {                       # extendido (web)
    #       codigo, superintendencia,
    #       se_prefixos: "ATB,JTP",
    #       cor: "info"|"success"|"warning"|"danger"|"violet"
    #     }
    #   }
    # Combinamos com REGIONAL_MAP do legado (read-only defaults).
    # ------------------------------------------------------------------
    REGIONAL_COR_OPCOES = ("info", "success", "warning", "danger", "violet")

    # ------------------------------------------------------------------
    # Visualizar / Colunas customizadas (RB-3 do desktop,
    # VisualizarColunasMixin):
    # Persiste em config['ui_state']['visualizar']:
    #   * visible_columns: list[str]   -> quais colunas mostrar
    #   * columns_order: list[str]     -> ordem em que aparecem
    #   * column_widths: dict[str,int] -> largura px persistida
    # ------------------------------------------------------------------
    # Mascara padrao do Visualizar (2026-05-08): subset legivel das
    # ~14 colunas mais relevantes para o operador. Substitui o default
    # de "todas visiveis" (67 colunas) que era ilegivel no boot.
    # User pode customizar via "Configurar Colunas" (botao na toolbar).
    DEFAULT_VIS_COLUMNS = [
        "cod",
        "ano_",
        "pi_base",
        "codigo_item",
        "nome_projeto",
        "alimentador_principal",
        "subestacao",
        "nome_regional",
        "tipo_pacote",
        "quantidade_material",
        "valor_obra",
        "obra_aprovada",
        "tecnico_dirty",
        "despacho_status",
    ]
