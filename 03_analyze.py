"""
Phase 2: End-to-end GSE investment analysis.

Reads:
  data/prices.csv, data/macro.csv, data/volumes.csv

Writes:
  outputs/figures/*.png           — all charts
  outputs/statistics.xlsx         — multi-sheet workbook of every table

Sections:
  1. Configuration
  2. Load & prepare
  3. Exploratory: correlations, pair plot, liquidity
  4. Baseline equal-weight portfolio (BOPP, GGBL, TOTAL, GOIL, GCB)
  5. Risk metrics: per-stock + portfolio vs GSE-CI
  6. Beta / alpha / Treynor / Information Ratio
  7. Rolling 1-year metrics + drawdowns
  8. Mean-variance optimisation: min-var, max-Sharpe, risk-parity, frontier
  9. Rebalancing: buy-and-hold vs monthly vs quarterly (zero TC)
 10. Ghana macro adjustments: real GHS + USD-translated views
 11. Robustness: bootstrap test for outperformance significance, VaR
 12. MTN scenario A — add as 6th stock from IPO
 13. MTN scenario B — replace worst-performer at Sep 2018
 14. Year-by-year attribution
"""

from __future__ import annotations
import os
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

# Quiet noisy warnings during optimisation
warnings.filterwarnings("ignore")

# Local import
import sys
sys.path.insert(0, str(Path(__file__).parent))
import lib

# ----------------------------------------------------------------------------
# 1. Configuration
# ----------------------------------------------------------------------------
ROOT = Path(os.environ.get(
    "GSE_ROOT",
    "/Users/kuameklaus/Documents/Claude/Projects/GSE Investment Analysis/analysis",
))
DATA = ROOT / "data"
FIG_DIR = ROOT / "outputs" / "figures"
REPORT_DIR = ROOT / "outputs" / "reports"
FIG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_TICKERS = ["BOPP", "GGBL", "TOTAL", "GOIL", "GCB"]
ALL_TICKERS = BASELINE_TICKERS + ["MTN"]
BENCHMARK = "GSE_CI"
INITIAL_INVESTMENT = 100_000.0
BASELINE_WEIGHTS = {t: 1.0 / len(BASELINE_TICKERS) for t in BASELINE_TICKERS}
MTN_IPO = pd.Timestamp("2018-09-05")

# Plot style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (12, 7)
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["font.family"] = "DejaVu Sans"
COLOR_PORTFOLIO = "#1f8a4c"
COLOR_BENCH = "#1f4ea8"
PALETTE = sns.color_palette("colorblind", n_colors=8)


def _save(fig, name: str):
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path.name}")


# ----------------------------------------------------------------------------
# 2. Load
# ----------------------------------------------------------------------------
print("Loading data...")
prices = pd.read_csv(DATA / "prices.csv", parse_dates=["Date"]).set_index("Date")
volumes = pd.read_csv(DATA / "volumes.csv", parse_dates=["Date"]).set_index("Date")
macro = pd.read_csv(DATA / "macro.csv", parse_dates=["Date"]).set_index("Date")
print(f"  prices: {prices.shape}  ({prices.index.min():%Y-%m-%d} .. {prices.index.max():%Y-%m-%d})")
print(f"  macro:  {macro.shape}")

returns = lib.daily_returns(prices)
bench_prices = prices[BENCHMARK]
bench_returns = returns[BENCHMARK]
daily_rfr = lib.daily_rfr(macro["tbill_91d"])
avg_rfr_annual_pct = float(macro["tbill_91d"].mean())
print(f"  avg risk-free rate (annual): {avg_rfr_annual_pct:.2f}%")

# ----------------------------------------------------------------------------
# 3. Exploratory: correlations, pair plot, liquidity
# ----------------------------------------------------------------------------
print("\n[3] Exploratory")
# Use only periods where all 6 + GSE_CI have data (post-MTN IPO subset is small,
# so do baseline-only correlations and a separate MTN-era version)
corr_all = prices[ALL_TICKERS + [BENCHMARK]].pct_change().corr()
corr_base = prices[BASELINE_TICKERS + [BENCHMARK]].pct_change().corr()

fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(corr_base, annot=True, fmt=".2f", cmap="coolwarm",
            vmin=-1, vmax=1, ax=ax, cbar_kws={"shrink": 0.8})
