#!/usr/bin/env python3
"""Prouve les critères de fin des étapes 0 et 1. Sortie : PASS / FAIL / NOT TESTED pour chaque critère.

    python3 operations/preuves.py            (tout sauf le test 3D si Playwright est absent)
    python3 operations/preuves.py --claude   (ajoute le test « l'île se charge dans une vraie session Claude Code » : consomme un peu d'usage)

Les tests qui écrivent travaillent sur une COPIE du journal (dossier temporaire) : le vrai registre n'est jamais modifié.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ILE = Path(__file__).resolve().parents[1]
DEPOT = ILE.parent
RES = []


def note(cid, titre, statut, detail=""):
    RES.append((cid, titre, statut, detail))
    print(f"{statut:<11} {cid:<5} {titre}" + (f"\n            {detail}" if detail else ""), flush=True)


def check(cid, titre, fn):
    try:
        ok, detail = fn()
        note(cid, titre, "PASS" if ok else "FAIL", detail)
    except Exception as e:
        note(cid, titre, "FAIL", f"{type(e).__name__}: {e}")


def port_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def http(port, path, body=None, headers=None, method=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers or {}, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def main():
    tmp = Path(tempfile.mkdtemp(prefix="ile-preuves-"))
    if (ILE / "operations" / "journal.jsonl").exists():
        shutil.copy(ILE / "operations" / "journal.jsonl", tmp / "journal.jsonl")
    env = dict(os.environ, ILE_OPS=str(tmp))
    port = port_libre()
    srv = subprocess.Popen([sys.executable, str(ILE / "serveur.py"), str(port), "--sans-navigateur"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=.2).close(); break
        except OSError:
            time.sleep(.1)
    sys.path.insert(0, str(ILE / "operations"))
    os.environ["ILE_OPS"] = str(tmp)
    import ile
    try:
        print(f"Preuves — journal copié dans {tmp}, serveur de test sur le port {port}\n")
        print("— Étape 0 : Résidence présidentielle —")

        def c01():
            s, d = http(port, "/api/residence")
            champs = {"priorite", "etat", "prochaines_actions", "problemes", "decisions", "etat_des_lieux"}
            manque = [x["id"] for x in d["sieges"] if not champs <= set(x)]
            return s == 200 and d["sieges"] and not manque and "decisions" in d and "instructions" in d, f"{len(d['sieges'])} projets, {len(d['decisions'])} décisions en attente, {sum(len(x['problemes']) for x in d['sieges'])} problèmes ouverts"
        check("C0.1", "La Résidence expose projets, priorité, avancement, prochaines actions, problèmes et décisions", c01)

        def c02():
            s, d = http(port, "/api/residence")
            sans_source = [f"{x['id']}:{i['nom']}" for x in d["sieges"] if x["etat"] for i in x["etat"]["indicateurs"] if not i.get("source")]
            sans_source += [p["id"] for x in d["sieges"] for p in x["problemes"] if not p.get("source")]
            sans_source += [q["id"] for q in d["decisions"] if not q.get("source")]
            nr = [x["id"] for x in d["sieges"] if not x["etat"] and not x["etat_des_lieux"]]
            return not sans_source, f"aucune donnée sans source ; « non renseigné » pour : {', '.join(nr) or 'aucun'}" if not sans_source else f"sans source : {sans_source[:6]}"
        check("C0.2", "Chaque donnée affichée cite sa source ; « non renseigné » sinon", c02)

        def c03():
            _, j = http(port, "/api/session")
            h = {"Content-Type": "application/json", "X-Ile-Jeton": j["jeton"]}
            s, r = http(port, "/api/instruction", {"texte": "Instruction de test des preuves"}, h)
            i = ile.etat()["instructions"][r["evenement"]]
            out = subprocess.run([sys.executable, str(ILE / "operations" / "ile.py"), "capteur", "session"], input=json.dumps({"session_id": "preuves"}), capture_output=True, text=True, env=env).stdout
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
            lue = ile.etat()["instructions"][r["evenement"]]["statut"]
            return s == 200 and i["auteur"]["verifie"] == "jeton" and "Instruction de test des preuves" in ctx and lue == "lue", f"inscrite ({r['evenement']}, auteur vérifié par jeton) → présentée au DG au démarrage de session → statut « {lue} »"
        check("C0.3", "Une instruction de la Résidence parvient au DG (hook SessionStart) et son statut le montre", c03)

        def c04():
            _, j = http(port, "/api/session")
            r1, _ = http(port, "/api/instruction", {"texte": "x"}, {"Content-Type": "application/json"})
            r2, _ = http(port, "/api/instruction", {"texte": "x"}, {"Content-Type": "application/json", "X-Ile-Jeton": j["jeton"], "Origin": "https://site-malveillant.example"})
            r3, _ = http(port, "/operations/journal.jsonl")
            r4, _ = http(port, "/api/session", headers={"Sec-Fetch-Site": "cross-site"})
            r5, _ = http(port, "/.git/config")
            ok = (r1, r2, r3, r4, r5) == (403, 403, 404, 403, 404)
            return ok, f"sans jeton {r1} · autre origine {r2} · journal brut {r3} · jeton depuis un autre site {r4} · fichier caché {r5}"
        check("C0.4", "Écritures protégées : jeton, origine ; fichiers internes non servis", c04)

        def c05():
            _, j = http(port, "/api/session")
            h = {"Content-Type": "application/json", "X-Ile-Jeton": j["jeton"]}
            d = next(iter(x for x in ile.etat()["decisions"].values() if x["verdict"] is None), None)
            if not d:
                return False, "aucune décision en attente à trancher"
            s1, _ = http(port, "/api/decision", {"id": d["id"], "verdict": "reportee", "motif": "test"}, h)
            s2, _ = http(port, "/api/decision", {"id": d["id"], "verdict": "approuvee"}, h)
            s3, _ = http(port, "/api/priorite", {"siege": "rev-em", "priorite": "P1"}, h)
            return (s1, s2, s3) == (200, 400, 200) and ile.etat()["decisions"][d["id"]]["par"]["role"] == "president", f"verdict inscrit {s1} · double verdict refusé {s2} · priorité fixée {s3} (sur la copie)"
        check("C0.5", "Le président tranche et fixe les priorités depuis la Résidence ; tout est inscrit", c05)

        def c06():
            reg = {b["id"]: b for b in json.loads((ILE / "registre.json").read_text())["batiments"]}
            _, d = http(port, "/api/residence")
            return "innovation" in reg and (ILE / "innovation" / "README.md").exists() and all((ILE / "innovation" / x).is_dir() for x in ("signaux", "opportunites", "decisions")) and "innovation" in d, "registre (chantier), dossier innovation/{signaux,opportunites,decisions}, section de la Résidence"
        check("C0.6", "Emplacement du département Innovation & Business prévu", c06)

        print("\n— Étape 1 : fondations —")

        def c11():
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ILE / "operations" / "tests")], capture_output=True, text=True, cwd=ILE)
            ligne = [l for l in r.stderr.splitlines() if l.startswith("Ran ")]
            return r.returncode == 0, (ligne[0] if ligne else "") + (" — OK" if r.returncode == 0 else " — " + r.stderr[-300:])
        check("C1.1", "Tests du registre (chaîne, transitions, droits, classement, parallélisme, agents fantômes)", c11)

        def c12():
            r = subprocess.run([sys.executable, str(ILE / "operations" / "ile.py"), "verifier"], capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "ILE_OPS"})
            return r.returncode == 0, r.stdout.strip()
        check("C1.2", "Le VRAI journal des opérations est intègre", c12)

        def c13():
            s = json.loads((DEPOT / ".claude" / "settings.json").read_text())
            cmds = [h["command"] for ev in s["hooks"].values() for g in ev for h in g["hooks"]]
            fichiers = [c.split('"')[1].replace("$CLAUDE_PROJECT_DIR", str(DEPOT)) for c in cmds]
            manquants = [f for f in fichiers if not Path(f).exists()]
            agents = sorted(p.name for p in (DEPOT / ".claude" / "agents").glob("*.md"))
            imp = "@ile-des-agents/CLAUDE.md" in (DEPOT / "CLAUDE.md").read_text()
            return not manquants and "chef-rev-em.md" in agents and (DEPOT / ".claude" / "commands" / "revue.md").exists() and imp, f"{len(cmds)} hooks pointent vers des fichiers existants · {len(agents)} agents et /revue visibles à la racine · constitution importée"
        check("C1.3", "Île active à la racine du dépôt (réglages, agents, commandes, constitution)", c13)

        def c14():
            s = json.loads((DEPOT / ".claude" / "settings.json").read_text())
            cmd = s["hooks"]["SubagentStart"][0]["hooks"][0]["command"].replace("$CLAUDE_PROJECT_DIR", str(DEPOT))
            e2 = dict(env, CLAUDE_PROJECT_DIR=str(DEPOT))
            subprocess.run(["bash", "-c", cmd], input=json.dumps({"agent_type": "general-purpose", "agent_id": "preuve-1", "session_id": "preuves", "transcript_path": "/tmp/t.jsonl"}), text=True, env=e2)
            r = [x for x in ile.etat()["runs"].values() if x.get("agent_id") == "preuve-1"]
            stop = s["hooks"]["SubagentStop"][0]["hooks"][0]["command"].replace("$CLAUDE_PROJECT_DIR", str(DEPOT))
            subprocess.run(["bash", "-c", stop], input=json.dumps({"agent_type": "general-purpose", "agent_id": "preuve-1", "session_id": "preuves"}), text=True, env=e2)
            r2 = [x for x in ile.etat()["runs"].values() if x.get("agent_id") == "preuve-1"]
            return r and r[0]["fin"] is None and r2[0]["fin"] is not None and r2[0]["transcript"], f"hook de départ → {r[0]['run']} (agent_id, session, trace) ; hook d'arrêt → exécution close"
        check("C1.4", "Les hooks de la racine inscrivent chaque agent avec son identité Claude Code", c14)

        def c15():
            a = {"role": "maire", "verifie": "declare"}
            _, e0 = http(port, "/api/etat")
            base = sorted(r["run"] for r in e0["runs_actifs"])   # exécutions réellement ouvertes avant le test (ex. la Forge qui lance les preuves)
            r1 = ile.run_debut("chef-lexnote", a)["donnees"]["run"]; r2 = ile.run_debut("chef-upsa-sales-pilot", a)["donnees"]["run"]
            _, e = http(port, "/api/etat")
            avant = sorted(e["sieges_actifs"])
            ile.run_fin(r1, a); ile.run_fin(r2, a)
            _, e2 = http(port, "/api/etat")
            apres = sorted(r["run"] for r in e2["runs_actifs"])
            return {"lexnote", "upsa-sales-pilot"} <= set(avant) and apres == base, f"2 missions en parallèle → sièges actifs {avant} ; après clôture → exécutions actives {apres or 'aucune'} (déjà ouvertes avant le test : {base or 'aucune'})"
        check("C1.5", "État v2 : plusieurs sièges actifs en parallèle, aucun agent sans exécution", c15)

        def c16():
            evs = ile.lire()
            props = [e for e in evs if e["type"] in ("mission.proposee", "siege.etat", "probleme.signale") and e["auteur"]["role"].startswith("chef-")]
            faibles = [e["id"] for e in props if e["auteur"]["verifie"] not in ("run", "hook", "jeton")]
            return props and not faibles, f"{len(props)} inscriptions de directeurs, toutes rattachées à une exécution ouverte" if not faibles else f"non vérifiées : {faibles}"
        check("C1.6", "Chaque proposition de directeur est attribuée à un agent identifié par son exécution", c16)

        def c17():
            ms = [m for m in ile.etat()["missions"].values() if m["statut"] in ("proposee", "attente_president", "planifiee")]
            sans = [m["id"] for m in ms if m["score"] is None or not m["classement"] or not m["classement"]["motif"]]
            return ms and not sans, f"{len(ms)} missions classées avec score, détail et motif" if not sans else f"non classées : {sans}"
        check("C1.7", "Le directeur général a classé les propositions (score + motif)", c17)

        def c18():
            node = shutil.which("node")
            js = ILE / "operations" / "tests" / "village_3d.js"
            if not node:
                return None, "node absent"
            r = subprocess.run([node, str(js), str(port)], capture_output=True, text=True, timeout=600, env=env)
            if r.returncode == 3:
                return None, r.stdout.strip() or r.stderr.strip()[-200:]
            return r.returncode == 0, r.stdout.strip()[-600:] or r.stderr.strip()[-400:]
        try:
            ok, det = c18()
            note("C1.8", "Métropole 3D : deux sièges allumés et deux courriers pour deux exécutions réelles, rien sinon", "NOT TESTED" if ok is None else ("PASS" if ok else "FAIL"), det)
        except Exception as e:
            note("C1.8", "Métropole 3D", "FAIL", str(e))

        if "--claude" in sys.argv:
            def c19():
                r = subprocess.run(["claude", "-p", "Réponds uniquement par la liste, séparée par des virgules, des noms des sous-agents dont le nom commence par chef-.", "--max-turns", "2"],
                                   cwd=DEPOT, capture_output=True, text=True, timeout=240, env={k: v for k, v in os.environ.items() if k != "ILE_OPS"})
                return "chef-rev-em" in r.stdout, (r.stdout.strip() or r.stderr.strip())[:300]
            check("C1.9", "Une vraie session Claude Code ouverte à la racine charge les agents de l'île", c19)
        else:
            note("C1.9", "Une vraie session Claude Code ouverte à la racine charge les agents de l'île", "NOT TESTED", "relancer avec --claude (consomme un peu d'usage)")
    finally:
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
    n = {s: sum(1 for r in RES if r[2] == s) for s in ("PASS", "FAIL", "NOT TESTED")}
    print(f"\nBilan : {n['PASS']} PASS · {n['FAIL']} FAIL · {n['NOT TESTED']} NOT TESTED")
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
