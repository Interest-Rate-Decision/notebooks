"""Writes the three notebooks from the cells below, with nbformat.

Edit the cells here, not in the .ipynb files, then:

    python scripts/build_notebooks.py
    jupyter nbconvert --to notebook --execute --inplace 0*.ipynb   # runs them on the synthetic sample
"""

import os

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "Interest-Rate-Decision/notebooks"
IRD = "https://interestratedecision.com"
V = "?via=notebooks"


def colab(name):
    return (
        f"[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]"
        f"(https://colab.research.google.com/github/{REPO}/blob/main/{name})"
    )


FOOTER = (
    "---\n\n"
    f"Decisions from [InterestRateDecision.com]({IRD}/{V}) (free to reuse with a link). "
    f"The method: [how the site measures a reaction]({IRD}/about/{V}#method). "
    f"The studies: [how often central banks surprise]({IRD}/blog/how-often-do-central-banks-surprise/{V}), "
    f"[the most volatile forex news]({IRD}/blog/most-volatile-forex-news/{V}), "
    f"[how to trade FOMC]({IRD}/blog/how-to-trade-fomc/{V}), "
    f"[can central bank decisions be predicted?]({IRD}/blog/can-central-bank-decisions-be-predicted/{V}). "
    f"Learn to test and trade the news: [Forexia's courses](https://forexiapro.com/courses{V}).\n\n"
    "Not financial advice. Past reactions say nothing certain about the next one.\n\n"
    f"Part of the Forexia network: [InterestRateDecision.com]({IRD}/{V}) · "
    f"[Forexia Academy](https://forexiapro.com/courses{V}) · "
    f"[TradingSignalBot](https://tradingsignalbot.com/{V}) · "
    "[PropSim](https://github.com/PropSim-Enterprise) · "
    "[OpenCharts](https://github.com/dylanpersonguy/OpenCharts)"
)

SETUP = '''\
# On Colab or Kaggle, fetch the repository first: the helper module and the synthetic sample.
import os, subprocess, sys
if not os.path.exists("ird_events.py"):
    if not os.path.exists("notebooks-repo"):
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/Interest-Rate-Decision/notebooks.git", "notebooks-repo"], check=True)
    os.chdir("notebooks-repo")
sys.path.insert(0, os.getcwd())

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import ird_events as ird'''

CONFIG = '''\
SAMPLE = True                    # True: synthetic candles from data/sample, offline. False: your own downloads.
CANDLES_DIR = "candles"          # scripts/download_candles.py writes candles/<PAIR>/*.csv
BANKS = ["fed", "ecb", "boe"]    # any of: fed ecb boe boj boc rba rbnz snb norges riksbank
SINCE = "2015-01-01"             # IRD's decisions go back to 2008

ird.banner(SAMPLE)
decisions = ird.load_decisions(sample=SAMPLE)
decisions = decisions[decisions.bank.isin(BANKS) & (decisions.time_utc >= pd.Timestamp(SINCE, tz="UTC"))]
candles = {
    pair: ird.load_sample_candles(pair) if SAMPLE else ird.load_candles(pair, CANDLES_DIR)
    for pair in decisions.pair.dropna().unique()
}
print(len(decisions), "decisions;", {pair: len(c) for pair, c in candles.items()}, "one-minute candles")'''

GET_CANDLES = f"""\
### Candles: download your own

Dukascopy's candles are not ours to share, so this repository ships none (only a synthetic sample). Two ways to get them:

1. **The `dukascopy-node` CLI** (needs Node.js): `python scripts/download_candles.py --banks fed ecb --since 2020-01-01` runs
   `npx dukascopy-node -i eurusd -from ... -to ... -t m1 -f csv` for the hours around each decision and writes `candles/EURUSD/`.
   Add `--dry-run` to see the commands first.
2. **By hand** from Dukascopy's historical data export (one-minute, bid, GMT): save each CSV in `candles/<PAIR>/`.

`ird.read_candle_csv` reads both formats. Then set `SAMPLE = False` below.
"""

