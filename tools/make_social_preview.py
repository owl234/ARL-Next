#!/usr/bin/env python3
"""Generate GitHub Social Preview (1280x640) for ARL-Next.

Usage:
    python3 tools/make_social_preview.py
Output:
    img/social-preview.png (1280x640, <1MB)

Role: uploaded once to GitHub Settings -> Social preview, served as the
og:image card when the repo URL is shared externally. Referenced by nothing
in the repo, invisible on github.com itself.

Design constraint: TIMELESS ONLY. No version number, no release-specific
claims -- the image must stay valid across releases without regeneration.
Only regenerate when brand positioning or the dashboard UI changes
materially.
Layout: dark gradient background, left text block (title/subtitle/selling
points), right dashboard screenshot with rounded corners + accent border.
Fonts: Arial Bold (EN) + Hiragino Sans GB (CN). Stdlib + Pillow only.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 640
REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "img" / "dashboard.png"
DST = REPO / "img" / "social-preview.png"
FONT_EN = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_CN = "/System/Library/Fonts/Hiragino Sans GB.ttc"

BG_TOP = (13, 20, 38)
BG_BOT = (24, 33, 62)
GRID = (22, 32, 58)
ACCENT = (79, 192, 141)      # ARL-Next green
GLOW_BLUE = (59, 130, 246)
TEXT_MAIN = (245, 247, 250)
TEXT_SUB = (196, 206, 226)
PILL_BG = (30, 42, 72)
TEXT_TAG = (232, 238, 248)
TEXT_DIM = (148, 162, 188)


def font(size, cn=False):
    try:
        return ImageFont.truetype(FONT_CN if cn else FONT_EN, size)
    except OSError:
        return ImageFont.load_default()


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *img.size], radius, fill=255)
    img.putalpha(mask)
    return img


def pill(d, x, y, text, fnt, fg, bg=None, outline=None, pad_left=34, pad_right=16, pad_y=9):
    bbox = d.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = tw + pad_left + pad_right, th + pad_y * 2
    if bg is not None:
        d.rounded_rectangle([x, y, x + w, y + h], h // 2, fill=bg)
    if outline is not None:
        d.rounded_rectangle([x, y, x + w, y + h], h // 2, outline=outline, width=2)
    return w, h


def main():
    base = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(base)
    for y in range(H):  # vertical gradient
        t = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))
    for gx in range(0, W, 48):  # faint engineering grid
        d.line([(gx, 0), (gx, H)], fill=GRID, width=1)
    for gy in range(0, H, 48):
        d.line([(0, gy), (W, gy)], fill=GRID, width=1)

    # accent glows: green top-left, blue bottom-right
    glow = Image.new("RGB", (520, 320), ACCENT)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    base.paste(Image.blend(Image.new("RGB", (520, 320), BG_TOP), glow, 0.35), (-130, -110))
    glow2 = Image.new("RGB", (560, 340), GLOW_BLUE)
    glow2 = glow2.filter(ImageFilter.GaussianBlur(130))
    base.paste(Image.blend(Image.new("RGB", (560, 340), BG_BOT), glow2, 0.28), (880, 420))
    d = ImageDraw.Draw(base)

    left_x = 56
    f_title, f_sub, f_tag, f_badge, f_ver = font(70), font(22), font(22, cn=True), font(18), font(20)
    d.text((left_x, 66), "ARL-Next", font=f_title, fill=TEXT_MAIN)
    d.text((left_x, 154), "Modern Attack Surface Reconnaissance", font=f_sub, fill=TEXT_SUB)
    d.text((left_x, 186), "& Asset Monitoring Platform", font=f_sub, fill=TEXT_SUB)
    d.line([(left_x, 234), (left_x + 176, 234)], fill=ACCENT, width=4)

    # selling points as filled pills (readable at thumbnail size)
    tags = ["企业资产关联", "异步解耦调度", "原生 MCP 集成", "容器化开箱部署"]
    y = 256
    for tag in tags:
        w, h = pill(d, left_x, y, tag, f_tag, TEXT_TAG, bg=PILL_BG)
        d.ellipse([left_x + 14, y + h // 2 - 5, left_x + 24, y + h // 2 + 5], fill=ACCENT)
        d.text((left_x + 34, y + 7), tag, font=f_tag, fill=TEXT_TAG)
        y += h + 12

    # capability badges (timeless: no version number, see docstring)
    badges = ["Docker-Ready", "MCP-Native", "GPL-3.0"]
    bx = left_x
    by = y + 10
    for b in badges:
        w, h = pill(d, bx, by, b, f_badge, ACCENT, outline=ACCENT, pad_left=16, pad_right=16, pad_y=9)
        bbox = d.textbbox((0, 0), b, font=f_badge)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((bx + (w - tw) // 2 - bbox[0], by + (h - th) // 2 - bbox[1]), b, font=f_badge, fill=ACCENT)
        bx += w + 10
    d.text((left_x, 572), "github.com/owl234/ARL-Next", font=f_ver, fill=TEXT_DIM)

    # screenshot card with drop shadow (full aspect-ratio fit, no edge clipping)
    shot = Image.open(SRC).convert("RGB")
    card_x = 508
    sw = W - card_x - left_x - 8  # symmetric right margin matching left_x
    sh = round(sw * shot.height / shot.width)
    card_y = (H - (sh + 8)) // 2
    resample = getattr(Image, "Resampling", Image).LANCZOS
    shot = shot.resize((sw, sh), resample)
    shot = rounded(shot, 16)
    sh_w, sh_h = sw + 60, sh + 60
    shadow = Image.new("L", (sh_w, sh_h), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([0, 0, sh_w, sh_h], 24, fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    base.paste(Image.new("RGB", (sh_w, sh_h), (0, 0, 0)), (card_x - 22, card_y - 14), shadow)
    card = Image.new("RGBA", (sw + 8, sh + 8), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, sw + 8, sh + 8], 20, outline=ACCENT, width=3)
    base.paste(card, (card_x, card_y), card)
    base.paste(shot, (card_x + 4, card_y + 4), shot)

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.unlink(missing_ok=True)
    base.save(DST, optimize=True)
    kb = DST.stat().st_size // 1024
    print(f"saved {DST} {base.size} {kb}KB")
    assert DST.stat().st_size < 1024 * 1024, "must be <1MB"


if __name__ == "__main__":
    main()
