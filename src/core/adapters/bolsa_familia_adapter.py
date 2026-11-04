"""
Adaptador especializado para a base da Folha de Pagamento do Bolsa Família.
Compatível tanto com extrações operacionais do SIBEC/SAGICAD (Caixa/MDS)
quanto com arquivos abertos do Portal da Transparência (CGU/MDS).
"""

import os
import io
import zipfile
import re
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
import pandas as pd

from src.core.adapters.base_adapter import BaseAdapter, StatCardDefinition
from src.core.file_inspector import get_municipio_nome
from src.core.lgpd import mask_cpf, mask_nis, mask_name, mask_cep


# Dicionário oficial de campos da Folha do Bolsa Família (Caixa/MDS - SIBEC e Transparência)
SIBEC_COLUMN_METADATA: Dict[str, Dict[str, Any]] = {
    "prog": {
        "label": "Código do Programa",
        "description": "Código do programa social (ex: 1466 para Bolsa Família)",
    },
    "ref_folha": {
        "label": "Mês de Referência da Folha",
        "description": "Ano e Mês de referência da folha de pagamento (AAAAMM)",
    },
    "uf": {
        "label": "UF do Município",
        "description": "Sigla da UF do município de vinculação da família",
    },
    "ibge": {
        "label": "Código IBGE do Município",
        "description": "Código IBGE de 7 dígitos do município",
    },
    "cod_familiar": {
        "label": "Código Familiar",
        "description": "Número de identificação da família no Cadastro Único",
    },
    "cpf": {
        "label": "CPF do Membro",
        "description": "Número do CPF do membro favorecido",
    },
    "nis": {
        "label": "NIS do Membro",
        "description": "Número de Identificação Social (NIS)",
    },
    "nome": {
        "label": "Nome do Membro",
        "description": "Nome completo da pessoa / favorecido",
    },
    "tipo_pgto_previsto": {
        "label": "Tipo de Pagamento Previsto",
        "description": "Canal ou modalidade de crédito do pagamento",
        "translations": {
            "01": "Plataforma Social",
            "1": "Plataforma Social",
            "02": "Crédito em Conta 023",
            "2": "Crédito em Conta 023",
            "03": "Crédito em Conta 013",
            "3": "Crédito em Conta 013",
            "04": "Crédito Conta 1288 (Caixa Tem)",
            "4": "Crédito Conta 1288 (Caixa Tem)",
        }
    },
    "pacto": {
        "label": "Tipo de Pacto",
        "description": "Indica vinculação a pacto de gestão",
        "translations": {
            "0": "Não",
            "1": "Municipal",
            "2": "Estadual",
            "3": "Municipal e Estadual",
        }
    },
    "compet_parcela": {
        "label": "Competência da Parcela",
        "description": "Ano e Mês de competência da parcela disponibilizada (AAAAMM)",
    },
    "tp_benef": {
        "label": "Tipo de Benefício",
        "description": "Sigla do benefício específico pago na parcela",
        "translations": {
            "BRC": "BRC - Renda de Cidadania",
            "BCO": "BCO - Complementar",
            "BPI": "BPI - Primeira Infância",
            "BVN": "BVN - Variável Nutriz",
            "BV": "BV - Variável Criança/Adolescente",
            "BVA": "BVA - Variável Adolescente",
            "BVG": "BVG - Variável Gestante",
            "BET": "BET - Extraordinário de Transição",
            "PAGB": "PAGB - Auxílio Gás",
            "AC-EV": "AC-EV - Auxílio Criança",
        }
    },
    "vlrbenef": {
        "label": "Valor do Benefício (R$)",
        "description": "Valor nominal deste benefício na parcela",
    },
    "vlrtotal": {
        "label": "Valor Total da Família (R$)",
        "description": "Somatório de todos os benefícios da família na folha",
    },
    "sitbeneficio": {
        "label": "Situação do Benefício",
        "description": "Situação operacional da parcela deste benefício",
    },
    "sitbeneficiario": {
        "label": "Situação do Beneficiário",
        "description": "Situação cadastral do membro beneficiário",
    },
    "sitfam": {
        "label": "Situação da Família",
        "description": "Situação consolidada da família na folha (Liberado / Bloqueado / Suspenso)",
    },
    "inicio_vig_benef": {
        "label": "Início de Vigência do Benefício",
        "description": "Data inicial de concessão do benefício",
    },
    "fim_vig_benef": {
        "label": "Fim de Vigência do Benefício",
        "description": "Data prevista de encerramento do benefício",
    },
    "marca_rf": {
        "label": "Responsável Familiar",
        "description": "Indicador se a linha representa o Responsável Familiar (Sim/Não)",
        "translations": {
            "S": "Sim",
            "N": "Não"
        }
    },
    "dec_jud": {
        "label": "Decisão Judicial",
        "description": "Benefício concedido por determinação judicial",
        "translations": {
            "S": "Sim",
            "N": "Não"
        }
    },
    "quilombola": {
        "label": "Família Quilombola",
        "description": "Indicador de pertencimento a comunidade quilombola",
        "translations": {
            "S": "Sim",
            "N": "Não"
        }
    },
    "trab_escrv": {
        "label": "Trabalho Análogo a Escravo",
        "description": "Família com histórico de resgate de trabalho análogo a escravo",
        "translations": {
            "S": "Sim",
            "N": "Não"
        }
    },
    "indigena": {
        "label": "Família Indígena",
        "description": "Indicador de pertencimento a povo indígena",
        "translations": {
            "S": "Sim",
            "N": "Não"
        }
    },
    "catador_recic": {
        "label": "Catador de Material Reciclável",
        "description": "Família com membro catador de materiais recicláveis",
        "translations": {
            "S": "Sim",
            "N": "Não"
        }
    },
    "trabalho_inf": {
        "label": "Foco de Trabalho Infantil",
        "description": "Família com identificação de trabalho infantil",
        "translations": {
            "S": "Sim",
            "N": "Não"
        }
    },
    "renda_per_capita": {
        "label": "Renda Familiar Per Capita (R$)",
        "description": "Renda per capita declarada no Cadastro Único",
    },
    "renda_com_pbf": {
        "label": "Renda Familiar com PBF (R$)",
        "description": "Renda per capita após a transferência do Bolsa Família",
    },
    "qtd_pessoas": {
        "label": "Quantidade de Membros da Família",
        "description": "Número de pessoas que compõem o grupo familiar",
    },
    "dt_atu_cadastral": {
        "label": "Data da Atualização Cadastral",
        "description": "Data da última atualização cadastral da família no CadÚnico",
    },
    "endereco": {
        "label": "Endereço Residencial",
        "description": "Logradouro, número e complementos da residência",
    },
    "bairro": {
        "label": "Bairro",
        "description": "Nome do bairro da família",
    },
    "cep": {
        "label": "CEP Residencial",
        "description": "Código de Endereçamento Postal",
    },
    "telefone1": {
        "label": "Telefone Principal",
        "description": "Telefone primário do Responsável Familiar",
    },
    "telefone2": {
        "label": "Telefone Secundário",
        "description": "Telefone secundário do Responsável Familiar",
    },
    # Portal da Transparência:
    "mes competencia": {
        "label": "Mês de Competência",
        "description": "Ano e Mês da parcela no Portal da Transparência",
    },
    "codigo municipio ibge": {
        "label": "Código IBGE do Município",
        "description": "Código IBGE do município favorecido",
    },
    "nome municipio": {
        "label": "Nome do Município",
        "description": "Nome oficial do município",
    },
    "nis favorecido": {
        "label": "NIS do Favorecido",
        "description": "NIS da pessoa titular do benefício",
    },
    "nome favorecido": {
        "label": "Nome do Favorecido",
        "description": "Nome da pessoa titular do benefício",
    },
    "valor parcela": {
        "label": "Valor da Parcela (R$)",
        "description": "Valor monetário pago na competência",
    }
}


