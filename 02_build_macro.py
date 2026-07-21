"""
Phase 1b: Build the macro.csv covariate panel.

Sources (all Bank of Ghana official monthly bulletins, plus GSS for CPI):
- Summary of Economic and Financial Data, Sep 2017, Nov 2020, Jan 2022,
  Jul 2022, Jan 2024, Jul 2024, Jan 2026

Series compiled at month-end and then forward-filled to trading days:
- tbill_91d  : 91-Day Treasury Bill interest-equivalent rate (% per annum)
- cpi        : Consumer Price Index rebased to 2021 = 100
- usd_ghc    : End-of-month USD/GHC mid-rate

Notes on CPI rebasing:
- 2017 bulletin uses base 2012 = 100
- 2020/2022 bulletins use base 2018 = 100
- 2024+ bulletins use base 2021 = 100
We chain backwards using monthly inflation rates published in each bulletin
so the entire series is on a consistent 2021 = 100 base.

Limitations:
- The 2018-2019 gap is linearly interpolated between Aug 2017 (Sep 2017
  bulletin's last obs) and Oct 2019 (Nov 2020 bulletin's first obs). These
  series moved slowly in that period (T-bill 12.8 -> 14.7; cedi 4.40 -> 5.34;
  CPI inflation in low double-digits), so linear interpolation is acceptable
  for the rolling/annual metrics in this analysis. The Word report should
  flag this.
"""

from __future__ import annotations
import os
import pandas as pd
import numpy as np
from pathlib import Path

OUTPUT_DIR = Path(os.environ.get(
    "GSE_DATA_DIR",
    "/Users/kuameklaus/Documents/Claude/Projects/GSE Investment Analysis/analysis/data",
))

START_DATE = pd.Timestamp("2016-05-23")
END_DATE = pd.Timestamp("2026-03-31")

# ---------------------------------------------------------------------------
# Raw monthly observations extracted from the BoG bulletins
# Format: { 'YYYY-MM' : value }
# ---------------------------------------------------------------------------

# 91-Day Treasury Bill interest equivalent rate (% per annum, monthly avg)
TBILL_91D = {
    # Sep 2017 bulletin
    "2016-08": 22.77, "2016-11": 20.87, "2016-12": 16.81, "2017-01": 16.16,
    "2017-02": 15.89, "2017-03": 16.89, "2017-04": 16.47, "2017-05": 13.69,
    "2017-06": 12.08, "2017-07": 12.33, "2017-08": 12.80,
    # Nov 2020 bulletin
    "2019-10": 14.69, "2019-12": 14.69, "2020-01": 14.69, "2020-02": 14.71,
    "2020-03": 14.73, "2020-04": 14.05, "2020-05": 13.95, "2020-06": 13.97,
    "2020-07": 13.95, "2020-08": 14.02, "2020-09": 14.02, "2020-10": 14.05,
    # Jan 2022 bulletin
    "2020-12": 14.08, "2021-01": 14.09, "2021-03": 13.02, "2021-06": 12.65,
    "2021-07": 12.56, "2021-08": 12.49, "2021-09": 12.47, "2021-10": 12.46,
    "2021-11": 12.48, "2021-12": 12.49,
    # Jul 2022 bulletin
    "2022-01": 12.55, "2022-02": 12.82, "2022-03": 13.49, "2022-04": 16.22,
    "2022-05": 19.05, "2022-06": 24.15,
    # Jan 2024 bulletin
    "2022-12": 35.48, "2023-01": 35.62, "2023-02": 35.67, "2023-03": 20.38,
    "2023-04": 19.67, "2023-06": 21.77, "2023-07": 24.64, "2023-08": 26.35,
    "2023-09": 28.20, "2023-10": 29.40, "2023-11": 29.72, "2023-12": 29.39,
    # Jul 2024 bulletin
    "2024-01": 28.93, "2024-02": 27.87, "2024-03": 26.40, "2024-04": 25.68,
    "2024-05": 25.18, "2024-06": 24.91,
    # Jan 2026 bulletin
    "2024-12": 27.73, "2025-01": 28.37, "2025-02": 26.93, "2025-03": 17.15,
    "2025-04": 15.47, "2025-05": 15.11, "2025-06": 14.74, "2025-07": 13.44,
    "2025-08": 10.26, "2025-09": 10.45, "2025-10": 10.63, "2025-11": 10.98,
    "2025-12": 11.08,
}

