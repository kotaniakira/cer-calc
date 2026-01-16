# CER Calculation Engine

厳密な評価エンジンとして、参照テキスト（正解）と仮説テキスト（対象）のアラインメントおよび CER（Character Error Rate）計算を行います。

## 機能

*   **高精度な文アラインメント**:
    *   **文字レベルDP（動的計画法）**を採用。句読点や改行がない連続した仮説テキストに対しても、参照テキスト（正解文）に合わせて最適な位置で自動分割し、全体のCER（編集距離）を最小化します。
*   **Char/Kana 両モード同時計算**:
    *   1回の実行で、表記通りの **Char CER** と、読み（かな）に変換した **Kana CER** (`pykakasi` 使用) の両方を算出します。
*   **厳格な評価ポリシー**:
    *   句読点・空白は評価から完全に除外。
    *   Unicode NFKC 正規化を適用。
    *   長音「ー」は句読点扱いとして除外（kana モード）。

## 使用方法

### 1. 入力データの準備と実行

2通りの方法で実行できます。

#### 方法A: 個別のファイルを指定する場合（推奨）

参照テキスト（正解）と仮説テキスト（対象）を別々のファイルとして用意し、引数で渡します。

```bash
# 仮想環境を有効化してから実行
.\venv\Scripts\python evaluate_cer.py ref.txt hyp.txt
```

*   `ref.txt`: 参照テキスト（1行1文で記述）。
*   `hyp.txt`: 仮説テキスト（行区切りは無視され、最適に再分割されます）。

#### 方法B: 統合ファイル (input_data.txt) を使う場合

`input_data.txt` という名前で、タグ（`[REF_BEGIN]`, `[REF_END]`, `[HYP_BEGIN]`, `[HYP_END]`）を含むファイルを作成し、引数なしで実行します。

```bash
.\venv\Scripts\python evaluate_cer.py
```

### 2. 出力

実行ディレクトリに以下の CSV ファイルが生成されます。

1.  **cer_summary.csv** (UTF-8): 全体の統計（Micro/Macro CER）。Char と Kana の結果が並記されます。
2.  **cer_details.csv** (UTF-8): 各文ごとの詳細スコア。1行の中に Char と Kana の両方の指標が含まれます。
3.  **cer_details_sjis.csv** (Shift-JIS): 詳細スコアの Excel 用ファイル（日本語ヘッダ付き、文字化け回避）。

## 必要要件

*   Python 3.x
*   pykakasi
*   python-Levenshtein