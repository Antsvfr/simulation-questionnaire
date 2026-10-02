"""Vues dérivées de l'échantillon : tableaux lisibles/codes, filtres, composition, corrélations.

Fonctions pures (sans Streamlit) pour pouvoir être testées.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from simulator import PROFIL_COL, SimParams, expected_distributions, status_frame
from survey_config import ALL_QS, BANNER, CATEGORICAL, QUESTIONS, SCALE_QS

NA_TXT = "Non applicable"
MISS_TXT = "Réponse manquante"
COMPLET, INCOMPLET = "Complet", "Incomplet"
LATENT_COL = "⚙ Profil latent simulé (interne au modèle)"
ORIGINE = "Origine"
COL_NB_MISS = "Nb réponses manquantes"
COL_MISS = "Questions manquantes"
COL_NA = "Questions non applicables"
COL_STATUT_Q = "Statut du questionnaire"
VARS = {"Q1": "Utilisation de l'IA", "Q2": "Tranche d'âge", "Q3": "Genre", "Q4": "Niveau d'études"}


def fmt_answer(q: str, code) -> str:
    """Texte lisible d'une réponse. Seuls les libellés présents dans le questionnaire sont utilisés."""
    spec = QUESTIONS[q]
    c = int(code)
    if spec["kind"] == "single":
        return spec["options"][c - 1]
    base = f"{c} sur {spec['levels']}"
    lab = spec["anchors"].get(c)
    return f"{base} · {lab}" if lab else base


def _summary_cols(df, st) -> pd.DataFrame:
    miss = st.eq("manquant")
    na = st.eq("non_applicable")
    return pd.DataFrame({
        COL_STATUT_Q: np.where(miss.sum(axis=1) == 0, COMPLET, INCOMPLET),
        COL_NB_MISS: miss.sum(axis=1).astype(int),
        COL_MISS: [", ".join(q for q in ALL_QS if m[q]) for _, m in miss.iterrows()],
        COL_NA: [", ".join(q for q in ALL_QS if m[q]) for _, m in na.iterrows()],
    }, index=df.index)


