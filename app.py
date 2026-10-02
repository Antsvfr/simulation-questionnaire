"""Simulateur de questionnaire « IA dans l'éducation » — Streamlit + pandas + Plotly.

Lancement : streamlit run app.py
Aucune connexion réseau, aucun envoi vers Qualtrics ou un autre service.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import exports as ex
from simulator import SimParams, effectifs, simulate, status_frame
from survey_config import (AGREE_QS, ALL_QS, BANNER, CATEGORICAL, QUESTIONS, SCALE6_QS, SCALE_QS,
                           SHORT_HDR, filters_table, scale_help, short)
from views import (COL_MISS, COL_NA, COL_NB_MISS, COL_STATUT_Q, COMPLET, LATENT_COL, MIN_PAIRS,
                   MISS_TXT, NA_TXT, VARS, Filters, codes_frame, composition_table, counts,
                   filter_mask, options_for, readable_frame, safe_spearman)

st.set_page_config(page_title="Simulation questionnaire IA & éducation", page_icon="🧪",
                   layout="wide")

NEG_POS = ["#b2182b", "#ef8a62", "#fddbc7", "#d1e5f0", "#67a9cf", "#2166ac"]
NEG_POS5 = ["#b2182b", "#ef8a62", "#bdbdbd", "#67a9cf", "#2166ac"]
BANNER_2L = BANNER.replace(" — AUCUNE", " —<br>AUCUNE")
CAT_SEQ = px.colors.qualitative.Safe
OBS_COLOR, EXP_COLOR = "#2166ac", "#9ca3af"

st.markdown("""<style>
.block-container{max-width:1400px;padding-top:2.2rem}
[data-testid="stMetricValue"]{font-size:1.9rem}
[data-testid="stMetricLabel"] p{font-size:.85rem}
.scope{background:#eef4fb;border-left:4px solid #2166ac;border-radius:4px;padding:.5rem .8rem;margin:.3rem 0 .8rem}
.internal{background:#f3f0ff;border:1px dashed #7c6bc4;border-radius:6px;padding:.5rem .8rem}
@media (max-width:640px){.block-container{padding:1rem .8rem}[data-testid="stMetricValue"]{font-size:1.5rem}}
</style>""", unsafe_allow_html=True)


# ============================================================================ état de session
WIDGET_DEFAULTS = {"w_n": 100, "w_seed": 42, "w_taux": 80, "w_manq": 2, "w_a1": 10, "w_a2": 62,
                   "w_a3": 20, "w_a4": 8, "w_force": 1.0, "w_l10": 0.0, "w_l10a": 0.0}
FILTER_DEFAULTS = {"f_search": "", "f_age": [], "f_genre": [], "f_niv": [], "f_use": [],
                   "f_comp": "Tous"}


def draft_params():
    """Paramètres tels que saisis dans la barre latérale (non encore appliqués)."""
    s = st.session_state
    ages = (s.w_a1, s.w_a2, s.w_a3, s.w_a4)
    if sum(ages) == 0:
        return None
    return SimParams(n=int(s.w_n), seed=int(s.w_seed), taux_usage=s.w_taux / 100, age_weights=ages,
                     taux_manquants=s.w_manq / 100, force_latent=float(s.w_force),
                     lien_q10_latent=float(s.w_l10), lien_q10_age=float(s.w_l10a))


def generate(params: SimParams):
    """Seule fonction qui remplace l'échantillon actif (paramètres + données + vues dérivées)."""
    df = simulate(params)
    st.session_state.sample = {
        "params": params, "df": df, "readable": readable_frame(df), "codes": codes_frame(df),
        "sid": st.session_state.get("sample", {}).get("sid", 0) + 1}


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


for k, v in {**WIDGET_DEFAULTS, **FILTER_DEFAULTS, "scope": "full", "view_mode": "Réponses lisibles"}.items():
    st.session_state.setdefault(k, list(v) if isinstance(v, list) else v)
if "sample" not in st.session_state:
    generate(draft_params())

S = st.session_state.sample
params, DF, READ, CODES = S["params"], S["df"], S["readable"], S["codes"]
N = len(DF)


def current_filters() -> Filters:
    s = st.session_state
    return Filters(s.f_search, list(s.f_age), list(s.f_genre), list(s.f_niv), list(s.f_use), s.f_comp)


FILT = current_filters()
MASK = filter_mask(READ, FILT)
FDF = DF[MASK]
NF = len(FDF)

# ============================================================================ utilitaires
def banner_box():
    st.markdown(
        f"<div style='background:#fff3cd;color:#664d03;border:2px solid #e0a800;border-radius:6px;"
        f"padding:.6rem 1rem;font-weight:700;text-align:center;letter-spacing:.02em'>⚠️ {BANNER}</div>",
        unsafe_allow_html=True)


def style(fig, title, height=420):
    fig.update_layout(
        title=dict(text=f"{title}<br><sup style='color:#b45309'>{BANNER_2L}</sup>", x=0.0),
        height=height + 60, margin=dict(t=110, b=130, l=60, r=30), legend_title_text="",
        template="plotly_white")
    fig.add_annotation(text=f"<b>{BANNER_2L}</b>", xref="paper", yref="paper", x=0.5, y=0, yshift=-80,
                       yanchor="top", showarrow=False, font=dict(size=10, color="#b45309"),
                       xanchor="center", align="center")
    return fig


def show(fig, key):
    st.plotly_chart(fig, width="stretch", key=key,
                    config={"toImageButtonOptions": {"filename": "SIMULATION_graphique"}})


def scope_choice():
    return FDF if st.session_state.scope == "filtered" else DF


def scope_label():
    return (f"Profils filtrés ({NF} sur {N})" if st.session_state.scope == "filtered"
            else f"Ensemble de l'échantillon ({N} profils)")


def scope_caption(d, extra=""):
    st.markdown(f"<div class='scope'><b>Périmètre :</b> {scope_label()} · "
                f"<b>{len(d)}</b> profils analysés. {extra}</div>", unsafe_allow_html=True)


def need_data(d) -> bool:
    """True (et message) si le périmètre est vide."""
    if len(d) == 0:
        st.warning("Aucun profil dans ce périmètre : modifiez ou réinitialisez les filtres "
                   "(onglet « Échantillon détaillé »), ou choisissez « Ensemble de l'échantillon ».")
        return True
    return False


def n_used(d, q):
    return int(d[q].notna().sum())


def qlabel(d, q, width=48):
    lab = QUESTIONS[q]["label"].strip("« »")
    return f"{q} — {lab[:width]}{'…' if len(lab) > width else ''} (n={n_used(d, q)})"


def diverging(d, qs, levels, title, key):
    """Barres divergentes ; % sur les répondants (non applicables et manquants exclus)."""
    colors = NEG_POS if levels == 6 else NEG_POS5
    fig = go.Figure()
    pct = {q: d[q].dropna().astype(int).value_counts(normalize=True)
           .reindex(range(1, levels + 1), fill_value=0) * 100 for q in qs}
    ylab = [qlabel(d, q) for q in qs]
    for k in range(1, levels + 1):
        vals = np.array([pct[q][k] for q in qs])
        name = f"{k}" if levels == 6 else f"{k} – {QUESTIONS[qs[0]]['anchors'][k]}"
        hov = f"Note {k} : " + "%{customdata:.1f} %<extra></extra>"
        if levels == 5 and k == 3:
            for sgn, leg in ((-1, True), (1, False)):
                fig.add_bar(y=ylab, x=sgn * vals / 2, orientation="h", name=name, customdata=vals,
                            marker_color=colors[k - 1], legendgroup=name, showlegend=leg,
                            hovertemplate=hov)
        else:
            neg = k < (levels + 1) / 2
            fig.add_bar(y=ylab, x=(-vals if neg else vals), orientation="h", name=name,
                        customdata=vals, marker_color=colors[k - 1], hovertemplate=hov)
    fig.update_layout(barmode="relative", yaxis=dict(autorange="reversed"),
                      xaxis_title="% des répondants (n = réponses valides)")
    show(style(fig, title, 140 + 55 * len(qs)), key)


def means_plot(d, qs, levels, title, key):
    m = pd.DataFrame({"q": [qlabel(d, q, 28) for q in qs], "m": [d[q].mean() for q in qs],
                      "sd": [d[q].std() for q in qs]})
    fig = go.Figure(go.Scatter(x=m.q, y=m.m, mode="markers", marker=dict(size=11, color=NEG_POS[5]),
                               error_y=dict(type="data", array=m.sd, visible=True),
                               hovertemplate="%{x}<br>Moyenne %{y:.2f}<extra></extra>"))
    fig.update_yaxes(range=[1, levels], dtick=1, title=f"Moyenne ± écart-type (1–{levels})")
    show(style(fig, title, 420), key)


# ============================================================================ barre latérale
sb = st.sidebar
sb.error(BANNER)
sb.header("Échantillon actif")
sb.markdown(f"**{N} profils** · graine **{params.seed}**")
if st.session_state.get("seed_msg"):
    sb.success(st.session_state.pop("seed_msg"))
sb.header("Paramètres de génération")
sb.caption("Modifier ces réglages ne change rien tant que vous n'avez pas cliqué sur un bouton "
           "de génération ci-dessous.")
sb.slider("Taille de l'échantillon", 20, 500, key="w_n", step=10)
sb.number_input("Graine aléatoire", 0, 10**6, key="w_seed")
sb.slider("Taux d'utilisation de l'IA visé (Q1 = Oui)", 0, 100, key="w_taux", step=5, format="%d %%")
sb.slider("Non-réponse accidentelle (cellules applicables)", 0, 30, key="w_manq", format="%d %%")
sb.caption("Répartition d'âge visée (Q2), normalisée automatiquement")
sb.slider("Moins de 18 ans", 0, 100, key="w_a1", format="%d")
sb.slider("18–24 ans", 0, 100, key="w_a2", format="%d")
sb.slider("25–34 ans", 0, 100, key="w_a3", format="%d")
sb.slider("35 ans et plus", 0, 100, key="w_a4", format="%d")
with sb.expander("Associations paramétrables (hypothèses)"):
    st.slider("Force du lien trait latent → Q5, Q7, Q9, Q12–Q15", 0.0, 1.5, key="w_force", step=0.1)
    st.slider("Lien trait latent → Q10 (0 = aucune association)", -1.0, 1.0, key="w_l10", step=0.1)
    st.slider("Lien âge → Q10 (0 = aucune association)", -0.5, 0.5, key="w_l10a", step=0.05)

DRAFT = draft_params()
if DRAFT is None:
    sb.warning("Au moins une tranche d'âge doit être supérieure à 0.")
elif DRAFT != params:
    sb.warning("⚠️ Paramètres modifiés **non encore appliqués** : l'échantillon affiché reste celui "
               "généré avec les paramètres précédents.")
sb.button("🔁 Reproduire avec cette graine", key="btn_repro", on_click=cb_reproduce, disabled=DRAFT is None,
          width="stretch", help="Régénère l'échantillon avec les paramètres ci-dessus ET la graine saisie "
          "(mêmes paramètres + même graine = mêmes données).")
sb.button("🎲 Générer un nouvel échantillon", key="btn_new", on_click=cb_new, disabled=DRAFT is None,
          width="stretch", type="primary", help="Tire une nouvelle graine (affichée ci-dessus) puis "
          "génère l'échantillon avec les paramètres ci-dessus.")

# ============================================================================ en-tête
st.title("🧪 Simulateur de questionnaire — IA dans l'éducation")
banner_box()
st.caption("Échantillon généré aléatoirement pour s'entraîner à analyser un questionnaire (Q1–Q15). "
           "Aucune connexion à Qualtrics ; aucune donnée n'est envoyée ni collectée.")
with st.expander("Paramètres exacts de l'échantillon actif"):
    pdict = {"Taille": params.n, "Graine": params.seed, "Taux d'usage visé": params.taux_usage,
             "Répartition d'âge saisie": params.age_weights,
             "Pondérations genre": params.genre_weights,
             "Non-réponse accidentelle": params.taux_manquants,
             "Force lien trait latent": params.force_latent,
             "Lien trait latent → Q10": params.lien_q10_latent, "Lien âge → Q10": params.lien_q10_age}
    st.dataframe(pd.DataFrame({"Valeur": {k: str(v) for k, v in pdict.items()}}), width="stretch")
    st.caption("Ces paramètres sont conservés avec l'échantillon, même si vous modifiez ensuite les réglages.")
with st.expander("Hypothèses de simulation et conventions de filtre (à lire)"):
    st.markdown(
        "- **Toutes les associations entre questions sont des hypothèses pédagogiques**, pas des résultats.\n"
        "- Un trait latent d'« appétence pour l'IA » est lié positivement à Q1, Q5, Q7, Q9 et Q12–Q15 ; "
        "Q6 y est faiblement lié ; Q8 dépend légèrement du niveau d'études ; Q11 est indépendante. "
        "**Q10 : aucune association par défaut.**\n"
        "- Le « profil latent simulé » est une information interne au modèle ; aucun profil n'est réel.\n"
        "- **Non applicable ≠ manquant** : le premier découle du filtre (jamais un oubli), le second est "
        "une non-réponse accidentelle simulée.\n"
        "- Q9–Q12 mesurent des dimensions différentes : aucun score global n'est calculé.")
    st.dataframe(pd.DataFrame(filters_table(), columns=["Question", "Posée à", "Nature de la règle"]),
                 hide_index=True, width="stretch")

st.radio("Périmètre des résumés et graphiques (composition, échelles, comparaisons, corrélations)",
         ["full", "filtered"], key="scope", horizontal=True,
         format_func=lambda v: (f"Ensemble de l'échantillon ({N})" if v == "full"
                                else f"Profils filtrés ({NF} sur {N})"),
         help="Les filtres se règlent dans l'onglet « Échantillon détaillé ». Les exports ont leurs "
              "propres boutons (tout / filtré).")

tabs = st.tabs(["🗂️ Échantillon détaillé", "🪪 Fiche individuelle", "🧩 Composition", "📈 Échelles",
                "🔀 Comparaisons", "🔗 Corrélations", "⬇️ Exports"])
(tab_det, tab_fiche, tab_comp, tab_lik, tab_cross, tab_corr, tab_export) = tabs

# ============================================================================ 1. échantillon détaillé
with tab_det:
    C = counts(DF)
    m = st.columns(5)
    m[0].metric("Profils synthétiques", C["profils"])
    m[1].metric("Utilisateurs / non-utilisateurs", f"{C['utilisateurs']} / {C['non_utilisateurs']}")
    m[2].metric("Questionnaires complets", f"{C['complets']} / {C['profils']}")
    m[3].metric("Réponses accidentellement manquantes", C["manquantes"])
    m[4].metric("Réponses non applicables", C["non_applicables"])
    st.info(
        "**Questionnaire complet** = aucune réponse accidentellement manquante parmi les questions "
        "**applicables** à ce profil. Une réponse **non applicable** (question non posée, par exemple Q8 pour "
        "un non-utilisateur) n'est **pas** un oubli et n'est jamais comptée comme manquante. Les chiffres "
        "ci-dessus portent sur l'échantillon complet, quel que soit le filtre.")

    st.subheader("Profils")
    f1, f2 = st.columns([1, 3])
    f1.text_input("Rechercher un identifiant", key="f_search", placeholder="ex. SYN-042")
    g = f2.columns(4)
    g[0].multiselect("Tranche d'âge", options_for("Q2"), key="f_age", placeholder="Toutes")
    g[1].multiselect("Genre", options_for("Q3"), key="f_genre", placeholder="Tous")
    g[2].multiselect("Niveau d'études", options_for("Q4"), key="f_niv", placeholder="Tous")
    g[3].multiselect("Utilise l'IA (Q1)", options_for("Q1"), key="f_use", placeholder="Tous")
    h1, h2 = st.columns([3, 1])
    h1.radio("Questionnaires", ["Tous", "Complets", "Incomplets"], key="f_comp", horizontal=True)
    h2.button("↺ Réinitialiser les filtres", key="btn_reset", on_click=cb_reset_filters, width="stretch")

    v1, v2, v3 = st.columns([2, 2, 2])
    mode = v1.radio("Affichage des réponses", ["Réponses lisibles", "Codes numériques"], key="view_mode",
                    horizontal=True)
    sort_col = v2.selectbox("Trier par", ["ID"] + ALL_QS + [COL_NB_MISS], key="sort_col")
    asc = v3.radio("Ordre", ["Croissant", "Décroissant"], key="sort_order", horizontal=True) == "Croissant"
    show_status = False
    if mode == "Codes numériques":
        show_status = st.checkbox("Afficher aussi le statut de chaque question (répondu / non_applicable / "
                                  "manquant)", key="show_status")

    st.markdown(f"**{NF} profils affichés sur {N} profils générés**"
                + (f" — filtres : {FILT.describe()}" if FILT.active() else ""))
    if NF == 0:
        st.warning("Aucun profil ne correspond à ces filtres. Élargissez la sélection ou cliquez sur "
                   "« Réinitialiser les filtres ».")
    else:
        table = (READ if mode == "Réponses lisibles" else CODES).loc[MASK].copy()
        order = CODES.loc[MASK, sort_col] if sort_col != "ID" else table["ID"]
        table = table.loc[order.sort_values(ascending=asc, na_position="last", kind="stable").index]
        if mode == "Codes numériques" and not show_status:
            table = table.drop(columns=[f"{q}_statut" for q in ALL_QS])
        cfg = {"ID": st.column_config.TextColumn("ID synthétique", pinned=True, width="medium"),
               LATENT_COL: st.column_config.TextColumn(LATENT_COL, help="Information interne au modèle de "
                                                       "simulation : non observable dans un vrai questionnaire."),
               COL_STATUT_Q: st.column_config.TextColumn("Statut du questionnaire", width="small")}
        for q in ALL_QS:
            lab = f"{q} · {SHORT_HDR[q]}"
            cfg[q] = (st.column_config.NumberColumn(lab, help=scale_help(q), format="%d")
                      if mode == "Codes numériques" else st.column_config.TextColumn(lab, help=scale_help(q)))
        st.dataframe(table, hide_index=True, width="stretch", height=460, column_config=cfg)
        st.caption("Cliquez sur un en-tête pour trier aussi directement dans le tableau ; survolez-le pour "
                   "voir la question complète. Q1–Q4 décrivent le profil (utilisation de l'IA, âge, genre, niveau). "
                   f"Dans « Réponses lisibles », « {NA_TXT} » et « {MISS_TXT} » sont distincts ; "
                   "en codes numériques, une cellule vide est l'un ou l'autre (cochez l'affichage des statuts).")

    with st.expander("Échelles et bornes (libellés du questionnaire)"):
        rows = [(q, QUESTIONS[q]["label"], f"1 à {QUESTIONS[q]['levels']}" if QUESTIONS[q]["kind"] != "single"
                 else f"codes 1 à {len(QUESTIONS[q]['options'])}",
                 " ; ".join(f"{k} = {v}" for k, v in (QUESTIONS[q].get("anchors") or {}).items())
                 or " / ".join(QUESTIONS[q]["options"])) for q in ALL_QS]
        st.dataframe(pd.DataFrame(rows, columns=["Question", "Intitulé", "Échelle", "Libellés disponibles"]),
                     hide_index=True, width="stretch")
        st.caption("Seuls les libellés présents dans le questionnaire sont affichés ; aucun libellé "
                   "intermédiaire n'est inventé pour les échelles à 6 niveaux.")
    with st.expander("Effectifs par question (échantillon complet)"):
        st.dataframe(effectifs(DF), hide_index=True, width="stretch")

# ============================================================================ 2. fiche individuelle
with tab_fiche:
    st.markdown("Consultez toutes les réponses d'un profil synthétique. Aucun nom, e-mail ni biographie "
                "fictive n'est généré, et aucune explication individuelle n'est inventée : les réponses "
                "sont des tirages aléatoires du modèle.")
    only_f = st.checkbox("Limiter la liste aux profils filtrés", key="fiche_only_f")
    ids = list(FDF["ID"] if only_f else DF["ID"])
    if not ids:
        st.warning("Aucun profil à afficher : les filtres ne renvoient aucun profil.")
    else:
        pid = st.selectbox("Identifiant synthétique", ids, key="fiche_id")
        row = DF[DF["ID"] == pid].iloc[0]
        rrow = READ[READ["ID"] == pid].iloc[0]
        st.subheader(f"Profil {pid}")
        c = st.columns(5)
        c[0].markdown(f"**Utilise l'IA (Q1)**  \n{rrow['Q1']}")
        c[1].markdown(f"**Tranche d'âge (Q2)**  \n{rrow['Q2']}")
        c[2].markdown(f"**Genre (Q3)**  \n{rrow['Q3']}")
        c[3].markdown(f"**Niveau d'études (Q4)**  \n{rrow['Q4']}")
        c[4].markdown(f"**Questionnaire**  \n{rrow[COL_STATUT_Q]}"
                      + (f" — manquantes : {rrow[COL_MISS]}" if rrow[COL_MISS] else ""))
        st.markdown(f"<div class='internal'>⚙ <b>Information interne au modèle</b> — profil latent simulé : "
                    f"<b>{rrow[LATENT_COL]}</b> (non observable dans un vrai questionnaire ; aucun profil "
                    f"n'est réel).</div>", unsafe_allow_html=True)
        stat = status_frame(DF[DF["ID"] == pid]).iloc[0]
        lines = []
        for q in ALL_QS:
            spec = QUESTIONS[q]
            statut = {"répondu": "Répondu", "non_applicable": NA_TXT, "manquant": MISS_TXT}[stat[q]]
            reponse = rrow[q] if stat[q] == "répondu" else "—"
            lines.append({"Q": q, "Texte de la question": spec["text"] + (" (intitulé)" if spec["text_is_title"] else ""),
                          "Réponse": reponse, "Statut": statut,
                          "Code": "" if stat[q] != "répondu" else str(int(row[q]))})
        ft = pd.DataFrame(lines)
        st.table(ft.set_index("Q"))
        st.caption("« Non applicable » : question non posée à ce profil (convention de filtre, pas un oubli). "
                   "« Réponse manquante » : question applicable restée sans réponse (non-réponse accidentelle "
                   "simulée). Pour Q1–Q8, seul l'intitulé du questionnaire est disponible (texte complet non "
                   "fourni) ; Q9–Q15 reprennent la formulation du questionnaire.")

# ============================================================================ 3. composition
with tab_comp:
    d = scope_choice()
    full = st.session_state.scope == "full"
    scope_caption(d, "Pourcentage observé = effectif ÷ réponses valides de la variable (manquants exclus).")
    if not need_data(d):
        st.info("**Probabilités paramétrées ≠ proportions observées.** Les paramètres définissent des "
                "probabilités de tirage ; dans un échantillon aléatoire de taille finie, les proportions "
                "obtenues fluctuent autour de ces probabilités (d'autant plus que l'échantillon est petit). "
                + ("" if full else "Pour les profils filtrés, les probabilités paramétrées ne s'appliquent "
                   "pas (sous-ensemble non aléatoire) : seules les proportions observées sont affichées."))
        cols = st.columns(2)
        for i, q in enumerate(["Q2", "Q3", "Q4", "Q1"]):
            t, n_valid, n_miss = composition_table(d, q, params if full else None)
            with cols[i % 2]:
                st.markdown(f"##### {q} — {VARS[q]}")
                st.caption(f"Dénominateur : {n_valid} réponses valides"
                           + (f" · {n_miss} réponse(s) manquante(s) exclue(s)" if n_miss else ""))
                if n_valid == 0:
                    st.warning("Aucune réponse valide pour cette variable dans ce périmètre.")
                    continue
                fig = go.Figure(go.Bar(x=t["Modalité"], y=t["% observé"], name="Observé",
                                       marker_color=OBS_COLOR, text=t["% observé"].map("{:.0f} %".format),
                                       textposition="outside", textangle=0))
                if full:
                    fig.add_bar(x=t["Modalité"], y=t["Probabilité paramétrée (%)"], name="Paramétré",
                                marker_color=EXP_COLOR, textposition="outside", textangle=0,
                                text=t["Probabilité paramétrée (%)"].map("{:.0f} %".format))
                fig.update_layout(barmode="group", yaxis=dict(title="%", range=[0, min(100, t.filter(like="%").max().max() * 1.25 + 5)]), xaxis_title="")
                show(style(fig, f"{q} — {VARS[q]} (n={n_valid})", 340), f"comp_{q}")
                tt = t.copy()
                tt["% observé"] = tt["% observé"].map("{:.1f} %".format)
                if full:
                    tt["Probabilité paramétrée (%)"] = tt["Probabilité paramétrée (%)"].map("{:.1f} %".format)
                st.dataframe(tt, hide_index=True, width="stretch")
        if full:
            st.caption("Q1 : la probabilité paramétrée est le taux d'utilisation visé ; Q4 : probabilité "
                       "marginale calculée à partir de la répartition d'âge (le niveau dépend de l'âge).")
        prof = d[("Profil_latent_simulé")].value_counts().rename_axis("⚙ Profil latent simulé (interne)")
        st.markdown("##### ⚙ Profil latent simulé — information interne au modèle")
        st.dataframe(prof.rename("Effectif").reset_index(), hide_index=True, width="stretch")

# ============================================================================ 4. échelles
with tab_lik:
    d = scope_choice()
    scope_caption(d, "Pourcentages calculés sur les réponses valides ; n affiché pour chaque question.")
    if not need_data(d):
        st.info("Les questions filtrées (Q5, Q7, Q8, Q9, Q11, Q12) ne sont posées qu'aux utilisateurs de l'IA. "
                "Échelles à 6 niveaux (Q5–Q8, Q13–Q15) et à 5 niveaux (Q9–Q12) présentées séparément ; "
                "aucun score global n'est calculé.")
        if all(n_used(d, q) == 0 for q in SCALE_QS):
            st.warning("Aucune réponse valide aux échelles dans ce périmètre.")
        else:
            diverging(d, SCALE6_QS, 6, "Échelles à 6 niveaux — 1–3 à gauche, 4–6 à droite", "div6")
            means_plot(d, SCALE6_QS, 6, "Moyennes — échelles à 6 niveaux", "mean6")
            diverging(d, AGREE_QS, 5, "Accord à 5 niveaux (Q9–Q12) — 3 « Neutre » centré", "div5")
            means_plot(d, AGREE_QS, 5, "Moyennes — accord à 5 niveaux (aucun score global)", "mean5")
            stats = pd.DataFrame({"Question": SCALE_QS, "n utilisé": [n_used(d, q) for q in SCALE_QS],
                                  "Moyenne": [d[q].mean() for q in SCALE_QS],
                                  "Écart-type": [d[q].std() for q in SCALE_QS]}).round(2)
            st.dataframe(stats, hide_index=True, width="stretch")
            if (stats["n utilisé"] < MIN_PAIRS).any():
                st.caption(f"⚠️ Certaines questions ont moins de {MIN_PAIRS} réponses valides : interpréter avec prudence.")

# ============================================================================ 5. comparaisons
with tab_cross:
    d = scope_choice()
    scope_caption(d, "Seuls les profils ayant une réponse valide aux deux variables sont utilisés.")
    if not need_data(d):
        left, right = st.columns(2)
        qv = left.selectbox("Variable d'intérêt", SCALE_QS, format_func=short, index=0)
        qg = right.selectbox("Comparer selon", CATEGORICAL[1:], format_func=short, index=2)
        order = QUESTIONS[qg]["options"]
        sub = d.dropna(subset=[qv, qg]).copy()
        sub[qg] = sub[qg].astype(int).map(lambda c: order[c - 1])
        if len(sub) == 0:
            st.warning(f"Aucun profil avec une réponse valide à {qv} et {qg} dans ce périmètre.")
        else:
            ncount = sub[qg].value_counts()
            sub["Groupe"] = sub[qg].map(lambda g: f"{g} (n={ncount[g]})")
            grp_order = [f"{o} (n={ncount[o]})" for o in order if o in ncount.index]
            lv = QUESTIONS[qv]["levels"]
            fig = px.box(sub, x="Groupe", y=qv, points="all", color="Groupe",
                         category_orders={"Groupe": grp_order}, color_discrete_sequence=CAT_SEQ)
            fig.update_layout(showlegend=False, yaxis=dict(range=[0.5, lv + 0.5], dtick=1, title=qv),
                              xaxis_title=QUESTIONS[qg]["label"])
            show(style(fig, f"{qv} selon {qg} — {len(sub)} profils avec réponses valides aux deux", 460), "box")
            tbl = (sub.groupby(qg)[qv].agg(n="count", moyenne="mean", écart_type="std")
                   .reindex([o for o in order if o in ncount.index]).round(2))
            tbl["alerte"] = np.where(tbl["n"] < 10, "n < 10 : prudence", "")
            st.dataframe(tbl, width="stretch")
        q4 = d.dropna(subset=["Q1", "Q4"]).copy()
        if len(q4):
            q4["Q1"] = q4["Q1"].astype(int).map(lambda c: QUESTIONS["Q1"]["options"][c - 1])
            q4["Q4"] = q4["Q4"].astype(int).map(lambda c: QUESTIONS["Q4"]["options"][c - 1])
            n4 = q4["Q4"].value_counts()
            ct = (pd.crosstab(q4["Q4"], q4["Q1"], normalize="index") * 100).reindex(
                [o for o in QUESTIONS["Q4"]["options"] if o in n4.index])
            ct.index = [f"{i} (n={n4[i]})" for i in ct.index]
            fig = px.bar(ct, barmode="stack", labels={"value": "% de répondants", "index": "Niveau d'études"},
                         color_discrete_sequence=[NEG_POS[5], "#9ca3af"])
            show(style(fig, f"Utilisation de l'IA (Q1) selon le niveau d'études (Q4) — n={len(q4)}", 380), "q1q4")

# ============================================================================ 6. corrélations
with tab_corr:
    d = scope_choice()
    scope_caption(d, f"Spearman sur paires complètes ; calcul refusé si n < {MIN_PAIRS} ou variable constante.")
    if not need_data(d):
        st.info("Seules les échelles ordinales Q5–Q15 sont corrélées. Les variables nominales (genre, "
                "niveau d'études, utilisation de l'IA…) ne sont jamais traitées comme des nombres.")
        corr, npair, notes = safe_spearman(d)
        if corr.drop(columns=[], errors="ignore").where(~np.eye(len(corr), dtype=bool)).notna().sum().sum() == 0:
            st.warning("Aucune corrélation calculable dans ce périmètre (effectifs insuffisants ou variables "
                       "constantes). Élargissez le périmètre ou augmentez la taille de l'échantillon.")
        else:
            text = corr.map(lambda v: "–" if pd.isna(v) else f"{v:.2f}")
            fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1,
                                       zmax=1, colorscale="RdBu", text=text.values, texttemplate="%{text}",
                                       hoverongaps=False, colorbar=dict(title="ρ")))
            fig.update_yaxes(autorange="reversed")
            show(style(fig, f"Corrélations de Spearman Q5–Q15 (« – » = non calculable ; n par paire ci-dessous)", 560),
                 "corr")
        with st.expander(f"Paires non calculées ({len(notes)})"):
            if notes:
                st.dataframe(pd.DataFrame(notes, columns=["Question A", "Question B", "n paires", "Motif"]),
                             hide_index=True, width="stretch")
            else:
                st.write("Toutes les paires sont calculables.")
        st.markdown("**Nombre de paires utilisables**")
        st.dataframe(npair, width="stretch")
        st.caption("Avec n ≈ 70–100, des corrélations de ±0,2 à ±0,3 peuvent apparaître par simple hasard. "
                   "Une corrélation n'est pas une causalité ; ici elle découle des hypothèses de simulation.")

