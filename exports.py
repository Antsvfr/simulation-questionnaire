"""Exports CSV / Excel / JSON construits depuis l'échantillon actif (tout ou profils filtrés)."""
from __future__ import annotations

import io
import json
from dataclasses import asdict

import numpy as np
import pandas as pd

import compliance
from simulator import SimParams
from survey_config import BANNER, FILTER_MODE_LABELS, MODE_FILTRE, QUESTIONS, codebook, filters_table
from views import (ORIGINE, Filters, MISS_TXT, NA_TXT, Q1_BIN_COL, codes_frame, composition_long,
                   counts, readable_frame)

SHEETS = ["Réponses lisibles", "Codes et statuts", "Dictionnaire", "Composition", "Paramètres",
          "Méthode et limites", "Contrôle de conformité", "Préparation de la base"]


def select(df: pd.DataFrame, ids) -> pd.DataFrame:
    return df if ids is None else df[df["ID"].isin(set(ids))]


def readable_export(d, mode: str = MODE_FILTRE):
    out = readable_frame(d, mode)
    out.insert(1, ORIGINE, BANNER)
    return out


def codes_export(d, mode: str = MODE_FILTRE):
    out = codes_frame(d, mode, with_status=True)
    out.insert(1, ORIGINE, BANNER)
    return out


VAR_TYPE = {"single": "Nominale", "agree": "Ordinale (5 modalités)", "scale": "Ordinale (8 modalités)"}


def dictionary(mode: str = MODE_FILTRE, df=None):
    """Dictionnaire complet : une ligne par (question, code), avec la formulation complète, le
    libellé exact de la modalité (jamais vide) et le type de variable — utilisé tel quel partout
    (génération, tableaux, graphiques, fiches, exports)."""
    cb = pd.DataFrame(codebook(), columns=["Question", "Formulation complète", "Code", "Libellé exact"])
    cb["Type de variable"] = cb["Question"].map(lambda q: VAR_TYPE[QUESTIONS[q]["kind"]])
    cb = cb[["Question", "Formulation complète", "Code", "Libellé exact", "Type de variable"]]
    flt = pd.DataFrame(filters_table(mode, df),
                       columns=["Question", "Posée à", "Nature de la règle", "Profils concernés"])
    st = pd.DataFrame({"Statut": ["répondu", "non_applicable", "manquant"],
                       "Signification": ["Réponse valide enregistrée",
                                         f"Question non posée à ce profil (« {NA_TXT} »), pas un oubli",
                                         f"Question applicable sans réponse, non-réponse accidentelle "
                                         f"simulée (« {MISS_TXT} »)"]})
    deriv = pd.DataFrame([{"Colonne": Q1_BIN_COL, "Origine": "Q1",
                          "Définition": "Oui → 1, Non → 0. Q1 d'origine est conservée telle quelle. "
                          "Ne recode jamais Q8, qui n'est pas une variable Oui/Non."}])
    return cb, flt, st, deriv


def parametres_table(params: SimParams, scope: str, n_total: int, n_exported: int,
                     filt: Filters | None) -> pd.DataFrame:
    """Feuille « Paramètres » : exactement les paramètres ayant réellement servi à produire
    l'échantillon actif — jamais les réglages affichés dans l'interface s'ils ont été modifiés
    depuis sans être appliqués (voir app.py : ce sont deux objets différents)."""
    a = np.asarray(params.age_weights, float)
    rows = [
        ("Version du questionnaire", params.version),
        ("Version du modèle de génération", params.model_version),
        ("Graine", params.seed),
        ("Taille de l'échantillon (demandée)", params.n),
        ("Taille de l'échantillon (générée)", n_total),
        ("Mode de filtrage", FILTER_MODE_LABELS.get(params.filter_mode, params.filter_mode)),
        ("Taux de non-réponse configuré (par cellule applicable)", params.taux_manquants),
        ("— Probabilités et associations utilisées —", ""),
        ("Taux d'utilisation de l'IA visé (Q1 = Oui)", params.taux_usage),
        ("Répartition d'âge saisie (Q2)", str(tuple(params.age_weights))),
        ("Répartition d'âge normalisée (%)", str(tuple(float(x) for x in np.round(a / a.sum() * 100, 1)))),
        ("Pondérations de genre (Q3)", str(tuple(params.genre_weights))),
        ("Force du lien trait latent → Q5, Q7, Q9, Q12–Q15", params.force_latent),
        ("Lien trait latent → Q10 (0 = aucune association)", params.lien_q10_latent),
        ("Lien âge → Q10 (0 = aucune association)", params.lien_q10_age),
        ("— Contexte de cet export —", ""),
        ("Périmètre exporté", scope), ("Profils exportés", n_exported),
        ("Filtres d'affichage appliqués à cet export", filt.describe() if filt else
         "aucun (échantillon complet)"),
    ]
    return pd.DataFrame(rows, columns=["Paramètre", "Valeur"]).astype({"Valeur": str})


