"""
Adaptador especializado para a base do CECAD / Cadastro Único.
Encapsula o FileInspector, DictionaryParser e DataEngine no contrato BaseAdapter.
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
import pandas as pd

from src.core.adapters.base_adapter import BaseAdapter, StatCardDefinition
from src.core.file_inspector import FileInspector
from src.core.data_engine import DataEngine
from src.core.dictionary_parser import DictionaryParser


class CecadAdapter(BaseAdapter):
    """Adaptador para leitura, filtragem e tradução do Cadastro Único (CECAD)."""

    adapter_id = "cecad"
    display_name = "Cadastro Único (CECAD)"
    description = "Base cadastral socioeconômica do MDS (famílias, indivíduos, renda e vulnerabilidade)."
    file_types = [("Bases do CECAD (*.zip, *.csv)", "*.zip;*.csv"), ("Todos os Arquivos", "*.*")]

    def __init__(self, dict_parser: DictionaryParser):
        self.dict_parser = dict_parser
        self.data_engine = DataEngine(dict_parser)
        self.inspector: Optional[FileInspector] = None

    def inspect_file(self, file_path: str) -> Dict[str, Any]:
        self.inspector = FileInspector(file_path)
        is_single, mun_list = self.inspector.scan_municipalities()
        date_info = self.inspector.date_info
        total_lines = self.inspector.total_lines_approx

        if is_single:
            mun_name = mun_list[0]["nome"] if mun_list else "Municipal"
            scope_desc = f"Base Municipal ({mun_name})"
        else:
            scope_desc = f"Base Estadual ({len(mun_list)} Municípios)"

        ref_desc = date_info.get("descricao") or "Não identificada no nome do arquivo"

        return {
            "is_single": is_single,
            "municipalities": mun_list,
            "date_info": date_info,
            "ref_desc": ref_desc,
            "total_lines_approx": total_lines,
            "columns": self.inspector.columns,
            "scope_desc": scope_desc,
            "delimiter": self.inspector.delimiter
        }

    def get_stat_card_definitions(self) -> List[StatCardDefinition]:
        return [
            StatCardDefinition("total_pessoas", "Total de Pessoas", "Total filtrado", "👥"),
            StatCardDefinition("total_familias", "Total de Famílias", "Famílias distintas", "🏠"),
            StatCardDefinition("pbf_percentual", "Bolsa Família", "Taxa de cobertura", "💳"),
            StatCardDefinition("desatualizados_percentual", "Desatualizados", "Mais de 24 meses", "⚠️"),
            StatCardDefinition("renda_media_rfpc", "Renda Média", "Média per capita", "💵")
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
        return self.data_engine.process_data(
            file_path=file_path,
            municipios_ibge=municipios_ibge,
            colunas_customizadas=colunas_customizadas,
            modo_lgpd=modo_lgpd,
            header_mode=header_mode,
            limite_linhas=limite_linhas,
            progress_callback=progress_callback,
            granularidade=kwargs.get("granularidade", "pessoa"),
            perfil_colunas=kwargs.get("perfil_colunas", "completo"),
            filtro_pbf=kwargs.get("filtro_pbf", "todos"),
            filtro_atualizacao=kwargs.get("filtro_atualizacao", "todos"),
            filtro_renda=kwargs.get("filtro_renda", "todas"),
            filtro_bairro=kwargs.get("filtro_bairro", None)
        )
