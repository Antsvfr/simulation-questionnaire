"""Contrôle de conformité : vérifications calculées sur l'échantillon et la configuration actifs,
jamais déduites ni supposées. Chaque ligne compare un résultat attendu à un résultat réellement
observé (sur les données en mémoire), avec un statut Vert/Rouge/Gris et une explication en cas
d'écart. Un statut n'est jamais forcé à Vert : à défaut de vérification possible, il est Gris.

Complète ce fichier plutôt que d'écrire les vérifications ailleurs : app.py et exports.py affichent
`control_table()` / `prep_base_table()` tels quels.
"""
from __future__ import annotations

import pandas as pd

from simulator import (GENERATOR_VERSION, SimParams, check_full_range, check_reproducible,
                       effectifs, status_frame)
from survey_config import ALL_QS, EXPERIENCE_QS, QUESTIONNAIRE_VERSION, QUESTIONS, codebook

VERT, ROUGE, GRIS = "Vert", "Rouge", "Gris"
COLS = ["Contrôle", "Résultat attendu", "Résultat observé", "Statut", "Explication en cas d'écart"]
PREP_COLS = ["Élément", "Résultat attendu", "Résultat observé", "Statut", "Explication"]


def _row(name, expected, observed, ok_condition, gris=False, explain_ok="", explain_ko=""):
    if gris:
        statut, explain = GRIS, explain_ok
    elif ok_condition:
        statut, explain = VERT, explain_ok
    else:
        statut, explain = ROUGE, explain_ko or "Écart détecté — voir le résultat observé ci-contre."
    return {"Contrôle": name, "Résultat attendu": expected, "Résultat observé": observed,
           "Statut": statut, "Explication en cas d'écart": explain}