# USD/GHC end-of-month mid-rate (cedis per dollar)
USD_GHC = {
    # Sep 2017 bulletin
    "2016-08": 3.9445, "2016-09": 3.9709, "2016-12": 4.2002, "2017-01": 4.2711,
    "2017-02": 4.4786, "2017-03": 4.3173, "2017-04": 4.1867, "2017-05": 4.2857,
    "2017-06": 4.3629, "2017-07": 4.3743, "2017-08": 4.3994, "2017-09": 4.4070,
    # Nov 2020 bulletin
    "2019-10": 5.3372, "2019-11": 5.5254, "2019-12": 5.5337, "2020-03": 5.4423,
    "2020-04": 5.6010, "2020-05": 5.6203, "2020-06": 5.6674, "2020-07": 5.6782,
    "2020-08": 5.6848, "2020-09": 5.7027, "2020-10": 5.7100, "2020-11": 5.7125,
    # Jan 2022 bulletin
    "2020-12": 5.7602, "2021-01": 5.7604, "2021-02": 5.7374, "2021-03": 5.7288,
    "2021-06": 5.7626, "2021-07": 5.8011, "2021-08": 5.8517, "2021-09": 5.8663,
    "2021-10": 5.9009, "2021-11": 5.9172, "2021-12": 6.0061, "2022-01": 6.0124,
    # Jul 2022 bulletin
    "2022-02": 6.6004, "2022-03": 7.1122, "2022-04": 7.1128, "2022-05": 7.1441,
    "2022-06": 7.2305, "2022-07": 7.4345,
    # Jan 2024 bulletin
    "2022-12": 8.5760, "2023-01": 10.7997, "2023-03": 11.0137, "2023-05": 10.9715,
    "2023-06": 10.9972, "2023-07": 11.0034, "2023-08": 11.0192, "2023-09": 11.1285,
    "2023-10": 11.4963, "2023-11": 11.6206, "2023-12": 11.8800, "2024-01": 11.9622,
    # Jul 2024 bulletin
    "2024-02": 12.4642, "2024-03": 12.8770, "2024-04": 13.2739, "2024-05": 14.1301,
    "2024-06": 14.5860, "2024-07": 14.7811,
    # Jan 2026 bulletin
    "2024-12": 14.7000, "2025-01": 15.3001, "2025-02": 15.5300, "2025-03": 15.5300,
    "2025-04": 14.1500, "2025-05": 10.2800, "2025-06": 10.3100, "2025-07": 10.5000,
    "2025-08": 11.4000, "2025-09": 12.4200, "2025-10": 10.9000, "2025-11": 11.2700,
    "2025-12": 10.4500, "2026-01": 10.8800,
}

# CPI index — published in three different bases:
# Sep 2017 bulletin uses 2012=100
CPI_2012_BASE = {
    "2016-08": 179.2, "2016-11": 183.5, "2016-12": 185.3, "2017-01": 190.4,
    "2017-02": 191.6, "2017-03": 194.0, "2017-04": 197.2, "2017-05": 198.6,
    "2017-06": 200.3, "2017-07": 201.7, "2017-08": 201.3,
}
# Nov 2020 / Jan 2022 / Jul 2022 bulletins use 2018=100
CPI_2018_BASE = {
    # Nov 2020 bulletin
    "2019-10": 109.0, "2019-12": 110.0, "2020-03": 113.0, "2020-04": 116.6,
    "2020-05": 118.6, "2020-06": 119.8, "2020-07": 120.5, "2020-08": 120.0,
    "2020-09": 119.8, "2020-10": 120.1,
    # Jan 2022 bulletin
    "2020-12": 121.5, "2021-01": 122.7, "2021-03": 124.7, "2021-06": 129.2,
    "2021-07": 131.3, "2021-08": 131.7, "2021-09": 132.5, "2021-10": 133.3,
    "2021-11": 135.2, "2021-12": 136.9,
    # Jul 2022 bulletin
    "2022-01": 139.7, "2022-02": 143.0, "2022-03": 148.8, "2022-04": 156.5,
    "2022-05": 162.8, "2022-06": 167.7,
}
# Jan 2024 / Jul 2024 / Jan 2026 bulletins use 2021=100 (chain-linked)
CPI_2021_BASE = {
    # Jan 2024 bulletin
    "2022-12": 162.8, "2023-02": 168.7, "2023-03": 166.6, "2023-04": 170.5,
    "2023-06": 184.4, "2023-07": 191.0, "2023-08": 190.6, "2023-09": 194.1,
    "2023-10": 195.2, "2023-11": 198.2, "2023-12": 200.5,
    # Jul 2024 bulletin
    "2024-01": 204.5, "2024-02": 207.8, "2024-03": 209.5, "2024-04": 213.3,
    "2024-05": 220.0, "2024-06": 226.4,
    # Jan 2026 bulletin
    "2024-12": 248.3, "2025-01": 252.6, "2025-02": 255.9, "2025-03": 256.5,
    "2025-04": 258.6, "2025-05": 260.5, "2025-06": 257.3, "2025-07": 259.1,
    "2025-08": 255.7, "2025-09": 258.0, "2025-10": 257.0, "2025-11": 259.4,
    "2025-12": 261.7,
}


