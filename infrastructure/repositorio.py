"""Persistência de personagens, fatos, sessões e turnos (RF01, RF02, RF04).

Toda função devolve modelos Pydantic de core/models.py. Linhas cruas do SQLite
não saem deste módulo.
"""
import json
import uuid
from datetime import datetime, timezone

from core.models import (
    DecisaoTurno,
    FatoCanonico,
    Personagem,
    ResultadoVerificacao,
    Sessao,
    Turno,
)
from infrastructure.db import conexao


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _novo_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- personagem

def _personagem(linha) -> Personagem:
    dados = dict(linha)
    dados["restricoes"] = json.loads(dados["restricoes"])
    return Personagem.model_validate(dados)


def salvar_personagem(id: str, nome: str, papel: str, registro_fala: str,
                      restricoes: list[str] | None = None) -> Personagem:
    """Cria ou atualiza a ficha. A data de criação original é preservada."""
    restricoes = [r.strip() for r in (restricoes or []) if r.strip()]
    # Valida antes de gravar: id fora do padrão ou campo vazio não entra no banco.
    Personagem(id=id, nome=nome.strip(), papel=papel.strip(),
               registro_fala=registro_fala.strip(), restricoes=restricoes,
               criado_em=datetime.now(timezone.utc))
    with conexao() as c:
        c.execute(
            """
            INSERT INTO personagem (id, nome, papel, registro_fala, restricoes, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nome = excluded.nome,
                papel = excluded.papel,
                registro_fala = excluded.registro_fala,
                restricoes = excluded.restricoes
            """,
            (id, nome.strip(), papel.strip(), registro_fala.strip(),
             json.dumps(restricoes, ensure_ascii=False), _agora()),
        )
    return buscar_personagem(id)


def buscar_personagem(personagem_id: str) -> Personagem | None:
    with conexao() as c:
        linha = c.execute(
            "SELECT * FROM personagem WHERE id = ?", (personagem_id,)
        ).fetchone()
    return _personagem(linha) if linha else None


def listar_personagens() -> list[Personagem]:
    with conexao() as c:
        linhas = c.execute("SELECT * FROM personagem ORDER BY nome").fetchall()
    return [_personagem(l) for l in linhas]


# ---------------------------------------------------------------------- fato

def _fato(linha) -> FatoCanonico:
    dados = dict(linha)
    dados["ativo"] = bool(dados["ativo"])
    return FatoCanonico.model_validate(dados)


def salvar_fato(personagem_id: str, fato_id: str, texto: str,
                origem: str = "autorado", escopo: str = "personagem",
                ativo: bool = True, turno_origem_id: str | None = None) -> FatoCanonico:
    texto = " ".join(texto.split())
    FatoCanonico(id=fato_id, personagem_id=personagem_id, texto=texto,
                 escopo=escopo, origem=origem, ativo=ativo,
                 turno_origem_id=turno_origem_id,
                 criado_em=datetime.now(timezone.utc))
    with conexao() as c:
        c.execute(
            """
            INSERT INTO fato_canonico
                (id, personagem_id, texto, escopo, origem, ativo, turno_origem_id, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(personagem_id, id) DO UPDATE SET
                texto = excluded.texto,
                escopo = excluded.escopo,
                origem = excluded.origem,
                ativo = excluded.ativo
            """,
            (fato_id, personagem_id, texto, escopo, origem, int(ativo),
             turno_origem_id, _agora()),
        )
    return buscar_fato(personagem_id, fato_id)


def buscar_fato(personagem_id: str, fato_id: str) -> FatoCanonico | None:
    with conexao() as c:
        linha = c.execute(
            "SELECT * FROM fato_canonico WHERE personagem_id = ? AND id = ?",
            (personagem_id, fato_id),
        ).fetchone()
    return _fato(linha) if linha else None


def listar_fatos(personagem_id: str, apenas_ativos: bool = True) -> list[FatoCanonico]:
    sql = "SELECT * FROM fato_canonico WHERE personagem_id = ?"
    if apenas_ativos:
        sql += " AND ativo = 1"
    with conexao() as c:
        linhas = c.execute(sql, (personagem_id,)).fetchall()
    # Ordena pelo número (F9 antes de F10), não pela string.
    return sorted((_fato(l) for l in linhas), key=lambda f: int(f.id[1:]))


def editar_texto_fato(personagem_id: str, fato_id: str, texto: str) -> FatoCanonico:
    atual = buscar_fato(personagem_id, fato_id)
    if atual is None:
        raise ValueError(f"Fato {fato_id} não existe para {personagem_id}.")
    return salvar_fato(personagem_id, fato_id, texto, origem=atual.origem,
                       escopo=atual.escopo, ativo=atual.ativo)


def definir_ativo(personagem_id: str, fato_id: str, ativo: bool) -> None:
    """Desativar em vez de deletar: turnos antigos referenciam o fato_id."""
    with conexao() as c:
        cursor = c.execute(
            "UPDATE fato_canonico SET ativo = ? WHERE personagem_id = ? AND id = ?",
            (int(ativo), personagem_id, fato_id),
        )
    if cursor.rowcount == 0:
        raise ValueError(f"Fato {fato_id} não existe para {personagem_id}.")


