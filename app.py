"""Sobe o site de dados em http://127.0.0.1:8765/

A pasta publicada é site/. Para atualizar os números, rode antes
02_exportar_site.py. O 2º turno só muda depois de 01_pipeline_dados.py --refresh-2t.
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
PORTA = 8765


def main() -> None:
    if not (SITE / "index.html").exists():
        raise SystemExit("site/index.html não existe. Rode 02_exportar_site.py antes.")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORTA), handler) as httpd:
        url = f"http://127.0.0.1:{PORTA}/"
        print(f"Site no ar em {url}", flush=True)
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Servidor encerrado.")


if __name__ == "__main__":
    main()
