"""Pacotes de troca (YAML, JSON), repositório e migração do banco."""
import json
import sqlite3

import pytest

from core import dialogo
from core.models import SessaoExportada
from infrastructure import db, pacote, repositorio
from tests.conftest import FICHA_INES


def test_importa_ines(ambiente):
    p = repositorio.buscar_personagem("ines")
    assert p.nome == "Inês"
    assert len(p.restricoes) == 2
    fatos = repositorio.listar_fatos("ines")
    assert [f.id for f in fatos] == [f"F{i:02d}" for i in range(1, 11)]


def test_pacote_invalido_explica_o_erro():
    with pytest.raises(pacote.PacoteInvalido) as erro:
        pacote.ler_ficha_yaml("id: ines\nnome: Inês\nfatos:\n  - id: X1\n    texto: a\n")
    mensagem = str(erro.value)
    assert "papel" in mensagem and "fatos > 0 > id" in mensagem


def test_pacote_com_id_repetido():
    texto = FICHA_INES.read_text(encoding="utf-8").replace("id: F02", "id: F01")
    with pytest.raises(pacote.PacoteInvalido, match="mais de uma vez"):
        pacote.ler_ficha_yaml(texto)


def test_yaml_ida_e_volta_preserva_promovidos_e_inativos(ambiente):
    repositorio.promover_a_canone("ines", "Inês foi casada.")
    repositorio.desativar_fato("ines", "F03")
    texto = pacote.ficha_para_yaml(pacote.exportar_ficha("ines"))
    ficha = pacote.ler_ficha_yaml(texto)
    f11 = next(f for f in ficha.fatos if f.id == "F11")
    f03 = next(f for f in ficha.fatos if f.id == "F03")
    assert f11.origem == "promovido" and f03.ativo is False
    assert "Inês" in texto   # acentos preservados, sem escape


def test_exportacao_reconstroi_a_sessao(ambiente):
    sessao = dialogo.nova_sessao("ines", "exportação")
    a = dialogo.responder(sessao.id, "Oi.")
    dialogo.decidir(a.id, "aceita")
    b = dialogo.responder(sessao.id, "Você já foi à capital?")
    dialogo.regenerar(b.id)

    texto = pacote.sessao_para_json(pacote.exportar_sessao(sessao.id))
    assert "Inês" in texto
    reconstruida = SessaoExportada.model_validate_json(texto)
    assert len(reconstruida.turnos) == 3
    assert reconstruida.memoria == [0]
    assert reconstruida.turnos[1].verificacao.fato_id == "F02"
    assert reconstruida.provedor["verificador"]["temperatura"] == 0.1
    assert len(reconstruida.canone) == 10


def test_fatos_ordenados_por_numero(ambiente):
    for _ in range(3):
        repositorio.promover_a_canone("ines", "Fato extra.")
    ids = [f.id for f in repositorio.listar_fatos("ines")]
    assert ids[-4:] == ["F10", "F11", "F12", "F13"]


def test_personagem_com_id_invalido(ambiente):
    with pytest.raises(ValueError):
        repositorio.salvar_personagem("Inês Nova", "Inês", "papel", "registro")


def test_banco_antigo_e_migrado(tmp_path, monkeypatch):
    """Um app.db criado pela primeira versão ganha as colunas novas sem perder dados."""
    caminho = tmp_path / "antigo.db"
    c = sqlite3.connect(caminho)
    c.executescript("""
        CREATE TABLE personagem (id TEXT PRIMARY KEY, nome TEXT NOT NULL, papel TEXT NOT NULL,
            registro_fala TEXT NOT NULL, restricoes TEXT NOT NULL DEFAULT '[]', criado_em TEXT NOT NULL);
        CREATE TABLE fato_canonico (id TEXT NOT NULL, personagem_id TEXT NOT NULL, texto TEXT NOT NULL,
            escopo TEXT NOT NULL DEFAULT 'personagem', origem TEXT NOT NULL DEFAULT 'autorado',
            ativo INTEGER NOT NULL DEFAULT 1, criado_em TEXT NOT NULL, PRIMARY KEY (personagem_id, id));
        CREATE TABLE sessao (id TEXT PRIMARY KEY, personagem_id TEXT NOT NULL, titulo TEXT NOT NULL,
            criada_em TEXT NOT NULL);
        CREATE TABLE turno (id TEXT PRIMARY KEY, sessao_id TEXT NOT NULL, indice INTEGER NOT NULL,
            fala_jogador TEXT NOT NULL, fala_npc TEXT NOT NULL, veredito TEXT NOT NULL, fato_id TEXT,
            justificativa TEXT NOT NULL, decisao TEXT NOT NULL DEFAULT 'pendente',
            criado_em TEXT NOT NULL, UNIQUE (sessao_id, indice));
        INSERT INTO personagem VALUES ('ines', 'Inês', 'herbolária', 'ríspida', '[]', '2026-09-10T00:00:00+00:00');
        INSERT INTO fato_canonico VALUES ('F01', 'ines', 'Fato.', 'personagem', 'autorado', 1, '2026-09-10T00:00:00+00:00');
    """)
    c.close()

    monkeypatch.setenv("CANONE_DB", str(caminho))
    db.inicializar()
    assert repositorio.listar_fatos("ines")[0].turno_origem_id is None
    sessao = repositorio.criar_sessao("ines", "pós-migração")
    assert repositorio.contar_turnos(sessao.id) == 0
    colunas = {l[1] for l in sqlite3.connect(caminho).execute("PRAGMA table_info(turno)")}
    assert {"latencia_geracao_ms", "latencia_verificacao_ms"} <= colunas


def test_caminho_do_banco_independe_da_pasta_atual(monkeypatch, tmp_path):
    monkeypatch.delenv("CANONE_DB", raising=False)
    monkeypatch.chdir(tmp_path)
    assert db.caminho_db() == db.RAIZ / "data" / "app.db"
