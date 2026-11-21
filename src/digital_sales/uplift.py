"""Uplift model: a T-learner of two logistic regressions, its Qini evaluation and the targeting economics."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from scipy.ndimage import gaussian_filter1d
from sklearn.model_selection import StratifiedKFold

from digital_sales.experiment import load_analysis_base, proportion_test, values
from digital_sales.paths import DB_PATH
from digital_sales.segments import load_segments

SEED = 2008

# Logistic regression fitted to each treatment group (statsmodels formula syntax, outcome ~ features)
FORMULA = "visit ~ recency + np.log(history) + both"

# The three rankings compared (display name -> column used to sort customers)
SCORES = {"T-learner uplift": "uplift_rank", "Response model": "response_rank",
          "Buyer-type rule": "rule_score"}

# Paired Qini differences tested (first minus second)
PAIRS = [("T-learner uplift", "Response model"), ("T-learner uplift", "Buyer-type rule"),
         ("Response model", "Buyer-type rule")]

MARGIN = 0.50                       # assumed share of revenue that is profit
COSTS = [0.15, 0.30, 0.50]          # assumed cost per email ($): low / mid / high
SIGMA = 0.05                        # smoothing width of the profit curves: sd of the Gaussian kernel, as a share of customers


def load_uplift_base(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Men's email vs no email, one row per customer, with the treatment dummy t and the "Both" flag."""
    df = load_analysis_base(db_path)
    df = df[df["treatment"].isin(["mens_email", "no_email"])].reset_index(drop=True)
    df = df.merge(load_segments(db_path)[["customer_id", "buyer_type"]], on="customer_id", how="left")
    df["t"] = (df["treatment"] == "mens_email").astype(int)        # 1 = got the men's email
    df["both"] = (df["buyer_type"] == "Both").astype(int)          # 1 = bought men's AND women's merchandise last year
    return df.astype({"history": float, "spend": float})


# --- T-learner ---

