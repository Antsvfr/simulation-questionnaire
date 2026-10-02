"""Simulateur de questionnaire « IA dans l'éducation » — Streamlit + pandas + Plotly.

Lancement : streamlit run app.py
Aucune connexion réseau, aucun envoi vers Qualtrics ou un autre service.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from simulator import (PROFILS, cronbach_alpha, export_frame, simulate, to_csv_bytes,
                       to_excel_bytes, to_json_bytes, with_labels)
from survey_config import (BANNER, CATEGORICAL, LIKERT_QS, QUESTIONS, SCALE_QS, short)

st.set_page_config(page_title="Simulation questionnaire IA & éducation", page_icon="🧪",
                   layout="wide")

NEG_POS = ["#b2182b", "#ef8a62", "#fddbc7", "#d1e5f0", "#67a9cf", "#2166ac"]  # divergente 1→6
CAT_SEQ = px.colors.qualitative.Safe


# ----------------------------------------------------------------------------- utilitaires
def banner_box():
    st.markdown(
        f"<div style='background:#fff3cd;color:#664d03;border:2px solid #e0a800;"
        f"border-radius:6px;padding:.6rem 1rem;font-weight:700;text-align:center;"
        f"letter-spacing:.02em'>⚠️ {BANNER}</div>", unsafe_allow_html=True)


def style(fig, title, height=420):
    """Applique titre + bandeau d'avertissement incrusté dans la figure (donc dans ses exports)."""
    fig.update_layout(
        title=dict(text=f"{title}<br><sup style='color:#b45309'>{BANNER}</sup>", x=0.0),
        height=height, margin=dict(t=90, b=70, l=60, r=30), legend_title_text="",
        template="plotly_white")
    fig.add_annotation(text=f"<b>{BANNER}</b>", xref="paper", yref="paper", x=0.5, y=-0.17,
                       showarrow=False, font=dict(size=10, color="#b45309"), xanchor="center")
    return fig


def show(fig, key):
    st.plotly_chart(fig, width="stretch", key=key,
                    config={"toImageButtonOptions": {"filename": "SIMULATION_graphique"}})


@st.cache_data(show_spinner=False)
def make_data(n, seed, taux, ages):
    return simulate(n, seed, taux, ages)


def likert_distribution(s: pd.Series) -> pd.Series:
    return s.dropna().astype(int).value_counts(normalize=True).reindex(range(1, 7), fill_value=0) * 100


# ----------------------------------------------------------------------------- barre latérale
st.sidebar.error(BANNER)
st.sidebar.header("Paramètres de simulation")
n = st.sidebar.slider("Taille de l'échantillon", 50, 500, 100, 10)
seed = st.sidebar.number_input("Graine aléatoire (reproductibilité)", 0, 10**6, 42)
taux = st.sidebar.slider("Taux d'utilisation de l'IA visé (Q1 = Oui)", 0.10, 0.95, 0.80, 0.05)
st.sidebar.caption("Répartition d'âge visée (Q2)")
a1 = st.sidebar.slider("Moins de 18 ans", 0, 40, 10, format="%d %%")
a2 = st.sidebar.slider("18–24 ans", 0, 100, 62, format="%d %%")
a3 = st.sidebar.slider("25–34 ans", 0, 60, 20, format="%d %%")
a4 = st.sidebar.slider("35 ans et plus", 0, 40, 8, format="%d %%")
if a1 + a2 + a3 + a4 == 0:
    st.sidebar.warning("Au moins une tranche d'âge doit être > 0.")
    st.stop()
if st.sidebar.button("🎲 Nouvel échantillon"):
    seed = int(np.random.default_rng().integers(0, 10**6))
    st.sidebar.info(f"Graine utilisée : {seed}")

df = make_data(n, int(seed), taux, (a1, a2, a3, a4))
lab = with_labels(df)
users = df[df["Q1"] == 1]

