"""
Definição dos Perfis Temáticos de Colunas para o Cadastro Único.
Permite à equipe municipal selecionar conjuntos focados de colunas.
"""

from typing import Dict, List, Set, Any

PROFILES: Dict[str, Dict[str, Any]] = {
    "completo": {
        "nome": "Completo (Todas as Colunas)",
        "descricao": "Exporta todas as colunas presentes no arquivo original traduzidas.",
        "colunas": []  # Vazio = todas as colunas
    },
    "geral": {
        "nome": "Visão Geral & Cadastro",
        "descricao": "Identificação da família, Responsável Familiar, endereço, datas de atualização e localização.",
        "colunas": [
            "cd_ibge", "cod_familiar_fam", "dat_cadastramento_fam", "dat_atual_fam",
            "cod_est_cadastral_fam", "cod_forma_coleta_fam", "dta_entrevista_fam",
            "nom_localidade_fam", "nom_tip_logradouro_fam", "nom_logradouro_fam",
            "num_logradouro_fam", "des_complemento_fam", "num_cep_logradouro_fam",
            "cod_unidade_territorial_fam", "nom_unidade_territorial_fam",
            "vlr_renda_media_fam", "fx_rfpc", "vlr_renda_total_fam", "marc_pbf", "qtde_meses_desat_cat",
            "nom_pessoa", "num_nis_pessoa_atual", "num_cpf_pessoa", "dta_nasc_pessoa",
            "cod_sexo_pessoa", "cod_raca_cor_pessoa", "cod_parentesco_rf_pessoa"
        ]
    },
    "bolsa_familia": {
        "nome": "Bolsa Família & Renda",
        "descricao": "Foco em benefícios (PBF, Gás, BPC), rendas familiares e individuais e atualização cadastral.",
        "colunas": [
            "cd_ibge", "cod_familiar_fam", "nom_unidade_territorial_fam", "nom_localidade_fam",
            "dat_atual_fam", "qtde_meses_desat_cat", "marc_pbf", "vlr_renda_media_fam",
            "vlr_renda_total_fam", "fx_rfpc", "marc_gas", "marc_bpc",
            "nom_pessoa", "num_nis_pessoa_atual", "num_cpf_pessoa", "cod_parentesco_rf_pessoa",
            "val_remuner_emprego_mes_ant", "val_renda_bruta_12_meses", "val_renda_doacao_mes_ant",
            "val_renda_aposent_mes_ant", "val_renda_pensao_mes_ant"
        ]
    },
    "habitacao": {
        "nome": "Habitação & Vulnerabilidade",
        "descricao": "Condições de moradia, abastecimento de água, esgoto, coleta de lixo, material do domicílio e infraestrutura.",
        "colunas": [
            "cd_ibge", "cod_familiar_fam", "nom_unidade_territorial_fam", "nom_localidade_fam",
            "nom_logradouro_fam", "num_logradouro_fam", "cod_local_domic_fam", "cod_especie_domic_fam",
            "qtd_comodos_domic_fam", "qtd_comodos_dormitorio_fam", "cod_material_piso_fam",
            "cod_material_domic_fam", "cod_agua_canalizada_fam", "cod_abastecimento_agua_fam",
            "cod_banheiro_domic_fam", "cod_escoa_sanitario_domic_fam", "cod_destino_lixo_domic_fam",
            "cod_iluminacao_domic_fam", "cod_calcamento_domic_fam", "vlr_renda_media_fam", "fx_rfpc", "marc_pbf"
        ]
    },
    "pessoas_trabalho": {
        "nome": "Pessoas, Educação & Trabalho",
        "descricao": "Dados individuais dos membros: escolaridade, deficiências, trabalho e rendimentos.",
        "colunas": [
            "cod_familiar_fam", "nom_localidade_fam", "nom_unidade_territorial_fam",
            "nom_pessoa", "num_nis_pessoa_atual", "num_cpf_pessoa", "dta_nasc_pessoa",
            "cod_sexo_pessoa", "cod_raca_cor_pessoa", "cod_parentesco_rf_pessoa",
            "cod_deficiencia_membro", "cod_deficiencia_cid_pessoa", "cod_sabe_ler_escrever_membro",
            "cod_frequenta_escola_membro", "cod_curso_frequenta_membro", "cod_ano_serie_frequenta_membro",
            "cod_curso_frequentou_pessoa_membro", "cod_trabalhou_semana_pes", "cod_trabalho_12_meses_pes",
            "cod_ocupacao_principal_pes", "val_remuner_emprego_mes_ant"
        ]
    }
}


def filter_columns_by_profile(all_columns: List[str], profile_key: str) -> List[str]:
    """Retorna a lista de colunas selecionadas para o perfil escolhido."""
    if profile_key not in PROFILES or profile_key == "completo":
        return all_columns

    profile_cols = PROFILES[profile_key]["colunas"]
    norm_profile_set = {c.lower().replace("d.", "").replace("p.", "") for c in profile_cols}

    selected = []
    for col in all_columns:
        c_norm = col.lower().replace("d.", "").replace("p.", "")
        if c_norm in norm_profile_set:
            selected.append(col)

    return selected if selected else all_columns
