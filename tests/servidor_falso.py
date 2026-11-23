"""Servidor falso compatível com a API de chat da OpenAI, só para testes.

Responde de forma determinística, sem modelo de linguagem, para que os testes
exercitem o caminho HTTP real do adaptador (infrastructure/provedor.py) sem
depender do LM Studio. Também pode ser rodado sozinho para experimentar as
interfaces sem modelo:

    python tests/servidor_falso.py            # escuta em 127.0.0.1:1234
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Fala do jogador (trecho) -> fala que o "gerador" devolve.
FALAS = {
    "capital": "Fui à capital vender ervas na primavera passada.",
    "marido": "Meu marido trabalhava pra guilda. Morreu antes da cheia.",
    "sozinha": "Nunca tive marido. Criei o Tomé sozinha.",
    "alucina": "Isso aqui é alucinação.",
}
FALA_PADRAO = "Hm. Tenho ervas pra separar."

# Trecho da fala do NPC -> (palavra que identifica o fato no cânone, ou id fixo).
CONTRADICOES = [
    ("capital", "limites do vilarejo"),
    ("nunca tive marido", "casada"),
    ("alucinação", "#F99"),          # fato inexistente: testa o rebaixamento
]


def _fatos(texto_usuario: str) -> dict[str, str]:
    return dict(re.findall(r"^\[(F\d+)\] (.+)$", texto_usuario, flags=re.MULTILINE))


def veredito(texto_usuario: str) -> dict:
    fala = texto_usuario.split("FALA A VERIFICAR", 1)[-1].strip().lower()
    fatos = _fatos(texto_usuario)
    for gatilho, alvo in CONTRADICOES:
        if gatilho in fala:
            if alvo.startswith("#"):
                return {"veredito": "contradiz", "fato_id": alvo[1:],
                        "justificativa": "teste de fato inexistente"}
            for fato_id, texto in fatos.items():
                if alvo in texto.lower():
                    return {"veredito": "contradiz", "fato_id": fato_id,
                            "justificativa": f"contraria {fato_id}"}
    return {"veredito": "consistente", "fato_id": None,
            "justificativa": "nenhum conflito encontrado"}


class _Manipulador(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencioso
        pass

    def _responder(self, status: int, corpo: dict) -> None:
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._responder(200, {"data": [{"id": m} for m in self.server.modelos]})
        else:
            self._responder(404, {"error": "not found"})

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        self.server.requisicoes.append(payload)

        if payload.get("model") not in self.server.modelos:
            self._responder(404, {"error": f"model {payload.get('model')} not found"})
            return

        mensagem = {"role": "assistant", "content": ""}
        motivo = "stop"
        if self.server.modo == "vazio":
            mensagem["reasoning_content"] = "pensando..." * 10
            motivo = "length"
        elif "response_format" in payload:
            texto = payload["messages"][-1]["content"]
            resultado = veredito(texto)
            if self.server.modo == "json_quebrado":
                mensagem["content"] = '{"veredito": "talvez"}'
            else:
                mensagem["content"] = json.dumps(resultado, ensure_ascii=False)
        else:
            pergunta = payload["messages"][-1]["content"].lower()
            fala = next((f for k, f in FALAS.items() if k in pergunta), FALA_PADRAO)
            mensagem["content"] = fala

        self._responder(200, {"choices": [{"message": mensagem, "finish_reason": motivo}]})


class ServidorFalso(ThreadingHTTPServer):
    def __init__(self, porta: int = 0, modelos=("modelo-falso",)):
        super().__init__(("127.0.0.1", porta), _Manipulador)
        self.modelos = list(modelos)
        self.requisicoes: list[dict] = []
        self.modo = "normal"   # "normal" | "vazio" | "json_quebrado"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/v1"

    def iniciar(self) -> "ServidorFalso":
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--porta", type=int, default=1234)
    p.add_argument("--modelo", default="qwen/qwen3.6-35b-a3b")
    a = p.parse_args()
    s = ServidorFalso(a.porta, modelos=[a.modelo])
    print(f"Servidor falso em {s.url} (modelo {a.modelo!r}). Ctrl+C encerra.")
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