# ----------------------------------------------------------------------------- en-tête
st.title("🧪 Simulateur de questionnaire — IA dans l'éducation")
banner_box()
st.caption("Échantillon généré aléatoirement à partir de profils latents corrélés pour "
           "s'entraîner à analyser un questionnaire. Aucune connexion à Qualtrics ; "
           "aucune donnée n'est envoyée ni collectée.")

c = st.columns(4)
c[0].metric("Répondants simulés", len(df))
c[1].metric("Utilisent l'IA (Q1)", f"{(df.Q1 == 1).mean():.0%}")
c[2].metric("Amélioration perçue moy. (Q5)", f"{users.Q5.mean():.2f} / 6")
c[3].metric("Souhaitent un encadrement (Q10 ≥ 4)", f"{(df.Q10 >= 4).mean():.0%}")

tab_dist, tab_lik, tab_cross, tab_corr, tab_data, tab_export = st.tabs(
    ["📊 Profils", "📈 Échelles & Likert", "🔀 Comparaisons", "🔗 Corrélations",
     "🗂️ Données", "⬇️ Exports"])

# ----------------------------------------------------------------------------- profils
with tab_dist:
    cols = st.columns(2)
    for i, q in enumerate(CATEGORICAL):
        opts = QUESTIONS[q]["options"]
        counts = lab[q].value_counts().reindex(opts, fill_value=0).rename_axis("Modalité").reset_index(name="n")
        counts["%"] = (counts["n"] / counts["n"].sum() * 100).round(1)
        fig = px.bar(counts, x="Modalité", y="n", text=counts["%"].map("{:.0f} %".format),
                     color="Modalité", color_discrete_sequence=CAT_SEQ)
        fig.update_layout(showlegend=False, yaxis_title="Effectif", xaxis_title="")
        with cols[i % 2]:
            show(style(fig, short(q), 360), f"dist_{q}")
    prof = df["Profil_simulé"].value_counts().reindex(PROFILS).rename_axis("Profil").reset_index(name="n")
    fig = px.pie(prof, names="Profil", values="n", hole=0.45, color_discrete_sequence=CAT_SEQ)
    show(style(fig, "Profils simulés (vérité terrain de la simulation)", 380), "profils")
    st.caption("Q1–Q4 : codes 1…n dans l'ordre des modalités du questionnaire.")

# ----------------------------------------------------------------------------- Likert
with tab_lik:
    st.info("Q5 à Q9 ne sont posées qu'aux utilisateurs de l'IA (Q1 = Oui) ; Q10 est posée à tous. "
            "Les non-concernés sont codés « vide » (NaN).")
    rows = []
    for q in SCALE_QS:
        d = likert_distribution(df[q])
        rows.append(pd.DataFrame({"Question": short(q).split(" — ")[0] + " — "
                                  + QUESTIONS[q]["label"][:45], "Note": d.index, "pct": d.values}))
    long = pd.concat(rows)
    fig = go.Figure()
    for note in range(1, 7):
        sub = long[long.Note == note]
        sign = -1 if note <= 3 else 1
        fig.add_bar(y=sub.Question, x=sign * sub.pct, orientation="h", name=str(note),
                    marker_color=NEG_POS[note - 1], customdata=sub.pct,
                    hovertemplate="%{y}<br>Note " + str(note) + " : %{customdata:.1f} %<extra></extra>")
    fig.update_layout(barmode="relative", xaxis_title="% des répondants (1–3 à gauche, 4–6 à droite)",
                      yaxis=dict(autorange="reversed"))
    show(style(fig, "Distribution des réponses sur l'échelle 1–6", 460), "likert_div")

    mean_sd = pd.DataFrame({"Question": SCALE_QS,
                            "Moyenne": [df[q].mean() for q in SCALE_QS],
                            "Écart-type": [df[q].std() for q in SCALE_QS],
                            "n valides": [int(df[q].notna().sum()) for q in SCALE_QS]}).round(2)
    fig = px.bar(mean_sd, x="Question", y="Moyenne", error_y="Écart-type", text="Moyenne",
                 color_discrete_sequence=[NEG_POS[5]])
    fig.update_yaxes(range=[0, 7], title="Moyenne (1–6)")
    show(style(fig, "Moyennes ± écart-type", 380), "means")
    st.dataframe(mean_sd, hide_index=True, width="stretch")
    alpha = cronbach_alpha(df[["Q5", "Q6", "Q7", "Q9"]])
    st.metric("Alpha de Cronbach (Q5, Q6, Q7, Q9 — à titre pédagogique)", f"{alpha:.2f}")

