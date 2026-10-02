import io
import pandas as pd
from simulator import simulate, to_csv_bytes, to_excel_bytes, to_json_bytes
from survey_config import BANNER, QUESTIONS


def test_reproductible_et_dimensions():
    a, b = simulate(100, 1), simulate(100, 1)
    assert a.equals(b) and len(a) == 100


def test_codes_valides_et_filtre():
    d = simulate(300, 3)
    for q, spec in QUESTIONS.items():
        valid = set(range(1, len(spec["options"]) + 1)) if spec["kind"] == "single" else set(range(1, 7))
        assert set(d[q].dropna().astype(int)) <= valid
    assert d.loc[d.Q1 == 2, ["Q5", "Q6", "Q7", "Q8", "Q9"]].isna().all().all()
    assert d["Q10"].notna().all()


def test_age_niveau_coherents():
    d = simulate(500, 5)
    assert (d.loc[d.Q2 == 1, "Q4"] <= 2).all()


def test_exports_portent_l_avertissement():
    d = simulate(100, 2)
    assert BANNER in to_csv_bytes(d).decode()
    assert BANNER in to_json_bytes(d).decode()
    x = pd.read_excel(io.BytesIO(to_excel_bytes(d)), sheet_name=None, header=None)
    assert all(s.astype(str).apply(lambda c: c.str.contains(BANNER, regex=False)).any().any() for s in x.values())