class BolsaFamiliaFolhaAdapter(BaseAdapter):
    """Adaptador para leitura, filtragem e estatísticas financeiras da Folha do Bolsa Família."""

    adapter_id = "bolsa_familia_folha"
    display_name = "Folha de Pagamento do Bolsa Família"
    description = "Dados mensais de concessão, valores e situação das parcelas (SIBEC / Transparência / MDS)."
    file_types = [("Folha do Bolsa Família (*.zip, *.csv)", "*.zip;*.csv"), ("Todos os Arquivos", "*.*")]

    def __init__(self):
        self.delimiter = ";"
        self.columns: List[str] = []
        self.is_zip = False
        self.total_lines_approx = 0

    def _open_stream(self, file_path: str):
        is_zip = zipfile.is_zipfile(file_path) if os.path.exists(file_path) else False
        if is_zip:
            z = zipfile.ZipFile(file_path, "r")
            csvs = [name for name in z.namelist() if name.lower().endswith(".csv")]
            if not csvs:
                raise ValueError("Nenhum arquivo .csv encontrado dentro do arquivo ZIP da Folha.")
            return z.open(csvs[0], "r"), z
        else:
            return open(file_path, "rb"), None

    def _detect_delimiter(self, line_str: str) -> str:
        for delim in [";", ",", "\t"]:
            if delim in line_str:
                return delim
        return ";"

    def inspect_file(self, file_path: str) -> Dict[str, Any]:
        stream, parent_zip = self._open_stream(file_path)
        try:
            line_bytes = stream.readline()
            if not line_bytes:
                raise ValueError("O arquivo da Folha do Bolsa Família está vazio.")

            header_str = ""
            for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
                try:
                    header_str = line_bytes.decode(enc).strip()
                    break
                except Exception:
                    continue

            self.delimiter = self._detect_delimiter(header_str)
            self.columns = [c.strip().strip('"') for c in header_str.split(self.delimiter) if c.strip()]

            # Encontra coluna de município IBGE
            idx_ibge = self._find_column_index(self.columns, [
                "ibge", "codigo municipio ibge", "codigo_municipio_ibge", "cd_ibge",
                "codigo ibge", "cod_ibge", "municipio_ibge", "cod_municipio"
            ])
            idx_ref = self._find_column_index(self.columns, [
                "ref_folha", "ref folha", "mes competencia", "mes_competencia", "mes_referencia"
            ])

            # Escaneia municípios e contagem
            counts: Dict[str, int] = {}
            total_records = 0
            detected_ref = ""

            reader = io.BufferedReader(stream, buffer_size=1024 * 1024 * 8)
            for line in reader:
                total_records += 1
                try:
                    l_str = line.decode("latin1").rstrip("\r\n")
                    flds = [f.strip().strip('"') for f in l_str.split(self.delimiter)]
                    if idx_ibge is not None and idx_ibge < len(flds):
                        code = flds[idx_ibge].strip()
                        if code:
                            counts[code] = counts.get(code, 0) + 1
                    if not detected_ref and idx_ref is not None and idx_ref < len(flds):
                        val_ref = flds[idx_ref].strip()
                        if len(val_ref) == 6 and val_ref.isdigit():
                            ano, mes = val_ref[:4], val_ref[4:]
                            detected_ref = f"Folha: {mes}/{ano}"
                except Exception:
                    continue

            self.total_lines_approx = total_records

            mun_list = []
            for code, cnt in sorted(counts.items(), key=lambda x: x[0]):
                m_nome = get_municipio_nome(code)
                mun_list.append({
                    "cd_ibge": code,
                    "nome": m_nome,
                    "rotulo": f"{code} - {m_nome} ({cnt:,} registros)".replace(",", "."),
                    "contagem": cnt
                })

            is_single = len(mun_list) <= 1
            if is_single:
                name = mun_list[0]["nome"] if mun_list else "Municipal"
                scope_desc = f"Folha Municipal ({name})"
            else:
                scope_desc = f"Folha Estadual ({len(mun_list)} Municípios)"

            ref_desc = detected_ref or self._extract_date_reference(file_path, header_str)

            return {
                "is_single": is_single,
                "municipalities": mun_list,
                "ref_desc": ref_desc,
                "total_lines_approx": total_records,
                "columns": self.columns,
                "scope_desc": scope_desc,
                "delimiter": self.delimiter
            }

        finally:
            stream.close()
            if parent_zip:
                parent_zip.close()

    def _find_column_index(self, columns: List[str], candidates: List[str]) -> Optional[int]:
        normalized = [c.lower().replace("_", " ").replace(".", " ").strip() for c in columns]
        for cand in candidates:
            c_norm = cand.lower().replace("_", " ").replace(".", " ").strip()
            for i, col in enumerate(normalized):
                if c_norm == col:
                    return i
        for cand in candidates:
            c_norm = cand.lower().replace("_", " ").replace(".", " ").strip()
            for i, col in enumerate(normalized):
                if c_norm in col or col in c_norm:
                    return i
        return None

    def _extract_date_reference(self, file_path: str, header_str: str) -> str:
        base_name = os.path.basename(file_path)
        m = re.search(r'C(\d{2})(\d{2})', base_name)
        if m:
            ano_s, mes_s = m.groups()
            return f"Competência: {mes_s}/20{ano_s}"
        m2 = re.search(r'(\d{4})(\d{2})', base_name)
        if m2:
            ano, mes = m2.groups()
            if 1 <= int(mes) <= 12 and 2000 <= int(ano) <= 2030:
                return f"Competência: {mes}/{ano}"
        return "Folha Mensal de Pagamentos"

    @staticmethod
    def format_column_header(col_name: str, header_mode: str = "amigavel", granularidade: str = "familia") -> str:
        """Formata o cabeçalho de uma coluna da folha de acordo com o modo escolhido."""
        col_key = col_name.strip().lower()
        meta = SIBEC_COLUMN_METADATA.get(col_key)
        if not meta:
            c_norm = col_key.replace(" ", "_")
            meta = SIBEC_COLUMN_METADATA.get(c_norm)

        desc = meta.get("label") if meta else col_name

        if granularidade == "familia":
            if col_key in ("cpf", "num_cpf"):
                desc = "CPF do Responsável Familiar (RF)"
            elif col_key in ("nis", "num_nis"):
                desc = "NIS do Responsável Familiar (RF)"
            elif col_key in ("nome", "nom_beneficiario", "nome beneficiario"):
                desc = "Nome do Responsável Familiar (RF)"

        if header_mode == "amigavel":
            return desc if desc else col_name
        elif header_mode == "tecnico_amigavel":
            return f"[{col_name}] {desc}" if desc and desc != col_name else col_name
        else:
            return col_name

    @staticmethod
    def format_cell_value(col_name: str, val: Any) -> Any:
        """Traduz códigos categóricos da Folha para descrições legíveis."""
        if not isinstance(val, str):
            return val
        v_str = val.strip()
        if not v_str:
            return ""

        col_key = col_name.strip().lower().replace(" ", "_")
        meta = SIBEC_COLUMN_METADATA.get(col_key)
        if meta and "translations" in meta:
            trans = meta["translations"]
            v_upper = v_str.upper()
            if v_upper in trans:
                return trans[v_upper]
            if v_str in trans:
                return trans[v_str]
            if v_str.isdigit():
                v_int = str(int(v_str))
                if v_int in trans:
                    return trans[v_int]
        return v_str

    def get_stat_card_definitions(self) -> List[StatCardDefinition]:
        return [
            StatCardDefinition("total_beneficiarios", "Total de Famílias", "Famílias na folha", "👥"),
            StatCardDefinition("valor_total_folha", "Total da Folha", "Valor total transferido", "💰"),
            StatCardDefinition("beneficio_medio", "Benefício Médio", "Valor médio por família", "💵"),
            StatCardDefinition("bloqueados_total", "Bloqueados / Suspensos", "Em averiguação/bloqueio", "⚠️"),
            StatCardDefinition("gpte_total", "Populações Tradicionais (GPTE)", "Catadores, trab. infantil, etc.", "🛡️")
        ]

    def process_data(
        self,
        file_path: str,
        municipios_ibge: Optional[List[str]] = None,
        colunas_customizadas: Optional[List[str]] = None,
        modo_lgpd: bool = False,
        header_mode: str = "amigavel",
        limite_linhas: Optional[int] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        **kwargs
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Lê, filtra, sumariza valores da Folha do Bolsa Família e anonimiza sob LGPD."""
        stream, parent_zip = self._open_stream(file_path)

        try:
            line_bytes = stream.readline()
            if not line_bytes:
                return pd.DataFrame(), {}

            header_str = ""
            for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
                try:
                    header_str = line_bytes.decode(enc).strip()
                    break
                except Exception:
                    continue

            delim = self._detect_delimiter(header_str)
            all_columns = [c.strip().strip('"') for c in header_str.split(delim) if c.strip()]

            # Mapeamento de colunas principais
            idx_ibge = self._find_column_index(all_columns, ["ibge", "codigo municipio ibge", "codigo_municipio_ibge", "cd_ibge"])
            idx_nis = self._find_column_index(all_columns, ["nis", "nis beneficiario", "nis favorecido", "num_nis_beneficiario", "num_nis"])
            idx_nome = self._find_column_index(all_columns, ["nome", "nome beneficiario", "nome favorecido", "nom_beneficiario"])
            idx_cpf = self._find_column_index(all_columns, ["cpf", "num_cpf"])

            # Valores (SIBEC usa VLRTOTAL para o total da família e VLRBENEF para o detalhe; Transparência usa VALOR PARCELA)
            idx_vlrtotal = self._find_column_index(all_columns, ["vlrtotal", "vlr_total", "valor parcela", "valor"])
            idx_vlrbenef = self._find_column_index(all_columns, ["vlrbenef", "vlr_beneficio", "vlr_parcela"])

            # Situação
            idx_sitbeneficio = self._find_column_index(all_columns, ["sitbeneficio", "sit_beneficio", "situacao parcela", "situacao"])
            idx_sitbeneficiario = self._find_column_index(all_columns, ["sitbeneficiario", "sit_beneficiario"])
            idx_sitfam = self._find_column_index(all_columns, ["sitfam", "sit_fam"])

            # Responsável Familiar no SIBEC
            idx_marca_rf = self._find_column_index(all_columns, ["marca_rf", "marca rf"])

            # Endereço no SIBEC
            idx_endereco = self._find_column_index(all_columns, ["endereco", "end"])
            idx_bairro = self._find_column_index(all_columns, ["bairro"])
            idx_cep = self._find_column_index(all_columns, ["cep"])
            idx_tel1 = self._find_column_index(all_columns, ["telefone1", "tel1"])
            idx_tel2 = self._find_column_index(all_columns, ["telefone2", "tel2"])

            # Dados Operacionais e Marcadores de Vulnerabilidade (Manual SIBEC)
            idx_dt_atu = self._find_column_index(all_columns, ["dt_atu_cadastral", "dt atu cadastral", "data_atualizacao", "data_atualizacao_cadastral"])
            idx_indigena = self._find_column_index(all_columns, ["indigena"])
            idx_quilombola = self._find_column_index(all_columns, ["quilombola"])
            idx_catador = self._find_column_index(all_columns, ["catador_recic", "catador"])
            idx_trab_inf = self._find_column_index(all_columns, ["trabalho_inf", "trabalho_infantil"])
            idx_trab_escrv = self._find_column_index(all_columns, ["trab_escrv", "trabalho_escravo"])
            idx_tp_benef = self._find_column_index(all_columns, ["tp_benef", "tipo_beneficio", "beneficio"])

            # Filtros do usuário
            target_ibges: Optional[Set[str]] = set(municipios_ibge) if municipios_ibge else None
            filtro_situacao = str(kwargs.get("filtro_situacao", "todos")).strip().lower()
            filtro_valor = str(kwargs.get("filtro_valor", "todas")).strip().lower()
            filtro_gpte = str(kwargs.get("filtro_gpte", "todos")).strip().lower()
            filtro_atualizacao = str(kwargs.get("filtro_atualizacao", "todos")).strip().lower()
            granularidade = str(kwargs.get("granularidade", "familia")).strip().lower()

            ref_year = 2026
            m_yr = re.search(r'C(\d{2})(\d{2})', os.path.basename(file_path))
            if m_yr:
                ref_year = 2000 + int(m_yr.group(1))
            else:
                m_yr4 = re.search(r'(\d{4})(\d{2})', os.path.basename(file_path))
                if m_yr4:
                    ref_year = int(m_yr4.group(1))

            selected_cols = colunas_customizadas if colunas_customizadas else all_columns
            selected_indices = [all_columns.index(c) for c in selected_cols if c in all_columns]

            processed_rows = []
            total_records = 0
            filtered_count = 0
            soma_valores = 0.0
            count_bloqueados = 0
            count_acima_600 = 0
            count_desat = 0
            count_gpte = 0
            count_bpi = 0
            distinct_families = set()

            if progress_callback:
                progress_callback(0.05, "Lendo e filtrando registros da Folha do Bolsa Família...")

            reader = io.BufferedReader(stream, buffer_size=1024 * 1024 * 8)

            for line in reader:
                total_records += 1

                if progress_callback and total_records % 250000 == 0:
                    progress_callback(min(0.85, total_records / 1500000.0), f"Processados {total_records:,} registros da Folha...")

                line_str = line.decode("latin1").rstrip("\r\n")
                fields = [f.strip().strip('"') for f in line_str.split(delim)]

                # Filtro Município
                if target_ibges and idx_ibge is not None and idx_ibge < len(fields):
                    if fields[idx_ibge].strip() not in target_ibges:
                        continue

                # Se o arquivo for SIBEC e granularidade == 'familia', filtra apenas linha master do Responsável Familiar
                is_rf = True
                if idx_marca_rf is not None and idx_marca_rf < len(fields):
                    val_rf = fields[idx_marca_rf].strip().upper()
                    is_rf = (val_rf == "S")
                    if granularidade == "familia" and not is_rf:
                        continue

                # Extrai valor da parcela (se for SIBEC e linha master, usa VLRTOTAL; senão VLRBENEF)
                val_float = 0.0
                raw_val = ""
                if idx_vlrtotal is not None and idx_vlrtotal < len(fields) and fields[idx_vlrtotal].strip():
                    raw_val = fields[idx_vlrtotal].strip()
                elif idx_vlrbenef is not None and idx_vlrbenef < len(fields):
                    raw_val = fields[idx_vlrbenef].strip()

                if raw_val:
                    if "," in raw_val and "." in raw_val:
                        cleaned = raw_val.replace(".", "").replace(",", ".")
                    elif "," in raw_val:
                        cleaned = raw_val.replace(",", ".")
                    else:
                        cleaned = raw_val
                    try:
                        val_float = float(cleaned)
                    except Exception:
                        val_float = 0.0

                # Extrai situação da parcela (procura em SITBENEFICIO, SITBENEFICIARIO, SITFAM)
                sit_parts = []
                for s_idx in [idx_sitbeneficio, idx_sitbeneficiario, idx_sitfam]:
                    if s_idx is not None and s_idx < len(fields):
                        s_val = fields[s_idx].lower().strip()
                        if s_val:
                            sit_parts.append(s_val)

                is_blocked = any("bloqueado" in s for s in sit_parts)
                is_suspended = any("suspenso" in s for s in sit_parts)
                is_cancelled = any("cancelado" in s for s in sit_parts)
                # SIBEC: Quando houver empilhamento, a situação é a mais grave.
                # Só é considerado liberado se contiver palavra de liberação E NÃO for bloqueado, suspenso ou cancelado.
                is_liberado = any(any(w in s for w in ["liberado", "pago", "disponivel", "emitido"]) for s in sit_parts) and not (is_blocked or is_suspended or is_cancelled)

                # Filtro Situação
                if filtro_situacao != "todos":
                    if filtro_situacao == "liberados" and not is_liberado:
                        continue
                    elif filtro_situacao == "bloqueados" and not is_blocked:
                        continue
                    elif filtro_situacao == "suspensos" and not is_suspended:
                        continue
                    elif filtro_situacao == "cancelados" and not is_cancelled:
                        continue

                # Filtro Faixa de Valor
                if filtro_valor != "todas":
                    if filtro_valor == "ate_600" and val_float > 600.0:
                        continue
                    elif filtro_valor == "601_a_800" and not (600.0 < val_float <= 800.0):
                        continue
                    elif filtro_valor == "acima_800" and val_float <= 800.0:
                        continue

                # Marcadores GPTE (Populações Tradicionais e Vulnerabilidades)
                is_indigena = (idx_indigena is not None and idx_indigena < len(fields) and fields[idx_indigena].strip().upper() == "S")
                is_quilombola = (idx_quilombola is not None and idx_quilombola < len(fields) and fields[idx_quilombola].strip().upper() == "S")
                is_catador = (idx_catador is not None and idx_catador < len(fields) and fields[idx_catador].strip().upper() == "S")
                is_trab_inf = (idx_trab_inf is not None and idx_trab_inf < len(fields) and fields[idx_trab_inf].strip().upper() == "S")
                is_trab_escrv = (idx_trab_escrv is not None and idx_trab_escrv < len(fields) and fields[idx_trab_escrv].strip().upper() == "S")
                has_any_gpte = is_indigena or is_quilombola or is_catador or is_trab_inf or is_trab_escrv

                # Filtro GPTE
                if filtro_gpte != "todos":
                    if filtro_gpte == "gpte_sim" and not has_any_gpte:
                        continue
                    elif filtro_gpte == "indigena" and not is_indigena:
                        continue
                    elif filtro_gpte == "quilombola" and not is_quilombola:
                        continue
                    elif filtro_gpte == "catador" and not is_catador:
                        continue
                    elif filtro_gpte == "trabalho_infantil" and not is_trab_inf:
                        continue
                    elif filtro_gpte == "trabalho_escravo" and not is_trab_escrv:
                        continue
                    elif filtro_gpte == "nao_gpte" and has_any_gpte:
                        continue

                # Data de Atualização Cadastral (> 2 anos = desatualizado)
                is_desat = False
                if idx_dt_atu is not None and idx_dt_atu < len(fields):
                    dt_val = fields[idx_dt_atu].strip()
                    if dt_val:
                        parts = dt_val.split("/")
                        if len(parts) == 3 and len(parts[2]) == 4:
                            try:
                                yr = int(parts[2])
                                if yr <= (ref_year - 2):
                                    is_desat = True
                            except Exception:
                                pass

                # Filtro Atualização Cadastral
                if filtro_atualizacao != "todos":
                    if filtro_atualizacao == "desatualizados" and not is_desat:
                        continue
                    elif filtro_atualizacao == "atualizados" and is_desat:
                        continue

                # Passou pelos filtros
                filtered_count += 1
                soma_valores += val_float

                if is_blocked or is_suspended:
                    count_bloqueados += 1

                if val_float > 600.0:
                    count_acima_600 += 1

                if has_any_gpte:
                    count_gpte += 1

                if is_desat:
                    count_desat += 1

                # Tipo de Benefício Primeira Infância (BPI)
                if idx_tp_benef is not None and idx_tp_benef < len(fields):
                    if "BPI" in fields[idx_tp_benef].strip().upper():
                        count_bpi += 1

                # Monta linha para visualização
                if limite_linhas is None or len(processed_rows) < limite_linhas:
                    row_vals = []
                    for idx in selected_indices:
                        val = fields[idx].strip() if idx < len(fields) else ""
                        col_name = all_columns[idx]

                        # Tradução categórica de valores
                        val = self.format_cell_value(col_name, val)

                        # Aplica LGPD estendida para a Folha
                        if modo_lgpd:
                            if idx == idx_nis:
                                val = mask_nis(val)
                            elif idx == idx_nome:
                                val = mask_name(val)
                            elif idx_cpf is not None and idx == idx_cpf:
                                val = mask_cpf(val)
                            elif idx in [idx_endereco, idx_bairro, idx_tel1, idx_tel2]:
                                val = "[OCULTO - LGPD]" if val.strip() else ""
                            elif idx == idx_cep:
                                val = mask_cep(val)

                        row_vals.append(val)

                    processed_rows.append(row_vals)

            if progress_callback:
                progress_callback(0.92, "Consolidando métricas e formatando tabela...")

            final_col_names = [
                self.format_column_header(col, header_mode=header_mode, granularidade=granularidade)
                for col in selected_cols
            ]
            df = pd.DataFrame(processed_rows, columns=final_col_names)

            media_parcela = (soma_valores / filtered_count) if filtered_count > 0 else 0.0
            pct_bloq = (count_bloqueados / filtered_count * 100.0) if filtered_count > 0 else 0.0
            pct_acima_600 = (count_acima_600 / filtered_count * 100.0) if filtered_count > 0 else 0.0
            pct_desat = (count_desat / filtered_count * 100.0) if filtered_count > 0 else 0.0
            pct_gpte = (count_gpte / filtered_count * 100.0) if filtered_count > 0 else 0.0

            metrics = {
                "total_registros": filtered_count,
                "total_beneficiarios": filtered_count,
                "valor_total_folha": soma_valores,
                "beneficio_medio": media_parcela,
                "bloqueados_total": count_bloqueados,
                "bloqueados_percentual": pct_bloq,
                "acima_600_total": count_acima_600,
                "acima_600_percentual": pct_acima_600,
                "desatualizados_total": count_desat,
                "desatualizados_percentual": pct_desat,
                "gpte_total": count_gpte,
                "gpte_percentual": pct_gpte,
                "bpi_total": count_bpi
            }

            if progress_callback:
                progress_callback(1.0, f"Concluído! {filtered_count:,} registros da Folha processados.")

            return df, metrics

        finally:
            stream.close()
            if parent_zip:
                parent_zip.close()
