"""
Módulo para proteção de dados pessoais (LGPD).
Fornece regras de mascaramento e anonimização de CPF, NIS, Nomes, Endereço Residencial,
CRAS de referência e Escolas para compartilhamento seguro intersetorial.
"""

import re
from typing import Any, Set

SENSITIVE_CPF_COLUMNS: Set[str] = {
    "num_cpf_pessoa",
    "num_cpf_entrevistador_fam"
}

SENSITIVE_NIS_COLUMNS: Set[str] = {
    "num_nis_pessoa_atual"
}

SENSITIVE_NAME_COLUMNS: Set[str] = {
    "nom_pessoa",
    "nom_completo_mae_pessoa",
    "nom_completo_pai_pessoa",
    "nom_entrevistador_fam"
}

SENSITIVE_DOCS_COLUMNS: Set[str] = {
    "num_identidade_pessoa",
    "cod_complemento_pessoa",
    "num_cart_trab_prev_soc_pessoa",
    "num_serie_trab_prev_soc_pessoa",
    "num_titulo_eleitor_pessoa",
    "num_zona_tit_eleitor_pessoa",
    "num_secao_tit_eleitor_pessoa"
}

SENSITIVE_ADDRESS_COLUMNS: Set[str] = {
    "nom_localidade_fam",
    "nom_tip_logradouro_fam",
    "nom_titulo_logradouro_fam",
    "nom_logradouro_fam",
    "num_logradouro_fam",
    "des_complemento_fam",
    "des_complemento_adic_fam",
    "num_cep_logradouro_fam",
    "txt_referencia_local_fam",
    "cod_cta_energ_unid_consum_fam",
    "num_ddd_contato_1_fam",
    "num_tel_contato_1_fam",
    "ic_tipo_contato_1_fam",
    "ic_envo_sms_contato_1_fam",
    "num_ddd_contato_2_fam",
    "num_tel_contato_2_fam",
    "ic_tipo_contato_2_fam",
    "ic_envo_sms_contato_2_fam"
}

SENSITIVE_CRAS_COLUMNS: Set[str] = {
    "nom_centro_assist_fam",
    "cod_centro_assist_fam",
    "nom_unidade_territorial_fam",
    "cod_unidade_territorial_fam"
}

SENSITIVE_SCHOOL_COLUMNS: Set[str] = {
    "nom_escola_memb",
    "cod_censo_inep_memb",
    "cod_escola_local_memb",
    "sig_uf_escola_memb",
    "nom_munic_escola_memb",
    "cod_ibge_munic_escola_memb"
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


def mask_cep(val: Any) -> str:
    """Mascara CEP residencial."""
    if not val:
        return ""
    return "*****--***"


def apply_lgpd_mask(col_name: str, value: Any) -> Any:
    """Aplica o mascaramento apropriado conforme a natureza da coluna sob a LGPD."""
    if value is None or value == "":
        return ""

    c_clean = col_name.strip().lower()
    # Remove prefixos de origem d. (domicílio) e p. (pessoa)
    if c_clean.startswith("d."):
        c_clean = c_clean[2:]
    elif c_clean.startswith("p."):
        c_clean = c_clean[2:]

    # Município sempre deve permanecer visível para agregação territorial
    if c_clean == "cd_ibge":
        return value

    if c_clean in SENSITIVE_CPF_COLUMNS:
        return mask_cpf(value)
    if c_clean in SENSITIVE_NIS_COLUMNS:
        return mask_nis(value)
    if c_clean in SENSITIVE_NAME_COLUMNS:
        return mask_name(value)
    if c_clean in SENSITIVE_DOCS_COLUMNS:
        return "*** [DOCUMENTO OCULTO]"
    if c_clean in SENSITIVE_ADDRESS_COLUMNS:
        if "cep" in c_clean:
            return mask_cep(value)
        return "[OCULTO - LGPD]"
    if c_clean in SENSITIVE_CRAS_COLUMNS:
        return "[OCULTO - LGPD]"
    if c_clean in SENSITIVE_SCHOOL_COLUMNS:
        return "[OCULTO - LGPD]"

    return value

