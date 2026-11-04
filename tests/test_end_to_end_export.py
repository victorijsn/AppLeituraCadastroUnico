import os
import unittest
import pandas as pd
import openpyxl
from src.core.dictionary_parser import DictionaryParser
from src.core.data_engine import DataEngine
from src.core.exporter import DataExporter

class TestEndToEndExport(unittest.TestCase):
    def setUp(self):
        self.dict_parser = DictionaryParser(json_path="src/assets/dicionario_padrao.json")
        self.data_engine = DataEngine(self.dict_parser)
        self.zip_path = "base/cecad/tab_cad_07082026_32_20260911.zip"
        if not os.path.exists(self.zip_path):
            self.zip_path = "base/tab_cad_07082026_32_20260911.zip"
        self.out_xlsx = "tests/e2e_kennedy.xlsx"
        self.out_csv = "tests/e2e_kennedy.csv"

    def tearDown(self):
        for f in [self.out_xlsx, self.out_csv]:
            if os.path.exists(f):
                os.remove(f)

    def test_full_pipeline(self):
        # 1. Process data for Presidente Kennedy (3204302)
        df, metrics = self.data_engine.process_data(
            file_path=self.zip_path,
            municipio_ibge="3204302",
            perfil_colunas="bolsa_familia",
            header_mode="amigavel",
            limite_linhas=100
        )
        self.assertEqual(len(df), 100)
        self.assertGreater(metrics["total_familias"], 0)

        # 2. Export to Excel
        DataExporter.export_to_excel(df, self.out_xlsx)
        self.assertTrue(os.path.exists(self.out_xlsx))

        # Check excel validity
        wb = openpyxl.load_workbook(self.out_xlsx)
        ws = wb.active
        self.assertEqual(ws.max_row, 101)  # 1 header + 100 rows
        # Check cell format for NIS (text preservation)
        nis_col_idx = None
        for col_idx in range(1, ws.max_column + 1):
            if "nis" in str(ws.cell(row=1, column=col_idx).value).lower():
                nis_col_idx = col_idx
                break
        if nis_col_idx:
            val = str(ws.cell(row=2, column=nis_col_idx).value)
            self.assertEqual(len(val), 11)

        # 3. Export to CSV
        DataExporter.export_to_csv(df, self.out_csv)
        self.assertTrue(os.path.exists(self.out_csv))
        with open(self.out_csv, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 101)
            self.assertIn(";", lines[0])

if __name__ == '__main__':
    unittest.main()
