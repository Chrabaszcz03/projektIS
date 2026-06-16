"""Export/import for events (JSON, YAML), prices (XML), and analysis results (DB)."""

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

_DEFAULT_EVENTS_JSON = os.path.join(OUTPUT_DIR, "events_export.json")
_DEFAULT_EVENTS_YAML = os.path.join(OUTPUT_DIR, "events_export.yaml")
_DEFAULT_PRICES_XML  = os.path.join(OUTPUT_DIR, "prices_export.xml")



def export_events_json(events_daily: pd.DataFrame, path: str | None = None) -> str:
    path = path or _DEFAULT_EVENTS_JSON
    os.makedirs(os.path.dirname(path), exist_ok=True)

    records = [
        {"date": row.date.strftime("%Y-%m-%d"), "category": row.category, "count": int(row.count)}
        for row in events_daily.itertuples(index=False)
    ]
    payload = {
        "meta": {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "schema_version": 1,
        },
        "records": records,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"   [JSON] {len(records)} rekordów → {path}")
    return path


def import_events_json(path: str | None = None) -> pd.DataFrame:
    path = path or _DEFAULT_EVENTS_JSON
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)

    df = pd.DataFrame(payload["records"])
    df["date"]  = pd.to_datetime(df["date"])
    df["count"] = df["count"].astype("int64")
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# YAML – events
# ---------------------------------------------------------------------------

def export_events_yaml(events_daily: pd.DataFrame, path: str | None = None) -> str:
    try:
        import yaml
    except ImportError:
        raise ImportError("pyyaml nie jest zainstalowany. Uruchom: pip install pyyaml")

    path = path or _DEFAULT_EVENTS_YAML
    os.makedirs(os.path.dirname(path), exist_ok=True)

    records = [
        {"date": row.date.strftime("%Y-%m-%d"), "category": row.category, "count": int(row.count)}
        for row in events_daily.itertuples(index=False)
    ]
    payload = {
        "meta": {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "schema_version": 1,
        },
        "records": records,
    }
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"   [YAML] {len(records)} rekordów → {path}")
    return path


def import_events_yaml(path: str | None = None) -> pd.DataFrame:
    try:
        import yaml
    except ImportError:
        raise ImportError("pyyaml nie jest zainstalowany. Uruchom: pip install pyyaml")

    path = path or _DEFAULT_EVENTS_YAML
    with open(path, encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)

    df = pd.DataFrame(payload["records"])
    df["date"]  = pd.to_datetime(df["date"])
    df["count"] = df["count"].astype("int64")
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# XML – prices
# ---------------------------------------------------------------------------

def export_prices_xml(prices_by_ticker: dict[str, pd.DataFrame], path: str | None = None) -> str:
    path = path or _DEFAULT_PRICES_XML
    os.makedirs(os.path.dirname(path), exist_ok=True)

    root = ET.Element("prices")
    root.set("exported_at", datetime.now().isoformat(timespec="seconds"))
    root.set("schema_version", "1")

    total_rows = 0
    for ticker, df in prices_by_ticker.items():
        coin_el = ET.SubElement(root, "coin", symbol=ticker)
        for row in df.itertuples(index=False):
            ET.SubElement(
                coin_el, "day",
                date=row.date.strftime("%Y-%m-%d"),
                price=str(row.price),
            )
        total_rows += len(df)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)

    print(f"   [XML]  {total_rows} wierszy ({', '.join(prices_by_ticker)}) → {path}")
    return path


def import_prices_xml(path: str | None = None) -> dict[str, pd.DataFrame]:
    path = path or _DEFAULT_PRICES_XML
    tree = ET.parse(path)
    root = tree.getroot()

    result: dict[str, pd.DataFrame] = {}
    for coin_el in root.findall("coin"):
        ticker = coin_el.attrib["symbol"]
        rows = [
            {"date": day.attrib["date"], "price": day.attrib["price"]}
            for day in coin_el.findall("day")
        ]
        df = pd.DataFrame(rows)
        df["date"]  = pd.to_datetime(df["date"])
        df["price"] = df["price"].astype("float64")
        result[ticker] = df.sort_values("date").reset_index(drop=True)

    return result


