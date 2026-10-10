#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Japan CPI core-core charts from STAT CSV (2020 / 2025 base)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "charts"

CORE_CORE = "生鮮食品及びエネルギーを除く総合"
ALL_ITEMS = "総合"
FRESH_FOOD = "生鮮食品"
ENERGY = "エネルギー"
FOOD_EX_FRESH = "生鮮食品を除く食料"

MAJOR10 = [
    "食料",
    "住居",
    "光熱・水道",
    "家具・家事用品",
    "被服及び履物",
    "保健医療",
    "交通・通信",
    "教育",
    "教養娯楽",
    "諸雑費",
]

# Approximate core-core contribution stack (ex-fresh-food / ex-energy leaning)
CORE_ITEMS = [
    FOOD_EX_FRESH,
    "住居",
    "家具・家事用品",
    "被服及び履物",
    "保健医療",
    "交通・通信",
    "教育",
    "教養娯楽",
    "諸雑費",
]


def setup_japanese_font() -> str:
    candidates = [
        "Noto Sans CJK JP",
        "Noto Sans CJK",
        "Noto Sans JP",
        "IPAexGothic",
        "IPAGothic",
        "Yu Gothic",
        "Hiragino Sans",
        "TakaoGothic",
        "Source Han Sans JP",
        "WenQuanYi Micro Hei",
        "Droid Sans Fallback",
        "DejaVu Sans",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return name
    for path in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-JP-Regular.otf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/ipaexfont-gothic/ipaexg.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]:
        p = Path(path)
        if p.exists():
            font_manager.fontManager.addfont(str(p))
            prop = font_manager.FontProperties(fname=str(p))
            plt.rcParams["font.family"] = prop.get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return prop.get_name()
    plt.rcParams["axes.unicode_minus"] = False
    return "DejaVu Sans"


def load_stat_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding="cp932", header=None)
    names = raw.iloc[0].astype(str)
    weights = pd.to_numeric(raw.iloc[5], errors="coerce")
    months = raw.iloc[6:].copy()
    months.index = months.iloc[:, 0].astype(str)
    months = months.drop(columns=months.columns[0])
    months.columns = names.iloc[1:].tolist()
    months = months.loc[:, ~months.columns.duplicated()]
    weight_map = {}
    for col, w in zip(names.iloc[1:], weights.iloc[1:]):
        if col not in weight_map and pd.notna(w):
            weight_map[col] = float(w)
    for c in months.columns:
        months[c] = pd.to_numeric(months[c], errors="coerce")
    months.attrs["weights"] = weight_map
    months.attrs["base"] = path.name
    return months


def yoy(series: pd.Series) -> pd.Series:
    prev = series.shift(12)
    return (series / prev - 1.0) * 100.0


