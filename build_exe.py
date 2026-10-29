"""
Script automatizado para gerar o executável autônomo (.exe) via PyInstaller.
"""

import os
import sys
import subprocess

def build():
    print("Iniciando empacotamento do AppLeituraCadastroUnico...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=AppLeituraCadastroUnico",
        "--onefile",
        "--noconsole",
        "--add-data=src/assets;src/assets",
        "--collect-data=customtkinter",
        "--clean",
        "run.py"
    ]

    print("Executando:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\nSucesso! Executável gerado na pasta dist/AppLeituraCadastroUnico.exe")
    else:
        print("\nFalha ao compilar com PyInstaller. Código:", res.returncode)

if __name__ == "__main__":
    build()
