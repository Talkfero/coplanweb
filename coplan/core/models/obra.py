"""Entidade Obra e seus agregados."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Identificacao:
    cod: str = ""
    ano_: str = ""
    projeto_investimento: str = ""
    pi_base: str = ""
    nome_projeto: str = ""
    codigo_item: str = ""


@dataclass
class Localizacao:
    nome_regional: str = ""
    nome_superintendencia: str = ""
    subestacao: str = ""
    nivel_tensao_obra: str = ""
    tensao_operacao: str = ""
    coordenada_inicio: str = ""
    coordenada_fim: str = ""
    alimentador_principal: str = ""
    alimentadores_beneficiados: str = ""


@dataclass
class MaterialObra:
    quantidade_material: str = ""
    caracteristicas_material: str = ""
    novo_bay: str = ""
    manobra: str = ""
    nivel_criticidade: str = ""


@dataclass
class GanhosAntes:
    contas_contratos_previos: str = ""
    carregamento_inicial: str = ""
    perdas_iniciais: str = ""
    tensao_media_inicial: str = ""
    tensao_min_inicial: str = ""
    tensao_min_linha_inicial: str = ""
    chi_inicial: str = ""
    ci_inicial: str = ""
    tensao_max_inicial: str = ""
    ganhos_totais_antes: str = ""


@dataclass
class GanhosDepois:
    contas_contratos_posteriores: str = ""
    carregamento_final: str = ""
    perdas_finais: str = ""
    tensao_media_final: str = ""
    tensao_min_final: str = ""
    tensao_min_linha_final: str = ""
    chi_final: str = ""
    ci_final: str = ""
    tensao_max_final: str = ""
    ganhos_totais_depois: str = ""


@dataclass
class GanhosAtual:
    contas_contratos_beneficiadas: str = ""
    cc_benef_chi_ci: str = ""
    tensao_min_registrada_atual: str = ""
    carregamento_max_registrado_atual: str = ""
    ganhos_totais_atual: str = ""


@dataclass
class Ganhos:
    antes: GanhosAntes = field(default_factory=GanhosAntes)
    depois: GanhosDepois = field(default_factory=GanhosDepois)
    atual: GanhosAtual = field(default_factory=GanhosAtual)


@dataclass
class DadosObra:
    tipo_pacote: str = ""
    obra_aprovada: str = ""
    valor_obra: str = ""
    descricao_obra: str = ""
    observacoes_gerais: str = ""
    criterios_status: str = ""
    criterios_motivos: str = ""
    criterios_limite_carreg: str = ""
    despacho_status: str = ""
    despacho_em: str = ""
    despacho_ref: str = ""
    municipio: str = ""


@dataclass
class AuditoriaTecnica:
    tecnico_snapshot_token: str = ""
    tecnico_snapshot_at: str = ""
    tecnico_snapshot_src: str = ""
    tecnico_dirty: str = ""


@dataclass
class AuditoriaRegistro:
    data_criacao: str = ""
    data_modificacao: str = ""
    criado_por: str = ""
    modificado_por: str = ""


@dataclass
class Obra:
    """Agregado-raiz da entidade Obra."""

    ident: Identificacao = field(default_factory=Identificacao)
    localizacao: Localizacao = field(default_factory=Localizacao)
    material: MaterialObra = field(default_factory=MaterialObra)
    ganhos: Ganhos = field(default_factory=Ganhos)
    dados: DadosObra = field(default_factory=DadosObra)
    auditoria_tecnica: AuditoriaTecnica = field(default_factory=AuditoriaTecnica)
    auditoria_registro: AuditoriaRegistro = field(default_factory=AuditoriaRegistro)

    @classmethod
    def from_row_dict(cls, row: Dict[str, Any]) -> "Obra":
        def _str(value: Any) -> str:
            return "" if value is None else str(value)

        def _pick(row_in: Dict[str, Any], cls_: type) -> dict:
            return {
                f.name: _str(row_in[f.name])
                for f in fields(cls_)
                if f.name in row_in
            }

        return cls(
            ident=Identificacao(**_pick(row, Identificacao)),
            localizacao=Localizacao(**_pick(row, Localizacao)),
            material=MaterialObra(**_pick(row, MaterialObra)),
            ganhos=Ganhos(
                antes=GanhosAntes(**_pick(row, GanhosAntes)),
                depois=GanhosDepois(**_pick(row, GanhosDepois)),
                atual=GanhosAtual(**_pick(row, GanhosAtual)),
            ),
            dados=DadosObra(**_pick(row, DadosObra)),
            auditoria_tecnica=AuditoriaTecnica(**_pick(row, AuditoriaTecnica)),
            auditoria_registro=AuditoriaRegistro(**_pick(row, AuditoriaRegistro)),
        )

    def to_row_dict(self) -> Dict[str, Any]:
        flat: Dict[str, Any] = {}
        flat.update(asdict(self.ident))
        flat.update(asdict(self.localizacao))
        flat.update(asdict(self.material))
        flat.update(asdict(self.ganhos.antes))
        flat.update(asdict(self.ganhos.depois))
        flat.update(asdict(self.ganhos.atual))
        flat.update(asdict(self.dados))
        flat.update(asdict(self.auditoria_tecnica))
        flat.update(asdict(self.auditoria_registro))
        return flat

    def is_aprovada(self) -> bool:
        valor = self.dados.obra_aprovada
        return str(valor or "").strip().upper() == "SIM"

    def is_tecnico_dirty(self) -> bool:
        valor = self.auditoria_tecnica.tecnico_dirty
        return str(valor or "").strip().upper() in {"SIM", "1", "TRUE", "S"}

    def scope_key(self) -> str:
        pacote = str(self.dados.tipo_pacote or "").strip()
        alimentador = str(self.localizacao.alimentador_principal or "").strip()
        ano = str(self.ident.ano_ or "").strip()
        if not (pacote or alimentador or ano):
            return ""
        return f"{pacote}|{alimentador}|{ano}"

    def integrity_reasons(self, requires_municipio: bool = False) -> List[str]:
        reasons: List[str] = []
        if not str(self.ident.pi_base or "").strip():
            reasons.append("Sem PI_BASE")
        if not str(self.ident.ano_ or "").strip():
            reasons.append("Sem Ano")
        if not str(self.ident.cod or "").strip():
            reasons.append("Sem COD/ID")
        if not str(self.localizacao.alimentador_principal or "").strip():
            reasons.append("Sem Alimentador")
        if not str(self.dados.tipo_pacote or "").strip():
            reasons.append("Sem Pacote")
        if requires_municipio and not str(self.dados.municipio or "").strip():
            reasons.append("Sem Municipio")
        return reasons

    def dup_key(self) -> str:
        cod_obra = str(self.ident.cod or "").strip()
        if cod_obra:
            return f"COD_OBRA:{cod_obra}"
        alim = str(self.localizacao.alimentador_principal or "").strip()
        municipio = str(self.dados.municipio or "").strip()
        descricao = " ".join(
            str(self.dados.descricao_obra or "").strip().upper().split()
        )
        pi_base = str(self.ident.pi_base or "").strip()
        ano = str(self.ident.ano_ or "").strip()
        return f"COMP:{alim}|{municipio}|{descricao}|{pi_base}|{ano}"

    def ganhos_consistente(self, tolerancia: float) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        has_antes = any(
            str(getattr(self.ganhos.antes, f.name) or "").strip()
            for f in fields(GanhosAntes)
        )
        has_depois = any(
            str(getattr(self.ganhos.depois, f.name) or "").strip()
            for f in fields(GanhosDepois)
        )
        if has_antes and not has_depois:
            errors.append("Depois vazio")
        if has_depois and not has_antes:
            errors.append("Antes vazio")

        ganho_total = _parse_float(self.ganhos.atual.ganhos_totais_atual)
        ganho_antes = _parse_float(self.ganhos.antes.ganhos_totais_antes)
        ganho_depois = _parse_float(self.ganhos.depois.ganhos_totais_depois)
        if (
            ganho_total is not None
            and ganho_antes is not None
            and ganho_depois is not None
            and abs(ganho_total - (ganho_depois - ganho_antes)) > tolerancia
        ):
            errors.append("Ganho total inconsistente")

        criterios_status = str(self.dados.criterios_status or "").strip().upper()
        if criterios_status == "DADOS_INSUFICIENTES":
            errors.append(
                "Criterios insuficientes para exportacao dependente de ganhos"
            )

        return len(errors) == 0, errors


def _parse_float(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None
