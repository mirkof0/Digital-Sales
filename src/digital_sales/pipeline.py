from digital_sales.experiment import (
    covariate_balance,
    lift_tests,
    load_analysis_base,
    spend_per_buyer,
    srm_test,
)
from digital_sales.get_data import build_database, download_raw
from digital_sales.quality import assert_no_errors, run_quality_checks


def main() -> None:
    csv_path = download_raw()
    build_database(csv_path)
    checks = run_quality_checks()
    print(checks.to_string(index=False))
    assert_no_errors(checks)
    run_ab_readout()


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


if __name__ == "__main__":
    main()
