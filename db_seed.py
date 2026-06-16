"""Seed the SQLite database from existing flat files (CSV + JSONL).

Run once: python db_seed.py
Idempotent: skips each table if it already has rows.
"""

import json
import os
import pandas as pd
from datetime import date as date_type
from sqlalchemy.orm import Session

from config import COINS, CATEGORY_MAP, DATE_FROM, DATE_TO
from models import Cryptocurrency, PriceHistory, EventCategory, Event, get_engine, init_db

EVENTS_FILE = os.path.join(os.path.dirname(__file__), "events.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

ALL_CATEGORIES = sorted(set(CATEGORY_MAP.values()) | {"Inne"})


def seed_cryptocurrencies(session: Session) -> dict[str, int]:
    if session.query(Cryptocurrency).count() > 0:
        print("  cryptocurrencies: already seeded, skipping.")
        return {c.symbol: c.id for c in session.query(Cryptocurrency).all()}

    rows = [Cryptocurrency(symbol=ticker, name=coin_id) for coin_id, ticker in COINS]
    session.add_all(rows)
    session.flush()
    print(f"  cryptocurrencies: inserted {len(rows)} rows.")
    return {c.symbol: c.id for c in rows}


def seed_prices(session: Session, crypto_ids: dict[str, int]) -> None:
    if session.query(PriceHistory).count() > 0:
        print("  price_history: already seeded, skipping.")
        return

    mappings = []
    for coin_id, ticker in COINS:
        path = os.path.join(DATA_DIR, f"{coin_id}_prices.csv")
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found, skipping {ticker}.")
            continue
        df = pd.read_csv(path, parse_dates=["date"])
        cid = crypto_ids[ticker]
        for row in df.itertuples(index=False):
            mappings.append({
                "crypto_id": cid,
                "date": row.date.date() if hasattr(row.date, "date") else row.date,
                "price": float(row.price),
            })

    session.bulk_insert_mappings(PriceHistory, mappings)
    print(f"  price_history: inserted {len(mappings)} rows.")


def seed_events(session: Session) -> None:
    if session.query(EventCategory).count() > 0:
        print("  event_categories / events: already seeded, skipping.")
        return

    # Insert categories
    cat_rows = [EventCategory(name=name) for name in ALL_CATEGORIES]
    session.add_all(cat_rows)
    session.flush()
    cat_id_by_name = {c.name: c.id for c in cat_rows}

    date_from = pd.Timestamp(DATE_FROM)
    date_to = pd.Timestamp(DATE_TO)

    mappings = []
    with open(EVENTS_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            date_str = obj.get("date", "")
            if not date_str:
                continue
            ts = pd.to_datetime(date_str, errors="coerce")
            if pd.isnull(ts) or ts < date_from or ts > date_to:
                continue

            raw_cat = (obj.get("category") or "").strip().upper()
            cat_name = CATEGORY_MAP.get(raw_cat, "Inne")

            mappings.append({
                "title": obj.get("headline") or "",
                "description": obj.get("short_description") or "",
                "date": ts.date(),
                "category_id": cat_id_by_name[cat_name],
            })

    session.bulk_insert_mappings(Event, mappings)
    print(f"  event_categories: inserted {len(cat_rows)} rows.")
    print(f"  events: inserted {len(mappings)} rows.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed crypto database from flat files.")
    parser.add_argument(
        "--pg",
        metavar="CONN_STR",
        default=None,
        help="PostgreSQL connection string, e.g. postgresql://user:pass@host/db. "
             "If omitted, seeds the local SQLite database.",
    )
    args = parser.parse_args()

    print("=== DB Seed ===")
    init_db(args.pg)
    engine = get_engine(args.pg)
    with Session(engine) as session:
        crypto_ids = seed_cryptocurrencies(session)
        seed_prices(session, crypto_ids)
        seed_events(session)
        session.commit()

    target = args.pg if args.pg else os.path.abspath(os.path.join(DATA_DIR, "crypto_events.db"))
    print("Gotowe! Baza danych:", target)


if __name__ == "__main__":
    main()
