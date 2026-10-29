import os
import unittest
from src.core.dictionary_parser import DictionaryParser, parse_resposta, normalize_col_name

class TestDictionaryParser(unittest.TestCase):
    def setUp(self):
        self.excel_path = "base/dicionariocecad_marc_pbf.xlsx"
        self.parser = DictionaryParser(excel_path=self.excel_path)

    def test_parse_resposta_hash(self):
        resp = "2 - Sem Registro Civil#3 - Cadastrado"
        mapping = parse_resposta(resp)
        self.assertEqual(mapping.get("2"), "Sem Registro Civil")
        self.assertEqual(mapping.get("3"), "Cadastrado")

    def test_parse_resposta_newline(self):
        resp = "1 - Feminina\n2 - Masculina\n3 – Não binário/a"
        mapping = parse_resposta(resp)
        self.assertEqual(mapping.get("1"), "Feminina")
        self.assertEqual(mapping.get("2"), "Masculina")
        self.assertIn("Não binário", mapping.get("3", ""))

    def test_load_excel_counts(self):
        self.assertGreater(len(self.parser.fields), 200)
        desc, mapping = self.parser.get_field_info("d.cod_est_cadastral_fam")
        self.assertEqual(mapping.get("3"), "Cadastrado")
        self.assertEqual(desc, "Estado cadastral da familia")

    def test_translation_normalization(self):
        # should work without d. prefix
        desc, mapping = self.parser.get_field_info("cod_est_cadastral_fam")
        self.assertEqual(mapping.get("3"), "Cadastrado")
        self.assertEqual(self.parser.translate_value("cod_est_cadastral_fam", "3"), "Cadastrado")
        self.assertEqual(self.parser.translate_value("d.cod_est_cadastral_fam", 3), "Cadastrado")

    def test_save_and_load_json(self):
        json_path = "src/assets/dicionario_padrao.json"
        self.parser.save_to_json(json_path)
        self.assertTrue(os.path.exists(json_path))

        parser_json = DictionaryParser(json_path=json_path)
        self.assertEqual(len(parser_json.fields), len(self.parser.fields))
        self.assertEqual(parser_json.translate_value("d.marc_pbf", "1"), "Sim")

if __name__ == '__main__':
    unittest.main()
