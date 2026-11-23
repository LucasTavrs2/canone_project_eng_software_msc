"""Adaptador do provedor de modelo de linguagem.

Fala com qualquer servidor que implemente a API de chat da OpenAI
(POST {url}/chat/completions). Foi testado com o LM Studio rodando localmente.

Toda a configuração vem de variáveis de ambiente, lidas a cada chamada. Trocar
de modelo ou de endereço não exige mudar código em core/ (RF10, RNF02).

Gerador e verificador são configurados por papel. Cada variável pode ser
definida para os dois papéis de uma vez (CANONE_LLM_*) ou só para um deles
(CANONE_GERADOR_* / CANONE_VERIFICADOR_*), que tem precedência:

    CANONE_LLM_URL        endereço base     (padrão http://localhost:1234/v1)
    CANONE_LLM_MODEL      identificador do modelo (padrão qwen/qwen3.6-35b-a3b)
    CANONE_LLM_API_KEY    chave, se o servidor exigir (o LM Studio não exige)
    CANONE_LLM_REASONING  valor de reasoning_effort (padrão "none";
                          vazio = não enviar o parâmetro)
    CANONE_LLM_TIMEOUT    segundos de espera por resposta (padrão 300)

Exemplo: usar um modelo menor só no verificador
    $env:CANONE_VERIFICADOR_MODEL = "openai/gpt-oss-20b"
"""
import os
import re
from dataclasses import asdict, dataclass

import requests
from pydantic import ValidationError

from core.models import ResultadoVerificacao

PADROES = {
    "URL": "http://localhost:1234/v1",
    "MODEL": "qwen/qwen3.6-35b-a3b",
    "API_KEY": "",
    # Sem isto, o Qwen3.6 gasta todo o orçamento de tokens raciocinando e
    # devolve content vazio. "/no_think" e chat_template_kwargs não funcionaram
    # no build testado; reasoning_effort="none" funcionou (reasoning_tokens: 0).
    "REASONING": "none",
    "TIMEOUT": "300",
}

# Decisões de projeto, não configuração: o gerador precisa de variedade
# (um NPC que responde sempre igual não serve para testar), o verificador
# precisa de julgamento estável (a mesma fala deve receber o mesmo veredito).
TEMPERATURA = {"gerador": 0.85, "verificador": 0.1}
MAX_TOKENS = {"gerador": 250, "verificador": 300}


class ErroProvedor(RuntimeError):
    """Erro genérico de comunicação com o provedor de modelo."""


class ProvedorIndisponivel(ErroProvedor):
    """Servidor fora do ar, endereço errado, chave recusada ou modelo não encontrado."""


class RespostaVazia(ErroProvedor):
    """O modelo respondeu, mas sem conteúdo aproveitável."""


class RespostaInvalida(ErroProvedor):
    """O verificador respondeu algo que não segue o esquema esperado."""


@dataclass(frozen=True)
class ConfigPapel:
    papel: str
    url: str
    modelo: str
    chave: str
    raciocinio: str | None
    timeout: float
    temperatura: float
    max_tokens: int

    def descrever(self) -> dict:
        """Versão segura para exibir e exportar (nunca inclui a chave)."""
        dados = asdict(self)
        dados["chave"] = "definida" if self.chave else "não definida"
        return dados


def _ler(papel: str, nome: str) -> str:
    for variavel in (f"CANONE_{papel.upper()}_{nome}", f"CANONE_LLM_{nome}"):
        if variavel in os.environ:
            return os.environ[variavel].strip()
    return PADROES[nome]


def configuracao(papel: str) -> ConfigPapel:
    if papel not in TEMPERATURA:
        raise ValueError(f"papel desconhecido: {papel!r}")
    try:
        timeout = float(_ler(papel, "TIMEOUT"))
    except ValueError:
        timeout = float(PADROES["TIMEOUT"])
    return ConfigPapel(
        papel=papel,
        url=_ler(papel, "URL").rstrip("/"),
        modelo=_ler(papel, "MODEL"),
        chave=_ler(papel, "API_KEY"),
        raciocinio=_ler(papel, "REASONING") or None,
        timeout=timeout,
        temperatura=TEMPERATURA[papel],
        max_tokens=MAX_TOKENS[papel],
    )


def descrever_configuracao() -> dict:
    return {papel: configuracao(papel).descrever() for papel in TEMPERATURA}


def _cabecalhos(cfg: ConfigPapel) -> dict:
    return {"Authorization": f"Bearer {cfg.chave}"} if cfg.chave else {}


_BLOCO_PENSAMENTO = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CERCA_CODIGO = re.compile(r"^```(?:json)?\s*|\s*```$")


def _limpar(texto: str) -> str:
    """Remove bloco de raciocínio inline e cercas de código, se vierem."""
    texto = _BLOCO_PENSAMENTO.sub("", texto)
    texto = _CERCA_CODIGO.sub("", texto.strip())
    return texto.strip()


