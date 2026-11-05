#!/usr/bin/env python3
"""Sert l'île en local et ouvre le village dans le navigateur.

    python3 serveur.py            (port 8000, ou le suivant libre)
    python3 serveur.py 8080
"""
import functools
import http.server
import os
import sys
import threading
import webbrowser

RACINE = os.path.dirname(os.path.abspath(__file__))


class Gestionnaire(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Pas de cache : le village relit etat-de-l-ile.json et les journaux toutes les 3 s.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # silencieux (le village interroge le serveur toutes les 3 s)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(Gestionnaire, directory=RACINE)
    for p in range(port, port + 20):
        try:
            serveur = http.server.ThreadingHTTPServer(("127.0.0.1", p), handler)
            break
        except OSError:
            continue
    else:
        sys.exit(f"Aucun port libre entre {port} et {port + 19}.")
    url = f"http://localhost:{serveur.server_address[1]}/village/"
    print(f"Île des Agents servie sur {url}  (Ctrl+C pour arrêter)")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nServeur arrêté.")


if __name__ == "__main__":
    main()
