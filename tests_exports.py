"""Relecture des fichiers exportés : lignes, Q1–Q15, codes ↔ libellés, accents, manquant ≠ non applicable,
dictionnaire, paramètres et contrôle de conformité — toujours en rouvrant le fichier réellement généré."""
import io
import json

import pandas as pd

import compliance
import exports as ex
from simulator import GENERATOR_VERSION, SimParams, simulate, status_frame
from survey_config import ALL_QS, BANNER, MODE_LIBRE, QUESTIONNAIRE_VERSION, QUESTIONS
from views import (LATENT_COL, MISS_TXT, NA_TXT, Q1_BIN_COL, Filters, filter_mask, fmt_answer,
                   readable_frame)

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
    assert Q1_BIN_COL in t.columns
    assert set(t.loc[t[Q1_BIN_COL] != "", Q1_BIN_COL]) <= {"1", "0"}


def test_csv_mode_sans_branchement_aucune_na():
    d_libre = simulate(SimParams(n=100, seed=42, taux_manquants=0.08, filter_mode=MODE_LIBRE))
    t = rd(ex.csv_codes(d_libre, MODE_LIBRE))
    assert (t[[f"{q}_statut" for q in ALL_QS]] != "non_applicable").to_numpy().all()


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


def test_excel_huit_feuilles_et_contenu():
    b = ex.excel_bytes(D, P, "Ensemble", 100, None, True, df_full=D)
    sheets = pd.read_excel(io.BytesIO(b), sheet_name=None, dtype=str, keep_default_na=False)
    assert list(sheets) == ex.SHEETS == [
        "Réponses lisibles", "Codes et statuts", "Dictionnaire", "Composition", "Paramètres",
        "Méthode et limites", "Contrôle de conformité", "Préparation de la base"]
    assert len(sheets["Réponses lisibles"]) == 100 and len(sheets["Codes et statuts"]) == 100
    assert all(q in sheets["Réponses lisibles"].columns for q in ALL_QS)
    assert list(sheets["Réponses lisibles"]["ID"]) == list(D["ID"])
    csv = rd(ex.csv_readable(D))
    assert (sheets["Réponses lisibles"]["Q10"].values == csv["Q10"].values).all()
    assert any("–" in v for v in sheets["Réponses lisibles"]["Q2"])  # accents/tirets conservés dans Excel

    param = pd.read_excel(io.BytesIO(b), sheet_name="Paramètres", header=None, dtype=str)
    flat_p = " ".join(param.fillna("").values.ravel())
    assert BANNER in flat_p and "Graine" in flat_p and "42" in flat_p
    assert QUESTIONNAIRE_VERSION in flat_p and GENERATOR_VERSION in flat_p
    assert "Mode de filtrage" in flat_p and "Probabilités et associations" in flat_p
    assert "Taux de non-réponse configuré" in flat_p

    meth = pd.read_excel(io.BytesIO(b), sheet_name="Méthode et limites", header=None, dtype=str)
    flat_m = " ".join(meth.fillna("").values.ravel())
    assert BANNER in flat_m and "Trait latent" in flat_m

    comp = pd.read_excel(io.BytesIO(b), sheet_name="Composition", header=2)
    assert comp["Probabilité paramétrée (%)"].notna().any()

    dic_all = pd.read_excel(io.BytesIO(b), sheet_name="Dictionnaire", header=2, dtype=str)
    dic = dic_all[dic_all["Type de variable"].notna()]  # seule la sous-table codebook a cette colonne
    from survey_config import codebook as _codebook
    assert len(dic) == len(_codebook())
    assert "Tout à fait d'accord" in set(dic["Libellé exact"].dropna())
    assert dic["Libellé exact"].notna().all() and (dic["Libellé exact"].str.strip() != "").all()
    assert set(dic.loc[dic["Question"] == "Q5", "Type de variable"].dropna()) == {"Ordinale (8 modalités)"}


def test_excel_code6_egale_libelle_5_pas_extremite_haute():
    b = ex.excel_bytes(D, P, "Ensemble", 100, None, True, df_full=D)
    dic = pd.read_excel(io.BytesIO(b), sheet_name="Dictionnaire", header=2, dtype=str)
    dic["Code"] = pd.to_numeric(dic["Code"], errors="coerce")
    for q in ("Q5", "Q6", "Q7", "Q8", "Q13", "Q14", "Q15"):
        row6 = dic[(dic["Question"] == q) & (dic["Code"] == 6)]
        assert len(row6) == 1
        assert row6["Libellé exact"].iloc[0] == "5"


