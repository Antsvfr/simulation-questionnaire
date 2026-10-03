"""Définition du questionnaire original (Q1–Q15) : modalités, codes, filtres — source unique de vérité.

Cette configuration correspond exactement au questionnaire fourni par l'utilisateur (export Qualtrics
à 8 modalités distinctes pour Q5–Q8 et Q13–Q15, 5 modalités pour Q9–Q12). Elle est utilisée par la
génération, l'affichage, les analyses et les exports : rien n'est redéfini ailleurs.
"""

# Identifiant de version du questionnaire modélisé. Change si la structure des questions change
# (nombre de modalités, questions ajoutées/retirées...). Sert à détecter un échantillon généré sous
# une version incompatible (voir app.py) pour ne jamais réinterpréter silencieusement d'anciennes
# données à 6 niveaux comme des données à 8 niveaux.
QUESTIONNAIRE_VERSION = "IA_ORIGINAL_15Q_8MOD"

BANNER = (
    "DONNÉES SYNTHÉTIQUES — SIMULATION PÉDAGOGIQUE — "
    "AUCUNE RÉPONSE RÉELLEMENT COLLECTÉE"
)

# --- Modes de filtrage (section « Parcours et réponses non applicables ») --------------------
# Le texte du questionnaire fourni ne prouve aucun branchement Qualtrics réel. Les deux modes ci-
# dessous sont donc proposés explicitement, au choix, plutôt que présentés comme la vérité du
# questionnaire original.
MODE_FILTRE = "simulation_filtree"       # conventions actuelles du simulateur (certaines Q exclues)
MODE_LIBRE = "sans_branchement"          # toutes les questions posées à tous, sans exception
FILTER_MODES = [MODE_FILTRE, MODE_LIBRE]
FILTER_MODE_LABELS = {
    MODE_FILTRE: "Simulation avec filtres (conventions actuelles du simulateur)",
    MODE_LIBRE: "Questionnaire sans branchement (toutes les questions à tous les profils)",
}

# --- Questions catégorielles : codes 1..n dans l'ordre indiqué -------------------------------
Q1_OPTIONS = ["Oui", "Non"]
Q2_OPTIONS = ["Moins de 18 ans", "18–24 ans", "25–34 ans", "35 ans et plus"]
Q3_OPTIONS = ["Homme", "Femme", "Autre", "Préfère ne pas répondre"]
Q4_OPTIONS = ["Bac / L1-L2", "Licence (L3)", "Master", "Doctorat / Autre"]

# --- Échelle d'accord à 5 modalités (Q9–Q12), telle que fournie -------------------------------
AGREE5 = {1: "Pas du tout d'accord", 2: "Plutôt pas d'accord", 3: "Neutre",
          4: "Plutôt d'accord", 5: "Tout à fait d'accord"}


def _s8(low: str, high: str) -> dict:
    """Échelle à 8 modalités DISTINCTES, conforme à l'export Qualtrics original : le code 1 et le
    code 8 portent les ancrages textuels fournis ; les codes 2 à 7 portent les libellés numériques
    « 1 » à « 6 » utilisés tels quels dans le questionnaire (ce ne sont pas des échelles à 6 niveaux
    rhabillées : il y a bien 8 choix sélectionnables)."""
    return {1: low, 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: high}


