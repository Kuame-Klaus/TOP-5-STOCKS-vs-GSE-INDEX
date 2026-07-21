"""Generate the narrative notebook (04_notebook.ipynb) from a template."""
import os
import nbformat as nbf
from pathlib import Path

ROOT = Path(os.environ.get(
    "GSE_ROOT",
    "/Users/kuameklaus/Documents/Claude/Projects/GSE Investment Analysis/analysis",
))
OUT = ROOT / "code" / "04_notebook.ipynb"

nb = nbf.v4.new_notebook()
cells = []

def md(s): cells.append(nbf.v4.new_markdown_cell(s))
def py(s): cells.append(nbf.v4.new_code_cell(s))

md("""# GSE Investment Strategy Analysis (2016–Q1 2026)
Equal-weighted portfolio of five GSE stocks — **BOPP, GGBL, TOTAL, GOIL, GCB** — measured against the **GSE Composite Index** over the 2016-05-23 to 2026-03-31 window, with **MTN** added as a scenario from its 2018-09-05 IPO.

This notebook is the narrative version of `03_analyze.py`. All analytical functions live in `lib.py` so this notebook stays focused on what the numbers mean.

**Key methodological choices** (improvements over last year's S&P 500 deck):
- Time-varying risk-free rate (BoG 91-day T-bill, monthly), not a constant 4.37%
- Sharpe ratio computed with consistent trading-day conventions (excess returns × 252 / (σ × √252))
- CAGR reported alongside arithmetic mean × 252
- Max drawdown, Sortino, Calmar, beta vs benchmark, Jensen's alpha, VaR/CVaR added
- Inflation-adjusted (real GHS) and USD-translated views using Ghana CPI and BoG FX
- Bootstrap test on whether the portfolio's excess return over GSE-CI is statistically distinguishable from zero
- Mean-variance optimisation (min-variance, max-Sharpe, risk-parity) and efficient frontier
- Periodic rebalancing (monthly, quarterly) compared against buy-and-hold drift
- Year-by-year per-stock attribution
- Liquidity diagnostics for the GSE's notoriously thin trading
""")

py("""import os, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path(os.environ.get('GSE_ROOT',
    '/Users/kuameklaus/Documents/Claude/Projects/GSE Investment Analysis/analysis'))
sys.path.insert(0, str(ROOT / 'code'))
import lib

sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

# Config
BASELINE_TICKERS = ['BOPP', 'GGBL', 'TOTAL', 'GOIL', 'GCB']
ALL_TICKERS = BASELINE_TICKERS + ['MTN']
BENCHMARK = 'GSE_CI'
WEIGHTS = {t: 1/5 for t in BASELINE_TICKERS}
INITIAL = 100_000
MTN_IPO = pd.Timestamp('2018-09-05')

prices = pd.read_csv(ROOT / 'data' / 'prices.csv', parse_dates=['Date']).set_index('Date')
volumes = pd.read_csv(ROOT / 'data' / 'volumes.csv', parse_dates=['Date']).set_index('Date')
macro = pd.read_csv(ROOT / 'data' / 'macro.csv', parse_dates=['Date']).set_index('Date')
daily_rfr = lib.daily_rfr(macro['tbill_91d'])
returns = lib.daily_returns(prices)
bench = prices[BENCHMARK]
print(f'Loaded {len(prices)} trading days; {prices.index.min():%Y-%m-%d} to {prices.index.max():%Y-%m-%d}')
print(f'Avg BoG 91-day T-bill RFR over period: {macro[\"tbill_91d\"].mean():.2f}%')""")

md("## 1. Data exploration")
md("Correlation matrix of daily returns for the baseline five stocks and the GSE Composite Index. Compare to last year's S&P deck where every pair correlated above 0.69 — the GSE stocks are far more independent of each other.")
py("""corr = prices[BASELINE_TICKERS + [BENCHMARK]].pct_change().corr()
fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', vmin=-1, vmax=1, ax=ax)
ax.set_title('Daily-return correlations (baseline 5 + GSE-CI)')
plt.show()
print(corr.round(2))""")

