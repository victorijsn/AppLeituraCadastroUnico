"""
Componente visual de Tabela de Pré-visualização de Dados com scroll horizontal e vertical.
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import pandas as pd

class PreviewTable(ctk.CTkFrame):
    """Tabela moderna para pré-visualização dos registros traduzidos."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=10, **kwargs)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Configura estilo do Treeview
        self._setup_style()

        self.tree = ttk.Treeview(self, show="headings", selectmode="browse")

        # Scrollbars
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=(2, 0), pady=(2, 0))
        self.vsb.grid(row=0, column=1, sticky="ns", pady=(2, 0))
        self.hsb.grid(row=1, column=0, sticky="ew", padx=(2, 0))

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#242424" if is_dark else "#F9FAFB"
        fg_color = "#F3F4F6" if is_dark else "#111827"
        header_bg = "#1E3A8A"
        header_fg = "#FFFFFF"

        style.configure(
            "Treeview",
            background=bg_color,
            foreground=fg_color,
            fieldbackground=bg_color,
            rowheight=26,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading",
            background=header_bg,
            foreground=header_fg,
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        style.map("Treeview.Heading", background=[("active", "#1D4ED8")])
        style.map("Treeview", background=[("selected", "#2563EB")], foreground=[("selected", "#FFFFFF")])

    def load_dataframe(self, df: pd.DataFrame):
        """Carrega e exibe os dados do DataFrame na tabela."""
        self._setup_style()
        self.clear()

        if df.empty:
            return

        columns = list(df.columns)
        self.tree["columns"] = columns

        for col in columns:
            self.tree.heading(col, text=col)
            # Calcula largura baseada no nome da coluna
            col_width = min(max(len(str(col)) * 10, 100), 300)
            self.tree.column(col, width=col_width, minwidth=80, anchor="w")

        # Insere linhas
        for _, row in df.iterrows():
            vals = [str(v) if pd.notna(v) and v is not None else "" for v in row]
            self.tree.insert("", "end", values=vals)

    def clear(self):
        """Limpa todos os dados da tabela."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree["columns"] = []
