"""Simulateur de questionnaire « IA dans l'éducation » — Streamlit + pandas + Plotly.

Lancement : streamlit run app.py
Aucune connexion réseau, aucun envoi vers Qualtrics ou un autre service.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from simulator import (PROFIL_COL, PROFILS, SimParams, effectifs, simulate, status_frame,
                       to_csv_bytes, to_excel_bytes, to_json_bytes, with_labels)
from survey_config import (AGREE_QS, BANNER, CATEGORICAL, QUESTIONS, SCALE6_QS, SCALE_QS,
                           filters_table, short)

st.set_page_config(page_title="Simulation questionnaire IA & éducation", page_icon="🧪",
                   layout="wide")

NEG_POS = ["#b2182b", "#ef8a62", "#fddbc7", "#d1e5f0", "#67a9cf", "#2166ac"]  # divergente 1→6
BANNER_2L = BANNER.replace(" — AUCUNE", " —<br>AUCUNE")
NEG_POS5 = ["#b2182b", "#ef8a62", "#bdbdbd", "#67a9cf", "#2166ac"]
CAT_SEQ = px.colors.qualitative.Safe


# ----------------------------------------------------------------------------- utilitaires
def banner_box():
    st.markdown(
        f"<div style='background:#fff3cd;color:#664d03;border:2px solid #e0a800;"
        f"border-radius:6px;padding:.6rem 1rem;font-weight:700;text-align:center;"
        f"letter-spacing:.02em'>⚠️ {BANNER}</div>", unsafe_allow_html=True)


def style(fig, title, height=420):
    """Titre + bandeau d'avertissement incrusté dans la figure (donc dans ses exports image)."""
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


@st.cache_data(show_spinner=False)
def make_data(params: SimParams):
    return simulate(params)


def n_used(q):
    return int(STAT[q].eq("répondu").sum())


def qlabel(q, width=48):
    lab = QUESTIONS[q]["label"].strip("« »")
    return f"{q} — {lab[:width]}{'…' if len(lab) > width else ''} (n={n_used(q)})"


def diverging(qs, levels, title, key, height=None):
    """Barres divergentes ; % calculés sur les répondants (non applicables et manquants exclus)."""
    colors = NEG_POS if levels == 6 else NEG_POS5
    fig = go.Figure()
    pct = {q: df[q].dropna().astype(int).value_counts(normalize=True)
           .reindex(range(1, levels + 1), fill_value=0) * 100 for q in qs}
    ylab = [qlabel(q) for q in qs]
    for k in range(1, levels + 1):
        vals = np.array([pct[q][k] for q in qs])
        name = f"{k}" if levels == 6 else f"{k} – {QUESTIONS[qs[0]]['anchors'][k]}"
        hov = f"Note {k} : " + "%{customdata:.1f} %<extra></extra>"
        if levels == 5 and k == 3:  # neutre : réparti de part et d'autre de l'axe
            for sgn, show_leg in ((-1, True), (1, False)):
                fig.add_bar(y=ylab, x=sgn * vals / 2, orientation="h", name=name, customdata=vals,
                            marker_color=colors[k - 1], legendgroup=name, showlegend=show_leg,
                            hovertemplate=hov)
        else:
            neg = k < (levels + 1) / 2
            fig.add_bar(y=ylab, x=(-vals if neg else vals), orientation="h", name=name,
                        customdata=vals, marker_color=colors[k - 1], hovertemplate=hov)
    fig.update_layout(barmode="relative", yaxis=dict(autorange="reversed"),
                      xaxis_title="% des répondants (n = répondants ayant une réponse valide)")
    show(style(fig, title, height or 140 + 55 * len(qs)), key)


def means_plot(qs, levels, title, key):
    d = pd.DataFrame({"q": [qlabel(q, 28) for q in qs], "m": [df[q].mean() for q in qs],
                      "sd": [df[q].std() for q in qs]})
    fig = go.Figure(go.Scatter(x=d.q, y=d.m, mode="markers", marker=dict(size=11, color=NEG_POS[5]),
                               error_y=dict(type="data", array=d.sd, visible=True),
                               hovertemplate="%{x}<br>Moyenne %{y:.2f}<extra></extra>"))
    fig.update_yaxes(range=[1, levels], dtick=1, title=f"Moyenne ± écart-type (1–{levels})")
    show(style(fig, title, 420), key)


