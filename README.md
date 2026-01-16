# CER Calculation Engine

厳密な評価エンジンとして、参照テキスト（正解）と仮説テキスト（対象）のアラインメントおよび CER（Character Error Rate）計算を行います。

## 機能

*   **文アラインメント**: 参照テキスト（1行1文）に合わせて、仮説テキストを最適に分割・割り当てます（動的計画法を使用）。
*   **2通りのCER計算**:
    *   **char モード**: 表記のまま評価。
    *   **kana モード**: 読み（かな）に変換して評価。
*   **厳格な評価ポリシー**:
    *   句読点・空白は評価から完全に除外。
    *   Unicode NFKC 正規化を適用。
    *   長音「ー」は句読点扱いとして除外（kana モード）。

## 使用方法

### 入力フォーマット

標準入力から以下の形式でテキストを渡してください。

```text
[REF_BEGIN]
<参照テキスト（正解）>
[REF_END]
[HYP_BEGIN]
<仮説テキスト（対象）>
[HYP_END]
```

### 実行コマンド

```bash
# 仮想環境を有効化してから実行
.\venv\Scripts\python evaluate_cer.py < input.txt
```

### 出力

以下の2つの CSV が標準出力に連続して出力されます。

1.  `cer_details.csv`: 各文ごとの詳細スコア（編集距離の内訳など）。
2.  `cer_summary.csv`: 全体の統計（Micro/Macro CER）。

## 必要要件

*   Python 3.x
*   pykakasi
*   python-Levenshtein
