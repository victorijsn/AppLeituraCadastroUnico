"""
Módulo para leitura, estruturação e compilação do Dicionário de Dados do CECAD / Cadastro Único.
"""

import os
import re
import json
from typing import Dict, Any, Optional, Tuple, List
import openpyxl

DEFAULT_ADDITIONAL_FIELDS = {
    "d.marc_gas": {
        "descricao": "Família beneficiária do Auxílio Gás",
        "mapeamento": {"0": "Não", "1": "Sim"}
    },
    "p.marc_gas": {
        "descricao": "Pessoa beneficiária do Auxílio Gás",
        "mapeamento": {"0": "Não", "1": "Sim"}
    },
    "p.ref_gas": {
        "descricao": "Mês/ano de referência da folha do Auxílio Gás",
        "mapeamento": {}
    },
    "d.marc_bpc": {
        "descricao": "Família beneficiária do Benefício de Prestação Continuada (BPC)",
        "mapeamento": {"0": "Não", "1": "Sim"}
    },
    "p.marc_bpc": {
        "descricao": "Pessoa beneficiária do Benefício de Prestação Continuada (BPC)",
        "mapeamento": {"0": "Não", "1": "Sim"}
    },
    "p.ref_bpc": {
        "descricao": "Mês/ano de referência da folha do BPC",
        "mapeamento": {}
    }
}


def normalize_col_name(col: str) -> str:
    """Remove prefixos d. e p. e converte para minúsculas."""
    c = col.strip().lower()
    if c.startswith("d."):
        c = c[2:]
    elif c.startswith("p."):
        c = c[2:]
    return c


def parse_resposta(resp_str: Any) -> Dict[str, str]:
    """
    Converte o texto da coluna Resposta em um dicionário {código: descrição}.
    Trata separadores como '#', quebras de linha '\n', e variações de hífens.
    """
    if not resp_str:
        return {}
    mapping = {}
    parts = re.split(r'[#\r\n]+', str(resp_str))
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Trata formato 'código - descrição' ou 'código: descrição'
        m = re.match(r'^([0-9A-Za-z]+)\s*[-–—:]\s*(.+)$', part)
        if m:
            code = m.group(1).strip()
            label = m.group(2).strip()
            # Limpa ruídos como links mds que porventura constem no texto do dicionário
            label = re.sub(r'aplicacoes\.mds\.gov\.br[^\s]*\s*', '', label)
            label = label.strip(' .;')
            mapping[code] = label
    return mapping


class DictionaryParser:
    """
    Gerencia o dicionário de dados do CECAD:
    - Carrega de arquivo Excel (.xlsx) ou JSON compilado
    - Mantém mapas de colunas, descrições e traduções categóricas
    """

    def __init__(self, excel_path: Optional[str] = None, json_path: Optional[str] = None):
        self.fields: Dict[str, Dict[str, Any]] = {}
        self.normalized_map: Dict[str, str] = {}

        if json_path and os.path.exists(json_path):
            self.load_from_json(json_path)
        elif excel_path and os.path.exists(excel_path):
            self.load_from_excel(excel_path)

        # Garante campos adicionais
        for campo, data in DEFAULT_ADDITIONAL_FIELDS.items():
            if campo not in self.fields:
                self.fields[campo] = data
                self.normalized_map[normalize_col_name(campo)] = campo

    def load_from_excel(self, file_path: str):
        """Lê a planilha oficial do dicionário e extrai os metadados dos campos."""
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active

        self.fields.clear()
        self.normalized_map.clear()

        # Localiza a linha do cabeçalho ('Campo', 'Descrição', 'Resposta')
        start_row = 1
        for row_idx in range(1, 10):
            vals = [str(cell.value).strip().lower() if cell.value is not None else '' for cell in ws[row_idx]]
            if any('campo' in v for v in vals):
                start_row = row_idx + 1
                break

        for row in ws.iter_rows(min_row=start_row, values_only=True):
            if not row or not row[0]:
                continue
            campo = str(row[0]).strip()
            descricao = str(row[1]).strip() if len(row) > 1 and row[1] is not None else campo
            resposta_raw = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ''

            mapeamento = parse_resposta(resposta_raw)

            self.fields[campo] = {
                'descricao': descricao,
                'mapeamento': mapeamento
            }
            self.normalized_map[normalize_col_name(campo)] = campo

    def load_from_json(self, json_path: str):
        """Carrega dicionário pré-compilado para máxima velocidade."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.fields = data.get('fields', {})
            self.normalized_map = {normalize_col_name(k): k for k in self.fields.keys()}

    def save_to_json(self, json_path: str):
        """Salva dicionário estruturado em JSON."""
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({'fields': self.fields}, f, ensure_ascii=False, indent=2)

    def get_field_info(self, col_name: str) -> Tuple[str, Dict[str, str]]:
        """
        Retorna (descricao_amigavel, mapeamento_categorico) para uma coluna dada.
        Tenta correspondência exata ou normalizada (sem d. / p.).
        """
        clean_col = col_name.strip()
        if clean_col in self.fields:
            item = self.fields[clean_col]
            return item.get('descricao', clean_col), item.get('mapeamento', {})

        norm = normalize_col_name(clean_col)
        if norm in self.normalized_map:
            orig = self.normalized_map[norm]
            item = self.fields[orig]
            return item.get('descricao', clean_col), item.get('mapeamento', {})

        return clean_col, {}

    def translate_value(self, col_name: str, value: Any) -> Any:
        """Traduz um valor codificado usando o dicionário se existir."""
        if value is None or value == '':
            return ''
        _, mapping = self.get_field_info(col_name)
        if not mapping:
            return value
        str_val = str(value).strip()
        if str_val in mapping:
            return mapping[str_val]
        if str_val.isdigit() and str(int(str_val)) in mapping:
            return mapping[str(int(str_val))]
        return value