# asked : "all" (posée à tous, mode "simulation_filtree") ou "users" (posée si Q1 = Oui, mode
#         "simulation_filtree" seulement — en mode "sans_branchement" toutes les questions sont
#         posées à tous, voir is_applicable()).
# rule  : "definie" = règle de non-applicabilité définie pour cette simulation (pas une exigence du
#         professeur) ; "convention" = autre choix de la simulation (None pour les questions posées à
#         tous). Aucun branchement Qualtrics n'a été vérifié : voir le mode « sans branchement ».
QUESTIONS = {
    "Q1": dict(label="Utilisez-vous l'IA dans le cadre de vos études ?", kind="single",
               options=Q1_OPTIONS, asked="all"),
    "Q2": dict(label="Quel est votre âge ?", kind="single", options=Q2_OPTIONS, asked="all"),
    "Q3": dict(label="Quel est votre genre ?", kind="single", options=Q3_OPTIONS, asked="all"),
    "Q4": dict(label="Quel est votre niveau d'études actuel ?", kind="single", options=Q4_OPTIONS,
               asked="all"),
    "Q5": dict(label="L'IA vous semble améliorer votre apprentissage :", kind="scale", levels=8,
               anchors=_s8("Pas du tout", "Énormément"), asked="users", rule="convention"),
    "Q6": dict(label="Les réponses fournies par l'IA vous semblent :", kind="scale", levels=8,
               anchors=_s8("Très peu fiables", "Très fiables"), asked="all", rule=None),
    "Q7": dict(label="L'utilisation de l'IA pour comprendre un cours vous semble :", kind="scale",
               levels=8, anchors=_s8("Très inefficace", "Très efficace"), asked="users",
               rule="convention"),
    "Q8": dict(label="À quel point faites-vous confiance à votre propre jugement lorsque vous "
                     "utilisez une réponse générée par l'IA ?", kind="scale", levels=8,
               anchors=_s8("Très peu", "Totalement"), asked="users", rule="definie"),
    "Q9": dict(label="« L'utilisation de l'IA améliore la qualité de mon travail scolaire. »",
               kind="agree", levels=5, anchors=AGREE5, asked="users", rule="definie"),
    "Q10": dict(label="« Les établissements d'enseignement devraient encadrer l'utilisation "
                      "de l'IA. »", kind="agree", levels=5, anchors=AGREE5, asked="all", rule=None),
    "Q11": dict(label="« J'ai tendance à vérifier les informations fournies par une IA avant "
                      "de les utiliser. »", kind="agree", levels=5, anchors=AGREE5,
                asked="users", rule="definie"),
    "Q12": dict(label="« L'IA m'aide à devenir plus autonome dans mes études. »",
                kind="agree", levels=5, anchors=AGREE5, asked="users", rule="definie"),
    "Q13": dict(label="Pour vous, l'impact de l'IA sur la créativité est :", kind="scale", levels=8,
                anchors=_s8("Réducteur", "Stimulant"), asked="all", rule=None),
    "Q14": dict(label="Pour vous, l'impact de l'IA sur l'esprit critique est :", kind="scale",
                levels=8, anchors=_s8("Négatif", "Positif"), asked="all", rule=None),
    "Q15": dict(label="Pour vous, l'utilisation de l'IA pour recevoir des explications sur un "
                      "cours est :", kind="scale", levels=8,
                anchors=_s8("Impersonnelle", "Personnalisée"), asked="all", rule=None),
}

# Texte intégral identique au libellé pour toutes les questions : ce questionnaire fournit la
# formulation complète de chacune (contrairement à une version antérieure où seuls Q9–Q15 avaient
# un texte distinct de l'intitulé court).
for _q, _d in QUESTIONS.items():
    _d["text"] = _d["label"]
    _d["text_is_title"] = False

ALL_QS = list(QUESTIONS)
CATEGORICAL = [q for q, d in QUESTIONS.items() if d["kind"] == "single"]
SCALE_QS = [q for q, d in QUESTIONS.items() if d["kind"] != "single"]
SCALE8_QS = [q for q in SCALE_QS if QUESTIONS[q]["levels"] == 8]
AGREE_QS = [q for q in SCALE_QS if QUESTIONS[q]["levels"] == 5]


SHORT_HDR = {"Q1": "Utilise l'IA", "Q2": "Âge", "Q3": "Genre", "Q4": "Niveau d'études",
             "Q5": "Amélioration apprentissage", "Q6": "Fiabilité réponses", "Q7": "Efficacité cours",
             "Q8": "Confiance jugement", "Q9": "IA améliore travail", "Q10": "Encadrement",
             "Q11": "Vérification infos", "Q12": "Autonomie", "Q13": "Créativité",
             "Q14": "Esprit critique", "Q15": "Explications cours"}


def scale_help(q: str) -> str:
    """Texte d'aide : question complète + toutes les modalités (aucune n'est inventée)."""
    spec = QUESTIONS[q]
    if spec["kind"] == "single":
        return f"{spec['text']} — Modalités : " + " / ".join(spec["options"])
    labs = " ; ".join(f"{k} = {v}" for k, v in spec["anchors"].items())
    return f"{spec['text']} — {spec['levels']} modalités distinctes ({labs})"