def control_table(df_full: pd.DataFrame, params: SimParams) -> pd.DataFrame:
    """Un contrôle par ligne, calculé sur `df_full` (l'échantillon actif complet, non filtré) et
    `params` (les paramètres ayant réellement servi à le générer)."""
    rows = []
    mode = params.filter_mode

    # 1. Taille générée == taille demandée
    rows.append(_row("Taille de l'échantillon généré", f"{params.n} profils", f"{len(df_full)} profils",
                     len(df_full) == params.n,
                     explain_ko=f"La génération a produit {len(df_full)} lignes pour {params.n} demandées."))

    # 2. Identifiants uniques
    dup = int(df_full["ID"].duplicated().sum()) if "ID" in df_full else len(df_full)
    rows.append(_row("Identifiants uniques", "0 doublon", f"{dup} doublon(s)", dup == 0,
                     explain_ko=f"{dup} identifiant(s) ID apparaissent plus d'une fois, ou colonne ID absente."))

    # 3. Q1 à Q15 présentes — vérifié avant tout calcul utilisant ces colonnes, pour ne jamais
    # planter sur un échantillon corrompu : une colonne manquante doit produire une ligne Rouge,
    # pas une exception.
    missing_cols = [q for q in ALL_QS if q not in df_full.columns]
    rows.append(_row("Colonnes Q1 à Q15 présentes", "Q1 … Q15", "Q1 … Q15" if not missing_cols
                     else f"manquent : {', '.join(missing_cols)}", not missing_cols,
                     explain_ko=f"Colonnes absentes : {', '.join(missing_cols)}."))

    # Les contrôles suivants portent sur les colonnes présentes ; une colonne manquante est déjà
    # signalée ci-dessus et complétée ici en NaN pour que les autres contrôles restent calculables
    # (ils la traiteront comme 100 % manquante, sans jamais masquer l'anomalie n°3 ci-dessus).
    df_full = df_full.copy()
    for q in missing_cols:
        df_full[q] = float("nan")
    if "Q1" not in df_full:
        return pd.DataFrame(rows, columns=COLS)  # Q1 absente : rien d'autre n'est calculable
    st = status_frame(df_full, mode)
    eff = effectifs(df_full, mode)

    # 4. Valeurs conformes aux modalités autorisées (ou NaN)
    bad = {}
    for q, spec in QUESTIONS.items():
        k = len(spec["options"]) if spec["kind"] == "single" else spec["levels"]
        valid = df_full[q].dropna().astype(int)
        hors_bornes = valid[(valid < 1) | (valid > k)]
        if len(hors_bornes):
            bad[q] = len(hors_bornes)
    rows.append(_row("Valeurs dans les modalités autorisées (1..k ou vide)", "Aucune valeur hors bornes",
                     "Aucune valeur hors bornes" if not bad else f"hors bornes : {bad}", not bad,
                     explain_ko=f"Codes hors bornes trouvés : {bad}."))

    # 5. Dictionnaire complet (aucun libellé de modalité vide)
    cb = codebook()
    vides = [(q, c) for q, _, c, lab in cb if not str(lab).strip()]
    rows.append(_row("Dictionnaire complet (aucun libellé vide)", "0 libellé vide",
                     "0 libellé vide" if not vides else f"{len(vides)} libellé(s) vide(s) : {vides}",
                     not vides, explain_ko=f"Entrées sans libellé : {vides}."))

    # 5bis. Code 6 d'une échelle à 8 modalités == libellé "5" (jamais l'ancrage haut)
    ko6 = {q: QUESTIONS[q]["anchors"][6] for q in ALL_QS
          if QUESTIONS[q].get("levels") == 8 and QUESTIONS[q]["anchors"][6] != "5"}
    rows.append(_row("Code 6 (échelle à 8 modalités) = libellé « 5 »", "« 5 » pour Q5, Q6, Q7, Q8, "
                     "Q13, Q14, Q15", "« 5 » pour toutes" if not ko6 else str(ko6), not ko6,
                     explain_ko=f"Code 6 mal étiqueté pour : {ko6} (ne doit jamais être l'ancrage haut)."))

    # 6. Cohérence valeurs <-> statuts
    incoh = 0
    for q in ALL_QS:
        s = st[q]
        incoh += int(((s == "répondu") & df_full[q].isna()).sum())
        incoh += int(((s != "répondu") & df_full[q].notna()).sum())
    rows.append(_row("Cohérence entre valeurs et statuts", "0 incohérence",
                     f"{incoh} incohérence(s)", incoh == 0,
                     explain_ko="Au moins une cellule a un statut qui ne correspond pas à sa valeur "
                                "(ex. « répondu » sans valeur, ou valeur présente marquée absente)."))

    # 7. Effectifs réconciliés : répondu + non_applicable + manquant == total, par question
    recon_bad = eff[eff["Répondu (n utilisé)"] + eff["Non applicable"] + eff["Manquant (accidentel)"]
                    != len(df_full)]["Question"].tolist()
    rows.append(_row("Effectifs réconciliés avec les données", f"Somme = {len(df_full)} pour chaque question",
                     "Conforme pour toutes" if not recon_bad else f"écart pour : {recon_bad}",
                     not recon_bad, explain_ko=f"Questions avec une somme incorrecte : {recon_bad}."))

    # 8. Paramètres et version présents
    champs = {"version (questionnaire)": params.version, "model_version (générateur)": params.model_version,
             "seed": params.seed, "n": params.n, "filter_mode": params.filter_mode,
             "taux_manquants": params.taux_manquants}
    vides_p = [k for k, v in champs.items() if v is None or v == ""]
    rows.append(_row("Paramètres et version présents", "Tous les champs renseignés",
                     "Tous renseignés" if not vides_p else f"manquants : {vides_p}", not vides_p,
                     explain_ko=f"Champs vides ou absents : {vides_p}."))

    # 9. Conformité des versions à la version actuelle de l'application
    conforme = params.version == QUESTIONNAIRE_VERSION and params.model_version == GENERATOR_VERSION
    rows.append(_row("Versions conformes à l'application actuelle",
                     f"{QUESTIONNAIRE_VERSION} / {GENERATOR_VERSION}",
                     f"{params.version} / {params.model_version}", conforme,
                     explain_ko="Échantillon généré sous une version différente : voir l'avertissement "
                                "de compatibilité. Les réponses ne sont jamais converties entre versions."))

    # 10. Reproductibilité (régénération réelle, pas supposée)
    repro = check_reproducible(params)
    rows.append(_row("Reproductibilité (mêmes graine + paramètres + versions)", "Données identiques",
                     "Données identiques" if repro else "Données différentes", repro,
                     explain_ko="Deux générations avec des paramètres strictement identiques ont produit "
                                "des données différentes : le générateur n'est pas déterministe."))

    # 11. Modalités extrêmes AUTORISÉES par le générateur (tirage indépendant, grand n — jamais
    # déduit de l'échantillon actif, dont un petit effectif ne prouverait rien).
    full_range = check_full_range(params)
    incomplets = {q: sorted(set(range(1, QUESTIONS[q]["levels"] + 1)) - r["observe"])
                 for q, r in full_range.items() if not r["complet"]}
    rows.append(_row("Le générateur autorise tous les codes (1..8 ou 1..5), y compris les extrémités",
                     "Tous les codes atteints sur un tirage indépendant de 20 000 profils",
                     "Tous atteints" if not incomplets else f"jamais observés : {incomplets}",
                     not incomplets,
                     explain_ko=f"Même sur 20 000 profils, certains codes ne sont jamais tirés : "
                                f"{incomplets}. Le générateur limite peut-être leur probabilité à 0."))

    # 12. Information (jamais un échec) : présence des codes extrêmes dans l'échantillon ACTIF actuel.
    # Leur absence sur un petit échantillon n'est pas une anomalie — voir le contrôle 11 ci-dessus,
    # qui est le seul habilité à juger si le générateur les autorise.
    absents_ici = {}
    for q in ALL_QS:
        spec = QUESTIONS[q]
        if spec["kind"] == "single":
            continue
        present = set(df_full[q].dropna().astype(int).unique())
        manquants = sorted({1, spec["levels"]} - present)
        if manquants:
            absents_ici[q] = manquants
    rows.append({"Contrôle": "Codes extrêmes observés dans l'échantillon actif (information)",
                "Résultat attendu": "Non applicable : dépend du tirage et de la taille de l'échantillon",
                "Résultat observé": "Tous présents ici" if not absents_ici else f"absents ici : {absents_ici}",
                "Statut": GRIS,
                "Explication en cas d'écart": ("—" if not absents_ici else
                    f"Sur {len(df_full)} profils, certains codes extrêmes n'apparaissent pas "
                    f"({absents_ici}). Ce n'est pas une erreur en soi (voir le contrôle précédent, qui "
                    f"vérifie séparément que le générateur les autorise) ; régénérer un échantillon plus "
                    f"grand les ferait probablement apparaître.")})

    return pd.DataFrame(rows, columns=COLS)


