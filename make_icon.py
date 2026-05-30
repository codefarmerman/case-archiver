"""
make_icon.py — 应用图标生成器
设计理念「索引卷宗」：一份法律文书 + 右侧多彩分类索引标签，
寓意"把杂乱案件材料分类、索引、归入标准卷宗"。
索引标签复用 app 内徽章语义色（绿/蓝/琥珀），与产品视觉语言呼应。

产物：
  icon.png  1024×1024
  icon.ico  多分辨率（16–256）
运行：python make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
SIZE = 1024
SS = 2
C = SIZE * SS

# 背景品牌绿渐变
BG_TOP = (33, 142, 73)
BG_BOT = (19, 104, 49)
# 卷宗文档
PAPER = (255, 255, 255)
PAPER_EDGE = (210, 222, 214)
LINE = (203, 213, 207)        # 文档内容线
HEADER = (26, 127, 55)        # 文档顶部色条（品牌绿）
# 分类索引标签：取与绿底强对比的色，呼应 app 徽章语义（蓝/琥珀/紫）
TABS = [(9, 105, 218), (212, 167, 44), (130, 80, 223)]  # 蓝 / 琥珀 / 紫

FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"


def _rounded(canvas, box, radius, fill):
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, fill=fill)
    return img


def _gradient(canvas, top, bot):
    g = Image.new("RGB", (1, canvas))
    for y in range(canvas):
        t = y / (canvas - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((canvas, canvas)).convert("RGBA")


def build_master() -> Image.Image:
    c = C
    base = Image.new("RGBA", (c, c), (0, 0, 0, 0))

    # ---- 背景圆角 tile + 渐变 ----
    tile_radius = int(c * 0.22)
    mask = Image.new("L", (c, c), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, c - 1, c - 1], radius=tile_radius, fill=255)
    base.paste(_gradient(c, BG_TOP, BG_BOT), (0, 0), mask)

    # 顶边亮线（让 tile 更"实"）
    rim = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        [0, 0, c - 1, c - 1], radius=tile_radius,
        outline=(255, 255, 255, 38), width=max(2, int(c * 0.004)),
    )
    base = Image.alpha_composite(base, Image.composite(rim, Image.new("RGBA", (c, c), (0, 0, 0, 0)), mask))

    # ---- 文档卡片几何 ----
    pw, ph = int(c * 0.46), int(c * 0.56)         # 卡片宽高
    px = (c - pw) // 2 - int(c * 0.02)            # 略左移，给右侧标签让位
    py = int(c * 0.22)
    p_radius = int(c * 0.035)

    # 卡片柔和投影
    shadow = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [px, py + int(c * 0.018), px + pw, py + ph + int(c * 0.018)],
        radius=p_radius, fill=(8, 46, 22, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(c * 0.02))
    base = Image.alpha_composite(base, shadow)

    # ---- 右侧分类索引标签（卡片右缘探出，明显可辨）----
    tab_w = int(c * 0.11)
    tab_h = int(c * 0.095)
    tab_x = px + pw - int(tab_w * 0.28)            # 卡片右缘外探更多
    gap = int(c * 0.03)
    total_h = len(TABS) * tab_h + (len(TABS) - 1) * gap
    tab_y0 = py + (ph - total_h) // 2
    for i, color in enumerate(TABS):
        ty = tab_y0 + i * (tab_h + gap)
        tab = _rounded(c, [tab_x, ty, tab_x + tab_w, ty + tab_h], int(c * 0.02), color + (255,))
        base = Image.alpha_composite(base, tab)

    # ---- 文档卡片本体（盖住标签左半，露出右侧彩色）----
    card = _rounded(c, [px, py, px + pw, py + ph], p_radius, PAPER + (255,))
    base = Image.alpha_composite(base, card)
    # 卡片描边
    border = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        [px, py, px + pw, py + ph], radius=p_radius, outline=PAPER_EDGE + (255,), width=max(2, int(c * 0.003)),
    )
    base = Image.alpha_composite(base, border)

    draw = ImageDraw.Draw(base)

    # 文档顶部品牌色条 + 「档」字
    header_h = int(ph * 0.26)
    hd = _rounded(c, [px, py, px + pw, py + header_h + p_radius], p_radius, HEADER + (255,))
    # 只保留顶部圆角，底部切平
    hd_draw = ImageDraw.Draw(hd)
    hd_draw.rectangle([px, py + header_h, px + pw, py + header_h + p_radius], fill=(0, 0, 0, 0))
    base = Image.alpha_composite(base, hd)

    draw = ImageDraw.Draw(base)
    font = ImageFont.truetype(FONT_BOLD, int(header_h * 0.66))
    bbox = draw.textbbox((0, 0), "档", font=font)
    gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (px + (pw - gw) / 2 - bbox[0], py + (header_h - gh) / 2 - bbox[1]),
        "档", font=font, fill=(255, 255, 255, 255),
    )

    # 文档正文内容线（3 条，递减宽度，最后一条短，留白）
    line_x = px + int(pw * 0.14)
    line_w_full = int(pw * 0.62)
    line_h = max(3, int(c * 0.012))
    widths = [1.0, 1.0, 0.6]
    start_y = py + header_h + int(ph * 0.16)
    line_gap = int(ph * 0.14)
    for i, wr in enumerate(widths):
        ly = start_y + i * line_gap
        draw.rounded_rectangle(
            [line_x, ly, line_x + int(line_w_full * wr), ly + line_h],
            radius=line_h // 2, fill=LINE + (255,),
        )

    return base.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    master = build_master()
    master.save(HERE / "icon.png")
    print(f"已生成 icon.png ({SIZE}×{SIZE})")
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    master.save(HERE / "icon.ico", format="ICO", sizes=sizes)
    print(f"已生成 icon.ico（{len(sizes)} 分辨率）")


if __name__ == "__main__":
    main()