def method_table(params: SimParams) -> pd.DataFrame:
    """Feuille « Méthode et limites » : comment les données sont construites, et ce que les chiffres
    ne permettent pas de conclure. Les paramètres eux-mêmes sont dans la feuille « Paramètres »."""
    rows = [
        ("Origine", BANNER), ("Connexion Qualtrics", "Aucune : rien n'est envoyé ni collecté"),
        ("Méthode de génération", "Trait latent « appétence pour l'IA » gaussien ; Q1 par régression "
                                  "logistique calée sur le taux visé ; réponses ordinales par arrondi "
                                  "d'une valeur latente bruitée, sur l'échelle exacte du questionnaire "
                                  "(8 modalités pour Q5–Q8 et Q13–Q15, 5 pour Q9–Q12)."),
        ("Objectif des paramètres", "Aucune association n'est réglée pour obtenir une conclusion, une "
                                    "corrélation précise ou un résultat significatif prédéterminés : "
                                    "voir la feuille Contrôle de conformité pour les vérifications "
                                    "réellement effectuées, et Préparation de la base pour les limites."),
        ("Questionnaire complet", "Aucune réponse accidentellement manquante parmi les questions "
                                  "applicables dans le mode actif. Une réponse non applicable n'est "
                                  "jamais comptée comme un oubli (voir feuille Dictionnaire, onglet "
                                  "filtres)."),
        ("Échelles", "Q5–Q8 et Q13–Q15 : 8 modalités distinctes (codes 1 et 8 = ancrages du "
                    "questionnaire propres à chaque question, codes 2 à 7 = libellés « 1 » à « 6 »). "
                    "Q9–Q12 : accord à 5 modalités. Jamais combinées entre elles ni avec un score "
                    "global (voir Préparation de la base)."),
        ("Profil latent simulé", "Information interne au modèle, non observable dans un vrai "
                                 "questionnaire ; aucun profil n'est réel."),
        ("Versions et compatibilité", f"Un échantillon généré sous une version différente de "
         f"{params.version} / {params.model_version} n'est jamais réinterprété automatiquement : il "
         f"est conservé de côté et signalé comme incompatible (voir l'avertissement dans l'application)."),
    ]
    return pd.DataFrame(rows, columns=["Rubrique", "Valeur"]).astype({"Valeur": str})


def _csv(frame: pd.DataFrame) -> bytes:
    # BOM UTF-8 : accents corrects à l'ouverture dans Excel ; relire avec encoding="utf-8-sig".
    return ("﻿" + frame.to_csv(index=False)).encode("utf-8")


def csv_readable(d, mode: str = MODE_FILTRE) -> bytes:
    return _csv(readable_export(d, mode))


def csv_codes(d, mode: str = MODE_FILTRE) -> bytes:
    return _csv(codes_export(d, mode))


def filename(kind: str, ext: str, params: SimParams, scope_key: str, n_rows: int) -> str:
    return f"SIMULATION_SYNTHETIQUE_{kind}_{scope_key}_graine{params.seed}_{n_rows}profils.{ext}"


