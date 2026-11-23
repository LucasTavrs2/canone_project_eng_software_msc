"""Linha de comando do Cânone (RF09), para o desenvolvedor de gameplay.

Rode da pasta do projeto:

    python -m cli --help
    python -m cli <comando> --help

Com --json, os comandos que produzem dados imprimem só o JSON, para serem
lidos por outro programa (por exemplo, um jogo que chama o Cânone por
subprocesso).

Códigos de saída: 0 sucesso; 1 erro de uso ou de dados; 3 erro do provedor.
"""
import argparse
import json
import sys
from pathlib import Path

from cli import api

MARCA = {"consistente": " ok ", "contradiz": "CONTRADIZ", "indeterminado": " ?? "}


# ------------------------------------------------------------------ saída

def _json(obj) -> None:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    elif isinstance(obj, list):
        obj = [o.model_dump(mode="json") if hasattr(o, "model_dump") else o for o in obj]
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _segundos(ms: int | None) -> str:
    return "-" if ms is None else f"{ms / 1000:.1f} s"


def _mostrar_turno(turno, nome: str) -> None:
    v = turno.verificacao
    print(f"{nome} > {turno.fala_npc}")
    print(f"        [{MARCA[v.veredito]}] {v.fato_id or '-'} · {v.justificativa}")
    print(f"        turno {turno.id} · {turno.decisao} · "
          f"geração {_segundos(turno.latencia_geracao_ms)} + "
          f"verificação {_segundos(turno.latencia_verificacao_ms)}")


def _nome_da_sessao(sessao_id: str) -> str:
    sessao = api.buscar_sessao(sessao_id)
    personagem = api.buscar_personagem(sessao.personagem_id) if sessao else None
    return personagem.nome if personagem else "NPC"


# --------------------------------------------------------------- comandos

def cmd_provedor(args) -> int:
    config = api.descrever_configuracao()
    if args.json:
        resultado = {"configuracao": config, "conexao": {}}
    else:
        for papel, c in config.items():
            print(f"{papel:12} {c['modelo']}  em {c['url']}  "
                  f"(temperatura {c['temperatura']}, reasoning_effort={c['raciocinio']}, "
                  f"chave {c['chave']})")
    falhou = False
    for papel in ("gerador", "verificador"):
        modelo = config[papel]["modelo"]
        try:
            disponiveis = api.listar_modelos(papel)
            ok = modelo in disponiveis
            detalhe = "modelo disponível" if ok else (
                f"servidor no ar, mas {modelo!r} não está na lista: {', '.join(disponiveis) or '(vazia)'}")
        except api.ErroProvedor as erro:
            ok, detalhe = False, str(erro)
        falhou |= not ok
        if args.json:
            resultado["conexao"][papel] = {"ok": ok, "detalhe": detalhe}
        else:
            print(f"{papel:12} {'OK ' if ok else 'ERRO'} {detalhe}")
    if args.json:
        _json(resultado)
    return 3 if falhou else 0


def cmd_importar(args) -> int:
    personagem = api.importar_ficha_yaml(Path(args.arquivo))
    fatos = api.listar_fatos(personagem.id)
    if args.json:
        _json({"personagem": personagem.model_dump(mode="json"), "fatos_ativos": len(fatos)})
    else:
        print(f"{personagem.nome} ({personagem.id}) importada com {len(fatos)} fatos ativos.")
    return 0


def cmd_exportar_personagem(args) -> int:
    texto = api.ficha_para_yaml(api.exportar_ficha(args.personagem))
    if args.saida:
        Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.saida).write_text(texto, encoding="utf-8")
        print(f"Pacote do personagem salvo em {args.saida}")
    else:
        print(texto, end="")
    return 0


def cmd_personagens(args) -> int:
    personagens = api.listar_personagens()
    if args.json:
        _json(personagens)
        return 0
    if not personagens:
        print("Nenhum personagem. Importe com: python -m cli importar <arquivo.yaml>")
    for p in personagens:
        print(f"{p.id:12} {p.nome} · {p.papel} · {len(api.listar_fatos(p.id))} fatos ativos")
    return 0


def cmd_fatos(args) -> int:
    fatos = api.listar_fatos(args.personagem, apenas_ativos=not args.todos)
    if args.json:
        _json(fatos)
        return 0
    for f in fatos:
        extras = []
        if f.origem == "promovido":
            extras.append("promovido")
        if not f.ativo:
            extras.append("inativo")
        sufixo = f"  ({', '.join(extras)})" if extras else ""
        print(f"[{f.id}] {f.texto}{sufixo}")
    return 0


def cmd_nova_sessao(args) -> int:
    sessao = api.nova_sessao(args.personagem, args.titulo)
    if args.json:
        _json(sessao)
    else:
        print(sessao.id)
    return 0


def cmd_sessoes(args) -> int:
    sessoes = api.listar_sessoes(args.personagem)
    if args.json:
        _json(sessoes)
        return 0
    for s in sessoes:
        n = len(api.listar_turnos(s.id))
        print(f"{s.id}  {s.criada_em:%Y-%m-%d %H:%M}  {n:3} turnos  {s.titulo}")
    return 0


