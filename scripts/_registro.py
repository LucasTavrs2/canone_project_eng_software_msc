"""Saída dupla para os scripts: imprime no terminal e grava em arquivo UTF-8.

Substitui o Tee-Object do PowerShell, que segurava a saída em buffer, não
registrava o que era digitado e gravava o arquivo com BOM.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


class Registro:
    def __init__(self, caminho: str | Path | None):
        self.arquivo = None
        if caminho:
            caminho = Path(caminho)
            caminho.parent.mkdir(parents=True, exist_ok=True)
            self.arquivo = caminho.open("w", encoding="utf-8", newline="\n")
            self.caminho = caminho

    def __call__(self, texto: str = "") -> None:
        print(texto)
        if self.arquivo:
            self.arquivo.write(texto + "\n")
            self.arquivo.flush()

    def entrada(self, prompt: str) -> str:
        resposta = input(prompt)
        if self.arquivo:
            self.arquivo.write(prompt + resposta + "\n")
            self.arquivo.flush()
        return resposta

    def fechar(self) -> None:
        if self.arquivo:
            self.arquivo.close()
            print(f"\nRegistro gravado em {self.caminho}")
            self.arquivo = None
