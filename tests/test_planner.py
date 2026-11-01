"""Bubble planning and the OpenRouter clients, with fake vision answers and a patched HTTP call."""

import base64
from unittest.mock import patch

from PIL import Image

from conftest import FakeVision, png_bytes
from generation.openrouter_image_client import OpenRouterImageClient
from layout.bubble_planner import default_plan, plan_bubbles

ART = Image.new("RGB", (300, 200), "white")
LINES = [("Dana (red coat)", "Hello"), ("Omer (green cap)", "Hi")]


def test_a_bare_array_answer_is_accepted():
    vision = FakeVision(lambda p, i: [{"mouth": [500, 500], "bubble": [200, 100]}, {"mouth": None, "bubble": [800, 100]}])
    plan = plan_bubbles(ART, LINES, has_caption=False, vision=vision)
    assert plan.bubbles == [(0.2, 0.1), (0.8, 0.1)]
    assert plan.speakers == [(0.5, 0.5), None]
    assert plan.caption_corner is None


def test_the_caption_corner_is_fixed_in_the_prompt_and_each_speakers_look_is_shown():
    answer = {"lines": [{"mouth": [1, 1], "bubble": [2, 2]}] * 2, "caption": "top-right"}
    vision = FakeVision(lambda p, i: answer)
    assert plan_bubbles(ART, LINES, has_caption=True, vision=vision).caption_corner == "top-right"
    assert "caption box goes in the top-left corner" in vision.prompts[0]
    assert "Dana (red coat)" in vision.prompts[0] and "Omer (green cap)" in vision.prompts[0]


def test_reserved_corners_are_kept_bubble_free():
    vision = FakeVision(lambda p, i: [{"bubble": [1, 1]}])
    plan_bubbles(ART, LINES[:1], False, rtl=True, vision=vision, reserved_corners=["bottom-left"])
    assert "Caption boxes may cover the bottom-left corners" in vision.prompts[0]
    assert "right-to-left" in vision.prompts[0]


def test_a_failed_or_short_answer_falls_back_to_none():
    def broken(prompt, image):
        raise RuntimeError("HTTP 500")
    assert plan_bubbles(ART, LINES, False, vision=FakeVision(broken)) is None
    assert plan_bubbles(ART, LINES, False, vision=FakeVision(lambda p, i: [{"bubble": [1, 1]}])) is None
    assert default_plan(2).bubbles == [(0.25, 0.18), (0.75, 0.18)]


def test_the_image_client_sends_reference_images_and_records_cost():
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes(ART)).decode()
    body = {"usage": {"cost": 0.02}, "choices": [{"message": {"images": [{"image_url": {"url": data_url}}]}}]}
    client = OpenRouterImageClient(api_key="test-only", model="test-model")
    with patch("generation.openrouter_image_client.requests.post") as post:
        post.return_value.json.return_value = body
        assert client.generate_image("scene", aspect_ratio="2:3", references=["photo-ref", "sheet-ref"]) == png_bytes(ART)
        content = post.call_args.kwargs["json"]["messages"][0]["content"]
        assert content[0] == {"type": "text", "text": "scene"}
        assert [part["image_url"]["url"] for part in content[1:]] == ["photo-ref", "sheet-ref"]

        client.generate_image("plain scene")  # without references the content stays a plain string
        assert post.call_args.kwargs["json"]["messages"][0]["content"] == "plain scene"
    assert client.usage == [{"model": "test-model", "cost": 0.02}] * 2
    assert round(client.total_cost, 4) == 0.04


def test_protected_subjects_are_returned_by_the_existing_vision_call():
    answer = {'lines': [{'mouth': [700, 500], 'bubble': [200, 100]}],
              'protected': [[600, 200, 200, 300], [100, 100, -1, 50], ['invalid']]}
    vision = FakeVision(lambda p, i: answer)
    plan = plan_bubbles(ART, LINES[:1], False, vision=vision)
    assert plan.protected == [(0.6, 0.2, 0.2, 0.3)]
    assert len(vision.prompts) == 1
    assert 'including companions' in vision.prompts[0]


def test_review_client_supports_text_only_and_reference_comparisons():
    from generation.vision_client import VisionClient
    client = VisionClient(api_key='test-only')
    body = {'usage': {'cost': .001}, 'choices': [{'message': {'content': '{"ok":true}'}}]}
    with patch('generation.vision_client.requests.post') as post:
        post.return_value.json.return_value = body
        client.ask_json('Review story', None)
        content = post.call_args.kwargs['json']['messages'][0]['content']
        assert [p['type'] for p in content] == ['text']
        client.ask_json('Compare references', [ART, 'data:sheet'])
        content = post.call_args.kwargs['json']['messages'][0]['content']
        assert [p['type'] for p in content] == ['text', 'image_url', 'image_url']
        assert content[-1]['image_url']['url'] == 'data:sheet'
    assert len(client.usage) == 2


def test_art_review_uses_stronger_model_and_meters_it(monkeypatch):
    from generation.vision_client import VisionClient, ART_REVIEW_MODEL, DEFAULT_MODEL
    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)
    client = VisionClient(api_key="test-only")
    body = {"usage": {"cost": .002}, "choices": [{"message": {"content": '{"ok":true}'}}]}
    with patch("generation.vision_client.requests.post") as post:
        post.return_value.json.return_value = body
        client.ask_art_json("Inspect action", ART)
        assert post.call_args.kwargs["json"]["model"] == ART_REVIEW_MODEL
        assert client.usage == [{"model": ART_REVIEW_MODEL, "cost": .002}]
        client.ask_json("Review story")
        assert post.call_args.kwargs["json"]["model"] == DEFAULT_MODEL
    assert VisionClient(api_key="test-only", model="explicit").art_model == "explicit"
