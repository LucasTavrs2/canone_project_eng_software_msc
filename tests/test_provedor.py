"""Adaptador do provedor: configuração por papel e mensagens de erro."""
import socket

import pytest

from infrastructure import provedor


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_configuracao_por_papel(monkeypatch):
    monkeypatch.setenv("CANONE_LLM_MODEL", "modelo-geral")
    monkeypatch.setenv("CANONE_VERIFICADOR_MODEL", "modelo-verificador")
    monkeypatch.delenv("CANONE_GERADOR_MODEL", raising=False)
    assert provedor.configuracao("gerador").modelo == "modelo-geral"
    assert provedor.configuracao("verificador").modelo == "modelo-verificador"


def test_reasoning_vazio_nao_envia_parametro(ambiente, monkeypatch):
    monkeypatch.setenv("CANONE_LLM_REASONING", "")
    provedor.gerar([{"role": "user", "content": "oi"}])
    assert "reasoning_effort" not in ambiente.requisicoes[-1]


def test_reasoning_padrao_e_none(ambiente):
    provedor.gerar([{"role": "user", "content": "oi"}])
    assert ambiente.requisicoes[-1]["reasoning_effort"] == "none"


def test_chave_nao_aparece_na_descricao(monkeypatch):
    monkeypatch.setenv("CANONE_LLM_API_KEY", "segredo")
    texto = str(provedor.descrever_configuracao())
    assert "segredo" not in texto


def test_servidor_fora_do_ar(monkeypatch):
    monkeypatch.setenv("CANONE_LLM_URL", f"http://127.0.0.1:{_porta_livre()}/v1")
    with pytest.raises(provedor.ProvedorIndisponivel, match="aba Developer"):
        provedor.gerar([{"role": "user", "content": "oi"}])
    with pytest.raises(provedor.ProvedorIndisponivel):
        provedor.listar_modelos()


def test_modelo_inexistente(ambiente, monkeypatch):
    monkeypatch.setenv("CANONE_LLM_MODEL", "outro-modelo")
    with pytest.raises(provedor.ProvedorIndisponivel, match="não foi encontrado"):
        provedor.gerar([{"role": "user", "content": "oi"}])


def test_resposta_vazia_por_raciocinio(ambiente):
    ambiente.modo = "vazio"
    with pytest.raises(provedor.RespostaVazia, match="raciocinando"):
        provedor.gerar([{"role": "user", "content": "oi"}])


def test_json_fora_do_esquema_e_recusado(ambiente):
    ambiente.modo = "json_quebrado"
    with pytest.raises(provedor.RespostaInvalida):
        provedor.verificar([{"role": "user", "content": "FALA A VERIFICAR\noi"}])


def test_listar_modelos(ambiente):
    assert provedor.listar_modelos() == ["modelo-falso"]


def test_fato_id_ignorado_fora_de_contradicao():
    from core.models import ResultadoVerificacao

    r = ResultadoVerificacao.model_validate_json(
        '{"veredito": "consistente", "fato_id": "F08", "justificativa": "confirma F08"}'
    )
    assert r.fato_id is None
