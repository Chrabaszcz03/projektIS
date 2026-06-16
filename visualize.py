"""Generate analysis charts and save to output/ directory."""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates

from config import ANALYSIS_CATEGORIES, CATEGORY_COLORS

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def _ensure_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── 1. Price timeline with geopolitical event markers ────────────────────────

def plot_price_timeline(
    prices_by_ticker: dict[str, pd.DataFrame],
    events_daily: pd.DataFrame,
) -> None:
    _ensure_output()
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    geo = events_daily[events_daily["category"] == "Geopolityka"].copy()
    top20 = geo.nlargest(20, "count")["date"]

    for ax, (ticker, df) in zip(axes, prices_by_ticker.items()):
        ax.plot(df["date"], df["price"], color="#1565C0", linewidth=0.8, label=ticker)
        for d in top20:
            if df["date"].min() <= d <= df["date"].max():
                ax.axvline(d, color="#F44336", alpha=0.35, linewidth=0.8)
        ax.set_ylabel(f"{ticker} (USD)", fontsize=10)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].xaxis.set_major_locator(mdates.YearLocator())
    fig.autofmt_xdate()

    patch = mpatches.Patch(color="#F44336", alpha=0.5, label="Top-20 dni Geopolityka")
    axes[0].legend(handles=[patch], fontsize=9)
    fig.suptitle("Ceny BTC i ETH (2015–2022) z zaznaczonymi dniami kluczowych wydarzeń geopolitycznych",
                 fontsize=12, y=1.01)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "price_timeline.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Zapisano: {path}")


# ── 2. Average daily return by category (grouped bar) ────────────────────────

def plot_avg_return_by_category(results: pd.DataFrame) -> None:
    _ensure_output()
    tickers = results["coin"].unique()
    n_tickers = len(tickers)
    cats = ANALYSIS_CATEGORIES
    x = np.arange(len(cats))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#1976D2", "#E53935"]

    for i, ticker in enumerate(tickers):
        sub = results[results["coin"] == ticker].set_index("category")
        means = [sub.loc[c, "mean_return_event"] if c in sub.index else 0 for c in cats]
        bars = ax.bar(x + i * width - width / 2, means, width, label=ticker, color=colors[i], alpha=0.85)
        for bar, m in zip(bars, means):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (0.02 if m >= 0 else -0.06),
                f"{m:.2f}%",
                ha="center", va="bottom" if m >= 0 else "top",
                fontsize=8,
            )

    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=20, ha="right", fontsize=10)
    ax.set_ylabel("Średnia dzienna zmiana ceny (%)", fontsize=11)
    ax.set_title("Średni dzienny zwrot BTC/ETH w dniach dużej aktywności mediów (wg kategorii)",
                 fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "avg_return_by_category.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Zapisano: {path}")


# ── 3. Box plots of BTC daily returns per category ───────────────────────────

def plot_return_distribution(
    prices_by_ticker: dict[str, pd.DataFrame],
    events_daily: pd.DataFrame,
) -> None:
    _ensure_output()
    from config import EVENT_THRESHOLD
    from analyze import compute_returns

    btc_df = prices_by_ticker.get("BTC")
    if btc_df is None:
        return

    returns_df = compute_returns(btc_df).dropna(subset=["daily_return_pct"])
    data_by_cat = []
    labels = []

    for cat in ANALYSIS_CATEGORIES:
        cat_events = events_daily[events_daily["category"] == cat]
        event_dates = set(cat_events.loc[cat_events["count"] >= EVENT_THRESHOLD, "date"])
        vals = returns_df.loc[returns_df["date"].isin(event_dates), "daily_return_pct"].values
        if len(vals) >= 5:
            data_by_cat.append(vals)
            labels.append(cat)

    fig, ax = plt.subplots(figsize=(12, 6))
    bp = ax.boxplot(
        data_by_cat,
        labels=labels,
        patch_artist=True,
        medianprops={"color": "black", "linewidth": 1.5},
        flierprops={"marker": "o", "markersize": 3, "alpha": 0.4},
        whis=1.5,
    )
    for patch, cat in zip(bp["boxes"], labels):
        patch.set_facecolor(CATEGORY_COLORS.get(cat, "#9E9E9E"))
        patch.set_alpha(0.75)

    ax.axhline(0, color="black", linewidth=0.7, linestyle="--")
    ax.set_ylabel("Dzienna zmiana ceny BTC (%)", fontsize=11)
    ax.set_title("Rozkład dziennych zwrotów BTC w dniach wzmożonych wiadomości (wg kategorii)",
                 fontsize=12)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "return_distribution.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Zapisano: {path}")


