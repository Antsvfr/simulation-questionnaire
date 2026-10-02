# Simulation de questionnaire — IA dans l'éducation (Q1–Q15)

> **DONNÉES SYNTHÉTIQUES — SIMULATION PÉDAGOGIQUE — AUCUNE RÉPONSE RÉELLEMENT COLLECTÉE**

Application Streamlit qui génère un échantillon synthétique (100 étudiants par défaut) pour s'entraîner à
analyser un questionnaire. **Aucune connexion à Qualtrics** ni à un service externe ; rien n'est envoyé.
La mention figure sur chaque page, chaque graphique (titre + annotation, donc aussi dans l'export image)
et chaque export (CSV, Excel, JSON).

## Lancement (macOS / Linux)

```bash
git clone https://github.com/antsvfr/simulation-questionnaire.git
cd simulation-questionnaire
git checkout claude/ai-education-survey-simulator-yqkf9f
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Tests (facultatif, ~1 min) : `python -m pytest -q`. Python ≥ 3.10 recommandé.

## Fonctionnement de l'échantillon

- L'échantillon est conservé dans `st.session_state` avec **les paramètres exacts de sa génération**.
  Changer d'onglet, filtrer, trier ou télécharger ne le régénère jamais.
- Modifier les réglages de la barre latérale affiche « paramètres non encore appliqués ».
- **🔁 Reproduire avec cette graine** : régénère avec les réglages et la graine saisis (mêmes paramètres +
  même graine = mêmes données). **🎲 Générer un nouvel échantillon** : tire et affiche une nouvelle graine.
- Onglets : Échantillon détaillé (indicateurs, tableau Q1–Q15, filtres, tri, lisible/codes) · Fiche individuelle ·
  Composition (probabilités paramétrées vs proportions observées) · Échelles · Comparaisons · Corrélations · Exports.
- Un sélecteur de **périmètre** (ensemble / profils filtrés) s'applique aux résumés et graphiques ; le périmètre et
  le dénominateur sont toujours affichés.

## Questionnaire

| Q | Échelle |
|---|---|
| Q1–Q4 | Catégorielles, codes 1…n dans l'ordre des modalités |
| Q5–Q8, Q13–Q15 | 1–6 (extrémités nommées ; Q13 Réducteur→Stimulant, Q14 Négatif→Positif, Q15 Impersonnelle→Personnalisée) |
| Q9–Q12 | Accord à 5 niveaux : 1 Pas du tout d'accord · 2 Plutôt pas d'accord · 3 Neutre · 4 Plutôt d'accord · 5 Tout à fait d'accord |

Les échelles à 5 et 6 niveaux sont toujours présentées séparément. **Aucun score global n'est calculé sur
Q9–Q12** (dimensions différentes).

## Non applicable ≠ manquant

- **Non applicable** : question non posée à ce répondant.
- **Manquant** : non-réponse accidentelle simulée (paramètre, 2 % par défaut, sur les cellules applicables Q2–Q15).
- Dans les codes, les deux sont des cellules vides ; les colonnes `Qx_statut` (`répondu` / `non_applicable` /
  `manquant`) les distinguent. L'application affiche le *n utilisé* partout et un tableau d'effectifs.

### Filtres (non-utilisateurs : Q1 = Non)
- **Minimum exigé par la consigne** — non applicables : **Q8, Q9, Q11, Q12**.
- **Conventions de la simulation, non vérifiées dans Qualtrics** : Q5 et Q7 aussi réservées aux utilisateurs ;
  Q6, Q10, Q13, Q14, Q15 posées à tous. Ces choix sont modifiables dans `survey_config.py` (`asked`/`rule`).

## Modèle de simulation (hypothèses, pas des résultats)

- Un trait latent « appétence pour l'IA » (construction de la simulation) est lié positivement à Q1, Q5, Q7, Q9,
  Q12–Q15 (force réglable) ; Q6 y est faiblement lié ; Q8 dépend légèrement du niveau d'études ;
  Q11 est indépendante du trait. Q5 → Q7 et Q5 → Q9 ont un lien additionnel modeste.
- **Q10 : aucune association imposée par défaut** (ni trait latent, ni âge). Deux curseurs optionnels
  (`lien_q10_latent`, `lien_q10_age`, défaut 0) permettent de tester une association.
- Avec n ≈ 100, des corrélations de ±0,2–0,3 apparaissent par hasard : ne pas les interpréter.
- `Profil_latent_simulé` (appétence faible / intermédiaire / élevée) catégorise ce trait ; **aucun profil n'est réel**.
- Âge et niveau d'études sont cohérents (< 18 ans → Bac/L1-L2). Même graine → mêmes données.

## Exports

Deux blocs séparés : **tout l'échantillon** et **profils filtrés uniquement**. Pour chacun : CSV lisible, CSV
codes + statuts, Excel (feuilles *Réponses lisibles*, *Codes et statuts*, *Dictionnaire*, *Composition*,
*Paramètres et méthode*) et JSON. Noms de fichier `SIMULATION_SYNTHETIQUE_…` ; colonne `Origine` dans chaque ligne ;
en-têtes en première ligne (pas de ligne de commentaire) ; UTF-8 avec BOM (accents corrects dans Excel).
Dans le CSV « codes », une cellule vide = non applicable **ou** manquant : voir `Qx_statut`.

## Validité des analyses

- Aucun score global ; Q9–Q12 (5 modalités) et Q5–Q8, Q13–Q15 (6 modalités) restent séparées.
- Corrélations de Spearman sur paires complètes, uniquement entre échelles ordinales (jamais sur genre, âge, etc.) ;
  refusées si n < 10 ou variable constante (« – » affiché, motif listé) ; n par paire affiché.
- Les réponses absentes ne sont jamais remplies : un questionnaire « complet » n'a aucune réponse accidentellement
  manquante parmi les questions applicables ; les non applicables ne comptent pas comme oubli.

## Fichiers

`survey_config.py` (questionnaire, textes, filtres) · `simulator.py` (génération, statuts) · `views.py` (tableaux, filtres,
composition, corrélations) · `exports.py` (CSV/Excel/JSON) · `app.py` (interface) · `tests_*.py` (générateur/vues,
exports relus, parcours Streamlit AppTest).

## Relire les exports

```python
pd.read_csv("SIMULATION_SYNTHETIQUE_lisibles_tout_graine42_100profils.csv", encoding="utf-8-sig")
pd.read_excel("SIMULATION_SYNTHETIQUE_classeur_tout_graine42_100profils.xlsx", sheet_name="Réponses lisibles")
```
Dans l'Excel, les feuilles annexes (Dictionnaire, Composition, Paramètres et méthode) ont le bandeau en A1 et leurs
tableaux à partir de la ligne 3.
