"""
Phase 1a: Build the cleaned wide-format price panel.

Reads each per-ticker CSV from ../Input files/, takes the
'Closing Price - VWAP (GH¢)' as the price, and the GSE Composite Index from
the xlsx, then joins on an aligned trading-date axis and writes
analysis/data/prices.csv.

Design notes:
- We use VWAP close (volume-weighted) rather than 'Last Transaction Price'
  because it is the standard adjusted close for a low-liquidity exchange like
  GSE and is less sensitive to a single end-of-day trade.
- Two source-file styles exist: the original five quote every field, the new
  GCB file only quotes thousand-separated numbers. pandas.read_csv handles
  both with default settings.
- 'Total Shares Traded' / 'Total Value Traded' columns have thousand
  separators on recent rows but not always on older rows. We parse them as
  strings then coerce, so we can keep them for the liquidity sanity check.
- Period is clipped to 2016-05-23 (GSE-CI start) -> 2026-03-31 (Q1 2026, per
  user spec). MTN keeps its native start date (2018-09-05) so it can serve
  as a scenario asset.
"""

from __future__ import annotations
import os
import pandas as pd
from pathlib import Path

# Paths can be overridden via environment variables so the same script runs
# both on the user's Mac and from the sandboxed Linux environment.
INPUT_DIR = Path(os.environ.get(
    "GSE_INPUT_DIR",
    "/Users/kuameklaus/Desktop/GSE Analysis/Input files",
))
OUTPUT_DIR = Path(os.environ.get(
    "GSE_DATA_DIR",
    "/Users/kuameklaus/Documents/Claude/Projects/GSE Investment Analysis/analysis/data",
))

START_DATE = pd.Timestamp("2016-05-23")  # GSE-CI series begins
END_DATE = pd.Timestamp("2026-03-31")    # User-specified Q1 2026 cutoff

# Ticker -> filename in INPUT_DIR
STOCK_FILES = {
    "BOPP":  "Daily Shares  ETFs BOPP.csv",
    "GGBL":  "Daily Shares  ETFs GGBL.csv",
    "TOTAL": "Daily Shares  ETFs TOTAL.csv",
    "GOIL":  "Daily Shares  ETFs GOIL.csv",
    "GCB":   "Daily Shares  ETFs 2023  GCB.csv",
    "MTN":   "Daily Shares  ETFs -MTN.csv",
}
INDEX_FILE = "GSE_Composite_Index.xlsx"

PRICE_COL = "Closing Price - VWAP (GH¢)"
VOLUME_COL = "Total Shares Traded"


def _coerce_number(series: pd.Series) -> pd.Series:
    """Strip thousand-separator commas, replace empty strings with NaN, cast to float."""
    return (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace({"": None, "nan": None, "NaN": None})
        .astype(float)
    )


