"""Shared code for the notebooks: decisions, candles, and the reaction measurement.

Decisions come from InterestRateDecision.com's open data (free to reuse with a
link to https://interestratedecision.com). Candles are the one-minute candles
you download yourself from Dukascopy: this repository ships none, only a
synthetic sample so the notebooks run offline.

The measurement in `reaction_of` is InterestRateDecision.com's own, with the
rules set before any decision was counted (https://interestratedecision.com/about/#method):

    the hour before  the high and low of the 60 minutes before the announcement (the box)
    the first side   the box edge price trades through first, within 30 minutes
    the close back   a five-minute candle (counted from the announcement) closing
                     back inside the box within 60 minutes of it
    the other side   after the close back, price trading through the opposite
                     edge within four hours

The decision brings a burst of orders at one minute; the first spike runs the
stops beyond one side of the hour before (a stop hunt), and when it closes back
the move often belongs to the other side. Counted honestly: decisions where the
first spike did not close back are counted too.
"""

from __future__ import annotations

import glob
import io
import os
import urllib.request
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

IRD = "https://interestratedecision.com"
DECISIONS_URL = f"{IRD}/data/decisions.csv"
VIA = "?via=notebooks"

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(HERE, "data", "sample")
SAMPLE_DECISIONS = os.path.join(SAMPLE_DIR, "decisions.csv")

# The pair InterestRateDecision.com measures each bank's reaction on, and where
# the bank's currency sits in it: when it is the quote, the pair falls as the
# bank's currency rises.
BANKS = {
    "fed": {"name": "Federal Reserve", "currency": "USD", "pair": "EURUSD", "side": "quote"},
    "ecb": {"name": "European Central Bank", "currency": "EUR", "pair": "EURUSD", "side": "base"},
    "boe": {"name": "Bank of England", "currency": "GBP", "pair": "GBPUSD", "side": "base"},
    "boj": {"name": "Bank of Japan", "currency": "JPY", "pair": "USDJPY", "side": "quote"},
    "boc": {"name": "Bank of Canada", "currency": "CAD", "pair": "USDCAD", "side": "quote"},
    "rba": {"name": "Reserve Bank of Australia", "currency": "AUD", "pair": "AUDUSD", "side": "base"},
    "rbnz": {"name": "Reserve Bank of New Zealand", "currency": "NZD", "pair": "NZDUSD", "side": "base"},
    "snb": {"name": "Swiss National Bank", "currency": "CHF", "pair": "USDCHF", "side": "quote"},
    "norges": {"name": "Norges Bank", "currency": "NOK", "pair": "EURNOK", "side": "quote"},
    "riksbank": {"name": "Sveriges Riksbank", "currency": "SEK", "pair": "EURSEK", "side": "quote"},
}

MINUTE = pd.Timedelta(minutes=1)
BEFORE_MIN = 180  # three hours before, as on the site's decision pages
AFTER_MIN = 300  # five hours after


def pip_size(pair: str) -> float:
    """A pip: 0.01 on yen pairs, 0.0001 on the others (a krone or krona pip is small: compare in pips only on one pair)."""
    return 0.01 if "JPY" in pair else 0.0001


def move_of(change_bp: float) -> str:
    if change_bp > 0:
        return "hike"
    if change_bp < 0:
        return "cut"
    return "hold"


# ---------------------------------------------------------------------------
# Decisions


def load_decisions(sample: bool = False, path: Optional[str] = None) -> pd.DataFrame:
    """Every decision since 2008: bank, bank_name, time_utc, date, rate, change_bp, plus move.

    sample=True reads the copy in data/sample (offline). Otherwise `path`, or the live
    file at https://interestratedecision.com/data/decisions.csv.
    """
    source = SAMPLE_DECISIONS if sample else (path or DECISIONS_URL)
    if source.startswith("http"):
        request = urllib.request.Request(source, headers={"User-Agent": "ird-notebooks"})
        with urllib.request.urlopen(request, timeout=30) as response:
            source = io.StringIO(response.read().decode("utf-8"))
    frame = pd.read_csv(source)
    frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)
    frame["move"] = frame["change_bp"].map(move_of)
    frame["pair"] = frame["bank"].map(lambda b: BANKS.get(b, {}).get("pair"))
    return frame.sort_values("time_utc").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Candles


