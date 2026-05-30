"""
make_icon.py — 应用图标生成器（立体 / 简约，Apple·小米设计语言）
理念「索引卷宗」：悬浮的法律卷宗 + 右侧分类索引标签，
寓意"把案件材料分类索引归入标准卷宗"。

立体技法：
  - 背景对角渐变 + 顶部柔光 + 四角柔暗角
  - 卡片悬浮于大尺度柔影之上（Apple 式 ambient shadow）
  - 各表面微渐变 + 顶边高光，标签做物理质感
产物：icon.png(1024) / icon.ico(16–256)；运行：python make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
SIZE = 1024
SS = 2
C = SIZE * SS

# 背景品牌绿（对角渐变：左上亮 → 右下深）
BG_TL = (46, 168, 92)     # #2ea85c
BG_BR = (16, 96, 44)      # #10602c
# 卷宗
PAPER_TOP = (255, 255, 255)
PAPER_BOT = (240, 244, 241)
LINE = (206, 216, 210)
HEADER_TOP = (33, 150, 73)
HEADER_BOT = (22, 116, 56)
# 分类索引标签（与 app 徽章语义色一致：蓝/琥珀/紫），每个上亮下深
TABS = [
    ((42, 137, 255), (9, 95, 210)),
    ((233, 190, 70), (203, 154, 30)),
    ((155, 110, 240), (120, 70, 210)),
]
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"


def _blank():
    return Image.new("RGBA", (C, C), (0, 0, 0, 0))


def _diag_gradient(tl, br):
    """对角线性渐变。"""
    small = 256
    g = Image.new("RGB", (small, small))
    px = g.load()
    for y in range(small):
        for x in range(small):
            t = (x + y) / (2 * (small - 1))
            px[x, y] = tuple(int(tl[i] + (br[i] - tl[i]) * t) for i in range(3))
    return g.resize((C, C), Image.BILINEAR).convert("RGBA")


def _vgrad(box, top, bot):
    """在指定矩形区域生成竖直渐变图层（带 alpha=255）。"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    g = g.resize((w, h)).convert("RGBA")
    layer = _blank()
    layer.paste(g, (x0, y0))
    return layer


def _rounded_mask(box, radius):
    m = Image.new("L", (C, C), 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=radius, fill=255)
    return m


def _soft_shadow(box, radius, dy, blur, alpha):
    """生成柔和投影图层。"""
    sh = _blank()
    ImageDraw.Draw(sh).rounded_rectangle(
        [box[0], box[1] + dy, box[2], box[3] + dy], radius=radius, fill=(6, 40, 20, alpha)
    )
    return sh.filter(ImageFilter.GaussianBlur(blur))


