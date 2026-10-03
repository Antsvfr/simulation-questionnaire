"""Vues dérivées de l'échantillon : tableaux lisibles/codes, filtres, composition, corrélations.

Fonctions pures (sans Streamlit) pour pouvoir être testées.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from simulator import PROFIL_COL, SimParams, expected_distributions, status_frame
from survey_config import (ALL_QS, BANNER, CATEGORICAL, MODE_FILTRE, MODE_LIBRE, QUESTIONS,
                           SCALE_QS, is_user_only)

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
    """Texte lisible d'une réponse : exactement le libellé du questionnaire pour ce code, jamais un
    code renommé ni un libellé intermédiaire inventé (ex. code 2 → « 1 », code 8 → « Énormément »)."""
    spec = QUESTIONS[q]
    c = int(code)
    return spec["options"][c - 1] if spec["kind"] == "single" else spec["anchors"][c]


def _summary_cols(df, st) -> pd.DataFrame:
    miss = st.eq("manquant")
    na = st.eq("non_applicable")
    return pd.DataFrame({
        COL_STATUT_Q: np.where(miss.sum(axis=1) == 0, COMPLET, INCOMPLET),
        COL_NB_MISS: miss.sum(axis=1).astype(int),
        COL_MISS: [", ".join(q for q in ALL_QS if m[q]) for _, m in miss.iterrows()],
        COL_NA: [", ".join(q for q in ALL_QS if m[q]) for _, m in na.iterrows()],
    }, index=df.index)


Q1_BIN_COL = "Q1_binaire"


def readable_frame(df: pd.DataFrame, mode: str = MODE_FILTRE) -> pd.DataFrame:
    """Une ligne par profil ; « Non applicable » et « Réponse manquante » sont distincts."""
    st = status_frame(df, mode)
    out = pd.DataFrame({"ID": df["ID"]})
    for q in ALL_QS:
        out[q] = [NA_TXT if s == "non_applicable" else MISS_TXT if s == "manquant" else fmt_answer(q, v)
                  for v, s in zip(df[q], st[q])]
    out = pd.concat([out, _summary_cols(df, st)], axis=1)
    out[LATENT_COL] = df[PROFIL_COL].astype(str)
    return out


def codes_frame(df: pd.DataFrame, mode: str = MODE_FILTRE, with_status: bool = True) -> pd.DataFrame:
    """Codes numériques (cellule vide = non applicable OU manquant ; voir Qx_statut).

    Inclut `Q1_binaire` (Oui=1, Non=0), une variable dérivée proposée en plus de Q1 (conservée telle
    quelle) — jamais un recodage de Q8, qui n'est pas une variable Oui/Non.
    """
    st = status_frame(df, mode)
    out = pd.DataFrame({"ID": df["ID"]})
    for q in ALL_QS:
        out[q] = df[q].astype("Int64")
        if q == "Q1":
            out[Q1_BIN_COL] = (df["Q1"] == 1).astype("Int64")
    if with_status:
        out = pd.concat([out, st.add_suffix("_statut")], axis=1)
    out = pd.concat([out, _summary_cols(df, st)], axis=1)
    out[LATENT_COL] = df[PROFIL_COL].astype(str)
    return out


def overview_text(c: dict) -> str:
    """Description courte calculée depuis `counts(df)` — aucune conclusion sur de vrais étudiants."""
    if c["profils"] == 0:
        return "Aucun profil dans ce périmètre."
    pct_use = c["utilisateurs"] / c["profils"] * 100
    pct_complet = c["complets"] / c["profils"] * 100
    return (f"Sur les {c['profils']} profils synthétiques de cet échantillon, {c['utilisateurs']} "
            f"({pct_use:.0f} %) déclarent utiliser l'IA et {c['non_utilisateurs']} ({100 - pct_use:.0f} %) "
            f"n'en déclarent pas l'usage. {c['complets']} profils ({pct_complet:.0f} %) ont un "
            f"questionnaire complet (aucune réponse manquante parmi les questions qui leur étaient "
            f"applicables). Au total, {c['manquantes']} réponses sont accidentellement manquantes et "
            f"{c['non_applicables']} ne s'appliquaient pas au profil concerné. Ces chiffres décrivent "
            f"uniquement les données simulées affichées ci-dessous, pas des étudiants réels.")


def counts(df: pd.DataFrame, mode: str = MODE_FILTRE) -> dict:
    st = status_frame(df, mode)
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


# ------------------------------------------------------------------------------------ question par question
def question_overview(d: pd.DataFrame, q: str, mode: str = MODE_FILTRE) -> dict:
    """n valides / manquants / non applicables pour une question, sur le périmètre `d`."""
    st = status_frame(d, mode)[q]
    return {"valides": int((st == "répondu").sum()), "manquants": int((st == "manquant").sum()),
            "non_applicables": int((st == "non_applicable").sum()), "total": len(d)}


def question_distribution(d: pd.DataFrame, q: str) -> pd.DataFrame:
    """Effectifs et % (sur réponses valides) pour chaque modalité, dans l'ordre du questionnaire."""
    spec = QUESTIONS[q]
    valid = d[q].dropna().astype(int)
    n = len(valid)
    if spec["kind"] == "single":
        modalites = spec["options"]
        eff = valid.value_counts().reindex(range(1, len(modalites) + 1), fill_value=0)
    else:
        modalites = [spec["anchors"][c] for c in range(1, spec["levels"] + 1)]
        eff = valid.value_counts().reindex(range(1, spec["levels"] + 1), fill_value=0)
    pct = (eff.values / n * 100) if n else np.full(len(modalites), np.nan)
    return pd.DataFrame({"Code": range(1, len(modalites) + 1), "Modalité": modalites,
                         "Effectif": eff.values, "% des réponses valides": np.round(pct, 1)})


