"""Tests du module de contrôle de conformité : chaque contrôle doit réagir à une vraie anomalie,
jamais être forcé au vert, et les éléments non vérifiables doivent rester gris."""
import dataclasses

import numpy as np

import compliance
from simulator import SimParams, check_full_range, check_reproducible, simulate
from survey_config import ALL_QS, QUESTIONS

P = SimParams(n=100, seed=42, taux_manquants=0.05)
D = simulate(P)


def test_echantillon_sain_est_majoritairement_vert():
    ctrl = compliance.control_table(D, P)
    assert set(ctrl["Statut"]) <= {compliance.VERT, compliance.GRIS}  # aucun rouge sur un échantillon sain
    assert (ctrl["Statut"] == compliance.VERT).sum() >= 10


def test_taille_incorrecte_detectee():
    ctrl = compliance.control_table(D, dataclasses.replace(P, n=50))
    row = ctrl.set_index("Contrôle").loc["Taille de l'échantillon généré"]
    assert row["Statut"] == compliance.ROUGE
    assert "100" in row["Résultat observé"]


def test_doublon_identifiant_detecte():
    bad = D.copy()
    bad.loc[bad.index[5], "ID"] = bad.loc[bad.index[6], "ID"]
    row = compliance.control_table(bad, P).set_index("Contrôle").loc["Identifiants uniques"]
    assert row["Statut"] == compliance.ROUGE and "1 doublon" in row["Résultat observé"]


def test_colonne_manquante_detectee():
    bad = D.drop(columns=["Q7"])
    row = compliance.control_table(bad, P).set_index("Contrôle").loc["Colonnes Q1 à Q15 présentes"]
    assert row["Statut"] == compliance.ROUGE and "Q7" in row["Résultat observé"]


def test_valeur_hors_bornes_detectee():
    bad = D.copy()
    bad.loc[bad.index[0], "Q13"] = 42
    row = compliance.control_table(bad, P).set_index("Contrôle")\
        .loc["Valeurs dans les modalités autorisées (1..k ou vide)"]
    assert row["Statut"] == compliance.ROUGE and "Q13" in row["Résultat observé"]


def test_incoherence_valeur_statut_detectee():
    bad = D.copy()
    nonuser_idx = bad.index[bad["Q1"] == 2][0]
    bad.loc[nonuser_idx, "Q9"] = 3  # Q9 non applicable pour ce profil : une valeur ici est incohérente
    row = compliance.control_table(bad, P).set_index("Contrôle").loc["Cohérence entre valeurs et statuts"]
    assert row["Statut"] == compliance.ROUGE


def test_dictionnaire_incomplet_detecte(monkeypatch):
    def fake_codebook():
        rows = []
        for q, d in QUESTIONS.items():
            if d["kind"] == "single":
                rows += [(q, d["label"], i, lab) for i, lab in enumerate(d["options"], 1)]
            else:
                rows += [(q, d["label"], c, d["anchors"].get(c, "")) for c in range(1, d["levels"] + 1)]
        rows[0] = (rows[0][0], rows[0][1], rows[0][2], "")  # vide le premier libellé
        return rows
    monkeypatch.setattr(compliance, "codebook", fake_codebook)
    row = compliance.control_table(D, P).set_index("Contrôle").loc["Dictionnaire complet (aucun libellé vide)"]
    assert row["Statut"] == compliance.ROUGE


def test_code6_mal_etiquete_detecte(monkeypatch):
    import copy
    patched = copy.deepcopy(QUESTIONS)
    patched["Q5"]["anchors"][6] = patched["Q5"]["anchors"][8]  # casse volontairement code6 -> ancrage haut
    monkeypatch.setattr(compliance, "QUESTIONS", patched)
    row = compliance.control_table(D, P).set_index("Contrôle")\
        .loc["Code 6 (échelle à 8 modalités) = libellé « 5 »"]
    assert row["Statut"] == compliance.ROUGE and "Q5" in row["Résultat observé"]


def test_versions_incompatibles_detectees():
    old = dataclasses.replace(P, version="ANCIENNE_VERSION")
    row = compliance.control_table(D, old).set_index("Contrôle").loc["Versions conformes à l'application actuelle"]
    assert row["Statut"] == compliance.ROUGE


def test_reproductibilite_reelle_et_plage_complete():
    assert check_reproducible(P) is True
    rng = check_full_range(P)
    for q in ("Q5", "Q6", "Q7", "Q8", "Q13", "Q14", "Q15"):
        assert rng[q]["complet"] and rng[q]["observe"] == set(range(1, 9))
    for q in ("Q9", "Q10", "Q11", "Q12"):
        assert rng[q]["complet"] and rng[q]["observe"] == set(range(1, 6))


def test_absence_codes_extremes_sur_petit_echantillon_reste_grise_jamais_rouge():
    # Un tout petit échantillon peut légitimement ne jamais tirer les codes 1 ou 8 : ce n'est pas
    # une erreur du générateur (vérifiée séparément, en vert) — l'information reste grise.
    tiny = simulate(dataclasses.replace(P, n=3, seed=7, taux_manquants=0))
    ctrl = compliance.control_table(tiny, dataclasses.replace(P, n=3, seed=7, taux_manquants=0))
    info = ctrl.set_index("Contrôle").loc["Codes extrêmes observés dans l'échantillon actif (information)"]
    assert info["Statut"] == compliance.GRIS
    range_row = ctrl.set_index("Contrôle").loc[
        "Le générateur autorise tous les codes (1..8 ou 1..5), y compris les extrémités"]
    assert range_row["Statut"] == compliance.VERT  # jugé sur un tirage indépendant, pas sur `tiny`


def test_prep_base_toujours_grise_et_mentionne_les_limites():
    prep = compliance.prep_base_table(D, P)
    assert (prep["Statut"] == compliance.GRIS).all()
    flat = " ".join(prep.astype(str).values.ravel())
    assert "Test d'attention" in flat and "Absent" in flat
    assert "Q8" in flat and "binaire" in flat.lower()
    assert "Q9" in flat and "composite" in flat.lower()
    assert "L5" in flat
    assert all(f"{q} :" in flat for q in ("Q9", "Q10", "Q11", "Q12"))  # dénominateurs explicites


def test_effectifs_reconcilies_detecte_incoherence_artificielle(monkeypatch):
    import pandas as pd

    def fake_effectifs(df, mode):
        return pd.DataFrame([{"Question": q, "Applicable (posée à)": 1, "Répondu (n utilisé)": 0,
                             "Non applicable": 0, "Manquant (accidentel)": 0} for q in ALL_QS])
    monkeypatch.setattr(compliance, "effectifs", fake_effectifs)
    row = compliance.control_table(D, P).set_index("Contrôle").loc["Effectifs réconciliés avec les données"]
    assert row["Statut"] == compliance.ROUGE
