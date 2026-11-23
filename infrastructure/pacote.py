"""Pacotes de troca: personagem em YAML e sessão em JSON (RF01, RF08).

O pacote YAML é o mesmo formato de data/personagens/ines.yaml. É como a
roteirista entrega um personagem ao desenvolvedor e como um personagem é
importado em outra máquina. O JSON de sessão é o registro completo que o
desenvolvedor devolve à roteirista.
"""
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from core.models import FichaPersonagem, Personagem, SessaoExportada
from infrastructure import provedor, repositorio


class PacoteInvalido(ValueError):
    """O arquivo não segue o formato esperado. A mensagem diz o que corrigir."""


def _explicar(erro: ValidationError) -> str:
    linhas = []
    for e in erro.errors():
        local = " > ".join(str(p) for p in e["loc"]) or "(raiz)"
        linhas.append(f"  - {local}: {e['msg']}")
    return "\n".join(linhas)


# ----------------------------------------------------------- personagem YAML

def ler_ficha_yaml(conteudo: str | bytes | Path) -> FichaPersonagem:
    """Lê e valida um pacote de personagem. Aceita caminho ou o texto do arquivo."""
    if isinstance(conteudo, Path):
        conteudo = conteudo.read_text(encoding="utf-8")
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode("utf-8-sig")
    try:
        dados = yaml.safe_load(conteudo)
    except yaml.YAMLError as erro:
        raise PacoteInvalido(f"O arquivo não é um YAML válido:\n  {erro}") from erro
    if not isinstance(dados, dict):
        raise PacoteInvalido("O arquivo deveria conter os campos id, nome, papel, "
                             "registro_fala, restricoes e fatos.")
    try:
        return FichaPersonagem.model_validate(dados)
    except ValidationError as erro:
        raise PacoteInvalido("Pacote de personagem inválido:\n" + _explicar(erro)) from erro


def importar_ficha(ficha: FichaPersonagem) -> Personagem:
    """Grava ficha e fatos. Fatos que já existem com o mesmo id são atualizados;
    fatos que existem no banco e não estão no pacote ficam como estão."""
    personagem = repositorio.salvar_personagem(
        id=ficha.id, nome=ficha.nome, papel=ficha.papel,
        registro_fala=ficha.registro_fala, restricoes=ficha.restricoes,
    )
    for fato in ficha.fatos:
        repositorio.salvar_fato(ficha.id, fato.id, fato.texto, origem=fato.origem,
                                escopo=fato.escopo, ativo=fato.ativo)
    return personagem


def importar_ficha_yaml(conteudo: str | bytes | Path) -> Personagem:
    return importar_ficha(ler_ficha_yaml(conteudo))


def exportar_ficha(personagem_id: str) -> FichaPersonagem:
    p = repositorio.buscar_personagem(personagem_id)
    if p is None:
        raise ValueError(f"Personagem {personagem_id!r} não existe.")
    fatos = repositorio.listar_fatos(personagem_id, apenas_ativos=False)
    return FichaPersonagem(
        id=p.id, nome=p.nome, papel=p.papel, registro_fala=p.registro_fala,
        restricoes=p.restricoes,
        fatos=[{"id": f.id, "texto": f.texto, "escopo": f.escopo,
                "origem": f.origem, "ativo": f.ativo} for f in fatos],
    )


def ficha_para_yaml(ficha: FichaPersonagem) -> str:
    dados = ficha.model_dump()
    # Omite os valores padrão para o arquivo continuar legível como o original.
    padrao = {"escopo": "personagem", "origem": "autorado", "ativo": True}
    dados["fatos"] = [
        {k: v for k, v in f.items() if not (k in padrao and v == padrao[k])}
        for f in dados["fatos"]
    ]
    return yaml.safe_dump(dados, allow_unicode=True, sort_keys=False, width=88)


# --------------------------------------------------------------- sessão JSON

def exportar_sessao(sessao_id: str) -> SessaoExportada:
    sessao = repositorio.buscar_sessao(sessao_id)
    if sessao is None:
        raise ValueError(f"Sessão {sessao_id!r} não encontrada.")
    turnos = repositorio.listar_turnos(sessao_id)
    return SessaoExportada(
        exportada_em=datetime.now(timezone.utc),
        provedor=provedor.descrever_configuracao(),
        sessao=sessao,
        personagem=repositorio.buscar_personagem(sessao.personagem_id),
        canone=repositorio.listar_fatos(sessao.personagem_id, apenas_ativos=False),
        memoria=[t.indice for t in turnos if t.decisao == "aceita"],
        turnos=turnos,
    )


def sessao_para_json(exportacao: SessaoExportada) -> str:
    return exportacao.model_dump_json(indent=2)


def salvar_sessao_json(sessao_id: str, destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(sessao_para_json(exportar_sessao(sessao_id)), encoding="utf-8")
    return destino