ax.set_title("Daily-return correlations: 5 baseline stocks + GSE-CI (2016–2026)")
_save(fig, "fig01_correlation_baseline")

fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(corr_all, annot=True, fmt=".2f", cmap="coolwarm",
            vmin=-1, vmax=1, ax=ax, cbar_kws={"shrink": 0.8})
ax.set_title("Daily-return correlations: 5 baseline + MTN + GSE-CI")
_save(fig, "fig02_correlation_with_mtn")

# Liquidity
liq = lib.liquidity_table(volumes, prices)
print("  Liquidity diagnostics:")
print(liq.round(2).to_string())

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
liq["pct_zero_trade"].sort_values().plot.barh(ax=axes[0], color=PALETTE[1])
axes[0].set_title("Share of zero-trade days per stock (lower = more liquid)")
axes[0].set_xlabel("%")
liq["avg_daily_volume"].sort_values().plot.barh(ax=axes[1], color=PALETTE[2])
axes[1].set_title("Avg daily volume on active days (log scale)")
axes[1].set_xscale("log")
axes[1].set_xlabel("shares")
fig.tight_layout()
_save(fig, "fig03_liquidity")

# Normalised price levels for the 5 baseline stocks + index
fig, ax = plt.subplots()
norm = prices[ALL_TICKERS + [BENCHMARK]].copy()
for c in norm.columns:
    s = norm[c].dropna()
    norm[c] = norm[c] / s.iloc[0]
for i, c in enumerate(norm.columns):
    ax.plot(norm.index, norm[c], label=c, color=PALETTE[i % len(PALETTE)],
            linewidth=1.8 if c == BENCHMARK else 1.1,
            linestyle="--" if c == BENCHMARK else "-")
ax.set_yscale("log")
ax.set_title("Normalised price levels (= 1.0 on first observation, log scale)")
ax.set_ylabel("multiple")
ax.legend(ncol=4, loc="upper left")
_save(fig, "fig04_normalised_prices_logscale")

# ----------------------------------------------------------------------------
# 4. Baseline equal-weight portfolio (buy-and-hold, no rebalancing)
# ----------------------------------------------------------------------------
print("\n[4] Baseline equal-weight portfolio (buy-and-hold)")
port_bh = lib.buy_and_hold_value(prices[BASELINE_TICKERS], BASELINE_WEIGHTS, INITIAL_INVESTMENT)
# Benchmark scaled to same initial $
bench_value = (bench_prices / bench_prices.iloc[0]) * INITIAL_INVESTMENT

fig, ax = plt.subplots()
ax.plot(port_bh.index, port_bh, label="Equal-weight 5-stock portfolio",
        color=COLOR_PORTFOLIO, linewidth=2.2)
ax.plot(bench_value.index, bench_value, label="GSE Composite Index",
        color=COLOR_BENCH, linewidth=2.2, linestyle="--")
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k"))
ax.set_title(f"Portfolio vs GSE-CI, GHS {INITIAL_INVESTMENT:,.0f} initial (2016–Q1 2026)")
ax.set_ylabel("Portfolio value (GHS)")
ax.legend()
_save(fig, "fig05_portfolio_vs_index")

# Per-stock cumulative wealth ($100k each)
fig, ax = plt.subplots()
for i, t in enumerate(ALL_TICKERS):
    s = prices[t].dropna()
    w = (s / s.iloc[0]) * INITIAL_INVESTMENT
    ax.plot(w.index, w, label=t, color=PALETTE[i % len(PALETTE)], linewidth=1.5)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k"))
ax.set_yscale("log")
ax.set_title("Single-stock cumulative wealth (GHS 100k each at start; log scale)")
ax.set_ylabel("Value (GHS)")
ax.legend(ncol=3)
_save(fig, "fig06_single_stock_wealth")

# ----------------------------------------------------------------------------
# 5. Risk metrics per stock + portfolio
# ----------------------------------------------------------------------------
print("\n[5] Risk metrics")
wealth_per_stock = {t: (prices[t].dropna() / prices[t].dropna().iloc[0]) * INITIAL_INVESTMENT
                    for t in ALL_TICKERS}
