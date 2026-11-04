import os
import unittest
from src.core.dictionary_parser import DictionaryParser
from src.core.data_engine import DataEngine

class TestDataEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = DictionaryParser(json_path="src/assets/dicionario_padrao.json")
        cls.engine = DataEngine(cls.parser)
        cls.zip_path = "base/cecad/tab_cad_07082026_32_20260911.zip"
        if not os.path.exists(cls.zip_path):
            cls.zip_path = "base/tab_cad_07082026_32_20260911.zip"

    def test_process_municipio_with_limit(self):
        # Filter for Presidente Kennedy (3204302) with 50 rows limit
        df, metrics = self.engine.process_data(
            file_path=self.zip_path,
            municipio_ibge="3204302",
            perfil_colunas="geral",
            limite_linhas=50
        )
        self.assertEqual(len(df), 50)
        self.assertGreater(metrics["total_registros"], 0)
        # Check that categorical translation occurred
        # In perfil geral, "Estado cadastral da familia" or "cod_est_cadastral_fam"
        found_translated = False
        for col in df.columns:
            if "estado cadastral" in col.lower():
                found_translated = True
                vals = df[col].dropna().unique()
                for v in vals:
                    if v:
                        self.assertIn(v, ["Cadastrado", "Sem Registro Civil"])
        self.assertTrue(found_translated)

    def test_granularity_familia(self):
        # Nível família (apenas RF)
        df, metrics = self.engine.process_data(
            file_path=self.zip_path,
            municipio_ibge="3204302",
            granularidade="familia",
            perfil_colunas="bolsa_familia",
            limite_linhas=30
        )
        self.assertLessEqual(len(df), 30)
        self.assertGreater(len(df), 0)

    def test_filter_bolsa_familia(self):
        df, metrics = self.engine.process_data(
            file_path=self.zip_path,
            municipio_ibge="3204302",
            filtro_pbf="sim",
            perfil_colunas="bolsa_familia",
            limite_linhas=20
        )
        self.assertEqual(len(df), 20)
        # Check that PBF column has only "Sim"
        for col in df.columns:
            if "bolsa família" in col.lower() or "marc_pbf" in col.lower():
                vals = set(df[col].unique())
                self.assertTrue(vals.issubset({"Sim"}))

    def test_modo_lgpd(self):
        df, _ = self.engine.process_data(
            file_path=self.zip_path,
            municipio_ibge="3204302",
            modo_lgpd=True,
            perfil_colunas="geral",
            limite_linhas=15
        )
        # Check CPF and Name masking
        for col in df.columns:
            if "cpf" in col.lower():
                sample_cpfs = [x for x in df[col] if x]
                for cpf in sample_cpfs:
                    self.assertIn("***", cpf)
            if "nome" in col.lower() and "pessoa" in col.lower():
                sample_names = [x for x in df[col] if x]
                for n in sample_names:
                    # should have dot like M. S.
                    self.assertTrue("." in n or "[" in n)

if __name__ == '__main__':
    unittest.main()