# ---------------------------------------------------------------------------

EVENT_STUDY = [
    new_markdown_cell(
        f"""\
# How does a pair react to a central bank decision? An event study

{colab("01-event-study.ipynb")}

Each bank's decisions on the pair [InterestRateDecision.com]({IRD}/{V}) measures it on (the Fed and the ECB on EUR/USD,
the BoE on GBP/USD, the BoJ on USD/JPY...): the path of price from **three hours before** each announcement to
**five hours after**, in pips from the last close before it, averaged by what the bank did: **hike, hold or cut**.

Paths are turned so that **up means the bank's currency rose**: for the Fed on EUR/USD, a falling EUR/USD is a rising dollar.
Pips only compare within one pair: a pip on EUR/NOK is a tenth of the size of one on EUR/USD.

{GET_CANDLES}"""
    ),
    new_code_cell(SETUP),
    new_code_cell(CONFIG),
    new_markdown_cell("## The path of each decision\n\nOne row per decision, one column per minute from −180 to +299."),
    new_code_cell(
        '''\
paths, rows = [], []
for d in decisions.itertuples():
    info = ird.BANKS[d.bank]
    p = ird.path_in_pips(candles[d.pair], d.time_utc, d.pair, info["side"])
    if p is None:
        continue  # no candles for this one: not downloaded, or a gap
    paths.append(p.rename((d.bank, d.date)))
    rows.append({"bank": d.bank, "date": d.date, "move": d.move, "change_bp": d.change_bp})
paths = pd.DataFrame(paths)
meta = pd.DataFrame(rows)
print(len(paths), "of", len(decisions), "decisions have candles")
meta.groupby(["bank", "move"]).size().unstack(fill_value=0)'''
    ),
    new_markdown_cell("## The average path, by bank and by move"),
    new_code_cell(
        '''\
moves = {"hike": "tab:red", "hold": "tab:gray", "cut": "tab:blue"}
banks = list(meta.bank.unique())
fig, axes = plt.subplots(len(banks), 1, figsize=(10, 3.4 * len(banks)), squeeze=False)
for ax, bank in zip(axes[:, 0], banks):
    for move, colour in moves.items():
        mask = (meta.bank == bank) & (meta.move == move)
        if mask.sum() == 0:
            continue
        ax.plot(paths.columns, paths[mask.to_numpy()].mean(), color=colour, label=f"{move} (n={mask.sum()})")
    ax.axvline(0, color="black", lw=0.8)
    ax.axhline(0, color="black", lw=0.5, alpha=0.4)
    ax.set_title(f"{ird.BANKS[bank]['name']} on {ird.BANKS[bank]['pair']}: average path, pips (up = {ird.BANKS[bank]['currency']} stronger)")
    ax.set_xlabel("minutes from the announcement")
    ax.legend(loc="upper left")
fig.tight_layout()
plt.show()'''
    ),
    new_markdown_cell(
        "## At set times\n\nMean and median in pips at a few minutes, and how many decisions each figure counts. "
        "Medians are steadier: one big surprise moves a mean."
    ),
    new_code_cell(
        '''\
at = [-60, -15, 1, 5, 15, 60, 240]
table = paths[at].copy()
table.insert(0, "move", meta.move.to_numpy())
table.insert(0, "bank", meta.bank.to_numpy())
grouped = table.groupby(["bank", "move"])
summary = grouped[at].agg(["mean", "median"]).round(1)
summary[("n", "")] = grouped.size()
summary'''
    ),
    new_markdown_cell("## How spread out it is\n\nThe average hides the spread: here every path of one bank, with the median on top."),
    new_code_cell(
        '''\
bank = banks[0]
mask = (meta.bank == bank).to_numpy()
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(paths.columns, paths[mask].T, color="tab:gray", alpha=0.25, lw=0.8)
ax.plot(paths.columns, paths[mask].median(), color="black", lw=2, label="median")
ax.axvline(0, color="black", lw=0.8)
ax.set_title(f"Every {ird.BANKS[bank]['name']} decision, pips (up = {ird.BANKS[bank]['currency']} stronger)")
ax.set_xlabel("minutes from the announcement")
ax.legend()
plt.show()'''
    ),
    new_markdown_cell(
        "## Reading it\n\n"
        "- The move a bank makes is usually expected: a cut that everyone expected can lift the bank's currency. "
        "What moves price is the gap between the decision and what was expected (notebook 02) and what the bank says.\n"
        "- The minutes after the announcement are where the spread is widest and fills are worst. "
        "Notebook 03 looks at them the way InterestRateDecision.com does: the hour before, the first spike, the close back.\n"
        "- A few decisions per bank and move is a small sample: read the `n` column before the line.\n\n" + FOOTER
    ),
]

