# paper-translator

PDF の論文を原文に忠実な逐語訳で日本語に翻訳し、図版を埋め込んだ **単一の HTML ファイル** として出力する [Claude Code](https://claude.com/claude-code) / [Codex](https://developers.openai.com/codex/) 用のスキルです。

- 全文を逐語訳 (省略・要約・補足なし)。専門用語は初出時に原語を併記
- ベクター図は SVG のまま、写真などのラスター画像は元の解像度の PNG で切り出して埋め込み
- 表は HTML の `<table>` で再現、数式は MathJax で表示
- 引用番号・図表番号・節番号はページ内リンク、URL・DOI・arXiv ID は新規タブで開くリンク
- 白基調のシンプルなデザイン

## 必要なもの

- [Claude Code](https://claude.com/claude-code) または [Codex](https://developers.openai.com/codex/)
- [uv](https://docs.astral.sh/uv/) (スクリプトの依存ライブラリ PyMuPDF を自動で導入するために使用)
- Python 3.10 以上

## インストール

### Claude Code

Claude Code のユーザースキルのディレクトリに clone します。

```bash
git clone https://github.com/hirobon1690/paper-translator.git ~/.claude/skills/paper-translator
```

特定のプロジェクトだけで使う場合は、プロジェクトの `.claude/skills/` に clone してください。

```bash
git clone https://github.com/hirobon1690/paper-translator.git .claude/skills/paper-translator
```

Claude Code を起動 (または再起動) すると、スキル `paper-translator` が認識されます。

### Codex

ユーザー共通で使う場合は、Codex のユーザースキルのディレクトリに clone します。

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/hirobon1690/paper-translator.git ~/.agents/skills/paper-translator
```

特定のプロジェクトだけで使う場合は、そのプロジェクトのルートで実行してください。

```bash
mkdir -p .agents/skills
git clone https://github.com/hirobon1690/paper-translator.git .agents/skills/paper-translator
```

利用するプロジェクトを Codex で開き、スキル `paper-translator` が認識されることを確認します。表示されない場合は Codex を再起動してください。配置場所と呼び出し方の詳細は [OpenAI 公式のスキルドキュメント](https://learn.chatgpt.com/docs/build-skills) を参照してください。

## 使い方

### Claude Code

スラッシュコマンドで PDF のパスを渡します。

```
/paper-translator ~/Downloads/paper.pdf
```

### Codex

Codex の入力欄で `$paper-translator` と PDF のパスを指定します。

```text
$paper-translator /絶対パス/paper.pdf を全文和訳して
```

空白を含むパスは、次のように引用符で囲んで指定できます。

```text
$paper-translator "/絶対パス/paper (1).pdf" を全文和訳して
```

### 自然言語での依頼と出力先の指定

Claude Code / Codex のどちらも、「この論文を翻訳して」のように自然言語で依頼できます。

出力先は既定で PDF と同じディレクトリの `<PDFのファイル名>_ja.html` です。出力先を変更したい場合は、依頼時に指定してください。

```text
この論文を全文和訳して: /絶対パス/paper.pdf
出力先は /絶対パス/output.html にしてください。
```

## 構成

```
paper-translator/
├── SKILL.md              スキル本体 (手順と翻訳方針)
├── assets/template.html  HTML テンプレート
└── scripts/
    ├── analyze_pdf.py    ページごとのテキスト・プレビュー・図の候補位置・埋め込み URL を抽出
    ├── crop.py           図を切り出す (ベクター図は SVG、ラスター画像は PNG を自動判定)
    └── finalize.py       画像を data URI で埋め込み、外部リンクを新規タブ化して単一 HTML にする
```

## 注意

- 数式の表示に MathJax の CDN を使うため、オフラインでは数式が LaTeX のソースのまま表示されます
- 図の自動検出は粗く、Claude Code / Codex がページ画像を見て範囲を補正する前提です。図の多い論文では時間がかかります
- 写真を多く含む論文では出力 HTML が数 MB になります
- 翻訳結果の取り扱いは原論文のライセンスに従ってください
