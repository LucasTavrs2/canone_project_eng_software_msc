"""Serviço de diálogo: o ciclo de um turno, compartilhado por todas as interfaces.

    fala do jogador
      -> contexto: ficha + cânone ativo + turnos aceitos (memória)
      -> chamada 1: geração da fala do NPC
      -> chamada 2: verificação (recebe só a fala e os fatos, nunca a ficha)
      -> validação determinística do fato_id (RNF04)
      -> persistência do turno como "pendente"
      -> decisão humana: aceitar, regenerar, descartar ou promover (RNF07)

A interface web (ui/), a linha de comando (cli/) e os scripts chamam estas
funções. Nenhuma delas reimplementa o ciclo.
"""
import time

from core.models import (
    FatoCanonico,
    Personagem,
    ResultadoVerificacao,
    Sessao,
    Turno,
)
from core.prompts import (
    SYSTEM_GERACAO,
    SYSTEM_VERIFICACAO,
    USER_VERIFICACAO,
    formatar_fatos,
    formatar_restricoes,
)
from infrastructure import provedor, repositorio

# Quantos turnos aceitos, no máximo, voltam ao prompt do gerador. Sessões de
# teste são curtas; o limite só evita estourar o contexto do modelo.
JANELA_MEMORIA = 30


# ------------------------------------------------------ montagem de prompts

def montar_prompt_geracao(personagem: Personagem, fatos: list[FatoCanonico],
                          memoria: list[Turno], fala_jogador: str) -> list[dict]:
    system = SYSTEM_GERACAO.format(
        nome=personagem.nome,
        papel=personagem.papel,
        registro_fala=personagem.registro_fala,
        restricoes=formatar_restricoes(personagem.restricoes),
        fatos=formatar_fatos(fatos),
    )
    mensagens = [{"role": "system", "content": system}]
    for turno in memoria[-JANELA_MEMORIA:]:
        mensagens.append({"role": "user", "content": turno.fala_jogador})
        mensagens.append({"role": "assistant", "content": turno.fala_npc})
    mensagens.append({"role": "user", "content": fala_jogador})
    return mensagens


def montar_prompt_verificacao(fala_npc: str, fatos: list[FatoCanonico]) -> list[dict]:
    """O verificador não recebe a ficha. Se soubesse quem é o personagem,
    tenderia a racionalizar uma contradição como "jeito dela"."""
    return [
        {"role": "system", "content": SYSTEM_VERIFICACAO},
        {"role": "user", "content": USER_VERIFICACAO.format(
            fatos=formatar_fatos(fatos), fala_npc=fala_npc)},
    ]


# ------------------------------------------------------------- verificação

def aplicar_rebaixamento(resultado: ResultadoVerificacao,
                         fatos: list[FatoCanonico]) -> ResultadoVerificacao:
    """RNF04: o fato_id vem de um modelo de linguagem e pode ser inventado.
    Uma contradição que aponta um fato inexistente ou inativo vira
    'indeterminado', com o motivo registrado na justificativa."""
    if resultado.veredito != "contradiz":
        return resultado
    if resultado.fato_id in {f.id for f in fatos}:
        return resultado
    return ResultadoVerificacao(
        veredito="indeterminado",
        fato_id=None,
        justificativa=(
            f"[rebaixado] O verificador apontou um fato inexistente "
            f"({resultado.fato_id!r}). Original: {resultado.justificativa}"
        ),
    )


def verificar_fala(fala_npc: str, fatos: list[FatoCanonico]) -> ResultadoVerificacao:
    """Verifica uma fala qualquer contra uma lista de fatos, sem gravar nada."""
    if not fala_npc.strip():
        raise provedor.RespostaVazia("Fala vazia não pode ser verificada.")
    bruto = provedor.verificar(montar_prompt_verificacao(fala_npc, fatos))
    return aplicar_rebaixamento(bruto, fatos)


def verificar_fala_contra_canone(personagem_id: str, fala_npc: str) -> ResultadoVerificacao:
    """Atalho para verificar uma fala escrita à mão (ou pré-gerada) contra o
    cânone ativo de um personagem."""
    return verificar_fala(fala_npc, repositorio.listar_fatos(personagem_id))


