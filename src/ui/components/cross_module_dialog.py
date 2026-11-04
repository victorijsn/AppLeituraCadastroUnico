"""
Componente visual de Cruzamento e Diagnóstico Integrado (CECAD × SIBEC).
Audita a defasagem temporal de 2 meses entre as bases, filtra o município alvo
(Afonso Cláudio / ES) e gera a conciliação completa nos 4 Quadrantes Operacionais.
"""

import os
import io
import re
import zipfile
import threading
from typing import Optional, Dict, Any, List, Tuple
from tkinter import filedialog, messagebox
import customtkinter as ctk
import pandas as pd

from src.core.file_inspector import parse_reference_date, get_municipio_nome, IBGE_MAP, FileInspector
from src.ui.components.municipality_selector import MunicipalitySelectorDialog
from src.ui.components.progress_modal import ProgressModal


class CrossModuleDialog(ctk.CTkToplevel):
    """
    Janela modal para configuração e execução do Cruzamento CECAD × SIBEC.
    Permite auditar a defasagem temporal de 2 meses do MDS, selecionar múltiplos municípios
    com nomes amigáveis e gerar relatórios operacionais completos nos 4 Quadrantes.
    """

    def __init__(self, parent, default_cecad: Optional[str] = None, default_sibec: Optional[str] = None):
        super().__init__(parent)

        self.parent = parent
        self.title("🔄 Cruzamento & Diagnóstico Integrado (CECAD × SIBEC)")
        self.geometry("860x730")
        self.minsize(800, 640)

        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self.cecad_path = default_cecad or ""
        self.sibec_path = default_sibec or ""
        self.cross_results: Optional[Dict[str, pd.DataFrame]] = None
        self.cross_metrics: Dict[str, Any] = {}
        self.q_badges: Dict[str, ctk.CTkLabel] = {}

        # Estado de seleção de municípios
        self.available_municipalities: List[Dict[str, Any]] = []
        self.selected_ibges: List[str] = []
        self._nome_to_ibge: Dict[str, str] = {}
        self._ibge_to_nome: Dict[str, str] = {}
        self._load_available_municipalities()

        # Pré-seleção se parent já tiver municípios selecionados
        if hasattr(self.parent, "selected_ibges") and self.parent.selected_ibges:
            self.selected_ibges = list(self.parent.selected_ibges)
        elif self.available_municipalities:
            self.selected_ibges = [str(self.available_municipalities[0]["cd_ibge"]).strip()]

        self._build_ui()
        self._center_window()
        self._update_municipality_ui()

        if self.cecad_path or self.sibec_path:
            self._audit_dates(user_click=False)

    def _center_window(self):
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()

            dialog_w = 860
            dialog_h = 730

            x = parent_x + max(0, (parent_w - dialog_w) // 2)
            y = parent_y + max(0, (parent_h - dialog_h) // 2)

            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self):
        main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=16)

        # 1. Header
        header_box = ctk.CTkFrame(main_container, fg_color="transparent")
        header_box.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            header_box,
            text="🔄 Conciliação Cadastral & Diagnóstico (CECAD × SIBEC)",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_box,
            text="Cruze a base cadastral (CECAD) com a folha de pagamentos (SIBEC) para identificar famílias em risco, novas concessões e busca ativa.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        ).pack(anchor="w", pady=(2, 0))

        # 2. Painel de Ingestão e Filtro de Município
        files_box = ctk.CTkFrame(main_container, corner_radius=10)
        files_box.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            files_box,
            text="📂 1. Seleção dos Arquivos e Território de Cruzamento",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # Linha CECAD
        cecad_row = ctk.CTkFrame(files_box, fg_color="transparent")
        cecad_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(cecad_row, text="Base CECAD (.zip/.csv):", width=180, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self.cecad_entry = ctk.CTkEntry(cecad_row, height=32, placeholder_text="Arquivo da Tab Cadastral do CECAD...")
        self.cecad_entry.pack(side="left", fill="x", expand=True, padx=6)
        if self.cecad_path:
            self.cecad_entry.insert(0, self.cecad_path)
        ctk.CTkButton(cecad_row, text="📁 Procurar", width=90, height=32, command=self._browse_cecad).pack(side="right")

        # Linha SIBEC
        sibec_row = ctk.CTkFrame(files_box, fg_color="transparent")
        sibec_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(sibec_row, text="Folha SIBEC (.CSV):", width=180, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self.sibec_entry = ctk.CTkEntry(sibec_row, height=32, placeholder_text="Arquivo analítico de pagamentos da Caixa/MDS...")
        self.sibec_entry.pack(side="left", fill="x", expand=True, padx=6)
        if self.sibec_path:
            self.sibec_entry.insert(0, self.sibec_path)
        ctk.CTkButton(sibec_row, text="📁 Procurar", width=90, height=32, command=self._browse_sibec).pack(side="right")

        # Linha Seleção de Município(s) de Análise
        mun_row = ctk.CTkFrame(files_box, fg_color="transparent")
        mun_row.pack(fill="x", padx=16, pady=(4, 6))
        ctk.CTkLabel(mun_row, text="Município(s) de Análise:", width=180, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

        self.mun_combo = ctk.CTkComboBox(
            mun_row,
            height=32,
            width=320,
            values=[m["nome"] for m in self.available_municipalities],
            command=self._on_mun_combo_selected
        )
        self.mun_combo.pack(side="left", padx=(0, 8))

        self.select_mun_btn = ctk.CTkButton(
            mun_row,
            text="🔍 Selecionar Municípios...",
            height=32,
            width=180,
            fg_color=("#2563EB", "#1D4ED8"),
            hover_color=("#1D4ED8", "#1E40AF"),
            command=self._open_municipality_selector
        )
        self.select_mun_btn.pack(side="left")

        # Linha de Status de Seleção
        status_row = ctk.CTkFrame(files_box, fg_color="transparent")
        status_row.pack(fill="x", padx=16, pady=(0, 8))

        self.mun_status_label = ctk.CTkLabel(
            status_row,
            text="🏙️ Inicializando municípios...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#1D4ED8", "#60A5FA"),
            anchor="w"
        )
        self.mun_status_label.pack(side="left", fill="x", expand=True)

        # Alias de compatibilidade
        self.mun_name_label = self.mun_status_label

        ctk.CTkLabel(
            files_box,
            text="ℹ️ Selecione um município pelo menu rápido ou clique em 'Selecionar Municípios...' para conciliar múltiplos municípios. Se o arquivo do CECAD for municipal, o município é selecionado automaticamente na leitura.",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
            wraplength=780,
            justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # 3. Painel de Auditoria de Defasagem Temporal
        self.audit_box = ctk.CTkFrame(main_container, corner_radius=10, fg_color=("#F0FDF4", "#052E16"), border_width=1, border_color=("#BBF7D0", "#14532D"))
        self.audit_box.pack(fill="x", pady=(0, 14))

        self.audit_title = ctk.CTkLabel(
            self.audit_box,
            text="⏱️ Auditoria de Defasagem Temporal do MDS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("#166534", "#86EFAC")
        )
        self.audit_title.pack(anchor="w", padx=16, pady=(10, 4))

        self.audit_msg = ctk.CTkLabel(
            self.audit_box,
            text="Carregue ambos os arquivos para auditar automaticamente as datas de competência.",
            font=ctk.CTkFont(size=11),
            text_color=("#15803D", "#A7F3D0"),
            wraplength=780,
            justify="left"
        )
        self.audit_msg.pack(anchor="w", padx=16, pady=(0, 10))

        # 4. Estrutura dos 4 Quadrantes Operacionais
        quad_title_box = ctk.CTkFrame(main_container, fg_color="transparent")
        quad_title_box.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            quad_title_box,
            text="📋 2. Diagnóstico em 4 Quadrantes Operacionais",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w")

        quad_container = ctk.CTkFrame(main_container, fg_color="transparent")
        quad_container.pack(fill="x", pady=(0, 14))
        quad_container.grid_columnconfigure((0, 1), weight=1, pad=10)
        quad_container.grid_rowconfigure((0, 1), weight=1, pad=10)

        # Q1: Compatíveis
        self._build_quadrant_card(
            parent=quad_container, row=0, col=0, q_key="q1",
            icon="✅", title="1. Compatíveis & Regulares",
            desc="Benefício ativo no SIBEC e cadastro com PBF no CECAD.",
            detail="Famílias com situação consolidada em ambas as bases.",
            badge_color=("#166534", "#15803D")
        )

        # Q2: Concessões Recentes
        self._build_quadrant_card(
            parent=quad_container, row=0, col=1, q_key="q2",
            icon="🆕", title="2. Concessões Recentes (Janela 2m)",
            desc="Recebendo na Folha atual, mas sem PBF no CECAD anterior.",
            detail="Explicado pelo intervalo oficial de 2 meses de consolidação do MDS.",
            badge_color=("#1D4ED8", "#2563EB")
        )

        # Q3: Bloqueados / Suspensos
        self._build_quadrant_card(
            parent=quad_container, row=1, col=0, q_key="q3",
            icon="⚠️", title="3. Bloqueados / Suspensos Recentes",
            desc="Benefício retido no SIBEC atual. Notificação imediata pelo CRAS.",
            detail="Enriquecido com endereço e telefone completos do CECAD.",
            badge_color=("#991B1B", "#DC2626")
        )

        # Q4: Busca Ativa CRAS
        self._build_quadrant_card(
            parent=quad_container, row=1, col=1, q_key="q4",
            icon="⏳", title="4. Risco de Bloqueio (Busca Ativa)",
            desc="Recebendo PBF, porém com CadÚnico desatualizado (> 2 anos).",
            detail="Permite visita domiciliar do CRAS antes do bloqueio pelo MDS.",
            badge_color=("#D97706", "#B45309")
        )

        # 5. Botões de Ação
        btn_box = ctk.CTkFrame(main_container, fg_color="transparent")
        btn_box.pack(fill="x", pady=(10, 4))

        ctk.CTkButton(
            btn_box,
            text="Fechar",
            width=100,
            height=38,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self.destroy
        ).pack(side="left")

        self.audit_btn = ctk.CTkButton(
            btn_box,
            text="🔍 Auditar Datas",
            width=150,
            height=38,
            command=lambda: self._audit_dates(user_click=True)
        )
        self.audit_btn.pack(side="left", padx=10)

        self.export_btn = ctk.CTkButton(
            btn_box,
            text="📊 Exportar Relatório (.xlsx)",
            width=210,
            height=38,
            fg_color="#047857",
            hover_color="#059669",
            state="disabled",
            command=self._export_results
        )
        self.export_btn.pack(side="right", padx=(6, 0))

        self.run_btn = ctk.CTkButton(
            btn_box,
            text="🚀 Executar Cruzamento",
            width=210,
            height=38,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            command=self._start_cross_analysis
        )
        self.run_btn.pack(side="right", padx=6)

    def _build_quadrant_card(self, parent, row: int, col: int, q_key: str, icon: str, title: str, desc: str, detail: str, badge_color: Tuple[str, str]):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color=("white", "gray19"), border_width=1, border_color=("gray85", "gray28"))
        card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        box = ctk.CTkFrame(card, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=12, pady=10)

        t_row = ctk.CTkFrame(box, fg_color="transparent")
        t_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(t_row, text=icon, font=ctk.CTkFont(size=18)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(t_row, text=title, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        badge = ctk.CTkLabel(
            t_row,
            text="- Famílias",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
            fg_color=badge_color[0],
            corner_radius=6,
            padx=8,
            pady=2
        )
        badge.pack(side="right")
        self.q_badges[q_key] = badge

        ctk.CTkLabel(box, text=desc, font=ctk.CTkFont(size=11), text_color=("gray30", "gray70"), wraplength=340, justify="left").pack(anchor="w", pady=(0, 3))
        ctk.CTkLabel(box, text=f"• {detail}", font=ctk.CTkFont(size=10), text_color=("gray45", "gray60"), wraplength=340, justify="left").pack(anchor="w")

    def _load_available_municipalities(self, uf_code: str = "32"):
        """Carrega lista de municípios disponíveis a partir do parent ou do mapa oficial do IBGE."""
        if hasattr(self.parent, "municipalities") and len(self.parent.municipalities) > 1:
            self.available_municipalities = list(self.parent.municipalities)
        else:
            mun_list = []
            for ibge, nome in IBGE_MAP.items():
                if not uf_code or ibge.startswith(uf_code):
                    mun_list.append({"cd_ibge": ibge, "nome": nome, "contagem": 0})
            mun_list.sort(key=lambda x: x["nome"])

            # Se o parent tiver contagem de 1 município, incorpora
            if hasattr(self.parent, "municipalities") and len(self.parent.municipalities) == 1:
                single_m = self.parent.municipalities[0]
                s_ibge = str(single_m["cd_ibge"]).strip()
                for m in mun_list:
                    if str(m["cd_ibge"]).strip() == s_ibge:
                        m["contagem"] = single_m.get("contagem", 0)
                        break

            self.available_municipalities = mun_list

        self._nome_to_ibge = {m["nome"]: str(m["cd_ibge"]).strip() for m in self.available_municipalities}
        self._ibge_to_nome = {str(m["cd_ibge"]).strip(): m["nome"] for m in self.available_municipalities}

    @property
    def mun_entry(self):
        """Shim de compatibilidade para código ou testes legados que acessam diag.mun_entry."""
        dialog = self
        class _EntryShim:
            def get(self_s):
                return dialog.selected_ibges[0] if dialog.selected_ibges else ""
            def delete(self_s, first, last=None):
                pass
            def insert(self_s, index, string):
                val = str(string).strip()
                if val:
                    dialog.selected_ibges = [val]
                    dialog._update_municipality_ui()
        return _EntryShim()

    def _update_municipality_ui(self):
        """Atualiza o ComboBox de seleção rápida e o rótulo de status com os municípios selecionados."""
        if not hasattr(self, "mun_combo") or not hasattr(self, "mun_status_label"):
            return

        combo_values = [m["nome"] for m in self.available_municipalities]
        self.mun_combo.configure(values=combo_values)

        if len(self.selected_ibges) == 1:
            ibge = self.selected_ibges[0]
            nome = self._ibge_to_nome.get(ibge, get_municipio_nome(ibge))
            self.mun_combo.set(nome)
            self.mun_status_label.configure(
                text=f"✅ 1 município selecionado: {ibge} - {nome}",
                text_color=("#166534", "#86EFAC")
            )
        elif len(self.selected_ibges) > 1:
            self.mun_combo.set(f"({len(self.selected_ibges)} municípios selecionados)")
            nomes = [self._ibge_to_nome.get(i, get_municipio_nome(i)) for i in self.selected_ibges]
            desc = f"✅ {len(self.selected_ibges)} municípios selecionados: {', '.join(nomes[:3])}{'...' if len(nomes) > 3 else ''}"
            self.mun_status_label.configure(text=desc, text_color=("#1D4ED8", "#60A5FA"))
        else:
            self.mun_combo.set("Selecione um município...")
            self.mun_status_label.configure(
                text="⚠️ Nenhum município selecionado. Escolha na lista ou clique em Selecionar Municípios.",
                text_color="#DC2626"
            )

    def _on_mun_combo_selected(self, choice: str):
        if choice in self._nome_to_ibge:
            ibge = self._nome_to_ibge[choice]
            self.selected_ibges = [ibge]
            self._update_municipality_ui()

    def _open_municipality_selector(self):
        def on_confirm(selected: List[str]):
            if selected:
                self.selected_ibges = selected
            self._update_municipality_ui()

        MunicipalitySelectorDialog(
            parent=self,
            municipalities=self.available_municipalities,
            selected_ibges=self.selected_ibges,
            on_confirm=on_confirm
        )

    def _on_mun_entry_changed(self, event=None):
        self._update_municipality_ui()

    def _browse_cecad(self):
        f = filedialog.askopenfilename(
            title="Selecione o arquivo da base CECAD",
            filetypes=[("Base CECAD (*.zip, *.csv)", "*.zip;*.csv"), ("Todos os Arquivos", "*.*")]
        )
        if f:
            self.cecad_entry.delete(0, "end")
            self.cecad_entry.insert(0, f)
            self._audit_dates(user_click=True)

    def _browse_sibec(self):
        f = filedialog.askopenfilename(
            title="Selecione a Folha de Pagamento SIBEC",
            filetypes=[("Folha SIBEC (*.csv, *.CSV)", "*.csv;*.CSV"), ("Todos os Arquivos", "*.*")]
        )
        if f:
            self.sibec_entry.delete(0, "end")
            self.sibec_entry.insert(0, f)
            self._audit_dates(user_click=True)

    def _detect_municipality_from_cecad(self, c_path: str) -> Optional[Tuple[bool, str]]:
        """
        Detecta se o arquivo do CECAD é de município único.
        Retorna (is_single, cd_ibge) ou None se não for identificado.
        """
        # 1. Se o parent possui inspeção prévia
        if hasattr(self.parent, "inspector_info") and self.parent.inspector_info:
            if self.parent.inspector_info.get("is_single"):
                muns = self.parent.inspector_info.get("municipalities", [])
                if muns:
                    return True, str(muns[0]["cd_ibge"]).strip()

        # 2. Padrão no nome do arquivo com 7 dígitos (ex: tab_cad_..._3200102_... ou cecad_3200102.zip)
        base_name = os.path.basename(c_path)
        m = re.search(r'[._-](\d{7})[._-]', base_name)
        if m and m.group(1) in IBGE_MAP:
            return True, m.group(1)

        # 3. Amostragem rápida das primeiras linhas
        try:
            insp = FileInspector(c_path)
            is_single, muns = insp.scan_municipalities(max_lines=3000)
            if is_single and muns:
                return True, str(muns[0]["cd_ibge"]).strip()
        except Exception:
            pass

        return None

    def _detect_municipality_from_sibec(self, s_path: str) -> Optional[str]:
        # Tenta pelo nome do arquivo: ex: .A3200102.
        m = re.search(r'\.A(\d{7})\.', os.path.basename(s_path))
        if m:
            return m.group(1)
        m2 = re.search(r'32\d{5}', os.path.basename(s_path))
        if m2:
            return m2.group(0)

        # Tenta ler a primeira linha do arquivo
        try:
            stream, parent_zip = self._open_file_stream(s_path)
            try:
                line_bytes = stream.readline()
                header = line_bytes.decode("latin1").strip().split(";")
                norm_h = [c.strip().lower() for c in header]
                idx_ibge = None
                for i, c in enumerate(norm_h):
                    if "ibge" in c or "codigo municipio" in c:
                        idx_ibge = i
                        break
                if idx_ibge is not None:
                    data_bytes = stream.readline()
                    if data_bytes:
                        d_fields = data_bytes.decode("latin1").split(";")
                        if idx_ibge < len(d_fields):
                            val = d_fields[idx_ibge].strip()
                            if len(val) == 7 and val.isdigit():
                                return val
            finally:
                stream.close()
                if parent_zip:
                    parent_zip.close()
        except Exception:
            pass

        return None

    def _audit_dates(self, user_click: bool = False):
        c_path = self.cecad_entry.get().strip()
        s_path = self.sibec_entry.get().strip()

        # Detecção de município único no CECAD: se for base de 1 município, seleciona automaticamente!
        if c_path and os.path.exists(c_path):
            cecad_detect = self._detect_municipality_from_cecad(c_path)
            if cecad_detect and cecad_detect[0]:
                single_ibge = cecad_detect[1]
                self.selected_ibges = [single_ibge]
                self._update_municipality_ui()

        # Detecção de município pelo SIBEC (ex: Afonso Cláudio em SIBEC municipal)
        if s_path and os.path.exists(s_path):
            det_ibge = self._detect_municipality_from_sibec(s_path)
            if det_ibge and (not self.selected_ibges or len(self.selected_ibges) > 1 or self.selected_ibges[0] not in self._ibge_to_nome):
                self.selected_ibges = [det_ibge]
                self._update_municipality_ui()

        if not c_path or not s_path:
            self.audit_box.configure(fg_color=("#FEF3C7", "#451A03"), border_color=("#FDE68A", "#78350F"))
            self.audit_title.configure(text="⚠️ Seleção Incompleta", text_color=("#92400E", "#FCD34D"))
            self.audit_msg.configure(text="Por favor, selecione tanto o arquivo do CECAD quanto o arquivo da Folha SIBEC para realizar a checagem temporal.", text_color=("#B45309", "#FDE68A"))
            return

        # Extrai data CECAD
        cecad_date_str = ""
        try:
            c_info = parse_reference_date(os.path.basename(c_path))
            cecad_date_str = c_info.get("base_mes_ano", "")
        except Exception:
            pass

        # Extrai data SIBEC (ex: C2610 -> 10/2026)
        sibec_date_str = ""
        m_sibec = re.search(r'C(\d{2})(\d{2})', os.path.basename(s_path))
        if m_sibec:
            ano_s, mes_s = m_sibec.groups()
            sibec_date_str = f"{mes_s}/20{ano_s}"
        else:
            m_sibec2 = re.search(r'(\d{4})(\d{2})', os.path.basename(s_path))
            if m_sibec2:
                ano_s, mes_s = m_sibec2.groups()
                sibec_date_str = f"{mes_s}/{ano_s}"

        # Calcula defasagem se tivermos ambas as datas
        if cecad_date_str and sibec_date_str:
            try:
                c_mes, c_ano = [int(x) for x in cecad_date_str.split("/")]
                s_mes, s_ano = [int(x) for x in sibec_date_str.split("/")]
                diff_months = (s_ano - c_ano) * 12 + (s_mes - c_mes)

                if diff_months == 2:
                    self.audit_box.configure(fg_color=("#F0FDF4", "#052E16"), border_color=("#BBF7D0", "#14532D"))
                    self.audit_title.configure(
                        text=f"✅ Defasagem Padrão Identificada: {diff_months} Meses (Normal MDS)",
                        text_color=("#166534", "#86EFAC")
                    )
                    self.audit_msg.configure(
                        text=f"CECAD ({cecad_date_str}) vs Folha SIBEC ({sibec_date_str}) = Intervalo exato de 2 meses.\n"
                             f"Esta é a defasagem operacional habitual do MDS. Clique em '🚀 Executar Cruzamento' abaixo para calcular os 4 Quadrantes.",
                        text_color=("#15803D", "#A7F3D0")
                    )
                elif 0 <= diff_months <= 3:
                    self.audit_box.configure(fg_color=("#EFF6FF", "#172554"), border_color=("#BFDBFE", "#1E40AF"))
                    self.audit_title.configure(
                        text=f"ℹ️ Defasagem Aceitável: {diff_months} Mês(es)",
                        text_color=("#1E40AF", "#93C5FD")
                    )
                    self.audit_msg.configure(
                        text=f"CECAD ({cecad_date_str}) vs Folha SIBEC ({sibec_date_str}) = Diferença de {diff_months} mês(es).\n"
                             f"As bases são compatíveis para cruzamento. Clique em '🚀 Executar Cruzamento' para processar.",
                        text_color=("#2563EB", "#BFDBFE")
                    )
                else:
                    self.audit_box.configure(fg_color=("#FEF2F2", "#450A0A"), border_color=("#FECACA", "#991B1B"))
                    self.audit_title.configure(
                        text=f"⚠️ Defasagem Atípica: {diff_months} Meses",
                        text_color=("#991B1B", "#FCA5A5")
                    )
                    self.audit_msg.configure(
                        text=f"CECAD ({cecad_date_str}) vs Folha SIBEC ({sibec_date_str}) = Diferença de {diff_months} meses.\n"
                             f"Recomenda-se utilizar versões mais próximas para evitar divergências cadastrais.",
                        text_color=("#B91C1C", "#F87171")
                    )

                if user_click:
                    messagebox.showinfo(
                        "Auditoria de Competências Concluída",
                        f"Auditoria realizada com sucesso!\n\n"
                        f"• Competência CECAD: {cecad_date_str}\n"
                        f"• Competência SIBEC: {sibec_date_str}\n"
                        f"• Intervalo Temporal: {diff_months} meses\n"
                        f"• Município Vinculado: {self.mun_name_label.cget('text')}\n\n"
                        "Tudo pronto! Clique em '🚀 Executar Cruzamento' para gerar o diagnóstico."
                    )
                return
            except Exception:
                pass

        # Fallback
        self.audit_box.configure(fg_color=("#F0FDF4", "#052E16"), border_color=("#BBF7D0", "#14532D"))
        self.audit_title.configure(
            text="✅ Arquivos Carregados para Conciliação",
            text_color=("#166534", "#86EFAC")
        )
        self.audit_msg.configure(
            text=f"CECAD: {os.path.basename(c_path)} | SIBEC: {os.path.basename(s_path)}\n"
                 "Clique em '🚀 Executar Cruzamento' para cruzar as bases e consolidar os 4 Quadrantes.",
            text_color=("#15803D", "#A7F3D0")
        )

    def _open_file_stream(self, file_path: str):
        if zipfile.is_zipfile(file_path):
            z = zipfile.ZipFile(file_path, "r")
            csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not csvs:
                raise ValueError(f"Nenhum arquivo .csv encontrado no ZIP: {file_path}")
            return z.open(csvs[0], "r"), z
        else:
            return open(file_path, "rb"), None

    # ==========================================
    # EXECUÇÃO DO CRUZAMENTO (BACKGROUND THREAD)
    # ==========================================
    def _start_cross_analysis(self):
        c_path = self.cecad_entry.get().strip()
        s_path = self.sibec_entry.get().strip()

        if not c_path or not os.path.exists(c_path):
            messagebox.showwarning("Aviso", "Por favor, selecione um arquivo válido do CECAD.")
            return

        if not s_path or not os.path.exists(s_path):
            messagebox.showwarning("Aviso", "Por favor, selecione um arquivo válido da Folha SIBEC.")
            return

        if not self.selected_ibges:
            messagebox.showwarning("Aviso", "Selecione ao menos um município para o cruzamento.")
            return

        target_ibges = list(self.selected_ibges)
        if len(target_ibges) == 1:
            nome_display = f"{target_ibges[0]} - {get_municipio_nome(target_ibges[0])}"
        else:
            nome_display = f"{len(target_ibges)} municípios selecionados"

        modal = ProgressModal(
            self,
            title="Cruzamento de Dados CECAD × SIBEC",
            message=f"Iniciando conciliação para {nome_display}...",
            indeterminate=False
        )

        threading.Thread(
            target=self._run_cross_analysis_worker,
            args=(modal, c_path, s_path, target_ibges, nome_display),
            daemon=True
        ).start()

    def _run_cross_analysis_worker(self, modal: ProgressModal, c_path: str, s_path: str, target_ibges: Any = None, mun_nome: Optional[str] = None):
        try:
            # Normalização dos códigos IBGE alvo (suporta único ou lista)
            if target_ibges is None:
                target_list = list(self.selected_ibges)
            elif isinstance(target_ibges, str):
                target_list = [target_ibges]
            elif isinstance(target_ibges, (list, set, tuple)):
                target_list = list(target_ibges)
            else:
                target_list = list(self.selected_ibges)

            target_set = set(str(x).strip() for x in target_list if str(x).strip())
            if not target_set:
                target_set = {"3200102"}
                target_list = ["3200102"]

            if len(target_set) == 1:
                single_code = list(target_set)[0]
                display_mun_str = f"{single_code} - {get_municipio_nome(single_code)}"
            else:
                nomes_sel = [get_municipio_nome(c) for c in sorted(target_set)]
                display_mun_str = f"{len(target_set)} municípios ({', '.join(nomes_sel[:3])}{'...' if len(nomes_sel) > 3 else ''})"

            # ----------------------------------------------------
            # ETAPA 1: Processa SIBEC (Linhas Família RF)
            # ----------------------------------------------------
            modal.update_progress(0.10, f"Lendo folha SIBEC ({display_mun_str})...")

            stream_s, zip_s = self._open_file_stream(s_path)
            sibec_families: List[Dict[str, Any]] = []

            try:
                line_bytes = stream_s.readline()
                header_str = line_bytes.decode("latin1").strip()
                delim_s = ";" if ";" in header_str else ","
                h_cols = [c.strip().strip('"').upper() for c in header_str.split(delim_s)]

                def find_s_idx(candidates):
                    for cand in candidates:
                        cand_u = cand.upper()
                        for i, c in enumerate(h_cols):
                            if cand_u == c or cand_u in c:
                                return i
                    return None

                idx_s_ibge = find_s_idx(["IBGE", "CODIGO MUNICIPIO IBGE", "CD_IBGE"])
                idx_s_cod = find_s_idx(["COD_FAMILIAR", "COD_FAMILIAR_FAM"])
                idx_s_nis = find_s_idx(["NIS", "NIS BENEFICIARIO", "NUM_NIS_BENEFICIARIO", "NIS FAVORECIDO"])
                idx_s_nom = find_s_idx(["NOME", "NOME BENEFICIARIO", "NOM_BENEFICIARIO", "NOME FAVORECIDO"])
                idx_s_cpf = find_s_idx(["CPF", "NUM_CPF"])
                idx_s_rf = find_s_idx(["MARCA_RF", "MARCA RF"])
                idx_s_sit = find_s_idx(["SITFAM", "SIT_FAM", "SITBENEFICIO", "SITUACAO"])
                idx_s_vlr = find_s_idx(["VLRTOTAL", "VLR_TOTAL", "VALOR PARCELA", "VLRBENEF"])
                idx_s_dt = find_s_idx(["DT_ATU_CADASTRAL", "DT ATU CADASTRAL", "DATA_ATUALIZACAO"])
                idx_s_end = find_s_idx(["ENDERECO", "END"])
                idx_s_bai = find_s_idx(["BAIRRO"])
                idx_s_cep = find_s_idx(["CEP"])
                idx_s_tel = find_s_idx(["TELEFONE1", "TEL1"])

                reader_s = io.BufferedReader(stream_s, buffer_size=1024 * 1024 * 8)
                for line in reader_s:
                    s_str = line.decode("latin1").rstrip("\r\n")
                    flds = [f.strip().strip('"') for f in s_str.split(delim_s)]

                    # Filtro territorial se a coluna de IBGE existir
                    s_code = ""
                    if idx_s_ibge is not None and idx_s_ibge < len(flds):
                        s_code = flds[idx_s_ibge].strip()
                        if s_code and s_code not in target_set:
                            continue

                    # Filtra apenas linha master do Responsável Familiar se existir
                    if idx_s_rf is not None and idx_s_rf < len(flds):
                        if flds[idx_s_rf].strip().upper() != "S":
                            continue

                    cod_fam = flds[idx_s_cod].strip() if idx_s_cod is not None and idx_s_cod < len(flds) else ""
                    nis_val = flds[idx_s_nis].strip() if idx_s_nis is not None and idx_s_nis < len(flds) else ""
                    nom_val = flds[idx_s_nom].strip() if idx_s_nom is not None and idx_s_nom < len(flds) else ""
                    cpf_val = flds[idx_s_cpf].strip() if idx_s_cpf is not None and idx_s_cpf < len(flds) else ""
                    sit_val = flds[idx_s_sit].strip() if idx_s_sit is not None and idx_s_sit < len(flds) else ""
                    vlr_val = flds[idx_s_vlr].strip() if idx_s_vlr is not None and idx_s_vlr < len(flds) else ""
                    dt_val = flds[idx_s_dt].strip() if idx_s_dt is not None and idx_s_dt < len(flds) else ""
                    end_val = flds[idx_s_end].strip() if idx_s_end is not None and idx_s_end < len(flds) else ""
                    bai_val = flds[idx_s_bai].strip() if idx_s_bai is not None and idx_s_bai < len(flds) else ""
                    cep_val = flds[idx_s_cep].strip() if idx_s_cep is not None and idx_s_cep < len(flds) else ""
                    tel_val = flds[idx_s_tel].strip() if idx_s_tel is not None and idx_s_tel < len(flds) else ""

                    sibec_families.append({
                        "ibge": s_code,
                        "cod_familiar": cod_fam,
                        "nis": nis_val,
                        "nome": nom_val,
                        "cpf": cpf_val,
                        "situacao_sibec": sit_val,
                        "valor_sibec": vlr_val,
                        "dt_atualizacao": dt_val,
                        "endereco_sibec": end_val,
                        "bairro_sibec": bai_val,
                        "cep_sibec": cep_val,
                        "telefone_sibec": tel_val
                    })

            finally:
                stream_s.close()
                if zip_s:
                    zip_s.close()

            # ----------------------------------------------------
            # ETAPA 2: Processa CECAD (Filtrando Municípios Alvo)
            # ----------------------------------------------------
            modal.update_progress(0.40, f"Filtrando base CECAD para {display_mun_str}...")

            stream_c, zip_c = self._open_file_stream(c_path)
            cecad_by_cod: Dict[str, Dict[str, Any]] = {}
            cecad_by_nis: Dict[str, Dict[str, Any]] = {}

            try:
                line_bytes = stream_c.readline()
                header_str = line_bytes.decode("latin1").strip()
                delim_c = ";" if ";" in header_str else ","
                h_cols_c = [c.strip().strip('"').lower() for c in header_str.split(delim_c)]

                def find_c_idx(candidates):
                    for cand in candidates:
                        cand_l = cand.lower()
                        for i, c in enumerate(h_cols_c):
                            if cand_l == c or cand_l in c:
                                return i
                    return None

                idx_c_ibge = find_c_idx(["cd_ibge", "ibge", "codigo_ibge"])
                idx_c_cod = find_c_idx(["cod_familiar_fam", "cod_familiar"])
                idx_c_nis = find_c_idx(["num_nis_pessoa_atual", "num_nis"])
                idx_c_nom = find_c_idx(["nom_pessoa", "nome"])
                idx_c_rf = find_c_idx(["cod_parentesco_rf_pessoa", "parentesco"])
                idx_c_pbf = find_c_idx(["marc_pbf"])
                idx_c_dt = find_c_idx(["dat_atual_fam", "dat_atualizacao_familia", "data_atualizacao"])
                idx_c_end = find_c_idx(["nom_logradouro_fam", "logradouro", "endereco"])
                idx_c_bai = find_c_idx(["nom_localidade_fam", "bairro", "localidade"])
                idx_c_cep = find_c_idx(["num_cep_logradouro_fam", "cep"])
                idx_c_tel = find_c_idx(["num_tel_contato_1_fam", "telefone", "tel"])

                total_cecad_mun = 0
                reader_c = io.BufferedReader(stream_c, buffer_size=1024 * 1024 * 8)

                for line in reader_c:
                    c_str = line.decode("latin1").rstrip("\r\n")
                    flds = [f.strip().strip('"') for f in c_str.split(delim_c)]

                    # Filtro do Município
                    c_code = ""
                    if idx_c_ibge is not None and idx_c_ibge < len(flds):
                        c_code = flds[idx_c_ibge].strip()
                        if c_code not in target_set:
                            continue

                    # Filtro do Responsável Familiar (RF = '1')
                    if idx_c_rf is not None and idx_c_rf < len(flds):
                        if flds[idx_c_rf].strip() != "1":
                            continue

                    total_cecad_mun += 1
                    cod_fam = flds[idx_c_cod].strip() if idx_c_cod is not None and idx_c_cod < len(flds) else ""
                    nis_val = flds[idx_c_nis].strip() if idx_c_nis is not None and idx_c_nis < len(flds) else ""
                    nom_val = flds[idx_c_nom].strip() if idx_c_nom is not None and idx_c_nom < len(flds) else ""
                    pbf_val = flds[idx_c_pbf].strip() if idx_c_pbf is not None and idx_c_pbf < len(flds) else ""
                    dt_val = flds[idx_c_dt].strip() if idx_c_dt is not None and idx_c_dt < len(flds) else ""
                    end_val = flds[idx_c_end].strip() if idx_c_end is not None and idx_c_end < len(flds) else ""
                    bai_val = flds[idx_c_bai].strip() if idx_c_bai is not None and idx_c_bai < len(flds) else ""
                    cep_val = flds[idx_c_cep].strip() if idx_c_cep is not None and idx_c_cep < len(flds) else ""
                    tel_val = flds[idx_c_tel].strip() if idx_c_tel is not None and idx_c_tel < len(flds) else ""

                    c_info = {
                        "ibge": c_code,
                        "cod_familiar": cod_fam,
                        "nis": nis_val,
                        "nome": nom_val,
                        "marc_pbf": pbf_val,
                        "dt_atualizacao_cecad": dt_val,
                        "endereco_cecad": end_val,
                        "bairro_cecad": bai_val,
                        "cep_cecad": cep_val,
                        "telefone_cecad": tel_val
                    }

                    cod_norm = cod_fam.lstrip("0")
                    nis_norm = nis_val.lstrip("0")
                    if cod_norm:
                        cecad_by_cod[cod_norm] = c_info
                    if nis_norm:
                        cecad_by_nis[nis_norm] = c_info

            finally:
                stream_c.close()
                if zip_c:
                    zip_c.close()

            # ----------------------------------------------------
            # ETAPA 3: Cruzamento & Classificação nos 4 Quadrantes
            # ----------------------------------------------------
            modal.update_progress(0.80, f"Cruzando {len(sibec_families):,} famílias nos 4 Quadrantes...")

            q1_rows: List[Dict[str, Any]] = []
            q2_rows: List[Dict[str, Any]] = []
            q3_rows: List[Dict[str, Any]] = []
            q4_rows: List[Dict[str, Any]] = []

            for s_fam in sibec_families:
                cod_norm = s_fam["cod_familiar"].lstrip("0")
                nis_norm = s_fam["nis"].lstrip("0")

                c_fam = cecad_by_cod.get(cod_norm) or cecad_by_nis.get(nis_norm)

                sit_u = s_fam["situacao_sibec"].upper()
                is_bloq = ("BLOQUEADO" in sit_u or "SUSPENSO" in sit_u or "CANCELADO" in sit_u)

                # Identificação do Município da Família
                fam_ibge = s_fam.get("ibge") or (c_fam.get("ibge") if c_fam else "") or (list(target_set)[0] if len(target_set) == 1 else "")
                fam_mun_display = f"{fam_ibge} - {get_municipio_nome(fam_ibge)}" if fam_ibge else ""

                # Monta registro integrado enriquecido
                item = {
                    "Município": fam_mun_display,
                    "Código Familiar": s_fam["cod_familiar"] or (c_fam["cod_familiar"] if c_fam else ""),
                    "NIS Favorecido": s_fam["nis"] or (c_fam["nis"] if c_fam else ""),
                    "Nome Favorecido": s_fam["nome"] or (c_fam["nome"] if c_fam else ""),
                    "Valor Parcela (R$)": s_fam["valor_sibec"],
                    "Situação SIBEC": s_fam["situacao_sibec"],
                    "PBF no CECAD Anterior": ("Sim" if c_fam["marc_pbf"] == "1" else "Não") if c_fam else "Novo Cadastro (Não constava)",
                    "Data Atualização SIBEC": s_fam["dt_atualizacao"],
                    "Data Atualização CECAD": c_fam["dt_atualizacao_cecad"] if c_fam else "",
                    "Endereço Residencial": s_fam["endereco_sibec"] or (c_fam["endereco_cecad"] if c_fam else ""),
                    "Bairro": s_fam["bairro_sibec"] or (c_fam["bairro_cecad"] if c_fam else ""),
                    "CEP": s_fam["cep_sibec"] or (c_fam["cep_cecad"] if c_fam else ""),
                    "Telefone": s_fam["telefone_sibec"] or (c_fam["telefone_cecad"] if c_fam else "")
                }

                # Q3: Bloqueados / Suspensos
                if is_bloq:
                    q3_rows.append(item)
                # Q1: Compatíveis & Regulares (Ativo no SIBEC e com PBF no CECAD)
                elif c_fam and c_fam["marc_pbf"] == "1":
                    q1_rows.append(item)
                # Q2: Concessões Recentes da Janela de 2 meses (Sem PBF ou novo cadastro no CECAD)
                else:
                    q2_rows.append(item)

                # Q4: Risco de Bloqueio por CadÚnico Desatualizado (> 2 anos)
                dt_str = s_fam["dt_atualizacao"] or (c_fam["dt_atualizacao_cecad"] if c_fam else "")
                is_desat = False
                if dt_str:
                    parts = dt_str.replace("-", "/").split("/")
                    yr = None
                    if len(parts) == 3:
                        if len(parts[2]) == 4:
                            yr = int(parts[2])
                        elif len(parts[0]) == 4:
                            yr = int(parts[0])
                    if yr and yr <= 2024:
                        is_desat = True

                if is_desat:
                    q4_rows.append(item)

            modal.update_progress(0.95, "Consolidando diagnósticos e tabelas...")

            df_q1 = pd.DataFrame(q1_rows)
            df_q2 = pd.DataFrame(q2_rows)
            df_q3 = pd.DataFrame(q3_rows)
            df_q4 = pd.DataFrame(q4_rows)

            resumo_data = [
                {"Indicador / Parâmetro": "Município(s) de Vinculação", "Valor": display_mun_str},
                {"Indicador / Parâmetro": "Total de Famílias na Folha SIBEC (Filtradas)", "Valor": len(sibec_families)},
                {"Indicador / Parâmetro": "Total de Famílias no CECAD (Municípios Selecionados)", "Valor": total_cecad_mun},
                {"Indicador / Parâmetro": "1. Compatíveis & Regulares (Q1)", "Valor": len(df_q1)},
                {"Indicador / Parâmetro": "2. Concessões Recentes — Janela 2 Meses (Q2)", "Valor": len(df_q2)},
                {"Indicador / Parâmetro": "3. Bloqueados / Suspensos — Ação Notificação CRAS (Q3)", "Valor": len(df_q3)},
                {"Indicador / Parâmetro": "4. Risco de Suspensão — Busca Ativa CadÚnico (Q4)", "Valor": len(df_q4)}
            ]
            df_resumo = pd.DataFrame(resumo_data)

            self.cross_results = {
                "resumo": df_resumo,
                "q1": df_q1,
                "q2": df_q2,
                "q3": df_q3,
                "q4": df_q4
            }
            self.cross_metrics = {
                "mun_ibge": list(target_set)[0] if len(target_set) == 1 else ", ".join(sorted(target_set)),
                "target_ibges": sorted(list(target_set)),
                "mun_nome": display_mun_str,
                "total_sibec": len(sibec_families),
                "total_cecad": total_cecad_mun,
                "q1": len(df_q1),
                "q2": len(df_q2),
                "q3": len(df_q3),
                "q4": len(df_q4)
            }

            modal.update_progress(1.0, "Cruzamento concluído!")

            def on_complete_ui():
                modal.close()
                self._update_quadrant_badges()
                self.export_btn.configure(state="normal")
                messagebox.showinfo(
                    "Cruzamento Concluído com Sucesso",
                    f"Conciliação cadastral concluída para {display_mun_str}!\n\n"
                    f"• 1. Compatíveis & Regulares: {len(df_q1):,} famílias\n"
                    f"• 2. Concessões Recentes (Janela 2m): {len(df_q2):,} famílias\n"
                    f"• 3. Bloqueados / Suspensos: {len(df_q3):,} famílias\n"
                    f"• 4. Risco de Bloqueio (Busca Ativa): {len(df_q4):,} famílias\n\n"
                    f"Clique em '📊 Exportar Relatório (.xlsx)' para salvar o diagnóstico completo multi-abas.".replace(",", ".")
                )

            self.after(0, on_complete_ui)

        except Exception as e:
            self.after(0, lambda: modal.close())
            self.after(0, lambda: messagebox.showerror("Erro no Cruzamento", str(e)))

    def _update_quadrant_badges(self):
        if not self.cross_metrics:
            return

        m = self.cross_metrics
        if "q1" in self.q_badges:
            self.q_badges["q1"].configure(text=f"{m.get('q1', 0):,} Famílias".replace(",", "."))
        if "q2" in self.q_badges:
            self.q_badges["q2"].configure(text=f"{m.get('q2', 0):,} Famílias".replace(",", "."))
        if "q3" in self.q_badges:
            self.q_badges["q3"].configure(text=f"{m.get('q3', 0):,} Famílias".replace(",", "."))
        if "q4" in self.q_badges:
            self.q_badges["q4"].configure(text=f"{m.get('q4', 0):,} Famílias".replace(",", "."))

    def _export_results(self):
        if not self.cross_results:
            messagebox.showwarning("Aviso", "Execute o cruzamento antes de exportar.")
            return

        target_ibges = self.cross_metrics.get("target_ibges", [])
        if len(target_ibges) == 1:
            mun_code = target_ibges[0]
        elif len(target_ibges) > 1:
            mun_code = f"multi_{len(target_ibges)}_municipios"
        else:
            mun_code = self.cross_metrics.get("mun_ibge", "municipio")

        default_file = f"diagnostico_cruzamento_cecad_sibec_{mun_code}.xlsx"

        out_path = filedialog.asksaveasfilename(
            title="Salvar Diagnóstico Integrado (Excel)",
            defaultextension=".xlsx",
            initialfile=default_file,
            filetypes=[("Planilha Excel (*.xlsx)", "*.xlsx")]
        )
        if not out_path:
            return

        try:
            with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
                if "resumo" in self.cross_results and not self.cross_results["resumo"].empty:
                    self.cross_results["resumo"].to_excel(writer, sheet_name="Resumo_Diagnóstico", index=False)
                if "q1" in self.cross_results and not self.cross_results["q1"].empty:
                    self.cross_results["q1"].to_excel(writer, sheet_name="1_Compatíveis_Regulares", index=False)
                if "q2" in self.cross_results and not self.cross_results["q2"].empty:
                    self.cross_results["q2"].to_excel(writer, sheet_name="2_Concessões_Recentes", index=False)
                if "q3" in self.cross_results and not self.cross_results["q3"].empty:
                    self.cross_results["q3"].to_excel(writer, sheet_name="3_Bloqueados_Notificar_CRAS", index=False)
                if "q4" in self.cross_results and not self.cross_results["q4"].empty:
                    self.cross_results["q4"].to_excel(writer, sheet_name="4_Busca_Ativa_CadÚnico", index=False)

            messagebox.showinfo(
                "Exportação Concluída",
                f"Relatório de Diagnóstico salvo com sucesso!\n\n"
                f"Arquivo gerado com 5 abas operacionais prontas para uso no CRAS.\n"
                f"Local: {out_path}"
            )
        except Exception as e:
            messagebox.showerror("Erro ao Exportar Relatório", str(e))
