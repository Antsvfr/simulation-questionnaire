#!/usr/bin/env bash
# Inspection de l'île par la Forge.
#   bash forge/inspection.sh          -> rapport complet
#   bash forge/inspection.sh --hook   -> mode hook de fin de tâche (silencieux si tout va bien)
cd "$(dirname "$0")/.." || exit 1
MODE="$1"

if [ "$MODE" = "--hook" ]; then
  INPUT="$(cat)"
  # Évite une boucle infinie : si Claude répare déjà suite au hook, on le laisse finir.
  echo "$INPUT" | grep -q '"stop_hook_active": *true' && exit 0
fi

ERREURS=()
AVERTISSEMENTS=()
OK=0

besoin() { if [ -e "$1" ]; then OK=$((OK+1)); else ERREURS+=("manquant : $1"); fi; }

besoin CLAUDE.md
besoin registre.json
besoin journal-de-l-ile.md
besoin village/index.html
besoin village/ville.js
besoin village/residence.html
besoin operations/ile.py
# Registre des opérations : le journal chaîné doit être intègre (toute ligne modifiée est détectée)
if [ -f operations/journal.jsonl ]; then
  if python3 operations/ile.py verifier >/dev/null 2>&1; then OK=$((OK+1)); else ERREURS+=("journal des opérations altéré : python3 operations/ile.py verifier"); fi
fi
[ -s operations/capteurs-erreurs.log ] && AVERTISSEMENTS+=("des capteurs (hooks) ont échoué : voir operations/capteurs-erreurs.log")
for a in critique-clarte critique-exigence critique-strategie forgeron architecte; do
  besoin ".claude/agents/$a.md"
done

if command -v python3 >/dev/null 2>&1; then
  LISTE=$(python3 - <<'PY'
import json, sys
try:
    r = json.load(open("registre.json", encoding="utf-8"))
except Exception as e:
    print("ERREUR", "registre.json illisible :", e); sys.exit()
ids = set()
for b in r.get("batiments", []):
    if b.get("id") in ids:
        print("ERREUR", "id en double dans le registre :", b.get("id"))
    ids.add(b.get("id"))
    if b.get("type") == "maison":
        print("MAISON", b["id"], b.get("dossier", ""), b.get("agent", ""))
PY
)
  while read -r type id dossier agent; do
    [ -z "$type" ] && continue
    if [ "$type" = "ERREUR" ]; then ERREURS+=("$id $dossier $agent"); continue; fi
    besoin "$dossier/CLAUDE.md"
    besoin "$dossier/journal.md"
    besoin "$agent"
    n=$(grep -rIl "TODO" "$dossier" 2>/dev/null | wc -l | tr -d ' ')
    [ "$n" != "0" ] && AVERTISSEMENTS+=("$id : $n fichier(s) contiennent encore un TODO")
  done <<< "$LISTE"
else
  AVERTISSEMENTS+=("python3 absent : registre non vérifié")
fi

if [ "$MODE" = "--hook" ]; then
  if [ ${#ERREURS[@]} -gt 0 ]; then
    { echo "La Forge a trouvé des problèmes sur l'île. Répare-les (ou explique pourquoi c'est voulu) :"
      printf ' - %s\n' "${ERREURS[@]}"; } >&2
    exit 2
  fi
  exit 0
fi

# Inspection complète : tests du registre des opérations
if python3 -m unittest discover -s operations/tests >/dev/null 2>&1; then OK=$((OK+1)); else ERREURS+=("tests du registre en échec : python3 -m unittest discover -s operations/tests -v"); fi

mkdir -p forge/rapports
RAPPORT="forge/rapports/$(date +%F)-inspection.md"
{
  echo "# Inspection de l'île — $(date '+%F %H:%M')"
  echo
  echo "✔ $OK éléments vérifiés"
  echo
  echo "## Erreurs (${#ERREURS[@]})"
  for e in "${ERREURS[@]}"; do echo "- $e"; done
  echo
  echo "## Avertissements (${#AVERTISSEMENTS[@]})"
  for a in "${AVERTISSEMENTS[@]}"; do echo "- $a"; done
} > "$RAPPORT"
cat "$RAPPORT"
[ ${#ERREURS[@]} -eq 0 ]
