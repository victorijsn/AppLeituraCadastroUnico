import os
import unittest
import pandas as pd
import openpyxl
from src.core.exporter import DataExporter, is_text_column

class TestExporter(unittest.TestCase):
    def setUp(self):
        self.output_xlsx = "tests/test_out.xlsx"
        self.output_csv = "tests/test_out.csv"
        self.df = pd.DataFrame({
            "Código IBGE": ["0012345", "3204302"],
            "Número NIS": ["00016320603", "01234567890"],
            "CPF do Responsável": ["00123456789", "09876543210"],
            "Nome da Pessoa": ["Maria da Silva", "João Pereira"],
            "Bolsa Família": ["Sim", "Não"],
            "Renda Média Familiar": [150.50, 450.00]
        })

    def tearDown(self):
        for f in [self.output_xlsx, self.output_csv]:
            if os.path.exists(f):
                os.remove(f)

    def test_is_text_column(self):
        self.assertTrue(is_text_column("Código IBGE"))
        self.assertTrue(is_text_column("Número NIS"))
        self.assertTrue(is_text_column("CPF da Pessoa"))
        self.assertFalse(is_text_column("Renda Média"))

    def test_export_to_excel(self):
        DataExporter.export_to_excel(self.df, self.output_xlsx)
        self.assertTrue(os.path.exists(self.output_xlsx))

        # Read back with openpyxl to verify cell types and leading zeros
        wb = openpyxl.load_workbook(self.output_xlsx)
        ws = wb.active
        # Check header
        self.assertEqual(ws.cell(row=1, column=1).value, "Código IBGE")
        # Check leading zero cell
        val = ws.cell(row=2, column=1).value
        self.assertEqual(val, "0012345")
        nis_val = ws.cell(row=2, column=2).value
        self.assertEqual(nis_val, "00016320603")

    def test_export_to_csv(self):
        DataExporter.export_to_csv(self.df, self.output_csv)
        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, "rb") as f:
            raw = f.read()
            # UTF-8 BOM is b'\xef\xbb\xbf'
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        text = raw.decode("utf-8-sig")
        self.assertIn("Código IBGE;Número NIS;CPF do Responsável", text)
        self.assertIn("0012345;00016320603;00123456789", text)

if __name__ == '__main__':
    unittest.main()
