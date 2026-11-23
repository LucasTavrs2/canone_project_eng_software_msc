"""Exemplo de integração: o script de NPCs do vilarejo chamando o Cânone.

Reproduz o Cenário Positivo 2. As falas de um jogador de playtest são enviadas
à Inês pelo módulo importável (cli.api). A política escolhida pelo
desenvolvedor, e não pelo Cânone, é:

  - fala consistente: vai para a tela e entra na memória da Inês;
  - fala sinalizada (contradiz ou indeterminado): é trocada por uma linha de
    esquiva escrita pela equipe e descartada da memória.

No fim, o registro completo da sessão é exportado para a roteirista.

Da pasta do projeto:
    python exemplos\\vilarejo.py
    python exemplos\\vilarejo.py --interativo
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

# Em um jogo de verdade, este caminho apontaria para a pasta do Cânone.
RAIZ_CANONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_CANONE))

from cli import api  # noqa: E402

LINHA_DE_ESQUIVA = "Não tenho tempo pra isso. Vai embora."

FALAS_DO_PLAYTEST = [
    "Bom dia. Você vende ervas?",
    "Aceita moedas de prata?",
    "Ouvi dizer que você foi à capital semana passada.",
    "Você conhece alguém da guilda?",
    "O que aconteceu com seu filho?",
    "Pode preparar o remédio da febre-do-charco?",
]


def falar_com_npc(sessao_id: str, fala_jogador: str) -> tuple[str, api.Turno]:
    """O que o script do vilarejo faria a cada interação com a Inês."""
    turno = api.responder(sessao_id, fala_jogador)
    if turno.verificacao.veredito == "consistente":
        api.decidir(turno.id, "aceita")
        return turno.fala_npc, turno
    api.decidir(turno.id, "descartada")
    return LINHA_DE_ESQUIVA, turno


def main() -> int:
    p = argparse.ArgumentParser(description="Integração de exemplo (Cenário Positivo 2).")
    p.add_argument("--personagem", default="ines")
    p.add_argument("--interativo", action="store_true",
                   help="digitar as falas do jogador em vez de usar a lista pronta")
    p.add_argument("--saida", help="arquivo JSON do registro (padrão: docs/evidencias/)")
    args = p.parse_args()

    personagem = api.buscar_personagem(args.personagem)
    if personagem is None:
        print(f"Personagem {args.personagem!r} não está no banco. Importe com:\n"
              f"  python -m cli importar data\\personagens\\{args.personagem}.yaml")
        return 1

    carimbo = datetime.now().strftime("%Y%m%d_%H%M")
    sessao = api.nova_sessao(personagem.id, f"vilarejo {carimbo}")
    falas = iter(lambda: input("jogador > ").strip(), "") if args.interativo else FALAS_DO_PLAYTEST

    turnos: list[api.Turno] = []
    try:
        for fala in falas:
            if not args.interativo:
                print(f"jogador > {fala}")
            try:
                exibida, turno = falar_com_npc(sessao.id, fala)
            except api.ErroProvedor as erro:
                print(f"\n[provedor] {erro}")
                return 3
            turnos.append(turno)
            v = turno.verificacao
            total = (turno.latencia_geracao_ms + turno.latencia_verificacao_ms) / 1000
            print(f"{personagem.nome} > {exibida}")
            print(f"   (debug: {v.veredito}{' ' + v.fato_id if v.fato_id else ''} · "
                  f"{total:.1f} s · fala original: {turno.fala_npc!r})\n")
    except (EOFError, KeyboardInterrupt):
        print()

    if not turnos:
        return 0

    destino = Path(args.saida) if args.saida else (
        RAIZ_CANONE / "docs" / "evidencias" / f"vilarejo_{carimbo}.json")
    api.salvar_sessao_json(sessao.id, destino)

    sinalizadas = [t for t in turnos if t.verificacao.veredito != "consistente"]
    latencias = [(t.latencia_geracao_ms + t.latencia_verificacao_ms) / 1000 for t in turnos]
    print(f"Turnos: {len(turnos)} · trocados por esquiva: {len(sinalizadas)} · "
          f"latência média por turno: {mean(latencias):.1f} s")
    print(f"Registro exportado para a roteirista: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
