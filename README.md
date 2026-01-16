# CER Calculation Engine

厳密な評価エンジンとして、参照テキスト（正解）と仮説テキスト（対象）のアラインメントおよび CER（Character Error Rate）計算を行います。

## 機能

*   **高精度な文アラインメント**:
    *   **文字レベルDP（動的計画法）**を採用。句読点や改行がない連続した仮説テキストに対しても、参照テキスト（正解文）に合わせて最適な位置で自動分割し、全体のCER（編集距離）を最小化します。
*   **2通りのCER計算**:
    *   **char モード**: 表記のまま評価。
    *   **kana モード**: 読み（かな）に変換して評価（`pykakasi` 使用）。
*   **厳格な評価ポリシー**:
    *   句読点・空白は評価から完全に除外。
    *   Unicode NFKC 正規化を適用。
    *   長音「ー」は句読点扱いとして除外（kana モード）。

## 使用方法

### 1. 入力データの準備

評価したいテキストを `input_data.txt` という名前で保存してください。以下のタグで正解（REF）と対象（HYP）を囲みます。

```text
[REF_BEGIN]
<参照テキスト（正解）: 1行1文>
[REF_END]
[HYP_BEGIN]
<仮説テキスト（対象）: 行区切りは無視され、最適に再分割されます>
[HYP_END]
```

### 2. 実行

```bash
# 仮想環境を有効化してから実行
.\venv\Scripts\python evaluate_cer.py
```

### 3. 出力

以下の CSV ファイルが生成されます。

1.  `cer_summary.csv` (UTF-8): 全体の統計（Micro/Macro CER）。
2.  `cer_details.csv` (UTF-8): 各文ごとの詳細スコア。
3.  `cer_details_sjis.csv` (Shift-JIS): 詳細スコアの Excel 用ファイル（文字化け回避）。

## 必要要件

*   Python 3.x
*   pykakasi
*   python-Levenshtein