def analysis_csv(table: pd.DataFrame) -> bytes:
    """Export d'un tableau d'analyse courant (déjà agrégé) : origine en première colonne, BOM UTF-8."""
    out = table.copy()
    out.insert(0, ORIGINE, BANNER)
    return _csv(out)


def analysis_filename(name: str, params: SimParams) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in name.strip().lower()).strip("_")[:60]
    return f"SIMULATION_SYNTHETIQUE_analyse_{slug}_graine{params.seed}.csv"


_FILL = {compliance.VERT: ("C6EFCE", "006100"), compliance.ROUGE: ("FFC7CE", "9C0006"),
        compliance.GRIS: ("D9D9D9", "404040")}


def _colorize_statut(ws, header_row: int, df: pd.DataFrame, statut_col: str = "Statut"):
    """Colore chaque ligne d'un tableau Vert/Rouge/Gris selon sa colonne `statut_col` (openpyxl,
    donc visible en rouvrant le fichier, pas seulement du texte)."""
    from openpyxl.styles import Font, PatternFill
    col_idx = list(df.columns).index(statut_col) + 1
    for i, val in enumerate(df[statut_col]):
        fill_hex, font_hex = _FILL.get(val, ("FFFFFF", "000000"))
        fill = PatternFill("solid", fgColor=fill_hex)
        font = Font(color=font_hex, bold=True)
        excel_row = header_row + 2 + i  # +1 bandeau A1, +1 en-tête, +1 base-1
        for c in range(1, len(df.columns) + 1):
            ws.cell(row=excel_row, column=c).fill = fill
        ws.cell(row=excel_row, column=col_idx).font = font


def excel_bytes(d, params: SimParams, scope: str, n_total: int, filt: Filters | None,
                params_full_scope: bool, df_full: pd.DataFrame | None = None) -> bytes:
    """`df_full` : l'échantillon actif complet (non filtré), utilisé pour les contrôles de
    conformité et le dénombrement précis des filtres. Par défaut égal à `d` (cas de l'export complet)."""
    mode = params.filter_mode
    full = df_full if df_full is not None else d
    cb, flt, st, deriv = dictionary(mode, d)
    comp = composition_long(d, scope, params if params_full_scope else None)
    param_tbl = parametres_table(params, scope, n_total, len(d), filt)
    meth_tbl = method_table(params)
    ctrl_tbl = compliance.control_table(full, params)
    prep_tbl = compliance.prep_base_table(full, params)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        readable_export(d, mode).to_excel(xw, sheet_name=SHEETS[0], index=False)
        codes_export(d, mode).to_excel(xw, sheet_name=SHEETS[1], index=False)
        r = 2  # tableaux annexes : bandeau en A1, tableaux à partir de la ligne 3
        plan = {SHEETS[2]: [cb, flt, st, deriv], SHEETS[3]: [comp], SHEETS[4]: [param_tbl],
               SHEETS[5]: [meth_tbl], SHEETS[6]: [ctrl_tbl], SHEETS[7]: [prep_tbl]}
        for name, frames in plan.items():
            row = r
            for fr in frames:
                fr.to_excel(xw, sheet_name=name, index=False, startrow=row)
                row += len(fr) + 3
            xw.sheets[name]["A1"] = BANNER
        _colorize_statut(xw.sheets[SHEETS[6]], r, ctrl_tbl)
        _colorize_statut(xw.sheets[SHEETS[7]], r, prep_tbl)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "B2" if ws.title in SHEETS[:2] else None
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col[:60])
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 70)
    return buf.getvalue()


def json_bytes(d, params: SimParams, scope: str, n_total: int, filt: Filters | None) -> bytes:
    payload = {"avertissement": BANNER, "version_questionnaire": params.version,
               "version_modele_generation": params.model_version,
               "mode_filtrage": params.filter_mode, "perimetre": scope, "profils_generes": n_total,
               "parametres": asdict(params),
               "filtres": filt.describe() if filt else "aucun",
               "note": "null = non applicable ou manquant : voir Qx_statut",
               "profils": json.loads(codes_export(d, params.filter_mode).to_json(orient="records"))}
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
