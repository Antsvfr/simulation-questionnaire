"""Parcours de l'interface Streamlit (AppTest) : état de session, filtres, fiche, périmètres."""
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from survey_config import BANNER


def fresh():
    at = AppTest.from_file("app.py", default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def sample(at):
    return at.session_state["sample"]


def txt(at):
    return " ".join([m.value for m in at.markdown] + [h.value for h in at.subheader] + [w.value for w in at.warning]
                    + [i.value for i in at.info] + [s.value for s in at.success] + [c.value for c in at.caption])


def test_generation_100_profils_et_mention():
    at = fresh()
    s = sample(at)
    assert len(s["df"]) == 100 and s["params"].seed == 42
    assert at.metric[0].value == "100"
    assert BANNER in txt(at)
    assert [m.label for m in at.metric][:5] == ["Profils synthétiques", "Utilisateurs / non-utilisateurs",
                                                 "Questionnaires complets",
                                                 "Réponses accidentellement manquantes",
                                                 "Réponses non applicables"]


def test_navigation_filtres_ne_regenere_pas():
    at = fresh()
    before, sid = sample(at)["df"].copy(), sample(at)["sid"]
    at.multiselect(key="f_use").set_value(["Non"]).run()
    at.radio(key="scope").set_value("filtered").run()
    at.radio(key="view_mode").set_value("Codes numériques").run()
    at.selectbox(key="sort_col").set_value("Q5").run()
    assert not at.exception
    assert sample(at)["sid"] == sid and sample(at)["df"].equals(before)
    assert "profils affichés sur 100 profils générés" in txt(at)


def test_reset_filtres():
    at = fresh()
    at.multiselect(key="f_use").set_value(["Non"]).run()
    at.text_input(key="f_search").set_value("SYN-0").run()
    assert "profils affichés sur 100" in txt(at) and "100 profils affichés" not in txt(at)
    at.button(key="btn_reset").click().run()
    assert at.multiselect(key="f_use").value == [] and at.text_input(key="f_search").value == ""
    assert "100 profils affichés sur 100 profils générés" in txt(at)


def test_filtre_sans_resultat():
    at = fresh()
    at.text_input(key="f_search").set_value("ZZZ-INEXISTANT").run()
    assert not at.exception
    assert "0 profils affichés sur 100 profils générés" in txt(at)
    assert "Aucun profil ne correspond à ces filtres" in txt(at)
    for scope_tab in ("filtered",):
        at.radio(key="scope").set_value(scope_tab).run()
        assert not at.exception
        assert "Aucun profil dans ce périmètre" in txt(at)


def test_parametres_non_appliques_puis_reproduction():
    at = fresh()
    s0 = sample(at)["df"].copy()
    at.slider(key="w_taux").set_value(30).run()
    assert "non encore appliqués" in txt(at)
    assert sample(at)["df"].equals(s0) and sample(at)["params"].taux_usage == 0.8   # rien n'a changé
    at.button(key="btn_repro").click().run()
    assert "non encore appliqués" not in txt(at)
    assert sample(at)["params"].taux_usage == 0.3 and sample(at)["params"].seed == 42
    d1 = sample(at)["df"].copy()
    at.button(key="btn_repro").click().run()
    assert sample(at)["df"].equals(d1)                 # même graine + mêmes paramètres = mêmes données


def test_nouvel_echantillon_nouvelle_graine():
    at = fresh()
    old_seed, old = sample(at)["params"].seed, sample(at)["df"].copy()
    at.button(key="btn_new").click().run()
    new_seed = sample(at)["params"].seed
    assert new_seed != old_seed and at.number_input(key="w_seed").value == new_seed
    assert not sample(at)["df"].equals(old)
    assert f"nouvelle graine : {new_seed}" in txt(at)


def test_parametres_actifs_conserves_apres_modification_des_reglages():
    at = fresh()
    at.slider(key="w_n").set_value(200).run()
    at.slider(key="w_manq").set_value(10).run()
    assert sample(at)["params"].n == 100 and len(sample(at)["df"]) == 100
    assert sample(at)["params"].taux_manquants == 0.02


def test_fiche_individuelle_et_toutes_les_reponses():
    at = fresh()
    ids = list(sample(at)["df"]["ID"])
    for pid in ("SYN-001", "SYN-003", ids[-1]):
        at.selectbox(key="fiche_id").set_value(pid).run()
        assert not at.exception
        assert f"Profil {pid}" in txt(at)
    # la dernière table de la fiche contient les 15 questions
    fiche = at.table[-1].value
    assert list(fiche.index) == [f"Q{i}" for i in range(1, 16)]
    assert set(fiche["Statut"]) <= {"Répondu", "Non applicable", "Réponse manquante"}
    assert "Information interne au modèle" in " ".join(m.value for m in at.markdown)


def test_toutes_les_fiches_sans_erreur_et_coherentes():
    at = fresh()
    from simulator import status_frame
    st_ = status_frame(sample(at)["df"])
    for pid in sample(at)["df"]["ID"][:100:7]:
        at.selectbox(key="fiche_id").set_value(pid).run()
        fiche = at.table[-1].value
        expected = st_.loc[sample(at)["df"]["ID"] == pid].iloc[0]
        names = {"répondu": "Répondu", "non_applicable": "Non applicable", "manquant": "Réponse manquante"}
        assert [names[expected[f"Q{i}"]] for i in range(1, 16)] == list(fiche["Statut"])


@pytest.mark.parametrize("taux", [0, 100])
def test_scenarios_0_et_100_pour_cent_utilisateurs(taux):
    at = fresh()
    at.slider(key="w_taux").set_value(taux).run()
    at.button(key="btn_repro").click().run()
    assert not at.exception, [e.value for e in at.exception]
    d = sample(at)["df"]
    assert (d.Q1 == 1).sum() == (100 if taux == 100 else 0)
    for scope in ("full", "filtered"):
        at.radio(key="scope").set_value(scope).run()
        assert not at.exception, [e.value for e in at.exception]


def test_donnees_manquantes_et_zero_manquant():
    at = fresh()
    at.slider(key="w_manq").set_value(0).run()
    at.button(key="btn_repro").click().run()
    assert at.metric[3].value == "0" and at.metric[2].value == "100 / 100"
    at.slider(key="w_manq").set_value(30).run()
    at.button(key="btn_repro").click().run()
    assert int(at.metric[3].value) > 50 and not at.exception


def test_modes_d_affichage():
    at = fresh()
    for mode in ("Codes numériques", "Réponses lisibles"):
        at.radio(key="view_mode").set_value(mode).run()
        assert not at.exception
    at.radio(key="view_mode").set_value("Codes numériques").run()
    at.checkbox(key="show_status").check().run()
    assert not at.exception
