# 📘 Guia Rápido de Instalação e Uso
## AppLeituraCadastroUnico — Gestão Municipal

Este guia foi elaborado para orientar as equipes técnicas dos municípios (CRAS, CREAS e Gestão CadÚnico/PBF) na instalação e primeiro uso do **AppLeituraCadastroUnico**.

> 💡 **Nota Importante:** O aplicativo foi desenvolvido para funcionar diretamente no perfil do usuário, **sem exigir senha de administrador (TI)** para instalação.

---

## 1. Passo a Passo de Instalação

### Passo 1: Baixar o Instalador
Baixe o arquivo **`Instalador_AppLeituraCadUnico_v1.0.exe`** enviado pela coordenação estadual (via link do Google Drive / OneDrive ou e-mail).

### Passo 2: Executar o Instalador
Dê dois cliques no arquivo baixado.

---

### ⚠️ O que fazer se aparecer a tela azul do Windows SmartScreen?

Como o aplicativo é uma ferramenta governamental distribuída internamente (sem compra de certificado comercial da Microsoft), o Windows pode exibir este aviso preventivo:

```
┌─────────────────────────────────────────────────────────────┐
│  O Windows protegeu o seu computador                        │
│                                                             │
│  O Microsoft Defender SmartScreen impediu a inicialização   │
│  de um aplicativo não reconhecido.                          │
│                                                             │
│  [ Mais informações ]                        [ Não executar ]│
└─────────────────────────────────────────────────────────────┘
```

**Como proceder:**
1. Clique no texto sublinhado **<u>Mais informações</u>**.
2. Em seguida, clique no botão **[ Executar assim mesmo ]** que aparecerá no canto inferior.
3. O assistente de instalação abrirá normalmente.

---

### Passo 3: Concluir o Assistente
1. Na tela do assistente, clique em **Avançar**.
2. Deixe marcada a opção **"Criar um atalho na Área de Trabalho"**.
3. Clique em **Instalar** e depois em **Concluir**.

Pronto! Um ícone chamado **`AppLeituraCadastroUnico`** estará disponível na sua Área de Trabalho e no Menu Iniciar.

---

## 2. Como Usar o Aplicativo (Passo a Passo Rápido)

```
 [1. Procurar Arquivo] ──> [2. Selecionar Município] ──> [3. Escolher Perfil] ──> [4. Exportar Excel]
 (Selecione o .zip/.csv)    (Ex: Presidente Kennedy)     (Ex: Bolsa Família)      (Planilha formatada)
```

1. **Abra o programa** pelo atalho na Área de Trabalho.
2. Clique no botão **`📁 Procurar Arquivo...`** e selecione a base do CECAD que você recebeu (pode ser o arquivo `.zip` compactado direto, não precisa descompactar!).
3. No campo **`Município / Território`**, selecione a sua cidade.
4. Escolha o **`Nível de Análise`**:
   - **Pessoa (Original):** Cada linha é um membro da família.
   - **Família (Apenas RF):** 1 linha por família, contendo o CPF e NIS do Responsável Familiar.
5. Escolha o **`Perfil de Colunas`** desejado (ex: *Visão Geral*, *Bolsa Família & Renda*, *Habitação*, etc.).
6. Clique em **`📊 Exportar Excel (.xlsx)`** para salvar a planilha pronta para análise.

---

## 3. Mensagem Padrão para o Setor de Tecnologia da Informação (TI)

Caso o computador da prefeitura possua bloqueio corporativo rígido de antivírus ou firewall que impeça a execução, copie e envie o texto abaixo para a equipe de suporte de TI do seu município:

---

> **Assunto:** Liberação de execução de aplicativo local - AppLeituraCadastroUnico (MDS/CECAD)
>
> Prezada equipe de TI,
>
> Solicitamos a liberação da execução local do software **AppLeituraCadastroUnico** nesta máquina da Secretaria Municipal de Assistência Social.
>
> **Finalidade do aplicativo:** Leitura e tradução dos códigos tabulares do banco de dados do Cadastro Único (CECAD) exportado pelo MDS, viabilizando o trabalho de busca ativa e gestão dos programas sociais do município.
>
> **Aspectos técnicos e de segurança:**
> - O aplicativo opera **100% offline e localmente** (não efetua tráfego de dados para a internet, atendendo integralmente à LGPD e à política de sigilo do CadÚnico).
> - Instalação no escopo do usuário (`%LOCALAPPDATA%\Programs\AppLeituraCadastroUnico`), não necessitando de privilégios de administrador do domínio ou gravação no `Program Files`.
> - Desenvolvido em ambiente seguro com Python/CustomTkinter e empacotado como executável padrão do Windows.
>
> Agradecemos pelo apoio na liberação.

---

## 4. Dúvidas Frequentes (FAQ)

- **Preciso descompactar o arquivo .zip de 1,5 GB antes de abrir?**  
  *Não! O aplicativo lê diretamente de dentro do arquivo .zip sem ocupar espaço extra no seu disco.*

- **O Excel vai apagar os zeros à esquerda do CPF e do NIS?**  
  *Não! O aplicativo formata automaticamente as colunas de CPF, NIS, CEP e Código IBGE como texto no arquivo .xlsx, preservando todos os dígitos intactos.*

- **O aplicativo funciona sem internet?**  
  *Sim! Ele opera 100% offline no seu computador.*