# ---------------------------------------------------------------------------

SURPRISE = [
    new_markdown_cell(
        f"""\
# The surprise against the reaction

{colab("02-surprise-vs-reaction.ipynb")}

Does the pair move more when the decision is further from what was expected? The surprise is
**actual minus consensus**: a positive surprise is hawkish (a higher rate than expected).

**The consensus is not in InterestRateDecision.com's open data.** The site shows it on each decision's page, from
FXStreet's calendar, but that figure is not ours to redistribute, so `decisions.csv` has the decision and the rate only.
This notebook gives you two choices:

1. **Your own consensus** (best): a file `consensus.csv` with the columns `bank,date,consensus` (the expected rate in percent,
   from a poll or calendar you are allowed to use). The surprise is then `(rate − consensus) × 100` basis points.
2. **The move as a proxy** (what runs without it): the change against the previous rate, `change_bp`.
   **This is not a surprise.** Most moves are expected days ahead, so the proxy mixes the expected with the unexpected and
   will understate the link. Every chart says which one it uses.

The reaction is the move in pips 15 and 60 minutes after the announcement, turned so that **up means the bank's currency rose**.

{GET_CANDLES}"""
    ),
    new_code_cell(SETUP),
    new_code_cell(CONFIG),
    new_code_cell(
        '''\
CONSENSUS_FILE = "consensus.csv"  # bank,date,consensus  e.g.  fed,2026-09-16,3.75

if os.path.exists(CONSENSUS_FILE):
    consensus = pd.read_csv(CONSENSUS_FILE, dtype={"date": str})
    data = decisions.merge(consensus, on=["bank", "date"], how="inner")
    data["surprise_bp"] = ((data["rate"] - data["consensus"]) * 100).round(1)
    SURPRISE_LABEL = "surprise: actual − consensus, bp"
else:
    data = decisions.copy()
    data["surprise_bp"] = data["change_bp"]
    SURPRISE_LABEL = "PROXY: the move against the previous rate, bp (not a surprise)"
print(SURPRISE_LABEL, "|", len(data), "decisions")'''
    ),
    new_code_cell(
        '''\
rows = []
for d in data.itertuples():
    p = ird.path_in_pips(candles[d.pair], d.time_utc, d.pair, ird.BANKS[d.bank]["side"])
    if p is None:
        continue
    rows.append({"bank": d.bank, "date": d.date, "move": d.move, "surprise_bp": d.surprise_bp,
                 "pips15": p.loc[14], "pips60": p.loc[59]})
reactions = pd.DataFrame(rows)
reactions.head()'''
    ),
    new_markdown_cell("## Scatter, by bank\n\nEach dot is a decision; the line is a least-squares fit, drawn only with two different surprises or more."),
    new_code_cell(
        '''\
banks = list(reactions.bank.unique())
fig, axes = plt.subplots(1, len(banks), figsize=(5 * len(banks), 4), squeeze=False)
for ax, bank in zip(axes[0], banks):
    part = reactions[reactions.bank == bank]
    ax.scatter(part.surprise_bp, part.pips15, alpha=0.7)
    if part.surprise_bp.nunique() >= 2:
        slope, intercept = np.polyfit(part.surprise_bp, part.pips15, 1)
        xs = np.linspace(part.surprise_bp.min(), part.surprise_bp.max(), 2)
        ax.plot(xs, slope * xs + intercept, color="black", lw=1, label=f"{slope:.2f} pips per bp")
        ax.legend()
    ax.axhline(0, color="black", lw=0.5, alpha=0.4)
    ax.set_title(f"{ird.BANKS[bank]['name']} on {ird.BANKS[bank]['pair']}")
    ax.set_xlabel(SURPRISE_LABEL)
    ax.set_ylabel(f"pips after 15 minutes (up = {ird.BANKS[bank]['currency']} stronger)")
fig.tight_layout()
plt.show()'''
    ),
    new_markdown_cell("## The numbers\n\nCorrelation and slope per bank, and the average reaction for each size of surprise."),
    new_code_cell(
        '''\
def fit(part):
    if len(part) < 3 or part.surprise_bp.nunique() < 2:
        return pd.Series({"n": len(part), "corr15": np.nan, "slope15": np.nan, "corr60": np.nan})
    return pd.Series({
        "n": len(part),
        "corr15": part.surprise_bp.corr(part.pips15),
        "slope15": np.polyfit(part.surprise_bp, part.pips15, 1)[0],
        "corr60": part.surprise_bp.corr(part.pips60),
    })

print(SURPRISE_LABEL)
display(reactions.groupby("bank")[["surprise_bp", "pips15", "pips60"]].apply(fit).round(2).astype({"n": int}))
reactions.groupby(["bank", "surprise_bp"])[["pips15", "pips60"]].agg(["mean", "count"]).round(1)'''
    ),
    new_markdown_cell(
        "## Reading it\n\n"
        "- With the proxy, a flat line does not mean surprises do not matter: it means the move alone does not say much, "
        "because most moves were expected. Bring a consensus file for the real test.\n"
        "- The sign should be positive: a hawkish surprise lifts the bank's currency. When it is not, the statement, "
        "the press conference or the projections usually said more than the rate.\n"
        "- InterestRateDecision.com counts how often each bank surprised, decision by decision since 2008, in its "
        f"[study of surprises]({IRD}/blog/how-often-do-central-banks-surprise/{V}).\n\n" + FOOTER
    ),
]