def question_summary_stats(d: pd.DataFrame, q: str) -> dict | None:
    """Médiane et moyenne (convention de score approximativement métrique) pour une échelle ordonnée."""
    spec = QUESTIONS[q]
    if spec["kind"] == "single":
        return None
    valid = d[q].dropna()
    if len(valid) == 0:
        return None
    return {"mediane": float(valid.median()), "moyenne": float(valid.mean()),
            "ecart_type": float(valid.std()) if len(valid) > 1 else float("nan"),
            "levels": spec["levels"], "n": len(valid)}


# ------------------------------------------------------------------------------------ comparaisons par groupe
def comparison_available(q: str, group_q: str, mode: str = MODE_FILTRE) -> bool:
    """False lorsque `q` est réservée aux utilisateurs et que le regroupement est Q1 (comparaison
    utilisateurs/non-utilisateurs non pertinente : les non-utilisateurs n'ont par construction aucune
    réponse applicable). Toujours disponible en mode « sans branchement » (aucune question exclue),
    mais alors les réponses des non-utilisateurs à une question d'expérience sont hypothétiques."""
    if mode == MODE_LIBRE:
        return True
    return not (group_q == "Q1" and is_user_only(q))


def comparison_table(d: pd.DataFrame, q: str, group_q: str, mode: str = MODE_FILTRE) -> pd.DataFrame:
    """Une ligne par groupe : n applicable, n valide, n manquant, n non applicable."""
    st = status_frame(d, mode)
    opts = QUESTIONS[group_q]["options"]
    rows = []
    for i, lab in enumerate(opts, 1):
        in_grp = d[group_q] == i
        s = st.loc[in_grp, q]
        rows.append({group_q: lab, "n du groupe": int(in_grp.sum()),
                    "Réponses valides": int((s == "répondu").sum()),
                    "Non applicable": int((s == "non_applicable").sum()),
                    "Manquant": int((s == "manquant").sum())})
    return pd.DataFrame(rows)


def comparison_distribution(d: pd.DataFrame, q: str, group_q: str) -> pd.DataFrame:
    """Distribution de `q` (% à l'intérieur de chaque groupe, sur réponses valides du groupe)."""
    spec = QUESTIONS[q]
    opts_g = QUESTIONS[group_q]["options"]
    codes = range(1, (len(spec["options"]) if spec["kind"] == "single" else spec["levels"]) + 1)
    rows = []
    for i, lab in enumerate(opts_g, 1):
        valid = d.loc[d[group_q] == i, q].dropna().astype(int)
        n = len(valid)
        eff = valid.value_counts().reindex(codes, fill_value=0)
        for c in codes:
            rows.append({group_q: lab, "Code": c, "Effectif": int(eff[c]), "n_groupe": n,
                        "% du groupe": round(eff[c] / n * 100, 1) if n else np.nan})
    return pd.DataFrame(rows)


SMALL_N_RULE = ("Règle documentée de cette simulation : en dessous de 10 réponses valides dans un "
                "groupe, l'effectif est signalé comme petit et la distribution n'est pas commentée "
                "en détail. Ce seuil ne garantit aucune validité statistique au-delà : il signale "
                "seulement qu'une différence vue sur peu de profils peut facilement s'inverser avec "
                "un autre tirage.")


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


def spearman_pair(d: pd.DataFrame, qa: str, qb: str, min_pairs: int = MIN_PAIRS) -> dict:
    """Spearman pour une seule paire, avec le tableau croisé des valeurs discrètes utilisées."""
    sub = d[[qa, qb]].dropna()
    n = len(sub)
    sub_i = sub.astype(int)
    ct = pd.crosstab(sub_i[qa], sub_i[qb]) if n else pd.DataFrame()
    if n < min_pairs:
        return {"rho": None, "n": n, "crosstab": ct, "reason": f"effectif insuffisant (n={n} < {min_pairs})"}
    if sub_i[qa].nunique() < 2 or sub_i[qb].nunique() < 2:
        return {"rho": None, "n": n, "crosstab": ct, "reason": "une des deux questions est constante "
                "sur les paires utilisables"}
    rho = float(sub_i[qa].rank().corr(sub_i[qb].rank()))
    return {"rho": rho, "n": n, "crosstab": ct, "reason": None}
