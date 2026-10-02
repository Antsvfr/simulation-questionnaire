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
# rule  : "minimum" = non-applicabilité exigée par la consigne ; "convention" = choix de la simulation
#         (None pour les questions posées à tous). Aucun branchement Qualtrics n'a été vérifié.
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
               asked="users", rule="minimum"),
    "Q9": dict(label="« L'utilisation de l'IA améliore la qualité de mon travail scolaire. »",
               kind="agree", levels=5, anchors=AGREE5, asked="users", rule="minimum"),
    "Q10": dict(label="« Les établissements d'enseignement devraient encadrer l'utilisation "
                      "de l'IA. »", kind="agree", levels=5, anchors=AGREE5, asked="all", rule=None),
    "Q11": dict(label="« J'ai tendance à vérifier les informations fournies par une IA avant "
                      "de les utiliser. »", kind="agree", levels=5, anchors=AGREE5,
                asked="users", rule="minimum"),
    "Q12": dict(label="« L'IA m'aide à devenir plus autonome dans mes études. »",
                kind="agree", levels=5, anchors=AGREE5, asked="users", rule="minimum"),
    "Q13": dict(label="Impact de l'IA sur la créativité", kind="scale", levels=6,
                anchors=_s6("Réducteur", "Stimulant"), asked="all", rule=None),
    "Q14": dict(label="Impact de l'IA sur l'esprit critique", kind="scale", levels=6,
                anchors=_s6("Négatif", "Positif"), asked="all", rule=None),
    "Q15": dict(label="Utilisation de l'IA pour recevoir des explications sur un cours",
                kind="scale", levels=6, anchors=_s6("Impersonnelle", "Personnalisée"),
                asked="all", rule=None),
}

ALL_QS = list(QUESTIONS)
CATEGORICAL = [q for q, d in QUESTIONS.items() if d["kind"] == "single"]
SCALE_QS = [q for q, d in QUESTIONS.items() if d["kind"] != "single"]
SCALE6_QS = [q for q in SCALE_QS if QUESTIONS[q]["levels"] == 6]
AGREE_QS = [q for q in SCALE_QS if QUESTIONS[q]["levels"] == 5]


def short(q: str) -> str:
    return f"{q} — {QUESTIONS[q]['label']}"


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
        elif d["rule"] == "minimum":
            out.append((q, "Utilisateurs (Q1 = Oui)", "Minimum exigé par la consigne"))
        else:
            out.append((q, "Utilisateurs (Q1 = Oui)",
                        "Convention de la simulation (non vérifiée dans Qualtrics)"))
    return out