# ----------------------------------------------------------------------------- barre latérale
st.sidebar.error(BANNER)
st.sidebar.header("Paramètres de simulation")
n = st.sidebar.slider("Taille de l'échantillon", 50, 500, 100, 10)
seed = st.sidebar.number_input("Graine aléatoire (reproductibilité)", 0, 10**6, 42)
if st.sidebar.button("🎲 Nouvel échantillon"):
    seed = int(np.random.default_rng().integers(0, 10**6))
    st.sidebar.info(f"Graine utilisée : {seed}")
taux = st.sidebar.slider("Taux d'utilisation de l'IA visé (Q1 = Oui)", 0.10, 0.95, 0.80, 0.05)
manq = st.sidebar.slider("Non-réponse accidentelle (cellules applicables)", 0, 15, 2, format="%d %%")
st.sidebar.caption("Répartition d'âge visée (Q2)")
a1 = st.sidebar.slider("Moins de 18 ans", 0, 40, 10, format="%d %%")
a2 = st.sidebar.slider("18–24 ans", 0, 100, 62, format="%d %%")
a3 = st.sidebar.slider("25–34 ans", 0, 60, 20, format="%d %%")
a4 = st.sidebar.slider("35 ans et plus", 0, 40, 8, format="%d %%")
if a1 + a2 + a3 + a4 == 0:
    st.sidebar.warning("Au moins une tranche d'âge doit être > 0.")
    st.stop()
with st.sidebar.expander("Associations paramétrables (hypothèses)"):
    force = st.slider("Force du lien trait latent → Q5, Q7, Q9, Q12–Q15", 0.0, 1.5, 1.0, 0.1)
    l10 = st.slider("Lien trait latent → Q10 (0 = aucune association)", -1.0, 1.0, 0.0, 0.1)
    l10a = st.slider("Lien âge → Q10 (0 = aucune association)", -0.5, 0.5, 0.0, 0.05)

params = SimParams(n=n, seed=int(seed), taux_usage=taux, age_weights=(a1, a2, a3, a4),
                   taux_manquants=manq / 100, force_latent=force, lien_q10_latent=l10,
                   lien_q10_age=l10a)
df = make_data(params)
lab = with_labels(df)
STAT = status_frame(df)
EFF = effectifs(df)
users = df[df["Q1"] == 1]

# ----------------------------------------------------------------------------- en-tête
st.title("🧪 Simulateur de questionnaire — IA dans l'éducation (Q1–Q15)")
banner_box()
st.caption("Échantillon généré aléatoirement pour s'entraîner à analyser un questionnaire. "
           "Aucune connexion à Qualtrics ; aucune donnée n'est envoyée ni collectée.")

with st.expander("Hypothèses de simulation et conventions de filtre (à lire)"):
    st.markdown(
        "- **Toutes les associations entre questions sont des hypothèses pédagogiques**, pas des résultats.\n"
        "- Un trait latent d'« appétence pour l'IA » est lié positivement à Q1, Q5, Q7, Q9 et Q12–Q15 "
        "(force réglable) ; Q6 y est faiblement lié ; Q8 dépend légèrement du niveau d'études ; "
        "Q11 est indépendante du trait.\n"
        "- **Q10 : aucune association par défaut** avec le trait latent ni l'âge (curseurs à 0).\n"
        "- Le « profil latent simulé » est une catégorisation du trait latent de la simulation ; "
        "aucun profil n'est réel.\n"
        "- **Non applicable aux non-utilisateurs (minimum exigé)** : Q8, Q9, Q11, Q12.\n"
        "- **Conventions de la simulation (non vérifiées dans Qualtrics)** : Q5 et Q7 aussi réservées aux "
        "utilisateurs ; Q6, Q10, Q13, Q14, Q15 posées à tous.\n"
        "- **Non applicable ≠ manquant** : le premier découle du filtre, le second est une non-réponse "
        "accidentelle (réglable). Les analyses n'utilisent que les réponses valides ; les n sont affichés.\n"
        "- Q9–Q12 mesurent des dimensions différentes : aucun score global n'est calculé.")
    st.dataframe(pd.DataFrame(filters_table(), columns=["Question", "Posée à", "Nature de la règle"]),
                 hide_index=True, width="stretch")

