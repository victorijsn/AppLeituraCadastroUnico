"""
Janela Principal da Aplicação AppLeituraCadastroUnico com CustomTkinter.
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


class MainWindow(ctk.CTk):
    """Janela principal do AppLeituraCadastroUnico."""

    def __init__(self):
        super().__init__()

        self.title("AppLeituraCadastroUnico — Leitor e Tradutor do Cadastro Único (CECAD)")
        self.geometry("1180x820")
        self.minsize(1040, 720)

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

        self.current_file_path: Optional[str] = None
        self.municipalities: List[Dict[str, Any]] = []
        self.custom_columns: Optional[List[str]] = None
        self.current_df_preview: Optional[pd.DataFrame] = None

        self._build_ui()

    def _build_ui(self):
        # 1. Barra Superior (Header)
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(14, 6))

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

        # Controles do Header (Tema e Dicionário)
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

        # 2. Painel de Ingestão de Arquivo
        file_frame = ctk.CTkFrame(self, corner_radius=10)
        file_frame.pack(fill="x", padx=20, pady=8)

        file_input_box = ctk.CTkFrame(file_frame, fg_color="transparent")
        file_input_box.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            file_input_box,
            text="Arquivo da Base CECAD (.zip ou .csv):",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 4))

        file_browse_row = ctk.CTkFrame(file_input_box, fg_color="transparent")
        file_browse_row.pack(fill="x")

        self.file_entry = ctk.CTkEntry(
            file_browse_row,
            placeholder_text="Selecione o arquivo baixado do MDS (ex: tab_cad_...zip ou .csv)...",
            font=ctk.CTkFont(size=12)
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browse_btn = ctk.CTkButton(
            file_browse_row,
            text="📁 Procurar Arquivo...",
            width=150,
            command=self._browse_file
        )
        self.browse_btn.pack(side="right")

        # Badges de Informações do Arquivo
        self.info_badge_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
        self.info_badge_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.badge_scope = ctk.CTkLabel(
            self.info_badge_frame,
            text="Escopo: Aguardando arquivo",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("gray85", "gray20"),
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.badge_scope.pack(side="left", padx=(0, 8))

        self.badge_date = ctk.CTkLabel(
            self.info_badge_frame,
            text="Referência: -",
            font=ctk.CTkFont(size=11),
            fg_color=("gray85", "gray20"),
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.badge_date.pack(side="left", padx=(0, 8))

        self.badge_count = ctk.CTkLabel(
            self.info_badge_frame,
            text="Registros: -",
            font=ctk.CTkFont(size=11),
            fg_color=("gray85", "gray20"),
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.badge_count.pack(side="left")

        # 3. Painel de Filtros e Opções
        config_frame = ctk.CTkFrame(self, corner_radius=10)
        config_frame.pack(fill="x", padx=20, pady=8)

        # Linha 1 de Opções: Município, Granularidade e Cabeçalhos
        row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(12, 6))

        # Município
        mun_box = ctk.CTkFrame(row1, fg_color="transparent")
        mun_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(mun_box, text="Município / Território:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.mun_combo = ctk.CTkComboBox(
            mun_box,
            values=["Nenhum município carregado"],
            command=self._on_municipio_changed,
            font=ctk.CTkFont(size=12)
        )
        self.mun_combo.pack(fill="x", pady=(2, 0))

        # Granularidade (Pessoa vs Família)
        gran_box = ctk.CTkFrame(row1, fg_color="transparent")
        gran_box.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(gran_box, text="Nível de Análise:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.gran_segmented = ctk.CTkSegmentedButton(
            gran_box,
            values=["Pessoa (Original)", "Família (Apenas RF)"],
            command=self._trigger_preview_update
        )
        self.gran_segmented.set("Pessoa (Original)")
        self.gran_segmented.pack(pady=(2, 0))

        # Cabeçalhos
        header_opt_box = ctk.CTkFrame(row1, fg_color="transparent")
        header_opt_box.pack(side="left")

        ctk.CTkLabel(header_opt_box, text="Cabeçalho das Colunas:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.header_segmented = ctk.CTkSegmentedButton(
            header_opt_box,
            values=["Nomes Amigáveis", "[Código] + Nome", "Códigos Técnicos"],
            command=self._trigger_preview_update
        )
        self.header_segmented.set("Nomes Amigáveis")
        self.header_segmented.pack(pady=(2, 0))

        # Linha 2 de Opções: Perfil de Colunas, Filtros Rápidos e Modo LGPD
        row2 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(6, 12))

        # Perfil de Colunas
        profile_box = ctk.CTkFrame(row2, fg_color="transparent")
        profile_box.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(profile_box, text="Perfil de Colunas:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        profile_values = [
            "Completo (Todas as Colunas)",
            "Visão Geral & Cadastro",
            "Bolsa Família & Renda",
            "Habitação & Vulnerabilidade",
            "Pessoas, Educação & Trabalho",
            "Personalizado..."
        ]
        self.profile_combo = ctk.CTkComboBox(
            profile_box,
            values=profile_values,
            command=self._on_profile_changed,
            width=220
        )
        self.profile_combo.set("Completo (Todas as Colunas)")
        self.profile_combo.pack(pady=(2, 0))

        # Bolsa Família
        pbf_box = ctk.CTkFrame(row2, fg_color="transparent")
        pbf_box.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(pbf_box, text="Bolsa Família:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.pbf_combo = ctk.CTkComboBox(
            pbf_box,
            values=["Todos", "Apenas Beneficiários (Sim)", "Não Beneficiários (Não)"],
            command=self._trigger_preview_update,
            width=165
        )
        self.pbf_combo.set("Todos")
        self.pbf_combo.pack(pady=(2, 0))

        # Atualização Cadastral
        desat_box = ctk.CTkFrame(row2, fg_color="transparent")
        desat_box.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(desat_box, text="Cadastro:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.desat_combo = ctk.CTkComboBox(
            desat_box,
            values=["Todos", "Desatualizados (> 2 anos)", "Atualizados (<= 2 anos)"],
            command=self._trigger_preview_update,
            width=165
        )
        self.desat_combo.set("Todos")
        self.desat_combo.pack(pady=(2, 0))

        # Faixa de Renda
        rfpc_box = ctk.CTkFrame(row2, fg_color="transparent")
        rfpc_box.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(rfpc_box, text="Faixa de Renda:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.rfpc_combo = ctk.CTkComboBox(
            rfpc_box,
            values=["Todas", "Extrema Pobreza", "Pobreza", "Baixa Renda", "Acima de 1/2 S.M."],
            command=self._trigger_preview_update,
            width=150
        )
        self.rfpc_combo.set("Todas")
        self.rfpc_combo.pack(pady=(2, 0))

        # Modo LGPD
        lgpd_box = ctk.CTkFrame(row2, fg_color="transparent")
        lgpd_box.pack(side="left", padx=(10, 0), pady=(16, 0))

        self.lgpd_switch = ctk.CTkSwitch(
            lgpd_box,
            text="Modo LGPD (Mascara CPF/NIS)",
            command=self._trigger_preview_update
        )
        self.lgpd_switch.pack()

        # 4. Cards de Estatísticas / Resumo
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(4, 6))

        stats_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.card_pessoas = StatCard(stats_frame, title="Total de Pessoas", initial_value="-", subtitle="Indivíduos filtrados", icon="👥")
        self.card_pessoas.grid(row=0, column=0, padx=4, sticky="ew")

        self.card_familias = StatCard(stats_frame, title="Total de Famílias", initial_value="-", subtitle="Famílias distintas", icon="🏠")
        self.card_familias.grid(row=0, column=1, padx=4, sticky="ew")

        self.card_pbf = StatCard(stats_frame, title="Bolsa Família", initial_value="-", subtitle="Taxa de cobertura", icon="💳")
        self.card_pbf.grid(row=0, column=2, padx=4, sticky="ew")

        self.card_desat = StatCard(stats_frame, title="Desatualizados", initial_value="-", subtitle="Mais de 24 meses", icon="⚠️")
        self.card_desat.grid(row=0, column=3, padx=4, sticky="ew")

        self.card_renda = StatCard(stats_frame, title="Renda Média", initial_value="-", subtitle="Per capita familiar", icon="💵")
        self.card_renda.grid(row=0, column=4, padx=4, sticky="ew")

        # 5. Tabela de Pré-visualização
        preview_container = ctk.CTkFrame(self, corner_radius=10)
        preview_container.pack(fill="both", expand=True, padx=20, pady=6)

        preview_header = ctk.CTkFrame(preview_container, fg_color="transparent")
        preview_header.pack(fill="x", padx=14, pady=(8, 4))

        ctk.CTkLabel(
            preview_header,
            text="Pré-visualização dos Dados Traduzidos (Primeiros 30 registros):",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            preview_header,
            text="🔄 Atualizar Prévia",
            width=120,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self._update_preview
        )
        self.refresh_btn.pack(side="right")

        self.preview_table = PreviewTable(preview_container)
        self.preview_table.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # 6. Barra Inferior de Ações e Progresso
        bottom_frame = ctk.CTkFrame(self, corner_radius=10)
        bottom_frame.pack(fill="x", padx=20, pady=(6, 14))

        # Status e Progresso
        progress_box = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        progress_box.pack(side="left", fill="x", expand=True, padx=16, pady=10)

        self.status_label = ctk.CTkLabel(
            progress_box,
            text="Pronto. Carregue um arquivo para começar.",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60")
        )
        self.status_label.pack(anchor="w")

        self.progress_bar = ctk.CTkProgressBar(progress_box)
        self.progress_bar.pack(fill="x", pady=(4, 0))
        self.progress_bar.set(0.0)

        # Botões de Exportação
        export_buttons_box = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        export_buttons_box.pack(side="right", padx=16, pady=10)

        self.export_excel_btn = ctk.CTkButton(
            export_buttons_box,
            text="📊 Exportar Excel (.xlsx)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            height=34,
            command=lambda: self._start_export("xlsx")
        )
        self.export_excel_btn.pack(side="left", padx=6)

        self.export_csv_btn = ctk.CTkButton(
            export_buttons_box,
            text="📄 Exportar CSV (.csv)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#047857",
            hover_color="#059669",
            height=34,
            command=lambda: self._start_export("csv")
        )
        self.export_csv_btn.pack(side="left", padx=6)

    def _toggle_theme(self):
        mode = self.theme_switch.get()
        ctk.set_appearance_mode(mode)
        if hasattr(self, "preview_table"):
            self.preview_table._setup_style()

    def _on_manage_dictionary(self):
        """Abre diálogo para visualização ou upload de novo dicionário Excel."""
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
                    self._trigger_preview_update()
                except Exception as e:
                    messagebox.showerror("Erro ao carregar dicionário", str(e))

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

        # Inicia inspeção em segundo plano
        self._set_ui_state(busy=True, message="Inspecionando estrutura do arquivo...")
        threading.Thread(target=self._inspect_file_worker, daemon=True).start()

    def _inspect_file_worker(self):
        try:
            self.inspector = FileInspector(self.current_file_path)

            # Extrai municípios disponíveis
            is_single, mun_list = self.inspector.scan_municipalities()
            self.municipalities = mun_list

            date_info = self.inspector.date_info

            def update_ui():
                # Atualiza Badges
                if is_single:
                    mun_name = mun_list[0]["nome"] if mun_list else "Municipal"
                    self.badge_scope.configure(text=f"Escopo: Base Municipal ({mun_name})")
                else:
                    self.badge_scope.configure(text=f"Escopo: Base Estadual ({len(mun_list)} Municípios)")

                ref_desc = date_info.get("descricao") or "Não identificada"
                self.badge_date.configure(text=f"Referência: {ref_desc}")

                total_lines = self.inspector.total_lines_approx
                self.badge_count.configure(text=f"Total: {total_lines:,} registros".replace(",", "."))

                # Atualiza Combobox de Municípios
                mun_values = [m["rotulo"] for m in self.municipalities]
                if not mun_values:
                    mun_values = ["Nenhum município detectado"]
                self.mun_combo.configure(values=mun_values)
                self.mun_combo.set(mun_values[0])

                self._set_ui_state(busy=False, message=f"Arquivo carregado com sucesso. {len(self.municipalities)} municípios disponíveis.")
                self._update_preview()

            self.after(0, update_ui)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro ao ler arquivo", str(e)))
            self.after(0, lambda: self._set_ui_state(busy=False, message="Erro na leitura do arquivo."))

    def _get_selected_ibge(self) -> Optional[str]:
        val = self.mun_combo.get()
        if not val or "Nenhum" in val:
            return None
        parts = val.split(" - ")
        return parts[0].strip() if parts else None

    def _on_municipio_changed(self, choice):
        self._trigger_preview_update()

    def _on_profile_changed(self, choice):
        if choice == "Personalizado...":
            if not self.inspector or not self.inspector.columns:
                messagebox.showwarning("Aviso", "Carregue um arquivo antes de selecionar colunas personalizadas.")
                self.profile_combo.set("Completo (Todas as Colunas)")
                return

            def on_save_cols(selected):
                self.custom_columns = selected
                self._trigger_preview_update()

            current_sel = self.custom_columns if self.custom_columns else self.inspector.columns
            ColumnSelectorDialog(self, self.inspector.columns, current_sel, self.dict_parser, on_save_cols)
        else:
            self.custom_columns = None
            self._trigger_preview_update()

    def _trigger_preview_update(self, *args):
        if self.current_file_path:
            self._update_preview()

    def _update_preview(self):
        if not self.current_file_path:
            return

        self._set_ui_state(busy=True, message="Gerando pré-visualização e calculando estatísticas...")
        threading.Thread(target=self._preview_worker, daemon=True).start()

    def _preview_worker(self):
        try:
            params = self._gather_engine_params()
            params["limite_linhas"] = 30  # Amostra rápida para a tabela

            df_sample, metrics = self.data_engine.process_data(**params)

            def update_ui():
                self.preview_table.load_dataframe(df_sample)
                self._update_stat_cards(metrics)
                self._set_ui_state(busy=False, message=f"Prévia atualizada: {len(df_sample)} linhas exibidas.")

            self.after(0, update_ui)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro na pré-visualização", str(e)))
            self.after(0, lambda: self._set_ui_state(busy=False, message="Erro ao gerar pré-visualização."))

    def _update_stat_cards(self, metrics: Dict[str, Any]):
        tot_pes = metrics.get("total_pessoas", 0)
        tot_fam = metrics.get("total_familias", 0)
        pbf_pct = metrics.get("pbf_percentual", 0.0)
        pbf_tot = metrics.get("pbf_beneficiarios", 0)
        desat_pct = metrics.get("desatualizados_percentual", 0.0)
        desat_tot = metrics.get("desatualizados_total", 0)
        renda = metrics.get("renda_media_rfpc", 0.0)

        self.card_pessoas.update_value(f"{tot_pes:,}".replace(",", "."), "Na amostra atual")
        self.card_familias.update_value(f"{tot_fam:,}".replace(",", "."), "Famílias")
        self.card_pbf.update_value(f"{pbf_pct:.1f}%", f"{pbf_tot:,} beneficiários".replace(",", "."))
        self.card_desat.update_value(f"{desat_pct:.1f}%", f"{desat_tot:,} desatualizados".replace(",", "."))
        self.card_renda.update_value(f"R$ {renda:.2f}".replace(".", ","), "Média familiar")

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
            "municipio_ibge": self._get_selected_ibge(),
            "granularidade": granularidade,
            "perfil_colunas": perfil_key,
            "colunas_customizadas": self.custom_columns,
            "filtro_pbf": filtro_pbf,
            "filtro_atualizacao": filtro_desat,
            "filtro_renda": filtro_renda,
            "modo_lgpd": bool(self.lgpd_switch.get()),
            "header_mode": header_mode
        }

    def _start_export(self, format_type: str):
        if not self.current_file_path:
            messagebox.showwarning("Aviso", "Selecione um arquivo CECAD antes de exportar.")
            return

        ibge = self._get_selected_ibge()
        mun_label = f"municipio_{ibge}" if ibge else "base"
        def_filename = f"cecad_traduzido_{mun_label}.{format_type}"

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

        self._set_ui_state(busy=True, message=f"Exportando dados para {format_type.upper()}...")
        threading.Thread(target=self._export_worker, args=(format_type, output_path), daemon=True).start()

    def _export_worker(self, format_type: str, output_path: str):
        try:
            params = self._gather_engine_params()

            def progress_hook(pct, msg):
                self.after(0, lambda: self.progress_bar.set(pct))
                self.after(0, lambda: self.status_label.configure(text=msg))

            params["progress_callback"] = progress_hook
            df_full, metrics = self.data_engine.process_data(**params)

            if df_full.empty:
                self.after(0, lambda: messagebox.showwarning("Aviso", "Nenhum registro encontrado para os filtros selecionados."))
                self.after(0, lambda: self._set_ui_state(busy=False, message="Exportação vazia."))
                return

            if format_type == "xlsx":
                DataExporter.export_to_excel(df_full, output_path, progress_callback=progress_hook)
            else:
                DataExporter.export_to_csv(df_full, output_path, progress_callback=progress_hook)

            def on_complete():
                self._set_ui_state(busy=False, message=f"Arquivo gerado com sucesso: {os.path.basename(output_path)}")
                messagebox.showinfo(
                    "Exportação Concluída",
                    f"Arquivo salvo com sucesso!\n\n"
                    f"Total de Registros: {len(df_full):,}\n"
                    f"Local: {output_path}".replace(",", ".")
                )

            self.after(0, on_complete)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro na exportação", str(e)))
            self.after(0, lambda: self._set_ui_state(busy=False, message="Falha durante a exportação."))

    def _set_ui_state(self, busy: bool, message: str = ""):
        state = "disabled" if busy else "normal"
        self.browse_btn.configure(state=state)
        self.export_excel_btn.configure(state=state)
        self.export_csv_btn.configure(state=state)
        self.refresh_btn.configure(state=state)
        if message:
            self.status_label.configure(text=message)
        if not busy:
            self.progress_bar.set(0.0)