md("**Liquidity diagnostic.** BOPP and GGBL trade very thinly — most days the closing VWAP is unchanged. This artificially flatters their measured Sharpe ratio.")
py("""liq = lib.liquidity_table(volumes, prices)
print(liq.round(2))""")

md("## 2. Portfolio construction (equal-weight buy-and-hold)")
py("""port = lib.buy_and_hold_value(prices[BASELINE_TICKERS], WEIGHTS, INITIAL)
bench_val = (bench / bench.iloc[0]) * INITIAL

fig, ax = plt.subplots()
ax.plot(port.index, port, label='Equal-weight portfolio', color='#1f8a4c', linewidth=2)
ax.plot(bench_val.index, bench_val, label='GSE-CI', color='#1f4ea8', linestyle='--', linewidth=2)
ax.set_title('Portfolio vs GSE-CI (GHS 100,000 initial)')
ax.set_ylabel('Value (GHS)')
ax.legend()
plt.show()

print(f'Portfolio final value: GHS {port.iloc[-1]:,.0f}  ({port.iloc[-1]/INITIAL:.2f}x, +{(port.iloc[-1]/INITIAL-1)*100:.1f}%)')
print(f'GSE-CI final value:    GHS {bench_val.iloc[-1]:,.0f}  ({bench_val.iloc[-1]/INITIAL:.2f}x, +{(bench_val.iloc[-1]/INITIAL-1)*100:.1f}%)')""")

md("## 3. Performance metrics")
md("Using **time-varying** BoG 91-day T-bill as the risk-free rate (mean ~18% over the period).")
py("""wealth_dict = {t: (prices[t].dropna()/prices[t].dropna().iloc[0])*INITIAL for t in ALL_TICKERS}
wealth_dict['Portfolio (EW)'] = port
wealth_dict['GSE-CI'] = bench_val

metrics = lib.metrics_table(wealth_dict, daily_rfr)
print(metrics.round(4).to_string())""")

md("## 4. Risk decomposition vs GSE-CI (beta, alpha, IR)")
py("""rel = lib.benchmark_relative_table({t: wealth_dict[t] for t in ALL_TICKERS + ['Portfolio (EW)']},
                                    bench_val, daily_rfr)
print(rel.round(4).to_string())""")

md("## 5. Rolling 1-year Sharpe and volatility")
py("""port_ret = port.pct_change()
fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
axes[0].plot(lib.rolling_sharpe(port_ret, daily_rfr), label='Portfolio', color='#1f8a4c')
axes[0].plot(lib.rolling_sharpe(returns[BENCHMARK], daily_rfr), label='GSE-CI', color='#1f4ea8', linestyle='--')
axes[0].axhline(0, color='black', linewidth=0.5)
axes[0].set_title('Rolling 1-year Sharpe ratio')
axes[0].legend()
axes[1].plot(lib.rolling_vol(port_ret)*100, label='Portfolio', color='#1f8a4c')
axes[1].plot(lib.rolling_vol(returns[BENCHMARK])*100, label='GSE-CI', color='#1f4ea8', linestyle='--')
axes[1].set_title('Rolling 1-year annualised volatility (%)')
axes[1].legend()
plt.show()""")

md("## 6. Drawdowns")
py("""dd_p = lib.drawdown_series(port)
dd_b = lib.drawdown_series(bench_val)
fig, ax = plt.subplots()
ax.fill_between(dd_p.index, dd_p*100, 0, color='#1f8a4c', alpha=0.5, label='Portfolio')
ax.plot(dd_b.index, dd_b*100, color='#1f4ea8', linestyle='--', label='GSE-CI')
ax.set_title('Drawdown from running peak (%)')
ax.legend()
plt.show()""")

