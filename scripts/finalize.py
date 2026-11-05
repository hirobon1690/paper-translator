# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""翻訳 HTML を単一ファイルに仕上げる。

- <img src="相対/ローカルパス"> を base64 data URI に埋め込む
- "#" で始まらないリンク (外部リンク) に target="_blank" rel="noopener noreferrer" を付与
- 壊れた内部リンク (#id の参照先が存在しない) を警告

使い方:
  python3 finalize.py IN.html OUT.html
  (IN.html 内の画像パスは IN.html のあるディレクトリからの相対パスとして解決する)
"""

import base64
import mimetypes
import re
import sys
from pathlib import Path

IMG_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.I)
A_RE = re.compile(r"<a\b([^>]*)>", re.I)
HREF_RE = re.compile(r'\bhref="([^"]*)"', re.I)
ID_RE = re.compile(r'\b(?:id|name)="([^"]+)"', re.I)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    html = src.read_text(encoding="utf-8")
    base = src.parent
    warnings = []
    n_img = 0

    def embed(m):
        nonlocal n_img
        path = m.group(2)
        if path.startswith("data:"):
            return m.group(0)
        if re.match(r"^[a-z]+://", path, re.I):
            warnings.append(f"外部画像のまま: {path}")
            return m.group(0)
        f = (base / path).resolve()
        if not f.exists():
            warnings.append(f"画像が見つからない: {path}")
            return m.group(0)
        mime = mimetypes.guess_type(f.name)[0] or "image/png"
        n_img += 1
        data = base64.b64encode(f.read_bytes()).decode("ascii")
        return f"{m.group(1)}data:{mime};base64,{data}{m.group(3)}"

    html = IMG_RE.sub(embed, html)

    n_ext = 0

    def fix_anchor(m):
        nonlocal n_ext
        attrs = m.group(1)
        h = HREF_RE.search(attrs)
        if not h or h.group(1).startswith("#") or h.group(1) == "":
            return m.group(0)
        n_ext += 1
        attrs = re.sub(r'\s+target="[^"]*"', "", attrs, flags=re.I)
        attrs = re.sub(r'\s+rel="[^"]*"', "", attrs, flags=re.I)
        return f'<a{attrs} target="_blank" rel="noopener noreferrer">'

    html = A_RE.sub(fix_anchor, html)

    ids = set(ID_RE.findall(html))
    for target in sorted(set(re.findall(r'href="#([^"]+)"', html))):
        if target not in ids:
            warnings.append(f"内部リンク先が存在しない: #{target}")

    dst.write_text(html, encoding="utf-8")
    print(f"{dst}: {len(html.encode('utf-8')) / 1024:.0f} KiB, 埋め込み画像 {n_img} 枚, 外部リンク {n_ext} 件")
    for w in warnings:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
