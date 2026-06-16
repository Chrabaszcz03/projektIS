"""Load events.json (JSONL) and aggregate into daily category counts."""

import json
import os
import pandas as pd

from config import CATEGORY_MAP, DATE_FROM, DATE_TO

EVENTS_FILE = os.path.join(os.path.dirname(__file__), "events.json")


def load_events() -> pd.DataFrame:
    """
    Returns a DataFrame with columns:
        date       — datetime64
        category   — analysis category (str)
        count      — number of articles that day in that category
    """
    rows = []
    with open(EVENTS_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw_cat = (obj.get("category") or "").strip().upper()
            category = CATEGORY_MAP.get(raw_cat, "Inne")
            date_str = obj.get("date", "")
            if not date_str:
                continue
            rows.append({"date": date_str, "category": category})

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # Restrict to our analysis window
    df = df[(df["date"] >= pd.Timestamp(DATE_FROM)) & (df["date"] <= pd.Timestamp(DATE_TO))]

    # Aggregate: number of articles per (date, category)
    agg = (
        df.groupby(["date", "category"])
        .size()
        .reset_index(name="count")
    )
    agg = agg.sort_values("date").reset_index(drop=True)
    return agg
