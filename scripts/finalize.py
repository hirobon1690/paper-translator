# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""翻訳 HTML を単一ファイルに仕上げる。

- <img src="相対/ローカルパス"> を base64 data URI に埋め込む
- 画像をリンク化し、別タブで画像そのものを開く (埋め込み画像は Blob URL を使用)
- 末尾の参考文献に、論文タイトルによる Google Scholar 検索リンクを付与
- "#" で始まらないリンク (外部リンク) に target="_blank" rel="noopener noreferrer" を付与
- 壊れた内部リンク (#id の参照先が存在しない) を警告

使い方:
  python3 finalize.py IN.html OUT.html
  (IN.html 内の画像パスは IN.html のあるディレクトリからの相対パスとして解決する)
"""

import base64
import html as html_lib
import mimetypes
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

IMG_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.I)
A_RE = re.compile(r"<a\b([^>]*)>", re.I)
HREF_RE = re.compile(r'\bhref="([^"]*)"', re.I)
ID_RE = re.compile(r'\b(?:id|name)="([^"]+)"', re.I)

IMAGE_LINK_SCRIPT = """<script id="paper-image-links">
(() => {
  for (const img of document.querySelectorAll('img')) {
    const src = img.getAttribute('src');
    if (!src) continue;
    let href = src;
    if (src.startsWith('data:')) {
      const comma = src.indexOf(',');
      const header = src.slice(5, comma);
      const payload = src.slice(comma + 1);
      const bytes = header.endsWith(';base64')
        ? Uint8Array.from(atob(payload), c => c.charCodeAt(0))
        : new TextEncoder().encode(decodeURIComponent(payload));
      href = URL.createObjectURL(new Blob([bytes], {
        type: header.split(';')[0] || 'application/octet-stream'
      }));
    }
    const existing = img.closest('a');
    const link = existing || document.createElement('a');
    link.href = href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    if (!existing) {
      img.before(link);
      link.append(img);
    }
  }
})();
</script>"""


def add_image_links(html):
    """画像データや本文を変更せず、画像リンク用スクリプトを一度だけ追加する。"""
    if 'id="paper-image-links"' in html:
        return html
    return re.sub(r"</body\s*>", lambda m: IMAGE_LINK_SCRIPT + "\n" + m[0],
                  html, count=1, flags=re.I)


def add_scholar_links(html, warnings=None):
    """参考文献の明示的なタイトルから検索リンクを作る。本文の引用は変更しない。"""
    if warnings is None:
        warnings = []

    def add_link(m):
        attrs, body = m.group(1), m.group(2)
        ref = ID_RE.search(attrs)
        if not ref or not ref.group(1).startswith("ref-"):
            return m.group(0)
        if re.search(r'class="[^"]*\bscholar-search\b', body):
            return m.group(0)
        title_attr = re.search(r'\bdata-paper-title="([^"]*)"', attrs)
        title = (" ".join(html_lib.unescape(title_attr.group(1)).split())
                 if title_attr else "")
        if not title:
            warnings.append(f"参考文献の論文タイトルが未指定: #{ref.group(1)} (data-paper-title)")
            return m.group(0)
        url = "https://scholar.google.com/scholar?q=" + quote_plus(title)
        label = html_lib.escape("Google Scholar で検索：" + title, quote=True)
        link = (f'<a class="scholar-search" href="{url}" target="_blank" '
                f'rel="noopener noreferrer" title="{label}" aria-label="{label}" '
                'style="margin-left:0.35em;text-decoration:none">'
                '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" '
                'viewBox="0 0 16 16" fill="none" stroke="currentColor" '
                'stroke-width="1.6" aria-hidden="true" style="vertical-align:-0.1em">'
                '<circle cx="6.5" cy="6.5" r="4.5"/>'
                '<path d="m10 10 4 4"/></svg></a>')
        return f"<li{attrs}>{body}{link}</li>"

    return re.sub(r"<li\b([^>]*)>(.*?)</li\s*>", add_link, html,
                  flags=re.I | re.S)


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
    html = add_scholar_links(html, warnings)

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

    html = add_image_links(html)
    dst.write_text(html, encoding="utf-8")
    print(f"{dst}: {len(html.encode('utf-8')) / 1024:.0f} KiB, 埋め込み画像 {n_img} 枚, 外部リンク {n_ext} 件")
    for w in warnings:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