def cmd_turnos(args) -> int:
    turnos = api.listar_turnos(args.sessao)
    if args.json:
        _json(turnos)
        return 0
    nome = _nome_da_sessao(args.sessao)
    for t in turnos:
        print(f"#{t.indice} você > {t.fala_jogador}")
        _mostrar_turno(t, nome)
        print()
    return 0


def cmd_responder(args) -> int:
    turno = api.responder(args.sessao, args.fala)
    if args.aceitar:
        turno = api.decidir(turno.id, "aceita")
    if args.json:
        _json(turno)
    else:
        _mostrar_turno(turno, _nome_da_sessao(args.sessao))
    return 0


def cmd_regenerar(args) -> int:
    turno = api.regenerar(args.turno)
    if args.json:
        _json(turno)
    else:
        _mostrar_turno(turno, _nome_da_sessao(turno.sessao_id))
    return 0


def cmd_decidir(args) -> int:
    turno = api.decidir(args.turno, args.decisao)
    if args.json:
        _json(turno)
    else:
        print(f"Turno {turno.id}: {turno.decisao}.")
    return 0


def cmd_promover(args) -> int:
    fato = api.promover(args.turno, args.afirmacao)
    if args.json:
        _json(fato)
    else:
        print(f"Promovido como [{fato.id}] {fato.texto}")
    return 0


def cmd_verificar(args) -> int:
    resultado = api.verificar_fala_contra_canone(args.personagem, args.fala)
    if args.json:
        _json(resultado)
    else:
        print(f"[{MARCA[resultado.veredito]}] {resultado.fato_id or '-'} · "
              f"{resultado.justificativa}")
    return 0


def cmd_exportar(args) -> int:
    if args.saida:
        destino = api.salvar_sessao_json(args.sessao, Path(args.saida))
        print(f"Sessão exportada para {destino}")
    else:
        print(api.exportar_sessao(args.sessao).model_dump_json(indent=2))
    return 0


# ------------------------------------------------------------------ parser

def montar_parser() -> argparse.ArgumentParser:
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--json", action="store_true",
                       help="imprime só JSON, para leitura por outro programa")

    p = argparse.ArgumentParser(
        prog="python -m cli",
        description="Cânone: diálogo de NPC com verificação de consistência canônica.",
    )
    sub = p.add_subparsers(dest="comando", required=True, metavar="<comando>")

    def comando(nome, funcao, ajuda):
        s = sub.add_parser(nome, parents=[comum], help=ajuda, description=ajuda)
        s.set_defaults(funcao=funcao)
        return s

    comando("provedor", cmd_provedor, "mostra a configuração do modelo e testa a conexão")

    s = comando("importar", cmd_importar, "importa um pacote de personagem (YAML)")
    s.add_argument("arquivo")

    s = comando("exportar-personagem", cmd_exportar_personagem,
                "gera o pacote YAML de um personagem (ficha + cânone)")
    s.add_argument("personagem")
    s.add_argument("-o", "--saida", help="arquivo de destino (.yaml)")

    comando("personagens", cmd_personagens, "lista os personagens cadastrados")

    s = comando("fatos", cmd_fatos, "lista o cânone de um personagem")
    s.add_argument("personagem")
    s.add_argument("--todos", action="store_true", help="inclui fatos desativados")

    s = comando("nova-sessao", cmd_nova_sessao, "cria uma sessão e imprime o id")
    s.add_argument("personagem")
    s.add_argument("titulo")

    s = comando("sessoes", cmd_sessoes, "lista as sessões de um personagem")
    s.add_argument("personagem")

    s = comando("turnos", cmd_turnos, "mostra todos os turnos de uma sessão")
    s.add_argument("sessao")

    s = comando("responder", cmd_responder,
                "gera a fala do NPC e o veredito; o turno fica pendente")
    s.add_argument("sessao")
    s.add_argument("fala", help="fala do jogador (entre aspas)")
    s.add_argument("--aceitar", action="store_true",
                   help="aceita o turno logo em seguida (entra na memória)")

    s = comando("regenerar", cmd_regenerar, "descarta a fala pendente e gera outra")
    s.add_argument("turno")

    s = comando("decidir", cmd_decidir, "aceita ou descarta um turno")
    s.add_argument("turno")
    s.add_argument("decisao", choices=["aceita", "descartada"])

    s = comando("promover", cmd_promover,
                "promove uma afirmação de um turno a fato canônico")
    s.add_argument("turno")
    s.add_argument("afirmacao", help='fato atômico em 3ª pessoa, ex.: "Inês foi casada."')

    s = comando("verificar", cmd_verificar,
                "verifica uma fala contra o cânone, sem gerar nem gravar nada")
    s.add_argument("personagem")
    s.add_argument("fala")

    s = comando("exportar", cmd_exportar, "exporta o registro completo de uma sessão (JSON)")
    s.add_argument("sessao")
    s.add_argument("-o", "--saida", help="arquivo de destino (.json)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = montar_parser().parse_args(argv)
    try:
        return args.funcao(args)
    except api.ErroProvedor as erro:
        print(f"[provedor] {erro}", file=sys.stderr)
        return 3
    except (ValueError, FileNotFoundError) as erro:
        print(f"[erro] {erro}", file=sys.stderr)
        return 1
