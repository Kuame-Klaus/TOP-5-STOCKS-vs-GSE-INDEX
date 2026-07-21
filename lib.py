"""
Library of analysis helpers for the GSE investment analysis.

Everything in this module is data-frame-in / data-frame-out so the same
functions can be called from both the script (03_analyze.py) and the
narrative notebook (04_notebook.ipynb).

Conventions
- All returns are daily simple returns unless otherwise specified.
- Annualization uses 252 trading days.
- Risk-free rate is time-varying: a daily series in % per annum.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import numpy as np
import pandas as pd

TRADING_DAYS = 252


# ----------------------------------------------------------------------------
# Returns
# ----------------------------------------------------------------------------
def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns: price[t] / price[t-1] - 1."""
    return prices.pct_change()


def cum_wealth(returns: pd.DataFrame, initial: float = 1.0) -> pd.DataFrame:
    """Cumulative wealth path from a return series."""
    return initial * (1.0 + returns.fillna(0.0)).cumprod()


def daily_rfr(tbill_annual_pct: pd.Series) -> pd.Series:
    """Convert annual % T-bill rate to daily (trading-day) decimal rate."""
    return (tbill_annual_pct / 100.0) / TRADING_DAYS


# ----------------------------------------------------------------------------
# Portfolio construction (no rebalancing = buy-and-hold drift)
# ----------------------------------------------------------------------------
def buy_and_hold_value(prices: pd.DataFrame, weights: dict[str, float],
                       initial: float = 100_000.0) -> pd.Series:
    """Buy-and-hold portfolio value (drifts with each stock's price).
    NaN prices (e.g. MTN before IPO) contribute zero, so the portfolio is
    only invested in the assets that exist at each date.
    """
    cols = list(weights.keys())
    # Allocate at first available date for each ticker
    allocations = {c: initial * weights[c] / prices[c].dropna().iloc[0] for c in cols}
    positions = pd.DataFrame({c: prices[c] * allocations[c] for c in cols})
    return positions.sum(axis=1, min_count=1)


def rebalanced_value(prices: pd.DataFrame, weights: dict[str, float],
                     freq: str | None = None,
                     initial: float = 100_000.0) -> pd.Series:
    """Periodically rebalanced portfolio.

    freq: None for buy-and-hold (no rebalancing), 'M' for monthly,
          'Q' for quarterly. Zero transaction cost.
    """
    if freq is None:
        return buy_and_hold_value(prices, weights, initial)

    cols = list(weights.keys())
    # Use price-derived returns, weight-averaged each period, then rebalance
    rets = prices[cols].pct_change().fillna(0.0)
    value = pd.Series(index=prices.index, dtype=float)
    value.iloc[0] = initial
    current_w = pd.Series(weights, dtype=float).reindex(cols).fillna(0.0)
    # Track value of each holding; rebalance at the END of each rebalance period
    holdings = current_w * initial
    rebalance_dates = (
        prices.resample(freq).last().index.intersection(prices.index)
    )
    for i in range(1, len(prices)):
        date = prices.index[i]
        # Apply day's return to each holding (skipping NaN assets)
        day_ret = rets.iloc[i]
        # Only assets that have a non-NaN return today participate
        valid = day_ret.notna() & holdings.notna()
        holdings = holdings.where(~valid, holdings * (1 + day_ret))
        total = holdings.sum()
        value.iloc[i] = total
        # Rebalance if this is a rebalance date and total > 0
        if date in rebalance_dates and total > 0:
            # Rebalance only to assets that have a price today
            live = prices.iloc[i][cols].notna()
            live_w = current_w * live
            if live_w.sum() > 0:
                live_w = live_w / live_w.sum()
            else:
                live_w = current_w
            holdings = live_w * total
    return value


# ----------------------------------------------------------------------------
# Risk & performance metrics
# ----------------------------------------------------------------------------
@dataclass
class Metrics:
    total_return: float
    cagr: float
    ann_vol: float
    sharpe: float
    sortino: float
    calmar: float
    max_dd: float
    max_dd_duration_days: int
    var_95_1d: float
    cvar_95_1d: float
    var_99_1d: float