md("## 7. Portfolio optimisation")
md("Constraints: long-only, fully invested. Compares equal-weight (the 'naïve' choice) to min-variance, max-Sharpe, and risk-parity portfolios computed from realised covariance over the full sample.")
py("""opt = lib.optimise_portfolios(returns[BASELINE_TICKERS], daily_rfr)
weights_df = pd.DataFrame({
    'Equal-weight': [WEIGHTS[t] for t in BASELINE_TICKERS],
    'Min-variance': opt['min_var'],
    'Max-Sharpe': opt['max_sharpe'],
    'Risk-parity': opt['risk_parity'],
}, index=BASELINE_TICKERS)
print(weights_df.round(4))

fig, ax = plt.subplots()
ax.plot(opt['frontier']['sigma']*100, opt['frontier']['mu']*100, color='black', label='Efficient frontier')
for w_arr, name, marker in [
    (np.array([WEIGHTS[t] for t in BASELINE_TICKERS]), 'Equal-weight', 'o'),
    (opt['min_var'].values, 'Min-variance', 's'),
    (opt['max_sharpe'].values, 'Max-Sharpe', '*'),
    (opt['risk_parity'].values, 'Risk-parity', 'D'),
]:
    mu_p, sig_p, sh = lib._portfolio_stats(w_arr, opt['mu_annual'].values,
                                            opt['cov_annual'].values, opt['rfr_annual'])
    ax.scatter(sig_p*100, mu_p*100, s=180, marker=marker, label=f'{name} (Sharpe={sh:.2f})',
               edgecolor='black')
ax.set_xlabel('Annualised vol (%)'); ax.set_ylabel('Annualised return (%)')
ax.set_title('Efficient frontier (long-only, fully invested)')
ax.legend()
plt.show()""")

md("## 8. Rebalancing (monthly / quarterly, zero transaction cost)")
py("""port_m = lib.rebalanced_value(prices[BASELINE_TICKERS], WEIGHTS, freq='ME', initial=INITIAL)
port_q = lib.rebalanced_value(prices[BASELINE_TICKERS], WEIGHTS, freq='QE', initial=INITIAL)

fig, ax = plt.subplots()
ax.plot(port.index, port, label='Buy-and-hold', color='#1f8a4c', linewidth=2)
ax.plot(port_m.index, port_m, label='Monthly rebal', color='orange', linewidth=1.5)
ax.plot(port_q.index, port_q, label='Quarterly rebal', color='purple', linewidth=1.5)
ax.plot(bench_val.index, bench_val, label='GSE-CI', color='#1f4ea8', linestyle='--')
ax.set_title('Equal-weight portfolio under different rebalancing schedules')
ax.legend()
plt.show()

print(lib.metrics_table({'B&H': port, 'Monthly': port_m, 'Quarterly': port_q, 'GSE-CI': bench_val},
                          daily_rfr).round(4).to_string())""")

md("## 9. Macro-adjusted views: real GHS and USD")
py("""deflator = (macro['cpi'] / macro['cpi'].iloc[0]).reindex(port.index).ffill()
fx = macro['usd_ghc'].reindex(port.index).ffill()
port_real = port / deflator
bench_real = bench_val / deflator
port_usd = port / fx
bench_usd = bench_val / fx

fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
axes[0].plot(port_real.index, port_real, label='Portfolio (real GHS)', color='#1f8a4c')
axes[0].plot(bench_real.index, bench_real, label='GSE-CI (real GHS)', color='#1f4ea8', linestyle='--')
axes[0].plot(port.index, port, label='Portfolio (nominal GHS)', color='#1f8a4c', linestyle=':', alpha=0.5)
axes[0].set_title('Inflation-adjusted (real GHS) — Ghana CPI'); axes[0].legend()
axes[1].plot(port_usd.index, port_usd, label='Portfolio (USD)', color='#1f8a4c')
axes[1].plot(bench_usd.index, bench_usd, label='GSE-CI (USD)', color='#1f4ea8', linestyle='--')
axes[1].set_title('USD-translated wealth'); axes[1].legend()
plt.show()""")

