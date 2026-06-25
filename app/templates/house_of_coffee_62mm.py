"""house-of-coffee-62mm: portrait coffee bag label for 62mm continuous Brother QL media."""
from __future__ import annotations

from PIL import Image, ImageDraw

from .base import LabelTemplate, mm_to_px

WIDTH_MM = 62
LABEL_HEIGHT_MM = 100  # nominal length for continuous roll; content can grow this.


class HouseOfCoffee62mmTemplate(LabelTemplate):
    name = "house-of-coffee-62mm"

    def render(self, data: dict, label_width_mm: int) -> Image.Image:
        c = self.constants
        width_px = mm_to_px(label_width_mm or WIDTH_MM)
        pad = c.padding_px
        border = c.border_width_px
        spacing = c.line_spacing_px

        header_font = self.load_font("DejaVuSans-Bold.ttf", c.header_font_size)
        product_font = self.load_font("DejaVuSans-Bold.ttf", c.product_font_size)
        attr_font = self.load_font("DejaVuSans.ttf", c.attr_font_size)
        footer_font = self.load_font("DejaVuSans.ttf", c.footer_font_size)

        # First pass on a tall scratch canvas to measure content, then crop to fit.
        scratch_height = mm_to_px(LABEL_HEIGHT_MM) * 2
        img = Image.new("RGB", (width_px, scratch_height), "white")
        draw = ImageDraw.Draw(img)

        y = pad

        # --- Header / logo zone ---
        header_text = "HOUSE OF COFFEE"
        y = self._draw_centered(draw, header_text, header_font, width_px, y)
        y += spacing
        draw.line([(pad, y), (width_px - pad, y)], fill="black", width=2)
        y += spacing * 2

        # --- Product name ---
        product_name = data.get("product_name", "").upper()
        y = self._draw_wrapped_centered(draw, product_name, product_font, width_px, y, pad, spacing)
        y += spacing * 2

        # --- Boxed attribute section ---
        box_top = y
        attr_rows = [
            ("Grind", data.get("grind", "")),
            ("Weight", data.get("weight", "")),
            ("Strength", data.get("strength", "")),
            ("Flavour", data.get("flavour", "")),
            ("Roast", data.get("roast", "")),
        ]
        attr_rows = [(label, value) for label, value in attr_rows if value]

        inner_y = box_top + pad
        for label, value in attr_rows:
            line = f"{label}: {value}"
            draw.text((pad * 2, inner_y), line, font=attr_font, fill="black")
            bbox = draw.textbbox((pad * 2, inner_y), line, font=attr_font)
            inner_y = bbox[3] + spacing
        box_bottom = inner_y + pad - spacing

        draw.rectangle(
            [(pad, box_top), (width_px - pad, box_bottom)],
            outline="black",
            width=border,
        )
        y = box_bottom + spacing * 3

        # --- Best-before line ---
        best_before = data.get("best_before", "")
        if best_before:
            footer_text = f"Best before: {best_before}"
            y = self._draw_centered(draw, footer_text, footer_font, width_px, y)
            y += spacing

        y += pad
        final_height = max(y, mm_to_px(20))
        return img.crop((0, 0, width_px, final_height))

    @staticmethod
    def _draw_centered(draw: ImageDraw.ImageDraw, text: str, font, width_px: int, y: int) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = max((width_px - text_width) // 2, 0)
        draw.text((x, y), text, font=font, fill="black")
        return bbox[3] - bbox[1] + y

    @staticmethod
    def _draw_wrapped_centered(draw, text: str, font, width_px: int, y: int, pad: int, spacing: int) -> int:
        max_width = width_px - 2 * pad
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x = max((width_px - line_width) // 2, 0)
            draw.text((x, y), line, font=font, fill="black")
            y = bbox[3] - bbox[1] + y + spacing
        return y
