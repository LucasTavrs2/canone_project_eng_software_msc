"""Interface web: roda o ui/app.py de verdade, sem navegador, com o AppTest do Streamlit.

Se o Streamlit não estiver instalado, estes testes são pulados.
"""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from infrastructure import repositorio  # noqa: E402
from tests.conftest import RAIZ  # noqa: E402

APP = str(RAIZ / "ui" / "app.py")


def _abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    _sem_erro(at)
    return at


def _sem_erro(at: AppTest) -> None:
    assert not at.exception, [e.value for e in at.exception]


def _botao(at: AppTest, rotulo: str):
    return next(b for b in at.button if b.label == rotulo)


def _rodar(at: AppTest) -> None:
    """Executa a ação pendente e redesenha a página (a ação pode pedir st.rerun)."""
    at.run()
    _sem_erro(at)
    at.run()
    _sem_erro(at)


def test_tela_inicial_e_importacao_do_exemplo(tmp_path, monkeypatch, servidor):
    monkeypatch.setenv("CANONE_DB", str(tmp_path / "vazio.db"))
    monkeypatch.setenv("CANONE_LLM_URL", servidor.url)
    monkeypatch.setenv("CANONE_LLM_MODEL", "modelo-falso")
    at = _abrir()
    assert at.header[0].value == "Boas-vindas ao Cânone"
    _botao(at, "Importar Inês (exemplo)").click()
    _rodar(at)
    assert at.header[0].value == "Inês"
    assert len(repositorio.listar_fatos("ines")) == 10


def test_conversa_revisao_e_promocao(ambiente):
    at = _abrir()
    assert at.header[0].value == "Inês"

    at.text_input(key="titulo_nova_sessao").input("teste da interface")
    _botao(at, "Nova sessão").click()
    _rodar(at)
    sessao = repositorio.listar_sessoes("ines")[0]
    assert sessao.titulo == "teste da interface"

    # Fala que contradiz o cânone: sinalizada, mas não bloqueada.
    at.chat_input[0].set_value("Você já foi à capital?")
    _rodar(at)
    turno = repositorio.listar_turnos(sessao.id)[-1]
    assert turno.decisao == "pendente" and turno.verificacao.fato_id == "F02"
    assert any("Contradiz F02" in m.value for m in at.markdown)

    at.button(key=f"regenerar_{turno.id}").click()
    _rodar(at)
    novo = repositorio.listar_turnos(sessao.id)[-1]
    assert repositorio.buscar_turno(turno.id).decisao == "regenerada"

    at.button(key=f"descartar_{novo.id}").click()
    _rodar(at)
    assert repositorio.buscar_turno(novo.id).decisao == "descartada"

    # Detalhe inventado, promovido a cânone.
    at.chat_input[0].set_value("Você tinha marido?")
    _rodar(at)
    inventou = repositorio.listar_turnos(sessao.id)[-1]
    at.text_input(key=f"promover_txt_{inventou.id}").input("Inês foi casada.")
    at.button(key=f"promover_{inventou.id}").click()
    _rodar(at)
    fato = repositorio.buscar_fato("ines", "F11")
    assert fato is not None and fato.origem == "promovido"
    assert repositorio.buscar_turno(inventou.id).decisao == "aceita"

    # A contradição com o fato promovido passa a ser detectada.
    at.chat_input[0].set_value("Você criou o Tomé sozinha?")
    _rodar(at)
    depois = repositorio.listar_turnos(sessao.id)[-1]
    assert depois.verificacao.fato_id == "F11"
    at.button(key=f"aceitar_{depois.id}").click()
    _rodar(at)
    assert repositorio.buscar_turno(depois.id).decisao == "aceita"


def test_ficha_e_canone(ambiente):
    # Cada ação parte de uma página recém-aberta, como quando a pessoa recarrega
    # o navegador. Isso evita depender do estado que o AppTest acumula entre
    # execuções: um campo criado depois de um st.rerun às vezes some desse estado.
    at = _abrir()
    campo = next(t for t in at.text_area if t.label == "Novo fato canônico")
    campo.input("Inês tem medo de cavalos.")
    _botao(at, "Adicionar ao cânone").click()
    at.run()
    _sem_erro(at)
    assert repositorio.buscar_fato("ines", "F11").texto == "Inês tem medo de cavalos."

    at = _abrir()
    at.button(key="ativo_ines_F11").click()
    at.run()
    _sem_erro(at)
    assert repositorio.buscar_fato("ines", "F11").ativo is False

    at = _abrir()
    registro = next(t for t in at.text_area if t.label == "Como fala (registro de fala)")
    registro.input("ríspida, econômica, seca")
    _botao(at, "Salvar ficha").click()
    at.run()
    _sem_erro(at)
    assert repositorio.buscar_personagem("ines").registro_fala == "ríspida, econômica, seca"


def test_provedor_fora_do_ar_mostra_erro(ambiente, monkeypatch):
    at = _abrir()
    at.text_input(key="titulo_nova_sessao").input("sem modelo")
    _botao(at, "Nova sessão").click()
    _rodar(at)

    monkeypatch.setenv("CANONE_LLM_URL", "http://127.0.0.1:9/v1")
    at.chat_input[0].set_value("Oi?")
    at.run()
    _sem_erro(at)
    assert any("O modelo não respondeu" in e.value for e in at.error)