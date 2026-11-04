"""
Janela Principal da Aplicação AppLeituraCadastroUnico com CustomTkinter.
Estrutura modular multi-bases (CECAD e Folha do Bolsa Família) em 4 passos:
Passo 1: Carregar Arquivo (seletor de base CECAD ou Folha PBF + popup modal bloqueador)
Passo 2: Aplicar Filtros (específicos para cada base, multi-municípios, LGPD)
Passo 3: Pré-visualizar Resultados & Estatísticas (cartões adaptativos do universo filtrado)
Passo 4: Exportar Arquivo (resumo, controle do teto de 1.048.575 do Excel, .xlsx e .csv)
"""

import os
import threading
from typing import Optional, List, Dict, Any
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import pandas as pd

from src.core.dictionary_parser import DictionaryParser
from src.core.exporter import DataExporter
from src.core.adapters.base_adapter import BaseAdapter
from src.core.adapters.cecad_adapter import CecadAdapter
from src.core.adapters.bolsa_familia_adapter import BolsaFamiliaFolhaAdapter
from src.ui.components.stat_card import StatCard
from src.ui.components.preview_table import PreviewTable
from src.ui.components.column_selector import ColumnSelectorDialog
from src.ui.components.progress_modal import ProgressModal
from src.ui.components.municipality_selector import MunicipalitySelectorDialog, EXCEL_MAX_ROWS
from src.ui.components.cross_module_dialog import CrossModuleDialog


