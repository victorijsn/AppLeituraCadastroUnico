"""
Diálogo modal para seleção personalizada de colunas com busca em tempo real.
"""

from typing import List, Dict, Callable
import customtkinter as ctk
from src.core.dictionary_parser import DictionaryParser

class ColumnSelectorDialog(ctk.CTkToplevel):
    """Janela modal para marcar/desmarcar colunas individualmente."""

    def __init__(self, parent, all_columns: List[str], selected_columns: List[str], dict_parser: DictionaryParser, on_save: Callable[[List[str]], None]):
        super().__init__(parent)
        self.title("Seleção Personalizada de Colunas")
        self.geometry("650x550")
        self.transient(parent)
        self.grab_set()

        self.all_columns = all_columns
        self.selected_set = set(selected_columns) if selected_columns else set(all_columns)
        self.dict_parser = dict_parser
        self.on_save = on_save

        self.checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.check_vars: Dict[str, ctk.BooleanVar] = {}

        self._build_ui()

    def _build_ui(self):
        # Cabeçalho
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            top_frame,
            text="Escolha as colunas para exportação",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_frame,
            text="Marque ou desmarque os campos que deseja incluir no arquivo final.",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray50")
        ).pack(anchor="w")

        # Barra de Busca e Ações Rápidas
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", padx=16, pady=8)

        self.search_entry = ctk.CTkEntry(
            actions_frame,
            placeholder_text="🔍 Filtrar colunas por nome ou código...",
            width=300
        )
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(
            actions_frame,
            text="Marcar Todas",
            width=100,
            command=self._select_all
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            actions_frame,
            text="Desmarcar Todas",
            width=110,
            fg_color="gray50",
            hover_color="gray40",
            command=self._deselect_all
        ).pack(side="left", padx=4)

        # Contador
        self.count_label = ctk.CTkLabel(actions_frame, text=f"{len(self.selected_set)} / {len(self.all_columns)} selecionadas")
        self.count_label.pack(side="right")

        # Área rolável de colunas
        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=8)

        self._populate_list(self.all_columns)

        # Botões inferiores
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=16, pady=(8, 16))

        ctk.CTkButton(
            bottom_frame,
            text="Salvar Seleção",
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            width=140,
            command=self._save_and_close
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            bottom_frame,
            text="Cancelar",
            fg_color="transparent",
            border_width=1,
            width=100,
            command=self.destroy
        ).pack(side="right")

    def _populate_list(self, cols_to_display: List[str]):
        # Limpa widgets anteriores
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()

        for col in cols_to_display:
            desc, _ = self.dict_parser.get_field_info(col)
            label_text = f"{col}  —  {desc}" if desc and desc != col else col

            if col not in self.check_vars:
                self.check_vars[col] = ctk.BooleanVar(value=(col in self.selected_set))

            cb = ctk.CTkCheckBox(
                self.scroll_frame,
                text=label_text,
                variable=self.check_vars[col],
                command=self._update_counter,
                font=ctk.CTkFont(size=12)
            )
            cb.pack(anchor="w", padx=8, pady=4, fill="x")
            self.checkboxes[col] = cb

    def _on_search(self, event=None):
        query = self.search_entry.get().strip().lower()
        if not query:
            filtered = self.all_columns
        else:
            filtered = []
            for col in self.all_columns:
                desc, _ = self.dict_parser.get_field_info(col)
                if query in col.lower() or (desc and query in desc.lower()):
                    filtered.append(col)
        self._populate_list(filtered)

    def _select_all(self):
        for col, var in self.check_vars.items():
            var.set(True)
            self.selected_set.add(col)
        self._update_counter()

    def _deselect_all(self):
        for col, var in self.check_vars.items():
            var.set(False)
        self.selected_set.clear()
        self._update_counter()

    def _update_counter(self):
        selected_count = sum(1 for var in self.check_vars.values() if var.get())
        self.count_label.configure(text=f"{selected_count} / {len(self.all_columns)} selecionadas")

    def _save_and_close(self):
        final_selected = [col for col in self.all_columns if self.check_vars[col].get()]
        self.on_save(final_selected)
        self.destroy()
