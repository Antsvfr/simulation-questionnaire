#!/usr/bin/env python3
"""Sert l'île en local, ouvre le village et la Résidence présidentielle.

    python3 serveur.py            (port 8000, ou le suivant libre)
    python3 serveur.py 8080
    python3 serveur.py 8080 --sans-navigateur

API (127.0.0.1 uniquement) :
  GET  /api/etat        projection 3D (agents réellement actifs)
  GET  /api/residence   tout ce que la Résidence affiche (projets, décisions, missions, problèmes…)
  GET  /api/journal     historique filtrable ?siege=&type=&n=
  GET  /api/verifier    intégrité du journal chaîné
  GET  /api/session     jeton d'écriture de cette session du serveur (lisible seulement par une page de même origine)
  POST /api/instruction | /api/decision | /api/priorite | /api/mission
       écritures du président : en-tête X-Ile-Jeton obligatoire, origine vérifiée, JSON ≤ 16 Ko
"""
import functools
import http.server
import json
import os
import re
import secrets
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE / "operations"))
import ile  # noqa: E402

JETON = secrets.token_urlsafe(24)          # change à chaque démarrage, jamais écrit sur disque
PRESIDENT = {"role": "president", "verifie": "jeton", "canal": "Résidence"}
INTERDITS = re.compile(r"^/(operations/(?!etat\.json$)|\.|.*/\.)")   # fichiers internes du registre, fichiers cachés


def _premieres_lignes(p: Path, n=4):
    try:
        L = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        return L[:n]
    except OSError:
        return None


def residence():
    """Agrège registre + projection du journal + états des lieux. Chaque donnée garde sa source."""
    p = ile.etat()
    v = ile.verifier()
    sieges = []
    for b in ile.registre().get("batiments", []):
        if b.get("type") not in ("maison",):
            continue
        sid = b["id"]
        s = p["sieges"].get(sid, {})
        edl = RACINE / b.get("dossier", "") / "etat-des-lieux.md"
        ms = [m for m in p["missions"].values() if m["siege"] == sid]
        sieges.append({
            "id": sid, "nom": b["nom"], "couleur": b.get("couleur"), "role": b.get("role"), "depot": b.get("depot") or None,
            "branche_active": b.get("branche_active") or None, "etat_registre": b.get("etat") or None,
            "priorite": s.get("priorite"), "priorite_motif": s.get("priorite_motif"),
            "etat": s.get("etat"),
            "etat_des_lieux": {"chemin": str(edl.relative_to(RACINE)), "extrait": _premieres_lignes(edl)} if edl.exists() else None,
            "prochaines_actions": sorted([m for m in ms if m["statut"] in ("proposee", "attente_president", "planifiee")], key=lambda m: (m["rang"] or 999, m["id"])),
            "missions_en_cours": [m for m in ms if m["statut"] in ("en_cours", "verification", "bloquee")],
            "problemes": [x for x in p["problemes"].values() if x["siege"] == sid and x["ouvert"]],
            "decisions": [d for d in p["decisions"].values() if d["siege"] == sid and d["verdict"] is None],
            "agents_actifs": [r for r in p["runs_actifs"] if r["siege"] == sid],
            "derniere_activite": s.get("derniere_activite"),
        })
    ordre = {"P1": 0, "P2": 1, "P3": 2, None: 3}
    sieges.sort(key=lambda x: (ordre.get(x["priorite"], 3), -len(x["decisions"]) - len([q for q in x["problemes"] if q["gravite"] == "bloquant"]), x["nom"]))
    return {
        "maj": p["maj"], "integrite": {"ok": v["ok"], "evenements": v["n"], "dernier_hash": v["dernier"], "erreurs": v["erreurs"][:5]},
        "sieges": sieges,
        "decisions": sorted([d for d in p["decisions"].values() if d["verdict"] is None], key=lambda d: d["quand"]),
        "decisions_tranchees": sorted([d for d in p["decisions"].values() if d["verdict"]], key=lambda d: d.get("tranchee", ""), reverse=True)[:10],
        "instructions": sorted(p["instructions"].values(), key=lambda i: i["quand"], reverse=True),
        "missions": sorted(p["missions"].values(), key=lambda m: (m["rang"] or 999, m["id"])),
        "agents_actifs": p["runs_actifs"], "agents_expires": p["runs_expires"],
        "runs": sorted(p["runs"].values(), key=lambda r: r["debut"], reverse=True)[:30],
        "innovation": {"statut": "prévu — étape 6 de la roadmap", "dossier": "innovation/", "actif": (RACINE / "innovation").exists() and any((RACINE / "innovation" / "opportunites").glob("*.md"))},
    }


