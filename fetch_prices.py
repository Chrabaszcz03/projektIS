"""Fetch historical daily close prices from Yahoo Finance via yfinance (no API key required)."""

import os
import yfinance as yf
import pandas as pd

from config import COINS, DATE_FROM, DATE_TO

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Map our coin IDs to Yahoo Finance ticker symbols
YAHOO_TICKERS = {
    "bitcoin":  "BTC-USD",
    "ethereum": "ETH-USD",
}


def _cache_path(coin_id: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{coin_id}_prices.csv")


def _fetch_from_yahoo(coin_id: str) -> pd.DataFrame:
    yahoo_symbol = YAHOO_TICKERS[coin_id]
    print(f"  Pobieranie danych dla {coin_id} ({yahoo_symbol}) z Yahoo Finance...")
    raw = yf.download(
        yahoo_symbol,
        start=DATE_FROM.isoformat(),
        end=DATE_TO.isoformat(),
        interval="1d",
        progress=False,
        auto_adjust=True,
    )
    if raw.empty:
        raise RuntimeError(f"Brak danych dla {yahoo_symbol}")

    # yfinance returns a MultiIndex on columns when downloading a single ticker
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Close"]].reset_index()
    df.columns = ["date", "price"]
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.dropna(subset=["price"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_prices(coin_id: str) -> pd.DataFrame:
    """Return daily prices DataFrame for coin_id, using disk cache when available."""
    path = _cache_path(coin_id)
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["date"])
        return df

    df = _fetch_from_yahoo(coin_id)
    df.to_csv(path, index=False)
    return df


def load_all_prices() -> dict[str, pd.DataFrame]:
    """Return {ticker: prices_df} for all configured coins."""
    result = {}
    for coin_id, ticker in COINS:
        result[ticker] = load_prices(coin_id)
    return result
