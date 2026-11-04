"""
Módulo de adaptadores para bases de dados sociais.
"""

from src.core.adapters.base_adapter import BaseAdapter, StatCardDefinition
from src.core.adapters.cecad_adapter import CecadAdapter
from src.core.adapters.bolsa_familia_adapter import BolsaFamiliaFolhaAdapter

__all__ = [
    "BaseAdapter",
    "StatCardDefinition",
    "CecadAdapter",
    "BolsaFamiliaFolhaAdapter"
]