# ── 4. Heatmap: p-value (category × coin) ────────────────────────────────────

def plot_heatmap_significance(results: pd.DataFrame) -> None:
    _ensure_output()
    tickers = sorted(results["coin"].unique())
    pivot = results.pivot(index="category", columns="coin", values="p_value")
    pivot = pivot.reindex(index=ANALYSIS_CATEGORIES, columns=tickers)

    fig, ax = plt.subplots(figsize=(7, 5))
    data = pivot.values.astype(float)
    im = ax.imshow(data, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=1)
    plt.colorbar(im, ax=ax, label="p-value")

    ax.set_xticks(range(len(tickers)))
    ax.set_xticklabels(tickers, fontsize=11)
    ax.set_yticks(range(len(ANALYSIS_CATEGORIES)))
    ax.set_yticklabels(ANALYSIS_CATEGORIES, fontsize=10)

    for i in range(len(ANALYSIS_CATEGORIES)):
        for j in range(len(tickers)):
            val = data[i, j]
            if np.isnan(val):
                continue
            text = f"{val:.3f}"
            if val < 0.05:
                text += " *"
            ax.text(j, i, text, ha="center", va="center", fontsize=9,
                    color="white" if val < 0.3 else "black")

    ax.set_title("Istotność statystyczna (p-value Welch t-test)\n* = p < 0.05", fontsize=12)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "heatmap_significance.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Zapisano: {path}")


# ── 5. Grouped bar: mean window impact per category (BTC vs ETH) ─────────────

def plot_window_impact_by_category(window_agg: pd.DataFrame) -> None:
    _ensure_output()
    tickers = sorted(window_agg["coin"].unique())
    cats = ANALYSIS_CATEGORIES
    x = np.arange(len(cats))
    width = 0.35
    colors = ["#1976D2", "#E53935"]

    fig, ax = plt.subplots(figsize=(12, 6))
    for i, ticker in enumerate(tickers):
        sub = window_agg[window_agg["coin"] == ticker].set_index("category")
        means = [sub.loc[c, "mean_impact"] if c in sub.index else 0.0 for c in cats]
        bars = ax.bar(
            x + i * width - width / 2, means, width,
            label=ticker, color=colors[i % len(colors)], alpha=0.85,
        )
        for bar, m in zip(bars, means):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (0.1 if m >= 0 else -0.25),
                f"{m:.2f}%",
                ha="center", va="bottom" if m >= 0 else "top",
                fontsize=8,
            )

    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=20, ha="right", fontsize=10)
    ax.set_ylabel("Średnia zmiana ceny w oknie ±3 dni (%)", fontsize=11)
    ax.set_title(
        "Średni wpływ okienkowy (±3 dni) wydarzeń na cenę BTC/ETH — wg kategorii",
        fontsize=12,
    )
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "window_impact_by_category.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Zapisano: {path}")


def generate_all(
    prices_by_ticker: dict[str, pd.DataFrame],
    events_daily: pd.DataFrame,
    results: pd.DataFrame,
    window_agg: pd.DataFrame,
) -> None:
    print("\nGenerowanie wykresów...")
    plot_price_timeline(prices_by_ticker, events_daily)
    plot_avg_return_by_category(results)
    plot_return_distribution(prices_by_ticker, events_daily)
    plot_heatmap_significance(results)
    plot_window_impact_by_category(window_agg)
