"""Ciclo de um turno: as decisões de projeto que a documentação defende."""
import pytest

from core import dialogo
from core.models import ResultadoVerificacao
from infrastructure import repositorio


def _sessao():
    return dialogo.nova_sessao("ines", "teste")


def test_responder_grava_turno_pendente_com_latencia(ambiente):
    turno = dialogo.responder(_sessao().id, "Que ervas você tem?")
    assert turno.decisao == "pendente"
    assert turno.verificacao.veredito == "consistente"
    assert turno.latencia_geracao_ms is not None
    assert turno.latencia_verificacao_ms is not None


def test_contradicao_aponta_fato_correto(ambiente):
    turno = dialogo.responder(_sessao().id, "Você já foi à capital?")
    assert turno.verificacao.veredito == "contradiz"
    assert turno.verificacao.fato_id == "F02"


def test_verificador_nao_recebe_a_ficha(ambiente):
    dialogo.responder(_sessao().id, "Que ervas você tem?")
    geracao, verificacao = ambiente.requisicoes[-2:]
    prompt_verificador = " ".join(m["content"] for m in verificacao["messages"])
    assert "herbolária do vilarejo inicial" in geracao["messages"][0]["content"]
    assert "herbolária do vilarejo inicial" not in prompt_verificador
    assert "ríspida" not in prompt_verificador
    assert "[F01]" in prompt_verificador


def test_temperaturas_por_papel(ambiente):
    dialogo.responder(_sessao().id, "Oi.")
    geracao, verificacao = ambiente.requisicoes[-2:]
    assert geracao["temperature"] == 0.85
    assert verificacao["temperature"] == 0.1
    assert "response_format" in verificacao and "response_format" not in geracao


def test_so_turnos_aceitos_entram_na_memoria(ambiente):
    sessao = _sessao()
    aceito = dialogo.responder(sessao.id, "Primeira pergunta.")
    dialogo.decidir(aceito.id, "aceita")
    descartado = dialogo.responder(sessao.id, "Pergunta descartada.")
    dialogo.decidir(descartado.id, "descartada")
    regenerado = dialogo.responder(sessao.id, "Pergunta regenerada.")
    dialogo.regenerar(regenerado.id)

    ambiente.requisicoes.clear()
    dialogo.responder(sessao.id, "Última.")
    mensagens = ambiente.requisicoes[0]["messages"]
    conteudos = [m["content"] for m in mensagens[1:]]
    assert "Primeira pergunta." in conteudos
    assert "Pergunta descartada." not in conteudos
    # O turno regenerado foi substituído por um novo, ainda pendente: nenhum entra.
    assert "Pergunta regenerada." not in conteudos
    assert conteudos[-1] == "Última."


def test_regenerar_marca_original_e_cria_novo(ambiente):
    sessao = _sessao()
    original = dialogo.responder(sessao.id, "Você já foi à capital?")
    novo = dialogo.regenerar(original.id)
    assert repositorio.buscar_turno(original.id).decisao == "regenerada"
    assert novo.id != original.id and novo.fala_jogador == original.fala_jogador
    assert novo.indice == original.indice + 1
    with pytest.raises(ValueError):
        dialogo.regenerar(original.id)


def test_fato_id_inexistente_e_rebaixado(ambiente):
    turno = dialogo.responder(_sessao().id, "Isso é alucina?")
    assert turno.verificacao.veredito == "indeterminado"
    assert turno.verificacao.fato_id is None
    assert "[rebaixado]" in turno.verificacao.justificativa


def test_rebaixamento_considera_so_fatos_ativos(ambiente):
    fatos = repositorio.listar_fatos("ines")
    repositorio.desativar_fato("ines", "F02")
    ativos = repositorio.listar_fatos("ines")
    r = ResultadoVerificacao(veredito="contradiz", fato_id="F02", justificativa="x")
    assert dialogo.aplicar_rebaixamento(r, fatos).veredito == "contradiz"
    assert dialogo.aplicar_rebaixamento(r, ativos).veredito == "indeterminado"


def test_promocao_faz_contradicao_posterior_ser_detectada(ambiente):
    """Cenário Negativo 1 e critério de aceitação do PRD."""
    sessao = _sessao()
    inventou = dialogo.responder(sessao.id, "Você tinha marido?")
    dialogo.decidir(inventou.id, "aceita")

    antes = dialogo.responder(sessao.id, "Você criou o Tomé sozinha?")
    assert antes.verificacao.veredito == "consistente"   # cânone não sabe do marido
    dialogo.decidir(antes.id, "descartada")

    fato = dialogo.promover(inventou.id, "Inês foi casada.")
    assert fato.id == "F11" and fato.origem == "promovido"
    assert fato.turno_origem_id == inventou.id

    depois = dialogo.responder(sessao.id, "Você criou o Tomé sozinha?")
    assert depois.verificacao.veredito == "contradiz"
    assert depois.verificacao.fato_id == "F11"


def test_promover_turno_pendente_tambem_aceita(ambiente):
    turno = dialogo.responder(_sessao().id, "Você tinha marido?")
    dialogo.promover(turno.id, "Inês foi casada.")
    assert repositorio.buscar_turno(turno.id).decisao == "aceita"


def test_nada_e_decidido_automaticamente(ambiente):
    turno = dialogo.responder(_sessao().id, "Você já foi à capital?")
    assert turno.decisao == "pendente"   # sinalizada, mas não bloqueada


def test_entradas_invalidas(ambiente):
    with pytest.raises(ValueError):
        dialogo.responder(_sessao().id, "   ")
    with pytest.raises(ValueError):
        dialogo.responder("nao-existe", "Oi")
    turno = dialogo.responder(_sessao().id, "Oi")
    with pytest.raises(ValueError):
        dialogo.decidir(turno.id, "talvez")
    with pytest.raises(ValueError):
        dialogo.promover(turno.id, "  ")


def test_janela_de_memoria(ambiente, monkeypatch):
    monkeypatch.setattr(dialogo, "JANELA_MEMORIA", 2)
    sessao = _sessao()
    for i in range(4):
        t = dialogo.responder(sessao.id, f"pergunta {i}")
        dialogo.decidir(t.id, "aceita")
    ambiente.requisicoes.clear()
    dialogo.responder(sessao.id, "final")
    conteudos = [m["content"] for m in ambiente.requisicoes[0]["messages"]]
    assert "pergunta 0" not in conteudos and "pergunta 3" in conteudos
