"""OpenRouter vision client: asks a multimodal model about an image and parses its JSON answer."""

import base64
import json
import os
from io import BytesIO
from typing import Dict, List, Optional, Union

import requests
from PIL import Image

from utils import get_logger

logger = get_logger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3.1-flash-lite"
ART_REVIEW_MODEL = "google/gemini-3.8-flash"


def encode_image(image: Image.Image) -> str:
    """JPEG data URL for an image, as vision models accept it."""
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def parse_json(content: str) -> Union[Dict, List]:
    """The JSON object or array in a model reply, ignoring any prose or code fences around it."""
    content = content.strip()
    # Models sometimes return a bare array instead of the wrapping object
    start = min(i for i in (content.find("{"), content.find("[")) if i != -1)
    return json.loads(content[start:max(content.rfind("}"), content.rfind("]")) + 1])


class VisionClient:
    """Client for JSON questions about an image through OpenRouter, with spend tracking."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize the vision client.

        Args:
            api_key: OpenRouter API key. If None, uses OPENROUTER_API_KEY
            model: Vision model id. If None, uses OPENROUTER_VISION_MODEL
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_VISION_MODEL", DEFAULT_MODEL)
        self.art_model = model or os.getenv("OPENROUTER_VISION_MODEL", ART_REVIEW_MODEL)
        self.total_cost = 0.0  # USD across all calls, from OpenRouter's usage report
        self.usage: List[Dict] = []  # {"model", "cost"} per call

    def ask_json(self, prompt: str, image=None, timeout: int = 60) -> Union[Dict, List]:
        """Text review and bubble placement use the lightweight model."""
        return self._ask_json(prompt, image, timeout, self.model)

    def ask_art_json(self, prompt: str, image, timeout: int = 90) -> Union[Dict, List]:
        """Use a stronger visual reviewer, with the same metering and no additional call."""
        return self._ask_json(prompt, image, timeout, self.art_model)

    def _ask_json(self, prompt, image, timeout, model):
        content = [{"type": "text", "text": prompt}]
        images = image if isinstance(image, (list, tuple)) else ([] if image is None else [image])
        for item in images:
            content.append({"type": "image_url", "image_url": {"url": item if isinstance(item, str) else encode_image(item)}})
        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": content,
                }],
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        cost = float(body.get("usage", {}).get("cost") or 0)
        self.total_cost += cost
        self.usage.append({"model": model, "cost": cost})
        return parse_json(body["choices"][0]["message"]["content"])
