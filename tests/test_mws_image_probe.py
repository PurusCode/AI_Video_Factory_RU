import base64
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.mws_image_probe import (
    _decode_b64,
    build_config,
    extract_inline_image,
    read_env_file,
    validate_image_bytes,
)


def png_bytes(width=800, height=450):
    image = Image.new("RGB", (width, height), (25, 45, 70))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class ImageProbeTests(unittest.TestCase):
    def test_env_file_parser_quotes_and_comments(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text('A="hello world"\nB=token # note\n# skipped\n', encoding="utf-8")
            self.assertEqual(read_env_file(path), {"A": "hello world", "B": "token"})

    def test_openai_b64_json_image(self):
        raw = png_bytes()
        payload = {"data": [{"b64_json": base64.b64encode(raw).decode()}]}
        result = extract_inline_image(payload)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], raw)

    def test_data_uri(self):
        raw = png_bytes()
        result = _decode_b64("data:image/png;base64," + base64.b64encode(raw).decode())
        self.assertEqual(result[0], raw)
        self.assertEqual(result[1], "png")

    def test_gemini_native_inline_data_shape(self):
        raw = png_bytes()
        payload = {"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "image/png", "data": base64.b64encode(raw).decode()
        }}]}}]}
        result = extract_inline_image(payload)
        self.assertEqual(result[0], raw)
        self.assertEqual(result[1], "png")

    def test_chat_completions_content_image_shape(self):
        raw = png_bytes()
        payload = {"choices": [{"message": {"content": [{
            "type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(raw).decode()}
        }]}}]}
        self.assertEqual(extract_inline_image(payload)[0], raw)

    def test_valid_image_dimensions(self):
        ok, fmt, width, height = validate_image_bytes(png_bytes())
        self.assertTrue(ok)
        self.assertEqual((fmt, width, height), ("PNG", 800, 450))

    def test_reject_non_image_bytes(self):
        ok, reason, *_ = validate_image_bytes(b"not an image")
        self.assertFalse(ok)
        self.assertIn("invalid_image", reason)


if __name__ == "__main__":
    unittest.main()