def desativar_fato(personagem_id: str, fato_id: str) -> None:
    definir_ativo(personagem_id, fato_id, False)


def proximo_id_fato(personagem_id: str) -> str:
    """Próximo identificador na sequência F01, F02, ... (conta os desativados)."""
    fatos = listar_fatos(personagem_id, apenas_ativos=False)
    numeros = [int(f.id[1:]) for f in fatos]
    return f"F{max(numeros, default=0) + 1:02d}"


def promover_a_canone(personagem_id: str, texto: str,
                      turno_origem_id: str | None = None) -> FatoCanonico:
    """RF07: transforma uma afirmação inventada pelo NPC em fato canônico."""
    return salvar_fato(personagem_id, proximo_id_fato(personagem_id), texto,
                       origem="promovido", turno_origem_id=turno_origem_id)


# -------------------------------------------------------------------- sessão

def criar_sessao(personagem_id: str, titulo: str) -> Sessao:
    if buscar_personagem(personagem_id) is None:
        raise ValueError(f"Personagem {personagem_id!r} não existe.")
    sessao_id = _novo_id()
    with conexao() as c:
        c.execute(
            "INSERT INTO sessao (id, personagem_id, titulo, criada_em) VALUES (?, ?, ?, ?)",
            (sessao_id, personagem_id, titulo.strip() or "sem título", _agora()),
        )
    return buscar_sessao(sessao_id)


def buscar_sessao(sessao_id: str) -> Sessao | None:
    with conexao() as c:
        linha = c.execute("SELECT * FROM sessao WHERE id = ?", (sessao_id,)).fetchone()
    return Sessao.model_validate(dict(linha)) if linha else None


def listar_sessoes(personagem_id: str) -> list[Sessao]:
    with conexao() as c:
        linhas = c.execute(
            "SELECT * FROM sessao WHERE personagem_id = ? ORDER BY criada_em DESC",
            (personagem_id,),
        ).fetchall()
    return [Sessao.model_validate(dict(l)) for l in linhas]


# --------------------------------------------------------------------- turno

def _turno(linha) -> Turno:
    d = dict(linha)
    d["verificacao"] = ResultadoVerificacao(
        veredito=d.pop("veredito"),
        fato_id=d.pop("fato_id"),
        justificativa=d.pop("justificativa"),
    )
    return Turno.model_validate(d)


def salvar_turno(sessao_id: str, fala_jogador: str, fala_npc: str,
                 verificacao: ResultadoVerificacao,
                 latencia_geracao_ms: int | None = None,
                 latencia_verificacao_ms: int | None = None) -> Turno:
    """Grava o turno como 'pendente'. O índice é calculado na mesma transação."""
    turno_id = _novo_id()
    with conexao() as c:
        indice = c.execute(
            "SELECT COALESCE(MAX(indice), -1) + 1 FROM turno WHERE sessao_id = ?",
            (sessao_id,),
        ).fetchone()[0]
        c.execute(
            """
            INSERT INTO turno
                (id, sessao_id, indice, fala_jogador, fala_npc, veredito, fato_id,
                 justificativa, decisao, latencia_geracao_ms, latencia_verificacao_ms,
                 criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?, ?)
            """,
            (turno_id, sessao_id, indice, fala_jogador, fala_npc,
             verificacao.veredito, verificacao.fato_id, verificacao.justificativa,
             latencia_geracao_ms, latencia_verificacao_ms, _agora()),
        )
    return buscar_turno(turno_id)


def buscar_turno(turno_id: str) -> Turno | None:
    with conexao() as c:
        linha = c.execute("SELECT * FROM turno WHERE id = ?", (turno_id,)).fetchone()
    return _turno(linha) if linha else None


def atualizar_decisao(turno_id: str, decisao: DecisaoTurno) -> Turno:
    if decisao not in ("pendente", "aceita", "regenerada", "descartada"):
        raise ValueError(f"Decisão inválida: {decisao!r}")
    with conexao() as c:
        cursor = c.execute("UPDATE turno SET decisao = ? WHERE id = ?", (decisao, turno_id))
    if cursor.rowcount == 0:
        raise ValueError(f"Turno {turno_id!r} não existe.")
    return buscar_turno(turno_id)


def listar_turnos(sessao_id: str, apenas_aceitos: bool = False) -> list[Turno]:
    sql = "SELECT * FROM turno WHERE sessao_id = ?"
    if apenas_aceitos:
        sql += " AND decisao = 'aceita'"
    sql += " ORDER BY indice"
    with conexao() as c:
        linhas = c.execute(sql, (sessao_id,)).fetchall()
    return [_turno(l) for l in linhas]


def contar_turnos(sessao_id: str) -> int:
    with conexao() as c:
        return c.execute(
            "SELECT COUNT(*) FROM turno WHERE sessao_id = ?", (sessao_id,)
        ).fetchone()[0]
