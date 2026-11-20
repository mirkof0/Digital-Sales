from digital_sales.experiment import (
    covariate_balance,
    lift_tests,
    load_analysis_base,
    spend_per_buyer,
    srm_test,
)
from digital_sales.get_data import build_database, download_raw
from digital_sales.quality import assert_no_errors, run_quality_checks
from digital_sales.segments import (
    head_to_head,
    interaction_tests,
    lift_table,
    load_segments,
    segment_lifts,
    segment_sizes,
)
from digital_sales.uplift import (
    best_share,
    coefficient_table,
    cross_fit_t_learner,
    decile_lifts,
    decile_profile,
    load_uplift_base,
    qini_table,
)


def main() -> None:
    csv_path = download_raw()
    build_database(csv_path)
    checks = run_quality_checks()
    print(checks.to_string(index=False))
    assert_no_errors(checks)
    run_ab_readout()
    run_segment_effects()
    run_uplift_model()


def run_ab_readout() -> None:
    """Phase 2: validity checks first, then the lift of each email."""
    df = load_analysis_base()

    print("\nValidity checks")
    chi2, p_srm = srm_test(df)
    print(f"SRM test: chi2 = {chi2:.2f}, p = {p_srm:.2f}")
    smd = covariate_balance(df)
    print(f"Largest |SMD|: {smd.abs().max().max():.3f}  (balanced if < 0.1)")

    print("\nLift analysis")
    print(lift_tests(df).round(3).to_string(index=False))

    print("\nSpend per buyer")
    print(spend_per_buyer(df).round(3).to_string())


def run_segment_effects() -> None:
    """Phase 3: visit lift of each email by segment, then whether it differs between segments."""
    seg = load_segments()

    print("\nSegment sizes per treatment")
    print(segment_sizes(seg).to_string())

    print("\nVisit lift by segment")
    print(lift_table(segment_lifts(seg)).to_string())

    print("\nMen's vs women's email within each segment")
    print(head_to_head(seg).round(4).to_string(index=False))

    print("\nInteraction tests: significant differences between segments (Holm p < 0.05)")
    het = interaction_tests(seg)
    print(het[het["p_holm"] < 0.05].round(4).to_string(index=False))


def run_uplift_model() -> None:
    """Phase 4: T-learner uplift model, its ranking quality against two baselines, and the targeting economics."""
    df = cross_fit_t_learner(load_uplift_base())
    print(f"\nUplift model: {len(df):,} customers, {df['t'].mean():.0%} emailed, "
          f"{df['both'].mean():.0%} 'Both' buyers")
    print(f"Predicted uplift: mean {df['uplift_score'].mean():.1%}, "
          f"from {df['uplift_score'].min():.1%} to {df['uplift_score'].max():.1%}")

    print("\nT-learner coefficients: emailed vs not emailed")
    print(coefficient_table(df).round(3).to_string())

    print("\nQini coefficients: extra visits per 1,000 customers over random targeting (bootstrap 95% CI)")
    print(qini_table(df).round(2).to_string())

    print("\nVisit lift by decile of predicted uplift (1 = highest)")
    deciles = decile_lifts(df)[["decile", "predicted_uplift", "abs_lift", "abs_ci_low", "abs_ci_high"]]
    print(deciles.round(3).to_string(index=False))

    print("\nWho gets targeted: mean features of the top, middle and bottom of the ranking")
    print(decile_profile(df).round(2).to_string())

    print("\nMost profitable share to email, per 1,000 customers (T-learner ranking, smoothed)")
    print(best_share(df).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
