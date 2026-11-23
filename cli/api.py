"""Módulo importável do Cânone para o desenvolvedor de gameplay (RF09).

Esta é a superfície pública estável para scripts de jogo. Tudo o que está em
__all__ pode ser usado sem conhecer o resto do código.

Uso típico, no script que controla os NPCs:

    import sys
    sys.path.insert(0, r"C:\\caminho\\para\\canone")
    from cli import api

    sessao = api.nova_sessao("ines", "playtest de sexta")
    turno = api.responder(sessao.id, "Você conhece a guilda?")

    if turno.verificacao.veredito == "consistente":
        api.decidir(turno.id, "aceita")       # entra na memória do NPC
        exibir(turno.fala_npc)
    else:
        api.decidir(turno.id, "descartada")   # fica só no registro
        exibir(LINHA_DE_ESQUIVA)

    api.salvar_sessao_json(sessao.id, "registros/playtest.json")

O Cânone informa, não decide: o que fazer com uma fala sinalizada é escolha
de quem chama (RNF07). Cada chamada a responder() faz duas chamadas ao modelo
e leva segundos; use em tempo de autoria ou para pré-gerar falas, não durante
a partida.
"""
from core.dialogo import (
    decidir,
    nova_sessao,
    promover,
    regenerar,
    responder,
    turno_pendente,
    verificar_fala_contra_canone,
)
from core.models import (
    FatoCanonico,
    Personagem,
    ResultadoVerificacao,
    Sessao,
    SessaoExportada,
    Turno,
)
from infrastructure.pacote import (
    PacoteInvalido,
    exportar_ficha,
    exportar_sessao,
    ficha_para_yaml,
    importar_ficha_yaml,
    salvar_sessao_json,
)
from infrastructure.provedor import (
    ErroProvedor,
    ProvedorIndisponivel,
    RespostaInvalida,
    RespostaVazia,
    descrever_configuracao,
    listar_modelos,
)
from infrastructure.repositorio import (
    buscar_personagem,
    buscar_sessao,
    buscar_turno,
    listar_fatos,
    listar_personagens,
    listar_sessoes,
    listar_turnos,
)

__all__ = [
    # ciclo de diálogo
    "nova_sessao", "responder", "decidir", "regenerar", "promover",
    "turno_pendente", "verificar_fala_contra_canone",
    # consulta
    "buscar_personagem", "buscar_sessao", "buscar_turno", "listar_fatos",
    "listar_personagens", "listar_sessoes", "listar_turnos",
    # pacotes
    "importar_ficha_yaml", "exportar_ficha", "ficha_para_yaml",
    "exportar_sessao", "salvar_sessao_json",
    # provedor
    "descrever_configuracao", "listar_modelos",
    # tipos
    "FatoCanonico", "Personagem", "ResultadoVerificacao", "Sessao",
    "SessaoExportada", "Turno",
    # erros
    "ErroProvedor", "ProvedorIndisponivel", "RespostaInvalida", "RespostaVazia",
    "PacoteInvalido",
]