md("## 10. Robustness — bootstrap test for outperformance")
md("**Important**: a high cumulative-return gap does not by itself prove the strategy is superior. We resample daily excess returns to see whether the observed outperformance is distinguishable from zero.")
py("""boot = lib.bootstrap_outperformance(port.pct_change(), returns[BENCHMARK], n_boot=5000)
print(f\"Observed annualised excess return: {boot['annualised_diff']*100:.2f}%\")
print(f\"95% bootstrap CI:                  [{boot['ci_95_low_annual']*100:.2f}%, {boot['ci_95_high_annual']*100:.2f}%]\")
print(f\"Two-sided p-value (H0: no diff):   {boot['p_value']:.4f}\")
print()
print(f\"=> {'STATISTICALLY SIGNIFICANT' if boot['p_value'] < 0.05 else 'NOT statistically significant at 5%'}\")
fig, ax = plt.subplots()
ax.hist(boot['boot_means']*252*100, bins=60, color='steelblue', edgecolor='white')
ax.axvline(boot['annualised_diff']*100, color='red', linewidth=2, label=f\"Observed: {boot['annualised_diff']*100:.2f}%\")
ax.axvline(0, color='black', linestyle='--', label='Null (no diff)')
ax.set_title('Bootstrap distribution of annualised excess return vs GSE-CI')
ax.legend()
plt.show()""")

md("## 11. MTN scenarios")
md("**Scenario A**: 6-stock equal-weight portfolio that starts at MTN's 2018-09-05 IPO and runs to today.")
py("""mtn_era_prices = prices.loc[MTN_IPO:][ALL_TICKERS]
six_w = {t: 1/6 for t in ALL_TICKERS}
port_6 = lib.buy_and_hold_value(mtn_era_prices, six_w, INITIAL)
port_5_post = lib.buy_and_hold_value(prices.loc[MTN_IPO:][BASELINE_TICKERS], WEIGHTS, INITIAL)
bench_post = (bench.loc[MTN_IPO:] / bench.loc[MTN_IPO:].iloc[0]) * INITIAL

fig, ax = plt.subplots()
ax.plot(port_5_post, label='5-stock baseline (post-IPO)', color='#1f8a4c', linewidth=2)
ax.plot(port_6, label='6-stock with MTN', color='red', linewidth=2)
ax.plot(bench_post, label='GSE-CI', color='#1f4ea8', linestyle='--')
ax.set_title('MTN Scenario A — 6-stock equal weight from MTN IPO')
ax.legend()
plt.show()
print(lib.metrics_table({'5-stock': port_5_post, '6-stock': port_6, 'GSE-CI': bench_post},
                          daily_rfr).round(4).to_string())""")

md("**Scenario B**: At MTN's IPO date, swap out the worst pre-IPO performer and put that capital into MTN.")
py("""pre = prices.loc[:MTN_IPO - pd.Timedelta(days=1), BASELINE_TICKERS]
pre_returns = pre.iloc[-1] / pre.iloc[0] - 1
worst = pre_returns.idxmin()
print(f'Pre-IPO cumulative returns:\\n{pre_returns.round(3).to_string()}')
print(f'\\nWorst performer = {worst} ({pre_returns[worst]*100:.1f}%) — swap for MTN at IPO')""")

py("""# Build the swap path
port_pre = lib.buy_and_hold_value(pre, WEIGHTS, INITIAL)
pre_positions = pd.DataFrame({c: pre[c] * (INITIAL*WEIGHTS[c]/pre[c].dropna().iloc[0]) for c in BASELINE_TICKERS})
swap_vals = pre_positions.iloc[-1]
new_tickers = [t for t in BASELINE_TICKERS if t != worst] + ['MTN']
post_prices = prices.loc[MTN_IPO:, new_tickers]
positions = {}
for t in new_tickers:
    dollar = float(swap_vals[worst]) if t == 'MTN' else float(swap_vals[t])
    p0 = float(post_prices[t].dropna().iloc[0])
    positions[t] = post_prices[t] * (dollar / p0)
port_post = pd.DataFrame(positions).sum(axis=1, min_count=1)
port_swap = pd.concat([port_pre, port_post[port_post.index > port_pre.index[-1]]])

fig, ax = plt.subplots()
ax.plot(port, label='5-stock baseline', color='#1f8a4c', linewidth=2)
ax.plot(port_swap, label=f'Swap {worst} -> MTN at IPO', color='red', linewidth=2)
ax.plot(bench_val, label='GSE-CI', color='#1f4ea8', linestyle='--')
ax.axvline(MTN_IPO, color='grey', linestyle=':', alpha=0.7)
ax.set_title(f'MTN Scenario B — swap {worst} for MTN at IPO')
ax.legend()
plt.show()
print(lib.metrics_table({'5-stock': port, f'Swap {worst}->MTN': port_swap, 'GSE-CI': bench_val},
                          daily_rfr).round(4).to_string())""")