wealth_per_stock["Portfolio (EW)"] = port_bh
wealth_per_stock["GSE_CI"] = bench_value

metrics_df = lib.metrics_table(wealth_per_stock, daily_rfr)
print(metrics_df.round(4).to_string())

# ----------------------------------------------------------------------------
# 6. Benchmark-relative metrics
# ----------------------------------------------------------------------------
print("\n[6] Benchmark-relative metrics (vs GSE-CI)")
rel_dict = {t: wealth_per_stock[t] for t in ALL_TICKERS}
rel_dict["Portfolio (EW)"] = port_bh
rel_df = lib.benchmark_relative_table(rel_dict, bench_value, daily_rfr)
print(rel_df.round(4).to_string())

# ----------------------------------------------------------------------------
# 7. Rolling Sharpe / vol / drawdown
# ----------------------------------------------------------------------------
print("\n[7] Rolling metrics + drawdowns")
port_ret = port_bh.pct_change()
roll_sharpe_p = lib.rolling_sharpe(port_ret, daily_rfr)
roll_sharpe_b = lib.rolling_sharpe(bench_returns, daily_rfr)
roll_vol_p = lib.rolling_vol(port_ret)
roll_vol_b = lib.rolling_vol(bench_returns)

fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
axes[0].plot(roll_sharpe_p.index, roll_sharpe_p, label="Portfolio", color=COLOR_PORTFOLIO)
axes[0].plot(roll_sharpe_b.index, roll_sharpe_b, label="GSE-CI", color=COLOR_BENCH, linestyle="--")
axes[0].axhline(0, color="black", linewidth=0.5)
axes[0].set_title("Rolling 1-year Sharpe ratio (time-varying T-bill RFR)")
axes[0].legend()

axes[1].plot(roll_vol_p.index, roll_vol_p * 100, label="Portfolio", color=COLOR_PORTFOLIO)
axes[1].plot(roll_vol_b.index, roll_vol_b * 100, label="GSE-CI", color=COLOR_BENCH, linestyle="--")
axes[1].set_title("Rolling 1-year annualised volatility (%)")
axes[1].set_ylabel("%")
axes[1].legend()
_save(fig, "fig07_rolling_sharpe_vol")

# Drawdown
dd_p = lib.drawdown_series(port_bh)
dd_b = lib.drawdown_series(bench_value)
fig, ax = plt.subplots()
ax.fill_between(dd_p.index, dd_p * 100, 0, color=COLOR_PORTFOLIO, alpha=0.45, label="Portfolio")
ax.plot(dd_b.index, dd_b * 100, color=COLOR_BENCH, linestyle="--", label="GSE-CI")
ax.set_title("Drawdown from running peak (%)")
ax.set_ylabel("Drawdown (%)")
ax.legend()
_save(fig, "fig08_drawdown")

# ----------------------------------------------------------------------------
# 8. Mean-variance optimisation
# ----------------------------------------------------------------------------
print("\n[8] Portfolio optimisation (baseline 5 stocks, fully invested, no shorts)")
opt = lib.optimise_portfolios(returns[BASELINE_TICKERS], daily_rfr)
print("  min-var weights:")
print(opt["min_var"].round(4).to_string())
print("  max-Sharpe weights:")
print(opt["max_sharpe"].round(4).to_string())
print("  risk-parity weights:")
print(opt["risk_parity"].round(4).to_string())

# Frontier plot with EW, MV, MS, RP overlaid
mu = opt["mu_annual"].values
cov = opt["cov_annual"].values
rfr_ann = opt["rfr_annual"]
def _ps(w):
    return lib._portfolio_stats(np.asarray(w), mu, cov, rfr_ann)
ew_w = np.array([BASELINE_WEIGHTS[t] for t in BASELINE_TICKERS])
mv_w = opt["min_var"].values
ms_w = opt["max_sharpe"].values
rp_w = opt["risk_parity"].values

fig, ax = plt.subplots()
ax.plot(opt["frontier"]["sigma"] * 100, opt["frontier"]["mu"] * 100,
        color="black", linewidth=1.5, label="Efficient frontier")
