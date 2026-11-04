"""
Módulo base para adaptadores de dados sociais (CECAD, Folha Bolsa Família, BPC, etc.).
Define a interface padronizada que permite desacoplar a ingestão, filtros,
métricas e regras LGPD da interface gráfica.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any, Callable
import pandas as pd


class StatCardDefinition:
    """Metadados para renderização dinâmica de um cartão de estatística."""

    def __init__(self, key: str, title: str, subtitle: str, icon: str):
        self.key = key
        self.title = title
        self.subtitle = subtitle
        self.icon = icon


class BaseAdapter(ABC):
    """Contrato abstrato que toda base de dados social deve implementar."""

    adapter_id: str = "base"
    display_name: str = "Base de Dados"
    description: str = "Descrição da base"
    file_types: List[Tuple[str, str]] = [("Arquivos da Base (*.zip, *.csv)", "*.zip;*.csv")]

    @abstractmethod
    def inspect_file(self, file_path: str) -> Dict[str, Any]:
        """
        Inspeciona o arquivo e retorna dicionário com:
        - 'is_single': bool
        - 'municipalities': List[Dict[str, Any]] (com 'cd_ibge', 'nome', 'contagem', 'rotulo')
        - 'date_info': Dict[str, str]
        - 'total_lines_approx': int
        - 'columns': List[str]
        - 'scope_desc': str
        """
        pass

    @abstractmethod
    def get_stat_card_definitions(self) -> List[StatCardDefinition]:
        """Retorna as definições dos 5 cartões de estatísticas para a interface."""
        pass

    @abstractmethod
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
        """
        Processa os registros aplicando filtros e regras de tradução/anonimização.
        Retorna (df_processado, metricas_resumo).
        """
        pass
