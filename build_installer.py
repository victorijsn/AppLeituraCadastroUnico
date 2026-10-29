"""
Script mestre de automação para compilação do executável e geração do instalador Windows.
"""

import os
import sys
import shutil
import subprocess
import zipfile

def find_inno_compiler() -> str:
    """Procura pelo executável do Inno Setup Compiler (ISCC.exe)."""
    # 1. No PATH
    iscc = shutil.which("ISCC.exe") or shutil.which("iscc")
    if iscc:
        return iscc

    # 2. Em locais padrões de instalação no Windows
    candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    return ""


def build_pipeline():
    print("=" * 65)
    print("  PIPELINE DE DISTRIBUIÇÃO: AppLeituraCadastroUnico")
    print("=" * 65)

    # 1. Compilar executável com PyInstaller
    print("\n[Etapa 1/3] Compilando executável autônomo (.exe) com PyInstaller...")
    res = subprocess.run([sys.executable, "build_exe.py"])
    if res.returncode != 0:
        print("[ERRO] Falha na compilação do PyInstaller. Abortando.")
        return False

    exe_path = os.path.join("dist", "AppLeituraCadastroUnico.exe")
    if not os.path.exists(exe_path):
        print(f"[ERRO] Arquivo {exe_path} não foi gerado.")
        return False
    exe_size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"[OK] Executável gerado: {exe_path} ({exe_size_mb:.1f} MB)")

    # 2. Gerar pacote ZIP portátil de contingência
    print("\n[Etapa 2/3] Gerando pacote portátil (.zip) para contingência...")
    zip_dest = os.path.join("dist", "AppLeituraCadastroUnico_Portatil.zip")
    with zipfile.ZipFile(zip_dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe_path, arcname="AppLeituraCadastroUnico.exe")
        if os.path.exists("docs/GUIA_RAPIDO_INSTALACAO.md"):
            z.write("docs/GUIA_RAPIDO_INSTALACAO.md", arcname="GUIA_RAPIDO_INSTALACAO.md")
    print(f"[OK] Pacote ZIP portátil criado: {zip_dest}")

    # 3. Compilar instalador clássico com Inno Setup
    print("\n[Etapa 3/3] Procurando Inno Setup Compiler para gerar o Instalador...")
    iscc_path = find_inno_compiler()

    if iscc_path:
        print(f"-> Inno Setup encontrado em: {iscc_path}")
        print("-> Compilando Instalador_AppLeituraCadUnico_v1.0.exe...")
        os.makedirs("dist_installer", exist_ok=True)
        res_inno = subprocess.run([iscc_path, "installer.iss"])
        if res_inno.returncode == 0:
            installer_path = os.path.join("dist_installer", "Instalador_AppLeituraCadUnico_v1.0.exe")
            inst_size_mb = os.path.getsize(installer_path) / (1024 * 1024)
            print(f"\n[SUCESSO] Instalador gerado com sucesso!")
            print(f"-> Local: {installer_path} ({inst_size_mb:.1f} MB)")
            print("-> Modo: Usuário (não exige permissão de administrador na máquina municipal)")
            return True
        else:
            print("[AVISO] Inno Setup retornou erro na compilação do instalador.")
    else:
        print("\n[INFO] O Inno Setup Compiler (ISCC.exe) não foi encontrado no seu computador.")
        print("Para gerar o arquivo 'Instalador_AppLeituraCadUnico_v1.0.exe':")
        print("  1. Instale o Inno Setup gratuitamente pelo comando no terminal:")
        print("     winget install JRSoftware.InnoSetup")
        print("     (ou baixe em: https://jrsoftware.org/isdl.php)")
        print("  2. Em seguida, execute novamente: python build_installer.py")
        print("\nEnquanto isso, você já tem o executável pronto para distribuição em:")
        print(f"  -> {exe_path}")
        print(f"  -> {zip_dest}")

    return True

if __name__ == "__main__":
    build_pipeline()
