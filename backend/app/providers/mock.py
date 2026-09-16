"""Offline provider: renders a labeled gradient so the pipeline, jobs, manifest
and tour all work with NO API key. Flip LUXE_PROVIDER=openai for real images."""
import io
import re
from PIL import Image, ImageDraw, ImageFont


class MockProvider:
    def generate(self, prompt: str, size: str, control=None) -> bytes:
        m = re.match(r"(\d+)x(\d+)", size or "1536x1024")
        w, h = (int(m.group(1)), int(m.group(2))) if m else (1536, 1024)
        img = Image.new("RGB", (w, h))
        px = img.load()
        for y in range(h):                      # warm vertical gradient
            t = y / h
            r = int(0x0b + (0xe6 - 0x0b) * (1 - t) * 0.15 + 0x1a)
            g = int(0x1f + (0xdd - 0x1f) * (1 - t) * 0.15 + 0x14)
            b = int(0x33 + (0xcb - 0x33) * (1 - t) * 0.15)
            for x in range(0, w, 2):
                px[x, y] = (min(r, 255), min(g, 255), min(b, 255))
                if x + 1 < w:
                    px[x + 1, y] = (min(r, 255), min(g, 255), min(b, 255))
        d = ImageDraw.Draw(img)
        subject = ""
        for line in prompt.splitlines():
            if line.startswith("Subject:"):
                subject = line.replace("Subject: the ", "").split(" of a")[0]
                break
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 54)
            small = ImageFont.truetype("DejaVuSans.ttf", 24)
        except Exception:
            font = small = ImageFont.load_default()
        d.text((60, h // 2 - 60), subject or "Room", fill=(245, 241, 232), font=font)
        d.text((60, h // 2 + 10), "MOCK RENDER — set LUXE_PROVIDER=openai for photoreal",
               fill=(200, 162, 74), font=small)
        d.rectangle([20, 20, w - 20, h - 20], outline=(200, 162, 74), width=3)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return buf.getvalue()