def build_combined(df20: pd.DataFrame, df25: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Prefer 2025-base from 202501 onward; 2020-base before that."""
    cols = [c for c in columns if c in df20.columns or c in df25.columns]
    out = {}
    for c in cols:
        s20 = df20[c] if c in df20.columns else pd.Series(dtype=float)
        s25 = df25[c] if c in df25.columns else pd.Series(dtype=float)
        s = s20.copy()
        if len(s25):
            s = s.reindex(sorted(set(s.index) | set(s25.index)))
            for m, v in s25.items():
                if str(m) >= "202501" and pd.notna(v):
                    s.loc[m] = v
        out[c] = s
    return pd.DataFrame(out).sort_index()


def build_yoy_same_base(df20: pd.DataFrame, df25: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """YoY from 2025-base when t and t-12 exist there; else 2020-base."""
    result = {}
    for c in columns:
        y20 = yoy(df20[c]) if c in df20.columns else pd.Series(dtype=float)
        y25 = yoy(df25[c]) if c in df25.columns else pd.Series(dtype=float)
        idx = sorted(set(y20.dropna().index) | set(y25.dropna().index))
        series = pd.Series(index=idx, dtype=float)
        for m in idx:
            if (
                c in df25.columns
                and m in y25.index
                and pd.notna(y25.get(m))
            ):
                prev = f"{int(m) - 100:06d}" if str(m).isdigit() else None
                if prev and prev in df25.index and pd.notna(df25.at[prev, c]):
                    series[m] = y25[m]
                    continue
            if m in y20.index and pd.notna(y20.get(m)):
                series[m] = y20[m]
        result[c] = series
    return pd.DataFrame(result).sort_index()


def weights_for(df25: pd.DataFrame, df20: pd.DataFrame, name: str) -> float:
    w25 = df25.attrs.get("weights", {})
    w20 = df20.attrs.get("weights", {})
    if name in w25:
        return w25[name]
    return w20.get(name, np.nan)


def contrib_table(yoy_df: pd.DataFrame, items: list[str], weights: dict[str, float]) -> pd.DataFrame:
    data = {}
    for item in items:
        if item not in yoy_df.columns:
            continue
        w = weights.get(item, np.nan)
        data[item] = yoy_df[item] * (w / 10000.0)
    return pd.DataFrame(data).sort_index()


def month_labels(index: pd.Index) -> list[str]:
    labels = []
    for m in index:
        s = str(m)
        if len(s) == 6 and s.isdigit():
            labels.append(f"{s[:4]}-{s[4:]}")
        else:
            labels.append(s)
    return labels


def style_axes(ax, title: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=14, pad=12)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_core_core_bars(yoy_cc: pd.Series, path: Path) -> None:
    s = yoy_cc.dropna()
    if len(s) > 96:
        s = s.iloc[-96:]
    fig, ax = plt.subplots(figsize=(14, 6))
    colors = ["#c0392b" if v >= 0 else "#2980b9" for v in s.values]
    ax.bar(range(len(s)), s.values, color=colors, width=0.85)
    ax.set_xticks(range(len(s)))
    labels = month_labels(s.index)
    step = max(1, len(labels) // 16)
    ax.set_xticklabels(
        [lab if i % step == 0 else "" for i, lab in enumerate(labels)],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    style_axes(ax, "コアコアCPI（生鮮食品及びエネルギーを除く総合）前年同月比", "前年同月比（%）")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_stacked(contrib: pd.DataFrame, path: Path, title: str, window: int = 36) -> None:
    df = contrib.dropna(how="all")
    if len(df) > window:
        df = df.iloc[-window:]
    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(df))
    bottom_pos = np.zeros(len(df))
    bottom_neg = np.zeros(len(df))
    cmap = plt.get_cmap("tab20")
    for i, col in enumerate(df.columns):
        vals = df[col].fillna(0.0).values
        pos = np.where(vals >= 0, vals, 0.0)
        neg = np.where(vals < 0, vals, 0.0)
        color = cmap(i % 20)
        ax.bar(x, pos, bottom=bottom_pos, color=color, width=0.85, label=col)
        ax.bar(x, neg, bottom=bottom_neg, color=color, width=0.85)
        bottom_pos += pos
        bottom_neg += neg
    ax.set_xticks(x)
    labels = month_labels(df.index)
    step = max(1, len(labels) // 12)
    ax.set_xticklabels(
        [lab if i % step == 0 else "" for i, lab in enumerate(labels)],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    style_axes(ax, title, "寄与度（%ポイント）")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def write_index_html(path: Path, latest: dict) -> None:
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>日本 コアコアCPI チャート</title>
  <style>
    :root {{
      --bg: #f3f6f8;
      --ink: #1a2330;
      --muted: #5a6a7a;
      --accent: #0b6e4f;
      --line: #d5dee6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(1200px 500px at 10% -10%, #d9ebe3 0%, transparent 55%),
        radial-gradient(900px 400px at 100% 0%, #dce7f2 0%, transparent 50%),
        var(--bg);
      line-height: 1.55;
    }}
    header {{
      padding: 2.5rem 1.25rem 1.25rem;
      max-width: 980px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 0.4rem;
      font-size: clamp(1.6rem, 3vw, 2.2rem);
      letter-spacing: 0.02em;
    }}
    .lede {{ color: var(--muted); max-width: 42rem; }}
    .meta {{
      margin-top: 1rem;
      font-size: 0.95rem;
      color: var(--muted);
    }}
    .meta strong {{ color: var(--accent); font-weight: 700; }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 0 1.25rem 3rem;
      display: grid;
      gap: 2rem;
    }}
    section h2 {{
      margin: 0 0 0.5rem;
      font-size: 1.15rem;
    }}
    section p {{
      margin: 0 0 0.75rem;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    img {{
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      background: #fff;
    }}
    footer {{
      max-width: 980px;
      margin: 0 auto;
      padding: 0 1.25rem 2.5rem;
      color: var(--muted);
      font-size: 0.85rem;
    }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <header>
    <h1>日本 コアコアCPI</h1>
    <p class="lede">総務省統計局の消費者物価指数から、コアコア（生鮮食品及びエネルギーを除く総合）の前年同月比と主要な寄与度分解を可視化しています。</p>
    <p class="meta">最新月: <strong>{latest.get("month", "—")}</strong> ／ コアコア前年同月比: <strong>{latest.get("core_core_yoy", "—")}</strong></p>
  </header>
  <main>
    <section>
      <h2>コアコアCPI 前年同月比</h2>
      <p>生鮮食品及びエネルギーを除く総合の前年同月比（バー）。</p>
      <img src="core_core_cpi_bars.png" alt="コアコアCPI前年同月比" />
    </section>
    <section>
      <h2>10大費目の寄与度（積み上げ）</h2>
      <p>総合に対する10大費目の寄与度近似（ウエイト×各費目前年同月比）。</p>
      <img src="cpi_contrib_major10_stacked.png" alt="10大費目寄与度" />
    </section>
    <section>
      <h2>コア寄与の近似（積み上げ）</h2>
      <p>生鮮食品を除く食料とエネルギー色の薄い費目を中心にしたコア寄与の近似分解。</p>
      <img src="cpi_contrib_core_items_stacked.png" alt="コア品目寄与度近似" />
    </section>
  </main>
  <footer>
    出典: <a href="https://www.stat.go.jp/data/cpi/">総務省統計局 消費者物価指数</a> ／
    系列データ: <a href="cpi_series.csv">cpi_series.csv</a>
  </footer>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font = setup_japanese_font()
    print(f"font={font}")

    df20 = load_stat_csv(DATA / "zmi2020aa.csv")
    df25 = load_stat_csv(DATA / "zmi2025aa.csv")

    needed = list(
        dict.fromkeys(
            [ALL_ITEMS, CORE_CORE, FRESH_FOOD, ENERGY, FOOD_EX_FRESH] + MAJOR10 + CORE_ITEMS
        )
    )
    yoy_df = build_yoy_same_base(df20, df25, needed)
    idx_df = build_combined(df20, df25, needed)

    series = pd.DataFrame(
        {
            "month": yoy_df.index,
            "all_items_index": idx_df.reindex(yoy_df.index)[ALL_ITEMS],
            "core_core_index": idx_df.reindex(yoy_df.index)[CORE_CORE],
            "all_items_yoy": yoy_df[ALL_ITEMS],
            "core_core_yoy": yoy_df[CORE_CORE],
        }
    )
    for col in MAJOR10:
        if col in yoy_df.columns:
            series[f"yoy_{col}"] = yoy_df[col]
    series.to_csv(OUT / "cpi_series.csv", index=False, encoding="utf-8")

    plot_core_core_bars(yoy_df[CORE_CORE], OUT / "core_core_cpi_bars.png")

    w = {}
    for name in MAJOR10 + CORE_ITEMS:
        w[name] = weights_for(df25, df20, name)
    major_c = contrib_table(yoy_df, MAJOR10, w)
    core_c = contrib_table(yoy_df, CORE_ITEMS, w)

    plot_stacked(
        major_c,
        OUT / "cpi_contrib_major10_stacked.png",
        "消費者物価指数 10大費目の寄与度（積み上げ・近似）",
    )
    plot_stacked(
        core_c,
        OUT / "cpi_contrib_core_items_stacked.png",
        "コア寄与の近似分解（生鮮除く食料＋主要費目）",
    )

    cc = yoy_df[CORE_CORE].dropna()
    latest_month = str(cc.index[-1]) if len(cc) else "—"
    latest_val = f"{cc.iloc[-1]:.2f}%" if len(cc) else "—"
    if len(latest_month) == 6 and latest_month.isdigit():
        latest_month_fmt = f"{latest_month[:4]}-{latest_month[4:]}"
    else:
        latest_month_fmt = latest_month
    write_index_html(OUT / "index.html", {"month": latest_month_fmt, "core_core_yoy": latest_val})

    meta = {
        "latest_month": latest_month_fmt,
        "core_core_yoy": latest_val,
        "font": font,
        "outputs": sorted(p.name for p in OUT.iterdir()),
    }
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