def _chamar(papel: str, messages: list[dict], response_format: dict | None = None) -> str:
    cfg = configuracao(papel)
    payload = {
        "model": cfg.modelo,
        "messages": messages,
        "temperature": cfg.temperatura,
        "max_tokens": cfg.max_tokens,
    }
    if cfg.raciocinio:
        payload["reasoning_effort"] = cfg.raciocinio
    if response_format is not None:
        payload["response_format"] = response_format

    try:
        resposta = requests.post(
            f"{cfg.url}/chat/completions",
            json=payload,
            headers=_cabecalhos(cfg),
            timeout=cfg.timeout,
        )
    except requests.exceptions.ConnectionError as erro:
        raise ProvedorIndisponivel(
            f"Não foi possível conectar em {cfg.url} ({papel}).\n"
            "  Ligue o servidor na aba Developer do LM Studio (Status deve ficar "
            "'Running') ou ajuste a variável CANONE_LLM_URL."
        ) from erro
    except requests.exceptions.Timeout as erro:
        raise ProvedorIndisponivel(
            f"O modelo não respondeu em {cfg.timeout:.0f}s ({papel}).\n"
            "  Verifique se o modelo está carregado e se a máquina não está saturada."
        ) from erro
    except requests.exceptions.RequestException as erro:
        raise ErroProvedor(f"Falha ao falar com {cfg.url}: {erro}") from erro

    if resposta.status_code in (401, 403):
        raise ProvedorIndisponivel(
            f"O servidor recusou a chave de acesso (HTTP {resposta.status_code}).\n"
            "  Confira a variável CANONE_LLM_API_KEY."
        )
    if resposta.status_code == 404:
        raise ProvedorIndisponivel(
            f"Servidor respondeu, mas o modelo {cfg.modelo!r} não foi encontrado.\n"
            f"  Veja o identificador exato em {cfg.url}/models e ajuste "
            "CANONE_LLM_MODEL."
        )
    if resposta.status_code != 200:
        raise ErroProvedor(
            f"O servidor respondeu HTTP {resposta.status_code} ({papel}).\n"
            f"  Detalhe: {resposta.text[:300]}"
        )

    try:
        escolha = resposta.json()["choices"][0]
        mensagem = escolha["message"]
    except (ValueError, KeyError, IndexError, TypeError) as erro:
        raise RespostaInvalida(
            f"Resposta fora do formato da API de chat: {resposta.text[:200]!r}"
        ) from erro

    conteudo = _limpar(mensagem.get("content") or "")
    if conteudo:
        return conteudo

    motivo = escolha.get("finish_reason")
    raciocinio = (mensagem.get("reasoning_content") or "").strip()
    if motivo == "length" and raciocinio:
        raise RespostaVazia(
            "O modelo consumiu todo o orçamento de tokens raciocinando e não "
            "chegou a escrever a resposta.\n"
            "  O servidor ignorou reasoning_effort. Desligue o raciocínio do modelo "
            "no LM Studio ou use outro modelo."
        )
    raise RespostaVazia(
        f"O modelo devolveu conteúdo vazio (finish_reason={motivo!r}).\n"
        f"  Raciocínio recebido: {raciocinio[:200]!r}"
    )


def gerar(messages: list[dict]) -> str:
    """Chamada 1: fala do NPC."""
    return _chamar("gerador", messages)


ESQUEMA_VERIFICACAO = {
    "type": "json_schema",
    "json_schema": {
        "name": "resultado_verificacao",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "veredito": {
                    "type": "string",
                    "enum": ["consistente", "contradiz", "indeterminado"],
                },
                "fato_id": {"type": ["string", "null"]},
                "justificativa": {"type": "string"},
            },
            "required": ["veredito", "fato_id", "justificativa"],
            "additionalProperties": False,
        },
    },
}


def verificar(messages: list[dict]) -> ResultadoVerificacao:
    """Chamada 2: veredito sobre a fala, validado pelo esquema Pydantic.

    O servidor recebe o esquema JSON e deveria respeitá-lo, mas nada garante
    isso; a validação aqui é a garantia de fato.
    """
    bruto = _chamar("verificador", messages, response_format=ESQUEMA_VERIFICACAO)
    try:
        return ResultadoVerificacao.model_validate_json(bruto)
    except ValidationError as erro:
        raise RespostaInvalida(
            "O verificador não devolveu um JSON no formato esperado.\n"
            f"  Recebido: {bruto[:200]!r}"
        ) from erro


def listar_modelos(papel: str = "gerador") -> list[str]:
    """Pergunta ao servidor quais modelos ele oferece. Serve de teste de conexão."""
    cfg = configuracao(papel)
    try:
        resposta = requests.get(
            f"{cfg.url}/models", headers=_cabecalhos(cfg), timeout=10
        )
    except requests.exceptions.RequestException as erro:
        raise ProvedorIndisponivel(
            f"Não foi possível conectar em {cfg.url}.\n"
            "  Ligue o servidor na aba Developer do LM Studio (Status deve ficar "
            "'Running') ou ajuste a variável CANONE_LLM_URL."
        ) from erro
    if resposta.status_code != 200:
        raise ProvedorIndisponivel(
            f"O servidor em {cfg.url} respondeu HTTP {resposta.status_code} "
            "ao listar modelos."
        )
    try:
        return [m["id"] for m in resposta.json().get("data", [])]
    except (ValueError, KeyError, TypeError) as erro:
        raise RespostaInvalida("Lista de modelos fora do formato esperado.") from erro
