"""Génération d'un échantillon synthétique conforme au questionnaire original (Q1–Q15, voir
survey_config.py). Q5–Q8 et Q13–Q15 ont 8 modalités distinctes ; Q9–Q12 en ont 5.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from survey_config import (ALL_QS, MODE_FILTRE, QUESTIONNAIRE_VERSION, QUESTIONS, is_applicable)

PROFILS = ["Appétence faible", "Appétence intermédiaire", "Appétence élevée"]
PROFIL_COL = "Profil_latent_simulé"
STATUTS = ["répondu", "non_applicable", "manquant"]

# Facteur de passage d'une échelle 1–6 (ancienne version) à une échelle 1–8 (questionnaire original) :
# new = 1 + (old - 1) * K8. Appliqué aux moyennes et aux écarts-types des questions à 8 modalités, pour
# que leur dispersion occupe proportionnellement la même place dans leur échelle qu'une échelle à 6
# niveaux l'aurait fait. Les coefficients appliqués à des entrées elles-mêmes non rescalées (trait
# latent L, niveau d'études) sont multipliés par K8 ; les coefficients reliant deux questions à 8
# modalités entre elles (ex. Q7 dépend de Q5) restent inchangés à condition d'utiliser la nouvelle
# moyenne de la question source (voir le calcul ci-dessous).
K8 = 7 / 5

# Identifiant du MODÈLE de génération (algorithme de simulate()), distinct de QUESTIONNAIRE_VERSION
# (qui identifie la structure du questionnaire). Change si la mécanique de tirage change (nouvelles
# variables latentes, nouvelle formule...), même si le questionnaire modélisé reste identique.
GENERATOR_VERSION = "GEN_LATENT_K8_V1"


@dataclass
class SimParams:
    n: int = 100
    seed: int = 42
    taux_usage: float = 0.80                 # cible pour Q1 = Oui
    age_weights: tuple = (0.10, 0.62, 0.20, 0.08)   # normalisés à la génération
    genre_weights: tuple = (0.46, 0.48, 0.03, 0.03)
    taux_manquants: float = 0.02             # non-réponse accidentelle, par cellule applicable (Q2–Q15)
    force_latent: float = 1.0                # multiplie le lien du trait latent avec Q5, Q7, Q9, Q12–Q15
    lien_q10_latent: float = 0.0             # DÉSACTIVÉ par défaut : aucune association imposée
    lien_q10_age: float = 0.0                # DÉSACTIVÉ par défaut
    filter_mode: str = MODE_FILTRE           # "simulation_filtree" ou "sans_branchement"
    version: str = QUESTIONNAIRE_VERSION     # identifiant de la structure du questionnaire modélisée
    model_version: str = GENERATOR_VERSION   # identifiant de l'algorithme de génération (simulate())


NIVEAU_P = {1: (0.95, 0.05, 0, 0), 2: (0.45, 0.35, 0.18, 0.02),
            3: (0.10, 0.25, 0.45, 0.20), 4: (0.03, 0.12, 0.40, 0.45)}  # P(niveau | âge)


def _norm(p):
    p = np.asarray(p, float)
    return p / p.sum()


def expected_distributions(p: SimParams) -> dict:
    """Probabilités définies par les paramètres (marginales), par question catégorielle.

    Q1 : taux visé ; Q4 : marginale de P(niveau | âge) pondérée par la répartition d'âge.
    """
    age = _norm(p.age_weights)
    niv = sum(w * _norm(NIVEAU_P[a + 1]) for a, w in enumerate(age))
    return {"Q1": [p.taux_usage, 1 - p.taux_usage], "Q2": list(age),
            "Q3": list(_norm(p.genre_weights)), "Q4": list(niv)}


def _calibrate_intercept(z0, target):
    """Décalage b tel que moyenne(sigmoïde(z0 + b)) = target (la probabilité moyenne vaut le taux visé)."""
    lo, hi = -40.0, 40.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if np.mean(1 / (1 + np.exp(-(z0 + mid)))) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _choice(rng, p, n):
    p = np.asarray(p, float)
    return rng.choice(len(p), size=n, p=p / p.sum()) + 1


def _lik(rng, mu, signal, noise, levels):
    """Tire une réponse ordinale 1..levels : valeur latente continue (moyenne + signal + bruit),
    arrondie puis bornée. Toutes les modalités autorisées restent atteignables (la probabilité
    décroît dans les extrémités mais n'est jamais nulle), sans qu'elles apparaissent forcément dans
    un petit échantillon."""
    raw = mu + signal + rng.normal(0, noise, size=len(signal))
    return np.clip(np.rint(raw), 1, levels).astype(int)


def simulate(params: SimParams | None = None) -> pd.DataFrame:
    """DataFrame de codes numériques ; NaN = non applicable (selon le mode) OU manquant (voir
    `status_frame`). Mêmes graine + paramètres + version → mêmes données."""
    p = params or SimParams()
    rng = np.random.default_rng(p.seed)
    n, f = p.n, p.force_latent

    age = _choice(rng, p.age_weights, n)
    niveau = np.array([_choice(rng, NIVEAU_P[a], 1)[0] for a in age])
    genre = _choice(rng, p.genre_weights, n)

    L = rng.normal(0, 1, n)  # trait latent « appétence pour l'IA » (construction de la simulation)

    z0 = 0.9 * L + 0.15 * (niveau - 2.5) - 0.2 * (age == 1)
    u = rng.random(n)  # tiré dans tous les cas : le flux aléatoire reste identique
    if p.taux_usage <= 0:
        q1 = np.full(n, 2)
    elif p.taux_usage >= 1:
        q1 = np.full(n, 1)
    else:
        prob = 1 / (1 + np.exp(-(z0 + _calibrate_intercept(z0, p.taux_usage))))
        q1 = np.where(u < prob, 1, 2)  # 1 = Oui, 2 = Non

    # --- Q5–Q8, Q13–Q15 : 8 modalités distinctes (voir K8 ci-dessus pour la logique de rescale) ---
    MU5, MU6, MU7, MU8 = 1 + 2.9 * K8, 1 + 2.6 * K8, 1 + 2.7 * K8, 1 + 3.0 * K8
    MU13, MU14, MU15 = 1 + 2.9 * K8, 1 + 2.5 * K8, 1 + 2.8 * K8
    q5 = _lik(rng, MU5, 0.9 * K8 * f * L, 0.9 * K8, 8)
    q6 = _lik(rng, MU6, 0.5 * K8 * f * L, 0.9 * K8, 8)
    q7 = _lik(rng, MU7, 0.6 * K8 * f * L + 0.3 * (q5 - MU5), 0.8 * K8, 8)
    q8 = _lik(rng, MU8, 0.3 * K8 * (niveau - 2.5), 1.0 * K8, 8)
    q13 = _lik(rng, MU13, 0.6 * K8 * f * L, 1.0 * K8, 8)
    q14 = _lik(rng, MU14, 0.5 * K8 * f * L, 1.0 * K8, 8)
    q15 = _lik(rng, MU15, 0.6 * K8 * f * L, 1.0 * K8, 8)

    # --- Q9–Q12 : 5 modalités d'accord, inchangées ----------------------------------------------
    q9 = _lik(rng, 3.4, 0.8 * f * L + 0.3 * (q5 - MU5), 0.7, 5)
    q10 = _lik(rng, 3.8, p.lien_q10_latent * L + p.lien_q10_age * (age - 2.5), 1.0, 5)
    q11 = _lik(rng, 3.6, 0 * L, 1.0, 5)  # indépendante du trait latent
    q12 = _lik(rng, 3.3, 0.7 * f * L, 0.8, 5)

    df = pd.DataFrame({"ID": [f"SYN-{i:03d}" for i in range(1, n + 1)],
                       "Q1": q1, "Q2": age, "Q3": genre, "Q4": niveau, "Q5": q5, "Q6": q6,
                       "Q7": q7, "Q8": q8, "Q9": q9, "Q10": q10, "Q11": q11, "Q12": q12,
                       "Q13": q13, "Q14": q14, "Q15": q15})
    df[ALL_QS] = df[ALL_QS].astype(float)

    applicable = pd.DataFrame({q: is_applicable(q, df["Q1"], p.filter_mode) for q in ALL_QS})
    df = df.mask(~applicable.reindex(columns=df.columns, fill_value=True))  # non applicable → NaN
    for q in ALL_QS[1:]:  # non-réponse accidentelle (Q1 jamais manquante)
        hit = applicable[q] & (rng.random(n) < p.taux_manquants)
        df.loc[hit, q] = np.nan

    df[PROFIL_COL] = pd.Categorical(
        np.select([L < -0.5, L > 0.6], [PROFILS[0], PROFILS[2]], PROFILS[1]), categories=PROFILS)
    df["Source"] = "SIMULATION"
    return df


# ------------------------------------------------------------------------- liens programmés
# Décrit, pour chaque question à 5/8 niveaux, comment son signal est construit dans simulate() :
# coefficient du trait latent L (fonction des paramètres), et dépendances directes à d'autres
# questions déjà tirées. Sert uniquement à expliquer d'où peuvent venir des corrélations observées.
# Les coefficients ci-dessous sont ceux réellement appliqués dans simulate() (K8 déjà inclus pour les
# questions à 8 modalités) : aucune duplication de constantes « magiques » ailleurs dans le code.
def _latent_coef(p: SimParams) -> dict:
    f = p.force_latent
    return {"Q5": 0.9 * K8 * f, "Q6": 0.5 * K8 * f, "Q7": 0.6 * K8 * f, "Q8": 0.0, "Q9": 0.8 * f,
            "Q10": p.lien_q10_latent, "Q11": 0.0, "Q12": 0.7 * f, "Q13": 0.6 * K8 * f,
            "Q14": 0.5 * K8 * f, "Q15": 0.6 * K8 * f}


DIRECT_LINKS = {"Q7": [("Q5", 0.3)], "Q9": [("Q5", 0.3)]}  # dépendance directe à la valeur tirée de Q5
NIVEAU_LINKS = {"Q8": 0.3 * K8}  # dépend du niveau d'études, pas du trait latent
AGE_LINKS_FN = {"Q10": lambda p: p.lien_q10_age}  # 0 par défaut


def programmed_link_note(qa: str, qb: str, params: SimParams) -> str:
    """Explique, à partir des coefficients réellement utilisés par `params`, pourquoi deux questions
    pourraient être corrélées (facteur latent commun, dépendance directe) ou non. Ne recherche ni ne
    promet aucune corrélation précise : décrit seulement la construction du modèle.
    """
    lat = _latent_coef(params)
    la, lb = lat.get(qa, 0.0), lat.get(qb, 0.0)
    bits = []
    if abs(la) > 1e-9 and abs(lb) > 1e-9:
        sens = "dans le même sens" if la * lb > 0 else "en sens opposés"
        bits.append(f"{qa} et {qb} chargent toutes les deux sur le trait latent « appétence pour "
                    f"l'IA » de la simulation (coefficients {la:+.2f} et {lb:+.2f}, {sens}) : une partie "
                    f"d'une éventuelle corrélation vient de ce facteur commun, pas d'un lien entre elles.")
    for x, y in ((qa, qb), (qb, qa)):
        for dep, coef in DIRECT_LINKS.get(x, []):
            if dep == y:
                bits.append(f"{x} dépend directement de la valeur tirée pour {y} dans la génération "
                            f"(coefficient {coef:+.2f}).")
    for q, coef in NIVEAU_LINKS.items():
        if q in (qa, qb):
            bits.append(f"{q} dépend du niveau d'études simulé (coefficient {coef:+.2f}), pas du trait "
                        f"latent ni directement de l'autre question.")
    for q, fn in AGE_LINKS_FN.items():
        if q in (qa, qb) and abs(fn(params)) > 1e-9:
            bits.append(f"{q} dépend aussi de l'âge simulé dans ce réglage (coefficient {fn(params):+.2f}).")
    if not bits:
        return (f"Aucun lien programmé n'a été identifié entre {qa} et {qb} dans la configuration "
                f"actuelle du modèle. Cela ne garantit pas leur indépendance : une corrélation peut "
                f"apparaître par hasard d'échantillonnage, surtout avec un petit effectif.")
    bits.append("L'absence d'autres liens programmés ne garantit pas l'indépendance du reste : le "
                "hasard d'échantillonnage peut aussi produire une corrélation apparente.")
    return " ".join(bits)


def status_frame(df: pd.DataFrame, mode: str = MODE_FILTRE) -> pd.DataFrame:
    """Statut de chaque cellule : répondu / non_applicable / manquant, selon le mode de filtrage
    (« simulation_filtree » ou « sans_branchement » — voir survey_config.is_applicable)."""
    out = {}
    for q in ALL_QS:
        applicable = is_applicable(q, df["Q1"], mode)
        out[q] = np.where(~applicable, "non_applicable",
                          np.where(df[q].isna(), "manquant", "répondu"))
    return pd.DataFrame(out, index=df.index)


def check_reproducible(params: SimParams) -> bool:
    """Reproduit réellement la génération (mêmes graine + paramètres + versions) et compare, plutôt
    que de supposer la reproductibilité du générateur."""
    return simulate(params).equals(simulate(params))


def check_full_range(params: SimParams, n_big: int = 20000) -> dict:
    """Vérifie, sur un tirage indépendant et volontairement grand (n_big), que le générateur AUTORISE
    bien chaque code 1..levels pour chaque question à échelle — y compris les extrémités (codes 1 et
    8, ou 1 et 5). N'utilise jamais l'échantillon actif pour cette vérification : l'absence d'un code
    extrême dans un petit échantillon ne serait pas une preuve que le générateur l'interdit.
    """
    from dataclasses import replace
    big = simulate(replace(params, n=n_big, taux_manquants=0.0, seed=params.seed + 999_983))
    out = {}
    for q, spec in QUESTIONS.items():
        if spec["kind"] == "single":
            continue
        present = set(big[q].dropna().astype(int).unique())
        out[q] = {"attendu": set(range(1, spec["levels"] + 1)), "observe": present,
                  "complet": present == set(range(1, spec["levels"] + 1))}
    return out


def effectifs(df: pd.DataFrame, mode: str = MODE_FILTRE) -> pd.DataFrame:
    """Effectifs par question : posée à, répondu, non applicable, manquant."""
    st = status_frame(df, mode)
    rows = []
    for q in ALL_QS:
        c = st[q].value_counts()
        rows.append({"Question": q, "Applicable (posée à)": int(len(df) - c.get("non_applicable", 0)),
                     "Répondu (n utilisé)": int(c.get("répondu", 0)),
                     "Non applicable": int(c.get("non_applicable", 0)),
                     "Manquant (accidentel)": int(c.get("manquant", 0))})
    return pd.DataFrame(rows)
