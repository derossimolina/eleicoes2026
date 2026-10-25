"""Sobe o site e, se o navegador não alcançar o TSE, o proxy /tse/.

A pasta publicada é site/. A página pede primeiro o JSON oficial do 2º turno
de 2026 (eleição 6258). Os arquivos /tse/ só encaminham esse mesmo JSON.
Não é um proxy aberto.

No Render, a variável PORT existe e o processo escuta em 0.0.0.0.
Na máquina local, fica em http://127.0.0.1:8765/.
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
BASE = "https://resultados.tse.jus.br/oficial/ele2026/6258/dados"
HOST_TSE = "resultados.tse.jus.br"
UFS = frozenset(
    "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to".split()
)


class SemSairDoTse(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urllib.parse.urlparse(newurl).hostname
        if host != HOST_TSE:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urllib.request.install_opener(urllib.request.build_opener(SemSairDoTse))


def url_tse(caminho: str) -> str | None:
    partes = [p for p in caminho.split("/") if p]
    if partes == ["tse", "br"]:
        return f"{BASE}/br/br-c0001-e006258-u.json"
    if len(partes) == 3 and partes[0] == "tse" and partes[1] == "uf":
        uf = partes[2].lower()
        if uf not in UFS:
            return None
        return f"{BASE}/{uf}/{uf}-c0001-e006258-u.json"
    if len(partes) == 4 and partes[0] == "tse" and partes[1] == "mun":
        uf = partes[2].lower()
        cd = partes[3]
        if uf not in UFS or not re.fullmatch(r"\d{5}", cd):
            return None
        return f"{BASE}/{uf}/{uf}{cd}-c0001-e006258-u.json"
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def do_GET(self):
        caminho = urllib.parse.urlparse(self.path).path
        if caminho.startswith("/tse/"):
            self.encaminhar_tse(caminho)
            return
        super().do_GET()

    def encaminhar_tse(self, caminho: str) -> None:
        destino = url_tse(caminho)
        if destino is None:
            self.responder(404, b'{"erro":"caminho recusado"}')
            return
        pedido = urllib.request.Request(
            destino,
            headers={"Accept": "application/json", "User-Agent": "eleicoes2026 derossi.dev"},
        )
        try:
            with urllib.request.urlopen(pedido, timeout=30) as resp:
                corpo = resp.read()
                codigo = getattr(resp, "status", 200)
                tipo = resp.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as erro:
            corpo = erro.read()
            codigo = erro.code
            tipo = erro.headers.get("Content-Type", "application/json") if erro.headers else "application/json"
        except Exception as erro:
            print(f"proxy {caminho} {erro}", flush=True)
            self.responder(502, b'{"erro":"sem resposta do TSE"}')
            return
        self.responder(codigo, corpo, tipo)

    def responder(self, codigo: int, corpo: bytes, tipo: str = "application/json; charset=utf-8") -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


def main() -> None:
    if not (SITE / "index.html").exists():
        raise SystemExit("site/index.html não existe. Rode 02_exportar_site.py antes.")
    porta = int(os.environ.get("PORT", "8765"))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((host, porta), Handler)
    print(f"Site no ar em http://127.0.0.1:{porta}/", flush=True)
    if host == "127.0.0.1" and os.environ.get("ELEICOES_SEM_BROWSER") != "1":
        webbrowser.open(f"http://127.0.0.1:{porta}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Servidor encerrado.")


if __name__ == "__main__":
    main()
