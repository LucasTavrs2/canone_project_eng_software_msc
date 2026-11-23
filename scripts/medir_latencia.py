"""Mede a latência real de um turno (geração + verificação).

Conduz uma sessão curta com perguntas fixas pelo mesmo serviço que as
interfaces usam, aceitando cada fala, e registra o tempo de cada chamada.
O número alimenta o Cenário Negativo 2 e a seção de requisitos não-funcionais.

Da pasta do projeto:
    python scripts\\medir_latencia.py
    python scripts\\medir_latencia.py --turnos 10
"""
import argparse
from datetime import datetime
from statistics import mean, median

from _registro import RAIZ, Registro

from core import dialogo
from infrastructure import repositorio
from infrastructure.provedor import ErroProvedor, descrever_configuracao

PERGUNTAS = [
    "Bom dia. Que ervas você tem hoje?",
    "Como está o rio?",
    "O inverno vai ser duro?",
    "Você troca ervas por quê?",
    "Quem te ensinou o ofício?",
    "Você sabe tratar a febre-do-charco?",
    "Onde fica sua casa?",
    "O que você acha da guilda?",
    "Há quanto tempo mora aqui?",
    "O que cresce no leito velho?",
]


def main() -> int:
    p = argparse.ArgumentParser(description="Mede a latência por turno.")
    p.add_argument("--personagem", default="ines")
    p.add_argument("--turnos", type=int, default=5, choices=range(1, len(PERGUNTAS) + 1),
                   metavar=f"1..{len(PERGUNTAS)}")
    p.add_argument("--saida", default=str(RAIZ / "docs/evidencias/latencia.txt"))
    args = p.parse_args()

    personagem = repositorio.buscar_personagem(args.personagem)
    if personagem is None:
        print(f"Personagem {args.personagem!r} não está no banco.")
        return 1

    log = Registro(args.saida)
    cfg = descrever_configuracao()
    sessao = dialogo.nova_sessao(personagem.id, f"medição de latência {datetime.now():%Y-%m-%d %H:%M}")
    log(f"Medição de latência · {datetime.now():%Y-%m-%d %H:%M} · sessão {sessao.id}")
    log(f"Gerador: {cfg['gerador']['modelo']} (reasoning_effort={cfg['gerador']['raciocinio']})")
    log(f"Verificador: {cfg['verificador']['modelo']} "
        f"(reasoning_effort={cfg['verificador']['raciocinio']})\n")
    log(f"{'#':>2}  {'geração':>8}  {'verific.':>8}  {'total':>7}  pergunta")

    geracao, verificacao = [], []
    try:
        for i, pergunta in enumerate(PERGUNTAS[:args.turnos], 1):
            turno = dialogo.responder(sessao.id, pergunta)
            dialogo.decidir(turno.id, "aceita")
            g, v = turno.latencia_geracao_ms / 1000, turno.latencia_verificacao_ms / 1000
            geracao.append(g)
            verificacao.append(v)
            log(f"{i:>2}  {g:>7.1f}s  {v:>7.1f}s  {g + v:>6.1f}s  {pergunta}")
    except ErroProvedor as erro:
        log(f"\n[provedor] {erro}")
        log.fechar()
        return 3

    totais = [g + v for g, v in zip(geracao, verificacao)]
    log("")
    log(f"Geração:     média {mean(geracao):.1f} s · mediana {median(geracao):.1f} s")
    log(f"Verificação: média {mean(verificacao):.1f} s · mediana {median(verificacao):.1f} s")
    log(f"Turno:       média {mean(totais):.1f} s · mín {min(totais):.1f} s · "
        f"máx {max(totais):.1f} s")
    log.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