# ============================================================================ 7. exports
@st.cache_data(show_spinner=False, max_entries=64)
def build(kind, sid, ids_key, scope, filt_desc, _d, _params, _filt, full_scope):
    if kind == "csv_lisible":
        return ex.csv_readable(_d)
    if kind == "csv_codes":
        return ex.csv_codes(_d)
    if kind == "xlsx":
        return ex.excel_bytes(_d, _params, scope, len(DF), _filt, full_scope)
    return ex.json_bytes(_d, _params, scope, len(DF), _filt)


def export_block(d, title, scope, scope_key, filt, full_scope):
    st.markdown(f"#### {title}")
    st.caption(f"{len(d)} profils · graine {params.seed}")
    if len(d) == 0:
        st.warning("Aucun profil à exporter : les filtres ne renvoient aucun résultat.")
        return
    ids_key = hash(tuple(d["ID"]))
    spec = [("csv_lisible", "csv", "lisibles", "text/csv", "⬇️ CSV — réponses lisibles"),
            ("csv_codes", "csv", "codes_statuts", "text/csv", "⬇️ CSV — codes et statuts"),
            ("xlsx", "xlsx", "classeur",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "⬇️ Excel (5 feuilles)"),
            ("json", "json", "donnees", "application/json", "⬇️ JSON")]
    for kind, ext, label, mime, btn in spec:
        data = build(kind, S["sid"], ids_key, scope, filt.describe() if filt else "", d, params, filt, full_scope)
        st.download_button(btn, data, ex.filename(label, ext, params, scope_key, len(d)), mime,
                           key=f"dl_{scope_key}_{kind}", on_click="ignore", width="stretch")


with tab_export:
    banner_box()
    st.markdown("Les exports utilisent **l'échantillon actif** (même graine, mêmes paramètres que les tableaux). "
                "Le nom de fichier contient « SIMULATION_SYNTHETIQUE » et chaque ligne a une colonne "
                f"`{'Origine'}`. Les CSV ont les en-têtes en première ligne (UTF-8 avec BOM : accents corrects "
                "dans Excel ; relire avec `encoding='utf-8-sig'`). Une cellule vide dans le CSV « codes » = non "
                "applicable ou manquant : voir les colonnes `Qx_statut`.")
    e1, e2 = st.columns(2)
    with e1:
        export_block(DF, "Exporter tout l'échantillon", f"Ensemble de l'échantillon ({N} profils)", "tout",
                     None, True)
    with e2:
        export_block(FDF, "Exporter uniquement les profils filtrés",
                     f"Profils filtrés ({NF} sur {N}) — {FILT.describe()}", "filtre", FILT, False)
    st.caption("Excel : feuilles « Réponses lisibles », « Codes et statuts » (en-têtes en ligne 1) puis "
               "« Dictionnaire », « Composition », « Paramètres et méthode » (bandeau en A1, tableaux à partir "
               "de la ligne 3).")

st.divider()
banner_box()
