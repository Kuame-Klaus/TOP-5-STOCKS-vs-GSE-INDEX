// Build the Word report: Investment Strategy Analysis (GSE Edition, 2026)
// Mirrors last year's structure with the new GSE numbers and added analyses.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Header, Footer, AlignmentType, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak, HeadingLevel, LevelFormat, TabStopType,
  TabStopPosition, PageOrientation,
} = require("docx");

const ROOT = process.env.GSE_ROOT || "/Users/kuameklaus/Documents/Claude/Projects/GSE Investment Analysis/analysis";
const FIG = path.join(ROOT, "outputs", "figures");
const OUT = path.join(ROOT, "outputs", "reports", "GSE Investment Strategy Analysis.docx");
fs.mkdirSync(path.dirname(OUT), { recursive: true });

// ---------- helpers ----------
const p = (text, opts = {}) => new Paragraph({
  spacing: { after: 120 },
  ...opts,
  children: [new TextRun({ text, ...(opts.run || {}) })],
});

const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 280, after: 200 },
  children: [new TextRun({ text })],
});
const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 220, after: 160 },
  children: [new TextRun({ text })],
});

const bullet = (text) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  spacing: { after: 80 },
  children: [new TextRun({ text })],
});

const fig = (filename, caption) => {
  const filePath = path.join(FIG, filename);
  const buf = fs.readFileSync(filePath);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 160, after: 60 },
      children: [new ImageRun({
        type: "png",
        data: buf,
        transformation: { width: 580, height: 340 },
        altText: { title: caption, description: caption, name: filename },
      })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 220 },
      children: [new TextRun({ text: caption, italics: true, size: 20 })],
    }),
  ];
};

