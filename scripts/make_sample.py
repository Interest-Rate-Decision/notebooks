"""Writes the synthetic candles in data/sample/, so the notebooks run offline.

The decision times are real (data/sample/decisions.csv, from
InterestRateDecision.com's open data). The candles are NOT: a seeded random
walk with a spike at each announcement, which sometimes closes back inside the
hour before and sometimes runs on. They exist to show the code working; no
figure computed from them means anything.

Two formats, so both loaders are exercised:
  EURUSD: the dukascopy-node CLI's CSV (timestamp in epoch ms)
  GBPUSD: Dukascopy's website export (Gmt time as DD.MM.YYYY HH:MM:SS.mmm)

    python scripts/make_sample.py
"""

import csv
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ird_events import AFTER_MIN, BANKS, BEFORE_MIN, SAMPLE_DIR, load_decisions, pip_size  # noqa: E402

START_PRICE = {"EURUSD": 1.10000, "GBPUSD": 1.30000}
TICKS = 6  # sub-steps per minute, for highs and lows


def synthetic_window(rng, t0, pair, side, change_bp, start):
    pip = pip_size(pair)
    minutes = np.arange(-BEFORE_MIN, AFTER_MIN)
    # Quiet before, a burst at the announcement, calmer after.
    vol = np.where(minutes < 0, 0.35, 1.6 * np.exp(-np.maximum(minutes, 0) / 40) + 0.45)
    steps = rng.normal(0, 1, (len(minutes), TICKS)) * (vol[:, None] / np.sqrt(TICKS)) * pip

    # The spike: toward the move a little more often than against it, oriented for the pair.
    bank_dir = np.sign(change_bp) if change_bp else rng.choice([-1, 1])
    pair_dir = bank_dir if side == "base" else -bank_dir
    direction = pair_dir if rng.random() < 0.6 else -pair_dir
    size = rng.uniform(12, 35) * pip
    spike_len = int(rng.integers(1, 4))
    i0 = BEFORE_MIN
    steps[i0 : i0 + spike_len] += direction * size / (spike_len * TICKS)
    # Half the time the spike closes back, and sometimes runs on to the other side.
    if rng.random() < 0.5:
        back_len = int(rng.integers(8, 40))
        steps[i0 + spike_len : i0 + spike_len + back_len] -= direction * size * rng.uniform(0.8, 1.8) / (back_len * TICKS)

    path = start + np.cumsum(steps.ravel())
    ticks = path.reshape(len(minutes), TICKS)
    opens = np.concatenate([[start], ticks[:-1, -1]])
    highs = np.maximum(ticks.max(axis=1), opens)
    lows = np.minimum(ticks.min(axis=1), opens)
    closes = ticks[:, -1]
    times = [t0 + pd.Timedelta(minutes=int(m)) for m in minutes]
    return times, opens, highs, lows, closes


def main():
    rng = np.random.default_rng(20261102)
    decisions = load_decisions(sample=True)
    rows = {pair: [] for pair in START_PRICE}
    for d in decisions.itertuples():
        pair = BANKS[d.bank]["pair"]
        if pair not in rows:
            continue
        start = START_PRICE[pair] + rng.normal(0, 0.01)
        times, o, h, l, c = synthetic_window(rng, d.time_utc, pair, BANKS[d.bank]["side"], d.change_bp, start)
        rows[pair].extend(zip(times, o, h, l, c))

    os.makedirs(SAMPLE_DIR, exist_ok=True)
    with open(os.path.join(SAMPLE_DIR, "EURUSD_m1_SYNTHETIC.csv"), "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow(["timestamp", "open", "high", "low", "close"])
        for t, o, h, l, c in sorted(rows["EURUSD"]):
            out.writerow([int(t.timestamp() * 1000), f"{o:.5f}", f"{h:.5f}", f"{l:.5f}", f"{c:.5f}"])
    with open(os.path.join(SAMPLE_DIR, "GBPUSD_m1_SYNTHETIC.csv"), "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow(["Gmt time", "Open", "High", "Low", "Close", "Volume"])
        for t, o, h, l, c in sorted(rows["GBPUSD"]):
            out.writerow([t.strftime("%d.%m.%Y %H:%M:%S.000"), f"{o:.5f}", f"{h:.5f}", f"{l:.5f}", f"{c:.5f}", "0"])
    print({pair: len(r) for pair, r in rows.items()}, "synthetic candles written to", SAMPLE_DIR)


if __name__ == "__main__":
    main()
