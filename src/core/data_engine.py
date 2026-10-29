"""
Motor de Processamento de Dados do Cadastro Único (CECAD).
Executa streaming com baixo consumo de memória, filtragem, tradução categórica e anonimização LGPD.
"""

import os
import io
import zipfile
import re
from typing import Dict, List, Optional, Tuple, Any, Callable
import pandas as pd

from src.core.dictionary_parser import DictionaryParser
from src.core.file_inspector import FileInspector
from src.core.thematic_profiles import filter_columns_by_profile
from src.core.lgpd import apply_lgpd_mask


class DataEngine:
    """Motor de consulta, filtragem e tradução da base do CECAD."""

    def __init__(self, dictionary_parser: DictionaryParser):
        self.dict_parser = dictionary_parser

    def _open_stream(self, file_path: str, is_zip: bool, csv_name: Optional[str] = None):
        """Abre stream de leitura otimizado."""
        if is_zip:
            z = zipfile.ZipFile(file_path, "r")
            name = csv_name
            if not name:
                csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
                if not csvs:
                    raise ValueError("Nenhum arquivo .csv encontrado no arquivo ZIP.")
                name = csvs[0]
            return z.open(name, "r"), z
        else:
            return open(file_path, "rb"), None

    def process_data(
        self,
        file_path: str,
        municipio_ibge: Optional[str] = None,
        granularidade: str = "pessoa",  # "pessoa" ou "familia"
        perfil_colunas: str = "completo",  # "completo", "geral", "bolsa_familia", "habitacao", "pessoas_trabalho", ou lista manual
        colunas_customizadas: Optional[List[str]] = None,
        filtro_pbf: str = "todos",  # "todos", "sim", "nao"
        filtro_atualizacao: str = "todos",  # "todos", "desatualizados", "atualizados"
        filtro_renda: str = "todas",  # "todas", "extrema_pobreza", "pobreza", "baixa_renda", "acima_meio_sm"
        filtro_bairro: Optional[str] = None,
        modo_lgpd: bool = False,
        header_mode: str = "amigavel",  # "amigavel", "tecnico_amigavel", "tecnico"
        limite_linhas: Optional[int] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Lê e processa o arquivo aplicando todos os critérios, traduções e cálculos de resumo.
        Retorna (DataFrame_processado, metricas_resumo).
        """
        inspector = FileInspector(file_path)
        stream, parent_zip = self._open_stream(file_path, inspector.is_zip, inspector.csv_internal_name)

        try:
            reader = io.BufferedReader(stream, buffer_size=1024 * 1024 * 8)
            header_line = reader.readline()
            if not header_line:
                return pd.DataFrame(), {}

            for enc in ["utf-8", "latin1", "cp1252"]:
                try:
                    header_str = header_line.decode(enc).strip()
                    break
                except Exception:
                    header_str = ""

            all_columns = [c.strip() for c in header_str.split(inspector.delimiter) if c.strip()]
            col_indices = {col: i for i, col in enumerate(all_columns)}

            # Mapeamento normalizado de colunas
            norm_indices = {col.lower().replace("d.", "").replace("p.", ""): i for i, col in enumerate(all_columns)}

            # Determina colunas selecionadas
            if colunas_customizadas:
                selected_cols = [c for c in colunas_customizadas if c in col_indices]
            else:
                selected_cols = filter_columns_by_profile(all_columns, perfil_colunas)

            if not selected_cols:
                selected_cols = all_columns

            selected_indices = [col_indices[c] for c in selected_cols if c in col_indices]

            # Índices de controle para filtros e métricas
            idx_ibge = norm_indices.get("cd_ibge")
            idx_parentesco = norm_indices.get("cod_parentesco_rf_pessoa")
            idx_pbf = norm_indices.get("marc_pbf")
            idx_desat = norm_indices.get("qtde_meses_desat_cat")
            idx_rfpc = norm_indices.get("fx_rfpc")
            idx_renda_media = norm_indices.get("vlr_renda_media_fam")
            idx_cod_fam = norm_indices.get("cod_familiar_fam")
            idx_bairro = norm_indices.get("nom_localidade_fam")
            idx_cras = norm_indices.get("nom_unidade_territorial_fam")

            delim_b = inspector.delimiter.encode("ascii")
            ibge_b = municipio_ibge.strip().encode("ascii") if municipio_ibge else None
            bairro_lower = filtro_bairro.strip().lower() if filtro_bairro else None

            # Pré-carrega mapas categóricos para as colunas selecionadas
            translation_maps: Dict[int, Dict[str, str]] = {}
            for col in selected_cols:
                idx = col_indices[col]
                _, mapping = self.dict_parser.get_field_info(col)
                if mapping:
                    translation_maps[idx] = mapping

            processed_rows = []
            total_lines = 0
            distinct_families = set()
            count_pbf_sim = 0
            count_desatualizados = 0
            total_renda_soma = 0.0
            renda_count = 0

            if progress_callback:
                progress_callback(0.05, "Iniciando leitura e filtragem dos registros...")

            for line in reader:
                total_lines += 1

                # Filtro rápido por município direto no início da linha (se aplicável)
                if ibge_b and idx_ibge == 0:
                    if not line.startswith(ibge_b):
                        continue

                # Notificação periódica de progresso
                if progress_callback and total_lines % 250000 == 0:
                    progress_callback(min(0.85, total_lines / 2000000.0), f"Processados {total_lines:,} registros...")

                # Decodifica e divide os campos
                line_str = line.decode("latin1").rstrip("\r\n")
                fields = line_str.split(inspector.delimiter)

                # Valida IBGE caso não seja o primeiro campo
                if ibge_b and idx_ibge is not None and idx_ibge < len(fields):
                    if fields[idx_ibge].strip() != municipio_ibge.strip():
                        continue

                # Filtro Granularidade: Família (apenas Responsável Familiar = 1)
                if granularidade == "familia" and idx_parentesco is not None and idx_parentesco < len(fields):
                    par_val = fields[idx_parentesco].strip()
                    if par_val != "1":
                        continue

                # Filtro Bolsa Família
                if filtro_pbf != "todos" and idx_pbf is not None and idx_pbf < len(fields):
                    pbf_val = fields[idx_pbf].strip()
                    if filtro_pbf == "sim" and pbf_val != "1":
                        continue
                    elif filtro_pbf == "nao" and pbf_val == "1":
                        continue

                # Filtro Atualização Cadastral
                if filtro_atualizacao != "todos" and idx_desat is not None and idx_desat < len(fields):
                    desat_val = fields[idx_desat].strip()
                    # 0, 1, 2 = até 24 meses (atualizado) | 3, 4, 5 = mais de 24 meses (desatualizado)
                    is_desat = desat_val in ("3", "4", "5")
                    if filtro_atualizacao == "desatualizados" and not is_desat:
                        continue
                    elif filtro_atualizacao == "atualizados" and is_desat:
                        continue

                # Filtro Faixa de Renda (fx_rfpc)
                # 1 = até R$ 89 | 2 = R$ 89 a R$ 178 | 3 = R$ 178 até 1/2 SM | 4 = acima 1/2 SM
                if filtro_renda != "todas" and idx_rfpc is not None and idx_rfpc < len(fields):
                    rfpc_val = fields[idx_rfpc].strip()
                    if filtro_renda == "extrema_pobreza" and rfpc_val != "1":
                        continue
                    elif filtro_renda == "pobreza" and rfpc_val != "2":
                        continue
                    elif filtro_renda == "baixa_renda" and rfpc_val != "3":
                        continue
                    elif filtro_renda == "acima_meio_sm" and rfpc_val != "4":
                        continue

                # Filtro Bairro / Unidade Territorial
                if bairro_lower:
                    match_loc = False
                    if idx_bairro is not None and idx_bairro < len(fields):
                        if bairro_lower in fields[idx_bairro].lower():
                            match_loc = True
                    if not match_loc and idx_cras is not None and idx_cras < len(fields):
                        if bairro_lower in fields[idx_cras].lower():
                            match_loc = True
                    if not match_loc:
                        continue

                # Coleta estatísticas
                if idx_cod_fam is not None and idx_cod_fam < len(fields):
                    distinct_families.add(fields[idx_cod_fam].strip())

                if idx_pbf is not None and idx_pbf < len(fields) and fields[idx_pbf].strip() == "1":
                    count_pbf_sim += 1

                if idx_desat is not None and idx_desat < len(fields) and fields[idx_desat].strip() in ("3", "4", "5"):
                    count_desatualizados += 1

                if idx_renda_media is not None and idx_renda_media < len(fields):
                    try:
                        renda_float = float(fields[idx_renda_media].strip().replace(",", "."))
                        total_renda_soma += renda_float
                        renda_count += 1
                    except Exception:
                        pass

                # Extrai apenas as colunas selecionadas com tradução e LGPD
                row_vals = []
                for idx in selected_indices:
                    val = fields[idx].strip() if idx < len(fields) else ""
                    col_name = all_columns[idx]

                    # Tradução Categórica
                    if idx in translation_maps:
                        mp = translation_maps[idx]
                        if val in mp:
                            val = mp[val]
                        elif val.isdigit() and str(int(val)) in mp:
                            val = mp[str(int(val))]

                    # LGPD Mascaramento
                    if modo_lgpd:
                        val = apply_lgpd_mask(col_name, val)

                    row_vals.append(val)

                processed_rows.append(row_vals)

                if limite_linhas and len(processed_rows) >= limite_linhas:
                    break

            if progress_callback:
                progress_callback(0.90, "Formatando tabela final e calculando resumo...")

            # Define nomes das colunas de saída
            final_col_names = []
            for col in selected_cols:
                desc, _ = self.dict_parser.get_field_info(col)
                # No nível Família (apenas Responsável Familiar), contextualiza dados de pessoa
                if granularidade == "familia":
                    c_norm = col.lower().replace("d.", "").replace("p.", "")
                    if c_norm == "num_cpf_pessoa":
                        desc = "CPF do Responsável Familiar (RF)"
                    elif c_norm == "num_nis_pessoa_atual":
                        desc = "NIS do Responsável Familiar (RF)"
                    elif c_norm == "nom_pessoa":
                        desc = "Nome do Responsável Familiar (RF)"

                if header_mode == "amigavel":
                    final_col_names.append(desc if desc else col)
                elif header_mode == "tecnico_amigavel":
                    final_col_names.append(f"[{col}] {desc}" if desc and desc != col else col)
                else:
                    final_col_names.append(col)

            df = pd.DataFrame(processed_rows, columns=final_col_names)

            total_pessoas = len(processed_rows)
            total_familias = len(distinct_families) if distinct_families else total_pessoas
            perc_pbf = (count_pbf_sim / total_pessoas * 100.0) if total_pessoas > 0 else 0.0
            perc_desat = (count_desatualizados / total_pessoas * 100.0) if total_pessoas > 0 else 0.0
            media_renda = (total_renda_soma / renda_count) if renda_count > 0 else 0.0

            metrics = {
                "total_registros": total_pessoas,
                "total_familias": total_familias,
                "total_pessoas": total_pessoas,
                "pbf_beneficiarios": count_pbf_sim,
                "pbf_percentual": perc_pbf,
                "desatualizados_total": count_desatualizados,
                "desatualizados_percentual": perc_desat,
                "renda_media_rfpc": media_renda
            }

            if progress_callback:
                progress_callback(1.0, f"Concluído! {total_pessoas:,} registros preparados.")

            return df, metrics

        finally:
            stream.close()
            if parent_zip:
                parent_zip.close()