def _annualize_vol(daily: pd.Series) -> float:
    return float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _cagr(wealth: pd.Series) -> float:
    wealth = wealth.dropna()
    if len(wealth) < 2:
        return float("nan")
    n_years = (wealth.index[-1] - wealth.index[0]).days / 365.25
    return float((wealth.iloc[-1] / wealth.iloc[0]) ** (1 / n_years) - 1)


def _max_drawdown(wealth: pd.Series) -> tuple[float, int]:
    """Return max drawdown (negative number) and its duration in days."""
    wealth = wealth.dropna()
    running_max = wealth.cummax()
    dd = (wealth - running_max) / running_max
    max_dd = float(dd.min())
    end = dd.idxmin()
    start = wealth.loc[:end].idxmax()
    duration = (end - start).days
    return max_dd, duration


def _sortino(daily: pd.Series, daily_rfr_series: pd.Series) -> float:
    excess = daily - daily_rfr_series.reindex(daily.index).ffill()
    downside = excess.clip(upper=0)
    dd = float(downside.std(ddof=1) * np.sqrt(TRADING_DAYS))
    if dd == 0:
        return float("nan")
    return float(excess.mean() * TRADING_DAYS / dd)


def metrics_for(wealth: pd.Series, daily_rfr_series: pd.Series) -> Metrics:
    """Compute the full suite of risk/return metrics on a wealth series."""
    wealth = wealth.dropna()
    daily = wealth.pct_change().dropna()
    total = float(wealth.iloc[-1] / wealth.iloc[0] - 1)
    cagr = _cagr(wealth)
    vol = _annualize_vol(daily)
    rfr_aligned = daily_rfr_series.reindex(daily.index).ffill()
    excess = daily - rfr_aligned
    sharpe = float(excess.mean() * TRADING_DAYS / vol) if vol > 0 else float("nan")
    sortino = _sortino(daily, daily_rfr_series)
    max_dd, dur = _max_drawdown(wealth)
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else float("nan")
    var_95 = float(np.percentile(daily, 5))
    cvar_95 = float(daily[daily <= var_95].mean())
    var_99 = float(np.percentile(daily, 1))
    return Metrics(
        total_return=total, cagr=cagr, ann_vol=vol, sharpe=sharpe,
        sortino=sortino, calmar=calmar, max_dd=max_dd,
        max_dd_duration_days=dur, var_95_1d=var_95,
        cvar_95_1d=cvar_95, var_99_1d=var_99,
    )


def metrics_table(wealth_dict: dict[str, pd.Series],
                  daily_rfr_series: pd.Series) -> pd.DataFrame:
    """Stack metrics for many series into one table."""
    rows = {}
    for name, w in wealth_dict.items():
        m = metrics_for(w, daily_rfr_series)
        rows[name] = {
            "Total Return": m.total_return,
            "CAGR": m.cagr,
            "Annualised Vol": m.ann_vol,
            "Sharpe (TV RFR)": m.sharpe,
            "Sortino": m.sortino,
            "Calmar": m.calmar,
            "Max Drawdown": m.max_dd,
            "Max DD Duration (days)": m.max_dd_duration_days,
            "VaR 95% (1d)": m.var_95_1d,
            "CVaR 95% (1d)": m.cvar_95_1d,
            "VaR 99% (1d)": m.var_99_1d,
        }
    return pd.DataFrame(rows).T


# ----------------------------------------------------------------------------
# Benchmark relative metrics (beta, alpha, IR, tracking error)
# ----------------------------------------------------------------------------
def benchmark_relative(asset_returns: pd.Series, bench_returns: pd.Series,
                       daily_rfr_series: pd.Series) -> dict:
    df = pd.concat([asset_returns, bench_returns], axis=1).dropna()
    df.columns = ["a", "b"]
    rfr_aligned = daily_rfr_series.reindex(df.index).ffill()
    ex_a = df["a"] - rfr_aligned
    ex_b = df["b"] - rfr_aligned
    cov = float(ex_a.cov(ex_b))
    var_b = float(ex_b.var(ddof=1))
    beta = cov / var_b if var_b > 0 else float("nan")
    alpha_daily = float(ex_a.mean() - beta * ex_b.mean())
    alpha_annual = alpha_daily * TRADING_DAYS
    corr = float(df["a"].corr(df["b"]))
    r2 = corr * corr
    diff = df["a"] - df["b"]
    te = float(diff.std(ddof=1) * np.sqrt(TRADING_DAYS))
    ir = float(diff.mean() * TRADING_DAYS / te) if te > 0 else float("nan")
    treynor = float(ex_a.mean() * TRADING_DAYS / beta) if beta else float("nan")
    return {
        "Beta": beta,
        "Alpha (annualised)": alpha_annual,
        "R^2 vs Benchmark": r2,
        "Tracking Error": te,
        "Information Ratio": ir,
        "Treynor Ratio": treynor,
    }


