"""Bundled presentation artwork shared by studio, PowerPoint and PDF exports."""
from pathlib import Path

from .visual.design_tokens import slide_theme_preset

ASSETS = Path(__file__).parent / 'assets'


def theme_background_path(theme):
    preset = slide_theme_preset(theme)
    asset = preset.get('background_asset')
    return ASSETS / Path(asset).name if asset else None


def add_theme_background(slide, theme, width, height):
    path = theme_background_path(theme)
    if path:
        picture = slide.shapes.add_picture(str(path), 0, 0, width=width, height=height)
        picture.name = f"Theme background: {slide_theme_preset(theme)['name']}"


def theme_font_path(theme):
    asset = slide_theme_preset(theme).get('font_asset')
    return ASSETS / Path(asset).name if asset else None
