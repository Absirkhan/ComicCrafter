"""Shared test setup: repo root on sys.path and fake network clients."""

from io import BytesIO
from typing import Callable, List, Optional

import pytest
import json
from PIL import Image



def png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeImages:
    """Stands in for OpenRouterImageClient: returns queued images (or raises) and records calls."""

    def __init__(self, images: Optional[List[Image.Image]] = None, error: Optional[Exception] = None):
        self.queue = list(images or [])
        self.error = error
        self.calls: List[dict] = []
        self.total_cost = 0.0

    def generate_image(self, prompt, negative_prompt=None, aspect_ratio=None, references=(), **kwargs) -> bytes:
        self.calls.append({"prompt": prompt, "aspect_ratio": aspect_ratio, "references": list(references),
                           "negative_prompt": negative_prompt})
        if self.error:
            raise self.error
        image = self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]
        self.total_cost += 0.01
        return png_bytes(image)


class FakeVision:
    """Stands in for VisionClient: answers with answer(prompt, image) and records prompts."""

    def __init__(self, answer: Callable = lambda prompt, image: {}):
        self.answer = answer
        self.prompts: List[str] = []
        self.model = "fake-vision"
        self.total_cost = 0.0

    def ask_json(self, prompt, image, timeout=60):
        self.prompts.append(prompt)
        answer = self.answer(prompt, image[0] if isinstance(image, list) else image)
        if isinstance(answer, dict) and "Verification data: " in prompt:
            data, _ = json.JSONDecoder().raw_decode(prompt.split("Verification data: ", 1)[1])
            answer.setdefault("requirement_checks", [{"index": i, "observed": r["expected"], "matches": True} for i, r in enumerate(data["requirements"])])
            answer.setdefault("prop_checks", [{"name": p["name"], "visible": False, "observed": "", "matches": True} for p in data["props"]])
        return answer


@pytest.fixture
def noise():
    return lambda size=(400, 600): Image.effect_noise(size, 80).convert("RGB")
