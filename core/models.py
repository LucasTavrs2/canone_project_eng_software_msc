"""Contratos de dados do Cânone (Pydantic).

Todo dado que atravessa uma fronteira do sistema passa por um destes esquemas:
a resposta do verificador (saída do modelo de linguagem), o pacote YAML de
personagem (entrada do roteirista) e o JSON exportado (saída para outros
programas). O repositório também devolve estes objetos, de modo que as
interfaces nunca manipulam linhas cruas do banco (RNF03).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Veredito = Literal["consistente", "contradiz", "indeterminado"]
OrigemFato = Literal["autorado", "promovido"]
EscopoFato = Literal["personagem", "mundo"]
DecisaoTurno = Literal["pendente", "aceita", "regenerada", "descartada"]

# Identificadores curtos e estáveis: vão para o prompt e para o registro.
PADRAO_ID_PERSONAGEM = r"^[a-z0-9][a-z0-9_-]*$"
PADRAO_ID_FATO = r"^F\d{2,}$"


class FatoCanonico(BaseModel):
    id: str = Field(pattern=PADRAO_ID_FATO)        # "F01", "F02"...
    personagem_id: str
    texto: str = Field(min_length=1)               # afirmação atômica, uma só ideia
    escopo: EscopoFato = "personagem"
    origem: OrigemFato = "autorado"
    ativo: bool = True                             # desativa em vez de deletar
    turno_origem_id: str | None = None             # só em fatos promovidos (RF07)
    criado_em: datetime


class Personagem(BaseModel):
    id: str = Field(pattern=PADRAO_ID_PERSONAGEM)
    nome: str = Field(min_length=1)
    papel: str = Field(min_length=1)               # "herbolária do vilarejo inicial"
    registro_fala: str = Field(min_length=1)       # "ríspida, econômica, ..."
    restricoes: list[str] = Field(default_factory=list)
    criado_em: datetime


class ResultadoVerificacao(BaseModel):
    """Saída da segunda chamada ao modelo. Validada antes de ser usada."""

    veredito: Veredito
    fato_id: str | None = None
    justificativa: str

    @model_validator(mode="after")
    def _fato_so_em_contradicao(self):
        # O modelo às vezes cita o fato que *confirma* a fala. Isso não é
        # contradição, e um fato_id fora de "contradiz" confundiria o registro.
        if self.veredito != "contradiz":
            self.fato_id = None
        return self


class Turno(BaseModel):
    id: str
    sessao_id: str
    indice: int = Field(ge=0)
    fala_jogador: str
    fala_npc: str
    verificacao: ResultadoVerificacao
    decisao: DecisaoTurno = "pendente"
    latencia_geracao_ms: int | None = None
    latencia_verificacao_ms: int | None = None
    criado_em: datetime


class Sessao(BaseModel):
    id: str
    personagem_id: str
    titulo: str
    criada_em: datetime


# ------------------------------------------------------- pacotes de troca

class FatoFicha(BaseModel):
    """Fato como aparece no pacote YAML do personagem."""

    id: str = Field(pattern=PADRAO_ID_FATO)
    texto: str = Field(min_length=1)
    escopo: EscopoFato = "personagem"
    origem: OrigemFato = "autorado"
    ativo: bool = True


class FichaPersonagem(BaseModel):
    """Pacote de personagem: ficha + cânone, no formato de data/personagens/*.yaml.

    É o que a roteirista entrega ao desenvolvedor (Cenário Positivo 2).
    """

    id: str = Field(pattern=PADRAO_ID_PERSONAGEM)
    nome: str = Field(min_length=1)
    papel: str = Field(min_length=1)
    registro_fala: str = Field(min_length=1)
    restricoes: list[str] = Field(default_factory=list)
    fatos: list[FatoFicha] = Field(default_factory=list)

    @field_validator("fatos")
    @classmethod
    def _ids_unicos(cls, fatos: list[FatoFicha]) -> list[FatoFicha]:
        vistos: set[str] = set()
        for fato in fatos:
            if fato.id in vistos:
                raise ValueError(f"o identificador {fato.id} aparece mais de uma vez")
            vistos.add(fato.id)
        return fatos


class SessaoExportada(BaseModel):
    """RF08: registro completo de uma sessão, suficiente para reconstruí-la."""

    formato: Literal["canone.sessao/1"] = "canone.sessao/1"
    exportada_em: datetime
    provedor: dict              # modelos e temperaturas em uso na exportação
    sessao: Sessao
    personagem: Personagem
    canone: list[FatoCanonico]  # inclui fatos desativados: turnos antigos os citam
    memoria: list[int]          # índices dos turnos aceitos (o que o NPC "lembra")
    turnos: list[Turno]         # todos, inclusive regenerados e descartados