for w, label, color, marker in [
    (ew_w, "Equal-weight", COLOR_PORTFOLIO, "o"),
    (mv_w, "Min-variance", PALETTE[3], "s"),
    (ms_w, "Max-Sharpe", PALETTE[4], "*"),
    (rp_w, "Risk-parity", PALETTE[5], "D"),
]:
    mu_p, sig_p, sh = _ps(w)
    ax.scatter(sig_p * 100, mu_p * 100, s=180, marker=marker, color=color,
               label=f"{label} (Sharpe={sh:.2f})", edgecolor="black", zorder=5)
ax.set_xlabel("Annualised volatility (%)")
ax.set_ylabel("Annualised expected return (%)")
ax.set_title("Efficient frontier — baseline 5 stocks (long-only, fully invested)")
ax.legend()
_save(fig, "fig09_efficient_frontier")

# Weights bar chart for the four portfolios
weights_df = pd.DataFrame({
    "Equal-weight": ew_w,
    "Min-variance": mv_w,
    "Max-Sharpe": ms_w,
    "Risk-parity": rp_w,
}, index=BASELINE_TICKERS)
fig, ax = plt.subplots()
weights_df.plot.bar(ax=ax, color=[COLOR_PORTFOLIO, PALETTE[3], PALETTE[4], PALETTE[5]])
ax.set_title("Portfolio weights under different objectives")
ax.set_ylabel("Weight")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(ticker.PercentFormatter(1.0))
_save(fig, "fig10_optimisation_weights")

# ----------------------------------------------------------------------------
# 9. Rebalancing comparison (zero transaction cost)
# ----------------------------------------------------------------------------
print("\n[9] Rebalancing comparison")
port_bh_5 = port_bh  # already computed
port_m = lib.rebalanced_value(prices[BASELINE_TICKERS], BASELINE_WEIGHTS, freq="ME", initial=INITIAL_INVESTMENT)
port_q = lib.rebalanced_value(prices[BASELINE_TICKERS], BASELINE_WEIGHTS, freq="QE", initial=INITIAL_INVESTMENT)

fig, ax = plt.subplots()
ax.plot(port_bh_5.index, port_bh_5, label="Buy-and-hold (drift)", color=COLOR_PORTFOLIO, linewidth=2.0)
ax.plot(port_m.index, port_m, label="Monthly rebalance", color=PALETTE[4], linewidth=1.5)
ax.plot(port_q.index, port_q, label="Quarterly rebalance", color=PALETTE[5], linewidth=1.5)
ax.plot(bench_value.index, bench_value, label="GSE-CI", color=COLOR_BENCH, linestyle="--", linewidth=2.0)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k"))
ax.set_title("Equal-weight portfolio under different rebalancing schedules (zero TC)")
ax.set_ylabel("Value (GHS)")
ax.legend()
_save(fig, "fig11_rebalancing")

rebal_metrics = lib.metrics_table({
    "Buy-and-hold": port_bh_5,
    "Monthly rebal": port_m,
    "Quarterly rebal": port_q,
    "GSE-CI": bench_value,
}, daily_rfr)
print(rebal_metrics.round(4).to_string())

# ----------------------------------------------------------------------------
# 10. Ghana macro adjustments — real and USD views
# ----------------------------------------------------------------------------
print("\n[10] Macro-adjusted views")
cpi = macro["cpi"]
fx = macro["usd_ghc"]
# Real (CPI-deflated) wealth
deflator = cpi / cpi.iloc[0]
port_real = port_bh / deflator.reindex(port_bh.index).ffill()
bench_real = bench_value / deflator.reindex(bench_value.index).ffill()
# USD-translated wealth (using GHS/USD)
fx_aligned = fx.reindex(port_bh.index).ffill()
port_usd = (port_bh / fx_aligned) * (fx_aligned.iloc[0] / fx_aligned.iloc[0])
bench_usd = (bench_value / fx_aligned)

fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
axes[0].plot(port_real.index, port_real, label="Portfolio (real GHS, 2016 prices)",
             color=COLOR_PORTFOLIO, linewidth=2.0)
axes[0].plot(bench_real.index, bench_real, label="GSE-CI (real GHS)",
             color=COLOR_BENCH, linestyle="--", linewidth=2.0)
axes[0].plot(port_bh.index, port_bh, label="Portfolio (nominal GHS)",
             color=COLOR_PORTFOLIO, linestyle=":", alpha=0.5)