def test_excel_filtres_decrits_sans_pretendre_qualtrics():
    b = ex.excel_bytes(D, P, "Ensemble", 100, None, True, df_full=D)
    dic = pd.read_excel(io.BytesIO(b), sheet_name="Dictionnaire", header=None, dtype=str)
    flat = " ".join(dic.fillna("").values.ravel())
    assert "Convention de simulation" in flat
    assert "Minimum exigé par la consigne" not in flat
    assert "non vérifiée dans Qualtrics" in flat


def test_excel_feuille_controle_de_conformite_colorée():
    import openpyxl
    b = ex.excel_bytes(D, P, "Ensemble", 100, None, True, df_full=D)
    sheets = pd.read_excel(io.BytesIO(b), sheet_name=None, header=2)
    ctrl = sheets["Contrôle de conformité"]
    assert list(ctrl.columns) == compliance.COLS
    assert set(ctrl["Statut"]) <= {compliance.VERT, compliance.ROUGE, compliance.GRIS}
    assert (ctrl["Statut"] == compliance.VERT).sum() >= 10   # la quasi-totalité des contrôles réussit
    assert (ctrl["Statut"] == compliance.GRIS).any()         # l'info codes-extrêmes reste grise

    wb = openpyxl.load_workbook(io.BytesIO(b))
    ws = wb["Contrôle de conformité"]
    seen = set()
    for row in ws.iter_rows(min_row=4, max_row=3 + len(ctrl)):
        fill = row[3].fill.fgColor.rgb
        seen.add(fill)
    assert "00C6EFCE" in seen  # au moins une ligne verte colorée (pas seulement du texte)

    prep = sheets["Préparation de la base"]
    assert (prep["Statut"] == compliance.GRIS).all()  # jamais vert artificiellement
    flat_prep = " ".join(prep.astype(str).values.ravel())
    assert "Test d'attention" in flat_prep and "Absent" in flat_prep
    assert "non binaire" in flat_prep.lower() or "Non applicable" in flat_prep
    assert "L5" in flat_prep


def test_controle_detecte_vraiment_une_anomalie_injectee():
    bad = D.copy()
    bad.loc[bad.index[0], "ID"] = bad.loc[bad.index[1], "ID"]  # doublon volontaire
    bad.loc[bad.index[2], "Q5"] = 99  # hors bornes volontaire
    ctrl = compliance.control_table(bad, P)
    rouges = set(ctrl.loc[ctrl["Statut"] == compliance.ROUGE, "Contrôle"])
    assert "Identifiants uniques" in rouges
    assert "Valeurs dans les modalités autorisées (1..k ou vide)" in rouges


def test_controle_jamais_force_au_vert_taille_incorrecte():
    wrong_params = SimParams(n=999, seed=42)  # n déclaré ne correspond pas aux 100 lignes de D
    ctrl = compliance.control_table(D, wrong_params)
    row = ctrl[ctrl["Contrôle"] == "Taille de l'échantillon généré"].iloc[0]
    assert row["Statut"] == compliance.ROUGE


def test_excel_filtre_sans_probabilites_parametrees():
    sub = D.head(10)
    b = ex.excel_bytes(sub, P, "Profils filtrés (10 sur 100)", 100, Filters(search="SYN-00"), False,
                       df_full=D)
    comp = pd.read_excel(io.BytesIO(b), sheet_name="Composition", header=2)
    assert comp["Probabilité paramétrée (%)"].isna().all()
    assert (comp["Dénominateur (réponses valides)"] <= 10).all()
    assert len(pd.read_excel(io.BytesIO(b), sheet_name="Réponses lisibles")) == 10
    # le contrôle de conformité porte sur l'échantillon actif complet (100), pas sur les 10 exportés
    ctrl = pd.read_excel(io.BytesIO(b), sheet_name="Contrôle de conformité", header=2)
    taille = ctrl[ctrl["Contrôle"] == "Taille de l'échantillon généré"].iloc[0]
    assert "100" in str(taille["Résultat observé"]) and taille["Statut"] == compliance.VERT


def test_json_et_nom_de_fichier():
    j = json.loads(ex.json_bytes(D, P, "Ensemble", 100, None))
    assert j["avertissement"] == BANNER and len(j["profils"]) == 100 and j["parametres"]["seed"] == 42
    assert j["version_questionnaire"] == QUESTIONNAIRE_VERSION
    assert j["version_modele_generation"] == GENERATOR_VERSION
    assert j["mode_filtrage"] == P.filter_mode
    assert Q1_BIN_COL in j["profils"][0]
    name = ex.filename("lisibles", "csv", P, "tout", 100)
    assert name.startswith("SIMULATION_SYNTHETIQUE") and "graine42" in name and name.endswith(".csv")


def test_export_vide_ne_plante_pas():
    e = ex.select(D, [])
    assert len(rd(ex.csv_readable(e))) == 0
    ex.excel_bytes(e, P, "Profils filtrés (0 sur 100)", 100, Filters(search="ZZZ"), False, df_full=D)
