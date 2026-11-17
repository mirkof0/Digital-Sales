"""A/B readout: validity checks (SRM, covariate balance) and the lift of each email."""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from digital_sales.paths import DB_PATH

FEATURES = ["recency", "history", "mens", "womens", "newbie", "zip_code", "channel"]

PAIRS = [
    ("mens_email", "no_email"),
    ("womens_email", "no_email"),
    ("mens_email", "womens_email"),
]


def load_analysis_base(db_path: Path = DB_PATH) -> pd.DataFrame:
    """One row per customer: features, treatment and outcomes."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.table("analysis_base").df()


# --- Validity checks ---

def srm_test(df: pd.DataFrame) -> tuple[float, float]:
    """SRM: are the group sizes consistent with the planned 1/3 each?"""
    counts = df["treatment"].value_counts()
    chi2, p_srm = stats.chisquare(counts)  # expected: equal thirds
    return chi2, p_srm


def covariate_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Standardised mean difference of each pre-campaign feature vs no email."""
    features = pd.get_dummies(df[FEATURES], dtype=float)
    means = features.groupby(df["treatment"]).mean()
    variances = features.groupby(df["treatment"]).var()

    return pd.DataFrame({
        group: (means.loc[group] - means.loc["no_email"])
               / np.sqrt((variances.loc[group] + variances.loc["no_email"]) / 2)
        for group in ["mens_email", "womens_email"]
    })


# --- Lift analysis ---

def values(df: pd.DataFrame, outcome: str, group: str) -> np.ndarray:
    """One outcome for one treatment group, as a numpy array."""
    return df.loc[df["treatment"] == group, outcome].to_numpy(dtype=float)


def proportion_test(y_t: np.ndarray, y_r: np.ndarray, alpha: float = 0.05) -> dict:
    """Two-proportion z-test for 0/1 outcomes: treated group t vs reference group r."""
    x_t, n_t = y_t.sum(), y_t.size          # successes, customers
    x_r, n_r = y_r.sum(), y_r.size
    p_t, p_r = x_t / n_t, x_r / n_r
    diff = p_t - p_r
    z_crit = stats.norm.ppf(1 - alpha / 2)  # 1.96

    # Test: SE under H0, where both groups share one pooled rate
    p_pool = (x_t + x_r) / (n_t + n_r)
    se_h0 = np.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_r))
    p_value = 2 * stats.norm.sf(abs(diff / se_h0))

    # CI for the difference: each group keeps its own rate
    se = np.sqrt(p_t * (1 - p_t) / n_t + p_r * (1 - p_r) / n_r)

    # CI for the relative lift: on the log of the rate ratio, then back-transformed
    log_rr = np.log(p_t / p_r)
    se_log = np.sqrt((1 - p_t) / x_t + (1 - p_r) / x_r)

    return {
        "treated_value": p_t,
        "reference_value": p_r,
        "abs_lift": diff,
        "abs_ci_low": diff - z_crit * se,
        "abs_ci_high": diff + z_crit * se,
        "rel_lift": p_t / p_r - 1,
        "rel_ci_low": np.exp(log_rr - z_crit * se_log) - 1,
        "rel_ci_high": np.exp(log_rr + z_crit * se_log) - 1,
        "p_value": p_value,
    }


def mean_test(y_t: np.ndarray, y_r: np.ndarray, alpha: float = 0.05) -> dict:
    """Welch's t-test for a continuous outcome: treated group t vs reference group r."""
    m_t, m_r = y_t.mean(), y_r.mean()
    welch = stats.ttest_ind(y_t, y_r, equal_var=False)
    ci = welch.confidence_interval(confidence_level=1 - alpha)
    z_crit = stats.norm.ppf(1 - alpha / 2)

    # Relative lift: same log-ratio idea as for rates, with the spend variances
    log_ratio = np.log(m_t / m_r)
    se_log = np.sqrt(y_t.var(ddof=1) / (y_t.size * m_t**2)
                     + y_r.var(ddof=1) / (y_r.size * m_r**2))

    return {
        "treated_value": m_t,
        "reference_value": m_r,
        "abs_lift": m_t - m_r,
        "abs_ci_low": ci.low,
        "abs_ci_high": ci.high,
        "rel_lift": m_t / m_r - 1,
        "rel_ci_low": np.exp(log_ratio - z_crit * se_log) - 1,
        "rel_ci_high": np.exp(log_ratio + z_crit * se_log) - 1,
        "p_value": welch.pvalue,
    }


TESTS = {"visit": proportion_test, "conversion": proportion_test, "spend": mean_test}


def lift_tests(df: pd.DataFrame) -> pd.DataFrame:
    """One row per outcome and pair of groups, with Holm-adjusted p-values."""
    rows = []
    for outcome, test in TESTS.items():
        for treated, reference in PAIRS:
            result = test(values(df, outcome, treated), values(df, outcome, reference))
            rows.append({"outcome": outcome, "treated": treated, "reference": reference,
                         "test": test.__name__, **result})
    results = pd.DataFrame(rows)

    # Holm correction across the three comparisons, separately for each outcome
    results["p_holm"] = results.groupby("outcome")["p_value"].transform(
        lambda p: multipletests(p, method="holm")[1]
    )
    return results


def spend_per_buyer(df: pd.DataFrame) -> pd.DataFrame:
    """Check if there is a difference in spending between buyers among different treatments."""
    tdf = df.groupby("treatment").agg(conversion=("conversion", "mean"),
                                      revenue_per_customer=("spend", "mean"))
    tdf["spend_per_buyer"] = tdf["revenue_per_customer"] / tdf["conversion"]
    return tdf.reindex(["no_email", "womens_email", "mens_email"])