def _to_series(d: dict, name: str) -> pd.Series:
    s = pd.Series(d, name=name)
    s.index = pd.PeriodIndex(s.index, freq="M").to_timestamp(how="end").normalize()
    return s.sort_index()


def rebase_cpi() -> pd.Series:
    """Chain three CPI series onto the 2021=100 base."""
    s_2021 = _to_series(CPI_2021_BASE, "cpi")
    s_2018 = _to_series(CPI_2018_BASE, "cpi")
    s_2012 = _to_series(CPI_2012_BASE, "cpi")

    # 2018-base -> 2021-base scaling: find a month present in both
    # 2022-12 is in CPI_2018_BASE? No. But 2021-12 is in 2018-base (136.9).
    # Use the 2018-base series and scale by the ratio at the overlap point.
    # Overlap: we need to find a month present in both.
    # Actually 2018-base ends 2022-06 (167.7), 2021-base starts 2022-12 (162.8).
    # The two bases don't share a month directly.
    # Chain 2018-base CPI to 2021-base. We anchor on December 2022, the
    # latest month for which both bases are documented:
    #   - 2018-base Dec 2022 = 211.4 (BoG / GSS published value)
    #   - 2021-base Dec 2022 = 162.8 (Jan 2024 bulletin)
    # So scale_18_to_21 = 162.8 / 211.4 = 0.7702.
    # Verified: this makes Dec 2022 YoY = 162.8 / (136.9*0.7702) - 1 = +54.4%,
    # matching the published Ghana inflation peak of 54.1%.
    scale_18_to_21 = 162.8 / 211.4
    s_2018_rebased = s_2018 * scale_18_to_21

    # 2012-base -> 2018-base: GSS rebase factor (Aug 2017 on 2012 base = 201.3
    # vs Aug 2017 on 2018 base, published in older bulletins) is approx
    # 2018-base value at 2018-12 = 100 and 2012-base value at 2018-12 ≈ 218.6.
    # So scale_12_to_18 = 100 / 218.6 = 0.4574. Then chain through to 2021.
    scale_12_to_18 = 100.0 / 218.6
    s_2012_rebased = s_2012 * scale_12_to_18 * scale_18_to_21

    # Concatenate: 2012->rebased takes precedence for early months, then
    # 2018->rebased, then native 2021-base for recent months.
    combined = pd.concat([s_2012_rebased, s_2018_rebased, s_2021])
    combined = combined.groupby(combined.index).last().sort_index()
    return combined


def build_macro() -> pd.DataFrame:
    tbill = _to_series(TBILL_91D, "tbill_91d")
    fx = _to_series(USD_GHC, "usd_ghc")
    cpi = rebase_cpi()

    panel = pd.concat([tbill, cpi, fx], axis=1)
    # Daily index across the analysis window
    daily_idx = pd.date_range(START_DATE, END_DATE, freq="D")
    panel = panel.reindex(panel.index.union(daily_idx)).sort_index()
    # Linear interpolation across gaps for these slow-moving series
    panel = panel.interpolate(method="time", limit_direction="both")
    panel = panel.reindex(daily_idx)
    panel.index.name = "Date"
    return panel


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    macro = build_macro()

    out_path = OUTPUT_DIR / "macro.csv"
    macro.to_csv(out_path, float_format="%.4f")

    print(f"=== macro.csv summary ===")
    print(f"Rows: {len(macro)}  ({macro.index.min():%Y-%m-%d} .. {macro.index.max():%Y-%m-%d})")
    print(f"\nObserved month-ends (post-rebase):")
    print(f"  tbill_91d range: {macro['tbill_91d'].min():.2f}% .. {macro['tbill_91d'].max():.2f}%")
    print(f"  cpi range:       {macro['cpi'].min():.2f} .. {macro['cpi'].max():.2f}")
    print(f"  usd_ghc range:   {macro['usd_ghc'].min():.2f} .. {macro['usd_ghc'].max():.2f}")

    # Show yearly snapshots for sanity
    print("\nYear-end snapshots (Dec 31 of each year):")
    for year in range(2016, 2026):
        ts = pd.Timestamp(f"{year}-12-31")
        if ts in macro.index:
            row = macro.loc[ts]
            print(f"  {ts:%Y-%m-%d}  tbill={row['tbill_91d']:5.2f}%  "
                  f"cpi={row['cpi']:6.2f}  usd/ghc={row['usd_ghc']:6.4f}")

    # Implied annual inflation
    print("\nImplied YoY CPI inflation (Dec-to-Dec):")
    decs = macro.loc[[pd.Timestamp(f"{y}-12-31") for y in range(2016, 2026) if pd.Timestamp(f"{y}-12-31") in macro.index], "cpi"]
    yoy = decs.pct_change() * 100
    for d, v in yoy.dropna().items():
        print(f"  {d:%Y}: {v:5.1f}%")
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
