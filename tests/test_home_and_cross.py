import os
import unittest
from src.ui.main_window import MainWindow
from src.ui.components.cross_module_dialog import CrossModuleDialog


class TestHomeAndCrossModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = MainWindow()
        cls.cecad_zip = "base/cecad/tab_cad_07082026_32_20260911.zip"
        if not os.path.exists(cls.cecad_zip):
            cls.cecad_zip = "base/tab_cad_07082026_32_20260911.zip"
        cls.sibec_csv = "base/folhaBolsaFamilia_SIBEC/BEC.E2.BOD1.F03.C2610.P1466.A3200102.CSV"

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_home_initialization_and_navigation(self):
        # 1. Deve iniciar na Tela Inicial (Passo 0)
        self.assertEqual(self.app.current_step, 0)
        self.assertEqual(self.app.stepper_frame.winfo_manager(), "")

        # 2. Ao clicar no módulo CECAD, vai para o Passo 1
        self.app._open_module("cecad")
        self.assertEqual(self.app.current_step, 1)
        self.assertEqual(self.app.current_adapter.adapter_id, "cecad")
        self.assertEqual(self.app.stepper_frame.winfo_manager(), "pack")

        # 3. Ao voltar para a tela inicial
        self.app._go_to_home()
        self.assertEqual(self.app.current_step, 0)
        self.assertEqual(self.app.stepper_frame.winfo_manager(), "")

        # 4. Ao clicar no módulo Folha SIBEC
        self.app._open_module("bolsa_familia_folha")
        self.assertEqual(self.app.current_step, 1)
        self.assertEqual(self.app.current_adapter.adapter_id, "bolsa_familia_folha")
        self.assertEqual(self.app.stepper_frame.winfo_manager(), "pack")

        # Retorna para Home ao final do teste
        self.app._go_to_home()

    def test_cross_module_defasagem_audit(self):
        if not os.path.exists(self.cecad_zip) or not os.path.exists(self.sibec_csv):
            self.skipTest("Arquivos reais de teste não encontrados.")

        diag = CrossModuleDialog(self.app, default_cecad=self.cecad_zip, default_sibec=self.sibec_csv)
        title_text = diag.audit_title.cget("text")
        msg_text = diag.audit_msg.cget("text")

        # 1. Deve identificar os 2 meses exatos de defasagem (Agosto vs Outubro)
        self.assertIn("2 Meses", title_text)
        self.assertIn("08/2026", msg_text)
        self.assertIn("10/2026", msg_text)

        # 2. Deve auto-detectar o município de Afonso Cláudio (3200102) com nome amigável no ComboBox
        self.assertEqual(diag.selected_ibges, ["3200102"])
        self.assertEqual(diag.mun_entry.get().strip(), "3200102")
        self.assertIn("Afonso Cláudio", diag.mun_combo.get())
        self.assertIn("Afonso Cláudio", diag.mun_status_label.cget("text"))

        # 3. Executa o cruzamento para Afonso Cláudio e valida os 4 Quadrantes
        class DummyModal:
            def update_progress(self, pct, msg): pass
            def close(self): pass

        diag._run_cross_analysis_worker(DummyModal(), self.cecad_zip, self.sibec_csv, ["3200102"], "Afonso Cláudio")
        m = diag.cross_metrics

        self.assertEqual(m["mun_ibge"], "3200102")
        self.assertEqual(m["total_sibec"], 1982)
        self.assertEqual(m["q1"], 1903)  # Compatíveis & Regulares
        self.assertEqual(m["q2"], 45)    # Concessões Recentes Janela 2m
        self.assertEqual(m["q3"], 34)    # Bloqueados / Suspensos
        self.assertEqual(m["q4"], 175)   # Risco Suspensão (Desatualizados)

        # 4. Verifica coluna de Município nos dados gerados
        df_q1 = diag.cross_results["q1"]
        self.assertIn("Município", df_q1.columns)
        self.assertIn("Afonso Cláudio", df_q1["Município"].iloc[0])

        diag.destroy()

    def test_cross_module_municipality_selection_ui(self):
        diag = CrossModuleDialog(self.app)

        # 1. Deve carregar a lista de municípios (ex: 78 municípios do ES)
        self.assertGreaterEqual(len(diag.available_municipalities), 70)
        self.assertIn("Afonso Cláudio - ES", diag._nome_to_ibge)

        # 2. Seleção rápida por ComboBox
        diag.mun_combo.set("Afonso Cláudio - ES")
        diag._on_mun_combo_selected("Afonso Cláudio - ES")
        self.assertEqual(diag.selected_ibges, ["3200102"])
        self.assertIn("1 município selecionado", diag.mun_status_label.cget("text"))

        # 3. Seleção de múltiplos municípios
        diag.selected_ibges = ["3200102", "3200607"]  # Afonso Cláudio + Brejetuba
        diag._update_municipality_ui()

        self.assertEqual(len(diag.selected_ibges), 2)
        self.assertIn("(2 municípios selecionados)", diag.mun_combo.get())
        self.assertIn("2 municípios selecionados", diag.mun_status_label.cget("text"))

        diag.destroy()

    def test_cross_module_cecad_single_municipality_auto_select(self):
        # Simula parent com inspeção de CECAD de município único
        old_info = getattr(self.app, "inspector_info", None)
        self.app.inspector_info = {
            "is_single": True,
            "municipalities": [{"cd_ibge": "3200102", "nome": "Afonso Cláudio - ES", "contagem": 1982}]
        }
        self.app.municipalities = self.app.inspector_info["municipalities"]
        self.app.selected_ibges = ["3200102"]

        diag = CrossModuleDialog(self.app, default_cecad="tab_cad_fake_3200102.zip")
        self.assertEqual(diag.selected_ibges, ["3200102"])
        self.assertIn("Afonso Cláudio", diag.mun_combo.get())

        # Restaura estado
        self.app.inspector_info = old_info or {}
        self.app.municipalities = []
        self.app.selected_ibges = []
        diag.destroy()


if __name__ == "__main__":
    unittest.main()
