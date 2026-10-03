"""Définition du questionnaire (Q1–Q15) : modalités, codes, filtres — source unique de vérité."""

BANNER = (
    "DONNÉES SYNTHÉTIQUES — SIMULATION PÉDAGOGIQUE — "
    "AUCUNE RÉPONSE RÉELLEMENT COLLECTÉE"
)

# --- Questions catégorielles : codes 1..n dans l'ordre indiqué -------------------------------
Q1_OPTIONS = ["Oui", "Non"]
Q2_OPTIONS = ["Moins de 18 ans", "18–24 ans", "25–34 ans", "35 ans et plus"]
Q3_OPTIONS = ["Homme", "Femme", "Autre", "Préfère ne pas répondre"]
Q4_OPTIONS = ["Bac / L1-L2", "Licence (L3)", "Master", "Doctorat / Autre"]

# --- Échelle d'accord à 5 modalités (Q9–Q12) -------------------------------------------------
AGREE5 = {1: "Pas du tout d'accord", 2: "Plutôt pas d'accord", 3: "Neutre",
          4: "Plutôt d'accord", 5: "Tout à fait d'accord"}


def _s6(low, high):
    """Échelle 1–6, seules les extrémités sont nommées."""
    return {1: low, 6: high}


# asked : "all" (posée à tous) ou "users" (posée si Q1 = Oui)
# rule  : "definie" = règle de non-applicabilité définie pour cette simulation (pas une exigence du
#         professeur) ; "convention" = autre choix de la simulation (None pour les questions posées à
#         tous). Aucun branchement Qualtrics n'a été vérifié.
QUESTIONS = {
    "Q1": dict(label="Utilisation de l'IA dans les études", kind="single", options=Q1_OPTIONS,
               asked="all"),
    "Q2": dict(label="Âge", kind="single", options=Q2_OPTIONS, asked="all"),
    "Q3": dict(label="Genre", kind="single", options=Q3_OPTIONS, asked="all"),
    "Q4": dict(label="Niveau d'études", kind="single", options=Q4_OPTIONS, asked="all"),
    "Q5": dict(label="Amélioration perçue de l'apprentissage", kind="scale", levels=6,
               anchors=_s6("Pas du tout", "Énormément"), asked="users", rule="convention"),
    "Q6": dict(label="Fiabilité perçue des réponses", kind="scale", levels=6,
               anchors=_s6("Très peu fiables", "Très fiables"), asked="all", rule=None),
    "Q7": dict(label="Efficacité pour comprendre un cours", kind="scale", levels=6,
               anchors=_s6("Très inefficace", "Très efficace"), asked="users", rule="convention"),
    "Q8": dict(label="Confiance dans son propre jugement face à une réponse d'IA",
               kind="scale", levels=6, anchors=_s6("Très peu", "Totalement"),
               asked="users", rule="definie"),
    "Q9": dict(label="« L'utilisation de l'IA améliore la qualité de mon travail scolaire. »",
               kind="agree", levels=5, anchors=AGREE5, asked="users", rule="definie"),
    "Q10": dict(label="« Les établissements d'enseignement devraient encadrer l'utilisation "
                      "de l'IA. »", kind="agree", levels=5, anchors=AGREE5, asked="all", rule=None),
    "Q11": dict(label="« J'ai tendance à vérifier les informations fournies par une IA avant "
                      "de les utiliser. »", kind="agree", levels=5, anchors=AGREE5,
                asked="users", rule="definie"),
    "Q12": dict(label="« L'IA m'aide à devenir plus autonome dans mes études. »",
                kind="agree", levels=5, anchors=AGREE5, asked="users", rule="definie"),
    "Q13": dict(label="Impact de l'IA sur la créativité", kind="scale", levels=6,
                anchors=_s6("Réducteur", "Stimulant"), asked="all", rule=None),
    "Q14": dict(label="Impact de l'IA sur l'esprit critique", kind="scale", levels=6,
                anchors=_s6("Négatif", "Positif"), asked="all", rule=None),
    "Q15": dict(label="Utilisation de l'IA pour recevoir des explications sur un cours",
                kind="scale", levels=6, anchors=_s6("Impersonnelle", "Personnalisée"),
                asked="all", rule=None),
}

# Texte affiché dans la fiche individuelle. Pour Q9–Q15 : formulation fournie pour le questionnaire.
# Pour Q1–Q8, seuls les intitulés ont été fournis : ils sont utilisés tels quels (text_is_title=True).
FULL_TEXT = {
    "Q9": "L'utilisation de l'IA améliore la qualité de mon travail scolaire.",
    "Q10": "Les établissements d'enseignement devraient encadrer l'utilisation de l'IA.",
    "Q11": "J'ai tendance à vérifier les informations fournies par une IA avant de les utiliser.",
    "Q12": "L'IA m'aide à devenir plus autonome dans mes études.",
    "Q13": "Pour vous, l'impact de l'IA sur la créativité est :",
    "Q14": "Pour vous, l'impact de l'IA sur l'esprit critique est :",
    "Q15": "Pour vous, l'utilisation de l'IA pour recevoir des explications sur un cours est :",
}
for _q, _d in QUESTIONS.items():
    _d["text"] = FULL_TEXT.get(_q, _d["label"])
    _d["text_is_title"] = _q not in FULL_TEXT

ALL_QS = list(QUESTIONS)
CATEGORICAL = [q for q, d in QUESTIONS.items() if d["kind"] == "single"]
SCALE_QS = [q for q, d in QUESTIONS.items() if d["kind"] != "single"]
SCALE6_QS = [q for q in SCALE_QS if QUESTIONS[q]["levels"] == 6]
AGREE_QS = [q for q in SCALE_QS if QUESTIONS[q]["levels"] == 5]


SHORT_HDR = {"Q1": "Utilise l'IA", "Q2": "Âge", "Q3": "Genre", "Q4": "Niveau d'études",
             "Q5": "Amélioration apprentissage", "Q6": "Fiabilité réponses", "Q7": "Efficacité cours",
             "Q8": "Confiance jugement", "Q9": "IA améliore travail", "Q10": "Encadrement",
             "Q11": "Vérification infos", "Q12": "Autonomie", "Q13": "Créativité",
             "Q14": "Esprit critique", "Q15": "Explications cours"}


def scale_help(q: str) -> str:
    """Texte d'aide : question complète + bornes de l'échelle (libellés présents dans le questionnaire)."""
    spec = QUESTIONS[q]
    if spec["kind"] == "single":
        return f"{spec['text']} — Modalités : " + " / ".join(spec["options"])
    anc = " ; ".join(f"{k} = {v}" for k, v in spec["anchors"].items())
    return f"{spec['text']} — Échelle 1 à {spec['levels']} ({anc})"


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
    """True si la question n'est posée qu'aux utilisateurs de l'IA (Q1 = Oui)."""
    return QUESTIONS[q]["asked"] == "users"


def is_applicable(q: str, q1_codes):
    """Série booléenne : la question q est-elle posée au répondant (selon Q1) ?"""
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


def filters_table():
    out = []
    for q, d in QUESTIONS.items():
        if d["asked"] == "all":
            out.append((q, "Tous les répondants", "—"))
        elif d["rule"] == "definie":
            out.append((q, "Utilisateurs (Q1 = Oui)", "Règle définie pour la simulation"))
        else:
            out.append((q, "Utilisateurs (Q1 = Oui)",
                        "Convention de la simulation (non vérifiée dans Qualtrics)"))
    return out
