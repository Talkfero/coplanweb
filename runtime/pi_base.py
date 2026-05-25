"""PI base helpers + PI_BASE_MAP/CUSTOM mutaveis + boot sequence.

Extraidos de codigo5_coplan.py. Mantem o boot que carrega as escolhas do
config.json no proprio import (mesmo comportamento do legado).

Inclui:
- PI_BASE_CUSTOM (lista mutavel) + PI_BASE_MAP (dict mutavel)
- _normalize_pi_base_name / _dedupe_pi_base_custom / _find_custom_pi_base
- _is_pi_base_known / get_all_pi_bases
- get_pi_base (com Qt prompt opcional)
- set_extra_keys_for_pi
"""
from __future__ import annotations

try:  # Qt e' opcional: a app web (headless) nao instala PySide6.
    from PySide6 import QtWidgets  # type: ignore[import-not-found]
except ModuleNotFoundError:  # o ramo prompt_user=True (QInputDialog) so roda no desktop
    QtWidgets = None  # type: ignore[assignment]

from runtime.calc import get_pi_metadata, get_pi_tipo_base
from runtime.config import ConfigManager
from runtime.text_utils import normalize_key


# ---------------------------------------------------------------------------
# Estado mutavel de sessao
# ---------------------------------------------------------------------------
PI_BASE_CUSTOM: list[str] = []
# Mapeamento temporario de PIs nao padrao para a base escolhida pelo usuario.
PI_BASE_MAP: dict = {}


# ---------------------------------------------------------------------------
# Helpers de normalizacao + busca
# ---------------------------------------------------------------------------
def _normalize_pi_base_name(name: str) -> str:
    return normalize_key(name).strip()


def _dedupe_pi_base_custom(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        raw = str(item or "").strip()
        if not raw:
            continue
        key = _normalize_pi_base_name(raw)
        if not key or key in seen:
            continue
        if get_pi_metadata(key) is not None:
            continue
        result.append(key)
        seen.add(key)
    return result


def _find_custom_pi_base(name: str) -> str | None:
    key = _normalize_pi_base_name(name)
    if not key:
        return None
    for custom in PI_BASE_CUSTOM:
        if _normalize_pi_base_name(custom) == key:
            return custom
    return None


def _is_pi_base_known(pi_base: str) -> bool:
    key = _normalize_pi_base_name(pi_base)
    if not key:
        return False
    if get_pi_metadata(key) is not None:
        return True
    return _find_custom_pi_base(pi_base) is not None


def get_all_pi_bases() -> list[str]:
    """Wrapper -- delega ao core service, passando PI_BASE_CUSTOM como custom_bases."""
    from core.services.pi_metadata_service import listar_todas_bases
    return listar_todas_bases(ConfigManager.load_config(), custom_bases=PI_BASE_CUSTOM)


# ---------------------------------------------------------------------------
# get_pi_base -- com Qt prompt opcional
# ---------------------------------------------------------------------------
def get_pi_base(pi: str, prompt_user: bool = True) -> str:
    """Retorna o PI base (tipo_base) para o PI informado.

    Caso o PI não esteja na metadata padrão, solicita ao usuário que escolha
    o PI mais próximo e armazena a escolha em ``PI_BASE_MAP``.

    O parâmetro ``prompt_user`` controla se as caixas de diálogo devem ser
    exibidas quando o PI não fizer parte da lista padrão. Quando ``False``
    o próprio ``pi`` é retornado sem qualquer interação.
    """
    metadata_base = get_pi_tipo_base(pi)
    if get_pi_metadata(pi) is not None:
        return metadata_base

    custom_base = _find_custom_pi_base(pi)
    if custom_base:
        return custom_base

    # Se o usuario ja escolheu anteriormente, reutiliza a escolha
    if pi in PI_BASE_MAP:
        return PI_BASE_MAP[pi]

    # Em modo silencioso, simplesmente retorne o proprio PI
    if not prompt_user:
        return pi

    QtWidgets.QMessageBox.information(
        None,
        "Atenção",
        f"Atenção: o PI '{pi}' não pertence à lista padrão. Por favor, selecione o PI mais próximo como base para geração dos campos.",
    )

    selectable_bases = get_all_pi_bases()
    selectable_bases.append("+ Criar novo PI_BASE...")

    base, ok = QtWidgets.QInputDialog.getItem(
        None,
        "Selecionar PI Base",
        "Selecione o PI mais próximo:",
        selectable_bases,
        0,
        False,
    )

    if ok and base == "+ Criar novo PI_BASE...":
        while True:
            novo_base, ok_text = QtWidgets.QInputDialog.getText(
                None,
                "Novo PI_BASE",
                "Digite o nome do novo PI_BASE:",
            )
            if not ok_text:
                return pi
            novo_base = _normalize_pi_base_name(novo_base)
            if not novo_base:
                QtWidgets.QMessageBox.warning(
                    None, "Entrada inválida", "O nome do PI_BASE não pode ficar vazio."
                )
                continue
            if get_pi_metadata(novo_base) is not None or _find_custom_pi_base(novo_base):
                QtWidgets.QMessageBox.warning(
                    None,
                    "PI_BASE duplicado",
                    "Esse PI_BASE já existe na lista padrão ou customizada.",
                )
                continue
            PI_BASE_CUSTOM.append(novo_base)
            ConfigManager.save_config({"pi_base_custom": PI_BASE_CUSTOM})
            base = novo_base
            ok = True
            break

    if ok and base:
        PI_BASE_MAP[pi] = base
        try:
            cfg = ConfigManager.load_config()
        except Exception:
            cfg = {}
        m = dict(cfg.get("pi_base_map", {}))
        m[pi] = base
        ConfigManager.save_config({"pi_base_map": m})
        return base

    # Se o usuario cancelar, retorna o proprio PI (evita falhas)
    return pi


# ---------------------------------------------------------------------------
# set_extra_keys_for_pi -- persiste extras por PI no config
# ---------------------------------------------------------------------------
def set_extra_keys_for_pi(pi_base: str, extra_keys: list[str]):
    try:
        cfg = ConfigManager.load_config()
    except Exception:
        cfg = {}
    m = dict(cfg.get("last_pi_extra_map", {}))
    m[pi_base.strip().upper()] = [k.strip().upper() for k in extra_keys if str(k).strip()]
    ConfigManager.save_config({"last_pi_extra_map": m})


# ---------------------------------------------------------------------------
# Boot sequence -- carrega as escolhas salvas no proprio import
# ---------------------------------------------------------------------------
try:
    _cfg_boot = ConfigManager.load_config()
    PI_BASE_MAP.update(_cfg_boot.get("pi_base_map", {}))
    PI_BASE_CUSTOM[:] = _dedupe_pi_base_custom(_cfg_boot.get("pi_base_custom", []))
except Exception:
    pass