def benchmark_relative_table(wealth_dict: dict[str, pd.Series],
                             bench_wealth: pd.Series,
                             daily_rfr_series: pd.Series) -> pd.DataFrame:
    bench_ret = bench_wealth.pct_change()
    rows = {}
    for name, w in wealth_dict.items():
        rows[name] = benchmark_relative(w.pct_change(), bench_ret, daily_rfr_series)
    return pd.DataFrame(rows).T


# ----------------------------------------------------------------------------
# Rolling metrics
# ----------------------------------------------------------------------------
def rolling_sharpe(returns: pd.Series, daily_rfr_series: pd.Series,
                   window: int = 252) -> pd.Series:
    rfr_aligned = daily_rfr_series.reindex(returns.index).ffill()
    excess = returns - rfr_aligned
    rmean = excess.rolling(window).mean()
    rstd = returns.rolling(window).std(ddof=1)
    return (rmean * TRADING_DAYS) / (rstd * np.sqrt(TRADING_DAYS))


def rolling_vol(returns: pd.Series, window: int = 252) -> pd.Series:
    return returns.rolling(window).std(ddof=1) * np.sqrt(TRADING_DAYS)


def drawdown_series(wealth: pd.Series) -> pd.Series:
    rm = wealth.cummax()
    return (wealth - rm) / rm


# ----------------------------------------------------------------------------
# Portfolio optimization (no-short-sale, fully invested)
# ----------------------------------------------------------------------------
def _portfolio_stats(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray,
                     rfr_annual: float) -> tuple[float, float, float]:
    """Return (annualised mu_p, annualised sigma_p, Sharpe) given annualised
    inputs."""
    mu_p = float(weights @ mu)
    sigma_p = float(np.sqrt(weights @ cov @ weights))
    sharpe = (mu_p - rfr_annual) / sigma_p if sigma_p > 0 else float("nan")
    return mu_p, sigma_p, sharpe


def optimise_portfolios(returns: pd.DataFrame, daily_rfr_series: pd.Series,
                        n_frontier: int = 50) -> dict:
    """Compute min-variance, max-Sharpe and risk-parity portfolios plus the
    efficient frontier. Constraints: weights >= 0, sum to 1.
    Uses scipy.optimize for the constrained problems.
    """
    from scipy.optimize import minimize

    rets = returns.dropna(how="any")
    mu = rets.mean().values * TRADING_DAYS
    cov = rets.cov().values * TRADING_DAYS
    n = len(mu)
    rfr_annual = float(daily_rfr_series.reindex(rets.index).ffill().mean() * TRADING_DAYS)

    bounds = [(0.0, 1.0)] * n
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1.0},)
    w0 = np.ones(n) / n

    # Min variance
    res_mv = minimize(lambda w: w @ cov @ w, w0, method="SLSQP",
                      bounds=bounds, constraints=cons)
    w_mv = res_mv.x

    # Max Sharpe
    res_ms = minimize(
        lambda w: -(_portfolio_stats(w, mu, cov, rfr_annual)[2]),
        w0, method="SLSQP", bounds=bounds, constraints=cons,
    )
    w_ms = res_ms.x

    # Risk parity (equal risk contribution)
    def risk_parity_obj(w):
        sigma = np.sqrt(w @ cov @ w)
        mrc = cov @ w / sigma if sigma > 0 else np.zeros_like(w)
        rc = w * mrc
        target = sigma / n
        return float(np.sum((rc - target) ** 2))
    res_rp = minimize(risk_parity_obj, w0, method="SLSQP",
                      bounds=bounds, constraints=cons)
    w_rp = res_rp.x

    # Efficient frontier: sweep target returns
    mu_min, mu_max = float(mu.min()), float(mu.max())
    target_mus = np.linspace(mu_min, mu_max, n_frontier)
    frontier = []
    for tm in target_mus:
        cons_t = (
            {"type": "eq", "fun": lambda w: w.sum() - 1.0},
            {"type": "eq", "fun": lambda w, t=tm: float(w @ mu) - t},
        )
        res = minimize(lambda w: w @ cov @ w, w0, method="SLSQP",
                       bounds=bounds, constraints=cons_t)
        if res.success:
            frontier.append({"mu": tm, "sigma": float(np.sqrt(res.x @ cov @ res.x))})
    frontier_df = pd.DataFrame(frontier)

    cols = list(rets.columns)
    return {
        "tickers": cols,
        "mu_annual": pd.Series(mu, index=cols),
        "cov_annual": pd.DataFrame(cov, index=cols, columns=cols),
        "rfr_annual": rfr_annual,
        "min_var": pd.Series(w_mv, index=cols),
        "max_sharpe": pd.Series(w_ms, index=cols),
        "risk_parity": pd.Series(w_rp, index=cols),
        "frontier": frontier_df,
    }


