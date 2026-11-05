# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///
"""PDF を解析して翻訳作業用の素材を作業ディレクトリに書き出す。

出力 (WORKDIR 配下):
  pages/page-NNN.png   各ページのプレビュー画像 (目視確認用)
  pages/page-NNN-annot.png  図候補(赤枠, #番号)・キャプション(青枠)・座標グリッド(50pt)入りプレビュー
  text/page-NNN.txt    各ページのテキスト (読み順に近い順で抽出)
  links.json           PDF 内の外部 URL リンク注釈
  figures.json         図の候補領域 (ページ座標, pt 単位) とキャプション候補
  summary.txt          上記の概要

使い方:
  uv run analyze_pdf.py PAPER.pdf WORKDIR [--dpi 100]
"""

import argparse
import json
import re
from pathlib import Path

import pymupdf

CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.?|Table)\s*([A-Z]?\d+|[IVX]+)\s*[.:|]", re.I)


def merge_rects(rects, gap):
    """近接する矩形を繰り返し結合する。"""
    rects = [pymupdf.Rect(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out = []
        while rects:
            r = rects.pop()
            grown = pymupdf.Rect(r.x0 - gap, r.y0 - gap, r.x1 + gap, r.y1 + gap)
            i = 0
            while i < len(rects):
                if grown.intersects(rects[i]):
                    r |= rects.pop(i)
                    grown = pymupdf.Rect(r.x0 - gap, r.y0 - gap, r.x1 + gap, r.y1 + gap)
                    changed = True
                else:
                    i += 1
            out.append(r)
        rects = out
    return rects


def figure_candidates(page):
    pw, ph = page.rect.width, page.rect.height
    rects = []
    for info in page.get_image_info():
        r = pymupdf.Rect(info["bbox"]) & page.rect
        if r.width > 20 and r.height > 20:
            rects.append(r)
    for d in page.get_drawings():
        r = pymupdf.Rect(d["rect"]) & page.rect
        # ページ全体を覆う背景や枠は除外
        if r.width > pw * 0.95 and r.height > ph * 0.95:
            continue
        if r.is_empty and r.width < 1 and r.height < 1:
            continue
        rects.append(r)
    merged = merge_rects(rects, gap=20)
    blocks = [b for b in page.get_text("blocks") if not CAPTION_RE.match(b[4])]
    cands = []
    for r in merged:
        if r.width < 60 or r.height < 40:
            continue
        # 図の中のラベル文字列 (軸ラベル等) を取り込むため、少し広げた範囲に入る文字ブロックを結合
        expanded = pymupdf.Rect(r)
        for b in blocks:
            br = pymupdf.Rect(b[:4])
            if br.width < r.width * 0.9 and pymupdf.Rect(r.x0 - 15, r.y0 - 15, r.x1 + 15, r.y1 + 15).contains(br):
                expanded |= br
        cands.append(expanded)
    return cands


def annotate(page, cands, caps, path, dpi):
    """候補枠 (赤) ・キャプション (青) ・50pt 間隔の座標グリッドを描いたプレビューを保存する。"""
    doc = pymupdf.open()
    doc.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
    p = doc[0]
    w, h = p.rect.width, p.rect.height
    for x in range(50, int(w), 50):
        p.draw_line((x, 0), (x, h), color=(0.6, 0.6, 1), width=0.3)
        p.insert_text((x + 1, 8), str(x), fontsize=6, color=(0, 0, 1))
    for y in range(50, int(h), 50):
        p.draw_line((0, y), (w, y), color=(0.6, 0.6, 1), width=0.3)
        p.insert_text((1, y - 1), str(y), fontsize=6, color=(0, 0, 1))
    for k, r in enumerate(cands):
        p.draw_rect(r, color=(1, 0, 0), width=1.2)
        p.insert_text((r.x0 + 2, r.y0 + 9), f"#{k}", fontsize=9, color=(1, 0, 0))
    for c in caps:
        p.draw_rect(pymupdf.Rect(c["bbox"]), color=(0, 0.4, 1), width=0.8)
    p.get_pixmap(dpi=dpi).save(path)


def captions(page):
    res = []
    for b in page.get_text("blocks"):
        text = b[4].strip()
        if CAPTION_RE.match(text):
            res.append({"bbox": [round(v, 1) for v in b[:4]], "text": text[:120].replace("\n", " ")})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("workdir")
    ap.add_argument("--dpi", type=int, default=100)
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    work = Path(args.workdir)
    (work / "pages").mkdir(parents=True, exist_ok=True)
    (work / "text").mkdir(parents=True, exist_ok=True)

    links, figures, summary = [], [], []
    meta = doc.metadata or {}
    summary.append(f"file: {args.pdf}")
    summary.append(f"pages: {doc.page_count}")
    summary.append(f"title(meta): {meta.get('title', '')}")
    summary.append("")

    for i, page in enumerate(doc, start=1):
        page.get_pixmap(dpi=args.dpi).save(work / "pages" / f"page-{i:03d}.png")
        (work / "text" / f"page-{i:03d}.txt").write_text(page.get_text("text", sort=False), encoding="utf-8")

        # 外部 URL のリンク注釈のみ記録する (内部ジャンプは本文から再構成できるので不要)
        for ln in page.get_links():
            if ln.get("uri"):
                links.append({"page": i, "uri": ln["uri"],
                              "anchor_text": page.get_textbox(ln["from"]).strip()[:200]})

        cands = figure_candidates(page)
        caps = captions(page)
        if cands or caps:
            annotate(page, cands, caps, work / "pages" / f"page-{i:03d}-annot.png", 110)
            figures.append({
                "page": i,
                "page_size": [round(page.rect.width, 1), round(page.rect.height, 1)],
                "candidates": [[round(v, 1) for v in r] for r in cands],
                "captions": caps,
            })
            summary.append(f"page {i}: {len(cands)} figure candidate(s), captions: "
                           + "; ".join(c["text"][:40] for c in caps))

    (work / "links.json").write_text(json.dumps(links, ensure_ascii=False, indent=1), encoding="utf-8")
    (work / "figures.json").write_text(json.dumps(figures, ensure_ascii=False, indent=1), encoding="utf-8")
    summary.append("")
    summary.append(f"external links: {len(links)}")
    (work / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    print(f"\nwritten to {work}")


if __name__ == "__main__":
    main()
