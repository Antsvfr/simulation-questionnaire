"""Simulateur de questionnaire « IA dans l'éducation » — Streamlit + pandas + Plotly.

Lancement : streamlit run app.py
Aucune connexion réseau, aucun envoi vers Qualtrics ou un autre service.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import compliance
import exports as ex
from simulator import SimParams, effectifs, programmed_link_note, simulate, status_frame
from survey_config import (AGREE_QS, ALL_QS, BANNER, CATEGORICAL, FILTER_MODE_LABELS, FILTER_MODES,
                           GROUPS, HYPOTHETICAL_NOTE, MODE_FILTRE, MODE_LIBRE, QUESTIONNAIRE_VERSION,
                           QUESTIONS, SCALE8_QS, SCALE_QS, SHORT_HDR, filters_table, group_of,
                           is_user_only, scale_help, short)
from views import (COL_MISS, COL_NA, COL_NB_MISS, COL_STATUT_Q, COMPLET, LATENT_COL, MIN_PAIRS,
                   MISS_TXT, NA_TXT, SMALL_N_RULE, VARS, Filters, codes_frame, comparison_available,
                   comparison_distribution, comparison_table, composition_table, counts,
                   filter_mask, options_for, overview_text, question_distribution,
                   question_overview, question_summary_stats, readable_frame, safe_spearman,
                   spearman_pair)

st.set_page_config(page_title="Simulation questionnaire IA & éducation", page_icon="🧪",
                   layout="wide")

SEQ8 = ["#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#d1e5f0", "#92c5de", "#4393c3", "#2166ac"]  # 1→8
SEQ5 = ["#b2182b", "#ef8a62", "#f0c330", "#67a9cf", "#2166ac"]                 # 1→5, neutre = or (≠ gris « absent »)
CAT_SEQ = px.colors.qualitative.Safe
OBS_COLOR, THEORY_COLOR = "#2166ac", "#9ca3af"
MINI_BANNER = "Données synthétiques — simulation pédagogique"

st.markdown("""<style>
.block-container{max-width:1280px;padding-top:1.4rem;padding-bottom:2rem}
[data-testid="stMetricValue"]{font-size:1.6rem}
[data-testid="stMetricLabel"] p{font-size:.82rem;color:#555}
.badge-internal{display:inline-block;background:#f3f0ff;border:1px solid #c9bdf5;border-radius:4px;
  padding:.1rem .5rem;font-size:.82rem;color:#4b3b8f}
.small-n{color:#9a6700;font-weight:600}
.reading-aid{background:#f3f6fb;border-radius:6px;padding:.6rem .9rem;font-size:.92rem;margin-top:.4rem}
hr{margin:.6rem 0}
@media (max-width:640px){.block-container{padding:.8rem .6rem}[data-testid="stMetricValue"]{font-size:1.25rem}}
</style>""", unsafe_allow_html=True)

SECTIONS = ["Vue d'ensemble", "Échantillon", "Analyse par question", "Comparaisons",
           "Relations entre réponses", "Exports et méthode"]
ICONS = {"Vue d'ensemble": "🏠", "Échantillon": "🧑‍🤝‍🧑", "Analyse par question": "❓",
         "Comparaisons": "🔀", "Relations entre réponses": "🔗", "Exports et méthode": "📦"}


# ============================================================================ état de session
WIDGET_DEFAULTS = {"w_n": 100, "w_seed": 42, "w_taux": 80, "w_manq": 2, "w_a1": 10, "w_a2": 62,
                   "w_a3": 20, "w_a4": 8, "w_force": 1.0, "w_l10": 0.0, "w_l10a": 0.0,
                   "w_mode": MODE_FILTRE}
FILTER_DEFAULTS = {"f_search": "", "f_age": [], "f_genre": [], "f_niv": [], "f_use": [],
                   "f_comp": "Tous"}
OTHER_DEFAULTS = {"nav": SECTIONS[0], "ech_sub": "Composition", "show_internal": False,
                  "rv_mode": "Réponses lisibles"}


def draft_params():
    """Paramètres tels que saisis dans le panneau de configuration (non encore appliqués)."""
    s = st.session_state
    ages = (s.w_a1, s.w_a2, s.w_a3, s.w_a4)
    if sum(ages) == 0:
        return None
    return SimParams(n=int(s.w_n), seed=int(s.w_seed), taux_usage=s.w_taux / 100, age_weights=ages,
                     taux_manquants=s.w_manq / 100, force_latent=float(s.w_force),
                     lien_q10_latent=float(s.w_l10), lien_q10_age=float(s.w_l10a),
                     filter_mode=s.w_mode)


def generate(params: SimParams):
    """Seule fonction qui remplace l'échantillon actif (paramètres + données + vues dérivées)."""
    df = simulate(params)
    st.session_state.sample = {
        "params": params, "df": df, "readable": readable_frame(df, params.filter_mode),
        "codes": codes_frame(df, params.filter_mode),
        "sid": st.session_state.get("sample", {}).get("sid", 0) + 1}
    st.session_state.pop("analysis_export", None)


def cb_reproduce():
    p = draft_params()
    if p:
        generate(p)
        st.session_state.seed_msg = f"Échantillon reproduit avec la graine {p.seed}."


def cb_new():
    p = draft_params()
    if p:
        rng = np.random.default_rng()
        new = int(rng.integers(0, 10**6))
        while new == st.session_state.sample["params"].seed:
            new = int(rng.integers(0, 10**6))
        st.session_state.w_seed = new
        generate(draft_params())
        st.session_state.seed_msg = f"Nouvel échantillon généré avec une nouvelle graine : {new}."


def cb_reset_filters():
    for k, v in FILTER_DEFAULTS.items():
        st.session_state[k] = list(v) if isinstance(v, list) else v


def goto(section):
    st.session_state["nav"] = section


for k, v in {**WIDGET_DEFAULTS, **FILTER_DEFAULTS, **OTHER_DEFAULTS}.items():
    st.session_state.setdefault(k, list(v) if isinstance(v, list) else v)

# Incompatibilité de version : un échantillon généré sous une structure de questionnaire différente
# (p. ex. échelles à 6 niveaux d'une version antérieure) n'est jamais réinterprété silencieusement
# sous la structure actuelle (8 niveaux). Il est conservé tel quel, de côté, et un nouvel échantillon
# doit être généré explicitement.
if "sample" in st.session_state:
    _old_version = getattr(st.session_state.sample.get("params"), "version", None)
    if _old_version != QUESTIONNAIRE_VERSION:
        st.session_state["incompatible_sample"] = st.session_state.pop("sample")

if "sample" not in st.session_state and "incompatible_sample" not in st.session_state:
    generate(draft_params())

if "sample" not in st.session_state:
    old = st.session_state["incompatible_sample"]
    old_v = getattr(old["params"], "version", "antérieure à cette fonctionnalité")
    st.error(
        "⚠️ **Échantillon précédent incompatible.** Il a été généré sous une version différente du "
        f"questionnaire (**{old_v}**), avec une structure de modalités différente de la version "
        f"actuelle (**{QUESTIONNAIRE_VERSION}**, 8 modalités distinctes pour Q5–Q8 et Q13–Q15). Pour "
        "ne jamais confondre des codes qui ne signifient pas la même chose, ces anciennes réponses ne "
        "sont **pas** converties automatiquement. Elles restent disponibles ci-dessous pour mémoire.")
    with st.expander("Paramètres de l'ancien échantillon (conservé, non utilisé)"):
        st.write(old["params"])
        st.caption(f"{len(old['df'])} profils générés sous cette ancienne version.")
    if st.button("🎲 Générer un nouvel échantillon (version actuelle, 8 modalités)", type="primary"):
        generate(draft_params())
        st.session_state.pop("incompatible_sample", None)
        st.rerun()
    st.stop()

S = st.session_state.sample
params, DF, READ, CODES = S["params"], S["df"], S["readable"], S["codes"]
N = len(DF)
MODE = params.filter_mode


def current_filters() -> Filters:
    s = st.session_state
    return Filters(s.f_search, list(s.f_age), list(s.f_genre), list(s.f_niv), list(s.f_use), s.f_comp)


FILT = current_filters()
MASK = filter_mask(READ, FILT)
FDF = DF[MASK]
RFDF = READ[MASK]
NF = len(FDF)


def set_export(name: str, table: pd.DataFrame):
    """Mémorise le dernier tableau d'analyse consulté, exportable depuis « Exports et méthode »."""
    st.session_state["analysis_export"] = {"name": name, "table": table}


# ============================================================================ utilitaires d'affichage
def style(fig, title, height=380):
    fig.update_layout(title=dict(text=title, x=0.0, font=dict(size=15)), height=height,
                      margin=dict(t=56, b=40, l=50, r=20), legend_title_text="", template="plotly_white")
    return fig


def show(fig, key):
    st.plotly_chart(fig, width="stretch", key=key,
                    config={"toImageButtonOptions": {"filename": "SIMULATION_SYNTHETIQUE_graphique"}})


def need_rows(d, msg=None) -> bool:
    if len(d) == 0:
        st.warning(msg or "Aucun profil dans la sélection actuelle. Ouvrez « Filtres » dans la barre "
                   "latérale et cliquez sur « Réinitialiser les filtres », ou élargissez votre sélection.")
        return True
    return False


_STATUT_CSS = {compliance.VERT: "background-color:#C6EFCE;color:#006100;font-weight:600",
              compliance.ROUGE: "background-color:#FFC7CE;color:#9C0006;font-weight:600",
              compliance.GRIS: "background-color:#D9D9D9;color:#404040;font-weight:600"}


def style_statut(v):
    return _STATUT_CSS.get(v, "")


def ordinal_bar(d: pd.DataFrame, q: str) -> go.Figure:
    spec = QUESTIONS[q]
    colors = SEQ8 if spec["levels"] == 8 else SEQ5
    t = question_distribution(d, q)
    fig = go.Figure(go.Bar(x=t["Modalité"], y=t["% des réponses valides"], marker_color=colors,
                           text=t["Effectif"].map(lambda v: f"{v}"), textposition="outside",
                           hovertemplate="%{x}<br>%{y:.1f} %% des réponses valides<extra></extra>"))
    fig.update_layout(xaxis_title="", yaxis_title="% des réponses valides",
                      yaxis_range=[0, max(5, t["% des réponses valides"].max() * 1.2 + 5)])
    fig.update_xaxes(tickangle=0)
    return fig


def nominal_bar(d: pd.DataFrame, q: str) -> go.Figure:
    t = question_distribution(d, q)
    fig = go.Figure(go.Bar(x=t["Modalité"], y=t["% des réponses valides"],
                           marker_color=CAT_SEQ[:len(t)],
                           text=t["Effectif"].map(lambda v: f"{v}"), textposition="outside"))
    fig.update_layout(xaxis_title="", yaxis_title="% des réponses valides",
                      yaxis_range=[0, max(5, t["% des réponses valides"].max() * 1.2 + 5)])
    return fig


def mini_composition(d, q, height=230):
    t, n_valid, _ = composition_table(d, q)
    if n_valid == 0:
        st.caption(f"{q} : aucune réponse valide dans la sélection actuelle.")
        return
    fig = go.Figure(go.Bar(x=t["Modalité"], y=t["% observé"], marker_color=CAT_SEQ[:len(t)],
                           text=t["% observé"].map(lambda v: f"{v:.0f} %")))
    fig.update_layout(title=dict(text=f"{q} — {VARS[q]}", font=dict(size=13)), height=height,
                      margin=dict(t=36, b=30, l=36, r=10), yaxis_title=None, xaxis_title=None,
                      template="plotly_white")
    fig.update_xaxes(tickfont=dict(size=10))
    show(fig, f"mini_{q}")


# ============================================================================ barre latérale
sb = st.sidebar
sb.caption(f"🔒 {MINI_BANNER}")
sb.markdown(f"**Échantillon actif : {N} profils** · graine **{params.seed}**  \n"
           f"Version **{params.version}** · {FILTER_MODE_LABELS.get(MODE, MODE)}")
if st.session_state.get("seed_msg"):
    sb.success(st.session_state.pop("seed_msg"))

with sb.expander("⚙️ Configurer la simulation", expanded=False):
    st.caption("Modifier ces réglages ne change rien tant que vous n'avez pas cliqué sur un bouton "
               "de génération ci-dessous.")
    st.radio("Mode de parcours du questionnaire", FILTER_MODES, key="w_mode",
             format_func=lambda m: FILTER_MODE_LABELS[m],
             help="« Simulation avec filtres » : conventions actuelles (certaines questions exclues "
             "pour les non-utilisateurs, voir le détail dans Exports et méthode). « Questionnaire sans "
             "branchement » : toutes les questions posées à tous ; les réponses des non-utilisateurs "
             "aux questions d'expérience sont alors hypothétiques. Le texte fourni ne prouve aucun "
             "branchement Qualtrics réel : les deux modes sont des choix explicites, pas un fait "
             "démontré du questionnaire original.")
    st.slider("Taille de l'échantillon", 20, 500, key="w_n", step=10)
    st.number_input("Graine aléatoire", 0, 10**6, key="w_seed")
    st.slider("Taux d'utilisation de l'IA visé (Q1 = Oui)", 0, 100, key="w_taux", step=5, format="%d %%")
    st.slider("Non-réponse accidentelle (cellules applicables)", 0, 30, key="w_manq", format="%d %%")
    st.caption("Répartition d'âge visée (Q2), normalisée automatiquement")
    st.slider("Moins de 18 ans", 0, 100, key="w_a1")
    st.slider("18–24 ans", 0, 100, key="w_a2")
    st.slider("25–34 ans", 0, 100, key="w_a3")
    st.slider("35 ans et plus", 0, 100, key="w_a4")
    with st.expander("Associations programmées (avancé)"):
        st.slider("Force du lien trait latent → Q5, Q7, Q9, Q12–Q15", 0.0, 1.5, key="w_force", step=0.1)
        st.slider("Lien trait latent → Q10 (0 = aucune association)", -1.0, 1.0, key="w_l10", step=0.1)
        st.slider("Lien âge → Q10 (0 = aucune association)", -0.5, 0.5, key="w_l10a", step=0.05)

    DRAFT = draft_params()
    if DRAFT is None:
        st.warning("Au moins une tranche d'âge doit être supérieure à 0.")
    elif DRAFT != params:
        st.warning("⚠️ **Modifications non appliquées** : l'échantillon affiché reste celui généré "
                   "avec les paramètres précédents.")
    st.button("🔁 Reproduire avec cette graine", key="btn_repro", on_click=cb_reproduce,
              disabled=DRAFT is None, width="stretch", help="Régénère avec les réglages ci-dessus ET "
              "la graine saisie (mêmes paramètres + même graine = mêmes données).")
    st.button("🎲 Générer un nouvel échantillon", key="btn_new", on_click=cb_new, disabled=DRAFT is None,
              width="stretch", type="primary", help="Tire une nouvelle graine (affichée ensuite) puis "
              "génère l'échantillon avec les réglages ci-dessus.")

sb.markdown("### 🔎 Filtres")
sb.text_input("Rechercher un identifiant", key="f_search", placeholder="ex. SYN-042")
sb.multiselect("Tranche d'âge", options_for("Q2"), key="f_age", placeholder="Toutes")
sb.multiselect("Genre", options_for("Q3"), key="f_genre", placeholder="Tous")
sb.multiselect("Niveau d'études", options_for("Q4"), key="f_niv", placeholder="Tous")
sb.multiselect("Utilise l'IA (Q1)", options_for("Q1"), key="f_use", placeholder="Tous")
sb.radio("Questionnaires", ["Tous", "Complets", "Incomplets"], key="f_comp", horizontal=True)
sb.markdown(f"**{NF} profils sélectionnés sur {N}**")
sb.caption(f"Filtres actifs : {FILT.describe()}" if FILT.active() else "Aucun filtre actif.")
sb.button("↺ Réinitialiser les filtres", key="btn_reset", on_click=cb_reset_filters, width="stretch")
sb.divider()
sb.caption("Aucune connexion à Qualtrics : rien n'est envoyé ni collecté.")

# ============================================================================ en-tête + navigation
h1, h2 = st.columns([3, 2])
h1.markdown("## 🧪 Simulateur de questionnaire — IA dans l'éducation")
h2.markdown(f"<div style='text-align:right;padding-top:.6rem;color:#8a6d00;font-size:.9rem'>"
           f"🔒 {MINI_BANNER}</div>", unsafe_allow_html=True)

nav = st.segmented_control("Section", SECTIONS, key="nav", required=True,
                           label_visibility="collapsed",
                           format_func=lambda s: f"{ICONS[s]} {s}")
if MODE == MODE_LIBRE:
    st.warning(f"🧭 {HYPOTHETICAL_NOTE}")
st.divider()

# ============================================================================ A. Vue d'ensemble
if nav == "Vue d'ensemble":
    C = counts(FDF, MODE)
    m = st.columns(3)
    m[0].metric("Profils générés", N, help="Nombre total de profils synthétiques produits par la "
               "dernière génération, avant tout filtre.")
    m[1].metric("Profils sélectionnés", NF, help="Profils restant après application des filtres actifs "
               "(barre latérale). C'est le dénominateur des indicateurs ci-dessous.")
    m[2].metric("Questionnaires complets", f"{C['complets']} / {C['profils']}" if C["profils"] else "—",
               help="Aucune réponse accidentellement manquante parmi les questions applicables à ce "
               "profil. Une question non applicable n'est jamais comptée comme un oubli.")
    m2 = st.columns(3)
    pct_use = (C["utilisateurs"] / C["profils"] * 100) if C["profils"] else 0
    m2[0].metric("Utilisateurs de l'IA", f"{pct_use:.0f} %", help=f"{C['utilisateurs']} profils sur "
               f"{C['profils']} sélectionnés ont répondu « Oui » à Q1.")
    m2[1].metric("Réponses manquantes", C["manquantes"], help="Réponses accidentellement absentes à "
               "des questions pourtant applicables au profil (non-réponse simulée).")
    m2[2].metric("Réponses non applicables", C["non_applicables"], help="Questions non posées à ce "
               "profil (p. ex. Q8 pour un non-utilisateur) : ce n'est pas un oubli, c'est une règle "
               "définie pour la simulation.")

    if not need_rows(FDF):
        st.markdown(f"<div class='reading-aid'>{overview_text(C)}</div>", unsafe_allow_html=True)

        st.markdown("#### Composition de l'échantillon sélectionné")
        cols = st.columns(4)
        for i, q in enumerate(["Q2", "Q3", "Q4", "Q1"]):
            with cols[i]:
                mini_composition(FDF, q)
        st.caption("Pourcentages calculés sur les réponses valides de chaque variable (voir « Échantillon » "
                   "pour le détail et les effectifs).")

        st.markdown("#### Aller plus loin")
        n1, n2, n3, n4 = st.columns(4)
        n1.button("🧑‍🤝‍🧑 Voir l'échantillon", on_click=goto, args=("Échantillon",), width="stretch")
        n2.button("❓ Analyser une question", on_click=goto, args=("Analyse par question",), width="stretch")
        n3.button("🔀 Comparer des groupes", on_click=goto, args=("Comparaisons",), width="stretch")
        n4.button("🔗 Voir les relations", on_click=goto, args=("Relations entre réponses",), width="stretch")

# ============================================================================ B. Échantillon
elif nav == "Échantillon":
    st.segmented_control("Vue", ["Composition", "Réponses individuelles"], key="ech_sub",
                         label_visibility="collapsed")

    if st.session_state.ech_sub == "Composition":
        if not need_rows(FDF):
            st.caption(f"Effectifs et pourcentages calculés sur les {NF} profils sélectionnés "
                       "(dénominateur : réponses valides de chaque variable).")
            cols = st.columns(2)
            for i, q in enumerate(["Q2", "Q3", "Q4", "Q1"]):
                t, n_valid, n_miss = composition_table(FDF, q)
                with cols[i % 2]:
                    st.markdown(f"##### {q} — {VARS[q]}")
                    st.caption(f"Dénominateur : {n_valid} réponses valides"
                               + (f" · {n_miss} manquante(s) exclue(s)" if n_miss else ""))
                    if n_valid == 0:
                        st.info("Aucune réponse valide pour cette variable dans la sélection actuelle.")
                        continue
                    show(style(nominal_bar(FDF, q), f"{q} (n={n_valid})", 300), f"comp_{q}")
                    tt = t.copy()
                    tt["% observé"] = tt["% observé"].map("{:.1f} %".format)
                    st.dataframe(tt, hide_index=True, width="stretch")

            with st.expander("📐 Proportions théoriques utilisées pour la génération"):
                st.caption("Ces probabilités décrivent **tout l'échantillon généré** (les N profils, "
                           "avant filtre), pas la sélection filtrée ci-dessus. Dans un tirage aléatoire "
                           "de taille finie, les proportions obtenues fluctuent autour des probabilités "
                           "visées — ce n'est pas une erreur du simulateur.")
                from simulator import expected_distributions
                exp = expected_distributions(params)
                for q in ["Q2", "Q3", "Q4", "Q1"]:
                    t_full, n_full, _ = composition_table(DF, q, params)
                    tt = t_full.rename(columns={"% observé": "% observé (échantillon complet)"})
                    st.markdown(f"**{q} — {VARS[q]}**")
                    st.dataframe(tt, hide_index=True, width="stretch")
            set_export(f"composition_{FILT.describe() if FILT.active() else 'ensemble'}",
                      pd.concat([composition_table(FDF, q)[0].assign(Question=q) for q in VARS], ignore_index=True))

    else:  # Réponses individuelles
        if not need_rows(FDF):
            v1, v2, v3 = st.columns([2, 2, 2])
            v1.radio("Affichage", ["Réponses lisibles", "Codes numériques"], key="rv_mode", horizontal=True)
            sort_col = v2.selectbox("Trier par", ["ID"] + ALL_QS + [COL_NB_MISS], key="sort_col")
            asc = v3.radio("Ordre", ["Croissant", "Décroissant"], key="sort_order",
                           horizontal=True) == "Croissant"
            st.checkbox("Afficher les paramètres internes (profil latent simulé)", key="show_internal",
                       help="Variable interne au modèle de simulation, non observable dans un vrai "
                       "questionnaire. Masquée par défaut pour ne pas la confondre avec une réponse.")

            table = (RFDF if st.session_state.rv_mode == "Réponses lisibles" else CODES.loc[MASK]).copy()
            order = CODES.loc[MASK, sort_col] if sort_col != "ID" else table["ID"]
            table = table.loc[order.sort_values(ascending=asc, na_position="last", kind="stable").index]
            drop_cols = [] if st.session_state.show_internal else [LATENT_COL]
            if st.session_state.rv_mode == "Codes numériques":
                drop_cols += [f"{q}_statut" for q in ALL_QS]
            table = table.drop(columns=[c for c in drop_cols if c in table.columns])

            cfg = {"ID": st.column_config.TextColumn("ID synthétique", pinned=True),
                  COL_STATUT_Q: st.column_config.TextColumn("Statut du questionnaire", width="small")}
            for q in ALL_QS:
                lab = f"{q} · {SHORT_HDR[q]}"
                cfg[q] = (st.column_config.NumberColumn(lab, help=scale_help(q), format="%d")
                          if st.session_state.rv_mode == "Codes numériques"
                          else st.column_config.TextColumn(lab, help=scale_help(q)))
            st.dataframe(table, hide_index=True, width="stretch", height=420, column_config=cfg)
            st.caption(f"« {NA_TXT} » (question non posée) et « {MISS_TXT} » (question applicable sans "
                       "réponse) sont toujours distincts dans l'affichage lisible. Survolez un en-tête "
                       "pour voir la question complète et ses modalités.")
            st.caption(f"Questions à 8 modalités distinctes : {', '.join(SCALE8_QS)}. "
                       f"Questions à 5 modalités d'accord : {', '.join(AGREE_QS)}.")
            set_export("reponses_individuelles", table)

            st.markdown("#### 🪪 Fiche individuelle")
            pid = st.selectbox("Choisir un profil pour voir le détail de ses réponses", list(FDF["ID"]),
                               key="fiche_id")
            if pid:
                row = DF[DF["ID"] == pid].iloc[0]
                rrow = READ[READ["ID"] == pid].iloc[0]
                st.markdown(f"##### Profil {pid}")
                c = st.columns(4)
                c[0].markdown(f"**Utilise l'IA**  \n{rrow['Q1']}")
                c[1].markdown(f"**Âge**  \n{rrow['Q2']}")
                c[2].markdown(f"**Genre**  \n{rrow['Q3']}")
                c[3].markdown(f"**Niveau d'études**  \n{rrow['Q4']}")
                st.caption(f"Questionnaire : {rrow[COL_STATUT_Q]}"
                          + (f" — manquantes : {rrow[COL_MISS]}" if rrow[COL_MISS] else ""))
                if st.session_state.show_internal:
                    st.markdown(f"<span class='badge-internal'>⚙ Profil latent simulé (interne) : "
                               f"{rrow[LATENT_COL]}</span>", unsafe_allow_html=True)
                stat = status_frame(DF[DF["ID"] == pid], MODE).iloc[0]
                lines = []
                for q in ALL_QS:
                    spec = QUESTIONS[q]
                    statut = {"répondu": "Répondu", "non_applicable": NA_TXT, "manquant": MISS_TXT}[stat[q]]
                    lines.append({"Q": q, "Question": spec["text"], "Réponse":
                                 rrow[q] if stat[q] == "répondu" else "—", "Statut": statut})
                st.table(pd.DataFrame(lines).set_index("Q"))
                st.caption("Aucun nom, e-mail ni biographie n'est généré ; aucune réponse n'est expliquée "
                          "individuellement — ce sont des tirages aléatoires du modèle.")

# ============================================================================ C. Analyse par question
elif nav == "Analyse par question":
    gcol, qcol = st.columns([2, 3])
    group = gcol.selectbox("Thème", [g for g, _ in GROUPS], key="q_group_sel")
    opts = [q for g, qs in GROUPS if g == group for q in qs]
    q = qcol.selectbox("Question", opts, format_func=short, key="q_select")

    if not need_rows(FDF):
        spec = QUESTIONS[q]
        st.markdown(f"### {q} — {spec['label']}")
        st.markdown(f"**Texte :** {spec['text']}" + (" *(intitulé du questionnaire)*" if spec["text_is_title"] else ""))
        if spec["kind"] == "single":
            st.caption("Modalités : " + " / ".join(spec["options"]))
        else:
            st.caption(f"{spec['levels']} modalités distinctes (code → libellé) : " +
                      " ; ".join(f"{k} → {v}" for k, v in spec["anchors"].items()))

        ov = question_overview(FDF, q, MODE)
        c = st.columns(3)
        c[0].metric("Réponses valides", ov["valides"], help="Sur les profils sélectionnés.")
        c[1].metric("Manquantes", ov["manquants"], help="Question applicable, restée sans réponse.")
        c[2].metric("Non applicables", ov["non_applicables"], help="Question non posée à ces profils.")

        t = question_distribution(FDF, q)
        if ov["valides"] == 0:
            st.info("Aucune réponse valide à cette question dans la sélection actuelle.")
        else:
            fig = nominal_bar(FDF, q) if spec["kind"] == "single" else ordinal_bar(FDF, q)
            show(style(fig, f"Distribution de {q} (n={ov['valides']})", 380), "qdist")

            st.markdown("**Tableau exact**")
            tt = t.copy()
            tt["% des réponses valides"] = tt["% des réponses valides"].map("{:.1f} %".format)
            st.dataframe(tt.drop(columns=["Code"]), hide_index=True, width="stretch")

            top = t.loc[t["Effectif"].idxmax()]
            aid = (f"Dans cet échantillon simulé, {int(top['Effectif'])} profils sur {ov['valides']} "
                  f"réponses valides ont choisi « {top['Modalité']} ».")
            if spec["kind"] != "single":
                stats = question_summary_stats(FDF, q)
                aid += (f" La médiane est {stats['mediane']:g}/{stats['levels']}.")
                with st.expander("Afficher une moyenne (convention : score traité comme approximativement métrique)"):
                    st.caption(f"Bornes de l'échelle : 1 à {stats['levels']}. Convention : les {stats['levels']} "
                              "positions sont traitées comme des écarts à peu près égaux pour pouvoir "
                              "calculer une moyenne ; rien ne garantit que ce soit exact pour ce type de "
                              "jugement.")
                    st.metric(f"Moyenne (sur {stats['n']} réponses)", f"{stats['moyenne']:.2f} / {stats['levels']}")
            st.markdown(f"<div class='reading-aid'>{aid}</div>", unsafe_allow_html=True)
            if spec["kind"] == "single":
                st.caption("Variable nominale : effectifs et pourcentages uniquement, aucune moyenne n'est "
                          "calculée.")
            set_export(f"distribution_{q}", t)

# ============================================================================ D. Comparaisons
elif nav == "Comparaisons":
    c1, c2 = st.columns(2)
    q = c1.selectbox("Question à analyser", ALL_QS, format_func=short, key="cmp_q")
    group_opts = [g for g in CATEGORICAL if g != q]
    group_q = c2.selectbox("Regrouper par", group_opts, format_func=short, key="cmp_group")

    if not need_rows(FDF):
        if not comparison_available(q, group_q, MODE):
            st.info(f"**Comparaison non disponible.** {short(q)} n'est posée qu'aux utilisateurs de "
                    f"l'IA : comparer ses réponses selon « utilise l'IA » (Q1) n'a pas de sens, puisque "
                    f"les non-utilisateurs n'ont par construction aucune réponse applicable. Choisissez "
                    f"un autre regroupement (âge, genre, niveau d'études).")
            ct = comparison_table(FDF, q, group_q, MODE)
            st.dataframe(ct, hide_index=True, width="stretch")
        else:
            ct = comparison_table(FDF, q, group_q, MODE)
            st.markdown("**Effectifs par groupe**")
            st.dataframe(ct, hide_index=True, width="stretch")
            empty_groups = ct.loc[ct["Réponses valides"] == 0, group_q].tolist()
            if empty_groups:
                st.caption(f"⚠️ Aucune réponse applicable pour : {', '.join(empty_groups)}.")
            small_groups = ct.loc[(ct["Réponses valides"] > 0) & (ct["Réponses valides"] < MIN_PAIRS), group_q].tolist()
            if small_groups:
                st.markdown(f"<span class='small-n'>Effectif faible (&lt; {MIN_PAIRS}) pour : "
                           f"{', '.join(small_groups)}.</span> {SMALL_N_RULE}", unsafe_allow_html=True)

            dist = comparison_distribution(FDF, q, group_q)
            if dist["Effectif"].sum() == 0:
                st.info("Aucune réponse valide à comparer dans la sélection actuelle.")
            else:
                spec = QUESTIONS[q]
                labels = (spec["options"] if spec["kind"] == "single" else
                         [spec["anchors"][c] for c in range(1, spec["levels"] + 1)])
                dist["Modalité"] = dist["Code"].map(lambda c: labels[c - 1])
                colors = (CAT_SEQ if spec["kind"] == "single" else
                         (SEQ8 if spec["levels"] == 8 else SEQ5))
                fig = px.bar(dist, x=group_q, y="% du groupe", color="Modalité", text=dist["Effectif"],
                            category_orders={"Modalité": labels, group_q: QUESTIONS[group_q]["options"]},
                            color_discrete_sequence=colors)
                fig.update_layout(barmode="stack", yaxis_title="% du groupe (réponses valides)",
                                  xaxis_title=short(group_q))
                show(style(fig, f"{short(q)} selon {short(group_q)} — barres empilées à 100 %", 440), "cmp")

                st.markdown("**Tableau croisé (effectifs)**")
                pivot = dist.pivot(index=group_q, columns="Modalité", values="Effectif").reindex(
                    QUESTIONS[group_q]["options"])[labels]
                st.dataframe(pivot, width="stretch")
                set_export(f"comparaison_{q}_par_{group_q}", pivot.reset_index())
        st.caption("Une différence observée entre groupes dans cet échantillon simulé ne constitue ni "
                  "une conclusion générale ni une preuve de causalité ; aucun test de significativité "
                  "n'est calculé ici.")

# ============================================================================ E. Relations entre réponses
elif nav == "Relations entre réponses":
    st.caption("Choisissez deux questions à échelle (Q5 à Q15). Les identifiants et les variables "
              "nominales (genre, niveau d'études…) sont exclus : une corrélation sur des codes de "
              "catégories n'aurait pas de sens.")
    c1, c2 = st.columns(2)
    qa = c1.selectbox("Première question", SCALE_QS, format_func=short, key="corr_a", index=0)
    default_b = next((q for q in SCALE_QS if q != qa), SCALE_QS[0])
    qb = c2.selectbox("Deuxième question", [q for q in SCALE_QS if q != qa], format_func=short,
                      key="corr_b")

    if not need_rows(FDF):
        res = spearman_pair(FDF, qa, qb)
        st.markdown(f"#### {short(qa)}  ↔  {short(qb)}")
        if res["rho"] is None:
            st.warning(f"Corrélation non calculable : {res['reason']} (n = {res['n']}).")
        else:
            c = st.columns(2)
            c[0].metric("Coefficient de Spearman (ρ)", f"{res['rho']:+.2f}")
            c[1].metric("Paires de réponses valides", res["n"])
            sens = "dans le même sens" if res["rho"] > 0 else "en sens opposés" if res["rho"] < 0 else "sans tendance"
            st.markdown(f"<div class='reading-aid'>Un coefficient {'positif' if res['rho']>=0 else 'négatif'} "
                       f"signifie que, dans cet échantillon, les profils qui répondent plus haut à "
                       f"{qa} ont tendance à répondre {sens} à {qb}.</div>", unsafe_allow_html=True)
            fig = go.Figure(go.Heatmap(z=res["crosstab"].values, x=[str(c) for c in res["crosstab"].columns],
                                       y=[str(i) for i in res["crosstab"].index], colorscale="Blues",
                                       text=res["crosstab"].values, texttemplate="%{text}",
                                       colorbar=dict(title="n")))
            fig.update_layout(xaxis_title=f"{qb} (code)", yaxis_title=f"{qa} (code)")
            show(style(fig, "Tableau croisé des réponses (effectifs)", 420), "pair_ct")
            set_export(f"correlation_{qa}_{qb}", res["crosstab"].rename(columns=str).reset_index())

        st.info("⚠️ Une corrélation n'établit pas une causalité. Dans cette simulation, certaines "
                "associations proviennent des règles de génération.")
        st.caption(programmed_link_note(qa, qb, params))

        with st.expander("📊 Matrice de corrélations — toutes les échelles (Q5–Q15)"):
            corr, npair, notes = safe_spearman(FDF)
            if corr.where(~np.eye(len(corr), dtype=bool)).notna().sum().sum() == 0:
                st.warning("Aucune corrélation calculable dans la sélection actuelle.")
            else:
                text = corr.map(lambda v: "–" if pd.isna(v) else f"{v:.2f}")
                fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index),
                                           zmin=-1, zmax=1, colorscale="RdBu", text=text.values,
                                           texttemplate="%{text}", hoverongaps=False,
                                           colorbar=dict(title="ρ")))
                fig.update_yaxes(autorange="reversed")
                show(style(fig, "Spearman — paires complètes (« – » = non calculable)", 520), "corr_mat")
            st.caption(f"Corrélation refusée si n < {MIN_PAIRS} ou si une variable est constante sur les "
                      "paires utilisables.")
            st.dataframe(npair, width="stretch")

# ============================================================================ F. Exports et méthode
elif nav == "Exports et méthode":
    st.caption(f"🔒 {BANNER}. Aucune connexion à Qualtrics ; aucune donnée envoyée ni collectée.")

    e1, e2, e3 = st.tabs(["📦 Échantillon complet", "🔎 Sélection filtrée", "📄 Analyse courante"])
    with e1:
        st.caption(f"{N} profils · graine {params.seed}")
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ CSV — réponses lisibles", ex.csv_readable(DF, MODE),
                           ex.filename("lisibles", "csv", params, "tout", N), "text/csv", width="stretch")
        d2.download_button("⬇️ CSV — codes et statuts", ex.csv_codes(DF, MODE),
                           ex.filename("codes_statuts", "csv", params, "tout", N), "text/csv", width="stretch")
        d3.download_button("⬇️ Excel (8 feuilles)",
                           ex.excel_bytes(DF, params, f"Ensemble ({N})", N, None, True, df_full=DF),
                           ex.filename("classeur", "xlsx", params, "tout", N),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
        st.download_button("⬇️ JSON", ex.json_bytes(DF, params, f"Ensemble ({N})", N, None),
                           ex.filename("donnees", "json", params, "tout", N), "application/json")

    with e2:
        st.caption(f"{NF} profils sur {N} · {FILT.describe()}")
        if need_rows(FDF, "Aucun profil filtré à exporter."):
            pass
        else:
            d1, d2, d3 = st.columns(3)
            d1.download_button("⬇️ CSV — réponses lisibles", ex.csv_readable(FDF, MODE),
                               ex.filename("lisibles", "csv", params, "filtre", NF), "text/csv", width="stretch")
            d2.download_button("⬇️ CSV — codes et statuts", ex.csv_codes(FDF, MODE),
                               ex.filename("codes_statuts", "csv", params, "filtre", NF), "text/csv", width="stretch")
            d3.download_button("⬇️ Excel (8 feuilles)",
                               ex.excel_bytes(FDF, params, f"Filtré ({NF} sur {N})", N, FILT, False,
                                              df_full=DF),
                               ex.filename("classeur", "xlsx", params, "filtre", NF),
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
            st.download_button("⬇️ JSON", ex.json_bytes(FDF, params, f"Filtré ({NF} sur {N})", N, FILT),
                               ex.filename("donnees", "json", params, "filtre", NF), "application/json")

    with e3:
        cur = st.session_state.get("analysis_export")
        if not cur:
            st.info("Aucune analyse courante. Consultez « Analyse par question », « Comparaisons » ou "
                    "« Relations entre réponses » pour activer cet export.")
        else:
            st.caption(f"Dernier tableau consulté : **{cur['name']}** ({len(cur['table'])} lignes)")
            st.dataframe(cur["table"], hide_index=True, width="stretch")
            st.download_button("⬇️ CSV — tableau de l'analyse courante", ex.analysis_csv(cur["table"]),
                               ex.analysis_filename(cur["name"], params), "text/csv")

    st.divider()
    st.markdown("### Méthode et limites")
    with st.expander("Graine et paramètres de l'échantillon actif", expanded=False):
        pdict = {"Version du questionnaire": params.version, "Mode de filtrage":
                FILTER_MODE_LABELS.get(MODE, MODE), "Taille": params.n, "Graine": params.seed,
                "Taux d'usage visé": params.taux_usage, "Répartition d'âge saisie": params.age_weights,
                "Pondérations genre": params.genre_weights,
                "Non-réponse accidentelle": params.taux_manquants, "Force lien trait latent": params.force_latent,
                "Lien trait latent → Q10": params.lien_q10_latent, "Lien âge → Q10": params.lien_q10_age}
        st.dataframe(pd.DataFrame({"Valeur": {k: str(v) for k, v in pdict.items()}}), width="stretch")
        st.caption("Ces paramètres sont conservés avec l'échantillon, même si les réglages affichés "
                  "dans « Configurer la simulation » sont ensuite modifiés sans être appliqués.")
    with st.expander("Associations programmées (hypothèses de la simulation)"):
        st.markdown(
            "- Toutes les associations entre questions sont des **hypothèses pédagogiques**, pas des résultats.\n"
            "- Un trait latent d'« appétence pour l'IA » est lié positivement à Q1, Q5, Q7, Q9 et Q12–Q15 ; "
            "Q6 y est faiblement lié ; Q8 dépend du niveau d'études (pas du trait latent) ; Q11 est "
            "indépendante. **Q10 : aucune association par défaut** (réglable dans « Associations "
            "programmées (avancé) »).\n"
            "- Le « profil latent simulé » est une information interne au modèle ; aucun profil n'est réel.")
    with st.expander("Mode de parcours et règles de non-applicabilité"):
        st.markdown(f"**Mode actif : {FILTER_MODE_LABELS.get(MODE, MODE)}**")
        if MODE == MODE_LIBRE:
            st.markdown(f"- {HYPOTHETICAL_NOTE}")
        else:
            st.markdown(
                "- Le texte du questionnaire fourni ne prouve aucun branchement Qualtrics réel : les "
                "exclusions ci-dessous sont des **conventions de simulation**, pas un fait démontré.\n"
                "- **Non applicable** : question non posée à ce profil par une convention de simulation "
                "(jamais une exigence du professeur, jamais un oubli).")
        st.dataframe(pd.DataFrame(filters_table(MODE, DF), columns=["Question", "Posée à", "Nature de la règle", "Profils concernés"]),
                    hide_index=True, width="stretch")
        st.markdown(
            "- **Manquant** : question applicable restée sans réponse — non-réponse accidentelle simulée "
            "(réglable). Non applicable et manquant sont toujours distingués (tableaux, exports `Qx_statut`) "
            "et aucune modalité « Je ne sais pas » n'est ajoutée (absente du questionnaire original).\n"
            "- Les deux modes ne sont jamais mélangés : un échantillon est généré entièrement sous l'un "
            "ou l'autre (le mode est enregistré avec ses paramètres et dans chaque export).")
    with st.expander("Limites des résultats"):
        st.markdown(
            "- Échantillon **synthétique** : aucune inférence sur de vrais étudiants.\n"
            "- Q9 à Q12 (5 modalités) et Q5–Q8, Q13–Q15 (8 modalités distinctes) ne sont **jamais "
            "combinées en un score global** : elles mesurent des dimensions différentes.\n"
            "- **Test d'attention absent de cette version** du questionnaire : aucun résultat de "
            "réussite/échec n'est calculé ou affiché, et aucun profil n'est écarté pour ce motif.\n"
            "- **Q8 n'est pas une variable Oui/Non** et n'est jamais recodée en binaire. Une variable "
            "dérivée **Q1_binaire** (Oui=1, Non=0) est proposée dans les exports « codes », en plus de "
            "Q1 d'origine conservée telle quelle ; elle ne répond à aucune consigne de recodage de Q8 "
            "d'un autre questionnaire.\n"
            "- Les variables nominales (genre, niveau d'études, utilisation de l'IA…) ne sont jamais "
            "moyennées ni corrélées comme des échelles ordinales.\n"
            f"- {SMALL_N_RULE}\n"
            "- Une corrélation n'établit pas une causalité ; certaines proviennent des règles de "
            "génération (voir « Relations entre réponses »), d'autres du hasard d'échantillonnage. Les "
            "paramètres de génération ne sont pas réglés pour obtenir une conclusion, une corrélation "
            "précise ou un résultat significatif prédéterminés.\n"
            "- Aucun test de significativité n'est calculé par défaut dans les comparaisons de groupes.")

    st.divider()
    st.markdown("### ✅ Contrôle de conformité")
    st.caption("Calculé à l'instant sur l'échantillon actif complet (pas sur un résultat supposé) ; "
              "identique à la feuille « Contrôle de conformité » de l'export Excel. Aucun statut n'est "
              "forcé au vert : Gris = non applicable ou non vérifiable, pas un échec.")
    ctrl = compliance.control_table(DF, params)
    n_red = (ctrl["Statut"] == compliance.ROUGE).sum()
    (st.error if n_red else st.success)(
        f"{(ctrl['Statut'] == compliance.VERT).sum()} contrôle(s) réussi(s), {n_red} anomalie(s), "
        f"{(ctrl['Statut'] == compliance.GRIS).sum()} information(s).")
    st.dataframe(ctrl.style.map(style_statut, subset=["Statut"]), hide_index=True, width="stretch")

    st.markdown("### 🧹 Préparation de la base — limites traitées honnêtement")
    st.caption("Ces éléments sont volontairement **gris** : ce ne sont pas des contrôles réussis ou "
              "échoués, mais des choix de portée du questionnaire.")
    st.dataframe(compliance.prep_base_table(DF, params).style.map(style_statut, subset=["Statut"]),
                hide_index=True, width="stretch")

st.divider()
st.caption(f"🔒 {MINI_BANNER} · Aucune connexion à Qualtrics.")