# ---------------------------------------------------------------------------

HOUR_BEFORE = [
    new_markdown_cell(
        f"""\
# The hour before, the first spike and the close back

{colab("03-hour-before-range.ipynb")}

This is [InterestRateDecision.com's own measurement]({IRD}/about/{V}#method), rule for rule (the code in `ird_events.reaction_of`
gives the site's figures on the site's candles). The rules were set before any decision was counted:

| | |
|---|---|
| **the hour before** | the high and low of the 60 minutes before the announcement: the box |
| **the first side** | the edge of the box price trades through first, within 30 minutes |
| **the close back** | a five-minute candle (counted from the announcement) closing back inside the box within 60 minutes |
| **the other side** | after the close back, price trading through the opposite edge within four hours |

The read: the decision brings a burst of orders within a minute; the first spike runs the stops resting beyond one side
of the hour before (a stop hunt), and when it closes back inside, the move often belongs to the other side.
The counts below include every decision where the first spike did **not** close back: they say how often it happened,
and how often it did not.

{GET_CANDLES}"""
    ),
    new_code_cell(SETUP),
    new_code_cell(CONFIG),
    new_code_cell(
        '''\
rows, measured = [], {}
for d in decisions.itertuples():
    r = ird.reaction_of(candles[d.pair], d.time_utc, d.pair)
    if r is None:
        continue  # fewer than 20 candles in the hour before, or none after
    measured[(d.bank, d.date)] = r
    rows.append({"bank": d.bank, "date": d.date, "move": d.move, "box_pips": round(r.box_pips, 1),
                 "first": r.first, "first_at": r.first_at, "first_pips": None if r.first_pips is None else round(r.first_pips, 1),
                 "closed_back": r.closed_back, "closed_back_at": r.closed_back_at, "other_side": r.other_side})
table = pd.DataFrame(rows)
table.tail(10)'''
    ),
    new_markdown_cell("## How often, by bank"),
    new_code_cell(
        '''\
def counts(part):
    n = len(part)
    broke = part["first"].notna().sum()
    back = (part["closed_back"] == True).sum()
    other = (part["other_side"] == True).sum()
    return pd.Series({
        "decisions": n,
        "broke an edge": broke,
        "closed back": back,
        "closed back, % of broke": round(100 * back / broke, 1) if broke else np.nan,
        "reached the other side": other,
        "other side, % of closed back": round(100 * other / back, 1) if back else np.nan,
        "median hour-before range, pips": part["box_pips"].median(),
    })

tallies = table.groupby("bank").apply(counts, include_groups=False)
whole = ["decisions", "broke an edge", "closed back", "reached the other side"]
tallies.astype({c: int for c in whole})'''
    ),
    new_markdown_cell(
        "## One decision, drawn\n\nThe hour before as a band, the announcement as a line, and the close back when there was one. "
        "Change `PICK` to look at another."
    ),
    new_code_cell(
        '''\
PICK = -1  # the latest; or an index into table
row = table.iloc[PICK]
r = measured[(row.bank, row.date)]
part = ird.window_of(candles[r.pair], r.t0, before=90, after=240)
fig, ax = plt.subplots(figsize=(11, 4.5))
ax.vlines(part.minute, part.low, part.high, color="tab:gray", lw=0.8)
ax.plot(part.minute, part.close, color="black", lw=0.8)
ax.axhspan(r.box_low, r.box_high, xmin=0, xmax=1, color="tab:orange", alpha=0.15, label="the hour before")
ax.axvline(0, color="tab:red", lw=1, label="announcement")
if r.closed_back_at:
    ax.axvline(r.closed_back_at, color="tab:green", lw=1, ls="--", label=f"the close back (+{r.closed_back_at} min)")
ax.set_title(f"{ird.BANKS[row.bank]['name']}, {row.date}: first side {r.first or 'none'}, "
             f"closed back {r.closed_back}, other side {r.other_side}")
ax.set_xlabel("minutes from the announcement")
ax.legend(loc="upper left")
plt.show()'''
    ),
    new_markdown_cell(
        "## By move\n\nDoes the close back happen more often on holds than on hikes and cuts?"
    ),
    new_code_cell(
        '''\
broke = table[table["first"].notna()]
(broke.assign(closed_back=broke.closed_back == True, other_side=broke.other_side == True)
      .groupby(["bank", "move"])[["closed_back", "other_side"]]
      .agg(["mean", "count"]).round(2))'''
    ),
    new_markdown_cell(
        "## Reading it\n\n"
        "- The close back is a count, not a promise: the share that did not close back is in the same table.\n"
        "- The hour before is often narrow, so a first spike through it is almost certain; what differs between banks "
        "is how often the close back follows, and how often the other side is reached after it.\n"
        "- The site publishes the same counts for every bank with the latest candles, and draws each decision: "
        f"start at [the Fed's page]({IRD}/fed/{V}) or [how to trade FOMC]({IRD}/blog/how-to-trade-fomc/{V}).\n\n" + FOOTER
    ),
]


def write(name, cells):
    nb = new_notebook(cells=cells)
    for i, cell in enumerate(nb.cells):
        cell.id = f"{name[:2]}-{i:02d}"  # fixed ids, so a rebuild changes nothing it should not
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    nb.metadata["colab"] = {"provenance": []}
    nbformat.validate(nb)
    path = os.path.join(ROOT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        nbformat.write(nb, f)
    print("wrote", path)


if __name__ == "__main__":
    write("01-event-study.ipynb", EVENT_STUDY)
    write("02-surprise-vs-reaction.ipynb", SURPRISE)
    write("03-hour-before-range.ipynb", HOUR_BEFORE)