# ------------------------------------------------------------------- turnos

def _sessao_e_personagem(sessao_id: str) -> tuple[Sessao, Personagem]:
    sessao = repositorio.buscar_sessao(sessao_id)
    if sessao is None:
        raise ValueError(f"Sessão {sessao_id!r} não existe.")
    personagem = repositorio.buscar_personagem(sessao.personagem_id)
    if personagem is None:
        raise ValueError(f"Personagem {sessao.personagem_id!r} não existe.")
    return sessao, personagem


def _turno_existente(turno_id: str) -> Turno:
    turno = repositorio.buscar_turno(turno_id)
    if turno is None:
        raise ValueError(f"Turno {turno_id!r} não existe.")
    return turno


def nova_sessao(personagem_id: str, titulo: str) -> Sessao:
    return repositorio.criar_sessao(personagem_id, titulo)


def responder(sessao_id: str, fala_jogador: str) -> Turno:
    """Gera, verifica e grava um turno. Devolve o turno com decisão 'pendente'.

    Nada é aceito nem bloqueado aqui (RNF07): quem chama decide com
    decidir(), regenerar() ou promover().
    """
    fala_jogador = fala_jogador.strip()
    if not fala_jogador:
        raise ValueError("A fala do jogador está vazia.")

    sessao, personagem = _sessao_e_personagem(sessao_id)
    # O cânone é relido a cada turno: um fato promovido no turno anterior
    # já vale para o próximo.
    fatos = repositorio.listar_fatos(personagem.id)
    memoria = repositorio.listar_turnos(sessao.id, apenas_aceitos=True)

    inicio = time.perf_counter()
    fala_npc = provedor.gerar(montar_prompt_geracao(personagem, fatos, memoria, fala_jogador))
    meio = time.perf_counter()
    resultado = verificar_fala(fala_npc, fatos)
    fim = time.perf_counter()

    return repositorio.salvar_turno(
        sessao.id, fala_jogador, fala_npc, resultado,
        latencia_geracao_ms=round((meio - inicio) * 1000),
        latencia_verificacao_ms=round((fim - meio) * 1000),
    )


def decidir(turno_id: str, decisao: str) -> Turno:
    """Aceitar (a fala entra na memória) ou descartar (fica só no registro)."""
    if decisao not in ("aceita", "descartada"):
        raise ValueError("Use 'aceita' ou 'descartada'.")
    turno = _turno_existente(turno_id)
    if turno.decisao == "regenerada":
        raise ValueError("Este turno já foi substituído por uma regeneração.")
    return repositorio.atualizar_decisao(turno_id, decisao)


def regenerar(turno_id: str) -> Turno:
    """Marca o turno como 'regenerada' e gera outra fala para a mesma pergunta."""
    turno = _turno_existente(turno_id)
    if turno.decisao != "pendente":
        raise ValueError(
            f"Só é possível regenerar um turno pendente (este está '{turno.decisao}')."
        )
    novo = responder(turno.sessao_id, turno.fala_jogador)
    repositorio.atualizar_decisao(turno_id, "regenerada")
    return novo


def promover(turno_id: str, afirmacao: str) -> FatoCanonico:
    """RF07: transforma uma afirmação feita pelo NPC num fato canônico.

    A afirmação é escrita pela pessoa, como fato atômico em terceira pessoa
    ("Inês foi casada."), e não copiada da fala. O fato guarda o turno de
    origem. Se o turno estava pendente, promover também o aceita.
    """
    afirmacao = afirmacao.strip()
    if not afirmacao:
        raise ValueError("Escreva a afirmação que será promovida.")
    turno = _turno_existente(turno_id)
    sessao, personagem = _sessao_e_personagem(turno.sessao_id)
    fato = repositorio.promover_a_canone(personagem.id, afirmacao, turno_origem_id=turno.id)
    if turno.decisao == "pendente":
        repositorio.atualizar_decisao(turno.id, "aceita")
    return fato


def turno_pendente(sessao_id: str) -> Turno | None:
    """O turno mais recente que ainda espera decisão, se houver."""
    pendentes = [t for t in repositorio.listar_turnos(sessao_id) if t.decisao == "pendente"]
    return pendentes[-1] if pendentes else None
