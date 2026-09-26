"""
Image analysis abstraction layer.

Goal: extract lightweight, honest visual characteristics from an uploaded
photo -- dominant color, and placeholders for category/brand/features that
a real computer-vision / multimodal model would fill in.

IMPORTANT: this module never fabricates a confident "brand" or "category"
result. If no real vision provider is configured, those fields are left
"unknown" rather than guessed, so the UI can honestly say "not detected"
instead of implying a certainty the app doesn't have.

To connect a real provider later:
  1. Implement a subclass of VisionProvider (e.g. AnthropicVisionProvider,
     GoogleVisionProvider) with an `analyze(image_path)` method.
  2. Set VISION_API_PROVIDER in the environment and wire it up in
     get_vision_provider() below.
Nothing else in the matching engine needs to change -- it only consumes the
dict shape returned by `analyze()`.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


IMAGE_FEATURES_SHAPE = {
    "category": None,        # str | None -- e.g. "laptop"
    "dominant_color": None,  # str | None -- e.g. "black"
    "brand_guess": None,     # str | None -- left None unless a real vision model is wired up
    "features_text": None,   # str | None -- free-text notes a vision model could add
    "source": "none",        # which provider produced this
}


class VisionProvider(ABC):
    @abstractmethod
    def analyze(self, image_path: str) -> dict[str, Any]:
        ...


class LocalFallbackVisionProvider(VisionProvider):
    """No external API calls. Uses Pillow to estimate a dominant color only.
    Category/brand are left unknown -- we do not pretend to detect them
    without a real model."""

    _COLOR_NAMES = {
        "black": (20, 20, 20), "white": (235, 235, 235), "gray": (128, 128, 128),
        "silver": (192, 192, 192), "red": (200, 40, 40), "blue": (40, 70, 200),
        "green": (40, 140, 60), "yellow": (220, 200, 40), "brown": (120, 80, 50),
        "orange": (230, 130, 40), "pink": (230, 150, 190), "purple": (120, 60, 160),
        "beige": (222, 202, 173), "gold": (200, 170, 80),
    }

    def analyze(self, image_path: str) -> dict[str, Any]:
        result = dict(IMAGE_FEATURES_SHAPE)
        result["source"] = "local_fallback"
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img = img.convert("RGB").resize((64, 64))
                pixels = list(img.getdata())
                avg = tuple(sum(c) / len(pixels) for c in zip(*pixels))
                result["dominant_color"] = self._closest_color_name(avg)
        except Exception:
            # Corrupt file, unsupported format, etc. -- fail soft.
            pass
        return result

    def _closest_color_name(self, rgb: tuple[float, float, float]) -> str:
        best_name, best_dist = "unknown", float("inf")
        for name, ref in self._COLOR_NAMES.items():
            dist = sum((a - b) ** 2 for a, b in zip(rgb, ref))
            if dist < best_dist:
                best_dist, best_name = dist, name
        return best_name


# class AnthropicVisionProvider(VisionProvider):
#     """Sketch: call a multimodal model with the image + a structured prompt
#     asking for {category, dominant_color, brand_guess, features_text} as JSON.
#     Fill this in when VISION_API_KEY / VISION_API_PROVIDER are configured."""
#     def analyze(self, image_path: str) -> dict[str, Any]:
#         raise NotImplementedError


def get_vision_provider() -> VisionProvider:
    from app.config import settings
    if settings.VISION_API_PROVIDER == "none" or not settings.VISION_API_KEY:
        return LocalFallbackVisionProvider()
    # Extend here once a real provider is implemented, e.g.:
    # if settings.VISION_API_PROVIDER == "anthropic":
    #     return AnthropicVisionProvider(settings.VISION_API_KEY)
    return LocalFallbackVisionProvider()


def analyze_image(image_path: str) -> dict[str, Any]:
    provider = get_vision_provider()
    return provider.analyze(image_path)