const cell = (text, opts = {}) => new TableCell({
  width: { size: opts.width || 1872, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" },
    bottom: { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" },
    left: { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" },
    right: { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" },
  },
  margins: { top: 80, bottom: 80, left: 120, right: 120 },
  shading: opts.header
    ? { fill: "1F4EA8", type: ShadingType.CLEAR }
    : undefined,
  children: [new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    children: [new TextRun({
      text: String(text),
      bold: !!opts.header,
      color: opts.header ? "FFFFFF" : "000000",
      size: 20,
    })],
  })],
});

const buildTable = (rows, columnWidths) => {
  return new Table({
    width: { size: columnWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths,
    rows: rows.map((row, i) => new TableRow({
      children: row.map((c, j) => cell(c, {
        header: i === 0,
        align: j === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
        width: columnWidths[j],
      })),
    })),
  });
};

// ---------- content ----------
const children = [];

// Title
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 800, after: 200 },
  children: [new TextRun({
    text: "Investment Strategy Analysis",
    size: 56, bold: true, color: "1F4EA8",
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [new TextRun({
    text: "Equal-Weighted GSE Top-Five vs the GSE Composite Index, 2016–Q1 2026",
    size: 32, color: "555555",
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 1200 },
  children: [new TextRun({ text: "Prepared May 2026", size: 22, italics: true })],
}));

// Executive Summary
children.push(h1("Executive Summary"));
children.push(p("This report extends a 2025 analysis of an equal-weighted S&P 500 portfolio to the Ghana Stock Exchange. An initial GHS 100,000 was equally distributed across five GSE-listed stocks — BOPP, GGBL, TOTAL, GOIL, and GCB — and held without rebalancing from 23 May 2016 to 31 March 2026 (a window chosen to start when the GSE Composite Index series begins). Performance is measured against the GSE Composite Index (GSE-CI). A separate set of scenarios brings MTN into the analysis from its September 2018 IPO."));
children.push(h2("Key findings"));
children.push(bullet("Nominal cumulative return: the equal-weighted portfolio returned roughly 1,197% (a 12.97× multiple of initial capital) versus 637% (7.37×) for the GSE-CI."));
children.push(bullet("CAGR: 29.7% for the portfolio against 22.5% for the index, on annualised volatilities of 30.8% and 13.7% respectively."));
children.push(bullet("Sharpe ratio (using the time-varying Bank of Ghana 91-day Treasury bill, averaging ~18% over the period): 0.41 for the portfolio against 0.26 for the index — roughly 60% better risk-adjusted return."));
children.push(bullet("Statistical robustness, however, is weak: a 5,000-iteration bootstrap of the daily excess-return series produces a two-sided p-value of 0.38 against the null of no outperformance, so the apparent edge cannot be distinguished from sampling noise."));
children.push(bullet("Real returns (deflated by Ghana CPI) are far more modest: the portfolio's real CAGR is 12.3%, the index's just 6.0%. In USD terms (at the daily GHS/USD mid-rate), the portfolio's CAGR is 17.0%; the index's is 10.5%."));
children.push(bullet("BOPP alone accounts for the bulk of the portfolio's outperformance, mirroring NVIDIA's role in last year's S&P 500 deck. BOPP grew 33× over the period."));
children.push(bullet("Adding MTN as a sixth equal-weighted stock from its IPO (Scenario A) tracks the five-stock baseline almost exactly. Swapping the worst pre-IPO performer (TOTAL) for MTN at the IPO date (Scenario B) is similarly near-neutral, as TOTAL went on to be one of the strongest contributors in 2023 and 2025."));
children.push(p("The methodological improvements relative to last year — time-varying risk-free rate, consistent day conventions for the Sharpe ratio, drawdown and downside-risk metrics, inflation- and FX-adjusted views, portfolio optimisation, and a bootstrap significance test — sharpen what we can and cannot claim from the data. The directional finding (the top-five portfolio outperformed the index) holds, but the inferential strength is weaker than the 2025 S&P 500 deck suggested for its US counterpart, and the GSE's notoriously thin trading for some names (BOPP and GGBL have ~62% zero-trade days) materially affects the measured Sharpe."));

// Introduction
children.push(h1("Introduction"));
children.push(p("Ordinary investors face a familiar choice between low-cost passive exposure via index funds and active stock selection. Last year's analysis applied this framing to the S&P 500: an equal-weighted portfolio of Apple, NVIDIA, Microsoft, Amazon, and Meta over 2015–2024 substantially outperformed the index. This report replicates the same exercise on the Ghana Stock Exchange, with two important methodological upgrades that produce a more defensible answer: a Ghana-specific risk-free rate, and a bootstrap significance test for the outperformance."));

// Case Description
children.push(h1("Case Description"));
children.push(h2("Details"));
children.push(p("The portfolio comprises five GSE-listed equities chosen to span sectors of meaningful economic weight in Ghana: agro-processing (BOPP, Benso Oil Palm Plantation), beverages (GGBL, Guinness Ghana Breweries), downstream fuel retail (TOTAL, TotalEnergies Marketing Ghana, and GOIL, Ghana Oil Company), and banking (GCB, GCB Bank). MTN (Scancom PLC, ticker MTNGH) is run as a scenario asset because its 2018 IPO post-dates the start of the analysis window."));
children.push(p("Benchmark: GSE Composite Index (GSE-CI), the all-share index of the Ghana Stock Exchange."));
children.push(p("Initial investment: GHS 100,000, allocated equally (20% each) at the close on 23 May 2016 (the first trading day for which the GSE-CI is published)."));
children.push(p("Holding period: 23 May 2016 to 31 March 2026 (~2,440 trading days)."));
children.push(h2("Participants"));
children.push(p("The intended reader is an ordinary Ghanaian retail investor weighing concentrated stock selection against passive exposure to the broader exchange. The methodology and data, however, are also suitable for a research or coursework setting."));

// Methodology
children.push(h1("Methodology"));
children.push(h2("Data collection"));
children.push(p("Daily VWAP-based closing prices for the six stocks were sourced from the Ghana Stock Exchange daily share trading reports (via afx.kwayisi.org). The GSE Composite Index series was sourced directly from the GSE. Macro covariates — Bank of Ghana 91-day Treasury bill auction rate, Ghana Statistical Service Consumer Price Index, and the BoG end-of-month interbank USD/GHC mid-rate — were compiled from seven BoG Summary of Economic and Financial Data bulletins (September 2017, November 2020, January 2022, July 2022, January 2024, July 2024, and January 2026). The CPI series was chained across three published base years (2012, 2018, 2021) onto a consistent 2021 = 100 base."));
children.push(p("Data cleaning was performed in Python (pandas) rather than Alteryx. Within-series gaps for thinly-traded stocks were forward-filled to the trading calendar defined by the GSE-CI; MTN's pre-IPO observations were left as missing rather than zero-filled so the asset only enters portfolio math from its actual listing date."));
children.push(h2("Data quality flags"));
children.push(bullet("Most of 2018 and 2019 are not directly covered by any BoG bulletin retrieved for this study; macro series for those years are linearly interpolated between Aug 2017 and Oct 2019. These were relatively quiet years for inflation, the cedi, and policy rates, so this is acceptable for portfolio-level metrics but worth flagging."));
children.push(bullet("BOPP and GGBL exhibit ~62% zero-trade-day rates, meaning the VWAP closing price is unchanged from the previous day on most observations. This depresses measured volatility and inflates measured Sharpe."));
children.push(h2("Data analysis"));
children.push(p("Analysis was conducted in Python using pandas, numpy, scipy, matplotlib and seaborn. Daily simple returns and log returns were both computed; the headline metrics use simple returns. Annualisation uses 252 trading days throughout."));
children.push(h2("Investment simulation"));
children.push(p("The baseline portfolio is constructed as a buy-and-hold equal-weight allocation (20% per stock at 23 May 2016 close). Parallel construction tests rebalance the portfolio monthly and quarterly back to 20% targets, assuming zero transaction cost (the GSE's actual costs would be higher, so the rebalancing comparisons here isolate the timing/weight effect from the cost drag)."));
children.push(h2("Risk-adjusted performance"));
children.push(p("Risk-adjusted performance is summarised by the following metrics. All are reported on an annualised basis where applicable."));
children.push(bullet("CAGR (compound annual growth rate) = (V_T / V_0)^(1/T) − 1, where T is years."));
children.push(bullet("Annualised volatility = σ_daily × √252, where σ_daily is the standard deviation of daily simple returns."));
children.push(bullet("Sharpe ratio = (mean daily return − daily risk-free rate) × 252 / (σ_daily × √252). The risk-free rate is the BoG 91-day T-bill auction rate (interest equivalent), converted from annual % to daily decimal as (rate/100)/252 and aligned to each trading day."));
children.push(bullet("Sortino ratio = mean excess return × 252 / (downside σ × √252), using only negative excess returns in the denominator."));
children.push(bullet("Calmar ratio = CAGR / |Max Drawdown|."));
children.push(bullet("Max drawdown = the worst peak-to-trough decline over the period, plus the time in days to reach the trough from the prior peak."));
children.push(bullet("Beta and Jensen's alpha = OLS regression of asset excess returns on GSE-CI excess returns."));
children.push(bullet("Tracking error and Information Ratio vs the GSE-CI."));
children.push(bullet("1-day historical VaR and CVaR at 95% confidence."));
children.push(p("Outperformance significance is tested by 5,000-iteration nonparametric bootstrap of the daily excess-return series (portfolio − benchmark), reporting a two-sided p-value against the null of zero mean difference and a 95% confidence interval on the annualised difference."));
children.push(p("Portfolio optimisation uses scipy.optimize SLSQP under the constraints w ≥ 0 and Σw = 1 (long-only, fully invested). Four portfolios are reported: equal-weight (the naïve choice), min-variance, max-Sharpe (using the average risk-free rate over the period), and risk-parity (equal contribution to portfolio variance)."));

// Analysis
children.push(h1("Analysis"));
children.push(h2("Relationship comparison"));
children.push(p("Unlike last year's S&P 500 stocks — which all correlated above 0.69 with each other and above 0.83 with the index — the five GSE stocks show much weaker pairwise relationships, ranging from near-zero to roughly 0.35. This reflects two structural features: the GSE-CI is dominated by a small number of large constituents (so individual stocks correlate weakly with the index unless they themselves are the dominant constituent), and the exchange's thin trading produces nominally low correlations because asynchronous price moves dampen pairwise covariance. The richer diversification implied here is partly an artifact of the latter."));
children.push(...fig("fig01_correlation_baseline.png", "Figure 1: Daily-return correlation matrix, baseline five stocks plus GSE Composite Index, 2016–2026."));

children.push(...fig("fig03_liquidity.png", "Figure 2: Liquidity diagnostics. Left: share of trading days with zero recorded volume (lower = more liquid). Right: average volume on active days (log scale). MTN is dramatically more liquid than the others; BOPP and GGBL barely trade."));

children.push(h2("Performance comparison"));
children.push(p("The cumulative wealth curve diverges decisively in BOPP's favour during 2021 and again in 2025. The equal-weighted portfolio ends the period at GHS 1.30 million from a GHS 100,000 start, a 12.97× multiple. The GSE Composite Index ends at GHS 737,000 (7.37×). Most of the gap is BOPP."));
children.push(...fig("fig05_portfolio_vs_index.png", "Figure 3: Portfolio vs GSE Composite Index, GHS 100,000 initial investment, no rebalancing."));
children.push(...fig("fig06_single_stock_wealth.png", "Figure 4: Per-stock cumulative wealth, GHS 100,000 each at the first available trading day (log scale). BOPP at 33× dominates; MTN starts later and reaches 7× from its 2018 IPO base."));

children.push(h2("Risk-adjusted returns"));
children.push(p("Table 1 summarises the headline risk-adjusted metrics. All figures use the time-varying BoG 91-day T-bill as the risk-free rate."));

children.push(buildTable([
  ["Metric", "Portfolio (EW)", "GSE-CI", "Δ"],
  ["Total return", "1,197%", "637%", "+560 pp"],
  ["CAGR", "29.7%", "22.5%", "+7.2 pp"],
  ["Annualised volatility", "30.8%", "13.7%", "+17.1 pp"],
  ["Sharpe ratio (TV RFR)", "0.41", "0.26", "+0.15"],
  ["Sortino ratio", "0.82", "0.44", "+0.38"],
  ["Calmar ratio", "0.47", "0.47", "≈ 0"],
  ["Max drawdown", "−62.7%", "−48.2%", "−14.5 pp"],
  ["Max DD duration (days)", "946", "941", "+5"],
  ["1-day 95% VaR", "−0.71%", "−1.03%", "+0.32 pp"],
  ["1-day 95% CVaR", "−2.19%", "−1.92%", "−0.27 pp"],
], [3000, 2200, 2200, 1960]));
children.push(p("Table 1: Performance and risk-adjusted return metrics for the equal-weighted portfolio versus the GSE Composite Index, 2016-05-23 to 2026-03-31.", { run: { italics: true, size: 18 } }));

children.push(...fig("fig07_rolling_sharpe_vol.png", "Figure 5: Rolling 1-year Sharpe ratio (top) and annualised volatility (bottom). The portfolio's Sharpe is consistently higher than the index's after 2020, but both swing sharply, including extended periods below zero during the 2018–2020 GSE downturn and the 2022 cedi/inflation crisis."));
children.push(...fig("fig08_drawdown.png", "Figure 6: Drawdown from running peak. The portfolio's max drawdown of −63% in 2018–2020 is materially deeper than the index's −48% over the same window."));

children.push(h2("Significance of outperformance"));
children.push(p("The cumulative-return picture is striking, but the underlying daily-return distribution does not support a confident claim of skill or repeatable edge. Resampling the daily excess-return series 5,000 times produces an annualised mean excess return of 9.2 percentage points with a 95% confidence interval of [−10.3%, 31.2%]. The two-sided p-value for the null of no outperformance is 0.38. The portfolio's edge is directionally positive over this particular ten-year window but cannot be statistically distinguished from luck."));
children.push(...fig("fig13_bootstrap.png", "Figure 7: Bootstrap distribution of annualised excess return over the GSE-CI. The observed value (red line) sits inside the bulk of the resampled null distribution centred near zero, yielding p = 0.38."));

children.push(h2("Portfolio optimisation"));
children.push(p("Long-only, fully invested mean-variance optimisation gives the unsurprising answer that, given BOPP's outsized realised return, a max-Sharpe portfolio loads ~72% into BOPP. This is the standard mean-variance overfitting problem: optimised weights are highly sensitive to realised-sample mean estimates, which are notoriously noisy. The min-variance and risk-parity portfolios (the latter not using expected-return estimates at all) give more defensible non-equal weights. Risk parity allocates roughly 25% / 26% / 20% / 21% / 8% to BOPP / GGBL / TOTAL / GOIL / GCB respectively — GCB receives the lowest weight because of its outsized 64% volatility."));
children.push(...fig("fig09_efficient_frontier.png", "Figure 8: Efficient frontier for the baseline five stocks, with the four candidate portfolios marked."));
children.push(...fig("fig10_optimisation_weights.png", "Figure 9: Portfolio weights under different objectives."));

children.push(h2("Rebalancing"));
children.push(p("Monthly and quarterly rebalancing to 20% targets produce essentially the same outcome (CAGR 32.9%, Sharpe 0.55), both ahead of buy-and-hold by ~3 CAGR points and ~0.04 Sharpe. The rebalancing benefit comes from systematically trimming BOPP after its strong years and reallocating into the lagging stocks. With zero transaction cost assumed, this gap is the upper bound on the rebalancing benefit; real-world GSE transaction costs of ~0.5%–1.0% per trade would meaningfully erode it."));
children.push(...fig("fig11_rebalancing.png", "Figure 10: Buy-and-hold, monthly-rebalanced, and quarterly-rebalanced portfolios vs the GSE-CI. Zero transaction cost assumed."));

children.push(h2("Inflation- and FX-adjusted views"));
children.push(p("The nominal-cedi return story flatters considerably under inflation and FX adjustment. Deflating by the Ghana CPI (rebased to 2016 = 1.0) cuts the portfolio's CAGR from 29.7% to 12.3% in real terms, and the GSE-CI's from 22.5% to 6.0%. The 2022 inflation spike (CPI +54% YoY in December 2022) and the parallel cedi depreciation are responsible for the bulk of this gap. In USD terms (using daily GHS/USD), the portfolio's CAGR is 17.0% and the index's 10.5% — competitive with global benchmarks for the period, but still meaningfully below the S&P 500 portfolio's 49% CAGR in last year's deck."));
children.push(...fig("fig12_macro_adjusted.png", "Figure 11: Macro-adjusted wealth paths. Top: real (CPI-deflated) GHS wealth. Bottom: USD-translated wealth."));

children.push(h2("MTN scenarios"));
children.push(p("Scenario A — adding MTN as a sixth equal-weighted holding (16.67% each) from its 2018-09-05 IPO — is near-neutral relative to the five-stock baseline measured over the same post-IPO window (CAGR 29.6% vs 29.5%). MTN's individual CAGR of 29.8% from IPO is roughly equal to the baseline portfolio's, so adding it as a sixth equal-weighted slice neither helps nor hurts materially."));
children.push(...fig("fig14_mtn_scenario_a.png", "Figure 12: MTN Scenario A — six-stock equal-weight portfolio starting at MTN's IPO."));

children.push(p("Scenario B — swapping out the worst pre-IPO performer (TOTAL, with a 13.2% cumulative return from May 2016 to Sep 2018) and reallocating that capital into MTN at the IPO date — is also near-neutral. The swap portfolio ends at 12.91× initial vs the baseline's 12.97×. The intuition is straightforward in hindsight: TOTAL underperformed in 2016–2018 but went on to deliver +25% in 2023 and +41% in 2025, so removing it actually hurt. The implicit lesson is the standard one against naïve momentum-chasing: past three-year underperformance is not a reliable signal of future underperformance."));
children.push(...fig("fig15_mtn_scenario_b.png", "Figure 13: MTN Scenario B — swap TOTAL for MTN at the IPO date."));

children.push(h2("Year-by-year attribution"));
children.push(p("Decomposing each year's portfolio return into per-stock contributions (assuming annual rebalancing to 20%) highlights two patterns. First, the portfolio's outperformance is concentrated in three years: 2017 (+96%), 2021 (+92%), and 2025 (+132%). Second, 2019 and 2020 were back-to-back loss years (−23% each) where every stock contributed negatively. The 2025 spike is broadly distributed across BOPP, TOTAL, and GCB — not just a single name."));
children.push(...fig("fig16_yearly_attribution.png", "Figure 14: Yearly per-stock contribution to portfolio return (annual rebalance to 20%)."));

// Discussion
children.push(h1("Discussion"));
children.push(h2("Interpretation"));
children.push(p("The headline result mirrors last year's S&P 500 finding directionally: an equal-weighted bet on the GSE's recognised names returned roughly twice the index over the decade, with a 60% higher Sharpe ratio. The mechanism is the same — one stock (BOPP here, NVIDIA there) drives most of the alpha. The Ghanaian version, however, comes with three caveats not present in the US version."));
children.push(p("First, the GSE has structurally thin trading for a number of names. BOPP and GGBL transact on barely a third of trading days, and individual GSE daily-bulletin records on the same date can disagree — typically a low/zero-volume placeholder paired with the actual traded VWAP. Our cleaning pipeline picks the higher-volume row in those duplicate-date cases, which is the correct choice but does mean the daily-return path has occasional large jumps reflecting these data-reconciliation events rather than market moves. The portfolio's 30.8% annualised volatility partly reflects this."));
children.push(p("Second, the outperformance is not statistically significant at conventional thresholds. The bootstrap p-value of 0.38 means there is roughly a 38% chance of observing a portfolio-vs-index excess return at least as extreme as the one observed under the null of no edge. Reasonable people can read this as either 'cumulative chart looks great but I can't prove it's repeatable' or as 'this is exactly the kind of weak-evidence story that should not drive an investment decision' — both are defensible."));
children.push(p("Third, the real (inflation-adjusted) returns are far less dramatic. A 29.7% nominal CAGR sounds spectacular, but 12.3% real after CPI is in line with what a well-diversified emerging-market equity portfolio has historically delivered. The 2022 cedi/inflation crisis was particularly punishing — both the portfolio and the index lost meaningful real ground that year despite nominal stability."));
children.push(h2("Limitations"));
children.push(bullet("The analysis covers a single ten-year window and cannot speak to longer-run performance. The pre-2016 GSE-CI data was not available for this study."));
children.push(bullet("Stale-pricing bias in BOPP and GGBL inflates measured Sharpe; we report the metric but should treat it as an upper bound."));
children.push(bullet("Transaction costs are excluded from the rebalancing scenarios. Real-world GSE costs would erode the ~3 pp CAGR benefit of monthly rebalancing."));
children.push(bullet("Macro covariates (T-bill, CPI, FX) are observed monthly and interpolated to daily; the analysis is robust to this for portfolio-level metrics but daily Sharpe values could shift modestly under different alignment choices."));
children.push(bullet("The five stocks chosen are not a passive 'top-five by market cap' — they were specified by the analyst. Conclusions are conditional on this selection."));
children.push(bullet("There is no out-of-sample test. All optimisation results use the same realised sample they were fit to."));

// Conclusion
children.push(h1("Conclusion"));
children.push(p("Over 2016–Q1 2026 an equal-weighted buy-and-hold portfolio of BOPP, GGBL, TOTAL, GOIL, and GCB outperformed the GSE Composite Index by roughly 560 percentage points cumulative and 7 CAGR points, with a 60% higher Sharpe ratio. The outperformance is driven primarily by BOPP, mirrors the single-stock dominance seen in last year's S&P 500 deck, and is not statistically distinguishable from sampling noise at conventional thresholds. Inflation- and FX-adjusted views compress the headline numbers substantially. Adding MTN as a sixth holding from its 2018 IPO does not materially change the picture under either scenario tested."));

// Recommendations
children.push(h1("Recommendations"));
children.push(bullet("For ordinary Ghanaian investors: a low-cost broad GSE exposure remains a defensible default. The active-pick portfolio delivered higher nominal returns over this decade but with materially deeper drawdowns (−63% vs −48%) and no statistical proof of repeatable edge."));
children.push(bullet("For experienced investors who do want to hold a concentrated GSE basket: equal-weighting is a poor starting point given the highly different volatilities across names. Risk parity (which does not rely on noisy expected-return estimates) is a more defensible default and naturally down-weights the GCB-style high-vol bank exposure."));
children.push(bullet("For all investors: focus on real returns, not nominal. Ghana's inflation regime has shifted multiple times in the period studied; a nominal CAGR figure can be highly misleading."));
children.push(bullet("For research extensions: (i) extend the window backward when pre-2016 GSE-CI data becomes available; (ii) develop a stale-pricing correction (e.g. Dimson 1979 adjustment) for the Sharpe ratios of BOPP and GGBL; (iii) add a transaction-cost overlay for the rebalancing comparison."));

// References
children.push(h1("References"));
children.push(bullet("Bank of Ghana, Summary of Economic and Financial Data (September 2017, November 2020, January 2022, July 2022, January 2024, July 2024, January 2026). bog.gov.gh/monetary-policy/summary-of-economic-and-financial-data."));
children.push(bullet("Ghana Statistical Service, Consumer Price Index Bulletins. statsghana.gov.gh."));
children.push(bullet("Ghana Stock Exchange, Daily Share Trading Reports (2016–2026)."));
children.push(bullet("afx.kwayisi.org, GSE daily price data archive."));
children.push(bullet("Sharpe, W. F. (1966). 'Mutual Fund Performance.' Journal of Business, 39(1), 119–138."));
children.push(bullet("Dimson, E. (1979). 'Risk Measurement when Shares are Subject to Infrequent Trading.' Journal of Financial Economics, 7(2), 197–226."));

// Appendix
children.push(h1("Appendix A — Reproducibility"));
children.push(p("All analysis code, data, and figures are provided alongside this report under /analysis."));
children.push(bullet("data/prices.csv — wide-format daily VWAP closing prices for the six stocks plus GSE-CI."));
children.push(bullet("data/volumes.csv — corresponding daily share volumes."));
children.push(bullet("data/macro.csv — daily BoG 91-day T-bill rate, Ghana CPI (rebased 2021 = 100), and USD/GHC mid-rate."));
children.push(bullet("code/01_clean_prices.py — builds prices.csv and volumes.csv from the raw GSE per-stock CSVs."));
children.push(bullet("code/02_build_macro.py — builds macro.csv from the BoG bulletins."));
children.push(bullet("code/lib.py — analysis helpers (returns, metrics, optimisation, bootstrap)."));
children.push(bullet("code/03_analyze.py — end-to-end analysis script that produces every figure and the multi-sheet statistics.xlsx."));
children.push(bullet("code/04_notebook.ipynb — narrative notebook version of the same analysis."));
children.push(bullet("outputs/figures/ — the 17 figures used in this report."));
children.push(bullet("outputs/statistics.xlsx — multi-sheet workbook with every numeric table."));

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } }, // 11pt
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Calibri", color: "1F4EA8" },
        paragraph: { spacing: { before: 320, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: "333333" },
        paragraph: { spacing: { before: 220, after: 140 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "GSE Investment Strategy Analysis — Page ", size: 18 }),
          new TextRun({ children: [PageNumber.CURRENT], size: 18 }),
        ],
      })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`Wrote ${OUT} (${buf.length.toLocaleString()} bytes)`);
});
