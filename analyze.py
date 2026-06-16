"""Statistical analysis: correlate news event days with crypto daily returns."""

import pandas as pd
import numpy as np
from scipy import stats
from datetime import timedelta

from config import ANALYSIS_CATEGORIES, EVENT_THRESHOLD


def compute_returns(prices_df: pd.DataFrame) -> pd.DataFrame:
    """Add a daily_return_pct column (% change vs previous day)."""
    df = prices_df.copy().sort_values("date").reset_index(drop=True)
    df["daily_return_pct"] = df["price"].pct_change() * 100
    return df


def get_price(prices_df: pd.DataFrame, target_date: pd.Timestamp) -> float | None:
    """Return the closing price for the date nearest to target_date."""
    if prices_df.empty:
        return None
    idx = pd.DatetimeIndex(prices_df["date"].values)
    pos = idx.get_indexer([target_date], method="nearest")[0]
    if pos < 0:
        return None
    return float(prices_df.iloc[pos]["price"])


def calculate_impact(
    prices_df: pd.DataFrame,
    event_date: pd.Timestamp,
    window_days: int = 3,
) -> float | None:
    """% price change from (event_date - window_days) to (event_date + window_days)."""
    price_before = get_price(prices_df, event_date - timedelta(days=window_days))
    price_after  = get_price(prices_df, event_date + timedelta(days=window_days))
    if price_before is None or price_after is None or price_before == 0:
        return None
    return (price_after - price_before) / price_before * 100


def analyze_window_impact(
    prices_by_ticker: dict[str, pd.DataFrame],
    events_daily: pd.DataFrame,
    window_days: int = 3,
) -> pd.DataFrame:
    """
    For every event day (count >= EVENT_THRESHOLD) and every coin compute the
    window-based % price impact.

    Returns a long-form DataFrame: coin | category | event_date | impact_pct
    """
    records = []
    for ticker, prices_df in prices_by_ticker.items():
        for category in ANALYSIS_CATEGORIES:
            cat_events = events_daily[events_daily["category"] == category]
            event_dates = cat_events.loc[cat_events["count"] >= EVENT_THRESHOLD, "date"]
            for event_date in event_dates:
                impact = calculate_impact(prices_df, event_date, window_days)
                if impact is not None:
                    records.append({
                        "coin":       ticker,
                        "category":   category,
                        "event_date": event_date,
                        "impact_pct": impact,
                    })
    return pd.DataFrame(records)


def aggregate_window_impact(impacts_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per (coin, category): mean, median, std, count of window impacts."""
    return (
        impacts_df.groupby(["coin", "category"])["impact_pct"]
        .agg(
            n_events="count",
            mean_impact="mean",
            median_impact="median",
            std_impact="std",
        )
        .reset_index()
    )


def print_window_results(window_agg: pd.DataFrame) -> None:
    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 120)
    pd.set_option("display.float_format", "{:.4f}".format)

    display = window_agg[[
        "coin", "category", "n_events",
        "mean_impact", "median_impact", "std_impact",
    ]].copy()
    display.columns = [
        "Moneta", "Kategoria", "N_eventów",
        "Śr_wpływ_%", "Mediana_%", "Std_%",
    ]
    print("\n" + "="*80)
    print("WYNIKI ANALIZY OKIENKOWEJ (±3 dni): Wpływ wydarzeń na zmianę ceny")
    print("="*80)
    print(display.to_string(index=False))
    print()


def analyze(
    prices_by_ticker: dict[str, pd.DataFrame],
    events_daily: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each (coin, category) pair compute:
      - n_event_days        : days with >= EVENT_THRESHOLD articles
      - mean_return_event   : mean daily return on event days
      - mean_return_control : mean daily return on non-event days
      - std_event / std_control
      - t_stat, p_value     : Welch t-test
      - significant         : p_value < 0.05
    """
    records = []

    for ticker, prices_df in prices_by_ticker.items():
        returns_df = compute_returns(prices_df)
        returns_df = returns_df.dropna(subset=["daily_return_pct"])

        for category in ANALYSIS_CATEGORIES:
            cat_events = events_daily[events_daily["category"] == category]
            event_dates = set(
                cat_events.loc[cat_events["count"] >= EVENT_THRESHOLD, "date"]
            )

            event_mask = returns_df["date"].isin(event_dates)
            event_returns   = returns_df.loc[event_mask,  "daily_return_pct"].values
            control_returns = returns_df.loc[~event_mask, "daily_return_pct"].values

            if len(event_returns) < 5 or len(control_returns) < 5:
                continue

            t_stat, p_value = stats.ttest_ind(
                event_returns, control_returns, equal_var=False
            )

            records.append({
                "coin":                ticker,
                "category":           category,
                "n_event_days":       int(len(event_returns)),
                "n_control_days":     int(len(control_returns)),
                "mean_return_event":  float(np.mean(event_returns)),
                "mean_return_control":float(np.mean(control_returns)),
                "std_event":          float(np.std(event_returns, ddof=1)),
                "std_control":        float(np.std(control_returns, ddof=1)),
                "t_stat":             float(t_stat),
                "p_value":            float(p_value),
                "significant":        bool(p_value < 0.05),
            })

    return pd.DataFrame(records)


def print_results(results: pd.DataFrame) -> None:
    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 120)
    pd.set_option("display.float_format", "{:.4f}".format)

    display = results[[
        "coin", "category", "n_event_days",
        "mean_return_event", "mean_return_control",
        "p_value", "significant",
    ]].copy()
    display.columns = [
        "Moneta", "Kategoria", "Dni_event",
        "Śr_zwrot_event%", "Śr_zwrot_control%",
        "p-value", "Istotny?",
    ]
    print("\n" + "="*80)
    print("WYNIKI ANALIZY: Wpływ kategorii wydarzeń na dzienne zwroty kryptowalut")
    print("="*80)
    print(display.to_string(index=False))
    print()
