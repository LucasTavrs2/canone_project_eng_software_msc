# Cânone

Diálogo de NPC gerado por modelo de linguagem, com verificação de consistência
canônica. Um modelo gera a fala do personagem; uma segunda chamada,
independente, verifica se a fala contradiz algum fato declarado como canônico.
O programa sinaliza, mas não bloqueia nada: a decisão é sempre de quem usa.

Prova de conceito parcial. Projeto final de disciplina do mestrado.

## Instalação

Requer Python 3.11 ou mais novo e um servidor de modelo compatível com a API
de chat da OpenAI. Foi testado com o LM Studio.

```powershell
cd C:\caminho\para\canone
pip install -r requirements.txt
python -m cli importar data\personagens\ines.yaml
python -m cli provedor
```

O último comando confere se o modelo está acessível.

## Uso

| Quem | Como | Comando |
|------|------|---------|
| Roteirista | interface web | `python -m streamlit run ui\app.py` |
| Roteirista | terminal | `python scripts\conversar.py` |
| Desenvolvedor | linha de comando | `python -m cli --help` |
| Desenvolvedor | módulo importável | `from cli import api` (ver `cli/api.py`) |
| Desenvolvedor | exemplo de integração | `python exemplos\vilarejo.py` |

Rode todos os comandos a partir da pasta do projeto.
Use `python -m streamlit` em vez de só `streamlit`: funciona mesmo quando a pasta
de scripts do Python não está no PATH do Windows.

## Configuração do provedor

O provedor é configurado por variáveis de ambiente, sem mudar código. Defina-as
na mesma janela do PowerShell, antes de rodar os comandos.

| Variável | Padrão | Para quê |
|----------|--------|----------|
| `CANONE_LLM_URL` | `http://localhost:1234/v1` | endereço do servidor |
| `CANONE_LLM_MODEL` | `qwen/qwen3.6-35b-a3b` | modelo usado pelos dois papéis |
| `CANONE_GERADOR_MODEL` | (o de cima) | modelo só do gerador |
| `CANONE_VERIFICADOR_MODEL` | (o de cima) | modelo só do verificador |
| `CANONE_LLM_API_KEY` | vazio | chave, se o servidor exigir |
| `CANONE_LLM_REASONING` | `none` | `reasoning_effort`; vazio = não enviar |
| `CANONE_LLM_TIMEOUT` | `300` | segundos de espera |
| `CANONE_DB` | `data\app.db` | arquivo do banco |

Exemplo: `$env:CANONE_VERIFICADOR_MODEL = "openai/gpt-oss-20b"`

## Estrutura

```
core/             domínio: contratos Pydantic, prompts, ciclo de um turno
  models.py         Personagem, FatoCanonico, Turno, Sessao, ResultadoVerificacao...
  prompts.py        prompts do gerador e do verificador
  dialogo.py        responder, regenerar, decidir, promover (usado por todas as interfaces)
infrastructure/   detalhes trocáveis
  provedor.py       adaptador HTTP do modelo (gerador e verificador configuráveis por papel)
  db.py             SQLite local, criação e migração do esquema
  schema.sql        tabelas personagem, fato_canonico, sessao, turno
  repositorio.py    persistência; devolve sempre modelos Pydantic
  pacote.py         personagem em YAML (importar/exportar) e sessão em JSON (exportar)
ui/app.py         interface web da roteirista (Streamlit)
cli/              interface do desenvolvedor
  comandos.py       linha de comando (python -m cli)
  api.py            módulo importável, superfície pública estável
scripts/          terminal interativo e geração de evidências
exemplos/         integração de exemplo num "script de jogo"
tests/            testes automatizados com servidor de modelo falso
data/             banco (app.db) e pacotes de personagem (personagens/*.yaml)
docs/evidencias/  saídas dos scripts de evidência
```

## Testes

```powershell
python -m pytest
```

São 43 testes. Os da interface (`tests/test_ui.py`) usam o AppTest do Streamlit
e são pulados se o Streamlit não estiver instalado. Os testes sobem um servidor falso que imita a API de chat, sem modelo de
linguagem, e usam um banco temporário: não tocam em `data\app.db` nem precisam
do LM Studio.

## Evidências

```powershell
python scripts\testar_verificador.py                 # bateria do verificador
python scripts\demonstrar_cn1.py                     # Cenário Negativo 1, antes e depois da promoção
python scripts\medir_latencia.py                     # latência real por turno
python scripts\conversar.py --registro docs\evidencias\sessao.txt
```

Cada script grava sua saída em `docs\evidencias\` (UTF-8, sem BOM).
