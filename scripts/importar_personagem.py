"""Importa um pacote de personagem (YAML) para o banco.

Da pasta do projeto:
    python scripts\\importar_personagem.py                      # Inês
    python scripts\\importar_personagem.py caminho\\outro.yaml

Equivale a: python -m cli importar <arquivo.yaml>
"""
import sys
from pathlib import Path

from _registro import RAIZ

from infrastructure.pacote import PacoteInvalido, importar_ficha_yaml
from infrastructure.repositorio import listar_fatos


def main() -> int:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data/personagens/ines.yaml"
    try:
        personagem = importar_ficha_yaml(caminho)
    except (PacoteInvalido, FileNotFoundError) as erro:
        print(erro)
        return 1
    print(f"{personagem.nome} importada com {len(listar_fatos(personagem.id))} fatos ativos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
