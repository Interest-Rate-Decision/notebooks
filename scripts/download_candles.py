"""Downloads one-minute candles around each decision with the dukascopy-node CLI.

Dukascopy's data is not ours to redistribute, so the notebooks ship none: run
this on your own machine (it needs Node.js, for npx). It reads the decisions from
InterestRateDecision.com, and for each one asks dukascopy-node for the day or two
that cover three hours before to five hours after it, one CSV per decision:

    candles/EURUSD/fed-2026-09-16.csv

    python scripts/download_candles.py --banks fed ecb --since 2020-01-01
    python scripts/download_candles.py --banks boj --since 2024-01-01 --dry-run   # print the commands only

Files already there are skipped, so it can be run again after new decisions.
By hand instead: export one-minute bid candles in GMT from Dukascopy's
historical data page and save the CSVs in candles/<PAIR>/; the notebooks read both.
"""

import argparse
import os
import shutil
import subprocess
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ird_events import AFTER_MIN, BANKS, BEFORE_MIN, load_decisions  # noqa: E402


def command(pair, t0, directory, name):
    start = (t0 - pd.Timedelta(minutes=BEFORE_MIN)).strftime("%Y-%m-%d")
    end = (t0 + pd.Timedelta(minutes=AFTER_MIN) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    npx = shutil.which("npx") or "npx"
    return [
        npx, "--yes", "dukascopy-node",
        "-i", pair.lower(), "-from", start, "-to", end,
        "-t", "m1", "-f", "csv", "-p", "bid",
        "-dir", directory, "-fn", name,
        "-r", "2", "-s",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--banks", nargs="+", default=["fed"], choices=sorted(BANKS))
    parser.add_argument("--since", default="2020-01-01")
    parser.add_argument("--until", default=None, help="last date (default: today)")
    parser.add_argument("--dir", default="candles")
    parser.add_argument("--decisions", default=None, help="a local decisions.csv instead of the live one")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    decisions = load_decisions(path=args.decisions)
    now = pd.Timestamp.now(tz="UTC")
    until = pd.Timestamp(args.until, tz="UTC") if args.until else now
    chosen = decisions[
        decisions.bank.isin(args.banks)
        & (decisions.time_utc >= pd.Timestamp(args.since, tz="UTC"))
        & (decisions.time_utc <= until)
        & (decisions.time_utc + pd.Timedelta(minutes=AFTER_MIN) < now)
    ]
    print(f"{len(chosen)} decisions of {', '.join(args.banks)} since {args.since}")
    for d in chosen.itertuples():
        directory = os.path.join(args.dir, d.pair)
        name = f"{d.bank}-{d.date}"
        if os.path.exists(os.path.join(directory, f"{name}.csv")):
            continue
        cmd = command(d.pair, d.time_utc, directory, name)
        print(" ".join(cmd))
        if not args.dry_run:
            os.makedirs(directory, exist_ok=True)
            subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
