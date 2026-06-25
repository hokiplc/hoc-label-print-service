"""Base abstraction for label templates. Templates render structured job data into a
PIL Image; they never execute or interpret caller-supplied markup or code."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image, ImageFont

from app.config import TemplateConstants

# 300 dpi-equivalent pixels-per-mm used by brother_ql raster conversion for QL printers.
PX_PER_MM = 11.81


def mm_to_px(mm: float) -> int:
    return round(mm * PX_PER_MM)


class LabelTemplate(ABC):
    name: str = ""

    def __init__(self, font_dir: str, constants: TemplateConstants) -> None:
        self.font_dir = Path(font_dir)
        self.constants = constants

    def load_font(self, filename: str, size: int) -> ImageFont.FreeTypeFont:
        path = self.font_dir / filename
        if path.is_file():
            return ImageFont.truetype(str(path), size)
        return ImageFont.load_default()

    @abstractmethod
    def render(self, data: dict, label_width_mm: int) -> Image.Image:
        """Render the label and return a PIL Image in printer-ready orientation."""
        raise NotImplementedError
