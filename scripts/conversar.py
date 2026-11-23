"""Conversa com um NPC pelo terminal (alternativa à interface web).

Da pasta do projeto:
    python scripts\\conversar.py
    python scripts\\conversar.py ines --registro docs\\evidencias\\cn1_promocao.txt

A cada fala do NPC:
    [a]ceitar   a fala entra na memória da sessão
    [r]egenerar descarta esta versão e gera outra para a mesma pergunta
    [d]escartar a fala fica só no registro
    [p]romover  aceita e transforma uma afirmação da fala em fato canônico
    [f]atos     mostra o cânone atual (não decide nada)

Com --registro, a conversa inteira, inclusive o que você digita, é gravada
num arquivo UTF-8.
"""
import argparse

from _registro import Registro

from core import dialogo
from infrastructure import repositorio
from infrastructure.provedor import ErroProvedor

MARCA = {"consistente": " ok ", "contradiz": "CONTRADIZ", "indeterminado": " ?? "}


def escolher_sessao(personagem_id: str, log: Registro, titulo: str | None) -> str:
    if titulo:
        return dialogo.nova_sessao(personagem_id, titulo).id
    sessoes = repositorio.listar_sessoes(personagem_id)[:10]
    if sessoes:
        log("\nSessões existentes:")
        for i, s in enumerate(sessoes, 1):
            log(f"  {i}. {s.titulo} ({repositorio.contar_turnos(s.id)} turnos)")
        escolha = log.entrada("Número para continuar, ou Enter para nova: ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(sessoes):
            return sessoes[int(escolha) - 1].id
    titulo = log.entrada("Título da nova sessão: ").strip() or "sem título"
    return dialogo.nova_sessao(personagem_id, titulo).id


def mostrar_fatos(personagem_id: str, log: Registro) -> None:
    for f in repositorio.listar_fatos(personagem_id):
        origem = "  (promovido)" if f.origem == "promovido" else ""
        log(f"        [{f.id}] {f.texto}{origem}")


def ler_acao(log: Registro) -> str:
    while True:
        acao = log.entrada(
            "        [a]ceitar / [r]egenerar / [d]escartar / [p]romover / [f]atos > "
        ).strip().lower()
        if acao in {"a", "r", "d", "p", "f"}:
            return acao
        log("        Responda a, r, d, p ou f.")


def main() -> None:
    p = argparse.ArgumentParser(description="Conversa com um NPC pelo terminal.")
    p.add_argument("personagem", nargs="?", default="ines")
    p.add_argument("--registro", help="grava a conversa neste arquivo (UTF-8)")
    p.add_argument("--titulo", help="cria direto uma sessão nova com este título")
    args = p.parse_args()

    log = Registro(args.registro)
    personagem = repositorio.buscar_personagem(args.personagem)
    if personagem is None:
        log(f"Personagem {args.personagem!r} não encontrado no banco.")
        log("Importe com: python -m cli importar data\\personagens\\ines.yaml")
        return

    sessao_id = escolher_sessao(personagem.id, log, args.titulo)
    anteriores = repositorio.contar_turnos(sessao_id)
    log(f"\n=== Conversando com {personagem.nome} ===")
    if anteriores:
        log(f"Retomando sessão com {anteriores} turnos.")
    log("Enter vazio encerra.\n")

    try:
        while True:
            pergunta = log.entrada("você > ").strip()
            if not pergunta:
                break
            try:
                turno = dialogo.responder(sessao_id, pergunta)
            except ErroProvedor as erro:
                log(f"\n[provedor] {erro}\n")
                continue

            while True:
                v = turno.verificacao
                log(f"\n{personagem.nome} > {turno.fala_npc}")
                log(f"        [{MARCA[v.veredito]}] {v.fato_id or '-'} · {v.justificativa}")
                log(f"        geração {turno.latencia_geracao_ms / 1000:.1f} s + "
                    f"verificação {turno.latencia_verificacao_ms / 1000:.1f} s")

                acao = ler_acao(log)
                while acao == "f":
                    mostrar_fatos(personagem.id, log)
                    acao = ler_acao(log)

                if acao == "r":
                    try:
                        turno = dialogo.regenerar(turno.id)
                    except ErroProvedor as erro:
                        log(f"\n[provedor] {erro}\n")
                        dialogo.decidir(turno.id, "descartada")
                        break
                    continue
                if acao == "d":
                    dialogo.decidir(turno.id, "descartada")
                elif acao == "p":
                    texto = log.entrada("        Afirmação a promover (fato em 3ª pessoa): ").strip()
                    if texto:
                        fato = dialogo.promover(turno.id, texto)
                        log(f"        Promovido como [{fato.id}] {fato.texto}")
                    else:
                        dialogo.decidir(turno.id, "aceita")
                        log("        Nada promovido; fala aceita.")
                else:
                    dialogo.decidir(turno.id, "aceita")
                log()
                break
    except (EOFError, KeyboardInterrupt):
        log()

    log(f"\nSessão {sessao_id} salva com {repositorio.contar_turnos(sessao_id)} turnos.")
    log.fechar()


if __name__ == "__main__":
    main()