axes[0].yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k"))
axes[0].set_title("Real (inflation-adjusted) wealth — base prices = 2016-05-23")
axes[0].set_ylabel("Value (real GHS)")
axes[0].legend()

axes[1].plot(port_usd.index, port_usd, label="Portfolio (USD)",
             color=COLOR_PORTFOLIO, linewidth=2.0)
axes[1].plot(bench_usd.index, bench_usd, label="GSE-CI (USD)",
             color=COLOR_BENCH, linestyle="--", linewidth=2.0)
axes[1].yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"${x/1000:,.0f}k"))
axes[1].set_title("USD-translated wealth (via daily GHS/USD)")
axes[1].set_ylabel("Value (USD)")
axes[1].legend()
_save(fig, "fig12_macro_adjusted")

macro_metrics = lib.metrics_table({
    "Portfolio (nominal GHS)": port_bh,
    "Portfolio (real GHS)": port_real,
    "Portfolio (USD)": port_usd,
    "GSE-CI (nominal GHS)": bench_value,
    "GSE-CI (real GHS)": bench_real,
    "GSE-CI (USD)": bench_usd,
}, daily_rfr)
print(macro_metrics.round(4).to_string())

# ----------------------------------------------------------------------------
# 11. Robustness: bootstrap + VaR
# ----------------------------------------------------------------------------
print("\n[11] Bootstrap test for outperformance significance")
boot = lib.bootstrap_outperformance(port_ret, bench_returns, n_boot=5000)
print(f"  observed daily mean diff: {boot['observed_mean_diff']:.6f}")
print(f"  annualised diff:          {boot['annualised_diff']:.4f}")
print(f"  p-value (two-sided H0=0): {boot['p_value']:.4f}")
print(f"  95% CI (annualised):      [{boot['ci_95_low_annual']:.4f}, {boot['ci_95_high_annual']:.4f}]")
print(f"  n obs={boot['n_obs']}, n_boot={boot['n_boot']}")

fig, ax = plt.subplots()
ax.hist(boot["boot_means"] * 252 * 100, bins=60, color=PALETTE[2], edgecolor="white")
ax.axvline(boot["annualised_diff"] * 100, color="red", linewidth=2.5,
           label=f"Observed: {boot['annualised_diff']*100:.2f}%")
ax.axvline(0, color="black", linewidth=1, linestyle="--", label="Null (no diff)")
ax.set_title(f"Bootstrap distribution of annualised excess return vs GSE-CI (5000 resamples, p={boot['p_value']:.3f})")
ax.set_xlabel("Annualised excess return (%)")
ax.legend()
_save(fig, "fig13_bootstrap")

# ----------------------------------------------------------------------------
# 12. MTN Scenario A — add MTN as 6th stock from IPO
# ----------------------------------------------------------------------------
print("\n[12] MTN Scenario A: 6-stock equal weight from Sep 2018")
six_w = {t: 1.0/6.0 for t in ALL_TICKERS}
# Run buy-and-hold from the MTN IPO date
mtn_era_prices = prices.loc[MTN_IPO:][ALL_TICKERS]
port_6 = lib.buy_and_hold_value(mtn_era_prices, six_w, INITIAL_INVESTMENT)
# Re-run baseline starting from same date for a fair comparison
port_5_mtn_era = lib.buy_and_hold_value(prices.loc[MTN_IPO:][BASELINE_TICKERS],
                                        BASELINE_WEIGHTS, INITIAL_INVESTMENT)
bench_mtn_era = (bench_prices.loc[MTN_IPO:] / bench_prices.loc[MTN_IPO:].iloc[0]) * INITIAL_INVESTMENT

fig, ax = plt.subplots()
ax.plot(port_5_mtn_era.index, port_5_mtn_era, label="5-stock baseline", color=COLOR_PORTFOLIO, linewidth=2)
ax.plot(port_6.index, port_6, label="6-stock (incl. MTN, equal weight)", color=PALETTE[6], linewidth=2)
ax.plot(bench_mtn_era.index, bench_mtn_era, label="GSE-CI", color=COLOR_BENCH, linestyle="--", linewidth=2)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k"))
ax.set_title("MTN Scenario A — 6-stock equal weight starting from MTN IPO (Sep 2018)")
ax.set_ylabel("Value (GHS)")
ax.legend()
_save(fig, "fig14_mtn_scenario_a")

