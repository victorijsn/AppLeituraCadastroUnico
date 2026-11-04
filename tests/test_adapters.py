import os
import unittest
import pandas as pd

from src.core.dictionary_parser import DictionaryParser
from src.core.adapters.cecad_adapter import CecadAdapter
from src.core.adapters.bolsa_familia_adapter import BolsaFamiliaFolhaAdapter


class TestAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = DictionaryParser(json_path="src/assets/dicionario_padrao.json")
        cls.cecad = CecadAdapter(cls.parser)
        cls.pbf = BolsaFamiliaFolhaAdapter()
        cls.cecad_zip = "base/cecad/tab_cad_07082026_32_20260911.zip"
        if not os.path.exists(cls.cecad_zip):
            cls.cecad_zip = "base/tab_cad_07082026_32_20260911.zip"

        # Cria arquivo de teste simulando Folha do Bolsa Família (Portal da Transparência)
        cls.folha_transparencia_csv = "tests/test_folha_transparencia.csv"
        df_transp = pd.DataFrame({
            "MES COMPETENCIA": ["202609"] * 6,
            "CODIGO MUNICIPIO IBGE": ["3204302", "3204302", "3204302", "3205309", "3205309", "3205309"],
            "NOME MUNICIPIO": ["PRESIDENTE KENNEDY", "PRESIDENTE KENNEDY", "PRESIDENTE KENNEDY", "VITORIA", "VITORIA", "VITORIA"],
            "UF": ["ES"] * 6,
            "NIS FAVORECIDO": ["12345678901", "23456789012", "34567890123", "45678901234", "56789012345", "67890123456"],
            "NOME FAVORECIDO": ["Maria da Silva", "Joao Pereira", "Ana Santos", "Carlos Souza", "Beatriz Lima", "Lucas Costa"],
            "VALOR PARCELA": ["600,00", "750,00", "900,00", "600,00", "650,00", "1200,00"]
        })
        df_transp.to_csv(cls.folha_transparencia_csv, sep=";", index=False, encoding="utf-8")

        # Cria arquivo de teste simulando Folha do SIBEC (com coluna de situação do benefício)
        cls.folha_sibec_csv = "tests/test_folha_sibec.csv"
        df_sibec = pd.DataFrame({
            "cd_ibge": ["3204302", "3204302", "3204302", "3204302"],
            "cod_familiar_fam": ["001", "002", "003", "004"],
            "num_nis_beneficiario": ["12345678901", "23456789012", "34567890123", "45678901234"],
            "nom_beneficiario": ["Maria da Silva", "Joao Souza", "Fernanda Lima", "Pedro Rocha"],
            "vlr_beneficio": ["600.00", "700.00", "600.00", "850.00"],
            "sit_beneficio": ["Liberado", "Bloqueado", "Suspenso", "Liberado"],
            "mot_bloqueio": ["", "Averiguacao Cadastral", "Frequencia Escolar", ""]
        })
        df_sibec.to_csv(cls.folha_sibec_csv, sep=";", index=False, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        for f in [cls.folha_transparencia_csv, cls.folha_sibec_csv]:
            if os.path.exists(f):
                os.remove(f)

    def test_cecad_adapter_inspection_and_process(self):
        info = self.cecad.inspect_file(self.cecad_zip)
        self.assertIn("municipalities", info)
        self.assertGreater(len(info["municipalities"]), 0)

        defs = self.cecad.get_stat_card_definitions()
        self.assertEqual(len(defs), 5)
        self.assertEqual(defs[0].key, "total_pessoas")

        df, metrics = self.cecad.process_data(
            file_path=self.cecad_zip,
            municipios_ibge=["3204302"],
            limite_linhas=5
        )
        self.assertEqual(len(df), 5)
        self.assertGreater(metrics["total_pessoas"], 5)

    def test_pbf_transparencia_inspection_and_process(self):
        info = self.pbf.inspect_file(self.folha_transparencia_csv)
        self.assertEqual(info["total_lines_approx"], 6)
        self.assertEqual(len(info["municipalities"]), 2)  # Presidente Kennedy e Vitoria

        # Filtra apenas Presidente Kennedy (3 parcelas: 600, 750, 900 -> total 2250, média 750)
        df, metrics = self.pbf.process_data(
            file_path=self.folha_transparencia_csv,
            municipios_ibge=["3204302"],
            modo_lgpd=True
        )

        self.assertEqual(len(df), 3)
        self.assertEqual(metrics["total_beneficiarios"], 3)
        self.assertEqual(metrics["valor_total_folha"], 2250.0)
        self.assertEqual(metrics["beneficio_medio"], 750.0)
        self.assertEqual(metrics["acima_600_total"], 2)  # 750 e 900

        # Verifica LGPD
        nis_col = [c for c in df.columns if "nis" in c.lower()][0]
        nome_col = [c for c in df.columns if "nome" in c.lower() and "favorecido" in c.lower()][0]
        self.assertIn("***", df[nis_col].iloc[0])
        self.assertIn(".", df[nome_col].iloc[0])

    def test_pbf_sibec_filters_and_metrics(self):
        info = self.pbf.inspect_file(self.folha_sibec_csv)
        self.assertEqual(info["total_lines_approx"], 4)

        # Filtra apenas Bloqueados
        df, metrics = self.pbf.process_data(
            file_path=self.folha_sibec_csv,
            filtro_situacao="bloqueados"
        )
        self.assertEqual(len(df), 1)
        self.assertEqual(metrics["total_beneficiarios"], 1)
        self.assertEqual(metrics["valor_total_folha"], 700.0)

    def test_pbf_formatting_and_translations(self):
        # Header formatting
        h_ami = self.pbf.format_column_header("COD_FAMILIAR", header_mode="amigavel")
        self.assertEqual(h_ami, "Código Familiar")

        h_tec_ami = self.pbf.format_column_header("COD_FAMILIAR", header_mode="tecnico_amigavel")
        self.assertEqual(h_tec_ami, "[COD_FAMILIAR] Código Familiar")

        h_tec = self.pbf.format_column_header("COD_FAMILIAR", header_mode="tecnico")
        self.assertEqual(h_tec, "COD_FAMILIAR")

        # Cell translations
        self.assertEqual(self.pbf.format_cell_value("MARCA_RF", "S"), "Sim")
        self.assertEqual(self.pbf.format_cell_value("MARCA_RF", "N"), "Não")
        self.assertEqual(self.pbf.format_cell_value("CATADOR_RECIC", "S"), "Sim")
        self.assertEqual(self.pbf.format_cell_value("TRABALHO_INF", "S"), "Sim")
        self.assertEqual(self.pbf.format_cell_value("TP_BENEF", "BRC"), "BRC - Renda de Cidadania")
        self.assertEqual(self.pbf.format_cell_value("TIPO_PGTO_PREVISTO", "4"), "Crédito Conta 1288 (Caixa Tem)")

    def test_real_sibec_file_if_available(self):
        real_sibec = "base/folhaBolsaFamilia_SIBEC/BEC.E2.BOD1.F03.C2610.P1466.A3200102.CSV"
        if not os.path.exists(real_sibec):
            return
        info = self.pbf.inspect_file(real_sibec)
        self.assertEqual(info["total_lines_approx"], 12201)
        self.assertEqual(len(info["municipalities"]), 1)
        self.assertEqual(info["municipalities"][0]["cd_ibge"], "3200102")

        df, metrics = self.pbf.process_data(
            file_path=real_sibec,
            granularidade="familia",
            modo_lgpd=True,
            header_mode="amigavel",
            limite_linhas=10
        )
        self.assertEqual(len(df), 10)
        self.assertEqual(metrics["total_beneficiarios"], 1982)
        self.assertAlmostEqual(metrics["valor_total_folha"], 1467625.0)
        self.assertEqual(metrics["bloqueados_total"], 34)
        self.assertIn("Código Familiar", df.columns)
        self.assertIn("Valor Total da Família (R$)", df.columns)

        # Teste 1: Filtro Situação Liberados NÃO traz bloqueados nem suspensos
        df_lib, m_lib = self.pbf.process_data(
            file_path=real_sibec,
            granularidade="familia",
            filtro_situacao="liberados"
        )
        self.assertEqual(m_lib["total_beneficiarios"], 1948)
        self.assertEqual(m_lib["bloqueados_total"], 0)

        # Teste 2: Filtro Situação Bloqueados traz apenas bloqueados
        df_bloq, m_bloq = self.pbf.process_data(
            file_path=real_sibec,
            granularidade="familia",
            filtro_situacao="bloqueados"
        )
        self.assertEqual(m_bloq["total_beneficiarios"], 29)

        # Teste 3: Filtro Situação Suspensos traz apenas suspensos
        df_susp, m_susp = self.pbf.process_data(
            file_path=real_sibec,
            granularidade="familia",
            filtro_situacao="suspensos"
        )
        self.assertEqual(m_susp["total_beneficiarios"], 5)
        # Verificação da soma exata das situações: 1948 + 29 + 5 = 1982
        self.assertEqual(m_lib["total_beneficiarios"] + m_bloq["total_beneficiarios"] + m_susp["total_beneficiarios"], 1982)

        # Teste 4: Filtros de Populações Tradicionais (GPTE)
        df_cat, m_cat = self.pbf.process_data(
            file_path=real_sibec,
            granularidade="familia",
            filtro_gpte="catador"
        )
        self.assertEqual(m_cat["total_beneficiarios"], 5)

        df_gpte, m_gpte = self.pbf.process_data(
            file_path=real_sibec,
            granularidade="familia",
            filtro_gpte="gpte_sim"
        )
        self.assertEqual(m_gpte["total_beneficiarios"], 13)

        df_nao_gpte, m_nao_gpte = self.pbf.process_data(
            file_path=real_sibec,
            granularidade="familia",
            filtro_gpte="nao_gpte"
        )
        self.assertEqual(m_nao_gpte["total_beneficiarios"], 1982 - 13)


if __name__ == "__main__":
    unittest.main()


