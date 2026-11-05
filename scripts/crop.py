# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///
"""PDF ページの指定領域を図として切り出す。

ベクター図は SVG (ベクターのまま、文字はパス化)、ラスター画像のみの領域は PNG で出力する。
座標は PDF の pt 単位 (左上原点)。figures.json の candidates をそのまま使える。

使い方:
  uv run crop.py PAPER.pdf PAGE X0 Y0 X1 Y1 OUT [--format auto|svg|png] [--dpi 200] [--pad 4]
  --dpi は PNG の最低解像度 (埋め込み画像の元解像度の方が高ければそちらに合わせる、上限 600)。
  PAGE は 1 始まり。OUT は拡張子なしで指定する (例: fig/fig3)。拡張子は形式に応じて付く。
  --format auto (既定): 領域内にベクター描画があれば SVG、ラスター画像だけなら PNG。

  目視確認用に、出力と同じディレクトリの _preview/ に PNG プレビューも書き出す
  (SVG の場合は SVG 化したものと同じ内容をラスタライズしたもの)。
"""

import argparse
from pathlib import Path

import pymupdf


def has_vector(page, clip):
    # 1 枚のラスター画像が領域の大部分を占める場合 (グラフを画像で貼った図など) はラスター扱い
    for info in page.get_image_info():
        if (pymupdf.Rect(info["bbox"]) & clip).get_area() >= 0.8 * clip.get_area():
            return False
    for d in page.get_drawings():
        # 白の塗りつぶしのみ (画像の下地など) はベクター図とみなさない
        if d["type"] == "f" and d.get("fill") and min(d["fill"]) >= 0.99:
            continue
        # 水平線・垂直線は面積 0 の矩形になるので少し広げて判定する
        if (pymupdf.Rect(d["rect"]) + (-0.5, -0.5, 0.5, 0.5)).intersects(clip):
            return True
    return False


def isolate(src, pno, clip):
    """clip の外側の文字・図形を削除した 1 ページの文書を返す (SVG に不要な要素を含めないため)。"""
    doc = pymupdf.open()
    doc.insert_pdf(src, from_page=pno, to_page=pno)
    page = doc[0]
    R, big = page.rect, 10000
    outside = [
        (R.x0 - big, R.y0 - big, R.x1 + big, clip.y0),
        (R.x0 - big, clip.y1, R.x1 + big, R.y1 + big),
        (R.x0 - big, clip.y0, clip.x0, clip.y1),
        (clip.x1, clip.y0, R.x1 + big, clip.y1),
    ]
    for r in outside:
        page.add_redact_annot(pymupdf.Rect(r), fill=False)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
    page.set_cropbox(clip)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("page", type=int)
    ap.add_argument("x0", type=float)
    ap.add_argument("y0", type=float)
    ap.add_argument("x1", type=float)
    ap.add_argument("y1", type=float)
    ap.add_argument("out")
    ap.add_argument("--format", choices=["auto", "svg", "png"], default="auto")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--pad", type=float, default=4)
    args = ap.parse_args()

    src = pymupdf.open(args.pdf)
    pno = args.page - 1
    page = src[pno]
    p = args.pad
    clip = pymupdf.Rect(args.x0 - p, args.y0 - p, args.x1 + p, args.y1 + p) & page.rect

    fmt = args.format
    if fmt == "auto":
        fmt = "svg" if has_vector(page, clip) else "png"

    out = Path(args.out).with_suffix(f".{fmt}")
    out.parent.mkdir(parents=True, exist_ok=True)
    preview = out.parent / "_preview" / f"{out.stem}.png"
    preview.parent.mkdir(exist_ok=True)

    if fmt == "svg":
        doc = isolate(src, pno, clip)
        svg = doc[0].get_svg_image(text_as_path=True)
        out.write_text(svg, encoding="utf-8")
        doc[0].get_pixmap(dpi=110).save(preview)
        size = f"{len(svg.encode()) / 1024:.0f} KiB"
    else:
        # 埋め込み画像の元の解像度を落とさないよう、領域内の画像の実効 dpi に合わせる
        dpi = args.dpi
        for info in page.get_image_info():
            r = pymupdf.Rect(info["bbox"])
            if r.intersects(clip) and r.width > 0:
                dpi = max(dpi, min(600, round(info["width"] / r.width * 72)))
        pix = page.get_pixmap(dpi=dpi, clip=clip)
        pix.save(out)
        page.get_pixmap(dpi=110, clip=clip).save(preview)
        size = f"{pix.width}x{pix.height}px"

    # 原寸 (1pt = 96/72 px) の 1.5 倍を表示幅の目安とする (CSS の max-width: 100% で本文幅に収まる)
    print(f"{out} ({fmt}, {size}, clip {tuple(round(v, 1) for v in clip)})")
    print(f"display width: {round(clip.width * 96 / 72 * 1.5)}")
    print(f"preview: {preview}")


if __name__ == "__main__":
    main()
