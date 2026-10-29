"""
Componente visual de Cartão de Estatística (StatCard) para resumo de métricas.
"""

import customtkinter as ctk

class StatCard(ctk.CTkFrame):
    """Card moderno com cantos arredondados para exibir métricas-chave."""

    def __init__(self, parent, title: str, initial_value: str = "-", subtitle: str = "", icon: str = "", **kwargs):
        super().__init__(parent, corner_radius=10, **kwargs)
        self.configure(fg_color=("gray90", "gray17"))

        self.title_label = ctk.CTkLabel(
            self,
            text=f"{icon} {title}".strip(),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray40", "gray60")
        )
        self.title_label.pack(anchor="w", padx=14, pady=(10, 2))

        self.value_label = ctk.CTkLabel(
            self,
            text=initial_value,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=("#1E3A8A", "#60A5FA")
        )
        self.value_label.pack(anchor="w", padx=14, pady=(0, 2))

        self.subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        self.subtitle_label.pack(anchor="w", padx=14, pady=(0, 10))

    def update_value(self, value: str, subtitle: str = ""):
        """Atualiza os valores exibidos no card."""
        self.value_label.configure(text=value)
        if subtitle:
            self.subtitle_label.configure(text=subtitle)
