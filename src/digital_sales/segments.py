"""Segment effects: the visit lift of each email within customer segments, and whether it differs between them."""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from digital_sales.experiment import proportion_test, values
from digital_sales.paths import DB_PATH, SQL_DIR

# Segment column -> (display name, segments in display order). Labels match sql/03_segments.sql.
DIMENSIONS = {
    "recency_band": ("Recency", ["1-3 months", "4-8 months", "9-12 months"]),
    "history_band": ("Past-year spend", ["Under $92", "$92-254", "$255+"]),
    "buyer_type":   ("Buyer type", ["Men's only", "Women's only", "Both"]),
    "channel":      ("Channel", ["Phone", "Web", "Multichannel"]),
    "newbie":       ("Customer", ["New", "Existing"]),
    "zip_code":     ("Area", ["Urban", "Suburban", "Rural"]),
}

EMAILS = ["mens_email", "womens_email"]

COMPARISONS = [
    ("mens_email", "no_email"),
    ("womens_email", "no_email"),
    ("mens_email", "womens_email"),
]


def load_segments(db_path: Path = DB_PATH) -> pd.DataFrame:
    """One row per customer: treatment, visit and the binned segment columns (sql/03_segments.sql)."""
    query = (SQL_DIR / "03_segments.sql").read_text(encoding="utf-8")
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.sql(query).df()


def segment_sizes(seg: pd.DataFrame) -> pd.DataFrame:
    """Customers per segment and treatment, to verify the segments are uniformly distributed among treatments."""
    return pd.concat(
        {label: pd.crosstab(seg[dim], seg["treatment"]).reindex(order)
         for dim, (label, order) in DIMENSIONS.items()},
        names=["Dimension", "Segment"],
    )[["no_email", "womens_email", "mens_email"]]


# --- Lift per segment ---

def segment_lifts(seg: pd.DataFrame) -> pd.DataFrame:
    """Visit lift of each email vs no email within each segment: 17 segments x 2 emails = 34 rows."""
    rows = []
    for dim, (label, order) in DIMENSIONS.items():      # 1. each dimension (recency, history, ...)
        for segment in order:                           # 2. each segment within it ("1-3 months", ...)
            sub = seg[seg[dim] == segment]              #    keep only this segment's customers
            for email in EMAILS:                        # 3. each treatment except control
                result = proportion_test(
                    values(sub, "visit", email),        #    y_t: 0/1 visits of emailed customers in the segment
                    values(sub, "visit", "no_email"),   #    y_r: 0/1 visits of non-emailed customers in the segment
                )
                rows.append({"dimension": label, "segment": segment, "email": email,
                             **result})                 #    ** merges proportion_test's dict into this row
    return pd.DataFrame(rows)


def fmt_lift(lift: float, low: float, high: float) -> str:
    return f"{lift * 100:+.1f} pp ({low * 100:.1f} to {high * 100:.1f})"


def lift_table(seg_lifts: pd.DataFrame) -> pd.DataFrame:
    """Compact the segment lifts into a readable table."""
    seg_lifts = seg_lifts.assign(
        lift_text=[fmt_lift(r.abs_lift, r.abs_ci_low, r.abs_ci_high) for r in seg_lifts.itertuples()]
    )
    rows = [(label, s) for label, order in DIMENSIONS.values() for s in order]

    seg_table = (seg_lifts.pivot(index=["dimension", "segment"], columns="email", values="lift_text")
                 .reindex(rows)[EMAILS])
    baseline = seg_lifts.groupby(["dimension", "segment"])["reference_value"].first()
    seg_table.insert(0, "no_email_visit_rate", baseline.map("{:.1%}".format))
    seg_table.columns = ["No-email visit rate", "Men's email lift (95% CI)", "Women's email lift (95% CI)"]
    return seg_table


# --- Statistical significance ---

def two_groups(seg: pd.DataFrame, treated: str, reference: str) -> pd.DataFrame:
    """Add the treated dummy variable as 0/1 (reference/treatment)."""
    data = seg[seg["treatment"].isin([treated, reference])].copy()
    data["treated"] = np.where(data["treatment"] == reference, 0, 1)
    return data


def interaction_wald(fit, dim: str) -> tuple[float, int, float]:
    """Joint Wald test that every treated x segment term of one dimension is zero."""
    names = [n for n in fit.params.index if n.startswith(f"treated:C({dim})")]
    R = np.zeros((len(names), len(fit.params)))
    for i, name in enumerate(names):
        R[i, fit.params.index.get_loc(name)] = 1
    wald = fit.wald_test(R, use_f=False, scalar=True)
    return float(wald.statistic), len(names), float(wald.pvalue)


def head_to_head(seg: pd.DataFrame) -> pd.DataFrame:
    """Is the gap non-zero in this segment? Men's vs women's email within each segment, Holm-adjusted."""
    rows = []
    for dim, (label, order) in DIMENSIONS.items():
        for segment in order:
            sub = seg[seg[dim] == segment]
            result = proportion_test(values(sub, "visit", "mens_email"), values(sub, "visit", "womens_email"))
            rows.append({"dimension": label, "segment": segment, **result})
    head_to_head = pd.DataFrame(rows)
    head_to_head["p_holm"] = multipletests(head_to_head["p_value"], method="holm")[1]
    return head_to_head


def interaction_tests(seg: pd.DataFrame) -> pd.DataFrame:
    """Is the gap the same size in every segment of this feature? One test per comparison and dimension."""
    rows = []
    for treated, reference in COMPARISONS:
        data = two_groups(seg, treated, reference)
        for dim, (label, _) in DIMENSIONS.items():
            fit = smf.ols(f"visit ~ treated * C({dim})", data=data).fit(cov_type="HC2")
            chi2, k, p = interaction_wald(fit, dim)
            rows.append({"comparison": f"{treated} vs {reference}", "dimension": label,
                         "chi2": chi2, "df": k, "p_value": p})
    het = pd.DataFrame(rows)
    het["p_holm"] = multipletests(het["p_value"], method="holm")[1]
    return het
