"""Generate the Mo's Place Radio logo asset for the Studio banner."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_logo(output_path: Path) -> None:
    size = 128
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.ellipse((8, 8, size - 8, size - 8), fill=(45, 107, 159, 255))
    draw.ellipse((20, 20, size - 20, size - 20), fill=(20, 28, 40, 255))
    draw.ellipse((30, 30, size - 30, size - 30), outline=(61, 139, 253, 255), width=3)

    try:
        font = ImageFont.truetype("segoeui.ttf", 42)
    except OSError:
        font = ImageFont.load_default()

    draw.text((size // 2, size // 2), "M", fill=(232, 237, 245, 255), font=font, anchor="mm")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "PNG")


if __name__ == "__main__":
    logo_file = Path(__file__).resolve().parent / "logo.png"
    create_logo(logo_file)
    print(f"Created {logo_file}")
