import io

import pytest
from app.export import ExportService
from app.redaction import RedactionService
from PIL import Image


@pytest.mark.asyncio
async def test_apply_redaction_rectangles_pixels():
    # Create a white 100x100 image
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))

    # Redact a 20x20 square starting at (40,40)
    regions = [{"x": 40, "y": 40, "width": 20, "height": 20, "color": "black"}]

    service = RedactionService()
    redacted = service._apply_redaction_rectangles(img, regions)

    # Check a few pixels inside the redaction are black
    for px, py in [(45, 45), (50, 50), (55, 55)]:
        r, g, b = redacted.getpixel((px, py))
        assert r == 0 and g == 0 and b == 0

    # Check outside pixel remains white
    r, g, b = redacted.getpixel((10, 10))
    assert (r, g, b) == (255, 255, 255)


def test_apply_redaction_rectangles_local_pixels():
    # Create a white 60x40 image
    img = Image.new("RGB", (60, 40), color=(255, 255, 255))

    # Redact two regions
    regions = [
        {"x": 5, "y": 5, "width": 10, "height": 10, "color": "black"},
        {"x": 30, "y": 10, "width": 20, "height": 15, "color": "black"},
    ]

    es = ExportService()
    out = es._apply_redaction_rectangles_local(img, regions)

    # Inside first region
    assert out.getpixel((10, 10)) == (0, 0, 0)
    # Inside second region
    assert out.getpixel((35, 15)) == (0, 0, 0)
    # Outside both regions
    assert out.getpixel((0, 0)) == (255, 255, 255)