# ----------------------------------------------------------------------------
# Bootstrap test for outperformance significance
# ----------------------------------------------------------------------------
def bootstrap_outperformance(port_returns: pd.Series, bench_returns: pd.Series,
                             n_boot: int = 5000, seed: int = 42) -> dict:
    """Test H0: mean(port - bench) = 0 via bootstrap resampling of the
    daily excess-return series. Returns p-value and bootstrap distribution."""
    diff = (port_returns - bench_returns).dropna()
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    n = len(diff)
    diff_vals = diff.values
    for i in range(n_boot):
        sample = rng.choice(diff_vals, size=n, replace=True)
        means[i] = sample.mean()
    obs = float(diff.mean())
    # Two-sided test centered at zero by shifting
    centered = means - obs
    p_two_sided = float(np.mean(np.abs(centered) >= abs(obs)))
    ci_low, ci_high = float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
    return {
        "observed_mean_diff": obs,
        "annualised_diff": obs * TRADING_DAYS,
        "p_value": p_two_sided,
        "ci_95_low_annual": ci_low * TRADING_DAYS,
        "ci_95_high_annual": ci_high * TRADING_DAYS,
        "n_obs": n,
        "n_boot": n_boot,
        "boot_means": means,
    }


# ----------------------------------------------------------------------------
# Yearly attribution: per-stock contribution to portfolio return each year
# ----------------------------------------------------------------------------
def yearly_attribution(prices: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """For each calendar year, decompose the portfolio's return into per-stock
    contributions assuming weights are rebalanced to target at the start of
    each year (cleanest attribution).
    """
    out = {}
    for year in sorted(set(prices.index.year)):
        yr = prices[prices.index.year == year]
        if len(yr) < 2:
            continue
        contribs = {}
        for t, w in weights.items():
            s = yr[t].dropna()
            if len(s) < 2:
                contribs[t] = 0.0
                continue
            ret = s.iloc[-1] / s.iloc[0] - 1
            contribs[t] = w * ret
        out[year] = contribs
    return pd.DataFrame(out).T  # rows=years, cols=tickers


# ----------------------------------------------------------------------------
# Liquidity diagnostics
# ----------------------------------------------------------------------------
def liquidity_table(volumes: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Per-ticker: avg daily volume, zero-trade days, %distinct prices."""
    rows = {}
    for col in volumes.columns:
        t = col.replace("_VOL", "")
        vol = volumes[col].dropna()
        zero_days = int((vol == 0).sum())
        avg_vol = float(vol[vol > 0].mean()) if (vol > 0).any() else 0.0
        prices_t = prices[t].dropna()
        distinct = int(prices_t.nunique())
        total_days = int(prices_t.notna().sum())
        rows[t] = {
            "avg_daily_volume": avg_vol,
            "zero_trade_days": zero_days,
            "pct_zero_trade": 100.0 * zero_days / max(total_days, 1),
            "distinct_prices": distinct,
            "total_obs": total_days,
            "pct_distinct": 100.0 * distinct / max(total_days, 1),
        }
    return pd.DataFrame(rows).T
