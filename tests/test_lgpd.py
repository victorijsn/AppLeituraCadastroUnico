import unittest
from src.core.lgpd import apply_lgpd_mask, mask_cpf, mask_nis, mask_name

class TestLgpdModule(unittest.TestCase):
    def test_cpf_nis_name_masking(self):
        self.assertEqual(mask_cpf("12345678901"), "***.***.789-**")
        self.assertEqual(mask_nis("12345678901"), "***.*****.90-*")
        self.assertEqual(mask_name("Maria Jose da Silva"), "M. J. da S.")

    def test_apply_lgpd_mask_address(self):
        self.assertEqual(apply_lgpd_mask("d.nom_logradouro_fam", "Avenida Central"), "[OCULTO - LGPD]")
        self.assertEqual(apply_lgpd_mask("num_logradouro_fam", "123"), "[OCULTO - LGPD]")
        self.assertEqual(apply_lgpd_mask("d.nom_localidade_fam", "Bairro das Flores"), "[OCULTO - LGPD]")
        self.assertEqual(apply_lgpd_mask("num_cep_logradouro_fam", "29000000"), "*****--***")
        self.assertEqual(apply_lgpd_mask("d.txt_referencia_local_fam", "Perto da padaria"), "[OCULTO - LGPD]")
        self.assertEqual(apply_lgpd_mask("num_tel_contato_1_fam", "999998888"), "[OCULTO - LGPD]")

    def test_apply_lgpd_mask_cras_and_school(self):
        self.assertEqual(apply_lgpd_mask("d.nom_centro_assist_fam", "CRAS Centro"), "[OCULTO - LGPD]")
        self.assertEqual(apply_lgpd_mask("nom_unidade_territorial_fam", "Território 1"), "[OCULTO - LGPD]")
        self.assertEqual(apply_lgpd_mask("p.nom_escola_memb", "Escola Municipal"), "[OCULTO - LGPD]")
        self.assertEqual(apply_lgpd_mask("cod_censo_inep_memb", "12345678"), "[OCULTO - LGPD]")

    def test_apply_lgpd_mask_preserves_municipio(self):
        # O código do município cd_ibge deve permanecer intacto para agregações territoriais
        self.assertEqual(apply_lgpd_mask("cd_ibge", "3205309"), "3205309")
        self.assertEqual(apply_lgpd_mask("d.cd_ibge", "3205309"), "3205309")

if __name__ == "__main__":
    unittest.main()