# ---------------------------------------------------------------------------
# DB – analysis results
# ---------------------------------------------------------------------------

def export_results_to_db(results: pd.DataFrame, conn_str: str | None = None) -> None:
    from models import get_engine, init_db, AnalysisResult

    init_db(conn_str)
    engine = get_engine(conn_str)

    mappings = [
        {
            "coin":                row.coin,
            "category":           row.category,
            "n_event_days":       int(row.n_event_days),
            "n_control_days":     int(row.n_control_days),
            "mean_return_event":  float(row.mean_return_event),
            "mean_return_control":float(row.mean_return_control),
            "std_event":          float(row.std_event),
            "std_control":        float(row.std_control),
            "t_stat":             float(row.t_stat),
            "p_value":            float(row.p_value),
            "significant":        int(row.significant),
        }
        for row in results.itertuples(index=False)
    ]

    with Session(engine) as session:
        session.query(AnalysisResult).delete()
        session.bulk_insert_mappings(AnalysisResult, mappings)
        session.commit()

    print(f"   [DB]   {len(mappings)} wyników analizy → analysis_results")


def import_results_from_db(conn_str: str | None = None) -> pd.DataFrame:
    from models import get_engine, AnalysisResult

    engine = get_engine(conn_str)
    with Session(engine) as session:
        rows = session.query(AnalysisResult).all()

    records = [
        {
            "coin":                r.coin,
            "category":           r.category,
            "n_event_days":       r.n_event_days,
            "n_control_days":     r.n_control_days,
            "mean_return_event":  r.mean_return_event,
            "mean_return_control":r.mean_return_control,
            "std_event":          r.std_event,
            "std_control":        r.std_control,
            "t_stat":             r.t_stat,
            "p_value":            r.p_value,
            "significant":        bool(r.significant),
        }
        for r in rows
    ]
    return pd.DataFrame(records)


def _check_events_roundtrip(original: pd.DataFrame, export_fn, import_fn, label: str) -> None:
    path = export_fn(original)
    recovered = import_fn(path)

    assert list(recovered.columns) == ["date", "category", "count"], \
        f"{label}: nieprawidłowe kolumny: {list(recovered.columns)}"
    assert str(recovered.dtypes["date"]).startswith("datetime64"), \
        f"{label}: zły typ 'date': {recovered.dtypes['date']}"
    assert recovered.dtypes["count"] == "int64", \
        f"{label}: zły typ 'count': {recovered.dtypes['count']}"

    orig  = original.sort_values(["date", "category"]).reset_index(drop=True)
    recv  = recovered.sort_values(["date", "category"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(orig, recv, check_like=False)
    print(f"   [OK] events {label} round-trip: {len(original)} wierszy")


def _check_prices_roundtrip(original: dict[str, pd.DataFrame]) -> None:
    path = export_prices_xml(original)
    recovered = import_prices_xml(path)

    for ticker, orig_df in original.items():
        assert ticker in recovered, f"XML: brakuje tickera {ticker} po imporcie"
        rec_df = recovered[ticker]
        orig_s = orig_df.sort_values("date").reset_index(drop=True)
        rec_s  = rec_df.sort_values("date").reset_index(drop=True)
        pd.testing.assert_frame_equal(
            orig_s[["date", "price"]], rec_s[["date", "price"]],
            check_like=False, rtol=1e-10,
        )
        print(f"   [OK] prices XML round-trip: {ticker} {len(orig_df)} wierszy")


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from load_events import load_events
    from fetch_prices import load_all_prices

    print("=== Round-trip verification ===\n")
    events_daily = load_events()
    prices = load_all_prices()

    _check_events_roundtrip(events_daily, export_events_json, import_events_json, "JSON")
    _check_events_roundtrip(events_daily, export_events_yaml, import_events_yaml, "YAML")
    _check_prices_roundtrip(prices)

    print("\nWszystkie testy round-trip zakonczone sukcesem.")
