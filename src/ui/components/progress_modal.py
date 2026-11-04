"""
Componente visual de Diálogo Modal de Progresso (ProgressModal).
Bloqueia interações na janela principal enquanto operações pesadas são executadas.
"""

from typing import Optional
import customtkinter as ctk


class ProgressModal(ctk.CTkToplevel):
    """
    Janela modal bloqueadora que exibe barra de progresso e status.
    Impede que o usuário interaja com a janela pai enquanto um processo estiver rodando.
    """

    def __init__(
        self,
        parent,
        title: str = "Processando Dados",
        message: str = "Aguarde enquanto os dados estão sendo processados...",
        indeterminate: bool = False
    ):
        super().__init__(parent)

        self.parent = parent
        self.title(title)
        self.geometry("480x200")
        self.resizable(False, False)

        # Configurações de modalidade rígida
        self.transient(parent)
        self.grab_set()
        self.focus_force()

        # Impede fechamento acidental pelo botão 'X' da janela
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self._build_ui(title, message, indeterminate)
        self._center_window()

    def _build_ui(self, title: str, message: str, indeterminate: bool):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=20)

        # Título
        self.title_label = ctk.CTkLabel(
            container,
            text=f"⏳ {title}",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.title_label.pack(fill="x", pady=(0, 8))

        # Mensagem descritiva de status
        self.status_label = ctk.CTkLabel(
            container,
            text=message,
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
            anchor="w",
            wraplength=430,
            justify="left"
        )
        self.status_label.pack(fill="x", pady=(0, 14))

        # Barra de Progresso
        self.progress_bar = ctk.CTkProgressBar(container, height=14)
        self.progress_bar.pack(fill="x", pady=(0, 6))

        # Rótulo de porcentagem
        self.percent_label = ctk.CTkLabel(
            container,
            text="0%" if not indeterminate else "Em processamento...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#1E3A8A", "#60A5FA"),
            anchor="e"
        )
        self.percent_label.pack(fill="x")

        if indeterminate:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
        else:
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0.0)

    def _center_window(self):
        self.update_idletasks()
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()

            dialog_w = 480
            dialog_h = 200

            x = parent_x + max(0, (parent_w - dialog_w) // 2)
            y = parent_y + max(0, (parent_h - dialog_h) // 2)

            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        except Exception:
            pass

    def update_progress(self, fraction: float, message: str = ""):
        """Atualiza a barra de progresso (0.0 a 1.0) e a mensagem de status."""
        def _update():
            clamped = max(0.0, min(1.0, fraction))
            self.progress_bar.set(clamped)
            self.percent_label.configure(text=f"{int(clamped * 100)}%")
            if message:
                self.status_label.configure(text=message)
        self.after(0, _update)

    def set_message(self, message: str):
        """Atualiza apenas a mensagem de status."""
        self.after(0, lambda: self.status_label.configure(text=message))

    def _on_close_attempt(self):
        """Ignora tentativa de fechar a janela enquanto o processo estiver em execução."""
        pass

    def close(self):
        """Libera o grab e destrói o diálogo com segurança."""
        def _do_close():
            try:
                self.grab_release()
            except Exception:
                pass
            try:
                self.destroy()
            except Exception:
                pass
        self.after(0, _do_close)
