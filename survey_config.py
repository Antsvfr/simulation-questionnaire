"""Définition du questionnaire (modalités et codes) — source unique de vérité."""

BANNER = (
    "DONNÉES SYNTHÉTIQUES — SIMULATION PÉDAGOGIQUE — "
    "AUCUNE RÉPONSE RÉELLEMENT COLLECTÉE"
)

NSP = "Non applicable (filtre)"  # libellé utilisé dans les exports pour les questions non posées

# --- Questions catégorielles : codes 1..n dans l'ordre indiqué -------------------------------
Q1_OPTIONS = ["Oui", "Non"]
Q2_OPTIONS = ["Moins de 18 ans", "18–24 ans", "25–34 ans", "35 ans et plus"]
Q3_OPTIONS = ["Homme", "Femme", "Autre", "Préfère ne pas répondre"]
Q4_OPTIONS = ["Bac / L1-L2", "Licence (L3)", "Master", "Doctorat / Autre"]

# --- Échelles 1–6 -----------------------------------------------------------------------------
LIKERT_ACCORD = {
    1: "Pas du tout d'accord", 2: "Plutôt pas d'accord", 3: "Un peu pas d'accord",
    4: "Un peu d'accord", 5: "Plutôt d'accord", 6: "Tout à fait d'accord",
}


def _anchored(low: str, high: str) -> dict:
    return {1: low, 6: high}


QUESTIONS = {
    "Q1": dict(label="Utilisation de l'IA dans les études", kind="single",
               options=Q1_OPTIONS, asked="all"),
    "Q2": dict(label="Âge", kind="single", options=Q2_OPTIONS, asked="all"),
    "Q3": dict(label="Genre", kind="single", options=Q3_OPTIONS, asked="all"),
    "Q4": dict(label="Niveau d'études", kind="single", options=Q4_OPTIONS, asked="all"),
    "Q5": dict(label="Amélioration perçue de l'apprentissage", kind="scale",
               anchors=_anchored("Pas du tout", "Énormément"), asked="users"),
    "Q6": dict(label="Fiabilité perçue des réponses", kind="scale",
               anchors=_anchored("Très peu fiables", "Très fiables"), asked="users"),
    "Q7": dict(label="Efficacité pour comprendre un cours", kind="scale",
               anchors=_anchored("Très inefficace", "Très efficace"), asked="users"),
    "Q8": dict(label="Confiance dans son propre jugement face à une réponse d'IA",
               kind="scale", anchors=_anchored("Très peu", "Totalement"), asked="users"),
    "Q9": dict(label="« L'utilisation de l'IA améliore la qualité de mon travail scolaire. »",
               kind="likert", anchors=LIKERT_ACCORD, asked="users"),
    # Énoncé tronqué dans la demande initiale : complété de façon vraisemblable (voir README).
    "Q10": dict(label="« Les établissements d'enseignement devraient encadrer "
                      "l'utilisation de l'IA. »",
                kind="likert", anchors=LIKERT_ACCORD, asked="all"),
}

CATEGORICAL = [q for q, d in QUESTIONS.items() if d["kind"] == "single"]
SCALE_QS = [q for q, d in QUESTIONS.items() if d["kind"] in ("scale", "likert")]
LIKERT_QS = ["Q9", "Q10"]


def short(q: str) -> str:
    return f"{q} — {QUESTIONS[q]['label']}"


def codebook():
    """Dictionnaire des codes : une ligne par (question, code)."""
    rows = []
    for q, d in QUESTIONS.items():
        if d["kind"] == "single":
            for i, lab in enumerate(d["options"], 1):
                rows.append((q, d["label"], i, lab))
        else:
            for c in range(1, 7):
                rows.append((q, d["label"], c, d["anchors"].get(c, "")))
    return rows