# ----------------------------------------------------------------------------- comparaisons
with tab_cross:
    left, right = st.columns(2)
    qv = left.selectbox("Variable d'intérêt", SCALE_QS, format_func=short, index=0)
    qg = right.selectbox("Comparer selon", CATEGORICAL[1:], format_func=short, index=2)
    order = QUESTIONS[qg]["options"]
    fig = px.box(lab.dropna(subset=[qv]), x=qg, y=qv, points="all", color=qg,
                 category_orders={qg: order}, color_discrete_sequence=CAT_SEQ)
    fig.update_layout(showlegend=False, yaxis=dict(range=[0.5, 6.5], dtick=1, title=qv),
                      xaxis_title=QUESTIONS[qg]["label"])
    show(style(fig, f"{qv} selon {qg}", 460), "box")
    grp = (lab.dropna(subset=[qv]).groupby(qg, observed=True)[qv]
           .agg(n="count", moyenne="mean", écart_type="std").reindex(order).round(2))
    st.dataframe(grp, width="stretch")
    st.caption("⚠️ Petits effectifs par groupe : interpréter avec prudence (c'est aussi une leçon de la simulation).")

    ct = pd.crosstab(lab["Q4"], lab["Q1"], normalize="index").reindex(QUESTIONS["Q4"]["options"]) * 100
    fig = px.bar(ct, barmode="stack", labels={"value": "% de répondants", "Q4": "Niveau d'études"},
                 color_discrete_sequence=[NEG_POS[5], "#9ca3af"])
    show(style(fig, "Utilisation de l'IA (Q1) selon le niveau d'études (Q4)", 380), "q1q4")

# ----------------------------------------------------------------------------- corrélations
with tab_corr:
    corr = df[SCALE_QS].corr(method="spearman")
    fig = px.imshow(corr.round(2), text_auto=True, zmin=-1, zmax=1, color_continuous_scale="RdBu",
                    aspect="auto")
    show(style(fig, "Corrélations de Spearman (Q5–Q10, paires complètes)", 520), "corr")

# ----------------------------------------------------------------------------- données
with tab_data:
    banner_box()
    mode_view = st.radio("Affichage", ["Libellés", "Codes"], horizontal=True)
    st.dataframe(lab if mode_view == "Libellés" else df, width="stretch", height=480)
    st.caption("Chaque ligne porte `Source = SIMULATION`.")

# ----------------------------------------------------------------------------- exports
with tab_export:
    banner_box()
    st.write("Chaque fichier exporté contient la mention d'avertissement "
             "(ligne `#` en tête du CSV, feuilles dédiées dans l'Excel, clé `avertissement` en JSON, "
             "colonne `Source`).")
    mode = st.selectbox("Contenu du CSV", ["both", "libellés", "codes"],
                        format_func={"both": "Libellés + colonnes *_code",
                                     "libellés": "Libellés seuls", "codes": "Codes numériques seuls"}.get)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ CSV", to_csv_bytes(df, mode), "SIMULATION_echantillon_synthetique.csv",
                       "text/csv", width="stretch")
    c2.download_button("⬇️ Excel (données + dictionnaire)", to_excel_bytes(df),
                       "SIMULATION_echantillon_synthetique.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")
    c3.download_button("⬇️ JSON", to_json_bytes(df), "SIMULATION_echantillon_synthetique.json",
                       "application/json", width="stretch")
    st.caption("Relire le CSV : `pd.read_csv(fichier, comment='#', encoding='utf-8-sig')` · "
               "Excel : `pd.read_excel(fichier, sheet_name='Données', header=2)`.")

st.divider()
banner_box()
