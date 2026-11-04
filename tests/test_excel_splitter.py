import os
import unittest
import pandas as pd
import openpyxl
from src.core.exporter import DataExporter


class TestExcelSplitter(unittest.TestCase):
    def setUp(self):
        self.output_xlsx = "tests/test_split_out.xlsx"
        # 12 linhas de dados
        self.df = pd.DataFrame({
            "Código IBGE": [f"3200{i:03d}" for i in range(12)],
            "Nome": [f"Pessoa {i}" for i in range(12)],
            "Renda": [100.0 * i for i in range(12)]
        })

    def tearDown(self):
        if os.path.exists(self.output_xlsx):
            os.remove(self.output_xlsx)

    def test_export_splits_into_multiple_sheets(self):
        # Limita a 5 linhas por aba -> deve gerar 3 abas (5 + 5 + 2)
        DataExporter.export_to_excel(
            self.df,
            self.output_xlsx,
            sheet_name="CadUnico",
            max_rows_per_sheet=5
        )

        self.assertTrue(os.path.exists(self.output_xlsx))
        wb = openpyxl.load_workbook(self.output_xlsx)
        sheet_names = wb.sheetnames

        self.assertEqual(len(sheet_names), 3)
        self.assertIn("CadUnico - Parte 1", sheet_names[0])
        self.assertIn("CadUnico - Parte 2", sheet_names[1])
        self.assertIn("CadUnico - Parte 3", sheet_names[2])

        # Verifica contagem de linhas em cada aba (1 linha de cabeçalho + dados)
        ws1 = wb[sheet_names[0]]
        self.assertEqual(ws1.max_row, 6)  # 1 header + 5 rows

        ws2 = wb[sheet_names[1]]
        self.assertEqual(ws2.max_row, 6)  # 1 header + 5 rows

        ws3 = wb[sheet_names[2]]
        self.assertEqual(ws3.max_row, 3)  # 1 header + 2 rows


if __name__ == "__main__":
    unittest.main()