def build_master() -> Image.Image:
    c = C
    base = _blank()
    tile_radius = int(c * 0.225)
    tile_mask = _rounded_mask([0, 0, c - 1, c - 1], tile_radius)

    # ---- 背景：对角渐变 ----
    base.paste(_diag_gradient(BG_TL, BG_BR), (0, 0), tile_mask)

    # 顶部柔光（径向高光，营造受光面）
    glow = _blank()
    ImageDraw.Draw(glow).ellipse(
        [int(c * 0.05), int(c * -0.35), int(c * 0.95), int(c * 0.5)], fill=(255, 255, 255, 46)
    )
    glow = glow.filter(ImageFilter.GaussianBlur(c * 0.06))
    base = Image.alpha_composite(base, Image.composite(glow, _blank(), tile_mask))

    # 极轻底部暗角（只在下方收一点，保持通透）
    vig = _blank()
    ImageDraw.Draw(vig).ellipse(
        [int(c * -0.1), int(c * 0.7), int(c * 1.1), int(c * 1.25)], fill=(0, 30, 12, 55)
    )
    vig = vig.filter(ImageFilter.GaussianBlur(c * 0.05))
    base = Image.alpha_composite(base, Image.composite(vig, _blank(), tile_mask))

    # 顶边高光细线
    rim = _blank()
    ImageDraw.Draw(rim).rounded_rectangle(
        [0, 0, c - 1, c - 1], radius=tile_radius, outline=(255, 255, 255, 60), width=max(2, int(c * 0.0035))
    )
    base = Image.alpha_composite(base, Image.composite(rim, _blank(), tile_mask))

    # ---- 卷宗卡片几何 ----
    pw, ph = int(c * 0.47), int(c * 0.55)
    px = (c - pw) // 2 - int(c * 0.025)
    py = int(c * 0.225)
    pr = int(c * 0.04)

    # 分类索引标签（先画，被卡片盖住左半）——每个立体渐变 + 小投影
    tab_w, tab_h = int(c * 0.115), int(c * 0.10)
    tab_x = px + pw - int(tab_w * 0.30)
    gap = int(c * 0.028)
    total_h = len(TABS) * tab_h + (len(TABS) - 1) * gap
    ty0 = py + (ph - total_h) // 2
    for i, (t_top, t_bot) in enumerate(TABS):
        ty = ty0 + i * (tab_h + gap)
        box = [tab_x, ty, tab_x + tab_w, ty + tab_h]
        base = Image.alpha_composite(base, _soft_shadow(box, int(c * 0.022), int(c * 0.006), c * 0.012, 90))
        tmask = _rounded_mask(box, int(c * 0.022))
        base = Image.alpha_composite(base, Image.composite(_vgrad(box, t_top, t_bot), _blank(), tmask))

    # 卡片大柔影（悬浮感）
    card_box = [px, py, px + pw, py + ph]
    base = Image.alpha_composite(base, _soft_shadow(card_box, pr, int(c * 0.022), c * 0.03, 120))

    # 卡片纸面（竖直微渐变）
    cmask = _rounded_mask(card_box, pr)
    base = Image.alpha_composite(base, Image.composite(_vgrad(card_box, PAPER_TOP, PAPER_BOT), _blank(), cmask))
    # 纸面顶边高光
    hl = _blank()
    ImageDraw.Draw(hl).rounded_rectangle(card_box, radius=pr, outline=(255, 255, 255, 200), width=max(2, int(c * 0.0025)))
    base = Image.alpha_composite(base, Image.composite(hl, _blank(), cmask))

    # 顶部品牌色条（渐变绿，仅上方圆角）
    header_h = int(ph * 0.27)
    head_box = [px, py, px + pw, py + header_h]
    head_layer = Image.composite(
        _vgrad([px, py, px + pw, py + header_h], HEADER_TOP, HEADER_BOT),
        _blank(),
        _rounded_mask([px, py, px + pw, py + header_h + pr], pr),
    )
    # 切掉底部圆角溢出（限制在 header_box 内）
    clip = _rounded_mask(card_box, pr)
    hclip = Image.new("L", (c, c), 0)
    ImageDraw.Draw(hclip).rectangle(head_box, fill=255)
    head_layer.putalpha(Image.composite(head_layer.getchannel("A"), Image.new("L", (c, c), 0),
                                         Image.composite(hclip, Image.new("L", (c, c), 0), clip)))
    base = Image.alpha_composite(base, head_layer)

    draw = ImageDraw.Draw(base)

    # 「档」字（白，带极轻投影）
    font = ImageFont.truetype(FONT_BOLD, int(header_h * 0.64))
    bbox = draw.textbbox((0, 0), "档", font=font)
    gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    gx = px + (pw - gw) / 2 - bbox[0]
    gy = py + (header_h - gh) / 2 - bbox[1]
    sh = _blank()
    ImageDraw.Draw(sh).text((gx, gy + int(c * 0.004)), "档", font=font, fill=(6, 40, 20, 110))
    base = Image.alpha_composite(base, sh.filter(ImageFilter.GaussianBlur(c * 0.004)))
    ImageDraw.Draw(base).text((gx, gy), "档", font=font, fill=(255, 255, 255, 255))

    # 正文内容线（2 条，简洁）
    draw = ImageDraw.Draw(base)
    line_x = px + int(pw * 0.15)
    line_w = int(pw * 0.6)
    line_h = max(3, int(c * 0.013))
    for i, wr in enumerate((1.0, 0.66)):
        ly = py + header_h + int(ph * 0.22) + i * int(ph * 0.18)
        draw.rounded_rectangle(
            [line_x, ly, line_x + int(line_w * wr), ly + line_h], radius=line_h // 2, fill=LINE + (255,)
        )

    return base.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    m = build_master()
    m.save(HERE / "icon.png")
    print(f"已生成 icon.png ({SIZE}×{SIZE})")
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    m.save(HERE / "icon.ico", format="ICO", sizes=sizes)
    print(f"已生成 icon.ico（{len(sizes)} 分辨率）")


if __name__ == "__main__":
    main()
