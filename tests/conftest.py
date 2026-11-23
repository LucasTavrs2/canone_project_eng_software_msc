"""Fixtures dos testes: banco temporário e servidor de modelo falso."""
from pathlib import Path

import pytest

from tests.servidor_falso import ServidorFalso

RAIZ = Path(__file__).resolve().parent.parent
FICHA_INES = RAIZ / "data" / "personagens" / "ines.yaml"


@pytest.fixture
def servidor():
    s = ServidorFalso().iniciar()
    yield s
    s.shutdown()
    s.server_close()


@pytest.fixture
def ambiente(tmp_path, monkeypatch, servidor):
    """Banco vazio em pasta temporária, provedor apontando para o servidor falso
    e a Inês importada. Nunca toca em data/app.db."""
    monkeypatch.setenv("CANONE_DB", str(tmp_path / "teste.db"))
    monkeypatch.setenv("CANONE_LLM_URL", servidor.url)
    monkeypatch.setenv("CANONE_LLM_MODEL", "modelo-falso")
    for var in ("CANONE_GERADOR_MODEL", "CANONE_VERIFICADOR_MODEL",
                "CANONE_GERADOR_URL", "CANONE_VERIFICADOR_URL", "CANONE_LLM_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    from infrastructure.pacote import importar_ficha_yaml
    importar_ficha_yaml(FICHA_INES)
    return servidor
