"""Génération d'un échantillon synthétique (Q1–Q15) et exports."""
from __future__ import annotations

import io
import json
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
    age_weights: tuple = (0.10, 0.62, 0.20, 0.08)
    taux_manquants: float = 0.02             # non-réponse accidentelle, par cellule applicable (Q2–Q15)
    force_latent: float = 1.0                # multiplie le lien du trait latent avec Q5, Q7, Q9, Q12–Q15
    lien_q10_latent: float = 0.0             # DÉSACTIVÉ par défaut : aucune association imposée
    lien_q10_age: float = 0.0                # DÉSACTIVÉ par défaut


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
    niveau_p = {1: (0.95, 0.05, 0, 0), 2: (0.45, 0.35, 0.18, 0.02),
                3: (0.10, 0.25, 0.45, 0.20), 4: (0.03, 0.12, 0.40, 0.45)}
    niveau = np.array([_choice(rng, niveau_p[a], 1)[0] for a in age])
    genre = _choice(rng, (0.46, 0.48, 0.03, 0.03), n)

    L = rng.normal(0, 1, n)  # trait latent « appétence pour l'IA » (construction de la simulation)

    logit0 = np.log(p.taux_usage / (1 - p.taux_usage))
    z = 0.9 * L + 0.15 * (niveau - 2.5) - 0.2 * (age == 1)
    z = z - z.mean() + logit0
    q1 = np.where(rng.random(n) < 1 / (1 + np.exp(-z)), 1, 2)  # 1 = Oui, 2 = Non

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


def with_labels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for q in CATEGORICAL:
        opts = QUESTIONS[q]["options"]
        out[q] = out[q].map(lambda c, o=opts: o[int(c) - 1] if pd.notna(c) else np.nan)
    return out


def export_frame(df: pd.DataFrame, mode: str = "both") -> pd.DataFrame:
    """Colonnes Qx + Qx_statut (distinguant non applicable / manquant, que la cellule vide ne dit pas)."""
    out = df.copy() if mode == "codes" else with_labels(df)
    if mode == "both":
        for q in CATEGORICAL:
            out[f"{q}_code"] = df[q]
    st = status_frame(df).add_suffix("_statut")
    return pd.concat([out, st], axis=1)


NOTE = "Cellule vide = non applicable OU manquant : voir colonnes Qx_statut."


def to_csv_bytes(df, mode="both") -> bytes:
    body = export_frame(df, mode).to_csv(index=False)
    return ("﻿# " + BANNER + "\n# " + NOTE + "\n" + body).encode("utf-8")


def to_excel_bytes(df) -> bytes:
    buf = io.BytesIO()
    cb = pd.DataFrame(codebook(), columns=["Question", "Intitulé", "Code", "Modalité"])
    ft = pd.DataFrame(filters_table(), columns=["Question", "Posée à", "Nature de la règle"])
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"AVERTISSEMENT": [BANNER, NOTE]}).to_excel(xw, sheet_name="AVERTISSEMENT", index=False)
        for name, frame in (("Données", export_frame(df, "both")), ("Dictionnaire", cb),
                            ("Filtres", ft), ("Effectifs", effectifs(df))):
            frame.to_excel(xw, sheet_name=name, index=False, startrow=2)
            xw.sheets[name]["A1"] = BANNER
        xw.sheets["AVERTISSEMENT"].column_dimensions["A"].width = 90
    return buf.getvalue()


def to_json_bytes(df) -> bytes:
    payload = {"avertissement": BANNER, "note": NOTE,
               "filtres": [dict(zip(("question", "posee_a", "regle"), r)) for r in filters_table()],
               "enregistrements": json.loads(export_frame(df, "both").to_json(orient="records"))}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
