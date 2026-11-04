"""
Janela Principal da Aplicação AppLeituraCadastroUnico com CustomTkinter.
Estrutura em 4 passos (Stepper Wizard):
Passo 1: Carregar Arquivo (com popup modal bloqueador)
Passo 2: Aplicar Filtros (seleção múltipla de municípios, granularidade, perfil, LGPD)
Passo 3: Pré-visualizar Resultados & Estatísticas (métricas completas do universo filtrado)
Passo 4: Exportar Arquivo (resumo, controle do limite de 1.048.575 do Excel, .xlsx e .csv)
"""

import os
import threading
from typing import Optional, List, Dict, Any
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import pandas as pd

from src.core.dictionary_parser import DictionaryParser
from src.core.file_inspector import FileInspector
from src.core.data_engine import DataEngine
from src.core.exporter import DataExporter
from src.core.thematic_profiles import PROFILES
from src.ui.components.stat_card import StatCard
from src.ui.components.preview_table import PreviewTable
from src.ui.components.column_selector import ColumnSelectorDialog
from src.ui.components.progress_modal import ProgressModal
from src.ui.components.municipality_selector import MunicipalitySelectorDialog, EXCEL_MAX_ROWS


class MainWindow(ctk.CTk):
    """Janela principal do AppLeituraCadastroUnico com fluxo estruturado em 4 passos."""

    def __init__(self):
        super().__init__()

        self.title("AppLeituraCadastroUnico — Leitor e Tradutor do Cadastro Único (CECAD)")
        self.geometry("1180x840")
        self.minsize(1060, 740)

        # Configura tema inicial
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Inicializa o parser com o dicionário padrão embutido
        default_json = os.path.join(os.path.dirname(__file__), "..", "assets", "dicionario_padrao.json")
        default_xlsx = os.path.join(os.path.dirname(__file__), "..", "..", "base", "dicionariocecad_marc_pbf.xlsx")

        if os.path.exists(default_json):
            self.dict_parser = DictionaryParser(json_path=default_json)
        elif os.path.exists(default_xlsx):
            self.dict_parser = DictionaryParser(excel_path=default_xlsx)
        else:
            self.dict_parser = DictionaryParser()

        self.data_engine = DataEngine(self.dict_parser)
        self.inspector: Optional[FileInspector] = None

        # Estados da aplicação
        self.current_step = 1
        self.current_file_path: Optional[str] = None
        self.municipalities: List[Dict[str, Any]] = []
        self.selected_ibges: List[str] = []
        self.custom_columns: Optional[List[str]] = None
        self.current_df_preview: Optional[pd.DataFrame] = None
        self.current_metrics: Dict[str, Any] = {}
        self.preview_dirty: bool = True

        self._build_ui()
        self._go_to_step(1)

    def _build_ui(self):
        # 1. Header Superior
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(12, 6))

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="📋 AppLeituraCadastroUnico",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Leitura, Tradução Categórica e Exportação da Base CECAD / CadÚnico para Municípios",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w")

        header_controls = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_controls.pack(side="right")

        self.dict_btn = ctk.CTkButton(
            header_controls,
            text="📖 Dicionário",
            width=110,
            fg_color=("gray85", "gray25"),
            text_color=("gray20", "gray90"),
            hover_color=("gray75", "gray35"),
            command=self._on_manage_dictionary
        )
        self.dict_btn.pack(side="left", padx=6)

        self.theme_switch = ctk.CTkSwitch(
            header_controls,
            text="Modo Escuro",
            command=self._toggle_theme,
            onvalue="Dark",
            offvalue="Light"
        )
        self.theme_switch.select()
        self.theme_switch.pack(side="left", padx=6)

        # 2. Barra Superior de Passos (Stepper)
        self.stepper_frame = ctk.CTkFrame(self, corner_radius=10)
        self.stepper_frame.pack(fill="x", padx=20, pady=(6, 10))

        self.step_buttons: List[ctk.CTkButton] = []
        step_definitions = [
            ("1. Carregar Arquivo 📁", 1),
            ("2. Aplicar Filtros ⚙️", 2),
            ("3. Pré-visualizar & Resumo 👁️", 3),
            ("4. Exportar Dados 💾", 4)
        ]

        self.stepper_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for idx, (label, s_num) in enumerate(step_definitions):
            btn = ctk.CTkButton(
                self.stepper_frame,
                text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
                corner_radius=8,
                command=lambda n=s_num: self._on_step_button_clicked(n)
            )
            btn.grid(row=0, column=idx, padx=6, pady=6, sticky="ew")
            self.step_buttons.append(btn)

        # 3. Área Central dos Passos
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, padx=20, pady=4)

        # Cria frames para cada passo
        self.step1_frame = self._build_step1_ui()
        self.step2_frame = self._build_step2_ui()
        self.step3_frame = self._build_step3_ui()
        self.step4_frame = self._build_step4_ui()

    # ==========================================
    # PASSO 1: CARREGAR ARQUIVO
    # ==========================================
    def _build_step1_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

        # Cabeçalho da Etapa
        top_box = ctk.CTkFrame(frame, fg_color="transparent")
        top_box.pack(fill="x", padx=24, pady=(20, 10))

        ctk.CTkLabel(
            top_box,
            text="📁 Passo 1: Seleção da Base de Dados do CECAD",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_box,
            text="Selecione o arquivo baixado do MDS (em formato .zip ou .csv). O programa inspecionará os dados automaticamente.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", pady=(2, 0))

        # Painel de Seleção de Arquivo
        select_box = ctk.CTkFrame(frame, corner_radius=8)
        select_box.pack(fill="x", padx=24, pady=12)

        file_browse_row = ctk.CTkFrame(select_box, fg_color="transparent")
        file_browse_row.pack(fill="x", padx=16, pady=16)

        self.file_entry = ctk.CTkEntry(
            file_browse_row,
            placeholder_text="Clique em 'Procurar Arquivo...' ou cole o caminho da base CECAD (.zip ou .csv)...",
            font=ctk.CTkFont(size=12),
            height=36
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.browse_btn = ctk.CTkButton(
            file_browse_row,
            text="📁 Procurar Arquivo...",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=170,
            height=36,
            command=self._browse_file
        )
        self.browse_btn.pack(side="right")

        # Cartão de Informações e Metadados do Arquivo
        self.meta_card = ctk.CTkFrame(frame, corner_radius=8)
        self.meta_card.pack(fill="both", expand=True, padx=24, pady=(6, 16))

        self.meta_title = ctk.CTkLabel(
            self.meta_card,
            text="ℹ️ Estrutura e Metadados da Base",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.meta_title.pack(anchor="w", padx=18, pady=(16, 10))

        self.meta_info_box = ctk.CTkFrame(self.meta_card, fg_color="transparent")
        self.meta_info_box.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        self.badge_scope = ctk.CTkLabel(
            self.meta_info_box,
            text="• Escopo: Nenhum arquivo carregado",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.badge_scope.pack(fill="x", pady=4)

        self.badge_date = ctk.CTkLabel(
            self.meta_info_box,
            text="• Data de Referência: -",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.badge_date.pack(fill="x", pady=4)

        self.badge_count = ctk.CTkLabel(
            self.meta_info_box,
            text="• Total aproximado: -",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.badge_count.pack(fill="x", pady=4)

        self.badge_mun_count = ctk.CTkLabel(
            self.meta_info_box,
            text="• Municípios detectados: -",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.badge_mun_count.pack(fill="x", pady=4)

        # Rodapé de Navegação do Passo 1
        foot_box = ctk.CTkFrame(frame, fg_color="transparent")
        foot_box.pack(fill="x", padx=24, pady=(0, 16))

        self.step1_next_btn = ctk.CTkButton(
            foot_box,
            text="Avançar para Filtros ➔",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            height=36,
            width=180,
            state="disabled",
            command=lambda: self._go_to_step(2)
        )
        self.step1_next_btn.pack(side="right")

        return frame

    # ==========================================
    # PASSO 2: APLICAR FILTROS
    # ==========================================
    def _build_step2_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

        # Cabeçalho da Etapa
        top_box = ctk.CTkFrame(frame, fg_color="transparent")
        top_box.pack(fill="x", padx=24, pady=(16, 8))

        ctk.CTkLabel(
            top_box,
            text="⚙️ Passo 2: Aplicação de Filtros e Critérios de Análise",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_box,
            text="Configure o escopo territorial, o nível de agregação, o perfil de colunas e as regras de anonimização LGPD.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", pady=(2, 0))

        scrollable_content = ctk.CTkScrollableFrame(frame, corner_radius=8)
        scrollable_content.pack(fill="both", expand=True, padx=24, pady=8)

        # Seção 1: Município / Território
        mun_section = ctk.CTkFrame(scrollable_content, corner_radius=8)
        mun_section.pack(fill="x", pady=6)

        mun_header = ctk.CTkFrame(mun_section, fg_color="transparent")
        mun_header.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            mun_header,
            text="🏙️ Município / Território da Base",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        self.mun_select_btn = ctk.CTkButton(
            mun_header,
            text="Selecionar Municípios...",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=170,
            height=28,
            command=self._open_municipality_selector
        )
        self.mun_select_btn.pack(side="right")

        self.mun_status_label = ctk.CTkLabel(
            mun_section,
            text="Nenhum município selecionado",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
            anchor="w"
        )
        self.mun_status_label.pack(fill="x", padx=16, pady=(0, 12))

        # Seção 2: Nível de Análise e Cabeçalhos
        gran_section = ctk.CTkFrame(scrollable_content, corner_radius=8)
        gran_section.pack(fill="x", pady=6)

        gran_row = ctk.CTkFrame(gran_section, fg_color="transparent")
        gran_row.pack(fill="x", padx=16, pady=12)

        # Granularidade
        gran_box = ctk.CTkFrame(gran_row, fg_color="transparent")
        gran_box.pack(side="left", fill="x", expand=True, padx=(0, 12))

        ctk.CTkLabel(
            gran_box,
            text="Nível de Análise (Granularidade):",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 4))

        self.gran_segmented = ctk.CTkSegmentedButton(
            gran_box,
            values=["Pessoa (Original)", "Família (Apenas RF)"],
            command=self._on_filter_changed
        )
        self.gran_segmented.set("Pessoa (Original)")
        self.gran_segmented.pack(fill="x")

        # Cabeçalhos
        header_box = ctk.CTkFrame(gran_row, fg_color="transparent")
        header_box.pack(side="right", fill="x", expand=True)

        ctk.CTkLabel(
            header_box,
            text="Estilo do Cabeçalho das Colunas:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 4))

        self.header_segmented = ctk.CTkSegmentedButton(
            header_box,
            values=["Nomes Amigáveis", "[Código] + Nome", "Códigos Técnicos"],
            command=self._on_filter_changed
        )
        self.header_segmented.set("Nomes Amigáveis")
        self.header_segmented.pack(fill="x")

        # Seção 3: Perfis Temáticos e Filtros Rápidos
        filter_section = ctk.CTkFrame(scrollable_content, corner_radius=8)
        filter_section.pack(fill="x", pady=6)

        filter_row1 = ctk.CTkFrame(filter_section, fg_color="transparent")
        filter_row1.pack(fill="x", padx=16, pady=(12, 6))

        # Perfil de Colunas
        prof_box = ctk.CTkFrame(filter_row1, fg_color="transparent")
        prof_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(prof_box, text="Perfil de Colunas:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        profile_values = [
            "Completo (Todas as Colunas)",
            "Visão Geral & Cadastro",
            "Bolsa Família & Renda",
            "Habitação & Vulnerabilidade",
            "Pessoas, Educação & Trabalho",
            "Personalizado..."
        ]
        self.profile_combo = ctk.CTkComboBox(
            prof_box,
            values=profile_values,
            command=self._on_profile_changed,
            height=30
        )
        self.profile_combo.set("Completo (Todas as Colunas)")
        self.profile_combo.pack(fill="x", pady=(2, 0))

        # Bolsa Família
        pbf_box = ctk.CTkFrame(filter_row1, fg_color="transparent")
        pbf_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(pbf_box, text="Bolsa Família:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.pbf_combo = ctk.CTkComboBox(
            pbf_box,
            values=["Todos", "Apenas Beneficiários (Sim)", "Não Beneficiários (Não)"],
            command=self._on_filter_changed,
            height=30
        )
        self.pbf_combo.set("Todos")
        self.pbf_combo.pack(fill="x", pady=(2, 0))

        filter_row2 = ctk.CTkFrame(filter_section, fg_color="transparent")
        filter_row2.pack(fill="x", padx=16, pady=(6, 12))

        # Atualização Cadastral
        desat_box = ctk.CTkFrame(filter_row2, fg_color="transparent")
        desat_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(desat_box, text="Atualização Cadastral:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.desat_combo = ctk.CTkComboBox(
            desat_box,
            values=["Todos", "Desatualizados (> 2 anos)", "Atualizados (<= 2 anos)"],
            command=self._on_filter_changed,
            height=30
        )
        self.desat_combo.set("Todos")
        self.desat_combo.pack(fill="x", pady=(2, 0))

        # Faixa de Renda
        rfpc_box = ctk.CTkFrame(filter_row2, fg_color="transparent")
        rfpc_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(rfpc_box, text="Faixa de Renda Per Capita:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.rfpc_combo = ctk.CTkComboBox(
            rfpc_box,
            values=["Todas", "Extrema Pobreza", "Pobreza", "Baixa Renda", "Acima de 1/2 S.M."],
            command=self._on_filter_changed,
            height=30
        )
        self.rfpc_combo.set("Todas")
        self.rfpc_combo.pack(fill="x", pady=(2, 0))

        # Seção 4: Proteção de Dados LGPD
        lgpd_section = ctk.CTkFrame(scrollable_content, corner_radius=8)
        lgpd_section.pack(fill="x", pady=6)

        lgpd_box = ctk.CTkFrame(lgpd_section, fg_color="transparent")
        lgpd_box.pack(fill="x", padx=16, pady=12)

        self.lgpd_switch = ctk.CTkSwitch(
            lgpd_box,
            text="Ativar Modo LGPD (Proteção de Identidade e Endereço)",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_filter_changed
        )
        self.lgpd_switch.pack(anchor="w")

        ctk.CTkLabel(
            lgpd_box,
            text="🔒 Oculta CPF, NIS, nomes, endereço residencial completo (rua, número, complemento, CEP, bairro, telefones e conta de luz), CRAS de referência e dados da escola dos filhos. Apenas o município (código IBGE) permanece visível para permitir análises territoriais seguras.",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
            wraplength=980,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # Rodapé de Navegação do Passo 2
        foot_box = ctk.CTkFrame(frame, fg_color="transparent")
        foot_box.pack(fill="x", padx=24, pady=12)

        ctk.CTkButton(
            foot_box,
            text="⬅ Voltar para Arquivo",
            font=ctk.CTkFont(size=12),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            height=36,
            width=160,
            command=lambda: self._go_to_step(1)
        ).pack(side="left")

        ctk.CTkButton(
            foot_box,
            text="Avançar para Pré-visualização ➔",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            height=36,
            width=230,
            command=lambda: self._go_to_step(3)
        ).pack(side="right")

        return frame

    # ==========================================
    # PASSO 3: PRÉ-VISUALIZAR E ESTATÍSTICAS
    # ==========================================
    def _build_step3_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

        # Cabeçalho da Etapa
        top_box = ctk.CTkFrame(frame, fg_color="transparent")
        top_box.pack(fill="x", padx=20, pady=(12, 6))

        ctk.CTkLabel(
            top_box,
            text="👁️ Passo 3: Pré-visualização e Estatísticas da População Filtrada",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            top_box,
            text="🔄 Recalcular Prévia",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=140,
            height=28,
            command=self._load_preview_and_metrics
        ).pack(side="right")

        # Cartões de Estatísticas (Total Real Filtrado)
        stats_frame = ctk.CTkFrame(frame, fg_color="transparent")
        stats_frame.pack(fill="x", padx=16, pady=(4, 6))
        stats_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.card_pessoas = StatCard(stats_frame, title="Total de Pessoas", initial_value="-", subtitle="Universo filtrado", icon="👥")
        self.card_pessoas.grid(row=0, column=0, padx=4, sticky="ew")

        self.card_familias = StatCard(stats_frame, title="Total de Famílias", initial_value="-", subtitle="Famílias distintas", icon="🏠")
        self.card_familias.grid(row=0, column=1, padx=4, sticky="ew")

        self.card_pbf = StatCard(stats_frame, title="Bolsa Família", initial_value="-", subtitle="Taxa de cobertura", icon="💳")
        self.card_pbf.grid(row=0, column=2, padx=4, sticky="ew")

        self.card_desat = StatCard(stats_frame, title="Desatualizados", initial_value="-", subtitle="Mais de 24 meses", icon="⚠️")
        self.card_desat.grid(row=0, column=3, padx=4, sticky="ew")

        self.card_renda = StatCard(stats_frame, title="Renda Média", initial_value="-", subtitle="Per capita familiar", icon="💵")
        self.card_renda.grid(row=0, column=4, padx=4, sticky="ew")

        # Tabela de Amostra Traduzida
        preview_container = ctk.CTkFrame(frame, corner_radius=8)
        preview_container.pack(fill="both", expand=True, padx=20, pady=6)

        table_header = ctk.CTkFrame(preview_container, fg_color="transparent")
        table_header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            table_header,
            text="Amostra dos Dados Traduzidos (Primeiras 30 linhas):",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")

        self.preview_table = PreviewTable(preview_container)
        self.preview_table.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Rodapé de Navegação do Passo 3
        foot_box = ctk.CTkFrame(frame, fg_color="transparent")
        foot_box.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            foot_box,
            text="⬅ Voltar para Filtros",
            font=ctk.CTkFont(size=12),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            height=36,
            width=160,
            command=lambda: self._go_to_step(2)
        ).pack(side="left")

        ctk.CTkButton(
            foot_box,
            text="Avançar para Exportação ➔",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            height=36,
            width=220,
            command=lambda: self._go_to_step(4)
        ).pack(side="right")

        return frame

    # ==========================================
    # PASSO 4: EXPORTAR ARQUIVO
    # ==========================================
    def _build_step4_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

        # Cabeçalho da Etapa
        top_box = ctk.CTkFrame(frame, fg_color="transparent")
        top_box.pack(fill="x", padx=24, pady=(16, 8))

        ctk.CTkLabel(
            top_box,
            text="💾 Passo 4: Exportação da Base Traduzida",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_box,
            text="Revise as especificações do arquivo gerado e inicie o salvamento em planilha Excel ou arquivo CSV.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", pady=(2, 0))

        content_box = ctk.CTkFrame(frame, corner_radius=8)
        content_box.pack(fill="both", expand=True, padx=24, pady=8)

        # Resumo da Exportação
        ctk.CTkLabel(
            content_box,
            text="📋 Resumo da Seleção Final",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=20, pady=(16, 8))

        self.export_summary_text = ctk.CTkLabel(
            content_box,
            text="Carregando resumo...",
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left"
        )
        self.export_summary_text.pack(fill="x", padx=20, pady=(0, 12))

        # Alerta do Limite de Linhas do Excel
        self.excel_alert_box = ctk.CTkFrame(content_box, corner_radius=8)
        self.excel_alert_box.pack(fill="x", padx=20, pady=8)

        self.excel_alert_label = ctk.CTkLabel(
            self.excel_alert_box,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=960,
            justify="left"
        )
        self.excel_alert_label.pack(fill="x", padx=16, pady=12)

        # Botões de Exportação
        export_actions = ctk.CTkFrame(content_box, fg_color="transparent")
        export_actions.pack(fill="x", padx=20, pady=16)

        self.btn_export_xlsx = ctk.CTkButton(
            export_actions,
            text="📊 Exportar Planilha Excel (.xlsx)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            height=44,
            command=lambda: self._start_export("xlsx")
        )
        self.btn_export_xlsx.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_export_csv = ctk.CTkButton(
            export_actions,
            text="📄 Exportar Arquivo CSV (.csv)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#047857",
            hover_color="#059669",
            height=44,
            command=lambda: self._start_export("csv")
        )
        self.btn_export_csv.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Rodapé de Navegação do Passo 4
        foot_box = ctk.CTkFrame(frame, fg_color="transparent")
        foot_box.pack(fill="x", padx=24, pady=12)

        ctk.CTkButton(
            foot_box,
            text="⬅ Voltar para Pré-visualização",
            font=ctk.CTkFont(size=12),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            height=36,
            width=200,
            command=lambda: self._go_to_step(3)
        ).pack(side="left")

        return frame

    # ==========================================
    # NAVEGAÇÃO ENTRE OS PASSOS
    # ==========================================
    def _go_to_step(self, step_number: int):
        # Validações de pré-requisitos para avançar
        if step_number > 1 and not self.current_file_path:
            messagebox.showwarning("Aviso", "Por favor, carregue um arquivo da base CECAD no Passo 1.")
            return

        if step_number > 2 and not self.selected_ibges:
            messagebox.showwarning("Aviso", "Selecione ao menos um município no Passo 2.")
            return

        self.current_step = step_number

        # Atualiza visual dos botões do Stepper
        for idx, btn in enumerate(self.step_buttons):
            s_num = idx + 1
            if s_num == step_number:
                btn.configure(
                    fg_color="#1E3A8A",
                    hover_color="#1D4ED8",
                    text_color="#FFFFFF"
                )
            elif s_num < step_number:
                btn.configure(
                    fg_color=("gray80", "gray25"),
                    hover_color=("gray70", "gray35"),
                    text_color=("#1E3A8A", "#60A5FA")
                )
            else:
                btn.configure(
                    fg_color=("gray85", "gray20"),
                    hover_color=("gray75", "gray25"),
                    text_color=("gray50", "gray50")
                )

        # Oculta todos os frames de passos
        self.step1_frame.pack_forget()
        self.step2_frame.pack_forget()
        self.step3_frame.pack_forget()
        self.step4_frame.pack_forget()

        # Exibe o frame ativo
        if step_number == 1:
            self.step1_frame.pack(fill="both", expand=True)
        elif step_number == 2:
            self.step2_frame.pack(fill="both", expand=True)
        elif step_number == 3:
            self.step3_frame.pack(fill="both", expand=True)
            if self.preview_dirty:
                self._load_preview_and_metrics()
        elif step_number == 4:
            self._update_step4_summary()
            self.step4_frame.pack(fill="both", expand=True)

    def _on_step_button_clicked(self, step_number: int):
        self._go_to_step(step_number)

    def _on_filter_changed(self, *args):
        self.preview_dirty = True

    # ==========================================
    # LÓGICA DO PASSO 1: INSPEÇÃO E CARREGAMENTO
    # ==========================================
    def _browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Selecione a Base de Dados do CECAD",
            filetypes=[("Bases do CECAD (*.zip, *.csv)", "*.zip;*.csv"), ("Todos os Arquivos", "*.*")]
        )
        if not file_path:
            return

        self.current_file_path = file_path
        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, file_path)
        self.preview_dirty = True

        # Abre modal bloqueador de progresso durante o carregamento
        modal = ProgressModal(
            self,
            title="Carregando Base CECAD",
            message="Inspecionando estrutura, cabeçalho e municípios...",
            indeterminate=False
        )

        threading.Thread(target=self._inspect_file_worker, args=(modal,), daemon=True).start()

    def _inspect_file_worker(self, modal: ProgressModal):
        try:
            self.inspector = FileInspector(self.current_file_path)

            modal.update_progress(0.3, "Escaneando municípios e totalizadores de registros...")
            is_single, mun_list = self.inspector.scan_municipalities()
            self.municipalities = mun_list

            # Seleciona município padrão inicial
            if mun_list:
                self.selected_ibges = [str(mun_list[0]["cd_ibge"]).strip()]
            else:
                self.selected_ibges = []

            date_info = self.inspector.date_info

            def on_success():
                modal.close()

                # Atualiza Badges no Passo 1
                if is_single:
                    mun_name = mun_list[0]["nome"] if mun_list else "Municipal"
                    self.badge_scope.configure(text=f"• Escopo: Base Municipal ({mun_name})")
                else:
                    self.badge_scope.configure(text=f"• Escopo: Base Estadual ({len(mun_list)} Municípios)")

                ref_desc = date_info.get("descricao") or "Não identificada no nome do arquivo"
                self.badge_date.configure(text=f"• Data de Referência: {ref_desc}")

                total_lines = self.inspector.total_lines_approx
                self.badge_count.configure(text=f"• Total aproximado: {total_lines:,} registros brutos".replace(",", "."))
                self.badge_mun_count.configure(text=f"• Municípios detectados: {len(mun_list)} municípios na base")

                self.step1_next_btn.configure(state="normal")
                self._update_municipality_status()

                # Avança automaticamente para o Passo 2 após inspecionar com sucesso
                self._go_to_step(2)

            self.after(0, on_success)

        except Exception as e:
            self.after(0, lambda: modal.close())
            self.after(0, lambda: messagebox.showerror("Erro ao ler arquivo", str(e)))

    # ==========================================
    # LÓGICA DO PASSO 2: SELEÇÃO DE MUNICÍPIOS E PERFIS
    # ==========================================
    def _open_municipality_selector(self):
        if not self.municipalities:
            messagebox.showwarning("Aviso", "Carregue um arquivo no Passo 1 antes de selecionar municípios.")
            return

        def on_confirm(selected):
            self.selected_ibges = selected
            self.preview_dirty = True
            self._update_municipality_status()

        MunicipalitySelectorDialog(self, self.municipalities, self.selected_ibges, on_confirm)

    def _update_municipality_status(self):
        if not self.selected_ibges:
            self.mun_status_label.configure(text="⚠️ Nenhum município selecionado.", text_color="#DC2626")
            return

        counts_map = {str(m["cd_ibge"]).strip(): (m.get("nome", ""), m.get("contagem", 0)) for m in self.municipalities}
        total_est = sum(counts_map.get(ibge, ("", 0))[1] for ibge in self.selected_ibges)

        if len(self.selected_ibges) == 1:
            ibge = self.selected_ibges[0]
            name, cnt = counts_map.get(ibge, (ibge, total_est))
            desc = f"1 município selecionado: {ibge} - {name} ({cnt:,} registros)".replace(",", ".")
        else:
            first_few = [counts_map.get(i, (i, 0))[0] for i in self.selected_ibges[:3]]
            more = f" e mais {len(self.selected_ibges) - 3}..." if len(self.selected_ibges) > 3 else ""
            desc = f"{len(self.selected_ibges)} municípios selecionados: {', '.join(first_few)}{more} — Total estimado: {total_est:,} registros".replace(",", ".")

        self.mun_status_label.configure(text=desc, text_color=("gray30", "gray80"))

    def _on_profile_changed(self, choice):
        self.preview_dirty = True
        if choice == "Personalizado...":
            if not self.inspector or not self.inspector.columns:
                messagebox.showwarning("Aviso", "Carregue um arquivo antes de selecionar colunas personalizadas.")
                self.profile_combo.set("Completo (Todas as Colunas)")
                return

            def on_save_cols(selected):
                self.custom_columns = selected
                self.preview_dirty = True

            current_sel = self.custom_columns if self.custom_columns else self.inspector.columns
            ColumnSelectorDialog(self, self.inspector.columns, current_sel, self.dict_parser, on_save_cols)
        else:
            self.custom_columns = None

    # ==========================================
    # LÓGICA DO PASSO 3: PRÉVIA E MÉTRICAS
    # ==========================================
    def _load_preview_and_metrics(self):
        if not self.current_file_path or not self.selected_ibges:
            return

        modal = ProgressModal(
            self,
            title="Processando Base de Dados",
            message="Filtrando registros e calculando métricas do universo completo...",
            indeterminate=False
        )

        threading.Thread(target=self._preview_worker, args=(modal,), daemon=True).start()

    def _preview_worker(self, modal: ProgressModal):
        try:
            params = self._gather_engine_params()
            params["limite_linhas"] = 30  # Amostra de visualização rápida para a tabela

            def progress_hook(pct, msg):
                modal.update_progress(pct, msg)

            params["progress_callback"] = progress_hook
            df_sample, metrics = self.data_engine.process_data(**params)

            self.current_df_preview = df_sample
            self.current_metrics = metrics
            self.preview_dirty = False

            def update_ui():
                modal.close()
                self.preview_table.load_dataframe(df_sample)
                self._update_stat_cards(metrics)

            self.after(0, update_ui)

        except Exception as e:
            self.after(0, lambda: modal.close())
            self.after(0, lambda: messagebox.showerror("Erro na pré-visualização", str(e)))

    def _update_stat_cards(self, metrics: Dict[str, Any]):
        tot_pes = metrics.get("total_pessoas", 0)
        tot_fam = metrics.get("total_familias", 0)
        pbf_pct = metrics.get("pbf_percentual", 0.0)
        pbf_tot = metrics.get("pbf_beneficiarios", 0)
        desat_pct = metrics.get("desatualizados_percentual", 0.0)
        desat_tot = metrics.get("desatualizados_total", 0)
        renda = metrics.get("renda_media_rfpc", 0.0)

        self.card_pessoas.update_value(f"{tot_pes:,}".replace(",", "."), "Total filtrado")
        self.card_familias.update_value(f"{tot_fam:,}".replace(",", "."), "Famílias distintas")
        self.card_pbf.update_value(f"{pbf_pct:.1f}%", f"{pbf_tot:,} beneficiários".replace(",", "."))
        self.card_desat.update_value(f"{desat_pct:.1f}%", f"{desat_tot:,} desatualizados".replace(",", "."))
        self.card_renda.update_value(f"R$ {renda:.2f}".replace(".", ","), "Média per capita")

    # ==========================================
    # LÓGICA DO PASSO 4: EXPORTAÇÃO
    # ==========================================
    def _update_step4_summary(self):
        tot_pes = self.current_metrics.get("total_pessoas", 0)
        gran = self.gran_segmented.get()
        lgpd_on = bool(self.lgpd_switch.get())
        prof = self.profile_combo.get()

        counts_map = {str(m["cd_ibge"]).strip(): m.get("nome", "") for m in self.municipalities}
        if len(self.selected_ibges) == 1:
            ibge = self.selected_ibges[0]
            mun_str = f"{ibge} - {counts_map.get(ibge, '')}"
        else:
            mun_str = f"{len(self.selected_ibges)} municípios selecionados"

        summary = (
            f"• Arquivo Fonte: {os.path.basename(self.current_file_path or '')}\n"
            f"• Municípios: {mun_str}\n"
            f"• Nível de Análise: {gran}\n"
            f"• Perfil de Colunas: {prof}\n"
            f"• Modo LGPD: {'ATIVADO (Identidades e Endereços Ocultados)' if lgpd_on else 'Desativado'}\n"
            f"• Total de Registros Filtrados: {tot_pes:,} registros".replace(",", ".")
        )
        self.export_summary_text.configure(text=summary)

        # Validação do Limite do Excel
        if tot_pes > EXCEL_MAX_ROWS:
            self.excel_alert_box.configure(fg_color=("#FEE2E2", "#450A0A"))
            self.excel_alert_label.configure(
                text=f"⚠️ Atenção: O total de {tot_pes:,} registros excede a capacidade de 1.048.575 linhas do Excel!\n"
                     "Ao exportar para Excel (.xlsx), o arquivo será dividido automaticamente em abas ('Parte 1', 'Parte 2'...). "
                     "Para arquivos unificados com mais de 1 milhão de linhas, recomendamos fortemente a exportação em CSV (.csv).".replace(",", "."),
                text_color=("#991B1B", "#FCA5A5")
            )
        else:
            self.excel_alert_box.configure(fg_color=("#DCFCE7", "#052E16"))
            self.excel_alert_label.configure(
                text=f"✅ Volume compatível: {tot_pes:,} registros (dentro do limite de 1.048.575 linhas do Excel).".replace(",", "."),
                text_color=("#166534", "#86EFAC")
            )

    def _start_export(self, format_type: str):
        if not self.current_file_path or not self.selected_ibges:
            messagebox.showwarning("Aviso", "Selecione o arquivo e os municípios antes de exportar.")
            return

        mun_tag = f"mun_{self.selected_ibges[0]}" if len(self.selected_ibges) == 1 else f"{len(self.selected_ibges)}_municipios"
        def_filename = f"cecad_traduzido_{mun_tag}.{format_type}"

        if format_type == "xlsx":
            output_path = filedialog.asksaveasfilename(
                title="Salvar Planilha Excel",
                defaultextension=".xlsx",
                initialfile=def_filename,
                filetypes=[("Planilha Excel (*.xlsx)", "*.xlsx")]
            )
        else:
            output_path = filedialog.asksaveasfilename(
                title="Salvar Arquivo CSV",
                defaultextension=".csv",
                initialfile=def_filename,
                filetypes=[("Arquivo CSV (*.csv)", "*.csv")]
            )

        if not output_path:
            return

        modal = ProgressModal(
            self,
            title=f"Exportando para {format_type.upper()}",
            message="Processando registros e gravando o arquivo...",
            indeterminate=False
        )

        threading.Thread(target=self._export_worker, args=(format_type, output_path, modal), daemon=True).start()

    def _export_worker(self, format_type: str, output_path: str, modal: ProgressModal):
        try:
            params = self._gather_engine_params()

            def progress_hook(pct, msg):
                modal.update_progress(pct, msg)

            params["progress_callback"] = progress_hook
            df_full, metrics = self.data_engine.process_data(**params)

            if df_full.empty:
                self.after(0, lambda: modal.close())
                self.after(0, lambda: messagebox.showwarning("Aviso", "Nenhum registro encontrado para os filtros selecionados."))
                return

            if format_type == "xlsx":
                DataExporter.export_to_excel(df_full, output_path, progress_callback=progress_hook)
            else:
                DataExporter.export_to_csv(df_full, output_path, progress_callback=progress_hook)

            def on_complete():
                modal.close()
                messagebox.showinfo(
                    "Exportação Concluída com Sucesso",
                    f"Arquivo salvo com sucesso!\n\n"
                    f"Total de Registros: {len(df_full):,}\n"
                    f"Local: {output_path}".replace(",", ".")
                )

            self.after(0, on_complete)

        except Exception as e:
            self.after(0, lambda: modal.close())
            self.after(0, lambda: messagebox.showerror("Erro na exportação", str(e)))

    # ==========================================
    # AUXILIARES E PARÂMETROS DO MOTOR
    # ==========================================
    def _gather_engine_params(self) -> Dict[str, Any]:
        gran_choice = self.gran_segmented.get()
        granularidade = "familia" if "Família" in gran_choice else "pessoa"

        header_choice = self.header_segmented.get()
        if "Nomes Amigáveis" in header_choice:
            header_mode = "amigavel"
        elif "[Código]" in header_choice:
            header_mode = "tecnico_amigavel"
        else:
            header_mode = "tecnico"

        prof_choice = self.profile_combo.get()
        prof_map = {
            "Completo (Todas as Colunas)": "completo",
            "Visão Geral & Cadastro": "geral",
            "Bolsa Família & Renda": "bolsa_familia",
            "Habitação & Vulnerabilidade": "habitacao",
            "Pessoas, Educação & Trabalho": "pessoas_trabalho"
        }
        perfil_key = prof_map.get(prof_choice, "completo")

        pbf_choice = self.pbf_combo.get()
        filtro_pbf = "sim" if "Beneficiários (Sim)" in pbf_choice else ("nao" if "Não Beneficiários" in pbf_choice else "todos")

        desat_choice = self.desat_combo.get()
        filtro_desat = "desatualizados" if "Desatualizados" in desat_choice else ("atualizados" if "Atualizados" in desat_choice else "todos")

        rfpc_choice = self.rfpc_combo.get()
        rfpc_map = {
            "Todas": "todas",
            "Extrema Pobreza": "extrema_pobreza",
            "Pobreza": "pobreza",
            "Baixa Renda": "baixa_renda",
            "Acima de 1/2 S.M.": "acima_meio_sm"
        }
        filtro_renda = rfpc_map.get(rfpc_choice, "todas")

        return {
            "file_path": self.current_file_path,
            "municipios_ibge": self.selected_ibges,
            "granularidade": granularidade,
            "perfil_colunas": perfil_key,
            "colunas_customizadas": self.custom_columns,
            "filtro_pbf": filtro_pbf,
            "filtro_atualizacao": filtro_desat,
            "filtro_renda": filtro_renda,
            "modo_lgpd": bool(self.lgpd_switch.get()),
            "header_mode": header_mode
        }

    def _toggle_theme(self):
        mode = self.theme_switch.get()
        ctk.set_appearance_mode(mode)
        if hasattr(self, "preview_table"):
            self.preview_table._setup_style()

    def _on_manage_dictionary(self):
        opt = messagebox.askyesno(
            "Gerenciador de Dicionário",
            f"Dicionário atual: {len(self.dict_parser.fields)} campos cadastrados.\n\n"
            "Deseja carregar um novo arquivo Excel (.xlsx) de Dicionário de Dados do MDS?"
        )
        if opt:
            path = filedialog.askopenfilename(
                title="Selecione o Dicionário do CECAD",
                filetypes=[("Planilhas Excel", "*.xlsx")]
            )
            if path:
                try:
                    self.dict_parser.load_from_excel(path)
                    messagebox.showinfo(
                        "Dicionário Carregado",
                        f"Sucesso! {len(self.dict_parser.fields)} campos carregados do novo dicionário."
                    )
                    self.preview_dirty = True
                except Exception as e:
                    messagebox.showerror("Erro ao carregar dicionário", str(e))
