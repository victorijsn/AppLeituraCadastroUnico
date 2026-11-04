; Script de Configuração do Inno Setup para o AppLeituraCadastroUnico
; Permite instalação em modo Usuário (PrivilegesRequired=lowest) sem exigir senha de Administrador (UAC).

#define MyAppName "AppLeituraCadastroUnico"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Gestão Cadastro Único"
#define MyAppExeName "AppLeituraCadastroUnico.exe"

[Setup]
; Identificador único do aplicativo (gerado para evitar conflitos)
AppId={{E68A9F43-159C-4D56-82BA-7A2D3C4B8901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Não exige privilégios de administrador - funciona em qualquer máquina municipal
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Configurações de saída do instalador
OutputDir=dist_installer
OutputBaseFilename=Instalador_AppLeituraCadUnico_v1.2
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; Desinstalação limpa
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Executável principal compilado pelo PyInstaller
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Recursos e dicionários padrão
Source: "src\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
; Documentação do usuário
Source: "docs\GUIA_RAPIDO_INSTALACAO.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall skipifsilent
