"""Parcours de l'interface Streamlit (AppTest) : navigation, état de session, filtres, analyses."""
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from survey_config import BANNER

SECTIONS = ["Vue d'ensemble", "Échantillon", "Analyse par question", "Comparaisons",
           "Relations entre réponses", "Exports et méthode"]


def fresh():
    at = AppTest.from_file("app.py", default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def goto(at, section):
    at.segmented_control(key="nav").set_value(section).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def sample(at):
    return at.session_state["sample"]


def txt(at):
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption]
                    + [w.value for w in at.warning] + [i.value for i in at.info]
                    + [s.value for s in at.success] + [h.value for h in at.subheader])


def test_generation_100_profils_et_mention():
    at = fresh()
    s = sample(at)
    assert len(s["df"]) == 100 and s["params"].seed == 42
    assert "Données synthétiques" in txt(at)  # mention discrète et permanente


def test_toutes_les_sections_sans_erreur():
    at = fresh()
    for s in SECTIONS:
        goto(at, s)


def test_navigation_et_filtres_ne_regenerent_pas():
    at = fresh()
    before, sid = sample(at)["df"].copy(), sample(at)["sid"]
    at.multiselect(key="f_use").set_value(["Non"]).run()
    for s in SECTIONS:
        goto(at, s)
    assert sample(at)["sid"] == sid and sample(at)["df"].equals(before)
    assert "sélectionnés sur" in txt(at)


def test_reset_filtres():
    at = fresh()
    at.multiselect(key="f_use").set_value(["Non"]).run()
    at.text_input(key="f_search").set_value("SYN-0").run()
    at.button(key="btn_reset").click().run()
    assert at.multiselect(key="f_use").value == [] and at.text_input(key="f_search").value == ""
    assert "100 profils sélectionnés sur 100" in txt(at)


def test_filtre_sans_resultat_affiche_message():
    at = fresh()
    at.text_input(key="f_search").set_value("ZZZ-INEXISTANT").run()
    assert "0 profils sélectionnés sur 100" in txt(at)
    for s in SECTIONS[:-1]:  # Exports a ses propres messages par bloc
        goto(at, s)
        assert "Aucun profil" in txt(at)


def test_parametres_non_appliques_puis_reproduction_meme_graine():
    at = fresh()
    d0 = sample(at)["df"].copy()
    at.slider(key="w_taux").set_value(30).run()
    assert "non appliqu" in txt(at).lower()
    assert sample(at)["df"].equals(d0) and sample(at)["params"].taux_usage == 0.8
    at.button(key="btn_repro").click().run()
    assert "non appliqu" not in txt(at).lower()
    assert sample(at)["params"].taux_usage == 0.3 and sample(at)["params"].seed == 42
    d1 = sample(at)["df"].copy()
    at.button(key="btn_repro").click().run()
    assert sample(at)["df"].equals(d1)  # même graine + mêmes paramètres = mêmes données


def test_nouvel_echantillon_nouvelle_graine():
    at = fresh()
    old_seed, old = sample(at)["params"].seed, sample(at)["df"].copy()
    at.button(key="btn_new").click().run()
    new_seed = sample(at)["params"].seed
    assert new_seed != old_seed and at.number_input(key="w_seed").value == new_seed
    assert not sample(at)["df"].equals(old)
    assert f"nouvelle graine : {new_seed}" in txt(at)


def test_fiche_individuelle():
    at = fresh()
    goto(at, "Échantillon")
    at.segmented_control(key="ech_sub").set_value("Réponses individuelles").run()
    for pid in ("SYN-001", "SYN-050"):
        at.selectbox(key="fiche_id").set_value(pid).run()
        assert not at.exception
        assert pid in txt(at)
    fiche = at.table[-1].value
    assert list(fiche.index) == [f"Q{i}" for i in range(1, 16)]
    assert set(fiche["Statut"]) <= {"Répondu", "Non applicable", "Réponse manquante"}
    # paramètres internes masqués par défaut
    assert "Profil latent simulé" not in txt(at)
    at.checkbox(key="show_internal").check().run()
    assert "Profil latent simulé" in txt(at)


def test_analyse_par_question_nominale_et_ordinale():
    at = fresh()
    goto(at, "Analyse par question")
    at.selectbox(key="q_group_sel").set_value("Profil et usage").run()
    at.selectbox(key="q_select").set_value("Q3").run()
    assert "aucune moyenne" in txt(at).lower()
    at.selectbox(key="q_group_sel").set_value("Apprentissage et confiance").run()
    at.selectbox(key="q_select").set_value("Q9").run()
    assert "médiane" in txt(at).lower()
    assert "analysis_export" in at.session_state


def test_comparaison_indisponible_pour_question_reservee_aux_utilisateurs():
    at = fresh()
    goto(at, "Comparaisons")
    at.selectbox(key="cmp_q").set_value("Q9").run()
    at.selectbox(key="cmp_group").set_value("Q1").run()
    assert "non disponible" in txt(at)
    at.selectbox(key="cmp_group").set_value("Q4").run()
    assert "non disponible" not in txt(at)


def test_correlation_deux_questions():
    at = fresh()
    goto(at, "Relations entre réponses")
    at.selectbox(key="corr_a").set_value("Q5").run()
    at.selectbox(key="corr_b").set_value("Q7").run()
    assert "causalité" in txt(at).lower()
    assert "latent" in txt(at).lower() or "lien" in txt(at).lower()


@pytest.mark.parametrize("taux", [0, 100])
def test_scenarios_0_et_100_pour_cent_utilisateurs(taux):
    at = fresh()
    at.slider(key="w_taux").set_value(taux).run()
    at.button(key="btn_repro").click().run()
    d = sample(at)["df"]
    assert (d.Q1 == 1).sum() == (100 if taux == 100 else 0)
    for s in SECTIONS:
        goto(at, s)


def test_export_echantillon_complet_filtre_et_analyse_courante():
    at = fresh()
    goto(at, "Analyse par question")
    at.selectbox(key="q_group_sel").set_value("Apprentissage et confiance").run()
    at.selectbox(key="q_select").set_value("Q5").run()
    goto(at, "Exports et méthode")
    assert len(at.tabs) >= 1  # blocs séparés présents
    assert "analysis_export" in at.session_state
    assert at.session_state["analysis_export"]["name"].startswith("distribution_Q5")


def test_donnees_manquantes_zero_et_non_nul():
    at = fresh()
    at.slider(key="w_manq").set_value(0).run()
    at.button(key="btn_repro").click().run()
    assert sample(at)["params"].taux_manquants == 0
    at.slider(key="w_manq").set_value(20).run()
    at.button(key="btn_repro").click().run()
    assert sample(at)["params"].taux_manquants == 0.2
    assert not at.exception
