"""Linha de comando: o critério 'a CLI produz fala e veredito sem a interface web'."""
import json

from cli.comandos import main
from tests.conftest import FICHA_INES


def _rodar(capsys, *argv) -> tuple[int, str, str]:
    codigo = main(list(argv))
    saida = capsys.readouterr()
    return codigo, saida.out, saida.err


def test_fluxo_completo_do_dev(ambiente, capsys, tmp_path):
    codigo, out, _ = _rodar(capsys, "nova-sessao", "ines", "playtest", "--json")
    assert codigo == 0
    sessao_id = json.loads(out)["id"]

    codigo, out, _ = _rodar(capsys, "responder", sessao_id, "Você já foi à capital?", "--json")
    turno = json.loads(out)
    assert codigo == 0
    assert turno["verificacao"]["veredito"] == "contradiz"
    assert turno["verificacao"]["fato_id"] == "F02"
    assert turno["decisao"] == "pendente"

    codigo, out, _ = _rodar(capsys, "decidir", turno["id"], "descartada")
    assert codigo == 0 and "descartada" in out

    codigo, out, _ = _rodar(capsys, "responder", sessao_id, "Oi.", "--aceitar")
    assert codigo == 0 and "aceita" in out and "Inês >" in out

    destino = tmp_path / "registro.json"
    codigo, _, _ = _rodar(capsys, "exportar", sessao_id, "-o", str(destino))
    exportado = json.loads(destino.read_text(encoding="utf-8"))
    assert codigo == 0 and len(exportado["turnos"]) == 2 and exportado["memoria"] == [1]


def test_verificar_sem_gerar(ambiente, capsys):
    codigo, out, _ = _rodar(capsys, "verificar", "ines", "Fui à capital ontem.", "--json")
    assert codigo == 0 and json.loads(out)["fato_id"] == "F02"
    assert all("response_format" in r for r in ambiente.requisicoes)


def test_provedor_ok(ambiente, capsys):
    codigo, out, _ = _rodar(capsys, "provedor")
    assert codigo == 0 and "OK" in out


def test_provedor_fora_do_ar_codigo_3(ambiente, capsys, monkeypatch):
    monkeypatch.setenv("CANONE_LLM_URL", "http://127.0.0.1:9/v1")
    codigo, _, _ = _rodar(capsys, "provedor")
    assert codigo == 3
    sessao = _rodar(capsys, "nova-sessao", "ines", "x")[1].strip()
    codigo, _, err = _rodar(capsys, "responder", sessao, "Oi.")
    assert codigo == 3 and "[provedor]" in err


def test_erro_de_dados_codigo_1(ambiente, capsys):
    codigo, _, err = _rodar(capsys, "responder", "sessao-inexistente", "Oi.")
    assert codigo == 1 and "não existe" in err


def test_importar_e_exportar_personagem(ambiente, capsys, tmp_path):
    destino = tmp_path / "ines_export.yaml"
    assert _rodar(capsys, "exportar-personagem", "ines", "-o", str(destino))[0] == 0
    codigo, out, _ = _rodar(capsys, "importar", str(destino))
    assert codigo == 0 and "10 fatos ativos" in out
    codigo, out, _ = _rodar(capsys, "fatos", "ines")
    assert "[F01]" in out


def test_promover_pela_cli(ambiente, capsys):
    sessao = _rodar(capsys, "nova-sessao", "ines", "x")[1].strip()
    turno = json.loads(_rodar(capsys, "responder", sessao, "Você tinha marido?", "--json")[1])
    codigo, out, _ = _rodar(capsys, "promover", turno["id"], "Inês foi casada.")
    assert codigo == 0 and "[F11]" in out
    codigo, out, _ = _rodar(capsys, "verificar", "ines", "Nunca tive marido.", "--json")
    assert json.loads(out)["fato_id"] == "F11"
