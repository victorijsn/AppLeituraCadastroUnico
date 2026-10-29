"""
Módulo para inspeção de arquivos do CECAD (ZIP ou CSV).
Reconhece estrutura, cabeçalho, delimitação, data de referência e lista de municípios.
"""

import os
import io
import re
import zipfile
import json
from typing import Dict, List, Optional, Tuple, Any

# Carrega mapa de municípios IBGE se disponível
IBGE_MAP: Dict[str, str] = {}
IBGE_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "municipios_ibge.json")
if os.path.exists(IBGE_JSON_PATH):
    try:
        with open(IBGE_JSON_PATH, "r", encoding="utf-8") as f:
            IBGE_MAP = json.load(f)
    except Exception:
        pass


def get_municipio_nome(cd_ibge: str) -> str:
    """Retorna 'Nome - UF' do município ou o próprio código se não localizado."""
    code = str(cd_ibge).strip()
    return IBGE_MAP.get(code, f"Município {code}")


def parse_reference_date(filename: str) -> Dict[str, str]:
    """
    Extrai datas de referência a partir de padrões típicos do CECAD.
    Exemplo: tab_cad_07082026_32_20260911
    -> base_ref: 08/2026
    -> extracao_ref: 11/09/2026
    """
    res = {
        "base_mes_ano": "",
        "extracao_data": "",
        "descricao": ""
    }
    base_name = os.path.basename(filename)

    # Procura padrão: tab_cad_DDMMAAAA_..._AAAAMMDD ou similar
    m = re.search(r'tab_cad_(\d{2})(\d{2})(\d{4})_.*_(\d{4})(\d{2})(\d{2})', base_name)
    if m:
        _, m_ref, a_ref, a_ext, m_ext, d_ext = m.groups()
        res["base_mes_ano"] = f"{m_ref}/{a_ref}"
        res["extracao_data"] = f"{d_ext}/{m_ext}/{a_ext}"
        res["descricao"] = f"Base: {res['base_mes_ano']} | Extração: {res['extracao_data']}"
        return res

    # Padrão simplificado com AAAAMMDD
    m2 = re.search(r'(\d{4})(\d{2})(\d{2})', base_name)
    if m2:
        ano, mes, dia = m2.groups()
        res["extracao_data"] = f"{dia}/{mes}/{ano}"
        res["descricao"] = f"Data: {res['extracao_data']}"

    return res


class FileInspector:
    """Inspeção rápida de arquivos CECAD (.zip ou .csv)."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.is_zip = zipfile.is_zipfile(file_path) if os.path.exists(file_path) else False
        self.csv_internal_name: Optional[str] = None
        self.delimiter = ";"
        self.columns: List[str] = []
        self.date_info = parse_reference_date(file_path)
        self.ibge_col_index = 0
        self.total_lines_approx = 0

        self._inspect_header()

    def _open_stream(self):
        """Retorna stream de leitura em bytes do CSV."""
        if self.is_zip:
            z = zipfile.ZipFile(self.file_path, "r")
            csvs = [name for name in z.namelist() if name.lower().endswith(".csv")]
            if not csvs:
                raise ValueError("Nenhum arquivo .csv encontrado dentro do arquivo ZIP.")
            self.csv_internal_name = csvs[0]
            return z.open(self.csv_internal_name, "r"), z
        else:
            return open(self.file_path, "rb"), None

    def _inspect_header(self):
        """Lê os primeiros bytes para obter cabeçalho e colunas."""
        stream, parent_zip = self._open_stream()
        try:
            line_bytes = stream.readline()
            if not line_bytes:
                return

            # Tenta decodificar cabeçalho
            for enc in ["utf-8", "latin1", "cp1252"]:
                try:
                    line_str = line_bytes.decode(enc).strip()
                    break
                except Exception:
                    line_str = ""

            # Detecta delimitador
            if ";" in line_str:
                self.delimiter = ";"
            elif "," in line_str:
                self.delimiter = ","

            self.columns = [col.strip() for col in line_str.split(self.delimiter) if col.strip()]

            # Encontra índice da coluna cd_ibge
            for i, col in enumerate(self.columns):
                c_clean = col.lower().replace("d.", "").replace("p.", "")
                if c_clean == "cd_ibge":
                    self.ibge_col_index = i
                    break
        finally:
            stream.close()
            if parent_zip:
                parent_zip.close()

    def scan_municipalities(self, max_lines: Optional[int] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Escaneia rapidamente a coluna de municípios.
        Retorna:
        - is_single_municipality (bool)
        - list_of_municipios: [{ 'cd_ibge': str, 'nome': str, 'contagem': int }]
        """
        counts: Dict[str, int] = {}
        total = 0

        stream, parent_zip = self._open_stream()
        try:
            reader = io.BufferedReader(stream, buffer_size=1024 * 1024 * 8)
            _ = reader.readline()  # ignora cabeçalho

            delim_b = self.delimiter.encode("ascii")

            for line in reader:
                total += 1
                semi_pos = line.find(delim_b)
                if semi_pos != -1:
                    ibge = line[:semi_pos].decode("latin1").strip()
                    counts[ibge] = counts.get(ibge, 0) + 1

                if max_lines and total >= max_lines:
                    break

            self.total_lines_approx = total

            mun_list = []
            for code, cnt in sorted(counts.items(), key=lambda x: x[0]):
                mun_list.append({
                    "cd_ibge": code,
                    "nome": get_municipio_nome(code),
                    "rotulo": f"{code} - {get_municipio_nome(code)} ({cnt:,} registros)".replace(",", "."),
                    "contagem": cnt
                })

            is_single = len(counts) == 1
            return is_single, mun_list
        finally:
            stream.close()
            if parent_zip:
                parent_zip.close()
