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


def test_export_echantillon_complet_respecte_le_mode_actif():
    # régression trouvée en navigateur : les boutons de téléchargement doivent lire le mode de
    # l'échantillon actif, pas le mode par défaut — sinon un CSV « sans branchement » affichait
    # encore des « Non applicable ». Garde statique : tout appel à csv_readable/csv_codes dans
    # app.py doit passer explicitement le mode (DF, MODE) / (FDF, MODE), jamais (DF) / (FDF) seuls.
    import re
    src = open("app.py", encoding="utf-8").read()
    bad = re.findall(r"ex\.csv_(?:readable|codes)\((?:DF|FDF)\)", src)
    assert not bad, f"appel(s) sans mode explicite : {bad}"

    at = fresh()
    at.radio(key="w_mode").set_value("sans_branchement").run()
    at.button(key="btn_repro").click().run()
    s = sample(at)
    assert s["params"].filter_mode == "sans_branchement"
    import exports as ex
    csv = ex.csv_readable(s["df"], s["params"].filter_mode).decode("utf-8-sig")
    assert "Non applicable" not in csv  # plus aucune question exclue dans ce mode (NaN résiduels = manquants)


def test_mode_sans_branchement_bascule_et_bandeau():
    at = fresh()
    assert sample(at)["params"].filter_mode == "simulation_filtree"
    at.radio(key="w_mode").set_value("sans_branchement").run()
    assert "non appliqu" in txt(at).lower()  # changer le mode est un réglage comme un autre
    at.button(key="btn_repro").click().run()
    assert sample(at)["params"].filter_mode == "sans_branchement"
    assert "hypothétiques" in txt(at).lower()
    for s in SECTIONS:
        goto(at, s)
    # 0 question non applicable en mode sans branchement
    from simulator import status_frame
    st = status_frame(sample(at)["df"], "sans_branchement")
    assert (st != "non_applicable").to_numpy().all()


def test_deux_modes_jamais_melanges_dans_un_echantillon():
    at = fresh()
    at.radio(key="w_mode").set_value("sans_branchement").run()
    at.button(key="btn_new").click().run()
    assert sample(at)["params"].filter_mode == "sans_branchement"
    at.radio(key="w_mode").set_value("simulation_filtree").run()
    at.button(key="btn_repro").click().run()
    assert sample(at)["params"].filter_mode == "simulation_filtree"  # l'échantillon actif est remplacé net


def test_echantillon_precedent_incompatible_est_signale_et_preserve():
    import dataclasses
    from simulator import SimParams, simulate

    old_params = dataclasses.replace(SimParams(), version="ANCIENNE_VERSION_6MOD")
    old_df = simulate(SimParams())
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["sample"] = {"params": old_params, "df": old_df, "readable": old_df,
                                  "codes": old_df, "sid": 1}
    at.run()
    assert not at.exception
    assert any("incompatible" in e.value.lower() for e in at.error)
    assert "incompatible_sample" in at.session_state
    assert at.session_state["incompatible_sample"]["params"].version == "ANCIENNE_VERSION_6MOD"
    regen = next(b for b in at.button if "8 modalités" in b.label)
    regen.click().run()
    assert not at.exception
    assert sample(at)["params"].version == "IA_ORIGINAL_15Q_8MOD"
