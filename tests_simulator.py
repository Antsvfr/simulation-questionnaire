import io

import numpy as np
import pandas as pd

from simulator import (PROFIL_COL, SimParams, effectifs, export_frame, simulate, status_frame,
                       to_csv_bytes, to_excel_bytes, to_json_bytes)
from survey_config import (AGREE5, ALL_QS, BANNER, CATEGORICAL, QUESTIONS, SCALE_QS, codebook)

MIN_NA = ["Q8", "Q9", "Q11", "Q12"]


def test_questionnaire_complet_et_echelles():
    assert ALL_QS == [f"Q{i}" for i in range(1, 16)]
    for q in ("Q9", "Q10", "Q11", "Q12"):
        assert QUESTIONS[q]["levels"] == 5 and QUESTIONS[q]["anchors"] == AGREE5
    assert AGREE5[3] == "Neutre"
    for q in ("Q5", "Q6", "Q7", "Q8", "Q13", "Q14", "Q15"):
        assert QUESTIONS[q]["levels"] == 6
    assert QUESTIONS["Q13"]["anchors"] == {1: "Réducteur", 6: "Stimulant"}
    assert QUESTIONS["Q14"]["anchors"] == {1: "Négatif", 6: "Positif"}
    assert QUESTIONS["Q15"]["anchors"] == {1: "Impersonnelle", 6: "Personnalisée"}
    assert {r[0] for r in codebook()} == set(ALL_QS)


def test_reproductible():
    assert simulate(SimParams(seed=1)).equals(simulate(SimParams(seed=1)))


def test_codes_valides():
    d = simulate(SimParams(n=400, seed=3))
    for q, spec in QUESTIONS.items():
        k = len(spec["options"]) if spec["kind"] == "single" else spec["levels"]
        assert set(d[q].dropna().astype(int)) <= set(range(1, k + 1)), q
    assert d["Q1"].notna().all()


def test_non_applicable_vs_manquant():
    d = simulate(SimParams(n=500, seed=4, taux_manquants=0.1))
    st = status_frame(d)
    nonusers = d["Q1"] == 2
    for q in MIN_NA:                                  # minimum exigé
        assert (st.loc[nonusers, q] == "non_applicable").all() and d.loc[nonusers, q].isna().all()
    for q in ALL_QS:                                  # aucune valeur dans une cellule non applicable
        assert d.loc[st[q] == "non_applicable", q].isna().all()
        assert d.loc[st[q] == "répondu", q].notna().all()
        assert d.loc[st[q] == "manquant", q].isna().all()
    assert (st.loc[~nonusers, MIN_NA] != "non_applicable").all().all()
    assert (st == "manquant").to_numpy().sum() > 0    # le manquant accidentel existe
    assert (simulate(SimParams(n=300, taux_manquants=0)).pipe(status_frame) == "manquant").sum().sum() == 0
    eff = effectifs(d)
    assert (eff["Répondu (n utilisé)"] + eff["Non applicable"] + eff["Manquant (accidentel)"] == len(d)).all()


def test_q10_sans_association_par_defaut():
    p = SimParams()
    assert p.lien_q10_latent == 0 and p.lien_q10_age == 0
    d = simulate(SimParams(n=20000, seed=7, taux_manquants=0))
    assert abs(d[["Q10", "Q5"]].corr(method="spearman").iloc[0, 1]) < 0.05
    d2 = simulate(SimParams(n=20000, seed=7, taux_manquants=0, lien_q10_latent=-0.8))
    assert d2[["Q10", "Q5"]].corr(method="spearman").iloc[0, 1] < -0.15  # option paramétrable


def test_age_niveau_coherents():
    d = simulate(SimParams(n=500, seed=5, taux_manquants=0))
    assert (d.loc[d.Q2 == 1, "Q4"] <= 2).all()


def test_pas_de_profil_reel():
    d = simulate()
    assert PROFIL_COL in d.columns and "Profil_simulé" not in d.columns


def test_exports():
    d = simulate()
    csv = to_csv_bytes(d).decode()
    assert BANNER in csv and "Q15_statut" in csv
    back = pd.read_csv(io.BytesIO(to_csv_bytes(d)), comment="#", encoding="utf-8-sig")
    assert all(f"{q}_statut" in back.columns for q in ALL_QS)
    assert BANNER in to_json_bytes(d).decode()
    sheets = pd.read_excel(io.BytesIO(to_excel_bytes(d)), sheet_name=None, header=None)
    assert {"Données", "Dictionnaire", "Filtres", "Effectifs"} <= set(sheets)
    assert all(s.astype(str).apply(lambda c: c.str.contains(BANNER, regex=False)).any().any()
               for s in sheets.values())
