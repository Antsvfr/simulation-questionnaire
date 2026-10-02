"""Tests du générateur et des vues (sans Streamlit)."""
import numpy as np
import pandas as pd
import pytest

from simulator import PROFIL_COL, SimParams, effectifs, expected_distributions, simulate, status_frame
from survey_config import AGREE5, ALL_QS, QUESTIONS, codebook
from views import (COL_NB_MISS, COL_STATUT_Q, COMPLET, INCOMPLET, LATENT_COL, MISS_TXT, NA_TXT, Filters,
                   codes_frame, composition_table, counts, filter_mask, fmt_answer, readable_frame,
                   safe_spearman)

MIN_NA = ["Q8", "Q9", "Q11", "Q12"]


def test_questionnaire_complet_et_echelles():
    assert ALL_QS == [f"Q{i}" for i in range(1, 16)]
    for q in ("Q9", "Q10", "Q11", "Q12"):
        assert QUESTIONS[q]["levels"] == 5 and QUESTIONS[q]["anchors"] == AGREE5
    for q in ("Q5", "Q6", "Q7", "Q8", "Q13", "Q14", "Q15"):
        assert QUESTIONS[q]["levels"] == 6
    assert {r[0] for r in codebook()} == set(ALL_QS)
    assert all(QUESTIONS[q]["text"] for q in ALL_QS)


def test_reproductible_et_graine():
    a, b = simulate(SimParams(seed=1)), simulate(SimParams(seed=1))
    assert a.equals(b)
    assert not a.equals(simulate(SimParams(seed=2)))


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
    for q in MIN_NA:
        assert (st.loc[nonusers, q] == "non_applicable").all()
    for q in ALL_QS:
        assert d.loc[st[q] != "répondu", q].isna().all() and d.loc[st[q] == "répondu", q].notna().all()
    assert (st == "manquant").to_numpy().sum() > 0
    eff = effectifs(d)
    assert (eff["Répondu (n utilisé)"] + eff["Non applicable"] + eff["Manquant (accidentel)"] == len(d)).all()


@pytest.mark.parametrize("taux", [0.0, 1.0])
def test_zero_et_cent_pour_cent_utilisateurs(taux):
    d = simulate(SimParams(n=100, seed=5, taux_usage=taux, taux_manquants=0))
    c = counts(d)
    assert c["utilisateurs"] == (100 if taux == 1 else 0)
    if taux == 0:
        assert c["non_applicables"] == 100 * 6 and c["complets"] == 100  # N/A ≠ oubli
        assert d[["Q8", "Q9", "Q11", "Q12", "Q5", "Q7"]].isna().all().all()
    else:
        assert c["non_applicables"] == 0
    r = readable_frame(d)
    assert len(r) == 100
    # corrélations et composition sans erreur même sans utilisateurs
    safe_spearman(d)
    composition_table(d, "Q1")


def test_taux_usage_calibre():
    d = simulate(SimParams(n=20000, seed=6, taux_usage=0.3, taux_manquants=0))
    assert abs((d.Q1 == 1).mean() - 0.3) < 0.01


def test_q10_sans_association_par_defaut():
    assert SimParams().lien_q10_latent == 0 and SimParams().lien_q10_age == 0
    d = simulate(SimParams(n=20000, seed=7, taux_manquants=0))
    assert abs(d[["Q10", "Q5"]].corr(method="spearman").iloc[0, 1]) < 0.05


def test_age_niveau_coherents_et_pas_de_profil_reel():
    d = simulate(SimParams(n=500, seed=5, taux_manquants=0))
    assert (d.loc[d.Q2 == 1, "Q4"] <= 2).all()
    assert PROFIL_COL in d.columns


def test_probabilites_parametrees_somment_a_1():
    ed = expected_distributions(SimParams(age_weights=(1, 2, 3, 4)))
    for q, p in ed.items():
        assert abs(sum(p) - 1) < 1e-9, q


def test_formats_lisibles():
    assert fmt_answer("Q5", 4) == "4 sur 6"
    assert fmt_answer("Q5", 1) == "1 sur 6 · Pas du tout"
    assert fmt_answer("Q9", 3) == "3 sur 5 · Neutre"
    assert fmt_answer("Q4", 3) == "Master"
    assert fmt_answer("Q14", 6) == "6 sur 6 · Positif"
    assert fmt_answer("Q14", 3) == "3 sur 6"  # aucun libellé intermédiaire inventé


def test_lisible_vs_codes_coherents():
    d = simulate(SimParams(n=200, seed=8, taux_manquants=0.1))
    r, c = readable_frame(d), codes_frame(d)
    assert list(r["ID"]) == list(c["ID"]) == list(d["ID"])
    for q in ALL_QS:
        for rv, cv, sv in zip(r[q], c[q], c[f"{q}_statut"]):
            if sv == "non_applicable":
                assert rv == NA_TXT and pd.isna(cv)
            elif sv == "manquant":
                assert rv == MISS_TXT and pd.isna(cv)
            else:
                assert rv == fmt_answer(q, cv)
    assert set(r[COL_STATUT_Q]) <= {COMPLET, INCOMPLET}
    assert (r[COL_NB_MISS] == (c[[f"{q}_statut" for q in ALL_QS]] == "manquant").sum(axis=1)).all()


def test_filtres():
    d = simulate(SimParams(n=200, seed=9, taux_manquants=0.1))
    r = readable_frame(d)
    assert filter_mask(r, Filters()).all()
    m = filter_mask(r, Filters(usage=["Non"]))
    assert (d.loc[m, "Q1"] == 2).all() and m.sum() == (d.Q1 == 2).sum()
    assert filter_mask(r, Filters(search="syn-001")).sum() == 1
    inc = filter_mask(r, Filters(completude="Incomplets"))
    assert inc.sum() == counts(d)["incomplets"]
    assert filter_mask(r, Filters(search="ZZZ")).sum() == 0
    assert filter_mask(r, Filters(ages=["Moins de 18 ans"], genres=["Homme"])).sum() == (
        (d.Q2 == 1) & (d.Q3 == 1)).sum()
    assert Filters().completude == "Tous" and not Filters().active()


def test_correlations_gardes_fous():
    d = simulate(SimParams(n=100, seed=10, taux_manquants=0))
    corr, npair, notes = safe_spearman(d)
    assert (np.diag(npair.values) == d[corr.columns].notna().sum().values).all()
    # effectif insuffisant
    c2, n2, notes2 = safe_spearman(d.head(5))
    assert c2.drop(index="Q10", columns="Q10").isna().all().all() or notes2
    # colonne constante
    k = d.copy()
    k["Q10"] = 3.0
    c3, _, n3 = safe_spearman(k)
    assert c3["Q10"].drop("Q10").isna().all() and any("constante" in x[3] for x in n3)
    # jamais de variables nominales
    assert not {"Q1", "Q2", "Q3", "Q4"} & set(corr.columns)
    # valeurs bornées
    assert corr.stack().abs().max() <= 1 + 1e-9


def test_composition_denominateur_et_filtre():
    d = simulate(SimParams(n=300, seed=11, taux_manquants=0.1))
    t, n_valid, n_miss = composition_table(d, "Q2", SimParams())
    assert n_valid + n_miss == 300 and t["Effectif"].sum() == n_valid
    assert abs(t["% observé"].sum() - 100) < 1e-6
    assert "Probabilité paramétrée (%)" in t and "Probabilité paramétrée (%)" not in composition_table(d, "Q2")[0]
    empty = composition_table(d.head(0), "Q2")
    assert empty[1] == 0