scenA_metrics = lib.metrics_table({
    "5-stock baseline (post-IPO)": port_5_mtn_era,
    "6-stock incl. MTN": port_6,
    "GSE-CI (post-IPO)": bench_mtn_era,
}, daily_rfr)
print(scenA_metrics.round(4).to_string())

# ----------------------------------------------------------------------------
# 13. MTN Scenario B — replace worst performer at Sep 2018
# ----------------------------------------------------------------------------
print("\n[13] MTN Scenario B: replace worst performer with MTN from Sep 2018")
# Compute cumulative return of each baseline stock from 2016-05-23 to 2018-09-04
pre_ipo = prices.loc[:MTN_IPO - pd.Timedelta(days=1), BASELINE_TICKERS]
pre_returns = pre_ipo.iloc[-1] / pre_ipo.iloc[0] - 1
worst = pre_returns.idxmin()
worst_ret = pre_returns.min()
print(f"  pre-IPO cumulative returns:\n{pre_returns.round(4).to_string()}")
print(f"  worst performer = {worst} ({worst_ret*100:.1f}%)")
# Construct: baseline pre-IPO, then swap worst for MTN post-IPO
# For simplicity in path construction: build a series that holds 5 stocks
# pre-IPO (equal weight) and swap one of them (the worst's $ position is
# liquidated and reinvested in MTN at the IPO close price)

# Pre-IPO portfolio value
port_pre = lib.buy_and_hold_value(pre_ipo, BASELINE_WEIGHTS, INITIAL_INVESTMENT)
val_at_swap = float(port_pre.iloc[-1])

# Post-IPO: re-allocate based on what each stock held at the swap date
# Get per-stock dollar value at swap date
def _alloc_dollars(prices_df, weights, initial):
    allocs = {c: initial * weights[c] / prices_df[c].dropna().iloc[0] for c in weights}
    return pd.DataFrame({c: prices_df[c] * allocs[c] for c in weights})

pre_positions = _alloc_dollars(pre_ipo, BASELINE_WEIGHTS, INITIAL_INVESTMENT)
swap_date_val = pre_positions.iloc[-1]
# Replace 'worst' with MTN: the dollar amount in 'worst' becomes the MTN holding
new_tickers = [t for t in BASELINE_TICKERS if t != worst] + ["MTN"]
post_prices = prices.loc[MTN_IPO:, new_tickers].copy()
# Convert each ticker's dollar position into share count at MTN_IPO
positions = {}
for t in new_tickers:
    if t == "MTN":
        dollar = float(swap_date_val[worst])
        price0 = float(post_prices["MTN"].dropna().iloc[0])
    else:
        dollar = float(swap_date_val[t])
        price0 = float(post_prices[t].dropna().iloc[0])
    shares = dollar / price0
    positions[t] = post_prices[t] * shares
positions_df = pd.DataFrame(positions)
port_post = positions_df.sum(axis=1, min_count=1)
# Concatenate
port_swap = pd.concat([port_pre, port_post[port_post.index > port_pre.index[-1]]])

# Compare to plain baseline
fig, ax = plt.subplots()
ax.plot(port_bh.index, port_bh, label="5-stock baseline (unchanged)", color=COLOR_PORTFOLIO, linewidth=2)
ax.plot(port_swap.index, port_swap, label=f"Swap: replace {worst} with MTN at IPO",
        color=PALETTE[6], linewidth=2)
ax.plot(bench_value.index, bench_value, label="GSE-CI", color=COLOR_BENCH, linestyle="--", linewidth=2)
ax.axvline(MTN_IPO, color="grey", linewidth=0.8, linestyle=":")
ax.text(MTN_IPO, ax.get_ylim()[1] * 0.95, "  MTN IPO", color="grey", fontsize=9)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k"))
ax.set_title(f"MTN Scenario B — swap worst performer ({worst}) for MTN at IPO")
ax.set_ylabel("Value (GHS)")
ax.legend()
_save(fig, "fig15_mtn_scenario_b")