def _times(column: pd.Series) -> pd.Series:
    """Epoch milliseconds or seconds, ISO strings, or Dukascopy's export format (DD.MM.YYYY HH:MM:SS.mmm)."""
    if pd.api.types.is_numeric_dtype(column):
        unit = "ms" if column.abs().max() > 1e11 else "s"
        return pd.to_datetime(column, unit=unit, utc=True)
    text = column.astype(str).str.strip()
    if text.str.match(r"^\d{2}\.\d{2}\.\d{4}").all():
        return pd.to_datetime(text.str.replace(r"\s*GMT.*$", "", regex=True), format="%d.%m.%Y %H:%M:%S.%f", utc=True)
    return pd.to_datetime(text, utc=True, format="mixed")


def read_candle_csv(path_or_buffer) -> pd.DataFrame:
    """One CSV of one-minute candles, from either source:

    - the dukascopy-node CLI (`-f csv`): timestamp,open,high,low,close[,volume], timestamp in epoch ms
    - Dukascopy's website export: Gmt time,Open,High,Low,Close,Volume, time as DD.MM.YYYY HH:MM:SS.mmm
    - anything with a time column (time, timestamp, date, datetime, gmt time) and open, high, low, close

    Returns a frame indexed by UTC time with open, high, low, close.
    """
    frame = pd.read_csv(path_or_buffer)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    time_col = next((c for c in ("timestamp", "time", "gmt time", "datetime", "date", "local time") if c in frame.columns), None)
    if time_col is None:
        raise ValueError(f"no time column in {list(frame.columns)}")
    missing = {"open", "high", "low", "close"} - set(frame.columns)
    if missing:
        raise ValueError(f"missing columns {sorted(missing)}")
    frame.index = _times(frame[time_col])
    frame.index.name = "time"
    candles = frame[["open", "high", "low", "close"]].astype(float)
    return candles[~candles.index.duplicated(keep="last")].sort_index()


def load_candles(pair: str, directory: str = "candles") -> pd.DataFrame:
    """Every CSV in candles/<PAIR>/ (or candles/<PAIR>*.csv), joined and deduplicated."""
    files = sorted(glob.glob(os.path.join(directory, pair.upper(), "*.csv")))
    files += sorted(glob.glob(os.path.join(directory, f"{pair.upper()}*.csv")))
    files += sorted(glob.glob(os.path.join(directory, pair.upper(), "**", "*.csv"), recursive=True))
    files = sorted(set(files))
    if not files:
        return pd.DataFrame(columns=["open", "high", "low", "close"], index=pd.DatetimeIndex([], tz="UTC", name="time"))
    frame = pd.concat([read_candle_csv(f) for f in files])
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def load_sample_candles(pair: str) -> pd.DataFrame:
    """The synthetic sample: random-walk candles shaped like a decision. Not prices."""
    return load_candles(pair, SAMPLE_DIR)


def window_of(candles: pd.DataFrame, t0: pd.Timestamp, before: int = BEFORE_MIN, after: int = AFTER_MIN) -> pd.DataFrame:
    """The candles from `before` minutes before t0 to `after` minutes after it, with `minute` from t0."""
    part = candles[(candles.index >= t0 - before * MINUTE) & (candles.index < t0 + after * MINUTE)].copy()
    part["minute"] = ((part.index - t0) / MINUTE).astype(int)
    return part


# ---------------------------------------------------------------------------
# Event study


def path_in_pips(candles: pd.DataFrame, t0: pd.Timestamp, pair: str, side: str = "base") -> Optional[pd.Series]:
    """The close at each minute from -180 to +299, in pips from the last close before t0.

    Oriented for the bank's currency: positive means the bank's currency rose
    (the pair is flipped when the bank's currency is the quote).
    """
    part = window_of(candles, t0)
    before = part[part["minute"] < 0]
    if len(before) < 20 or (part["minute"] >= 0).sum() == 0:
        return None
    ref = before["close"].iloc[-1]
    sign = 1.0 if side == "base" else -1.0
    series = (part.set_index("minute")["close"] - ref) / pip_size(pair) * sign
    full = pd.RangeIndex(-BEFORE_MIN, AFTER_MIN)
    return series.reindex(full).ffill()


# ---------------------------------------------------------------------------
# The hour before and the close back: InterestRateDecision.com's measurement


@dataclass
class Reaction:
    pair: str
    t0: pd.Timestamp
    box_high: float
    box_low: float
    box_pips: float
    first: Optional[str]  # "up", "down" or None (no edge traded through in 30 minutes)
    first_at: Optional[int]  # minutes after the announcement
    first_pips: Optional[float]  # how far past the box the first spike reached
    closed_back: Optional[bool]
    closed_back_at: Optional[int]  # minutes after the announcement
    other_side: Optional[bool]
    spike_up: float  # largest move up from the last close before, within 15 minutes, pips
    spike_down: float
    move15: Optional[float]  # close 15 minutes after, from the last close before, pips
    move60: Optional[float]
    move240: Optional[float]