c = st.columns(4)
n_q10 = n_used("Q10")
c[0].metric("Répondants simulés", len(df))
c[1].metric("Utilisent l'IA (Q1)", f"{(df.Q1 == 1).mean():.0%}", f"n = {len(df)}", delta_color="off")
c[2].metric("Amélioration perçue moy. (Q5)", f"{users.Q5.mean():.2f} / 6", f"n = {n_used('Q5')}",
            delta_color="off")
c[3].metric("Q10 : plutôt/tout à fait d'accord", f"{(df.Q10.dropna() >= 4).mean():.0%}",
            f"n = {n_q10}", delta_color="off")

tab_dist, tab_lik, tab_cross, tab_corr, tab_data, tab_export = st.tabs(
    ["📊 Profils", "📈 Échelles", "🔀 Comparaisons", "🔗 Corrélations", "🗂️ Données & effectifs",
     "⬇️ Exports"])

# ----------------------------------------------------------------------------- profils
with tab_dist:
    cols = st.columns(2)
    for i, q in enumerate(CATEGORICAL):
        opts = QUESTIONS[q]["options"]
        counts = lab[q].value_counts().reindex(opts, fill_value=0).rename_axis("Modalité").reset_index(name="n")
        counts["%"] = (counts["n"] / max(counts["n"].sum(), 1) * 100).round(1)
        fig = px.bar(counts, x="Modalité", y="n", text=counts["%"].map("{:.0f} %".format),
                     color="Modalité", color_discrete_sequence=CAT_SEQ)
        fig.update_layout(showlegend=False, yaxis_title="Effectif", xaxis_title="")
        with cols[i % 2]:
            show(style(fig, f"{short(q)} (n={n_used(q)})", 360), f"dist_{q}")
    prof = df[PROFIL_COL].value_counts().reindex(PROFILS).rename_axis("Profil").reset_index(name="n")
    fig = px.pie(prof, names="Profil", values="n", hole=0.45, color_discrete_sequence=CAT_SEQ)
    show(style(fig, f"Profil latent simulé — catégorisation du trait de la simulation (n={len(df)})", 380),
         "profils")
    st.caption("Q1–Q4 : codes 1…n dans l'ordre des modalités. Pourcentages sur les réponses valides.")

# ----------------------------------------------------------------------------- échelles
with tab_lik:
    st.info("Q5, Q7, Q8, Q9, Q11, Q12 ne sont posées qu'aux utilisateurs de l'IA (Q1 = Oui). "
            "Les échelles à 6 niveaux (Q5–Q8, Q13–Q15) et à 5 niveaux (Q9–Q12) sont présentées "
            "séparément ; elles ne sont pas comparables entre elles.")
    diverging(SCALE6_QS, 6, "Échelles à 6 niveaux — 1–3 à gauche, 4–6 à droite", "div6")
    means_plot(SCALE6_QS, 6, "Moyennes par question — échelles à 6 niveaux", "mean6")
    diverging(AGREE_QS, 5, "Accord à 5 niveaux (Q9–Q12) — 3 « Neutre » centré", "div5")
    means_plot(AGREE_QS, 5, "Moyennes par question — accord à 5 niveaux (aucun score global)", "mean5")
    stats = pd.DataFrame({"Question": SCALE_QS,
                          "n utilisé": [n_used(q) for q in SCALE_QS],
                          "Moyenne": [df[q].mean() for q in SCALE_QS],
                          "Écart-type": [df[q].std() for q in SCALE_QS]}).round(2)
    st.dataframe(stats, hide_index=True, width="stretch")

