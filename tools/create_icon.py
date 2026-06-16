from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
PNG_PATH = ASSET_DIR / "12grid-live-monitor-icon.png"
ICO_PATH = ASSET_DIR / "12grid-live-monitor-icon.ico"


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    size = 1024
    image = Image.new("RGBA", (size, size), (10, 12, 18, 255))
    draw = ImageDraw.Draw(image)

    for y in range(size):
        shade = int(24 + (y / size) * 34)
        draw.line([(0, y), (size, y)], fill=(8, shade, 42, 255))

    margin = 96
    panel = [margin, margin, size - margin, size - margin]
    draw.rounded_rectangle(panel, radius=92, fill=(18, 24, 34, 255), outline=(66, 211, 255, 255), width=10)

    grid_margin = 165
    gap = 18
    cell = (size - grid_margin * 2 - gap * 3) // 4
    colors = [
        (255, 64, 90, 255),
        (38, 198, 218, 255),
        (96, 232, 132, 255),
        (255, 196, 64, 255),
    ]
    for row in range(3):
        for col in range(4):
            x = grid_margin + col * (cell + gap)
            y = grid_margin + row * (cell + gap)
            fill = (30, 38, 50, 255)
            outline = colors[(row + col) % len(colors)]
            draw.rounded_rectangle([x, y, x + cell, y + cell], radius=18, fill=fill, outline=outline, width=7)
            triangle = [
                (x + cell * 0.42, y + cell * 0.34),
                (x + cell * 0.42, y + cell * 0.66),
                (x + cell * 0.68, y + cell * 0.50),
            ]
            draw.polygon(triangle, fill=outline)

    badge = [size - 310, size - 275, size - 105, size - 105]
    draw.rounded_rectangle(badge, radius=46, fill=(255, 42, 82, 255), outline=(255, 255, 255, 230), width=6)
    font = load_font(86)
    draw.text((badge[0] + 42, badge[1] + 38), "12", font=font, fill=(255, 255, 255, 255))

    image.save(PNG_PATH)
    image.save(
        ICO_PATH,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(ICO_PATH)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/msjhbd.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
