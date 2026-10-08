"""Charts for the liquidity pack (static PNG, light theme)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402

from . import config  # noqa: E402
from .data import HISTORICAL_EVENTS  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e6e5e1"
BLUE = "#2a78d6"
BLUE_LIGHT = "#cde2fb"
ORANGE = "#eb6834"
CRITICAL = "#d03b3b"


def _style(ax, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=12)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _limit_lines(ax, x_left) -> None:
    for level, color, label in (
        (config.LCR_INTERNAL_LIMIT, MUTED, "Internal limit"),
        (config.REG_MINIMUM, CRITICAL, "Regulatory minimum"),
    ):
        ax.axhline(level, color=color, linewidth=1, linestyle="--")
        ax.text(x_left, level + 0.004, f"{label} {level:.0%}", color=INK_2,
                fontsize=8, va="bottom")


def lcr_history(lcr_daily: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(lcr_daily.index, lcr_daily["lcr"], color=BLUE, linewidth=2)
    _limit_lines(ax, lcr_daily.index[0])

    # alternate label placement so neighbouring events don't collide
    placements = [((-12, -34), "right"), ((-12, 42), "right"), ((14, -36), "left")]
    for i, (day, _, desc) in enumerate(HISTORICAL_EVENTS):
        if day < len(lcr_daily):
            d = lcr_daily.index[day]
            y = lcr_daily["lcr"].iloc[day]
            ax.plot(d, y, "o", color=BLUE, markersize=8,
                    markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
            offset, ha = placements[i % len(placements)]
            ax.annotate(textwrap.fill(desc, 30), (d, y), xytext=offset,
                        textcoords="offset points", fontsize=8, color=INK_2,
                        ha=ha, va="center",
                        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))

    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0.95, max(lcr_daily["lcr"].max() * 1.08, 1.3))
    _style(ax, "Liquidity Coverage Ratio - daily actuals")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def attribution_bars(drivers: pd.DataFrame, label_col: str, title: str, path: Path) -> None:
    d = drivers.iloc[::-1]  # largest at the top
    colors = [BLUE if v >= 0 else ORANGE for v in d["delta"]]
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(d) + 1.5))
    ax.barh(d[label_col], d["delta"], color=colors, height=0.6)
    ax.axvline(0, color=MUTED, linewidth=1)
    span = d["delta"].abs().max()
    for i, v in enumerate(d["delta"]):
        ax.text(v + (0.02 * span if v >= 0 else -0.02 * span), i,
                f"{v:+,.0f}" if round(v) else "0", va="center", ha="left" if v >= 0 else "right",
                color=INK, fontsize=9)
    ax.set_xlim(-span * 1.25, span * 1.25)
    ax.set_xlabel("Change in LCR surplus, EUR mn", color=INK_2, fontsize=9)
    _style(ax, title)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.tick_params(axis="y", colors=INK_2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def lcr_forecast(lcr_daily: pd.DataFrame, fcst: pd.DataFrame, path: Path,
                 history_days: int = 30) -> None:
    hist = lcr_daily["lcr"].tail(history_days)
    fig, ax = plt.subplots(figsize=(10, 4.5))

    ax.fill_between(fcst.index, fcst["lcr_low"], fcst["lcr_high"],
                    color=BLUE_LIGHT, linewidth=0, label="90% band")
    ax.plot(hist.index, hist, color=BLUE, linewidth=2, label="Actual")
    joined = pd.concat([hist.tail(1), fcst["lcr"]])
    ax.plot(joined.index, joined, color=BLUE, linewidth=2, linestyle=(0, (4, 3)),
            label="Forecast (pipeline)")
    _limit_lines(ax, hist.index[0])

    low = fcst["lcr"].idxmin()
    ax.annotate(f"Low point {fcst.loc[low, 'lcr']:.0%}", (low, fcst.loc[low, "lcr"]),
                xytext=(14, -4), textcoords="offset points", ha="left",
                fontsize=9, color=INK)

    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0.95, max(fcst["lcr_high"].max(), hist.max()) * 1.05)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="upper left")
    _style(ax, "LCR outlook - next 10 business days")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