def cross_fit_t_learner(df: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Out-of-fold scores of the three rankings: each customer is scored by models trained on the other 4 folds."""
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    strata = df["t"].astype(str) + "_" + df["visit"].astype(str)   # same emailed/visited mix in every fold
    is_treated = df["t"].to_numpy() == 1

    mu1, mu0, fold = np.zeros(len(df)), np.zeros(len(df)), np.zeros(len(df), dtype=int)
    for k, (train, test) in enumerate(folds.split(df, strata)):
        treated, control = train[is_treated[train]], train[~is_treated[train]]
        m1 = smf.logit(FORMULA, data=df.iloc[treated]).fit(disp=0)  # emailed customers     -> mu_1(x)
        m0 = smf.logit(FORMULA, data=df.iloc[control]).fit(disp=0)  # non-emailed customers -> mu_0(x)
        mu1[test] = m1.predict(df.iloc[test])
        mu0[test] = m0.predict(df.iloc[test])
        fold[test] = k

    df = df.assign(fold=fold,
                   uplift_score=mu1 - mu0,                      # T-learner: predicted extra visit probability
                   response_score=mu1,                          # response model: P(visit) if emailed
                   rule_score=df["both"].astype(float))         # phase 3 rule: "Both" buyers first
    # Percentile within each fold: scores from different folds sit on slightly different scales
    df["uplift_rank"] = df.groupby("fold")["uplift_score"].rank(pct=True)
    df["response_rank"] = df.groupby("fold")["response_score"].rank(pct=True)
    return df


def coefficient_table(df: pd.DataFrame) -> pd.DataFrame:
    """Coefficients of the two logistic regressions fitted on all customers, with a z-test of their difference."""
    is_treated = df["t"] == 1
    fit1 = smf.logit(FORMULA, data=df[is_treated]).fit(disp=0)     # emailed customers
    fit0 = smf.logit(FORMULA, data=df[~is_treated]).fit(disp=0)    # non-emailed customers

    coefs = pd.DataFrame({"emailed (m1)": fit1.params, "not emailed (m0)": fit0.params})
    coefs["difference"] = coefs["emailed (m1)"] - coefs["not emailed (m0)"]
    z = coefs["difference"] / np.sqrt(fit1.bse ** 2 + fit0.bse ** 2)    # bse: standard errors of the coefficients
    coefs["p (difference)"] = 2 * stats.norm.sf(z.abs())                # two-sided p-value
    return coefs


# --- Qini evaluation ---

def uplift_curve(y, t, score, seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
    """Extra outcomes per 1,000 customers when only the top fraction (by score) is emailed."""
    rng = np.random.default_rng(seed)
    order = np.lexsort((rng.random(len(score)), -np.asarray(score)))   # best first, ties in random order
    y, t = np.asarray(y, dtype=float)[order], np.asarray(t)[order]
    n_t, n_c = np.cumsum(t), np.cumsum(1 - t)                           # N_T, N_C in the top fraction
    y_t, y_c = np.cumsum(y * t), np.cumsum(y * (1 - t))                 # Y_T, Y_C in the top fraction
    q = y_t - np.divide(y_c * n_t, n_c, out=np.zeros(len(y)), where=n_c > 0)   # Qini: Y_T - Y_C * N_T / N_C
    n = np.arange(1, len(y) + 1)
    per_1000 = np.divide(q * n, n_t, out=np.zeros(len(y)), where=n_t > 0) * 1000 / len(y)
    return np.r_[0, n / len(y)], np.r_[0, per_1000]


def qini_coefficient(y, t, score) -> float:
    """Average gain over random targeting across all shares emailed, in extra outcomes per 1,000 customers."""
    frac, curve = uplift_curve(y, t, score)
    return np.trapezoid(curve - frac * curve[-1], frac)


def bootstrap_qini(df: pd.DataFrame, n_boot: int = 200, seed: int = SEED) -> pd.DataFrame:
    """Qini coefficient of each ranking on resampled customers (the scores stay fixed)."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_boot):
        d = df.iloc[rng.integers(0, len(df), len(df))]
        rows.append({name: qini_coefficient(d["visit"], d["t"], d[col]) for name, col in SCORES.items()})
    return pd.DataFrame(rows)


def qini_table(df: pd.DataFrame, n_boot: int = 200, seed: int = SEED) -> pd.DataFrame:
    """Qini coefficient of each ranking and of the paired differences, with percentile bootstrap 95% CIs."""
    qini = {name: qini_coefficient(df["visit"], df["t"], df[col]) for name, col in SCORES.items()}
    boot = bootstrap_qini(df, n_boot, seed)
    for a, b in PAIRS:
        label = f"{a} minus {b.lower()}"
        qini[label] = qini[a] - qini[b]
        boot[label] = boot[a] - boot[b]

    return pd.DataFrame({"Qini coefficient": pd.Series(qini),
                         "95% CI low": boot.quantile(0.025),
                         "95% CI high": boot.quantile(0.975)})


# --- Deciles of the T-learner ranking ---

def uplift_deciles(df: pd.DataFrame) -> pd.Series:
    """Decile of the T-learner ranking: 1 = top 10%, 10 = bottom 10%."""
    return pd.qcut(df["uplift_rank"].rank(method="first", ascending=False), 10, labels=range(1, 11))


def decile_lifts(df: pd.DataFrame) -> pd.DataFrame:
    """Observed visit lift (men's email vs no email) and mean predicted uplift in each decile."""
    rows = []
    for decile, sub in df.groupby(uplift_deciles(df), observed=True):
        r = proportion_test(values(sub, "visit", "mens_email"), values(sub, "visit", "no_email"))
        rows.append({"decile": int(decile), "predicted_uplift": sub["uplift_score"].mean(), **r})
    return pd.DataFrame(rows)


def decile_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Mean features of the top 10%, middle 80% and bottom 10% of the T-learner ranking."""
    decile = uplift_deciles(df)
    group = np.select([decile == 1, decile == 10], ["Top 10%", "Bottom 10%"], "Middle 80%")
    return (pd.get_dummies(df[["recency", "history", "newbie", "buyer_type", "channel"]], dtype=float)
            .groupby(group).mean()
            .reindex(["Top 10%", "Middle 80%", "Bottom 10%"]).T)


# --- Targeting economics ---

def smooth(curve: np.ndarray, sigma: int) -> np.ndarray:
    """Gaussian smoothing; odd reflection at the edges keeps both end points unchanged."""
    pad = 4 * sigma                                           # the kernel reaches 4 sd on each side
    padded = np.pad(curve, pad, mode="reflect", reflect_type="odd")
    return gaussian_filter1d(padded, sigma)[pad:-pad]


def profit_curves(df: pd.DataFrame, ranking: str = "uplift_rank") -> tuple[np.ndarray, dict[float, np.ndarray]]:
    """Smoothed profit per 1,000 customers by share emailed, for free emails ($0) and each cost in COSTS."""
    frac, revenue = uplift_curve(df["spend"], df["t"], df[ranking])   # extra revenue per 1,000 customers
    sigma = int(SIGMA * len(frac))
    return frac, {cost: smooth(MARGIN * revenue - cost * 1000 * frac, sigma) for cost in [0.0] + COSTS}


def best_share(df: pd.DataFrame, ranking: str = "uplift_rank") -> pd.DataFrame:
    """Most profitable share to email at each cost, against emailing everyone (profit per 1,000 customers)."""
    frac, curves = profit_curves(df, ranking)
    rows = []
    for cost, profit in curves.items():
        best = np.argmax(profit)
        rows.append({"cost per email ($)": cost, "best share emailed": frac[best],
                     "profit at best share ($)": profit[best], "profit emailing everyone ($)": profit[-1]})
    return pd.DataFrame(rows)


def block_line(frac: np.ndarray, curve: np.ndarray, score: pd.Series) -> np.ndarray:
    """Expected curve of a ranking with tied scores: a straight line within each block of equal scores.

    Customers with the same score are emailed in random order, so in expectation each extra email in a block
    adds that block's average. Only the block ends carry information; anything in between is noise.
    """
    shares = (score.value_counts().sort_index(ascending=False).cumsum() / len(score)).to_numpy()
    knots = np.r_[0.0, shares]                                       # 0, end of block 1, ..., 1
    return np.interp(frac, knots, np.interp(knots, frac, curve))


def targeting_curves(df: pd.DataFrame, step: int = 100) -> pd.DataFrame:
    """Extra visits and extra revenue per 1,000 customers by share emailed, for each ranking.

    Kept every `step`-th customer. The column extra_revenue_per_1000_smoothed is the Gaussian-smoothed curve for
    the two models, and the expected straight-line curve (block_line) for the buyer-type rule, whose order after
    the "Both" buyers is random. Profit at any margin m and cost c is then
    m * extra_revenue_per_1000_smoothed - c * 1000 * share_emailed (smoothing a straight line changes nothing).

    SIGMA = 5% was checked on the buyer-type rule, whose true curve is known: over 30 random orders it lost the
    least profit when its peak was used to choose how many customers to email (widths from 1% to 20% tried).
    """
    tables = []
    for name, col in SCORES.items():
        frac, visits = uplift_curve(df["visit"], df["t"], df[col])
        _, revenue = uplift_curve(df["spend"], df["t"], df[col])
        if name == "Buyer-type rule":
            smoothed = block_line(frac, revenue, df[col])
        else:
            smoothed = smooth(revenue, int(SIGMA * len(frac)))      # smooth first, then thin out
        idx = np.r_[0:len(frac):step, len(frac) - 1]
        tables.append(pd.DataFrame({
            "ranking": name,
            "share_emailed": frac[idx],
            "extra_visits_per_1000": visits[idx],
            "extra_revenue_per_1000": revenue[idx],
            "extra_revenue_per_1000_smoothed": smoothed[idx],
        }))
    return pd.concat(tables, ignore_index=True)
