"""Conexão com o banco SQLite local (RNF01: arquivo único, sem servidor).

O caminho do banco é resolvido a partir da pasta do projeto, e não da pasta
de onde o programa foi chamado. Assim, um script de jogo que importe o Cânone
de outro diretório usa o mesmo banco que a interface da roteirista.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_SCHEMA = Path(__file__).resolve().parent / "schema.sql"

# Colunas acrescentadas depois da primeira versão do banco. Bancos antigos
# recebem as colunas na primeira abertura, sem perder dados.
_MIGRACOES = {
    "turno": {
        "latencia_geracao_ms": "INTEGER",
        "latencia_verificacao_ms": "INTEGER",
    },
    "fato_canonico": {
        "turno_origem_id": "TEXT",
    },
}

_inicializados: set[Path] = set()


def caminho_db() -> Path:
    """data/app.db na pasta do projeto, ou o que estiver em CANONE_DB."""
    return Path(os.environ.get("CANONE_DB") or RAIZ / "data" / "app.db")


def _abrir(caminho: Path) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(caminho)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def inicializar() -> None:
    """Cria as tabelas e aplica migrações pendentes. Idempotente."""
    caminho = caminho_db()
    c = _abrir(caminho)
    try:
        with c:
            c.executescript(CAMINHO_SCHEMA.read_text(encoding="utf-8"))
            for tabela, colunas in _MIGRACOES.items():
                existentes = {l["name"] for l in c.execute(f"PRAGMA table_info({tabela})")}
                for nome, tipo in colunas.items():
                    if nome not in existentes:
                        c.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")
    finally:
        c.close()
    _inicializados.add(caminho)


@contextmanager
def conexao():
    """Abre, faz commit (ou rollback em erro) e fecha.

    Garante que o banco foi inicializado antes do primeiro uso no processo.
    """
    caminho = caminho_db()
    if caminho not in _inicializados:
        inicializar()
    c = _abrir(caminho)
    try:
        with c:
            yield c
    finally:
        c.close()
