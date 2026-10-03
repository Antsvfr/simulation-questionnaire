"""Exports CSV / Excel / JSON construits depuis l'échantillon actif (tout ou profils filtrés)."""
from __future__ import annotations

import io
import json
from dataclasses import asdict

import numpy as np
import pandas as pd

from simulator import SimParams, status_frame
from survey_config import BANNER, QUESTIONS, codebook, filters_table
from views import (ORIGINE, Filters, MISS_TXT, NA_TXT, codes_frame, composition_long, counts,
                   readable_frame)

SHEETS = ["Réponses lisibles", "Codes et statuts", "Dictionnaire", "Composition",
          "Paramètres et méthode"]


def select(df: pd.DataFrame, ids) -> pd.DataFrame:
    return df if ids is None else df[df["ID"].isin(set(ids))]


def readable_export(d):
    out = readable_frame(d)
    out.insert(1, ORIGINE, BANNER)
    return out


def codes_export(d):
    out = codes_frame(d, with_status=True)
    out.insert(1, ORIGINE, BANNER)
    return out


def dictionary():
    cb = pd.DataFrame(codebook(), columns=["Question", "Intitulé", "Code", "Modalité"])
    cb["Texte affiché dans la fiche"] = cb["Question"].map(lambda q: QUESTIONS[q]["text"])
    cb["Texte = intitulé seul"] = cb["Question"].map(lambda q: QUESTIONS[q]["text_is_title"])
    flt = pd.DataFrame(filters_table(), columns=["Question", "Posée à", "Nature de la règle"])
    st = pd.DataFrame({"Statut": ["répondu", "non_applicable", "manquant"],
                       "Signification": ["Réponse valide enregistrée",
                                         f"Question non posée à ce profil (« {NA_TXT} »), pas un oubli",
                                         f"Question applicable sans réponse, non-réponse accidentelle "
                                         f"simulée (« {MISS_TXT} »)"]})
    return cb, flt, st


def method_table(params: SimParams, scope: str, n_total: int, n_exported: int, filt: Filters | None):
    a = np.asarray(params.age_weights, float)
    rows = [("Origine", BANNER), ("Connexion Qualtrics", "Aucune : rien n'est envoyé ni collecté"),
            ("Périmètre exporté", scope), ("Profils exportés", n_exported),
            ("Profils générés (échantillon actif)", n_total),
            ("Filtres appliqués", filt.describe() if filt else "aucun (échantillon complet)"),
            ("Graine", params.seed), ("Taille demandée", params.n),
            ("Taux d'utilisation visé (Q1 = Oui)", params.taux_usage),
            ("Répartition d'âge saisie", str(tuple(params.age_weights))),
            ("Répartition d'âge normalisée (%)", str(tuple(np.round(a / a.sum() * 100, 1)))),
            ("Pondérations genre", str(tuple(params.genre_weights))),
            ("Non-réponse accidentelle (par cellule applicable)", params.taux_manquants),
            ("Force du lien trait latent → Q5, Q7, Q9, Q12–Q15", params.force_latent),
            ("Lien trait latent → Q10 (0 = aucune association)", params.lien_q10_latent),
            ("Lien âge → Q10 (0 = aucune association)", params.lien_q10_age),
            ("Méthode", "Trait latent « appétence pour l'IA » gaussien ; Q1 par régression logistique "
                        "calée sur le taux visé ; réponses ordinales par arrondi d'une valeur latente "
                        "bruitée. Toutes les associations sont des hypothèses pédagogiques."),
            ("Questionnaire complet", "Aucune réponse accidentellement manquante parmi les questions "
                                      "applicables. Une réponse non applicable n'est pas un oubli."),
            ("Échelles", "Q5–Q8 et Q13–Q15 : 1–6 ; Q9–Q12 : accord à 5 modalités. Aucun score global."),
            ("Profil latent simulé", "Information interne au modèle, non observable dans un vrai "
                                     "questionnaire ; aucun profil n'est réel.")]
    return pd.DataFrame(rows, columns=["Rubrique", "Valeur"]).astype({"Valeur": str})


def _csv(frame: pd.DataFrame) -> bytes:
    # BOM UTF-8 : accents corrects à l'ouverture dans Excel ; relire avec encoding="utf-8-sig".
    return ("﻿" + frame.to_csv(index=False)).encode("utf-8")


def csv_readable(d) -> bytes:
    return _csv(readable_export(d))


def csv_codes(d) -> bytes:
    return _csv(codes_export(d))


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


def excel_bytes(d, params: SimParams, scope: str, n_total: int, filt: Filters | None,
                params_full_scope: bool) -> bytes:
    cb, flt, st = dictionary()
    comp = composition_long(d, scope, params if params_full_scope else None)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        readable_export(d).to_excel(xw, sheet_name=SHEETS[0], index=False)
        codes_export(d).to_excel(xw, sheet_name=SHEETS[1], index=False)
        r = 2  # tableaux annexes : bandeau en A1, tableaux à partir de la ligne 3
        for name, frames in ((SHEETS[2], [cb, flt, st]), (SHEETS[3], [comp]),
                             (SHEETS[4], [method_table(params, scope, n_total, len(d), filt)])):
            row = r
            for fr in frames:
                fr.to_excel(xw, sheet_name=name, index=False, startrow=row)
                row += len(fr) + 3
            xw.sheets[name]["A1"] = BANNER
        for ws in xw.book.worksheets:
            ws.freeze_panes = "B2" if ws.title in SHEETS[:2] else None
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col[:60])
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 70)
    return buf.getvalue()


def json_bytes(d, params: SimParams, scope: str, n_total: int, filt: Filters | None) -> bytes:
    payload = {"avertissement": BANNER, "perimetre": scope, "profils_generes": n_total,
               "parametres": asdict(params),
               "filtres": filt.describe() if filt else "aucun",
               "note": "null = non applicable ou manquant : voir Qx_statut",
               "profils": json.loads(codes_export(d).to_json(orient="records"))}
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
