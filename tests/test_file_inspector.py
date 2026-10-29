import unittest
from src.core.file_inspector import FileInspector, parse_reference_date, get_municipio_nome

class TestFileInspector(unittest.TestCase):
    def test_parse_reference_date(self):
        info = parse_reference_date("tab_cad_07082026_32_20260911.zip")
        self.assertEqual(info["base_mes_ano"], "08/2026")
        self.assertEqual(info["extracao_data"], "11/09/2026")

    def test_get_municipio_nome(self):
        # 3205309 is Vitoria - ES
        nome = get_municipio_nome("3205309")
        self.assertIn("Vitória", nome)
        self.assertIn("ES", nome)

        # 3204302 is Presidente Kennedy - ES
        nome_pk = get_municipio_nome("3204302")
        self.assertIn("Presidente Kennedy", nome_pk)

    def test_inspect_zip_header(self):
        inspector = FileInspector("base/tab_cad_07082026_32_20260911.zip")
        self.assertTrue(inspector.is_zip)
        self.assertEqual(inspector.delimiter, ";")
        self.assertGreater(len(inspector.columns), 150)
        self.assertIn("d.cd_ibge", inspector.columns)
        self.assertEqual(inspector.ibge_col_index, 0)

    def test_scan_municipalities_partial(self):
        inspector = FileInspector("base/tab_cad_07082026_32_20260911.zip")
        # Scan first 5000 lines for fast unit test
        is_single, mun_list = inspector.scan_municipalities(max_lines=5000)
        self.assertFalse(is_single)
        self.assertGreater(len(mun_list), 0)
        self.assertTrue(all("cd_ibge" in m for m in mun_list))

if __name__ == '__main__':
    unittest.main()