def reaction_of(candles: pd.DataFrame, t0: pd.Timestamp, pair: str) -> Optional[Reaction]:
    """The measurement, rule for rule as InterestRateDecision.com's (src/lib/reaction.ts).

    `candles` are one-minute candles indexed by their opening time (UTC).
    Returns None with fewer than 20 candles in the hour before or none after.
    """
    pip = pip_size(pair)
    t0 = pd.Timestamp(t0)
    before = candles[(candles.index >= t0 - 60 * MINUTE) & (candles.index < t0)]
    after = candles[candles.index >= t0]
    if len(before) < 20 or len(after) == 0:
        return None
    pre_close = float(before["close"].iloc[-1])
    box_high = float(before["high"].max())
    box_low = float(before["low"].min())
    minutes = ((after.index - t0) / MINUTE).to_numpy()
    highs, lows, closes = after["high"].to_numpy(), after["low"].to_numpy(), after["close"].to_numpy()

    def at(m: int) -> Optional[float]:
        idx = np.nonzero(minutes < m)[0]
        if len(idx) == 0 or minutes[idx[-1]] < m - 5:
            return None
        return (closes[idx[-1]] - pre_close) / pip

    first15 = minutes < 15
    spike_up = max(0.0, float(((highs[first15] - pre_close) / pip).max(initial=0)))
    spike_down = max(0.0, float(((pre_close - lows[first15]) / pip).max(initial=0)))

    # The first side: the first one-minute candle through an edge, within 30 minutes.
    first, first_at, break_idx = None, None, -1
    for i in range(len(after)):
        if minutes[i] >= 30:
            break
        up, down = highs[i] - box_high, box_low - lows[i]
        if up > 0 or down > 0:
            first = "up" if up >= down else "down"  # through both edges in one minute: the bigger run is the spike
            first_at, break_idx = int(round(minutes[i])), i
            break

    closed_back = closed_back_at = other_side = first_pips = None
    if first:
        # Five-minute candles counted from the announcement; the close of each is its last minute's close.
        bins = np.floor(minutes / 5).astype(int)
        start_bin = int(bins[break_idx])
        closed_back, back_time = False, None
        for k in range(start_bin, 12):
            in_bin = np.nonzero(bins == k)[0]
            if len(in_bin) == 0:
                continue
            close = closes[in_bin[-1]]
            if (close < box_high) if first == "up" else (close > box_low):
                closed_back, closed_back_at = True, (k + 1) * 5
                back_time = (k + 1) * 5
                break
        spike = minutes < (back_time if closed_back else 60)
        extreme = highs[spike].max() if first == "up" else lows[spike].min()
        first_pips = abs(extreme - (box_high if first == "up" else box_low)) / pip
        if closed_back:
            later = (minutes >= back_time) & (minutes < 240)
            other_side = bool((lows[later] < box_low).any() if first == "up" else (highs[later] > box_high).any())

    return Reaction(
        pair=pair,
        t0=t0,
        box_high=box_high,
        box_low=box_low,
        box_pips=(box_high - box_low) / pip,
        first=first,
        first_at=first_at,
        first_pips=first_pips,
        closed_back=closed_back,
        closed_back_at=closed_back_at,
        other_side=other_side,
        spike_up=spike_up,
        spike_down=spike_down,
        move15=at(15),
        move60=at(60),
        move240=at(240),
    )


def tally(reactions: list) -> dict:
    """How often: n measured, broke an edge, closed back, reached the other side; median box and spike in pips."""
    rs = [r for r in reactions if r is not None]
    return {
        "n": len(rs),
        "broke": sum(1 for r in rs if r.first),
        "closed_back": sum(1 for r in rs if r.closed_back),
        "other_side": sum(1 for r in rs if r.other_side),
        "median_box_pips": float(np.median([r.box_pips for r in rs])) if rs else 0.0,
        "median_spike_pips": float(np.median([max(r.spike_up, r.spike_down) for r in rs])) if rs else 0.0,
    }


def banner(sample: bool) -> None:
    if sample:
        print(
            "SAMPLE MODE: the candles are synthetic (a random walk shaped like a decision), "
            "so every figure below is meaningless. Set SAMPLE = False and download candles to study real decisions."
        )
    else:
        print("Decisions from InterestRateDecision.com (https://interestratedecision.com/?via=notebooks); candles your own.")
