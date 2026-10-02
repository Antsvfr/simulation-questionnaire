# Simulation de questionnaire — IA dans l'éducation

> **DONNÉES SYNTHÉTIQUES — SIMULATION PÉDAGOGIQUE — AUCUNE RÉPONSE RÉELLEMENT COLLECTÉE**

Application Streamlit qui génère un échantillon synthétique (100 étudiants par défaut) pour s'entraîner
à analyser un questionnaire. **Aucune connexion à Qualtrics** ni à un service externe ; rien n'est envoyé.
La mention d'avertissement figure sur chaque page, chaque graphique (titre + annotation, donc aussi dans
l'export PNG) et chaque export (CSV, Excel, JSON).

## Lancement

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
python -m pytest -q tests_simulator.py               # tests (facultatif)
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `survey_config.py` | Questions, modalités, codes, bandeau d'avertissement |
| `simulator.py` | Génération des données, exports, alpha de Cronbach |
| `app.py` | Interface Streamlit + graphiques Plotly |
| `tests_simulator.py` | Tests (reproductibilité, codes valides, filtre, exports) |

## Modèle de simulation

- Un trait latent « enthousiasme envers l'IA » pilote Q5, Q7, Q9 (corrélés), Q6 plus faiblement et Q10 négativement
  (les sceptiques réclament plus d'encadrement).
- L'âge et le niveau d'études sont cohérents (ex. < 18 ans → Bac/L1-L2) ; ils influencent Q1 et Q8.
- **Filtre** : Q5–Q9 ne sont posées qu'aux utilisateurs (Q1 = Oui), vides sinon ; Q10 est posée à tous.
- La colonne `Profil_simulé` donne la « vérité terrain » (Non-utilisateur / Sceptique / Pragmatique / Enthousiaste).
- Même graine → mêmes données. Paramètres réglables : taille, graine, taux d'usage, répartition d'âge.

## Codes

Q1–Q4 : codes 1…n dans l'ordre des modalités (ex. Q1 : 1 = Oui, 2 = Non). Q5–Q8 : 1–6 avec ancrages
aux extrémités. Q9–Q10 : accord 1 (Pas du tout d'accord) → 6 (Tout à fait d'accord). Le dictionnaire complet
est dans l'export Excel (feuille « Dictionnaire »).

## Hypothèses à valider

L'énoncé fourni s'arrêtait en cours de Q10 et ne précisait pas l'échelle de Q9/Q10. J'ai supposé :
Q10 = « Les établissements d'enseignement devraient encadrer l'utilisation de l'IA », et Q9/Q10 en échelle
d'accord à 6 points. Tout se modifie dans `survey_config.py` (et la logique de génération dans `simulator.py`).
Si le questionnaire comporte d'autres questions (Q11+), il suffit de les ajouter à `QUESTIONS` et au simulateur.

## Relire les exports

```python
pd.read_csv("SIMULATION_echantillon_synthetique.csv", comment="#", encoding="utf-8-sig")
pd.read_excel("SIMULATION_echantillon_synthetique.xlsx", sheet_name="Données", header=2)
```
