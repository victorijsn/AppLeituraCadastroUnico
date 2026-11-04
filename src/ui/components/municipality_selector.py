"""
Diálogo modal para seleção múltipla de municípios com monitoramento em tempo real do limite do Excel.
"""

from typing import List, Dict, Any, Callable, Set
import customtkinter as ctk

EXCEL_MAX_ROWS = 1_048_575


class MunicipalitySelectorDialog(ctk.CTkToplevel):
    """
    Diálogo modal para selecionar múltiplos municípios em bases estaduais.
    Exibe contagem individual e alerta visual sobre o limite do Excel.
    """

    def __init__(
        self,
        parent,
        municipalities: List[Dict[str, Any]],
        selected_ibges: List[str],
        on_confirm: Callable[[List[str]], None]
    ):
        super().__init__(parent)

        self.parent = parent
        self.municipalities = municipalities
        self.selected_set: Set[str] = set(selected_ibges) if selected_ibges else set()
        self.on_confirm = on_confirm

        # Mapeia cd_ibge para contagem
        self.counts_map = {str(m["cd_ibge"]).strip(): m.get("contagem", 0) for m in municipalities}

        self.title("Seleção de Municípios — Base CECAD")
        self.geometry("700x620")
        self.minsize(580, 500)

        self.transient(parent)
        self.grab_set()

        self.checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.check_vars: Dict[str, ctk.BooleanVar] = {}

        self._build_ui()
        self._center_window()
        self._update_summary()

    def _center_window(self):
        self.update_idletasks()
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()

            dialog_w = 700
            dialog_h = 620

            x = parent_x + max(0, (parent_w - dialog_w) // 2)
            y = parent_y + max(0, (parent_h - dialog_h) // 2)

            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self):
        # 1. Cabeçalho
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            top_frame,
            text="🏙️ Seleção de Municípios da Base Estadual",
            font=ctk.CTkFont(size=17, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_frame,
            text="Selecione os municípios desejados. Acompanhe a estimativa total em relação ao limite do Excel.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", pady=(2, 0))

        # 2. Painel de Capacidade do Excel
        self.capacity_frame = ctk.CTkFrame(self, corner_radius=8)
        self.capacity_frame.pack(fill="x", padx=20, pady=8)

        cap_header = ctk.CTkFrame(self.capacity_frame, fg_color="transparent")
        cap_header.pack(fill="x", padx=14, pady=(10, 4))

        self.tally_label = ctk.CTkLabel(
            cap_header,
            text="Total Selecionado: 0 registros (0,0% do limite Excel)",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.tally_label.pack(side="left")

        self.limit_badge = ctk.CTkLabel(
            cap_header,
            text="Limite Excel: 1.048.575 linhas",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        self.limit_badge.pack(side="right")

        self.capacity_bar = ctk.CTkProgressBar(self.capacity_frame, height=10)
        self.capacity_bar.pack(fill="x", padx=14, pady=(2, 6))
        self.capacity_bar.set(0.0)

        self.warning_label = ctk.CTkLabel(
            self.capacity_frame,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#DC2626"
        )
        self.warning_label.pack(anchor="w", padx=14, pady=(0, 8))

        # 3. Barra de Busca e Botões Rápidos
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", padx=20, pady=6)

        self.search_entry = ctk.CTkEntry(
            actions_frame,
            placeholder_text="🔍 Filtrar municípios por nome ou código IBGE...",
            width=280
        )
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(
            actions_frame,
            text="Marcar Todos",
            width=100,
            command=self._select_all
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            actions_frame,
            text="Desmarcar Todos",
            width=110,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self._deselect_all
        ).pack(side="left", padx=4)

        # 4. Lista Rolável de Municípios
        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=8)

        self._populate_list(self.municipalities)

        # 5. Barra Inferior de Ações
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(10, 18))

        self.confirm_btn = ctk.CTkButton(
            bottom_frame,
            text="Confirmar Seleção",
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            height=34,
            command=self._save_and_close
        )
        self.confirm_btn.pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            bottom_frame,
            text="Cancelar",
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            height=34,
            command=self.destroy
        ).pack(side="right")

    def _populate_list(self, mun_items: List[Dict[str, Any]]):
        # Limpa widgets anteriores
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()

        for mun in mun_items:
            ibge = str(mun["cd_ibge"]).strip()
            name = mun.get("nome", ibge)
            count = mun.get("contagem", 0)

            label_text = f"{ibge} - {name} ({count:,} registros)".replace(",", ".")

            if ibge not in self.check_vars:
                self.check_vars[ibge] = ctk.BooleanVar(value=(ibge in self.selected_set))

            var = self.check_vars[ibge]
            cb = ctk.CTkCheckBox(
                self.scroll_frame,
                text=label_text,
                variable=var,
                command=lambda b=ibge: self._on_checkbox_toggle(b),
                font=ctk.CTkFont(size=12)
            )
            cb.pack(anchor="w", padx=12, pady=4)
            self.checkboxes[ibge] = cb

    def _on_checkbox_toggle(self, ibge: str):
        if self.check_vars[ibge].get():
            self.selected_set.add(ibge)
        else:
            self.selected_set.discard(ibge)
        self._update_summary()

    def _on_search(self, event=None):
        query = self.search_entry.get().strip().lower()
        if not query:
            filtered = self.municipalities
        else:
            filtered = [
                m for m in self.municipalities
                if query in str(m.get("cd_ibge", "")).lower() or query in str(m.get("nome", "")).lower()
            ]
        self._populate_list(filtered)

    def _select_all(self):
        for ibge in self.counts_map.keys():
            self.selected_set.add(ibge)
            if ibge in self.check_vars:
                self.check_vars[ibge].set(True)
        self._update_summary()

    def _deselect_all(self):
        self.selected_set.clear()
        for var in self.check_vars.values():
            var.set(False)
        self._update_summary()

    def _update_summary(self):
        total_selected_records = sum(self.counts_map.get(ibge, 0) for ibge in self.selected_set)
        num_selected = len(self.selected_set)

        pct = (total_selected_records / EXCEL_MAX_ROWS) * 100.0 if EXCEL_MAX_ROWS > 0 else 0.0
        bar_val = min(1.0, total_selected_records / EXCEL_MAX_ROWS)
        self.capacity_bar.set(bar_val)

        tally_str = (
            f"Selecionados: {num_selected} municípios | "
            f"Total estimado: {total_selected_records:,} registros ({pct:.1f}% do teto Excel)"
        ).replace(",", ".")
        self.tally_label.configure(text=tally_str)

        if total_selected_records > EXCEL_MAX_ROWS:
            self.warning_label.configure(
                text="⚠️ Atenção: A soma ultrapassa o limite de 1.048.575 linhas do Excel! "
                     "Ao exportar em Excel, o arquivo será dividido em abas automáticas (ou recomendamos exportar em CSV)."
            )
            self.capacity_bar.configure(progress_color="#DC2626")
        elif pct >= 80.0:
            self.warning_label.configure(text="ℹ️ Próximo ao limite máximo de uma única planilha Excel.")
            self.capacity_bar.configure(progress_color="#D97706")
        else:
            self.warning_label.configure(text="")
            self.capacity_bar.configure(progress_color=("#1E3A8A", "#3B82F6"))

        self.confirm_btn.configure(text=f"Confirmar Seleção ({num_selected} municípios)")

    def _save_and_close(self):
        selected_list = sorted(list(self.selected_set))
        self.on_confirm(selected_list)
        self.destroy()
