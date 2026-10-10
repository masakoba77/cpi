# Japan Core-Core CPI Charts

総務省統計局の消費者物価指数（CPI）CSVから、**コアコアCPI**（生鮮食品及びエネルギーを除く総合）の前年同月比と寄与度チャートを生成します。

## Charts

Generated under [`charts/`](charts/):

| File | Description |
|------|-------------|
| `core_core_cpi_bars.png` | コアコアCPI 前年同月比（バー） |
| `cpi_contrib_major10_stacked.png` | 10大費目の寄与度（積み上げ・近似） |
| `cpi_contrib_core_items_stacked.png` | コア寄与の近似分解（積み上げ） |
| `cpi_series.csv` | 月次系列（指数・前年同月比） |
| `index.html` | 簡易ギャラリー |

## Data

Place STAT CSVs in `data/`:

- [zmi2025aa.csv](https://www.stat.go.jp/data/cpi/2025/csv/zmi2025aa.csv) (2025年基準)
- [zmi2020aa.csv](https://www.stat.go.jp/data/cpi/2020/csv/zmi2020aa.csv) (2020年基準)

前年同月比は、同一基準で計算できる場合は2025年基準を優先し、それ以外は2020年基準を用います。指数表示は2025年1月以降を2025年基準、それ以前を2020年基準で接続しています。

## Usage

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/create_cpi_charts.py
```

Open `charts/index.html` in a browser.

## Notes

- 寄与度は「ウエイト（1万分比）× 各系列の前年同月比 / 10000」の近似です。
- 日本語フォントは Noto CJK / IPAex などを自動検出します（無い場合はフォールバック）。

## Source

[総務省統計局 消費者物価指数](https://www.stat.go.jp/data/cpi/)
