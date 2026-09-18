"""Batch contact-sheet rendering for first-pass agent review."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                pass
    return ImageFont.load_default()


def build_contact_sheet(items: Iterable[tuple[str, str | Path]], destination: str | Path, columns: int = 4, cell_width: int = 260) -> Path:
    rows = list(items)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        image = Image.new("RGB", (cell_width, 80), "#121722")
        ImageDraw.Draw(image).text((16, 20), "No samples", fill="white", font=_font(20))
        image.save(destination, quality=90)
        return destination
    cell_height = int(cell_width * 16 / 9) + 42
    row_count = (len(rows) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, row_count * cell_height), "#0c1018")
    draw = ImageDraw.Draw(sheet)
    label_font = _font(18)
    for index, (label, source) in enumerate(rows):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        try:
            with Image.open(source) as opened:
                thumb = opened.convert("RGB")
                thumb.thumbnail((cell_width - 12, cell_height - 48))
                paste_x = x + (cell_width - thumb.width) // 2
                sheet.paste(thumb, (paste_x, y + 4))
        except Exception:
            draw.rectangle((x + 6, y + 6, x + cell_width - 6, y + cell_height - 44), fill="#2a3140")
            draw.text((x + 18, y + 24), "UNREADABLE", fill="#ffb56b", font=label_font)
        draw.rectangle((x, y + cell_height - 40, x + cell_width, y + cell_height), fill="#111827")
        draw.text((x + 10, y + cell_height - 32), label, fill="#e8f1ff", font=label_font)
    sheet.save(destination, quality=90)
    return destination
