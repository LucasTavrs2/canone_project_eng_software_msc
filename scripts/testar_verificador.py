"""Bateria de teste direto do verificador (sem gerador, sem banco).

Cada caso é uma fala escrita à mão, verificada contra os 10 fatos autorados da
Inês lidos do YAML. Ler do YAML, e não do banco, mantém o teste reprodutível
mesmo depois que fatos forem promovidos na interface.

Da pasta do projeto:
    python scripts\\testar_verificador.py
    python scripts\\testar_verificador.py --repeticoes 3 --saida docs\\evidencias\\verificador_estabilidade.txt

Ressalva metodológica: os casos foram escritos pelos autores do projeto e a
maioria é contradição explícita. Acertar todos indica ausência de falha em
casos claros, não acurácia geral.
"""
import argparse
import time
from collections import Counter
from datetime import datetime, timezone
from statistics import mean

from _registro import RAIZ, Registro

from core.dialogo import verificar_fala
from core.models import FatoCanonico
from infrastructure.pacote import ler_ficha_yaml
from infrastructure.provedor import ErroProvedor, descrever_configuracao

# (fala, veredito esperado, fato esperado). "?" = caso ambíguo, sem gabarito.
CASOS = [
    ("Fui à feira da cidade no mês passado.", "contradiz", "F02"),
    ("Minha mãe era ferreira, me ensinou a bater no ferro.", "contradiz", "F08"),
    ("A guilda é gente boa, confio neles.", "contradiz", "F04"),
    ("A queimadura fica no meu antebraço esquerdo.", "contradiz", "F03"),
    ("Aceito moeda de prata, se tiver.", "contradiz", "F06"),
    ("Tem outra herbolária no norte que também faz o remédio.", "contradiz", "F09"),
    ("Meu filho Tomé está lá fora cortando lenha.", "contradiz", "F01"),
    ("Minha casa fica na borda oeste, perto da colina.", "contradiz", "F07"),
    ("Troco ervas por lenha e grão.", "consistente", None),
    ("Aprendi tudo com minha mãe.", "consistente", None),
    ("Não saio daqui desde a cheia.", "consistente", None),
    ("Gosto do cheiro de alecrim pela manhã.", "consistente", None),
    # Casos difíceis: contradição indireta, implícita ou de grau
    ("Faz tempo que não vou tão longe assim.", "?", None),
    ("O menino já deve estar quase da minha altura.", "?", None),
    ("Peguei essas ervas na estrada da serra.", "?", None),
    ("Meu ouvido bom é o esquerdo.", "contradiz", "F10"),
    ("Conheço um da guilda que é decente.", "?", None),
    ("A prateleira de baixo é onde guardo o que era do Tomé.", "contradiz", "F05"),
]


def fatos_autorados() -> list[FatoCanonico]:
    ficha = ler_ficha_yaml(RAIZ / "data/personagens/ines.yaml")
    agora = datetime.now(timezone.utc)
    return [FatoCanonico(id=f.id, personagem_id=ficha.id, texto=f.texto, criado_em=agora)
            for f in ficha.fatos if f.ativo]


def main() -> int:
    p = argparse.ArgumentParser(description="Teste direto do verificador.")
    p.add_argument("--repeticoes", type=int, default=1,
                   help="quantas vezes verificar cada fala (mede estabilidade)")
    p.add_argument("--saida", default=str(RAIZ / "docs/evidencias/verificador_v2.txt"))
    args = p.parse_args()

    log = Registro(args.saida)
    fatos = fatos_autorados()
    cfg = descrever_configuracao()["verificador"]
    log(f"Teste do verificador · {datetime.now():%Y-%m-%d %H:%M}")
    log(f"Modelo: {cfg['modelo']} · temperatura {cfg['temperatura']} · "
        f"{len(fatos)} fatos · {args.repeticoes} repetição(ões) por caso\n")

    acertos_v = acertos_f = total_v = total_f = instaveis = 0
    latencias = []
    try:
        for fala, esperado, fato_esperado in CASOS:
            resultados = []
            for _ in range(args.repeticoes):
                inicio = time.perf_counter()
                resultados.append(verificar_fala(fala, fatos))
                latencias.append(time.perf_counter() - inicio)

            obtidos = Counter((r.veredito, r.fato_id) for r in resultados)
            estavel = len(obtidos) == 1
            instaveis += not estavel

            if esperado == "?":
                marca = "-- "
            else:
                ok = [r.veredito == esperado and (esperado != "contradiz" or r.fato_id == fato_esperado)
                      for r in resultados]
                acertos_v += sum(r.veredito == esperado for r in resultados)
                total_v += len(resultados)
                if esperado == "contradiz":
                    acertos_f += sum(r.fato_id == fato_esperado for r in resultados)
                    total_f += len(resultados)
                marca = "OK " if all(ok) else "XX "

            log(f"{marca} {fala}{' (sem gabarito)' if esperado == '?' else ''}")
            log(f"     esperado: {esperado} / {fato_esperado}")
            for (veredito, fato_id), n in obtidos.items():
                vezes = f"  ({n}x)" if args.repeticoes > 1 else ""
                log(f"     obtido:   {veredito} / {fato_id}{vezes}")
            if not estavel:
                log("     ** veredito mudou entre repetições **")
            log(f"     {resultados[0].justificativa}\n")
    except ErroProvedor as erro:
        log(f"\n[provedor] {erro}")
        log.fechar()
        return 3

    log(f"Vereditos corretos: {acertos_v}/{total_v}")
    log(f"Fatos corretos:     {acertos_f}/{total_f}")
    if args.repeticoes > 1:
        log(f"Casos com veredito instável entre repetições: {instaveis}/{len(CASOS)}")
    log(f"Latência por verificação: média {mean(latencias):.1f} s · "
        f"mín {min(latencias):.1f} s · máx {max(latencias):.1f} s")
    log.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
