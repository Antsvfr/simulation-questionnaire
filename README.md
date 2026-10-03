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

## Navigation

Six sections, sélectionnées par les boutons en haut de page :

| Section | Contenu |
|---|---|
| 🏠 Vue d'ensemble | Indicateurs clés (avec aide contextuelle), composition compacte, description calculée, liens rapides |
| 🧑‍🤝‍🧑 Échantillon | *Composition* (effectifs/% par âge, genre, niveau, usage + proportions théoriques séparées) et *Réponses individuelles* (tableau Q1–Q15, tri, lisible/codes, fiche d'un profil) |
| ❓ Analyse par question | Une question à la fois (texte complet, n valides/manquants/NA, distribution, tableau exact, aide à la lecture) |
| 🔀 Comparaisons | Une question × un regroupement (âge/genre/niveau/usage), barres à 100 %, tableau croisé, petits effectifs signalés |
| 🔗 Relations entre réponses | Corrélation de Spearman entre deux échelles, tableau croisé, explication du signe, liens programmés réels, matrice globale en option |
| 📦 Exports et méthode | Trois exports séparés (échantillon complet / sélection filtrée / tableau de l'analyse courante) + méthode et limites |

Les **filtres globaux** (recherche, âge, genre, niveau, usage de l'IA, complet/incomplet) sont dans la barre
latérale, toujours visibles, et s'appliquent à toutes les sections et à tous les exports : « X profils
sélectionnés sur N » et un bouton « Réinitialiser les filtres » sont toujours affichés.

## Fonctionnement de l'échantillon

- L'échantillon est conservé dans `st.session_state` avec **les paramètres exacts de sa génération**.
  Changer de section, filtrer, trier ou télécharger ne le régénère jamais.
- Les réglages de génération sont dans le panneau replié **« ⚙️ Configurer la simulation »** (barre latérale).
  Les modifier affiche « modifications non appliquées » tant qu'aucun bouton n'a été cliqué.
- **🔁 Reproduire avec cette graine** : régénère avec les réglages et la graine saisis (mêmes paramètres +
  même graine = mêmes données). **🎲 Générer un nouvel échantillon** : tire et affiche une nouvelle graine.

## Questionnaire

Conforme exactement au questionnaire original fourni (identifiant de version **`IA_ORIGINAL_15Q_8MOD`**,
affiché dans la barre latérale et dans chaque export) :

| Q | Échelle |
|---|---|
| Q1–Q4 | Catégorielles, codes 1…n dans l'ordre des modalités |
| Q5–Q8, Q13–Q15 | **8 modalités distinctes** (pas 6) : code 1 et code 8 = ancrages du questionnaire (ex. « Pas du tout » / « Énormément ») ; codes 2 à 7 = libellés numériques « 1 » à « 6 » utilisés tels quels |
| Q9–Q12 | Accord à 5 niveaux : 1 Pas du tout d'accord · 2 Plutôt pas d'accord · 3 Neutre · 4 Plutôt d'accord · 5 Tout à fait d'accord |

Les questions à 5 et à 8 modalités sont toujours présentées séparément (couleurs, graphiques, aucune moyenne
commune). **Aucun score global n'est calculé sur Q9–Q12**. **Q8 n'est jamais recodée en binaire** (ce n'est pas
une variable Oui/Non) ; une variable dérivée **`Q1_binaire`** (Oui=1, Non=0) est proposée dans les exports
« codes », en plus de Q1 d'origine. **Aucun test d'attention** n'existe dans ce questionnaire : l'application
l'indique explicitement et ne calcule ni résultat de réussite/échec ni exclusion de profil pour ce motif.

### Compatibilité de version

Si un échantillon a été généré sous une structure différente (p. ex. une version antérieure à 6 niveaux), il
n'est **jamais** réinterprété silencieusement sous la structure actuelle : l'application affiche une erreur
explicite, conserve l'ancien échantillon de côté (consultable, non utilisé) et exige un clic explicite sur
« Générer un nouvel échantillon » avant de continuer.

## Deux modes de parcours (barre latérale → Configurer la simulation)

Le texte du questionnaire fourni ne prouve aucun branchement Qualtrics réel : deux modes sont donc proposés
explicitement, jamais mélangés dans un même échantillon (le mode actif est affiché, enregistré avec les
paramètres et dans chaque export) :

- **Simulation avec filtres** (par défaut) : conventions actuelles du simulateur — certaines questions
  d'expérience (Q5, Q7, Q8, Q9, Q11, Q12) sont exclues (non applicables) pour les non-utilisateurs de l'IA.
- **Questionnaire sans branchement** : toutes les questions sont posées à tous les profils, y compris aux
  non-utilisateurs. Leurs réponses à ces questions d'expérience sont alors **hypothétiques** — un bandeau le
  rappelle sur chaque page et dans la méthode.

## Non applicable ≠ manquant

- **Non applicable** : question non posée à ce répondant (uniquement en mode « simulation avec filtres »).
- **Manquant** : non-réponse accidentelle simulée (paramètre, 2 % par défaut, sur les cellules applicables).
- Dans les codes, les deux sont des cellules vides ; les colonnes `Qx_statut` (`répondu` / `non_applicable` /
  `manquant`) les distinguent. L'application affiche le *n utilisé* partout et un tableau d'effectifs. Aucune
  modalité « Je ne sais pas » n'est ajoutée (absente du questionnaire original).

### Filtres (mode « simulation avec filtres », non-utilisateurs : Q1 = Non)
Toutes les exclusions sont des **conventions de simulation** (jamais une exigence du professeur, jamais un
branchement Qualtrics vérifié) : Q8, Q9, Q11, Q12, Q5 et Q7 sont réservées aux utilisateurs ; Q6, Q10, Q13,
Q14, Q15 posées à tous. Ces choix sont modifiables dans `survey_config.py` (`asked`/`rule`). Le détail,
avec le nombre réel de profils concernés par chaque exclusion, est dans le dictionnaire exporté et dans
« Exports et méthode » → *Mode de parcours et règles de non-applicabilité*.

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

Trois blocs séparés dans « 📦 Exports et méthode » : **échantillon complet**, **sélection filtrée**, et **tableau
de l'analyse courante** (le dernier tableau consulté dans Analyse par question, Comparaisons ou Relations entre
réponses). Les deux premiers : CSV lisible, CSV codes + statuts, Excel (8 feuilles, voir ci-dessous) et JSON.
Noms de fichier `SIMULATION_SYNTHETIQUE_…` ; colonne `Origine` dans chaque ligne ; en-têtes en première ligne
(pas de ligne de commentaire) ; UTF-8 avec BOM (accents corrects dans Excel). Dans le CSV « codes », une cellule
vide = non applicable **ou** manquant : voir `Qx_statut`. Les paramètres exportés sont toujours ceux qui ont
**réellement servi à générer l'échantillon actif**, même si les réglages affichés dans l'interface ont été
modifiés depuis sans être appliqués.

### Les 8 feuilles du classeur Excel

| Feuille | Contenu |
|---|---|
| Réponses lisibles | Une ligne par profil, libellés exacts du questionnaire |
| Codes et statuts | Idem en codes numériques + `Qx_statut` + `Q1_binaire` |
| Dictionnaire | Codebook complet (question, formulation, code, libellé, type de variable), filtres décrits précisément, légende des statuts, variable dérivée |
| Composition | Effectifs/% par âge, genre, niveau, usage, avec les probabilités théoriques quand le périmètre est l'échantillon complet |
| **Paramètres** | Version du questionnaire, version du modèle de génération, graine, taille demandée/générée, mode de filtrage, taux de non-réponse, probabilités et associations réellement utilisées |
| Méthode et limites | Comment les données sont construites, et ce qu'elles ne permettent pas de conclure |
| **Contrôle de conformité** | 13 vérifications calculées sur l'échantillon actif (taille, identifiants, bornes des codes, dictionnaire complet, code 6 = libellé « 5 », cohérence valeurs/statuts, effectifs réconciliés, versions, reproductibilité, plage complète des modalités), colorées **Vert/Rouge/Gris** (vraies couleurs de cellule, pas seulement du texte) |
| **Préparation de la base** | Limites traitées honnêtement, toujours en **gris** : données manquantes avec dénominateurs explicites, absence de test d'attention, non-binarisation de Q8, absence d'indice composite Q9–Q12 |

## Contrôle de conformité

Affiché dans l'application (section Exports et méthode) et dans l'export Excel — les deux sont calculés à
l'identique sur l'échantillon actif, jamais supposés. Aucun statut n'est forcé au vert : un contrôle non
vérifiable (ex. présence des codes extrêmes dans le seul échantillon actif, par opposition à leur autorisation
par le générateur, vérifiée séparément sur un tirage indépendant de 20 000 profils) reste gris. Testé avec de
vraies anomalies injectées (doublon d'identifiant, code hors bornes, incohérence valeur/statut, taille erronée,
version incompatible) pour vérifier que chaque contrôle réagit réellement (`tests_compliance.py`).

## Validité des analyses

- Aucun score global ; Q9–Q12 (5 modalités) et Q5–Q8, Q13–Q15 (8 modalités) restent toujours séparées.
- Corrélations de Spearman sur paires complètes, uniquement entre échelles ordinales (jamais sur genre, âge, etc.) ;
  refusées si n < 10 ou variable constante (« – » affiché, motif listé) ; n par paire affiché. Les paramètres de
  génération ne sont pas réglés pour obtenir une conclusion, une corrélation précise ou un résultat significatif.
- Les réponses absentes ne sont jamais remplies : un questionnaire « complet » n'a aucune réponse accidentellement
  manquante parmi les questions applicables ; les non applicables ne comptent pas comme oubli.
- Aucun test d'attention, aucun recodage binaire de Q8, aucune variable nominale moyennée ou corrélée comme une
  échelle ordinale. Ce questionnaire sur l'IA n'a aucun lien avec une éventuelle base de satisfaction
  professionnelle L5.

## Fichiers

`survey_config.py` (questionnaire, textes, groupes, filtres) · `simulator.py` (génération, statuts, liens
programmés, vérifications de reproductibilité/plage) · `views.py` (tableaux, filtres, composition, question par
question, comparaisons, corrélations) · `compliance.py` (contrôle de conformité, préparation de la base) ·
`exports.py` (CSV/Excel/JSON) · `app.py` (interface à six sections) · `tests_*.py` (générateur/vues, exports
relus, contrôle de conformité, parcours Streamlit AppTest).

## Relire les exports

```python
pd.read_csv("SIMULATION_SYNTHETIQUE_lisibles_tout_graine42_100profils.csv", encoding="utf-8-sig")
pd.read_excel("SIMULATION_SYNTHETIQUE_classeur_tout_graine42_100profils.xlsx", sheet_name="Réponses lisibles")
pd.read_excel("SIMULATION_SYNTHETIQUE_classeur_tout_graine42_100profils.xlsx", sheet_name="Contrôle de conformité", header=2)
```
Dans l'Excel, les feuilles annexes ont le bandeau en A1 et leurs tableaux à partir de la ligne 3 (`header=2`
pour les lire avec pandas).
