"""
Módulo para proteção de dados pessoais (LGPD).
Fornece regras de mascaramento e anonimização de CPF, NIS e Nomes para compartilhamento intersetorial.
"""

import re
from typing import Any, List, Set

SENSITIVE_CPF_COLUMNS = {
    "p.num_cpf_pessoa",
    "d.num_cpf_entrevistador_fam",
    "num_cpf_pessoa",
    "num_cpf_entrevistador_fam"
}

SENSITIVE_NIS_COLUMNS = {
    "p.num_nis_pessoa_atual",
    "num_nis_pessoa_atual"
}

SENSITIVE_NAME_COLUMNS = {
    "p.nom_pessoa",
    "p.nom_completo_mae_pessoa",
    "p.nom_completo_pai_pessoa",
    "d.nom_entrevistador_fam",
    "nom_pessoa",
    "nom_completo_mae_pessoa",
    "nom_completo_pai_pessoa",
    "nom_entrevistador_fam"
}


def mask_cpf(val: Any) -> str:
    """Mascara CPF preservando apenas dígitos de controle (ex: ***.***.123-**)."""
    if not val:
        return ""
    digits = re.sub(r"\D", "", str(val))
    if len(digits) < 11:
        digits = digits.zfill(11)
    if len(digits) == 11:
        return f"***.***.{digits[6:9]}-**"
    return "***.***.***-**"


def mask_nis(val: Any) -> str:
    """Mascara NIS (ex: ***.*****.12-*)."""
    if not val:
        return ""
    digits = re.sub(r"\D", "", str(val))
    if len(digits) < 11:
        digits = digits.zfill(11)
    if len(digits) == 11:
        return f"***.*****.{digits[8:10]}-*"
    return "***.*****.**-*"


def mask_name(val: Any) -> str:
    """Substitui o nome por iniciais (ex: 'Maria Jose da Silva' -> 'M. J. d. S.')."""
    if not val:
        return ""
    parts = str(val).strip().split()
    if not parts:
        return ""
    masked_parts = []
    for p in parts:
        if p.lower() in ("da", "de", "do", "das", "dos", "e"):
            masked_parts.append(p.lower())
        else:
            masked_parts.append(f"{p[0].upper()}.")
    return " ".join(masked_parts)


def apply_lgpd_mask(col_name: str, value: Any) -> Any:
    """Aplica o mascaramento apropriado conforme o tipo da coluna."""
    if value is None or value == "":
        return ""
    c_lower = col_name.strip().lower()
    if c_lower in SENSITIVE_CPF_COLUMNS:
        return mask_cpf(value)
    if c_lower in SENSITIVE_NIS_COLUMNS:
        return mask_nis(value)
    if c_lower in SENSITIVE_NAME_COLUMNS:
        return mask_name(value)
    return value
