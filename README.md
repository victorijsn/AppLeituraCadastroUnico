# 📋 AppLeituraCadastroUnico

Aplicativo desktop local e portátil para leitura, tradução e tratamento analítico da base de dados do **Cadastro Único (CECAD)** disponibilizada pelo Ministério do Desenvolvimento e Assistência Social, Família e Combate à Fome (MDS).

---

## 🚀 Funcionalidades Principais

- **Tradução Automática de Códigos:** Converte instantaneamente os mais de 115 campos codificados (ex: `cod_est_cadastral_fam = 3` $\rightarrow$ `Cadastrado`, `marc_pbf = 1` $\rightarrow$ `Sim`) para texto em português claro, além de traduzir os nomes técnicos das colunas para descrições amigáveis do dicionário.
- **Suporte Nativo a Arquivos .ZIP e .CSV:** Lê diretamente arquivos compactados de até 1,5 GB e mais de 1,8 milhão de linhas via streaming em memória, sem exigir descompactação prévia.
- **Detecção Inteligente:** Reconhece automaticamente o escopo do arquivo (Base Estadual vs. Base Municipal) e a data de referência dos dados (ex: `08/2026`).
- **Filtro Geográfico por Município:** Permite selecionar o município desejado a partir do nome ou código IBGE, reduzindo arquivos estaduais pesados para o volume do município (garantindo compatibilidade com o limite de 1 milhão de linhas do Excel).
- **Níveis de Granularidade:**
  - **Pessoa (Original):** Cada linha representa um membro da família.
  - **Família (Consolidado):** Filtra apenas o Responsável Familiar (RF), gerando 1 linha por família.
- **Perfis Temáticos Pré-configurados:**
  - *Completo:* Todas as colunas traduzidas.
  - *Visão Geral & Cadastro:* Identificação, Responsável Familiar, endereço e atualização cadastral.
  - *Bolsa Família & Renda:* Benefícios (PBF, Gás, BPC), rendimentos familiares e individuais.
  - *Habitação & Vulnerabilidade:* Condições de moradia, água, esgoto, lixo, piso, paredes e infraestrutura.
  - *Pessoas, Educação & Trabalho:* Escolaridade, deficiências, trabalho e rendimento individual.
  - *Personalizado:* Modal com busca e seleção manual de colunas.
- **Filtros Rápidos Pré-Exportação:**
  - Bolsa Família (Todos / Sim / Não)
  - Situação Cadastral (Todos / Desatualizados > 2 anos / Atualizados <= 2 anos)
  - Faixa de Renda (Todas / Extrema Pobreza / Pobreza / Baixa Renda / Acima 1/2 SM)
  - Busca por Bairro / Unidade Territorial (CRAS)
- **Modo LGPD / Compartilhamento:** Mascara CPF (`***.***.123-**`) e NIS (`***.*****.12-*`) e oculta nomes completos, ideal para repassar planilhas a outras secretarias (Saúde, Educação, Habitação) sem ferir a Lei Geral de Proteção de Dados.
- **Cards de Métricas e Prévia em Tempo Real:** Exibe total de famílias, total de pessoas, % de Bolsa Família, % de desatualizados e renda média familiar per capita antes de exportar.
- **Exportação Profissional:**
  - **Excel (.xlsx):** Preserva zeros à esquerda em CPF, NIS, CEP e IBGE como texto estrito (impedindo que o Excel os converta para notação científica como `3,2E+10`), com cabeçalho formatado em azul escuro, congelamento de linha superior e filtro automático ativo.
  - **CSV Brasileiro:** Ponto-e-vírgula (`;`) com codificação `UTF-8 com BOM` (`utf-8-sig`).

---

## 🛠️ Tecnologias Utilizadas

- **Interface Gráfica:** [CustomTkinter](https://customtkinter.tomschimansky.com/) (moderna, cantos arredondados, alternância Modo Escuro / Claro)
- **Processamento de Dados:** Python 3.12+ com streaming via `io.BufferedReader`, `Pandas` e `DuckDB`
- **Geração de Planilhas:** `xlsxwriter` e `openpyxl`
- **Empacotamento:** `PyInstaller` (executável portátil autônomo `.exe`)

---

## 📂 Estrutura do Projeto

```
AppLeituraCadastroUnico/
│
├── base/                                # Dados de teste fornecidos
│   ├── dicionariocecad_marc_pbf.xlsx    # Dicionário oficial do CECAD
│   └── tab_cad_07082026_32_20260911.zip # Base de teste estadual (ES)
│
├── docs/                                # Documentação e especificações
│   └── ESPECIFICACAO_TECNICA.md
│
├── src/                                 # Código-fonte
│   ├── app.py                           # Ponto de entrada
│   ├── core/                            # Regras de negócio e motores
│   │   ├── dictionary_parser.py         # Leitor e tradutor do dicionário
│   │   ├── file_inspector.py            # Reconhecimento de ZIP/CSV e municípios
│   │   ├── thematic_profiles.py         # Perfis temáticos de colunas
│   │   ├── data_engine.py               # Motor de filtragem e tradução
│   │   ├── exporter.py                  # Exportadores formatados XLSX e CSV
│   │   └── lgpd.py                      # Mascaramento de dados sensíveis
│   ├── ui/                              # Interface gráfica
│   │   ├── main_window.py               # Janela principal
│   │   └── components/
│   │       ├── stat_card.py             # Cards de resumo
│   │       ├── preview_table.py         # Tabela de prévia
│   │       └── column_selector.py       # Diálogo de seleção de colunas
│   └── assets/                          # Recursos embutidos
│       ├── dicionario_padrao.json       # Dicionário pré-compilado
│       └── municipios_ibge.json         # Base oficial de 5.571 municípios do Brasil
│
├── tests/                               # Testes unitários e de integração
│   ├── test_dictionary_parser.py
│   ├── test_file_inspector.py
│   ├── test_data_engine.py
│   ├── test_exporter.py
│   └── test_end_to_end_export.py
│
├── run.py                               # Inicializador rápido
├── build_exe.py                         # Script para compilar o executável .exe
├── requirements.txt                     # Dependências do projeto
└── README.md                            # Guia do projeto
```

---

## 💻 Como Executar

### 1. Pré-requisitos
- Python 3.10 ou superior instalado.

### 2. Instalação das dependências
No terminal do Windows (PowerShell):
```powershell
# Criação do ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalação dos pacotes
pip install -r requirements.txt
```

### 3. Execução do aplicativo
```powershell
python run.py
```

### 4. Execução dos testes automatizados
```powershell
python -m unittest discover tests
```

---

## 📦 Como Gerar o Executável (.exe)

Para gerar um arquivo `.exe` portátil que pode ser executado em qualquer computador com Windows sem necessidade de Python instalado:
```powershell
python build_exe.py
```
O executável compilado será salvo em `dist/AppLeituraCadastroUnico.exe`.

---

## 🔒 Privacidade e LGPD

O aplicativo é executado **100% localmente e offline** na máquina do usuário. Nenhum dado do Cadastro Único é transmitido para a internet ou para servidores externos.