class MainWindow(ctk.CTk):
    """Janela principal com suporte multi-bases e fluxo estruturado em 4 passos."""

    def __init__(self):
        super().__init__()

        self.title("AppLeituraCadastroUnico — Central de Dados Sociais (CECAD & Folha Bolsa Família)")
        self.geometry("1180x850")
        self.minsize(1060, 750)

        # Configura tema inicial
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Inicializa o parser com o dicionário padrão embutido
        default_json = os.path.join(os.path.dirname(__file__), "..", "assets", "dicionario_padrao.json")
        default_xlsx = os.path.join(os.path.dirname(__file__), "..", "..", "base", "dicionariocecad_marc_pbf.xlsx")
        default_xlsx_cecad = os.path.join(os.path.dirname(__file__), "..", "..", "base", "cecad", "dicionariocecad_marc_pbf.xlsx")

        if os.path.exists(default_json):
            self.dict_parser = DictionaryParser(json_path=default_json)
        elif os.path.exists(default_xlsx):
            self.dict_parser = DictionaryParser(excel_path=default_xlsx)
        elif os.path.exists(default_xlsx_cecad):
            self.dict_parser = DictionaryParser(excel_path=default_xlsx_cecad)
        else:
            self.dict_parser = DictionaryParser()

        # Registro de Adaptadores Multi-Base
        self.cecad_adapter = CecadAdapter(self.dict_parser)
        self.pbf_adapter = BolsaFamiliaFolhaAdapter()
        self.adapters: Dict[str, BaseAdapter] = {
            "cecad": self.cecad_adapter,
            "bolsa_familia_folha": self.pbf_adapter
        }
        self.current_adapter: BaseAdapter = self.cecad_adapter

        # Estados da aplicação
        self.current_step = 0
        self.current_file_path: Optional[str] = None
        self.municipalities: List[Dict[str, Any]] = []
        self.selected_ibges: List[str] = []
        self.custom_columns: Optional[List[str]] = None
        self.current_df_preview: Optional[pd.DataFrame] = None
        self.current_metrics: Dict[str, Any] = {}
        self.preview_dirty: bool = True
        self.inspector_info: Dict[str, Any] = {}

        self._build_ui()
        self._go_to_home()

    def _build_ui(self):
        # 1. Header Superior
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(12, 6))

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="📋 AppLeituraCadastroUnico & Folha PBF",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Leitura, Tratamento e Exportação de Dados Sociais Municipais (CECAD & Folha de Pagamentos)",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w")

        header_controls = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_controls.pack(side="right")

        self.home_btn = ctk.CTkButton(
            header_controls,
            text="🏠 Início",
            width=90,
            fg_color=("#2563EB", "#3B82F6"),
            text_color="white",
            hover_color=("#1D4ED8", "#2563EB"),
            command=self._on_home_clicked
        )
        self.home_btn.pack(side="left", padx=6)

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

        # 2. Barra Superior de Passos (Stepper) - gerido dinamicamente
        self.stepper_frame = ctk.CTkFrame(self, corner_radius=10)

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

        # Cria frames para a tela inicial e para cada passo
        self.home_frame = self._build_home_ui()
        self.step1_frame = self._build_step1_ui()
        self.step2_frame = self._build_step2_ui()
        self.step3_frame = self._build_step3_ui()
        self.step4_frame = self._build_step4_ui()

    # ==========================================
    # TELA INICIAL: HUB DE MÓDULOS SOCIAIS
    # ==========================================
    def _build_home_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=12)

        # 1. Hero / Header de Recepção
        hero_box = ctk.CTkFrame(frame, corner_radius=10, fg_color=("gray90", "gray17"))
        hero_box.pack(fill="x", padx=20, pady=(16, 14))

        ctk.CTkLabel(
            hero_box,
            text="🏛️ Central de Inteligência de Dados Sociais",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w", padx=20, pady=(14, 4))

        ctk.CTkLabel(
            hero_box,
            text="Selecione o módulo de trabalho desejado para realizar a ingestão, auditoria, estatísticas e exportação:",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70")
        ).pack(anchor="w", padx=20, pady=(0, 14))

        # 2. Grid de Módulos (3 Cards)
        cards_container = ctk.CTkFrame(frame, fg_color="transparent")
        cards_container.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        cards_container.grid_columnconfigure((0, 1, 2), weight=1, uniform="module_card", pad=12)
        cards_container.grid_rowconfigure(0, weight=1)

        # Card 1: CECAD
        card_cecad = self._create_module_card(
            parent=cards_container,
            icon="📋",
            title="Cadastro Único (CECAD)",
            badge_text="Bases MDS (.zip / .csv)",
            badge_color=("#DBEAFE", "#1E3A8A"),
            badge_text_color=("#1E40AF", "#93C5FD"),
            description="Leitura completa das bases estaduais e municipais do CadÚnico.",
            bullets=[
                "Tradução de códigos com dicionário oficial MDS",
                "Perfis: Geral, Bolsa Família, Habitação, Trabalho",
                "Filtros de vulnerabilidade e atualização cadastral",
                "Métricas demográficas e renda média (RFPC)"
            ],
            btn_text="Acessar Módulo CECAD ➔",
            btn_color=("#1D4ED8", "#2563EB"),
            btn_hover=("#1E40AF", "#1D4ED8"),
            command=lambda: self._open_module("cecad")
        )
        card_cecad.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Card 2: SIBEC (Folha Bolsa Família)
        card_sibec = self._create_module_card(
            parent=cards_container,
            icon="💳",
            title="Folha Bolsa Família (SIBEC)",
            badge_text="Caixa Econômica / MDS",
            badge_color=("#D1FAE5", "#064E3B"),
            badge_text_color=("#065F46", "#6EE7B7"),
            description="Ingestão de arquivos operacionais da folha (SIBEC / Transparência).",
            bullets=[
                "Visão por Família Titular ou Benefícios individuais",
                "Discriminação de BRC, BCO, BPI, BVN, BVA, BVG",
                "Filtros de parcelas: Liberadas, Bloqueadas, Suspensas",
                "Total financeiro da folha e CadÚnico desatualizado"
            ],
            btn_text="Acessar Folha PBF ➔",
            btn_color=("#059669", "#10B981"),
            btn_hover=("#047857", "#059669"),
            command=lambda: self._open_module("bolsa_familia_folha")
        )
        card_sibec.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        # Card 3: Cruzamento & Diagnóstico
        card_cross = self._create_module_card(
            parent=cards_container,
            icon="🔄",
            title="Cruzamento & Diagnóstico",
            badge_text="Auditoria CECAD × SIBEC",
            badge_color=("#EDE9FE", "#4C1D95"),
            badge_text_color=("#5B21B6", "#C4B5FD"),
            description="Conciliação cadastral com auditoria da defasagem de 2 meses do MDS.",
            bullets=[
                "Checagem automática de datas e defasagem temporal",
                "Classificação em 4 quadrantes operacionais",
                "Busca ativa: famílias na folha com CadÚnico > 2 anos",
                "Exportação de listas para busca ativa do CRAS"
            ],
            btn_text="Explorar Cruzamento ➔",
            btn_color=("#6D28D9", "#7C3AED"),
            btn_hover=("#5B21B6", "#6D28D9"),
            command=self._open_cross_module
        )
        card_cross.grid(row=0, column=2, sticky="nsew", padx=4, pady=4)

        # 3. Rodapé Informativo
        footer = ctk.CTkFrame(frame, corner_radius=8, fg_color=("gray92", "gray17"))
        footer.pack(fill="x", padx=20, pady=(0, 16))

        pills = [
            ("🛡️ Modo LGPD", "Ocultação de nomes, CPFs, NIS e endereços"),
            ("📊 Teto do Excel", "Particionamento inteligente acima de 1M de linhas"),
            ("⚡ Motor Streaming", "Leitura de baixo consumo de memória RAM")
        ]
        footer.grid_columnconfigure((0, 1, 2), weight=1)
        for idx, (p_title, sub) in enumerate(pills):
            p_box = ctk.CTkFrame(footer, fg_color="transparent")
            p_box.grid(row=0, column=idx, padx=12, pady=10)
            ctk.CTkLabel(p_box, text=p_title, font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="center")
            ctk.CTkLabel(p_box, text=sub, font=ctk.CTkFont(size=10), text_color=("gray40", "gray60")).pack(anchor="center")

        return frame

    def _create_module_card(
        self, parent, icon: str, title: str, badge_text: str,
        badge_color: tuple, badge_text_color: tuple,
        description: str, bullets: List[str],
        btn_text: str, btn_color: tuple, btn_hover: tuple,
        command
    ) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=("white", "gray19"), border_width=1, border_color=("gray80", "gray28"))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=14)

        # Top row: Icon + Badge
        top_row = ctk.CTkFrame(content, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(top_row, text=icon, font=ctk.CTkFont(size=26)).pack(side="left")

        badge = ctk.CTkLabel(
            top_row,
            text=f" {badge_text} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=badge_color,
            text_color=badge_text_color,
            corner_radius=6
        )
        badge.pack(side="right")

        # Title
        ctk.CTkLabel(
            content,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", pady=(2, 6))

        # Description
        ctk.CTkLabel(
            content,
            text=description,
            font=ctk.CTkFont(size=11),
            text_color=("gray30", "gray70"),
            wraplength=260,
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # Bullets
        bullet_box = ctk.CTkFrame(content, fg_color="transparent")
        bullet_box.pack(fill="both", expand=True, pady=(0, 12))
        for b in bullets:
            b_row = ctk.CTkFrame(bullet_box, fg_color="transparent")
            b_row.pack(fill="x", pady=2)
            ctk.CTkLabel(b_row, text="•", font=ctk.CTkFont(size=12, weight="bold"), text_color=("gray40", "gray60")).pack(side="left", anchor="n", padx=(0, 4))
            ctk.CTkLabel(b_row, text=b, font=ctk.CTkFont(size=11), text_color=("gray30", "gray75"), wraplength=240, justify="left").pack(side="left", anchor="w")

        # Action Button
        btn = ctk.CTkButton(
            content,
            text=btn_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=38,
            corner_radius=8,
            fg_color=btn_color,
            hover_color=btn_hover,
            command=command
        )
        btn.pack(fill="x", side="bottom")

        return card

    def _open_module(self, adapter_id: str):
        if adapter_id not in self.adapters:
            return
        self.current_adapter = self.adapters[adapter_id]
        if adapter_id == "cecad":
            self.base_segmented.set("📋 Cadastro Único (CECAD)")
        else:
            self.base_segmented.set("💳 Folha do Bolsa Família (PBF)")

        # Mostra o stepper
        if hasattr(self, "stepper_frame") and self.stepper_frame.winfo_manager() != "pack":
            self.stepper_frame.pack(fill="x", padx=20, pady=(6, 10), before=self.content_container)

        self._reset_file_state()
        self.badge_scope.configure(text=f"• Base selecionada: {self.current_adapter.display_name}")
        self.badge_date.configure(text="• Aguardando seleção do arquivo...")
        self._update_step2_filter_visibility()
        self._setup_stat_cards_for_adapter()
        self._go_to_step(1)

    def _open_cross_module(self):
        cecad_p = self.current_file_path if (self.current_adapter.adapter_id == "cecad" and self.current_file_path) else None
        pbf_p = self.current_file_path if (self.current_adapter.adapter_id == "bolsa_familia_folha" and self.current_file_path) else None
        CrossModuleDialog(self, default_cecad=cecad_p, default_sibec=pbf_p)

    def _go_to_home(self):
        self.current_step = 0
        if hasattr(self, "stepper_frame") and self.stepper_frame.winfo_manager() == "pack":
            self.stepper_frame.pack_forget()
        for f in [self.step1_frame, self.step2_frame, self.step3_frame, self.step4_frame]:
            f.pack_forget()
        if hasattr(self, "home_frame"):
            self.home_frame.pack(fill="both", expand=True)
        if hasattr(self, "home_btn"):
            self.home_btn.configure(state="disabled")

    def _on_home_clicked(self):
        if self.current_file_path:
            confirm = messagebox.askyesno(
                "Retornar ao Início",
                "Deseja voltar à Tela Inicial para trocar de módulo?\n\n"
                "Os dados da sessão atual serão reiniciados."
            )
            if not confirm:
                return
            self._reset_file_state()
        self._go_to_home()

    def _reset_file_state(self):
        self.current_file_path = None
        self.municipalities = []
        self.selected_ibges = []
        self.current_df_preview = None
        self.current_metrics = {}
        self.preview_dirty = True
        self.file_entry.delete(0, "end")
        self.badge_scope.configure(text="• Escopo: Nenhum arquivo carregado")
        self.badge_date.configure(text="• Data de Referência: -")
        self.badge_count.configure(text="• Total aproximado: -")
        self.badge_mun_count.configure(text="• Municípios detectados: -")
        self.step1_next_btn.configure(state="disabled")

    # ==========================================
    # PASSO 1: CARREGAR ARQUIVO COM SELETOR DE BASE
    # ==========================================
    def _build_step1_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

        top_box = ctk.CTkFrame(frame, fg_color="transparent")
        top_box.pack(fill="x", padx=24, pady=(16, 6))

        ctk.CTkLabel(
            top_box,
            text="📁 Passo 1: Seleção da Base de Dados e Carregamento do Arquivo",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_box,
            text="Escolha a base social desejada e selecione o arquivo correspondente (.zip ou .csv).",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", pady=(2, 0))

        # Seletor de Base de Dados
        base_select_frame = ctk.CTkFrame(frame, corner_radius=8)
        base_select_frame.pack(fill="x", padx=24, pady=8)

        base_row = ctk.CTkFrame(base_select_frame, fg_color="transparent")
        base_row.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            base_row,
            text="Tipo de Base Social:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(0, 14))

        self.base_segmented = ctk.CTkSegmentedButton(
            base_row,
            values=["📋 Cadastro Único (CECAD)", "💳 Folha do Bolsa Família (PBF)"],
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            command=self._on_base_type_changed
        )
        self.base_segmented.set("📋 Cadastro Único (CECAD)")
        self.base_segmented.pack(side="left", fill="x", expand=True)

        # Painel de Seleção de Arquivo
        select_box = ctk.CTkFrame(frame, corner_radius=8)
        select_box.pack(fill="x", padx=24, pady=8)

        file_browse_row = ctk.CTkFrame(select_box, fg_color="transparent")
        file_browse_row.pack(fill="x", padx=16, pady=14)

        self.file_entry = ctk.CTkEntry(
            file_browse_row,
            placeholder_text="Selecione o arquivo da base baixado (.zip ou .csv)...",
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

        # Cartão de Informações e Metadados
        self.meta_card = ctk.CTkFrame(frame, corner_radius=8)
        self.meta_card.pack(fill="both", expand=True, padx=24, pady=(6, 14))

        self.meta_title = ctk.CTkLabel(
            self.meta_card,
            text="ℹ️ Estrutura e Metadados da Base",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.meta_title.pack(anchor="w", padx=18, pady=(14, 8))

        self.meta_info_box = ctk.CTkFrame(self.meta_card, fg_color="transparent")
        self.meta_info_box.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        self.badge_scope = ctk.CTkLabel(self.meta_info_box, text="• Escopo: Nenhum arquivo carregado", font=ctk.CTkFont(size=12), anchor="w")
        self.badge_scope.pack(fill="x", pady=3)

        self.badge_date = ctk.CTkLabel(self.meta_info_box, text="• Data de Referência: -", font=ctk.CTkFont(size=12), anchor="w")
        self.badge_date.pack(fill="x", pady=3)

        self.badge_count = ctk.CTkLabel(self.meta_info_box, text="• Total aproximado: -", font=ctk.CTkFont(size=12), anchor="w")
        self.badge_count.pack(fill="x", pady=3)

        self.badge_mun_count = ctk.CTkLabel(self.meta_info_box, text="• Municípios detectados: -", font=ctk.CTkFont(size=12), anchor="w")
        self.badge_mun_count.pack(fill="x", pady=3)

        # Rodapé de Navegação do Passo 1
        foot_box = ctk.CTkFrame(frame, fg_color="transparent")
        foot_box.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkButton(
            foot_box,
            text="🏠 Voltar ao Início",
            font=ctk.CTkFont(size=12),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            height=36,
            width=160,
            command=self._on_home_clicked
        ).pack(side="left")

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

    def _on_base_type_changed(self, choice: str):
        if "Folha" in choice:
            self.current_adapter = self.adapters["bolsa_familia_folha"]
        else:
            self.current_adapter = self.adapters["cecad"]

        # Reseta seleção de arquivo para a nova base
        self.current_file_path = None
        self.file_entry.delete(0, "end")
        self.selected_ibges = []
        self.municipalities = []
        self.preview_dirty = True
        self.step1_next_btn.configure(state="disabled")

        self.badge_scope.configure(text=f"• Base selecionada: {self.current_adapter.display_name}")
        self.badge_date.configure(text="• Aguardando seleção do arquivo...")
        self.badge_count.configure(text="• Total aproximado: -")
        self.badge_mun_count.configure(text="• Municípios detectados: -")

        self._update_step2_filter_visibility()
        self._setup_stat_cards_for_adapter()

    # ==========================================
    # PASSO 2: APLICAR FILTROS (ADAPTATIVO)
    # ==========================================
    def _build_step2_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

        top_box = ctk.CTkFrame(frame, fg_color="transparent")
        top_box.pack(fill="x", padx=24, pady=(16, 8))

        ctk.CTkLabel(
            top_box,
            text="⚙️ Passo 2: Aplicação de Filtros e Critérios de Análise",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_box,
            text="Configure o escopo territorial, os recortes específicos da base selecionada e as regras de anonimização LGPD.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", pady=(2, 0))

        scrollable_content = ctk.CTkScrollableFrame(frame, corner_radius=8)
        scrollable_content.pack(fill="both", expand=True, padx=24, pady=8)

        # Seção 1: Município / Território (Comum a ambas as bases)
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

        # ==========================================
        # FILTROS ESPECÍFICOS DO CECAD
        # ==========================================
        self.cecad_filters_container = ctk.CTkFrame(scrollable_content, fg_color="transparent")
        self.cecad_filters_container.pack(fill="x")

        # Nível de Análise e Cabeçalhos (CECAD)
        gran_section = ctk.CTkFrame(self.cecad_filters_container, corner_radius=8)
        gran_section.pack(fill="x", pady=6)

        gran_row = ctk.CTkFrame(gran_section, fg_color="transparent")
        gran_row.pack(fill="x", padx=16, pady=12)

        gran_box = ctk.CTkFrame(gran_row, fg_color="transparent")
        gran_box.pack(side="left", fill="x", expand=True, padx=(0, 12))

        ctk.CTkLabel(gran_box, text="Nível de Análise (Granularidade):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        self.gran_segmented = ctk.CTkSegmentedButton(gran_box, values=["Pessoa (Original)", "Família (Apenas RF)"], command=self._on_filter_changed)
        self.gran_segmented.set("Pessoa (Original)")
        self.gran_segmented.pack(fill="x")

        header_box = ctk.CTkFrame(gran_row, fg_color="transparent")
        header_box.pack(side="right", fill="x", expand=True)

        ctk.CTkLabel(header_box, text="Estilo do Cabeçalho das Colunas:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        self.header_segmented = ctk.CTkSegmentedButton(header_box, values=["Nomes Amigáveis", "[Código] + Nome", "Códigos Técnicos"], command=self._on_filter_changed)
        self.header_segmented.set("Nomes Amigáveis")
        self.header_segmented.pack(fill="x")

        # Perfis Temáticos e Filtros Rápidos (CECAD)
        filter_section = ctk.CTkFrame(self.cecad_filters_container, corner_radius=8)
        filter_section.pack(fill="x", pady=6)

        filter_row1 = ctk.CTkFrame(filter_section, fg_color="transparent")
        filter_row1.pack(fill="x", padx=16, pady=(12, 6))

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
        self.profile_combo = ctk.CTkComboBox(prof_box, values=profile_values, command=self._on_profile_changed, height=30)
        self.profile_combo.set("Completo (Todas as Colunas)")
        self.profile_combo.pack(fill="x", pady=(2, 0))

        pbf_box = ctk.CTkFrame(filter_row1, fg_color="transparent")
        pbf_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(pbf_box, text="Bolsa Família:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.pbf_combo = ctk.CTkComboBox(pbf_box, values=["Todos", "Apenas Beneficiários (Sim)", "Não Beneficiários (Não)"], command=self._on_filter_changed, height=30)
        self.pbf_combo.set("Todos")
        self.pbf_combo.pack(fill="x", pady=(2, 0))

        filter_row2 = ctk.CTkFrame(filter_section, fg_color="transparent")
        filter_row2.pack(fill="x", padx=16, pady=(6, 12))

        desat_box = ctk.CTkFrame(filter_row2, fg_color="transparent")
        desat_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(desat_box, text="Atualização Cadastral:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.desat_combo = ctk.CTkComboBox(desat_box, values=["Todos", "Desatualizados (> 2 anos)", "Atualizados (<= 2 anos)"], command=self._on_filter_changed, height=30)
        self.desat_combo.set("Todos")
        self.desat_combo.pack(fill="x", pady=(2, 0))

        rfpc_box = ctk.CTkFrame(filter_row2, fg_color="transparent")
        rfpc_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(rfpc_box, text="Faixa de Renda Per Capita:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.rfpc_combo = ctk.CTkComboBox(rfpc_box, values=["Todas", "Extrema Pobreza", "Pobreza", "Baixa Renda", "Acima de 1/2 S.M."], command=self._on_filter_changed, height=30)
        self.rfpc_combo.set("Todas")
        self.rfpc_combo.pack(fill="x", pady=(2, 0))

        # ==========================================
        # FILTROS ESPECÍFICOS DA FOLHA PBF
        # ==========================================
        self.pbf_filters_container = ctk.CTkFrame(scrollable_content, fg_color="transparent")
        # Inicia desempacotado (visível apenas quando Folha PBF estiver ativa)

        # Seção 1: Nível de Análise e Cabeçalhos (Folha PBF)
        pbf_gran_section = ctk.CTkFrame(self.pbf_filters_container, corner_radius=8)
        pbf_gran_section.pack(fill="x", pady=6)

        pbf_gran_row = ctk.CTkFrame(pbf_gran_section, fg_color="transparent")
        pbf_gran_row.pack(fill="x", padx=16, pady=12)

        pbf_gran_box = ctk.CTkFrame(pbf_gran_row, fg_color="transparent")
        pbf_gran_box.pack(side="left", fill="x", expand=True, padx=(0, 12))

        ctk.CTkLabel(pbf_gran_box, text="Nível de Análise da Folha:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        self.pbf_gran_segmented = ctk.CTkSegmentedButton(
            pbf_gran_box,
            values=["Família Titular (Linha RF)", "Detalhe Benefícios (Todas as Linhas)"],
            command=self._on_filter_changed
        )
        self.pbf_gran_segmented.set("Família Titular (Linha RF)")
        self.pbf_gran_segmented.pack(fill="x")

        pbf_header_box = ctk.CTkFrame(pbf_gran_row, fg_color="transparent")
        pbf_header_box.pack(side="right", fill="x", expand=True)

        ctk.CTkLabel(pbf_header_box, text="Estilo do Cabeçalho das Colunas:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        self.pbf_header_segmented = ctk.CTkSegmentedButton(
            pbf_header_box,
            values=["Nomes Amigáveis", "[Código] + Nome", "Códigos Técnicos"],
            command=self._on_filter_changed
        )
        self.pbf_header_segmented.set("Nomes Amigáveis")
        self.pbf_header_segmented.pack(fill="x")

        # Seção 2: Recortes Operacionais, Situação e GPTE
        pbf_filt_section = ctk.CTkFrame(self.pbf_filters_container, corner_radius=8)
        pbf_filt_section.pack(fill="x", pady=6)

        pbf_f_row1 = ctk.CTkFrame(pbf_filt_section, fg_color="transparent")
        pbf_f_row1.pack(fill="x", padx=16, pady=(12, 6))

        # Situação do Benefício
        sit_box = ctk.CTkFrame(pbf_f_row1, fg_color="transparent")
        sit_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(sit_box, text="Situação da Parcela / Benefício:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.pbf_sit_combo = ctk.CTkComboBox(
            sit_box,
            values=["Todos", "Liberados / Pagos", "Bloqueados", "Suspensos", "Cancelados"],
            command=self._on_filter_changed,
            height=30
        )
        self.pbf_sit_combo.set("Todos")
        self.pbf_sit_combo.pack(fill="x", pady=(2, 0))

        # Faixa de Valor da Parcela
        val_box = ctk.CTkFrame(pbf_f_row1, fg_color="transparent")
        val_box.pack(side="right", fill="x", expand=True)

        ctk.CTkLabel(val_box, text="Faixa de Valor da Parcela (R$):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.pbf_val_combo = ctk.CTkComboBox(
            val_box,
            values=["Todas", "Até R$ 600,00", "R$ 601,00 a R$ 800,00", "Acima de R$ 800,00"],
            command=self._on_filter_changed,
            height=30
        )
        self.pbf_val_combo.set("Todas")
        self.pbf_val_combo.pack(fill="x", pady=(2, 0))

        pbf_f_row2 = ctk.CTkFrame(pbf_filt_section, fg_color="transparent")
        pbf_f_row2.pack(fill="x", padx=16, pady=(6, 12))

        # Populações Tradicionais (GPTE)
        gpte_box = ctk.CTkFrame(pbf_f_row2, fg_color="transparent")
        gpte_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(gpte_box, text="Populações Tradicionais (GPTE):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.pbf_gpte_combo = ctk.CTkComboBox(
            gpte_box,
            values=[
                "Todas as Famílias",
                "Apenas Populações Tradicionais (Sim)",
                "Famílias Indígenas",
                "Famílias Quilombolas",
                "Catadores de Material Reciclável",
                "Foco de Trabalho Infantil",
                "Trabalho Análogo a Escravo",
                "Apenas Não-GPTE (Geral)"
            ],
            command=self._on_filter_changed,
            height=30
        )
        self.pbf_gpte_combo.set("Todas as Famílias")
        self.pbf_gpte_combo.pack(fill="x", pady=(2, 0))

        # Atualização Cadastral no SIBEC
        desat_box = ctk.CTkFrame(pbf_f_row2, fg_color="transparent")
        desat_box.pack(side="right", fill="x", expand=True)

        ctk.CTkLabel(desat_box, text="Atualização Cadastral (CadÚnico):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.pbf_desat_combo = ctk.CTkComboBox(
            desat_box,
            values=[
                "Todas as Famílias",
                "Desatualizados (> 2 anos) — Risco Bloqueio",
                "Atualizados (<= 2 anos)"
            ],
            command=self._on_filter_changed,
            height=30
        )
        self.pbf_desat_combo.set("Todas as Famílias")
        self.pbf_desat_combo.pack(fill="x", pady=(2, 0))

        # Seção Comum: Proteção de Dados LGPD
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

        self.lgpd_desc_label = ctk.CTkLabel(
            lgpd_box,
            text="🔒 Oculta CPF, NIS, nomes, endereço residencial completo, CRAS e escolas dos dependentes. Preserva o município (código IBGE) e valores para permitir análises territoriais seguras.",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
            wraplength=980,
            justify="left"
        )
        self.lgpd_desc_label.pack(anchor="w", pady=(4, 0))

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

    def _update_step2_filter_visibility(self):
        if self.current_adapter.adapter_id == "cecad":
            self.pbf_filters_container.pack_forget()
            self.cecad_filters_container.pack(fill="x")
        else:
            self.cecad_filters_container.pack_forget()
            self.pbf_filters_container.pack(fill="x")

    # ==========================================
    # PASSO 3: PRÉ-VISUALIZAR E ESTATÍSTICAS
    # ==========================================
    def _build_step3_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

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

        # Cartões de Estatísticas Dinâmicos
        stats_frame = ctk.CTkFrame(frame, fg_color="transparent")
        stats_frame.pack(fill="x", padx=16, pady=(4, 6))
        stats_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.cards: List[StatCard] = []
        for i in range(5):
            card = StatCard(stats_frame, title=f"Métrica {i+1}", initial_value="-", subtitle="-", icon="📊")
            card.grid(row=0, column=i, padx=4, sticky="ew")
            self.cards.append(card)

        self._setup_stat_cards_for_adapter()

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

    def _setup_stat_cards_for_adapter(self):
        defs = self.current_adapter.get_stat_card_definitions()
        for idx, card in enumerate(self.cards):
            if idx < len(defs):
                d = defs[idx]
                card.title_label.configure(text=f"{d.icon} {d.title}".strip())
                card.subtitle_label.configure(text=d.subtitle)
                card.update_value("-")

    # ==========================================
    # PASSO 4: EXPORTAR ARQUIVO
    # ==========================================
    def _build_step4_ui(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_container, corner_radius=10)

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

        ctk.CTkLabel(content_box, text="📋 Resumo da Seleção Final", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20, pady=(16, 8))

        self.export_summary_text = ctk.CTkLabel(content_box, text="Carregando resumo...", font=ctk.CTkFont(size=12), anchor="w", justify="left")
        self.export_summary_text.pack(fill="x", padx=20, pady=(0, 12))

        # Alerta do Limite de Linhas do Excel
        self.excel_alert_box = ctk.CTkFrame(content_box, corner_radius=8)
        self.excel_alert_box.pack(fill="x", padx=20, pady=8)

        self.excel_alert_label = ctk.CTkLabel(self.excel_alert_box, text="", font=ctk.CTkFont(size=12, weight="bold"), wraplength=960, justify="left")
        self.excel_alert_label.pack(fill="x", padx=16, pady=12)

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
        if step_number > 1 and not self.current_file_path:
            messagebox.showwarning("Aviso", "Por favor, carregue um arquivo no Passo 1.")
            return

        if step_number > 2 and not self.selected_ibges:
            messagebox.showwarning("Aviso", "Selecione ao menos um município no Passo 2.")
            return

        self.current_step = step_number

        for idx, btn in enumerate(self.step_buttons):
            s_num = idx + 1
            if s_num == step_number:
                btn.configure(fg_color="#1E3A8A", hover_color="#1D4ED8", text_color="#FFFFFF")
            elif s_num < step_number:
                btn.configure(fg_color=("gray80", "gray25"), hover_color=("gray70", "gray35"), text_color=("#1E3A8A", "#60A5FA"))
            else:
                btn.configure(fg_color=("gray85", "gray20"), hover_color=("gray75", "gray25"), text_color=("gray50", "gray50"))

        self.step1_frame.pack_forget()
        self.step2_frame.pack_forget()
        self.step3_frame.pack_forget()
        self.step4_frame.pack_forget()
        if hasattr(self, "home_frame"):
            self.home_frame.pack_forget()
        if hasattr(self, "home_btn"):
            self.home_btn.configure(state="normal")
        if hasattr(self, "stepper_frame") and self.stepper_frame.winfo_manager() != "pack":
            self.stepper_frame.pack(fill="x", padx=20, pady=(6, 10), before=self.content_container)

        if step_number == 1:
            self.step1_frame.pack(fill="both", expand=True)
        elif step_number == 2:
            self._update_step2_filter_visibility()
            self.step2_frame.pack(fill="both", expand=True)
        elif step_number == 3:
            self._setup_stat_cards_for_adapter()
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
            title=f"Selecione o Arquivo — {self.current_adapter.display_name}",
            filetypes=self.current_adapter.file_types
        )
        if not file_path:
            return

        self.current_file_path = file_path
        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, file_path)
        self.preview_dirty = True

        modal = ProgressModal(
            self,
            title=f"Carregando {self.current_adapter.display_name}",
            message="Inspecionando estrutura, cabeçalho e municípios...",
            indeterminate=False
        )

        threading.Thread(target=self._inspect_file_worker, args=(modal,), daemon=True).start()

    def _inspect_file_worker(self, modal: ProgressModal):
        try:
            modal.update_progress(0.2, "Escaneando registros e identificando municípios...")
            info = self.current_adapter.inspect_file(self.current_file_path)
            self.inspector_info = info
            self.municipalities = info.get("municipalities", [])

            if self.municipalities:
                self.selected_ibges = [str(self.municipalities[0]["cd_ibge"]).strip()]
            else:
                self.selected_ibges = []

            def on_success():
                modal.close()

                scope_desc = info.get("scope_desc", "Base Carregada")
                ref_desc = info.get("ref_desc", "Não identificada")
                total_lines = info.get("total_lines_approx", 0)

                self.badge_scope.configure(text=f"• Escopo: {scope_desc}")
                self.badge_date.configure(text=f"• Referência: {ref_desc}")
                self.badge_count.configure(text=f"• Total aproximado: {total_lines:,} registros".replace(",", "."))
                self.badge_mun_count.configure(text=f"• Municípios detectados: {len(self.municipalities)} municípios na base")

                self.step1_next_btn.configure(state="normal")
                self._update_municipality_status()
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
        cols = self.inspector_info.get("columns", [])
        if choice == "Personalizado...":
            if not cols:
                messagebox.showwarning("Aviso", "Carregue um arquivo antes de selecionar colunas personalizadas.")
                self.profile_combo.set("Completo (Todas as Colunas)")
                return

            def on_save_cols(selected):
                self.custom_columns = selected
                self.preview_dirty = True

            current_sel = self.custom_columns if self.custom_columns else cols
            ColumnSelectorDialog(self, cols, current_sel, self.dict_parser, on_save_cols)
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
            message=f"Filtrando {self.current_adapter.display_name} e calculando métricas...",
            indeterminate=False
        )

        threading.Thread(target=self._preview_worker, args=(modal,), daemon=True).start()

    def _gather_params_for_active_adapter(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "file_path": self.current_file_path,
            "municipios_ibge": self.selected_ibges,
            "colunas_customizadas": self.custom_columns,
            "modo_lgpd": bool(self.lgpd_switch.get())
        }

        if self.current_adapter.adapter_id == "cecad":
            gran_choice = self.gran_segmented.get()
            params["granularidade"] = "familia" if "Família" in gran_choice else "pessoa"

            header_choice = self.header_segmented.get()
            if "Nomes Amigáveis" in header_choice:
                params["header_mode"] = "amigavel"
            elif "[Código]" in header_choice:
                params["header_mode"] = "tecnico_amigavel"
            else:
                params["header_mode"] = "tecnico"

            prof_choice = self.profile_combo.get()
            prof_map = {
                "Completo (Todas as Colunas)": "completo",
                "Visão Geral & Cadastro": "geral",
                "Bolsa Família & Renda": "bolsa_familia",
                "Habitação & Vulnerabilidade": "habitacao",
                "Pessoas, Educação & Trabalho": "pessoas_trabalho"
            }
            params["perfil_colunas"] = prof_map.get(prof_choice, "completo")

            pbf_choice = self.pbf_combo.get()
            params["filtro_pbf"] = "sim" if "Beneficiários (Sim)" in pbf_choice else ("nao" if "Não Beneficiários" in pbf_choice else "todos")

            desat_choice = self.desat_combo.get()
            params["filtro_atualizacao"] = "desatualizados" if "Desatualizados" in desat_choice else ("atualizados" if "Atualizados" in desat_choice else "todos")

            rfpc_choice = self.rfpc_combo.get()
            rfpc_map = {
                "Todas": "todas",
                "Extrema Pobreza": "extrema_pobreza",
                "Pobreza": "pobreza",
                "Baixa Renda": "baixa_renda",
                "Acima de 1/2 S.M.": "acima_meio_sm"
            }
            params["filtro_renda"] = rfpc_map.get(rfpc_choice, "todas")

        elif self.current_adapter.adapter_id == "bolsa_familia_folha":
            # Granularidade
            gran_choice = getattr(self, "pbf_gran_segmented", None)
            if gran_choice and "Detalhe" in gran_choice.get():
                params["granularidade"] = "beneficio"
            else:
                params["granularidade"] = "familia"

            # Cabeçalho
            head_choice = getattr(self, "pbf_header_segmented", None)
            if head_choice:
                hc = head_choice.get()
                if "Nomes Amigáveis" in hc:
                    params["header_mode"] = "amigavel"
                elif "[Código]" in hc:
                    params["header_mode"] = "tecnico_amigavel"
                else:
                    params["header_mode"] = "tecnico"
            else:
                params["header_mode"] = "amigavel"

            # Situação
            sit_choice = self.pbf_sit_combo.get().lower()
            if "liberado" in sit_choice:
                params["filtro_situacao"] = "liberados"
            elif "bloqueado" in sit_choice:
                params["filtro_situacao"] = "bloqueados"
            elif "suspenso" in sit_choice:
                params["filtro_situacao"] = "suspensos"
            elif "cancelado" in sit_choice:
                params["filtro_situacao"] = "cancelados"
            else:
                params["filtro_situacao"] = "todos"

            # Valor
            val_choice = self.pbf_val_combo.get()
            if "Até R$ 600" in val_choice:
                params["filtro_valor"] = "ate_600"
            elif "601" in val_choice:
                params["filtro_valor"] = "601_a_800"
            elif "Acima" in val_choice:
                params["filtro_valor"] = "acima_800"
            else:
                params["filtro_valor"] = "todas"

            # Populações Tradicionais (GPTE)
            gpte_widget = getattr(self, "pbf_gpte_combo", None)
            if gpte_widget:
                gc = gpte_widget.get().lower()
                if "indígena" in gc:
                    params["filtro_gpte"] = "indigena"
                elif "quilombola" in gc:
                    params["filtro_gpte"] = "quilombola"
                elif "catador" in gc:
                    params["filtro_gpte"] = "catador"
                elif "infantil" in gc:
                    params["filtro_gpte"] = "trabalho_infantil"
                elif "escravo" in gc:
                    params["filtro_gpte"] = "trabalho_escravo"
                elif "apenas populações tradicionais" in gc:
                    params["filtro_gpte"] = "gpte_sim"
                elif "não-gpte" in gc:
                    params["filtro_gpte"] = "nao_gpte"
                else:
                    params["filtro_gpte"] = "todos"
            else:
                params["filtro_gpte"] = "todos"

            # Atualização Cadastral
            desat_widget = getattr(self, "pbf_desat_combo", None)
            if desat_widget:
                dc = desat_widget.get().lower()
                if "desatualizado" in dc:
                    params["filtro_atualizacao"] = "desatualizados"
                elif "atualizado" in dc:
                    params["filtro_atualizacao"] = "atualizados"
                else:
                    params["filtro_atualizacao"] = "todos"
            else:
                params["filtro_atualizacao"] = "todos"

        return params

    def _preview_worker(self, modal: ProgressModal):
        try:
            params = self._gather_params_for_active_adapter()
            params["limite_linhas"] = 30

            def progress_hook(pct, msg):
                modal.update_progress(pct, msg)

            params["progress_callback"] = progress_hook
            df_sample, metrics = self.current_adapter.process_data(**params)

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
        if self.current_adapter.adapter_id == "cecad":
            tot_pes = metrics.get("total_pessoas", 0)
            tot_fam = metrics.get("total_familias", 0)
            pbf_pct = metrics.get("pbf_percentual", 0.0)
            pbf_tot = metrics.get("pbf_beneficiarios", 0)
            desat_pct = metrics.get("desatualizados_percentual", 0.0)
            desat_tot = metrics.get("desatualizados_total", 0)
            renda = metrics.get("renda_media_rfpc", 0.0)

            self.cards[0].update_value(f"{tot_pes:,}".replace(",", "."), "Total filtrado")
            self.cards[1].update_value(f"{tot_fam:,}".replace(",", "."), "Famílias distintas")
            self.cards[2].update_value(f"{pbf_pct:.1f}%", f"{pbf_tot:,} beneficiários".replace(",", "."))
            self.cards[3].update_value(f"{desat_pct:.1f}%", f"{desat_tot:,} desatualizados".replace(",", "."))
            self.cards[4].update_value(f"R$ {renda:.2f}".replace(".", ","), "Média per capita")

        elif self.current_adapter.adapter_id == "bolsa_familia_folha":
            tot_ben = metrics.get("total_beneficiarios", 0)
            vlr_tot = metrics.get("valor_total_folha", 0.0)
            vlr_med = metrics.get("beneficio_medio", 0.0)
            bloq_tot = metrics.get("bloqueados_total", 0)
            bloq_pct = metrics.get("bloqueados_percentual", 0.0)
            gpte_tot = metrics.get("gpte_total", 0)
            gpte_pct = metrics.get("gpte_percentual", 0.0)

            self.cards[0].update_value(f"{tot_ben:,}".replace(",", "."), "Famílias na folha")
            self.cards[1].update_value(f"R$ {vlr_tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "Total transferido")
            self.cards[2].update_value(f"R$ {vlr_med:.2f}".replace(".", ","), "Valor médio")
            self.cards[3].update_value(f"{bloq_tot:,} ({bloq_pct:.1f}%)".replace(",", "."), "Bloqueados / Suspensos")
            self.cards[4].update_value(f"{gpte_tot:,} ({gpte_pct:.1f}%)".replace(",", "."), "Populações Tradicionais (GPTE)")

    # ==========================================
    # LÓGICA DO PASSO 4: EXPORTAÇÃO
    # ==========================================
    def _update_step4_summary(self):
        tot_reg = self.current_metrics.get("total_registros", 0)
        lgpd_on = bool(self.lgpd_switch.get())

        counts_map = {str(m["cd_ibge"]).strip(): m.get("nome", "") for m in self.municipalities}
        if len(self.selected_ibges) == 1:
            ibge = self.selected_ibges[0]
            mun_str = f"{ibge} - {counts_map.get(ibge, '')}"
        else:
            mun_str = f"{len(self.selected_ibges)} municípios selecionados"

        summary = (
            f"• Base de Dados: {self.current_adapter.display_name}\n"
            f"• Arquivo Fonte: {os.path.basename(self.current_file_path or '')}\n"
            f"• Municípios: {mun_str}\n"
            f"• Modo LGPD: {'ATIVADO (Identidades e Endereços Ocultados)' if lgpd_on else 'Desativado'}\n"
            f"• Total de Registros Filtrados: {tot_reg:,} registros".replace(",", ".")
        )
        self.export_summary_text.configure(text=summary)

        if tot_reg > EXCEL_MAX_ROWS:
            self.excel_alert_box.configure(fg_color=("#FEE2E2", "#450A0A"))
            self.excel_alert_label.configure(
                text=f"⚠️ Atenção: O total de {tot_reg:,} registros excede a capacidade de 1.048.575 linhas do Excel!\n"
                     "Ao exportar para Excel (.xlsx), o arquivo será dividido automaticamente em abas ('Parte 1', 'Parte 2'...). "
                     "Para arquivos unificados com mais de 1 milhão de linhas, recomendamos fortemente a exportação em CSV (.csv).".replace(",", "."),
                text_color=("#991B1B", "#FCA5A5")
            )
        else:
            self.excel_alert_box.configure(fg_color=("#DCFCE7", "#052E16"))
            self.excel_alert_label.configure(
                text=f"✅ Volume compatível: {tot_reg:,} registros (dentro do limite de 1.048.575 linhas do Excel).".replace(",", "."),
                text_color=("#166534", "#86EFAC")
            )

    def _start_export(self, format_type: str):
        if not self.current_file_path or not self.selected_ibges:
            messagebox.showwarning("Aviso", "Selecione o arquivo e os municípios antes de exportar.")
            return

        prefix = "folha_pbf" if self.current_adapter.adapter_id == "bolsa_familia_folha" else "cecad"
        mun_tag = f"mun_{self.selected_ibges[0]}" if len(self.selected_ibges) == 1 else f"{len(self.selected_ibges)}_municipios"
        def_filename = f"{prefix}_traduzido_{mun_tag}.{format_type}"

        if format_type == "xlsx":
            output_path = filedialog.asksaveasfilename(
                title=f"Salvar Planilha Excel — {self.current_adapter.display_name}",
                defaultextension=".xlsx",
                initialfile=def_filename,
                filetypes=[("Planilha Excel (*.xlsx)", "*.xlsx")]
            )
        else:
            output_path = filedialog.asksaveasfilename(
                title=f"Salvar Arquivo CSV — {self.current_adapter.display_name}",
                defaultextension=".csv",
                initialfile=def_filename,
                filetypes=[("Arquivo CSV (*.csv)", "*.csv")]
            )

        if not output_path:
            return

        modal = ProgressModal(
            self,
            title=f"Exportando {self.current_adapter.display_name} para {format_type.upper()}",
            message="Processando registros e gravando o arquivo...",
            indeterminate=False
        )

        threading.Thread(target=self._export_worker, args=(format_type, output_path, modal), daemon=True).start()

    def _export_worker(self, format_type: str, output_path: str, modal: ProgressModal):
        try:
            params = self._gather_params_for_active_adapter()

            def progress_hook(pct, msg):
                modal.update_progress(pct, msg)

            params["progress_callback"] = progress_hook
            df_full, metrics = self.current_adapter.process_data(**params)

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
                    f"Base: {self.current_adapter.display_name}\n"
                    f"Total de Registros: {len(df_full):,}\n"
                    f"Local: {output_path}".replace(",", ".")
                )

            self.after(0, on_complete)

        except Exception as e:
            self.after(0, lambda: modal.close())
            self.after(0, lambda: messagebox.showerror("Erro na exportação", str(e)))

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
                    messagebox.showinfo("Dicionário Carregado", f"Sucesso! {len(self.dict_parser.fields)} campos carregados do novo dicionário.")
                    self.preview_dirty = True
                except Exception as e:
                    messagebox.showerror("Erro ao carregar dicionário", str(e))
