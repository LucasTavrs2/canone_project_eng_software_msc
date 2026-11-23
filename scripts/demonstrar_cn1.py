"""Demonstração isolada do Cenário Negativo 1 e do efeito da promoção (RF07).

Passa falas fixas pelo verificador, sem passar pelo gerador. Isso isola o
verificador do ruído da geração: a única coisa que muda entre "antes" e
"depois" é a presença do fato promovido no cânone.

    Fase 1  o NPC inventa um detalhe (marido)            -> esperado: consistente
    Fase 2  o NPC contradiz o detalhe ("nunca tive...")  -> esperado: consistente  (CN1)
    Fase 3  a roteirista promove o detalhe a cânone
    Fase 4  a mesma fala da fase 2, de novo              -> esperado: contradiz / Fnn

O fato promovido existe só na memória deste script; o banco não é alterado,
a menos que se use --gravar.

Da pasta do projeto:
    python scripts\\demonstrar_cn1.py
    python scripts\\demonstrar_cn1.py --repeticoes 5
"""
import argparse
from collections import Counter
from datetime import datetime, timezone

from _registro import RAIZ, Registro

from core.dialogo import verificar_fala
from core.models import FatoCanonico
from infrastructure import repositorio
from infrastructure.provedor import ErroProvedor, descrever_configuracao

FALA_INVENTADA = "Meu marido trabalhava pra guilda. Morreu antes da cheia."
FALA_CONTRADITORIA = "Nunca tive marido. Criei o Tomé sozinha desde o começo."
FATO_PROMOVIDO = "Inês foi casada."


def rodar(log, rotulo, fala, fatos, repeticoes):
    log(f'  fala: "{fala}"')
    resultados = [verificar_fala(fala, fatos) for _ in range(repeticoes)]
    contagem = Counter((r.veredito, r.fato_id) for r in resultados)
    for (veredito, fato_id), n in contagem.items():
        log(f"  veredito: {veredito}{' / ' + fato_id if fato_id else ''}  ({n}/{repeticoes})")
    log(f"  justificativa: {resultados[0].justificativa}")
    return contagem.most_common(1)[0][0]


def main() -> int:
    p = argparse.ArgumentParser(description="Demonstração do Cenário Negativo 1.")
    p.add_argument("--personagem", default="ines")
    p.add_argument("--fala-inventada", default=FALA_INVENTADA)
    p.add_argument("--fala-contraditoria", default=FALA_CONTRADITORIA)
    p.add_argument("--fato", default=FATO_PROMOVIDO, help="afirmação a promover")
    p.add_argument("--repeticoes", type=int, default=3)
    p.add_argument("--gravar", action="store_true", help="grava o fato promovido no banco")
    p.add_argument("--saida", default=str(RAIZ / "docs/evidencias/cn1_verificador.txt"))
    args = p.parse_args()

    personagem = repositorio.buscar_personagem(args.personagem)
    if personagem is None:
        print(f"Personagem {args.personagem!r} não está no banco.")
        return 1

    log = Registro(args.saida)
    fatos = repositorio.listar_fatos(personagem.id)
    novo_id = repositorio.proximo_id_fato(personagem.id)
    promovido = FatoCanonico(id=novo_id, personagem_id=personagem.id, texto=args.fato,
                             origem="promovido", criado_em=datetime.now(timezone.utc))
    cfg = descrever_configuracao()["verificador"]

    log(f"Demonstração do Cenário Negativo 1 · {datetime.now():%Y-%m-%d %H:%M}")
    log(f"Verificador: {cfg['modelo']} · temperatura {cfg['temperatura']} · "
        f"{args.repeticoes} repetições por fala\n")
    log(f"Cânone ativo de {personagem.nome} ({len(fatos)} fatos):")
    for f in fatos:
        log(f"  [{f.id}] {f.texto}")

    try:
        log("\nFase 1 · o NPC inventa um detalhe, que não é promovido")
        f1 = rodar(log, "fase1", args.fala_inventada, fatos, args.repeticoes)
        log("  -> informação nova não é contradição; nada a sinalizar.")

        log("\nFase 2 · quinze falas depois, o NPC contradiz o que inventou")
        f2 = rodar(log, "fase2", args.fala_contraditoria, fatos, args.repeticoes)
        log("  -> Cenário Negativo 1: a contradição é entre duas falas do NPC, e o")
        log("     verificador só compara cada fala com o cânone declarado.")

        log("\nFase 3 · a roteirista promove o detalhe a fato canônico")
        log(f"  [{promovido.id}] {promovido.texto}  (origem: promovido)")
        if args.gravar:
            repositorio.promover_a_canone(personagem.id, args.fato)
            log("  (gravado no banco)")

        log("\nFase 4 · a mesma fala da fase 2, verificada de novo")
        f4 = rodar(log, "fase4", args.fala_contraditoria, fatos + [promovido], args.repeticoes)
    except ErroProvedor as erro:
        log(f"\n[provedor] {erro}")
        log.fechar()
        return 3

    esperado = (f1[0] == "consistente" and f2[0] == "consistente"
                and f4 == ("contradiz", promovido.id))
    log("\nResumo")
    log(f"  fase 2 antes da promoção: {f2[0]}")
    log(f"  fase 2 depois da promoção: {f4[0]}{' / ' + f4[1] if f4[1] else ''}")
    if esperado:
        log("  Resultado conforme o esperado: a promoção é o que torna a contradição detectável.")
    else:
        log("  Resultado diferente do esperado. Veja as justificativas acima; tente outra")
        log("  redação com --fala-inventada, --fala-contraditoria ou --fato.")
    log.fechar()
    return 0 if esperado else 2


if __name__ == "__main__":
    raise SystemExit(main())