class Gestionnaire(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _origine_ok(self):
        o = self.headers.get("Origin")
        if o is None:
            return True     # requête non navigateur (curl, tests) : le jeton reste obligatoire
        port = self.server.server_address[1]
        return o in (f"http://localhost:{port}", f"http://127.0.0.1:{port}")

    def do_GET(self):
        u = urlparse(self.path)
        if INTERDITS.match(u.path):
            return self._json(404, {"erreur": "introuvable"})
        try:
            if u.path == "/api/etat":
                return self._json(200, ile.etat_3d(ile.etat()))
            if u.path == "/api/residence":
                return self._json(200, residence())
            if u.path == "/api/verifier":
                return self._json(200, ile.verifier())
            if u.path == "/api/session":
                if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
                    return self._json(403, {"erreur": "origine refusée"})
                return self._json(200, {"jeton": JETON})
            if u.path == "/api/journal":
                q = parse_qs(u.query)
                evs = ile.lire()
                if q.get("siege"):
                    evs = [e for e in evs if e["donnees"].get("siege") == q["siege"][0]]
                if q.get("type"):
                    evs = [e for e in evs if e["type"].startswith(q["type"][0])]
                n = min(int(q.get("n", ["200"])[0]), 2000)
                return self._json(200, {"evenements": evs[-n:][::-1], "total": len(evs)})
        except ile.ErreurIle as e:
            return self._json(500, {"erreur": str(e)})
        if u.path.startswith("/api/"):
            return self._json(404, {"erreur": "introuvable"})
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if not self._origine_ok():
            return self._json(403, {"erreur": "origine refusée"})
        if not secrets.compare_digest(self.headers.get("X-Ile-Jeton", ""), JETON):
            return self._json(403, {"erreur": "jeton absent ou invalide"})
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._json(415, {"erreur": "JSON attendu"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > 16384:
            return self._json(413, {"erreur": "requête trop grande"})
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/instruction":
                ev = ile.donner_instruction(d.get("texte"), PRESIDENT, d.get("siege") or None)
            elif u.path == "/api/decision":
                ev = ile.trancher(d.get("id"), d.get("verdict"), PRESIDENT, (d.get("motif") or "")[:2000] or None)
            elif u.path == "/api/priorite":
                ev = ile.fixer_priorite(d.get("siege"), d.get("priorite"), PRESIDENT, (d.get("motif") or "")[:500] or None)
            elif u.path == "/api/mission":
                if d.get("vers") not in ("planifiee", "rejetee", "attente_president"):
                    return self._json(400, {"erreur": "le président peut retenir, rejeter ou mettre en attente une mission"})
                ev = ile.changer_statut(d.get("id"), d.get("vers"), PRESIDENT, (d.get("motif") or "")[:1000] or None)
            else:
                return self._json(404, {"erreur": "introuvable"})
        except (ile.ErreurIle, ValueError, TypeError) as e:
            return self._json(400, {"erreur": str(e)})
        return self._json(200, {"ok": True, "evenement": ev["id"], "hash": ev["hash"]})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8000
    handler = functools.partial(Gestionnaire, directory=str(RACINE))
    for p in range(port, port + 20):
        try:
            serveur = http.server.ThreadingHTTPServer(("127.0.0.1", p), handler)
            break
        except OSError:
            continue
    else:
        sys.exit(f"Aucun port libre entre {port} et {port + 19}.")
    if ile.JOURNAL.exists():
        ile._ecrire_etat(ile.etat())
    base = f"http://localhost:{serveur.server_address[1]}"
    print(f"Île des Agents : {base}/village/   ·   Résidence : {base}/village/residence.html   (Ctrl+C pour arrêter)")
    if "--sans-navigateur" not in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(base + "/village/")).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nServeur arrêté.")


if __name__ == "__main__":
    main()
