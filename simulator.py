"""Génération d'un échantillon synthétique (Q1–Q15)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from survey_config import (ALL_QS, BANNER, CATEGORICAL, QUESTIONS, codebook, filters_table,
                           is_applicable)

PROFILS = ["Appétence faible", "Appétence intermédiaire", "Appétence élevée"]
PROFIL_COL = "Profil_latent_simulé"
STATUTS = ["répondu", "non_applicable", "manquant"]


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
    raw = mu + signal + rng.normal(0, noise, size=len(signal))
    return np.clip(np.rint(raw), 1, levels).astype(int)


def simulate(params: SimParams | None = None) -> pd.DataFrame:
    """DataFrame de codes numériques ; NaN = non applicable OU manquant (voir `status_frame`)."""
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

    q5 = _lik(rng, 3.9, 0.9 * f * L, 0.9, 6)
    q6 = _lik(rng, 3.6, 0.5 * f * L, 0.9, 6)
    q7 = _lik(rng, 3.7, 0.6 * f * L + 0.3 * (q5 - 3.9), 0.8, 6)
    q8 = _lik(rng, 4.0, 0.3 * (niveau - 2.5), 1.0, 6)
    q9 = _lik(rng, 3.4, 0.8 * f * L + 0.3 * (q5 - 3.9), 0.7, 5)
    q10 = _lik(rng, 3.8, p.lien_q10_latent * L + p.lien_q10_age * (age - 2.5), 1.0, 5)
    q11 = _lik(rng, 3.6, 0 * L, 1.0, 5)  # indépendante du trait latent
    q12 = _lik(rng, 3.3, 0.7 * f * L, 0.8, 5)
    q13 = _lik(rng, 3.9, 0.6 * f * L, 1.0, 6)
    q14 = _lik(rng, 3.5, 0.5 * f * L, 1.0, 6)
    q15 = _lik(rng, 3.8, 0.6 * f * L, 1.0, 6)

    df = pd.DataFrame({"ID": [f"SYN-{i:03d}" for i in range(1, n + 1)],
                       "Q1": q1, "Q2": age, "Q3": genre, "Q4": niveau, "Q5": q5, "Q6": q6,
                       "Q7": q7, "Q8": q8, "Q9": q9, "Q10": q10, "Q11": q11, "Q12": q12,
                       "Q13": q13, "Q14": q14, "Q15": q15})
    df[ALL_QS] = df[ALL_QS].astype(float)

    applicable = pd.DataFrame({q: is_applicable(q, df["Q1"]) for q in ALL_QS})
    df = df.mask(~applicable.reindex(columns=df.columns, fill_value=True))  # non applicable → NaN
    for q in ALL_QS[1:]:  # non-réponse accidentelle (Q1 jamais manquante)
        hit = applicable[q] & (rng.random(n) < p.taux_manquants)
        df.loc[hit, q] = np.nan

    df[PROFIL_COL] = pd.Categorical(
        np.select([L < -0.5, L > 0.6], [PROFILS[0], PROFILS[2]], PROFILS[1]), categories=PROFILS)
    df["Source"] = "SIMULATION"
    return df


# ------------------------------------------------------------------------- liens programmés
# Décrit, pour chaque question à 5/6 niveaux, comment son signal est construit dans simulate() :
# coefficient du trait latent L (fonction des paramètres), et dépendances directes à d'autres
# questions déjà tirées. Sert uniquement à expliquer d'où peuvent venir des corrélations observées.
def _latent_coef(p: SimParams) -> dict:
    f = p.force_latent
    return {"Q5": 0.9 * f, "Q6": 0.5 * f, "Q7": 0.6 * f, "Q8": 0.0, "Q9": 0.8 * f,
            "Q10": p.lien_q10_latent, "Q11": 0.0, "Q12": 0.7 * f, "Q13": 0.6 * f,
            "Q14": 0.5 * f, "Q15": 0.6 * f}


DIRECT_LINKS = {"Q7": [("Q5", 0.3)], "Q9": [("Q5", 0.3)]}  # dépendance directe à la valeur tirée de Q5
NIVEAU_LINKS = {"Q8": 0.3}       # dépend du niveau d'études, pas du trait latent
AGE_LINKS_FN = {"Q10": lambda p: p.lien_q10_age}  # 0 par défaut


def programmed_link_note(qa: str, qb: str, params: SimParams) -> str:
    """Explique, à partir des coefficients réellement utilisés par `params`, pourquoi deux questions
    pourraient être corrélées (facteur latent commun, dépendance directe) ou non.
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


def status_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Statut de chaque cellule : répondu / non_applicable / manquant."""
    out = {}
    for q in ALL_QS:
        applicable = is_applicable(q, df["Q1"])
        out[q] = np.where(~applicable, "non_applicable",
                          np.where(df[q].isna(), "manquant", "répondu"))
    return pd.DataFrame(out, index=df.index)


def effectifs(df: pd.DataFrame) -> pd.DataFrame:
    """Effectifs par question : posée à, répondu, non applicable, manquant."""
    st = status_frame(df)
    rows = []
    for q in ALL_QS:
        c = st[q].value_counts()
        rows.append({"Question": q, "Applicable (posée à)": int(len(df) - c.get("non_applicable", 0)),
                     "Répondu (n utilisé)": int(c.get("répondu", 0)),
                     "Non applicable": int(c.get("non_applicable", 0)),
                     "Manquant (accidentel)": int(c.get("manquant", 0))})
    return pd.DataFrame(rows)


