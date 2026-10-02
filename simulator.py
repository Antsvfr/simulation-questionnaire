"""Génération d'un échantillon synthétique cohérent (profils latents corrélés)."""
from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd

from survey_config import (BANNER, CATEGORICAL, QUESTIONS, SCALE_QS, codebook)

PROFILS = ["Non-utilisateur", "Sceptique", "Pragmatique", "Enthousiaste"]


def _choice(rng, options, p, n):
    p = np.asarray(p, float)
    return rng.choice(len(options), size=n, p=p / p.sum()) + 1  # codes 1..k


def _likert(rng, latent, mu, loading, noise):
    raw = mu + loading * latent + rng.normal(0, noise, size=len(latent))
    return np.clip(np.rint(raw), 1, 6).astype(int)


def simulate(n: int = 100, seed: int = 42, taux_usage: float = 0.80,
             age_weights=(0.10, 0.62, 0.20, 0.08)) -> pd.DataFrame:
    """Retourne un DataFrame de codes numériques (NaN = question non posée).

    Structure : un trait latent d'« enthousiasme envers l'IA » influence Q5–Q9 ;
    l'âge et le niveau d'études pilotent Q1 et la confiance en soi (Q8) ;
    les attentes d'encadrement (Q10) sont plus fortes chez les sceptiques.
    """
    rng = np.random.default_rng(seed)

    # Q2 puis Q4 cohérent avec l'âge
    age = _choice(rng, range(4), age_weights, n)
    niveau_p = {1: (0.95, 0.05, 0, 0), 2: (0.45, 0.35, 0.18, 0.02),
                3: (0.10, 0.25, 0.45, 0.20), 4: (0.03, 0.12, 0.40, 0.45)}
    niveau = np.array([_choice(rng, range(4), niveau_p[a], 1)[0] for a in age])
    genre = _choice(rng, range(4), (0.46, 0.48, 0.03, 0.03), n)

    # Trait latent d'enthousiasme (légèrement plus élevé aux niveaux avancés)
    latent = rng.normal(0, 1, n) + 0.15 * (niveau - 2.5)

    # Q1 : régression logistique calée sur le taux d'usage cible
    logit0 = np.log(taux_usage / (1 - taux_usage))
    z = logit0 + 0.9 * latent + 0.15 * (niveau - 2.5) - 0.2 * (age == 1)
    z += logit0 - np.mean(z)  # recalage de la moyenne sur le taux cible
    usage = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)  # 1 = utilise
    q1 = np.where(usage == 1, 1, 2)  # code 1 = Oui, 2 = Non

    q5 = _likert(rng, latent, 3.9, 0.9, 0.9)
    q6 = _likert(rng, 0.6 * latent + rng.normal(0, 0.6, n), 3.6, 0.8, 0.8)
    q7 = _likert(rng, 0.8 * q5 / 6 * 2 + 0.4 * latent, 2.4, 1.0, 0.8)
    q8 = _likert(rng, 0.25 * (niveau - 2.5) - 0.35 * (q6 - 3.5) / 1.2
                 + rng.normal(0, 0.6, n), 4.0, 1.0, 0.8)
    q9 = _likert(rng, 0.7 * latent + 0.35 * (q5 - 3.5), 3.9, 0.9, 0.7)
    q10 = _likert(rng, -0.55 * latent + 0.25 * (age - 2.5), 4.4, 0.9, 1.0)

    df = pd.DataFrame({"ID": [f"SYN-{i:03d}" for i in range(1, n + 1)],
                       "Q1": q1, "Q2": age, "Q3": genre, "Q4": niveau,
                       "Q5": q5, "Q6": q6, "Q7": q7, "Q8": q8, "Q9": q9, "Q10": q10})

    # Filtre : Q5–Q9 réservées aux utilisateurs ; Q10 posée à tous
    non_users = df["Q1"] == 2
    for q, d in QUESTIONS.items():
        if d["asked"] == "users":
            df[q] = df[q].astype("float").mask(non_users)

    # Profil simulé (vérité terrain utile pour vérifier l'analyse)
    profil = np.select([usage == 0, latent < -0.5, latent > 0.6],
                       ["Non-utilisateur", "Sceptique", "Enthousiaste"], "Pragmatique")
    df["Profil_simulé"] = pd.Categorical(profil, categories=PROFILS)
    df["Source"] = "SIMULATION"
    return df


def with_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Copie avec les modalités textuelles pour Q1–Q4 (Q5–Q10 restent numériques)."""
    out = df.copy()
    for q in CATEGORICAL:
        opts = QUESTIONS[q]["options"]
        out[q] = out[q].map(lambda c, o=opts: o[int(c) - 1])
    return out


def export_frame(df: pd.DataFrame, mode: str = "both") -> pd.DataFrame:
    """mode : 'codes', 'libellés' ou 'both' (libellés + colonnes *_code pour Q1–Q4)."""
    if mode == "codes":
        return df.copy()
    lab = with_labels(df)
    if mode == "both":
        for q in CATEGORICAL:
            lab[f"{q}_code"] = df[q]
    return lab


def to_csv_bytes(df: pd.DataFrame, mode: str = "both") -> bytes:
    body = export_frame(df, mode).to_csv(index=False)
    return ("﻿# " + BANNER + "\n" + body).encode("utf-8")  # BOM : ouverture directe dans Excel


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    cb = pd.DataFrame(codebook(), columns=["Question", "Intitulé", "Code", "Modalité"])
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"AVERTISSEMENT": [BANNER]}).to_excel(xw, sheet_name="AVERTISSEMENT", index=False)
        export_frame(df, "both").to_excel(xw, sheet_name="Données", index=False, startrow=2)
        xw.sheets["Données"]["A1"] = BANNER
        cb.to_excel(xw, sheet_name="Dictionnaire", index=False, startrow=2)
        xw.sheets["Dictionnaire"]["A1"] = BANNER
        xw.sheets["AVERTISSEMENT"].column_dimensions["A"].width = 90
    return buf.getvalue()


def to_json_bytes(df: pd.DataFrame) -> bytes:
    payload = {"avertissement": BANNER,
               "enregistrements": json.loads(export_frame(df, "both").to_json(orient="records"))}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def cronbach_alpha(items: pd.DataFrame) -> float:
    items = items.dropna()
    k = items.shape[1]
    if k < 2 or len(items) < 3:
        return float("nan")
    return k / (k - 1) * (1 - items.var(ddof=1).sum() / items.sum(axis=1).var(ddof=1))
