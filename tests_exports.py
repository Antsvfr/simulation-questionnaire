"""Relecture des fichiers exportés : lignes, Q1–Q15, codes ↔ libellés, accents, manquant ≠ non applicable."""
import io
import json

import pandas as pd

import exports as ex
from simulator import SimParams, simulate, status_frame
from survey_config import ALL_QS, BANNER, QUESTIONS
from views import (LATENT_COL, MISS_TXT, NA_TXT, Filters, filter_mask, fmt_answer, readable_frame)

P = SimParams(n=100, seed=42, taux_manquants=0.08)
D = simulate(P)


def rd(b):
    return pd.read_csv(io.BytesIO(b), encoding="utf-8-sig", dtype=str, keep_default_na=False)


def test_csv_lisible():
    b = ex.csv_readable(D)
    first = b.decode("utf-8-sig").splitlines()[0]
    assert first.startswith("ID,Origine,Q1,") and not first.startswith("#")  # en-têtes en première ligne
    t = rd(b)
    assert len(t) == 100 and all(q in t.columns for q in ALL_QS)
    assert (t["Origine"] == BANNER).all()
    assert set(t["Q2"]) <= set(QUESTIONS["Q2"]["options"]) | {MISS_TXT}
    assert "18–24 ans" in set(t["Q2"]) and "Préfère ne pas répondre" in b.decode("utf-8")  # accents conservés
    assert LATENT_COL in t.columns  # colonne interne au modèle, clairement nommée
    # accord avec l'affichage
    shown = readable_frame(D)
    assert (t["Q5"].values == shown["Q5"].values).all()
    assert (t["ID"].values == shown["ID"].values).all()
    assert NA_TXT in set(t["Q8"]) and MISS_TXT in set(t.values.ravel())


def test_csv_codes_et_correspondance():
    t = rd(ex.csv_codes(D))
    st = status_frame(D)
    assert len(t) == 100 and all(q in t.columns and f"{q}_statut" in t.columns for q in ALL_QS)
    for q in ALL_QS:
        for code, statut, true_v, true_s in zip(t[q], t[f"{q}_statut"], D[q], st[q]):
            assert statut == true_s
            if true_s == "répondu":
                assert code == str(int(true_v))          # entiers, pas « 4.0 »
            else:
                assert code == ""                        # vide pour NA et manquant
    r = rd(ex.csv_readable(D))
    for q in ALL_QS:  # codes ↔ libellés
        for code, lib in zip(t[q], r[q]):
            if code:
                assert lib == fmt_answer(q, int(code))
    na_cells = (t[[f"{q}_statut" for q in ALL_QS]] == "non_applicable").sum().sum()
    miss_cells = (t[[f"{q}_statut" for q in ALL_QS]] == "manquant").sum().sum()
    assert na_cells > 0 and miss_cells > 0
    assert (r[ALL_QS] == NA_TXT).sum().sum() == na_cells and (r[ALL_QS] == MISS_TXT).sum().sum() == miss_cells


def test_export_filtre_et_complet():
    f = Filters(usage=["Non"])
    mask = filter_mask(readable_frame(D), f)
    sub = ex.select(D, D.loc[mask, "ID"])
    assert 0 < len(sub) < len(D)
    t = rd(ex.csv_readable(sub))
    assert len(t) == len(sub) == mask.sum() and (t["Q1"] == "Non").all()
    assert set(t["ID"]) == set(D.loc[mask, "ID"])
    assert len(ex.select(D, None)) == 100
    assert len(ex.select(D, [])) == 0


def test_excel_feuilles_et_contenu():
    b = ex.excel_bytes(D, P, "Ensemble", 100, None, True)
    sheets = pd.read_excel(io.BytesIO(b), sheet_name=None, dtype=str, keep_default_na=False)
    assert list(sheets) == ex.SHEETS
    assert len(sheets["Réponses lisibles"]) == 100 and len(sheets["Codes et statuts"]) == 100
    assert all(q in sheets["Réponses lisibles"].columns for q in ALL_QS)
    assert list(sheets["Réponses lisibles"]["ID"]) == list(D["ID"])
    csv = rd(ex.csv_readable(D))
    assert (sheets["Réponses lisibles"]["Q10"].values == csv["Q10"].values).all()
    assert any("–" in v for v in sheets["Réponses lisibles"]["Q2"])  # accents/tirets conservés dans Excel
    meth = pd.read_excel(io.BytesIO(b), sheet_name="Paramètres et méthode", header=None, dtype=str)
    flat = " ".join(meth.fillna("").values.ravel())
    assert BANNER in flat and "Graine" in flat and "42" in flat
    comp = pd.read_excel(io.BytesIO(b), sheet_name="Composition", header=2)
    assert comp["Probabilité paramétrée (%)"].notna().any()
    dic = pd.read_excel(io.BytesIO(b), sheet_name="Dictionnaire", header=None, dtype=str)
    assert "Tout à fait d'accord" in " ".join(dic.fillna("").values.ravel())


def test_excel_filtre_sans_probabilites_parametrees():
    sub = D.head(10)
    b = ex.excel_bytes(sub, P, "Profils filtrés (10 sur 100)", 100, Filters(search="SYN-00"), False)
    comp = pd.read_excel(io.BytesIO(b), sheet_name="Composition", header=2)
    assert comp["Probabilité paramétrée (%)"].isna().all()
    assert (comp["Dénominateur (réponses valides)"] <= 10).all()
    assert len(pd.read_excel(io.BytesIO(b), sheet_name="Réponses lisibles")) == 10


def test_json_et_nom_de_fichier():
    j = json.loads(ex.json_bytes(D, P, "Ensemble", 100, None))
    assert j["avertissement"] == BANNER and len(j["profils"]) == 100 and j["parametres"]["seed"] == 42
    name = ex.filename("lisibles", "csv", P, "tout", 100)
    assert name.startswith("SIMULATION_SYNTHETIQUE") and "graine42" in name and name.endswith(".csv")


def test_export_vide_ne_plante_pas():
    e = ex.select(D, [])
    assert len(rd(ex.csv_readable(e))) == 0
    ex.excel_bytes(e, P, "Profils filtrés (0 sur 100)", 100, Filters(search="ZZZ"), False)
