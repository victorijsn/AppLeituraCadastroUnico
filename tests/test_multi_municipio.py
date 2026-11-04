import os
import unittest
from src.core.dictionary_parser import DictionaryParser
from src.core.data_engine import DataEngine


class TestMultiMunicipioAndMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = DictionaryParser(json_path="src/assets/dicionario_padrao.json")
        cls.engine = DataEngine(cls.parser)
        cls.zip_path = "base/cecad/tab_cad_07082026_32_20260911.zip"
        if not os.path.exists(cls.zip_path):
            cls.zip_path = "base/tab_cad_07082026_32_20260911.zip"

    def test_multi_municipio_filtering(self):
        # 3204302 = Presidente Kennedy, 3200102 = Afonso Cláudio (ou outro do ES)
        selected = ["3204302", "3200102"]
        df, metrics = self.engine.process_data(
            file_path=self.zip_path,
            municipios_ibge=selected,
            perfil_colunas="geral",
            header_mode="tecnico",
            limite_linhas=40
        )

        self.assertEqual(len(df), 40)
        # As métricas devem contemplar o total da soma dos municípios selecionados
        self.assertGreater(metrics["total_registros"], 40)
        self.assertGreater(metrics["total_familias"], 0)

        # Verifica se o código IBGE das linhas pertence à lista selecionada
        col_ibge = None
        for col in df.columns:
            if "cd_ibge" in col.lower():
                col_ibge = col
                break
        self.assertIsNotNone(col_ibge)
        unique_ibges = set(df[col_ibge].unique())
        self.assertTrue(unique_ibges.issubset(set(selected)))

    def test_metrics_on_full_dataset_with_preview_limit(self):
        # Quando limite_linhas é 10, o DataFrame deve ter 10 linhas, mas as métricas devem ter o total real (> 10)
        df, metrics = self.engine.process_data(
            file_path=self.zip_path,
            municipio_ibge="3204302",
            perfil_colunas="bolsa_familia",
            limite_linhas=10
        )
        self.assertEqual(len(df), 10)
        # O município 3204302 possui muito mais de 10 pessoas
        self.assertGreater(metrics["total_pessoas"], 10)
        self.assertGreater(metrics["total_familias"], 10)
        self.assertGreaterEqual(metrics["pbf_percentual"], 0.0)


if __name__ == "__main__":
    unittest.main()
