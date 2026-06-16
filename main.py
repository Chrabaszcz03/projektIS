"""Main pipeline: fetch prices, load events, analyse, visualise."""

import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fetch_prices import load_all_prices
from load_events import load_events
from analyze import (
    analyze, print_results,
    analyze_window_impact, aggregate_window_impact, print_window_results,
)
import visualize
import export_import


def main():
    print("=== Wpływ Wydarzeń na Ceny Kryptowalut ===\n")

    print("1. Pobieranie / wczytywanie cen kryptowalut...")
    prices = load_all_prices()
    for ticker, df in prices.items():
        print(f"   {ticker}: {len(df)} dni ({df['date'].min().date()} do {df['date'].max().date()})")

    print("\n2. Wczytywanie wydarzeń...")
    events_daily = load_events()
    print(f"   Załadowano {len(events_daily)} rekordów (data × kategoria)")
    print(f"   Kategorie: {events_daily['category'].unique().tolist()}")

    print("\n3. Analiza statystyczna (Welch t-test)...")
    results = analyze(prices, events_daily)
    print_results(results)

    print("3b. Analiza okienkowa (±3 dni)...")
    window_impacts = analyze_window_impact(prices, events_daily)
    window_agg     = aggregate_window_impact(window_impacts)
    print_window_results(window_agg)

    print("4. Generowanie wykresów...")
    visualize.generate_all(prices, events_daily, results, window_agg)

    print("\n5. Eksport danych...")
    export_import.export_events_json(events_daily)
    export_import.export_events_yaml(events_daily)
    export_import.export_prices_xml(prices)
    export_import.export_results_to_db(results)

    print("\nGotowe! Wykresy i eksport zapisane w katalogu output/")


if __name__ == "__main__":
    main()
