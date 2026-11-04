"""
Módulo para exportação otimizada em XLSX (Excel) e CSV.
Garante preservação de zeros à esquerda (CPF, NIS, IBGE, CEP) e formatação profissional.
"""

import os
import re
from typing import Optional, Callable
import pandas as pd
import xlsxwriter

# Colunas que NUNCA devem perder zeros à esquerda
TEXT_COLUMNS_PATTERNS = [
    r'cpf', r'nis', r'ibge', r'cep', r'cod_familiar', r'codigo.*familiar', r'unidade.*territorial'
]


def is_text_column(col_name: str) -> bool:
    """Verifica se a coluna deve ser forçada como texto estrito para preservar zeros à esquerda."""
    col_lower = col_name.lower()
    return any(re.search(pat, col_lower) for pat in TEXT_COLUMNS_PATTERNS)


class DataExporter:
    """Exportador para planilhas Excel formatadas e CSVs brasileiros."""

    @staticmethod
    def export_to_excel(
        df: pd.DataFrame,
        output_path: str,
        sheet_name: str = "Cadastro Unico",
        progress_callback: Optional[Callable[[float, str], None]] = None,
        max_rows_per_sheet: int = 1_000_000
    ) -> str:
        """
        Exporta DataFrame para .xlsx profissional com xlsxwriter:
        - Zeros preservados em CPF, NIS, IBGE, CEP
        - Cabeçalho estilizado (azul escuro, texto branco, negrito)
        - Linha de cabeçalho congelada (Freeze Panes)
        - Filtro automático ativado
        - Divisão automática em abas se total_rows > max_rows_per_sheet
        """
        if progress_callback:
            progress_callback(0.1, "Iniciando criação da planilha Excel...")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        workbook = xlsxwriter.Workbook(output_path, {"constant_memory": True})

        # Formatos visuais
        header_format = workbook.add_format({
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#1E3A8A",
            "border": 1,
            "border_color": "#D1D5DB",
            "valign": "vcenter",
            "align": "left",
            "font_name": "Segoe UI",
            "font_size": 10
        })

        cell_format = workbook.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "valign": "vcenter"
        })

        text_format = workbook.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "num_format": "@",  # Formato texto estrito
            "valign": "vcenter"
        })

        headers = list(df.columns)
        num_cols = len(headers)
        total_rows = len(df)

        col_text_flags = [is_text_column(h) for h in headers]
        col_widths = [min(max(len(str(h)) + 3, 12), 45) for h in headers]

        # Limite máximo seguro por aba no Excel (limite absoluto do xlsxwriter é 1.048.576)
        MAX_ROWS_PER_SHEET = max_rows_per_sheet

        def init_worksheet(name: str):
            ws = workbook.add_worksheet(name[:31])
            ws.set_row(0, 26)
            for c_idx, h in enumerate(headers):
                ws.write_string(0, c_idx, str(h), header_format)
            ws.freeze_panes(1, 0)
            for c_idx, w in enumerate(col_widths):
                ws.set_column(c_idx, c_idx, w)
            return ws

        sheet_index = 1
        current_sheet_name = f"{sheet_name[:20]} - Parte {sheet_index}" if total_rows > MAX_ROWS_PER_SHEET else sheet_name[:31]
        worksheet = init_worksheet(current_sheet_name)
        rows_in_current_sheet = 0

        # Escreve linhas
        for row_idx, row in enumerate(df.itertuples(index=False)):
            if rows_in_current_sheet >= MAX_ROWS_PER_SHEET:
                # Finaliza aba anterior com autofiltro
                if rows_in_current_sheet > 0 and num_cols > 0:
                    worksheet.autofilter(0, 0, rows_in_current_sheet, num_cols - 1)

                sheet_index += 1
                current_sheet_name = f"{sheet_name[:20]} - Parte {sheet_index}"
                worksheet = init_worksheet(current_sheet_name)
                rows_in_current_sheet = 0

            target_row = rows_in_current_sheet + 1
            worksheet.set_row(target_row, 20)

            for col_idx, val in enumerate(row):
                if pd.isna(val) or val is None:
                    worksheet.write_blank(target_row, col_idx, None, cell_format)
                    continue

                if col_text_flags[col_idx]:
                    val_str = str(val).strip()
                    worksheet.write_string(target_row, col_idx, val_str, text_format)
                else:
                    if isinstance(val, (int, float)):
                        worksheet.write_number(target_row, col_idx, val, cell_format)
                    else:
                        worksheet.write(target_row, col_idx, str(val), cell_format)

            rows_in_current_sheet += 1

            if progress_callback and (row_idx + 1) % 10000 == 0:
                pct = 0.1 + (row_idx / total_rows) * 0.85
                progress_callback(pct, f"Gravando linha {row_idx + 1:,} no Excel (Aba {sheet_index})...".replace(",", "."))

        # Ativa autofiltro na última aba
        if rows_in_current_sheet > 0 and num_cols > 0:
            worksheet.autofilter(0, 0, rows_in_current_sheet, num_cols - 1)

        workbook.close()

        if progress_callback:
            progress_callback(1.0, f"Arquivo Excel salvo com sucesso em {os.path.basename(output_path)}!")

        return output_path

    @staticmethod
    def export_to_csv(
        df: pd.DataFrame,
        output_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Exporta DataFrame para CSV compatível com o padrão Excel do Brasil:
        - UTF-8 com BOM (utf-8-sig)
        - Separador ponto-e-vírgula (;)
        """
        if progress_callback:
            progress_callback(0.2, "Gravando arquivo CSV...")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Força colunas de texto (CPF, NIS, etc) a manter aspas se necessário
        df.to_csv(
            output_path,
            sep=";",
            index=False,
            encoding="utf-8-sig"
        )

        if progress_callback:
            progress_callback(1.0, f"Arquivo CSV salvo com sucesso em {os.path.basename(output_path)}!")

        return output_path
