"""Interface web do Cânone para a roteirista (U1).

Da pasta do projeto:
    python -m streamlit run ui\\app.py

Abas:
    Conversa              conversar como jogador e revisar cada fala (RF03, RF05, RF06, RF07)
    Ficha                 quem o personagem é e como fala (RF01)
    Cânone                fatos que nenhuma fala pode contrariar (RF02)
    Registro e exportação tudo o que foi gerado, inclusive o descartado (RF04, RF08)

Esta camada só desenha a tela e repassa ações. O ciclo de um turno está em
core/dialogo.py, o mesmo usado pela linha de comando.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from core import dialogo  # noqa: E402
from core.models import Turno  # noqa: E402
from infrastructure import pacote, provedor, repositorio  # noqa: E402

FICHA_EXEMPLO = RAIZ / "data" / "personagens" / "ines.yaml"
PASTA_EVIDENCIAS = RAIZ / "docs" / "evidencias"

st.set_page_config(page_title="Cânone", page_icon="📜", layout="wide")


# ------------------------------------------------------------------ apoio

def avisar(mensagem: str) -> None:
    """Mensagem curta que sobrevive ao recarregamento da página."""
    st.session_state.setdefault("avisos", []).append(mensagem)


def mostrar_avisos() -> None:
    for mensagem in st.session_state.pop("avisos", []):
        st.toast(mensagem)


def segundos(ms: int | None) -> str:
    return "-" if ms is None else f"{ms / 1000:.1f} s"


def erro_provedor(erro: Exception) -> None:
    st.error(f"**O modelo não respondeu.**\n\n{erro}")
    st.caption("Confira o LM Studio (aba Developer, Status 'Running') e use "
               "'Testar conexão' na barra lateral.")


# -------------------------------------------------------------- callbacks
# Callbacks rodam antes de a página ser redesenhada; por isso podem trocar a
# seleção de personagem e de sessão.

def cb_importar_exemplo() -> None:
    personagem = pacote.importar_ficha_yaml(FICHA_EXEMPLO)
    st.session_state["sel_personagem"] = personagem.id
    avisar(f"{personagem.nome} importada.")


def cb_importar_upload() -> None:
    arquivo = st.session_state.get("upload_yaml")
    if arquivo is None:
        avisar("Escolha um arquivo .yaml antes de importar.")
        return
    try:
        personagem = pacote.importar_ficha_yaml(arquivo.getvalue())
    except pacote.PacoteInvalido as erro:
        st.session_state["erro_importacao"] = str(erro)
        return
    st.session_state.pop("erro_importacao", None)
    st.session_state["sel_personagem"] = personagem.id
    avisar(f"{personagem.nome} importado(a) do pacote.")


def cb_criar_personagem() -> None:
    s = st.session_state
    restricoes = s.get("novo_restricoes", "").splitlines()
    try:
        personagem = repositorio.salvar_personagem(
            id=s.get("novo_id", "").strip(), nome=s.get("novo_nome", ""),
            papel=s.get("novo_papel", ""), registro_fala=s.get("novo_registro", ""),
            restricoes=restricoes,
        )
    except ValueError:
        s["erro_criacao"] = ("Preencha todos os campos. O identificador usa só letras "
                             "minúsculas, números, '-' ou '_' (ex.: ines, ferreiro_bento).")
        return
    s.pop("erro_criacao", None)
    s["sel_personagem"] = personagem.id
    avisar(f"{personagem.nome} criado(a). Agora cadastre o cânone.")


def cb_nova_sessao(personagem_id: str) -> None:
    titulo = st.session_state.get("titulo_nova_sessao", "").strip() or "sem título"
    sessao = dialogo.nova_sessao(personagem_id, titulo)
    st.session_state[f"sel_sessao_{personagem_id}"] = sessao.id
    st.session_state["titulo_nova_sessao"] = ""
    avisar(f"Sessão '{sessao.titulo}' criada.")


# ------------------------------------------------------------ barra lateral

def barra_lateral():
    """Desenha a barra lateral e devolve (personagem, sessão) selecionados."""
    with st.sidebar:
        st.title("📜 Cânone")
        st.caption("Diálogo de NPC com verificação de consistência canônica")

        personagens = repositorio.listar_personagens()
        personagem = None
        if personagens:
            ids = [p.id for p in personagens]
            if st.session_state.get("sel_personagem") not in ids:
                st.session_state["sel_personagem"] = ids[0]
            nomes = {p.id: f"{p.nome} · {p.papel}" for p in personagens}
            escolhido = st.selectbox("Personagem", ids, format_func=nomes.get,
                                     key="sel_personagem")
            personagem = next(p for p in personagens if p.id == escolhido)
        else:
            st.info("Nenhum personagem cadastrado.")
            st.button("Importar Inês (exemplo)", on_click=cb_importar_exemplo,
                      type="primary")

        with st.expander("Novo personagem"):
            st.text_input("Identificador", key="novo_id", placeholder="ex.: ferreiro_bento")
            st.text_input("Nome", key="novo_nome")
            st.text_input("Papel narrativo", key="novo_papel",
                          placeholder="ex.: ferreiro do vilarejo")
            st.text_area("Como fala", key="novo_registro",
                         placeholder="ex.: falante, exagerado, adora contar vantagem")
            st.text_area("Restrições (uma por linha)", key="novo_restricoes")
            st.button("Criar personagem", on_click=cb_criar_personagem)
            if "erro_criacao" in st.session_state:
                st.error(st.session_state["erro_criacao"])

        with st.expander("Importar pacote de personagem (YAML)"):
            st.file_uploader("Arquivo .yaml", type=["yaml", "yml"], key="upload_yaml")
            st.button("Importar", on_click=cb_importar_upload)
            if "erro_importacao" in st.session_state:
                st.error(st.session_state["erro_importacao"])

        sessao = None
        if personagem is not None:
            st.divider()
            sessoes = repositorio.listar_sessoes(personagem.id)
            chave = f"sel_sessao_{personagem.id}"
            if sessoes:
                ids = [s.id for s in sessoes]
                if st.session_state.get(chave) not in ids:
                    st.session_state[chave] = ids[0]
                rotulos = {s.id: f"{s.titulo} · {repositorio.contar_turnos(s.id)} turnos · "
                                 f"{s.criada_em:%d/%m %H:%M}" for s in sessoes}
                escolhida = st.selectbox("Sessão", ids, format_func=rotulos.get, key=chave)
                sessao = next(s for s in sessoes if s.id == escolhida)
            else:
                st.caption("Nenhuma sessão ainda.")
            st.text_input("Título da nova sessão", key="titulo_nova_sessao",
                          placeholder="ex.: conversas sobre a guilda")
            st.button("Nova sessão", on_click=cb_nova_sessao, args=(personagem.id,))

        st.divider()
        with st.expander("Provedor de modelo"):
            for papel, cfg in provedor.descrever_configuracao().items():
                st.markdown(f"**{papel.capitalize()}:** `{cfg['modelo']}`  \n"
                            f"{cfg['url']} · temperatura {cfg['temperatura']}")
            if st.button("Testar conexão"):
                for papel in ("gerador", "verificador"):
                    modelo = provedor.configuracao(papel).modelo
                    try:
                        disponiveis = provedor.listar_modelos(papel)
                    except provedor.ErroProvedor as erro:
                        st.error(str(erro))
                        break
                    if modelo in disponiveis:
                        st.success(f"{papel}: modelo disponível.")
                    else:
                        st.warning(f"{papel}: servidor no ar, mas `{modelo}` não está "
                                   f"carregado. Disponíveis: {', '.join(disponiveis) or 'nenhum'}.")
            st.caption("Para trocar, defina CANONE_LLM_URL e CANONE_LLM_MODEL "
                       "antes de abrir a interface.")

    return personagem, sessao


# ------------------------------------------------------------------ conversa

def selo(turno: Turno, fatos_por_id: dict) -> None:
    v = turno.verificacao
    if v.veredito == "contradiz":
        fato = fatos_por_id.get(v.fato_id)
        texto = f" — {fato.texto}" if fato else ""
        st.markdown(f":red[**Contradiz {v.fato_id}**]{texto}")
    elif v.veredito == "indeterminado":
        st.markdown(":orange[**Indeterminado**] — o verificador não conseguiu decidir")
    else:
        st.markdown(":green[**Consistente**] com o cânone")
    st.caption(f"{v.justificativa}  \n"
               f"geração {segundos(turno.latencia_geracao_ms)} · "
               f"verificação {segundos(turno.latencia_verificacao_ms)}")


def acoes_pendente(turno: Turno, nome: str) -> None:
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Aceitar", key=f"aceitar_{turno.id}", type="primary"):
        dialogo.decidir(turno.id, "aceita")
        st.rerun()
    if c2.button("Regenerar", key=f"regenerar_{turno.id}"):
        with st.spinner(f"{nome} está respondendo de novo…"):
            try:
                dialogo.regenerar(turno.id)
            except provedor.ErroProvedor as erro:
                erro_provedor(erro)
                return
        st.rerun()
    if c3.button("Descartar", key=f"descartar_{turno.id}"):
        dialogo.decidir(turno.id, "descartada")
        st.rerun()
    with c4.popover("Promover a cânone"):
        formulario_promocao(turno, rotulo_botao="Promover e aceitar")


def cb_promover(turno_id: str) -> None:
    chave = f"promover_txt_{turno_id}"
    texto = st.session_state.get(chave, "").strip()
    if not texto:
        avisar("Escreva a afirmação antes de promover.")
        return
    fato = dialogo.promover(turno_id, texto)
    st.session_state[chave] = ""   # evita promover o mesmo texto duas vezes
    avisar(f"Promovido como [{fato.id}] {fato.texto}")


def formulario_promocao(turno: Turno, rotulo_botao: str = "Promover") -> None:
    st.caption("Escreva a afirmação como fato atômico, em terceira pessoa. "
               "Uma ideia só por fato.")
    st.text_input("Novo fato canônico", key=f"promover_txt_{turno.id}",
                  placeholder="ex.: Inês foi casada.")
    st.button(rotulo_botao, key=f"promover_{turno.id}", type="primary",
              on_click=cb_promover, args=(turno.id,))


def aba_conversa(personagem, sessao) -> None:
    if sessao is None:
        st.info("Crie uma sessão na barra lateral para começar a conversar.")
        return

    fatos_por_id = {f.id: f for f in repositorio.listar_fatos(personagem.id, apenas_ativos=False)}
    turnos = repositorio.listar_turnos(sessao.id)
    mostrar_tudo = st.toggle("Mostrar também falas regeneradas e descartadas",
                             key=f"mostrar_tudo_{sessao.id}")
    st.caption("Só falas **aceitas** entram na memória do personagem. "
               "Regeneradas e descartadas ficam apenas no registro.")

    anterior = None
    for t in turnos:
        if t.decisao in ("regenerada", "descartada") and not mostrar_tudo:
            continue
        repetida = (anterior is not None and anterior.decisao == "regenerada"
                    and anterior.fala_jogador == t.fala_jogador)
        if not repetida:
            with st.chat_message("user"):
                st.markdown(t.fala_jogador)
        with st.chat_message("assistant", avatar="🌿"):
            if t.decisao in ("regenerada", "descartada"):
                st.markdown(f":gray[~~{t.fala_npc}~~]")
                st.caption(f"{t.decisao} · {t.verificacao.veredito}"
                           f"{' ' + t.verificacao.fato_id if t.verificacao.fato_id else ''}")
            else:
                st.markdown(t.fala_npc)
                selo(t, fatos_por_id)
                if t.decisao == "pendente":
                    acoes_pendente(t, personagem.nome)
                else:
                    with st.popover(f"Promover afirmação da fala #{t.indice}"):
                        formulario_promocao(t)
        anterior = t

    pendente = dialogo.turno_pendente(sessao.id)
    pergunta = st.chat_input(
        "Decida sobre a última fala antes de continuar" if pendente
        else f"Fale com {personagem.nome} como se fosse o jogador…",
        disabled=pendente is not None,
        key=f"chat_{sessao.id}",
    )
    if pergunta:
        with st.chat_message("user"):
            st.markdown(pergunta)
        with st.chat_message("assistant", avatar="🌿"):
            with st.spinner(f"{personagem.nome} está respondendo… (geração + verificação)"):
                try:
                    dialogo.responder(sessao.id, pergunta)
                except provedor.ErroProvedor as erro:
                    erro_provedor(erro)
                    return
        st.rerun()


# -------------------------------------------------------------------- ficha

def aba_ficha(personagem) -> None:
    st.caption("A ficha vai para o gerador de falas. O verificador não a recebe: "
               "ele julga só fatos, nunca tom ou personalidade.")
    with st.form(f"ficha_{personagem.id}"):
        nome = st.text_input("Nome", personagem.nome)
        papel = st.text_input("Papel narrativo", personagem.papel)
        registro = st.text_area("Como fala (registro de fala)", personagem.registro_fala)
        restricoes = st.text_area("Restrições de comportamento (uma por linha)",
                                  "\n".join(personagem.restricoes), height=120)
        if st.form_submit_button("Salvar ficha", type="primary"):
            try:
                repositorio.salvar_personagem(personagem.id, nome, papel, registro,
                                              restricoes.splitlines())
            except ValueError:
                st.error("Nome, papel e registro de fala não podem ficar vazios.")
            else:
                avisar("Ficha salva.")
                st.rerun()

    st.divider()
    st.markdown("**Pacote do personagem**")
    st.caption("Ficha e cânone num arquivo YAML, para entregar a outra pessoa da equipe "
               "ou importar em outra máquina.")
    st.download_button(
        "Baixar pacote (YAML)",
        data=pacote.ficha_para_yaml(pacote.exportar_ficha(personagem.id)),
        file_name=f"{personagem.id}.yaml",
        mime="text/yaml",
        key=f"baixar_pacote_{personagem.id}",
    )


# ------------------------------------------------------------------- cânone

def aba_canone(personagem) -> None:
    st.caption("Cada fala gerada é comparada com os fatos **ativos** abaixo. "
               "Escreva um fato por afirmação: fatos compostos tendem a produzir "
               "vereditos indeterminados. O programa não verifica se dois fatos se "
               "contradizem entre si.")

    with st.form(f"novo_fato_{personagem.id}", clear_on_submit=True):
        texto = st.text_area("Novo fato canônico",
                             placeholder=f"ex.: {personagem.nome} tem medo de cavalos.")
        if st.form_submit_button("Adicionar ao cânone", type="primary"):
            if texto.strip():
                fato_id = repositorio.proximo_id_fato(personagem.id)
                repositorio.salvar_fato(personagem.id, fato_id, texto)
                avisar(f"[{fato_id}] adicionado ao cânone.")
                st.rerun()
            else:
                st.warning("Escreva o fato antes de adicionar.")

    mostrar_inativos = st.toggle("Mostrar fatos desativados", key=f"inativos_{personagem.id}")
    fatos = repositorio.listar_fatos(personagem.id, apenas_ativos=not mostrar_inativos)
    if not fatos:
        st.info("Nenhum fato canônico. Sem cânone, toda fala será 'consistente'.")

    for f in fatos:
        with st.container(border=True):
            c_texto, c_editar, c_ativo = st.columns([6, 1, 1])
            rotulos = []
            if f.origem == "promovido":
                rotulos.append(":blue[promovido de uma fala]")
            if not f.ativo:
                rotulos.append(":gray[desativado]")
            extra = f"  \n{' · '.join(rotulos)}" if rotulos else ""
            corpo = f"~~{f.texto}~~" if not f.ativo else f.texto
            c_texto.markdown(f"**{f.id}** {corpo}{extra}")
            with c_editar.popover(f"Editar {f.id}"):
                novo = st.text_area("Texto do fato", f.texto,
                                    key=f"editar_txt_{personagem.id}_{f.id}")
                if st.button("Salvar", key=f"editar_{personagem.id}_{f.id}", type="primary"):
                    if novo.strip():
                        repositorio.editar_texto_fato(personagem.id, f.id, novo)
                        avisar(f"[{f.id}] atualizado.")
                        st.rerun()
            rotulo = "Desativar" if f.ativo else "Reativar"
            if c_ativo.button(rotulo, key=f"ativo_{personagem.id}_{f.id}"):
                repositorio.definir_ativo(personagem.id, f.id, not f.ativo)
                avisar(f"[{f.id}] {'desativado' if f.ativo else 'reativado'}.")
                st.rerun()


# ------------------------------------------------------- registro e exportação

def aba_registro(personagem, sessao) -> None:
    if sessao is None:
        st.info("Nenhuma sessão selecionada.")
        return

    turnos = repositorio.listar_turnos(sessao.id)
    sinalizados = [t for t in turnos if t.verificacao.veredito != "consistente"]
    aceitos = [t for t in turnos if t.decisao == "aceita"]
    totais = [(t.latencia_geracao_ms or 0) + (t.latencia_verificacao_ms or 0)
              for t in turnos if t.latencia_geracao_ms is not None]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Falas geradas", len(turnos))
    m2.metric("Na memória (aceitas)", len(aceitos))
    m3.metric("Sinalizadas", len(sinalizados))
    m4.metric("Tempo médio por fala", f"{sum(totais) / len(totais) / 1000:.1f} s" if totais else "-")

    if turnos:
        st.dataframe(
            [{
                "#": t.indice,
                "jogador": t.fala_jogador,
                personagem.nome: t.fala_npc,
                "veredito": t.verificacao.veredito,
                "fato": t.verificacao.fato_id or "",
                "decisão": t.decisao,
                "geração (s)": round((t.latencia_geracao_ms or 0) / 1000, 1),
                "verificação (s)": round((t.latencia_verificacao_ms or 0) / 1000, 1),
                "justificativa": t.verificacao.justificativa,
            } for t in turnos],
            hide_index=True,
        )
    else:
        st.caption("Sessão vazia.")

    st.divider()
    st.markdown("**Exportar a sessão**")
    st.caption("JSON com ficha, cânone (inclusive desativados), todos os turnos com "
               "veredito e decisão, e os modelos usados.")
    nome_arquivo = f"sessao_{personagem.id}_{sessao.id}.json"
    c1, c2 = st.columns(2)
    c1.download_button(
        "Baixar JSON",
        data=pacote.sessao_para_json(pacote.exportar_sessao(sessao.id)),
        file_name=nome_arquivo,
        mime="application/json",
        type="primary",
        key=f"baixar_json_{sessao.id}",
    )
    if c2.button("Salvar cópia em docs/evidencias", key=f"salvar_evid_{sessao.id}"):
        destino = pacote.salvar_sessao_json(sessao.id, PASTA_EVIDENCIAS / nome_arquivo)
        st.success(f"Salvo em {destino}")


# --------------------------------------------------------------------- página

def main() -> None:
    mostrar_avisos()
    personagem, sessao = barra_lateral()

    if personagem is None:
        st.header("Boas-vindas ao Cânone")
        st.markdown(
            "Comece importando a personagem de exemplo (Inês, a herbolária) ou crie "
            "um personagem na barra lateral."
        )
        return

    st.header(personagem.nome)
    st.caption(f"{personagem.papel} · {personagem.registro_fala}")

    conversa, ficha, canone, registro = st.tabs(
        ["Conversa", "Ficha", "Cânone", "Registro e exportação"]
    )
    with conversa:
        aba_conversa(personagem, sessao)
    with ficha:
        aba_ficha(personagem)
    with canone:
        aba_canone(personagem)
    with registro:
        aba_registro(personagem, sessao)


main()