# ----------------------------------------------------------------------------- comparaisons
with tab_cross:
    left, right = st.columns(2)
    qv = left.selectbox("Variable d'intérêt", SCALE_QS, format_func=short, index=0)
    qg = right.selectbox("Comparer selon", CATEGORICAL[1:], format_func=short, index=2)
    order = QUESTIONS[qg]["options"]
    sub = lab.dropna(subset=[qv, qg]).copy()
    ncount = sub[qg].value_counts()
    sub["Groupe"] = sub[qg].map(lambda g: f"{g} (n={ncount[g]})")
    grp_order = [f"{o} (n={ncount[o]})" for o in order if o in ncount.index]
    lv = QUESTIONS[qv]["levels"]
    fig = px.box(sub, x="Groupe", y=qv, points="all", color="Groupe", category_orders={"Groupe": grp_order},
                 color_discrete_sequence=CAT_SEQ)
    fig.update_layout(showlegend=False, yaxis=dict(range=[0.5, lv + 0.5], dtick=1, title=qv),
                      xaxis_title=QUESTIONS[qg]["label"])
    show(style(fig, f"{qv} selon {qg} — {len(sub)} répondants avec réponses valides aux deux", 460), "box")
    tbl = (sub.groupby(qg, observed=True)[qv].agg(n="count", moyenne="mean", écart_type="std")
           .reindex([o for o in order if o in ncount.index]).round(2))
    tbl["alerte"] = np.where(tbl["n"] < 10, "n < 10 : prudence", "")
    st.dataframe(tbl, width="stretch")

    q4 = lab.dropna(subset=["Q1", "Q4"])
    n4 = q4["Q4"].value_counts()
    ct = pd.crosstab(q4["Q4"], q4["Q1"], normalize="index").reindex(QUESTIONS["Q4"]["options"]).dropna(how="all") * 100
    ct.index = [f"{i} (n={n4[i]})" for i in ct.index]
    fig = px.bar(ct, barmode="stack", labels={"value": "% de répondants", "index": "Niveau d'études"},
                 color_discrete_sequence=[NEG_POS[5], "#9ca3af"])
    show(style(fig, f"Utilisation de l'IA (Q1) selon le niveau d'études (Q4) — n={len(q4)}", 380), "q1q4")

# ----------------------------------------------------------------------------- corrélations
with tab_corr:
    corr = df[SCALE_QS].corr(method="spearman")
    npair = df[SCALE_QS].notna().astype(int).T @ df[SCALE_QS].notna().astype(int)
    fig = px.imshow(corr.round(2), text_auto=True, zmin=-1, zmax=1, color_continuous_scale="RdBu",
                    aspect="auto")
    show(style(fig, "Corrélations de Spearman Q5–Q15 (paires complètes ; n par paire ci-dessous)", 640),
         "corr")
    st.caption("Effectifs par paire de questions (les non-applicables et manquants sont exclus) :")
    st.dataframe(npair, width="stretch")
    st.caption("Une corrélation n'est pas une causalité ; ici elle découle des hypothèses de simulation. "
               "Avec n ≈ 70–100, des corrélations de ±0,2 à ±0,3 peuvent apparaître par simple hasard "
               "d'échantillonnage (ex. Q10, sans lien imposé par défaut).")

# ----------------------------------------------------------------------------- données
with tab_data:
    banner_box()
    st.subheader("Effectifs utilisés par question")
    st.dataframe(EFF, hide_index=True, width="stretch")
    st.caption("« Non applicable » = question non posée (filtre) ; « Manquant » = non-réponse accidentelle "
               "simulée. Les deux sont des cellules vides dans les codes : voir `Qx_statut`.")
    mode_view = st.radio("Affichage", ["Libellés", "Codes", "Statuts"], horizontal=True)
    st.dataframe({"Libellés": lab, "Codes": df, "Statuts": STAT}[mode_view], width="stretch", height=420)

# ----------------------------------------------------------------------------- exports
with tab_export:
    banner_box()
    st.write("Chaque fichier contient la mention d'avertissement (ligne `#` en tête du CSV, feuilles dédiées "
             "dans l'Excel, clé `avertissement` en JSON, colonne `Source`) et des colonnes `Qx_statut` "
             "distinguant répondu / non_applicable / manquant.")
    mode = st.selectbox("Contenu du CSV", ["both", "libellés", "codes"],
                        format_func={"both": "Libellés + colonnes *_code",
                                     "libellés": "Libellés seuls", "codes": "Codes numériques seuls"}.get)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ CSV", to_csv_bytes(df, mode), "SIMULATION_echantillon_synthetique.csv",
                       "text/csv", width="stretch")
    c2.download_button("⬇️ Excel (données, dictionnaire, filtres, effectifs)", to_excel_bytes(df),
                       "SIMULATION_echantillon_synthetique.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    c3.download_button("⬇️ JSON", to_json_bytes(df), "SIMULATION_echantillon_synthetique.json",
                       "application/json", width="stretch")
    st.caption("Relire le CSV : `pd.read_csv(fichier, comment='#', encoding='utf-8-sig')` · "
               "Excel : `pd.read_excel(fichier, sheet_name='Données', header=2)`.")

st.divider()
banner_box()