def readable_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par profil ; « Non applicable » et « Réponse manquante » sont distincts."""
    st = status_frame(df)
    out = pd.DataFrame({"ID": df["ID"]})
    for q in ALL_QS:
        out[q] = [NA_TXT if s == "non_applicable" else MISS_TXT if s == "manquant" else fmt_answer(q, v)
                  for v, s in zip(df[q], st[q])]
    out = pd.concat([out, _summary_cols(df, st)], axis=1)
    out[LATENT_COL] = df[PROFIL_COL].astype(str)
    return out


def codes_frame(df: pd.DataFrame, with_status: bool = True) -> pd.DataFrame:
    """Codes numériques (cellule vide = non applicable OU manquant ; voir Qx_statut)."""
    st = status_frame(df)
    out = pd.DataFrame({"ID": df["ID"]})
    for q in ALL_QS:
        out[q] = df[q].astype("Int64")
    if with_status:
        out = pd.concat([out, st.add_suffix("_statut")], axis=1)
    out = pd.concat([out, _summary_cols(df, st)], axis=1)
    out[LATENT_COL] = df[PROFIL_COL].astype(str)
    return out


def counts(df: pd.DataFrame) -> dict:
    st = status_frame(df)
    complet = st.eq("manquant").sum(axis=1) == 0
    return {"profils": len(df), "utilisateurs": int((df["Q1"] == 1).sum()),
            "non_utilisateurs": int((df["Q1"] == 2).sum()), "complets": int(complet.sum()),
            "incomplets": int((~complet).sum()), "manquantes": int(st.eq("manquant").to_numpy().sum()),
            "non_applicables": int(st.eq("non_applicable").to_numpy().sum())}


# ------------------------------------------------------------------------------------ filtres
def options_for(q: str) -> list:
    return list(QUESTIONS[q]["options"]) + [MISS_TXT]


@dataclass
class Filters:
    search: str = ""
    ages: list = field(default_factory=list)
    genres: list = field(default_factory=list)
    niveaux: list = field(default_factory=list)
    usage: list = field(default_factory=list)
    completude: str = "Tous"  # Tous / Complets / Incomplets

    def active(self) -> bool:
        return bool(self.search.strip() or self.ages or self.genres or self.niveaux or self.usage
                    or self.completude != "Tous")

    def describe(self) -> str:
        parts = []
        if self.search.strip():
            parts.append(f"identifiant contient « {self.search.strip()} »")
        for lab, v in (("âge", self.ages), ("genre", self.genres), ("niveau", self.niveaux),
                       ("utilise l'IA", self.usage)):
            if v:
                parts.append(f"{lab} ∈ {{{', '.join(v)}}}")
        if self.completude != "Tous":
            parts.append(f"questionnaires {self.completude.lower()}")
        return " ; ".join(parts) if parts else "aucun filtre"


def filter_mask(readable: pd.DataFrame, f: Filters) -> pd.Series:
    m = pd.Series(True, index=readable.index)
    if f.search.strip():
        m &= readable["ID"].str.contains(f.search.strip(), case=False, regex=False)
    for sel, q in ((f.ages, "Q2"), (f.genres, "Q3"), (f.niveaux, "Q4"), (f.usage, "Q1")):
        if sel:
            m &= readable[q].isin(sel)
    if f.completude == "Complets":
        m &= readable[COL_STATUT_Q] == COMPLET
    elif f.completude == "Incomplets":
        m &= readable[COL_STATUT_Q] == INCOMPLET
    return m


# ------------------------------------------------------------------------------------ composition
def composition_table(d: pd.DataFrame, q: str, params: SimParams | None = None) -> tuple:
    """(tableau, n_valides, n_manquants). `params` fourni → ajoute la probabilité paramétrée.

    Pourcentage observé : effectif / réponses valides de la variable (manquants exclus).
    """
    opts = QUESTIONS[q]["options"]
    valid = d[q].dropna().astype(int)
    n_valid, n_miss = len(valid), int(d[q].isna().sum())
    eff = valid.value_counts().reindex(range(1, len(opts) + 1), fill_value=0)
    t = pd.DataFrame({"Modalité": opts, "Effectif": eff.values,
                      "% observé": (eff.values / n_valid * 100) if n_valid else np.nan})
    if params is not None:
        t["Probabilité paramétrée (%)"] = np.array(expected_distributions(params)[q]) * 100
    return t, n_valid, n_miss


def composition_long(d: pd.DataFrame, scope_label: str, params: SimParams | None) -> pd.DataFrame:
    rows = []
    for q, name in VARS.items():
        t, n_valid, n_miss = composition_table(d, q, params)
        for _, r in t.iterrows():
            rows.append({"Variable": f"{q} — {name}", "Modalité": r["Modalité"],
                         "Périmètre": scope_label, "Dénominateur (réponses valides)": n_valid,
                         "Effectif": int(r["Effectif"]),
                         "% observé": None if pd.isna(r["% observé"]) else round(r["% observé"], 1),
                         "Probabilité paramétrée (%)": (round(r["Probabilité paramétrée (%)"], 1)
                                                        if "Probabilité paramétrée (%)" in t else None)})
        rows.append({"Variable": f"{q} — {name}", "Modalité": MISS_TXT, "Périmètre": scope_label,
                     "Dénominateur (réponses valides)": n_valid, "Effectif": n_miss,
                     "% observé": None, "Probabilité paramétrée (%)": None})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------ corrélations
MIN_PAIRS = 10


def safe_spearman(d: pd.DataFrame, qs=SCALE_QS, min_pairs: int = MIN_PAIRS) -> tuple:
    """Spearman par paires complètes, uniquement sur des échelles ordinales (jamais sur Q1–Q4 nominales).

    Retourne (corr, n_pairs, notes). Une corrélation est NaN si n < min_pairs ou si l'une des deux
    variables est constante sur les paires utilisables.
    """
    corr = pd.DataFrame(np.nan, index=qs, columns=qs)
    npair = pd.DataFrame(0, index=qs, columns=qs, dtype=int)
    notes = []
    for i, a in enumerate(qs):
        for b in qs[i:]:
            sub = d[[a, b]].dropna() if a != b else d[[a]].dropna()
            n = len(sub)
            npair.loc[a, b] = npair.loc[b, a] = n
            if a == b:
                continue
            if n < min_pairs:
                notes.append((a, b, n, f"effectif insuffisant (n={n} < {min_pairs})"))
            elif sub[a].nunique() < 2 or sub[b].nunique() < 2:
                notes.append((a, b, n, "variable constante sur les paires utilisables"))
            else:
                corr.loc[a, b] = corr.loc[b, a] = sub[a].rank().corr(sub[b].rank())
    for q in qs:
        corr.loc[q, q] = 1.0 if (d[q].nunique() > 1 and d[q].notna().sum() >= min_pairs) else np.nan
    return corr, npair, notes