def short(q: str) -> str:
    return f"{q} — {QUESTIONS[q]['label']}"


# Regroupement du sélecteur de question (section « Analyse par question »).
GROUPS = [
    ("Profil et usage", ["Q1", "Q2", "Q3", "Q4"]),
    ("Apprentissage et confiance", ["Q5", "Q6", "Q7", "Q8", "Q9"]),
    ("Encadrement, vérification et autonomie", ["Q10", "Q11", "Q12"]),
    ("Créativité, esprit critique et personnalisation", ["Q13", "Q14", "Q15"]),
]


def group_of(q: str) -> str:
    return next(name for name, qs in GROUPS if q in qs)


def is_user_only(q: str) -> bool:
    """True si la question n'est posée qu'aux utilisateurs de l'IA (Q1 = Oui), en mode filtré.

    En mode « sans branchement », aucune question n'est exclue : voir is_applicable().
    """
    return QUESTIONS[q]["asked"] == "users"


EXPERIENCE_QS = [q for q in ALL_QS if is_user_only(q)]  # Q5, Q7, Q8, Q9, Q11, Q12

HYPOTHETICAL_NOTE = (
    "Mode « Questionnaire sans branchement » : toutes les questions sont posées à tous les profils, "
    "y compris " + ", ".join(EXPERIENCE_QS) + " aux non-utilisateurs de l'IA (Q1 = Non). Pour ces "
    "profils, les réponses à ces questions d'expérience avec l'IA sont hypothétiques — un non-"
    "utilisateur répond quand même à une question qui suppose un usage — et doivent être lues avec "
    "cette réserve méthodologique, pas comme un vécu réel.")


def is_applicable(q: str, q1_codes, mode: str = MODE_FILTRE):
    """Série booléenne : la question q est-elle posée au répondant (selon Q1 et le mode) ?

    Mode « sans_branchement » : toujours applicable (aucune question exclue). Mode
    « simulation_filtree » : comportement conventionnel actuel du simulateur (voir filters_table).
    """
    if mode == MODE_LIBRE:
        return q1_codes.notna() & True
    if QUESTIONS[q]["asked"] == "all":
        return q1_codes.notna() & True
    return q1_codes == 1


def codebook():
    rows = []
    for q, d in QUESTIONS.items():
        if d["kind"] == "single":
            rows += [(q, d["label"], i, lab) for i, lab in enumerate(d["options"], 1)]
        else:
            rows += [(q, d["label"], c, d["anchors"].get(c, "")) for c in range(1, d["levels"] + 1)]
    return rows


def filters_table(mode: str = MODE_FILTRE, df=None):
    """Quelles questions sont exclues pour qui, dans le mode donné, et pourquoi — jamais présenté
    comme un branchement Qualtrics prouvé (le texte du questionnaire ne le démontre pas).

    Avec `df` (l'échantillon actif), ajoute le nombre réel de profils concernés par l'exclusion,
    plutôt qu'une description abstraite.
    """
    def n_non_users():
        if df is None or "Q1" not in df:
            return None
        return int((df["Q1"] == 2).sum())

    if mode == MODE_LIBRE:
        return [(q, "Tous les répondants", "Mode « sans branchement » : aucune question exclue "
                "— voir la réserve sur les réponses hypothétiques", "—") for q in QUESTIONS]
    out = []
    for q, d in QUESTIONS.items():
        if d["asked"] == "all":
            out.append((q, "Tous les répondants", "—", 0))
        else:
            n = n_non_users()
            detail = (f"Convention de simulation : exclut les {n} profil(s) non-utilisateurs de "
                     f"l'IA (Q1 = Non) de cet échantillon" if n is not None else
                     "Convention de simulation : exclut les profils non-utilisateurs de l'IA (Q1 = Non)")
            out.append((q, "Utilisateurs (Q1 = Oui)",
                        detail + " ; non vérifiée dans Qualtrics (le texte du questionnaire ne "
                        "prouve aucun branchement réel).", n if n is not None else "—"))
    return out