def load_stock(ticker: str, filename: str) -> pd.DataFrame:
    path = INPUT_DIR / filename
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    # Parse date dd/mm/yyyy
    df["Date"] = pd.to_datetime(df["Daily Date"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["Date"])

    df["Price"] = _coerce_number(df[PRICE_COL])
    df["Volume"] = _coerce_number(df[VOLUME_COL])

    # Drop rows where price could not be parsed or is non-positive
    df = df[df["Price"].notna() & (df["Price"] > 0)].copy()

    # Per-ticker date range
    n_in = len(df)
    df = df[(df["Date"] >= START_DATE) & (df["Date"] <= END_DATE)].copy()
    print(f"  {ticker}: {n_in} parsed rows -> {len(df)} after date clip "
          f"[{df['Date'].min():%Y-%m-%d} .. {df['Date'].max():%Y-%m-%d}]")

    # On duplicate-date rows (some raw files have a 0-volume placeholder plus
    # the actual traded row), explicitly keep the row with the higher recorded
    # volume — that's the genuine trade. drop_duplicates(keep='last') would
    # work for the current input files only because of pandas sort-stability
    # quirks; selecting by volume is reproducible regardless.
    df = (df.sort_values(["Date", "Volume"], ascending=[True, True])
            .drop_duplicates("Date", keep="last"))
    out = df[["Date", "Price", "Volume"]].rename(
        columns={"Price": ticker, "Volume": f"{ticker}_VOL"}
    )
    return out


def load_index() -> pd.DataFrame:
    path = INPUT_DIR / INDEX_FILE
    df = pd.read_excel(path, sheet_name="GSE Composite Index")
    df.columns = [c.strip() for c in df.columns]
    df["Date"] = pd.to_datetime(df["Date"])
    df["GSE_CI"] = pd.to_numeric(df["GSE-CI Value"], errors="coerce")
    df = df.dropna(subset=["GSE_CI"])
    df = df[(df["Date"] >= START_DATE) & (df["Date"] <= END_DATE)].copy()
    print(f"  GSE_CI: {len(df)} rows "
          f"[{df['Date'].min():%Y-%m-%d} .. {df['Date'].max():%Y-%m-%d}]")
    return df[["Date", "GSE_CI"]].sort_values("Date").drop_duplicates("Date", keep="last")


def main() -> None:
    print("Loading stocks...")
    stock_frames = [load_stock(t, f) for t, f in STOCK_FILES.items()]
    print("Loading index...")
    idx = load_index()

    # Outer-join everything on Date so we can see where each series has gaps
    print("Joining...")
    panel = idx.copy()
    for sf in stock_frames:
        panel = panel.merge(sf, on="Date", how="outer")
    panel = panel.sort_values("Date").reset_index(drop=True)

    # Split prices vs volumes
    price_cols = ["GSE_CI"] + list(STOCK_FILES.keys())
    volume_cols = [f"{t}_VOL" for t in STOCK_FILES.keys()]

    prices = panel[["Date"] + price_cols].copy()
    volumes = panel[["Date"] + volume_cols].copy()

    # Forward-fill prices for missing trading days WITHIN each series' lifetime
    # (Common practice for thinly-traded GSE stocks; MTN's pre-IPO NaNs are
    # left alone — those are not gaps, the asset didn't exist.)
    for col in ["GSE_CI", "BOPP", "GGBL", "TOTAL", "GOIL", "GCB"]:
        # Find first non-NaN; only ffill after that
        first_valid = prices[col].first_valid_index()
        if first_valid is not None:
            prices.loc[first_valid:, col] = prices.loc[first_valid:, col].ffill()
    # MTN: only ffill from its IPO date forward (handled the same way)
    first_valid = prices["MTN"].first_valid_index()
    if first_valid is not None:
        prices.loc[first_valid:, "MTN"] = prices.loc[first_valid:, "MTN"].ffill()

    # Trading-day calendar = union of dates where GSE_CI exists (it represents
    # the exchange's actual trading days)
    trading_days = panel.loc[panel["GSE_CI"].notna(), "Date"].sort_values()
    prices = prices[prices["Date"].isin(trading_days)].reset_index(drop=True)
    volumes = volumes[volumes["Date"].isin(trading_days)].reset_index(drop=True)

    # Write
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prices_path = OUTPUT_DIR / "prices.csv"
    volumes_path = OUTPUT_DIR / "volumes.csv"
    prices.to_csv(prices_path, index=False, float_format="%.4f")
    volumes.to_csv(volumes_path, index=False, float_format="%.0f")

    # Summary
    print("\n=== prices.csv summary ===")
    print(f"Rows: {len(prices)}  ({prices['Date'].min():%Y-%m-%d} .. {prices['Date'].max():%Y-%m-%d})")
    print("\nPer-column coverage:")
    for c in price_cols:
        non_na = prices[c].notna().sum()
        first = prices.loc[prices[c].notna(), "Date"].min()
        last = prices.loc[prices[c].notna(), "Date"].max()
        print(f"  {c:8s}  {non_na:5d} non-NaN   {first:%Y-%m-%d} .. {last:%Y-%m-%d}")

    print("\nHead:")
    print(prices.head(5).to_string(index=False))
    print("\nTail:")
    print(prices.tail(5).to_string(index=False))
    print(f"\nWrote: {prices_path}")
    print(f"Wrote: {volumes_path}")


if __name__ == "__main__":
    main()