def prep_base_table(df_full: pd.DataFrame, params: SimParams) -> pd.DataFrame:
    """« Préparation de la base » : limites et non-applicabilités traitées honnêtement, toujours en
    gris (ni vert ni rouge : ce ne sont pas des contrôles réussis/échoués mais des choix de portée)."""
    mode = params.filter_mode
    eff = effectifs(df_full, mode)
    sub = eff[eff["Question"].isin(["Q9", "Q10", "Q11", "Q12"])]
    manq_lines = "; ".join(f"{r['Question']} : {r['Manquant (accidentel)']}/{r['Applicable (posée à)']}"
                           for _, r in sub.iterrows())
    rows = [
        {"Élément": "Données manquantes (dénominateur = questions applicables)",
         "Résultat attendu": "Compté avec un dénominateur explicite par question",
         "Résultat observé": manq_lines or "aucune question concernée",
         "Statut": GRIS, "Explication": "Dénominateur = profils pour qui la question est applicable "
         "dans le mode actif ; voir la feuille Composition et effectifs() pour le détail des 15 questions."},
        {"Élément": "Test d'attention", "Résultat attendu": "—", "Résultat observé": "Absent",
         "Statut": GRIS, "Explication": "Ce questionnaire ne comporte aucun test d'attention : aucun "
         "résultat de réussite/échec n'est calculé, et aucun profil n'est écarté pour ce motif."},
        {"Élément": "Recodage binaire de Q8", "Résultat attendu": "—",
         "Résultat observé": "Non applicable", "Statut": GRIS,
         "Explication": "Q8 n'est pas une variable Oui/Non et n'est jamais recodée en binaire. Seule "
         "Q1 (déjà binaire par nature) a une variable dérivée Q1_binaire ; Q1 d'origine est conservée."},
        {"Élément": "Indice composite Q9–Q12", "Résultat attendu": "—", "Résultat observé": "Non défini",
         "Statut": GRIS, "Explication": "Q9 à Q12 mesurent des dimensions différentes (qualité perçue "
         "du travail, encadrement souhaité, vérification des informations, autonomie) : aucun indice "
         "composite n'est calculé en les combinant."},
        {"Élément": "Portée de ce questionnaire", "Résultat attendu": "—",
         "Résultat observé": "Usage de l'IA dans l'éducation (Q1–Q15)", "Statut": GRIS,
         "Explication": "Ce questionnaire sur l'IA dans l'éducation ne remplace pas, et n'a aucun lien "
         "avec, une éventuelle base de satisfaction professionnelle L5 : les deux sont des instruments "
         "distincts qui ne doivent pas être confondus ni fusionnés."},
    ]
    return pd.DataFrame(rows, columns=PREP_COLS)