scenB_metrics = lib.metrics_table({
    "5-stock baseline": port_bh,
    f"Swap {worst} -> MTN": port_swap,
    "GSE-CI": bench_value,
}, daily_rfr)
print(scenB_metrics.round(4).to_string())

# ----------------------------------------------------------------------------
# 14. Year-by-year attribution
# ----------------------------------------------------------------------------
print("\n[14] Yearly attribution (annual rebal)")
attr = lib.yearly_attribution(prices[BASELINE_TICKERS], BASELINE_WEIGHTS)
attr["Portfolio total"] = attr.sum(axis=1)
print(attr.round(4).to_string())

fig, ax = plt.subplots(figsize=(13, 6))
attr_plot = attr.drop(columns=["Portfolio total"]) * 100
attr_plot.plot.bar(stacked=True, ax=ax, color=PALETTE[:len(BASELINE_TICKERS)], edgecolor="white")
ax.plot(range(len(attr_plot)), (attr["Portfolio total"] * 100).values,
        color="black", marker="o", linewidth=2, label="Portfolio total")
ax.set_title("Yearly return attribution by stock (annual rebal to 20% weights)")
ax.set_ylabel("Contribution (% of portfolio return)")
ax.axhline(0, color="black", linewidth=0.5)
ax.legend(loc="lower left", ncol=3)
_save(fig, "fig16_yearly_attribution")

# ----------------------------------------------------------------------------
# Persist all tables to a multi-sheet xlsx
# ----------------------------------------------------------------------------
print("\nWriting outputs/statistics.xlsx ...")
xlsx_path = ROOT / "outputs" / "statistics.xlsx"
with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
    metrics_df.to_excel(xw, sheet_name="Per-stock + Portfolio")
    rel_df.to_excel(xw, sheet_name="Benchmark-relative")
    corr_base.to_excel(xw, sheet_name="Correlation baseline")
    corr_all.to_excel(xw, sheet_name="Correlation with MTN")
    liq.to_excel(xw, sheet_name="Liquidity")
    pd.DataFrame({
        "mu_annual": opt["mu_annual"], "vol_annual": np.sqrt(np.diag(opt["cov_annual"])),
    }).to_excel(xw, sheet_name="Optim inputs")
    weights_df.to_excel(xw, sheet_name="Optim weights")
    opt["frontier"].to_excel(xw, sheet_name="Efficient frontier", index=False)
    rebal_metrics.to_excel(xw, sheet_name="Rebalancing")
    macro_metrics.to_excel(xw, sheet_name="Macro views")
    pd.DataFrame({
        "Observed mean diff (daily)": [boot["observed_mean_diff"]],
        "Annualised diff": [boot["annualised_diff"]],
        "p-value (two-sided)": [boot["p_value"]],
        "95% CI low (annual)": [boot["ci_95_low_annual"]],
        "95% CI high (annual)": [boot["ci_95_high_annual"]],
        "n observations": [boot["n_obs"]],
        "n bootstrap": [boot["n_boot"]],
    }).T.to_excel(xw, sheet_name="Bootstrap test", header=False)
    scenA_metrics.to_excel(xw, sheet_name="MTN Scenario A")
    scenB_metrics.to_excel(xw, sheet_name="MTN Scenario B")
    attr.to_excel(xw, sheet_name="Yearly attribution")

print(f"  wrote {xlsx_path}")

# Also save the headline number figure (Old vs New flagship chart)
port_total = float(port_bh.iloc[-1] / port_bh.iloc[0] - 1)
bench_total = float(bench_value.iloc[-1] / bench_value.iloc[0] - 1)
fig, ax = plt.subplots(figsize=(9, 6))
labels = ["GSE-CI", "Equal-weight portfolio"]
values = [bench_total * 100, port_total * 100]
colors = [COLOR_BENCH, COLOR_PORTFOLIO]
bars = ax.bar(labels, values, color=colors, edgecolor="black")
for bar, v in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, v + max(values)*0.02,
            f"{v:,.1f}%", ha="center", fontsize=14, fontweight="bold")
ax.set_title("Cumulative return 2016-05-23 → 2026-03-31 (nominal GHS)")
ax.set_ylabel("Cumulative return (%)")
_save(fig, "fig17_headline_cumulative")

print("\nDone.")