md("## 12. Yearly attribution")
py("""attr = lib.yearly_attribution(prices[BASELINE_TICKERS], WEIGHTS)
attr['Portfolio'] = attr.sum(axis=1)
fig, ax = plt.subplots(figsize=(13, 6))
(attr.drop(columns='Portfolio') * 100).plot.bar(stacked=True, ax=ax, edgecolor='white')
ax.plot(range(len(attr)), attr['Portfolio']*100, color='black', marker='o', linewidth=2, label='Portfolio total')
ax.axhline(0, color='black', linewidth=0.5)
ax.set_ylabel('Annual return contribution (%)')
ax.set_title('Year-by-year per-stock attribution (annual rebal)')
ax.legend(ncol=3, loc='lower left')
plt.show()
print((attr*100).round(2).to_string())""")

md("""## 13. Discussion

**Headline.** The equal-weight five-stock GSE portfolio returned **~1,197%** over 2016–Q1 2026 versus the GSE Composite Index's **~637%**. CAGR: 29.7% vs 22.5%. Annualised vol: 20.4% vs 13.7%. Sharpe (with time-varying BoG 91-day T-bill RFR averaging ~18%): 0.52 vs 0.26.

**But the bootstrap puts a heavy asterisk on it.** The p-value for the portfolio's excess return over the index is **0.34** — well above the conventional 5% threshold. We cannot reject the null hypothesis that the apparent outperformance is sampling noise. In plain terms: even though the chart looks decisive, picking these five stocks in 2016 was not statistically distinguishable from buying the index.

**Liquidity caveat.** BOPP (62% zero-trade days) and GGBL (61% zero-trade days) trade very infrequently. Their measured volatility is biased downward by stale pricing, which inflates their Sharpe ratios — and by extension the portfolio's. The Sharpe ratios for thinly-traded GSE names should be read as upper bounds, not point estimates.

**Macro view.** When deflated by Ghana CPI, the portfolio's CAGR collapses from 29.7% to 13.1%. In USD terms it's 17.0%. The GSE-CI's real CAGR is 6.8% (USD: 10.5%). Most of the nominal-cedi return story is being eaten by inflation — particularly the 2022 spike to 54% YoY.

**MTN scenarios.** Both are near-neutral. The 6-stock add (Scenario A) tracks the 5-stock baseline almost exactly post-IPO. The swap (Scenario B) replaces TOTAL (the worst pre-IPO performer) with MTN at IPO, but TOTAL went on to be one of the strongest performers in 2023 and 2025, so the swap doesn't help. The lesson: 'replace the worst' is hindsight on the wrong direction — past underperformance was not predictive here.

**Optimisation.** The max-Sharpe portfolio loads ~72% into BOPP — unsurprising given BOPP's outsized realised return — but this is the standard MVO overfitting problem: optimised weights are exquisitely sensitive to realised-sample noise. The risk-parity portfolio (which doesn't use return estimates) gives a more defensible non-equal weighting: 25% / 26% / 20% / 21% / 8% for BOPP/GGBL/TOTAL/GOIL/GCB respectively.

**What this means for a real investor.** Same conclusion as last year, but with sharper Ghana-specific texture: index funds (or in Ghana's case, a GSE-CI ETF if one exists, or a broad-based fund) remain the sensible default. The 'top 5' approach delivered higher returns but with materially higher risk and no proof the outperformance is repeatable. If a Ghanaian investor must pick stocks, the risk-parity weighting is a more honest starting point than equal weight, and they should plan for ~62% drawdowns rather than the ~48% the index has historically endured.
""")

nb.cells = cells
nbf.write(nb, OUT)
print(f"Wrote {OUT}")
