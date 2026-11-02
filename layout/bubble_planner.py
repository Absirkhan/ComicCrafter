"""Vision-based placement of speech bubbles relative to the speaking characters."""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from PIL import Image

from generation.vision_client import DEFAULT_MODEL, VisionClient, encode_image  # noqa: F401
from utils import get_logger

logger = get_logger(__name__)

Point = Tuple[float, float]  # normalized 0-1 (x, y)


@dataclass
class BubblePlan:
    """Where to put a panel's bubbles.

    Attributes:
        speakers: For each dialogue line, the speaker's mouth position (None if not visible)
        bubbles: For each dialogue line, the bubble center in empty space
        caption_corner: "top-left" or "top-right" as chosen by the model; None lets the renderer
            start from the corner read first
    """
    speakers: List[Optional[Point]]
    bubbles: List[Point]
    caption_corner: Optional[str] = None
    protected: List[Tuple[float, float, float, float]] = field(default_factory=list)
    protected_checked: bool = False


def _prompt(
    lines: List[Tuple[str, str]], has_caption: bool, rtl: bool = False, reserved_corners: Sequence[str] = ()
) -> str:
    keep_clear = (
        f"\nCaption boxes may cover the {' and '.join(reserved_corners)} corners; keep bubbles out of them."
        if reserved_corners else ""
    )
    order = "further right (this comic reads right-to-left)" if rtl else "further left"
    numbered = "\n".join(f'{i + 1}. {speaker or "unknown"}: "{text}"' for i, (speaker, text) in enumerate(lines))
    return f"""This is a comic book panel. Speech bubbles will be drawn on it for these lines:
{numbered}

For each line, find the speaking character in the image and return:
- "mouth": [x, y] of that character's mouth, or null if the speaker isn't visible
- "bubble": [x, y] center for the bubble in EMPTY space near the speaker (sky, background, wall),
  never covering any face or the main action, ideally above or beside the speaker's head.
  Bubbles for different lines must not overlap; earlier lines go higher and {order}.
{f'A narration caption box goes in the {"top-right" if rtl else "top-left"} corner; keep bubbles out of it.' if has_caption else ''}{keep_clear}

Coordinates are integers from 0 to 1000 (0,0 is top-left, 1000,1000 bottom-right).
Also identify tight protected rectangles [x, y, width, height] around all faces (including companions),\nimportant props and hands performing the focal action. Use the same 0-1000 coordinate system.\nRespond with only JSON: {{"lines": [{{"mouth": [x, y], "bubble": [x, y]}}], "protected": [[x, y, width, height]]}}"""


_encode = encode_image


def _point(value) -> Optional[Point]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    x, y = (min(1.0, max(0.0, float(v) / 1000)) for v in value)
    return (x, y)


def plan_bubbles(
    image: Image.Image,
    lines: List[Tuple[str, str]],
    has_caption: bool,
    rtl: bool = False,
    vision: Optional[VisionClient] = None,
    reserved_corners: Sequence[str] = (),
    precise: bool = False,
) -> Optional[BubblePlan]:
    """Ask a vision model where each speaker is and where their bubble fits.

    Args:
        image: Panel image
        lines: (speaker, text) for each dialogue line; speaker may include a short look description
        has_caption: Whether the panel also has a narration caption (kept in the reading-first corner)
        rtl: Whether the comic reads right-to-left
        vision: Vision client (its cost is recorded there); a default VisionClient if None
        reserved_corners: Corners taken by other boxes (e.g. a dedication note), kept bubble-free

    Returns:
        BubblePlan, or None if the request or response failed
    """
    vision = vision or VisionClient()
    try:
        prompt = _prompt(lines, has_caption, rtl, reserved_corners)
        if precise:
            prompt += ('\nA first layout could not fit. Recheck tight rectangles around actual faces and focal '
                       'hands/props; do not mark whole bodies or empty background as protected. '
                       'An off-panel speaker has mouth:null. Inspect the whole panel for usable empty space.')
        ask = getattr(vision, 'ask_art_json', vision.ask_json) if precise else vision.ask_json
        data = ask(prompt, image)
        if isinstance(data, list):
            data = {"lines": data}

        planned = data.get("lines", [])
        if len(planned) < len(lines):
            raise ValueError(f"expected {len(lines)} lines, got {len(planned)}")

        bubbles = [_point(p.get("bubble")) for p in planned[:len(lines)]]
        if any(b is None for b in bubbles):
            raise ValueError("missing bubble position")

        protected = []
        rectangles = data.get("protected")
        for rect in (rectangles[:16] if isinstance(rectangles, list) else []):
            if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                continue
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1000 for v in rect):
                continue
            x, y, w, h = rect
            if w > 0 and h > 0:
                protected.append((x / 1000, y / 1000, min(w, 1000 - x) / 1000, min(h, 1000 - y) / 1000))
        corner = data.get("caption")
        return BubblePlan(
            speakers=[_point(p.get("mouth")) for p in planned[:len(lines)]],
            bubbles=bubbles,
            protected=protected,
            protected_checked=isinstance(rectangles, list) and len(rectangles) == len(protected),
            caption_corner=corner if corner in ("top-left", "top-right") else None,
        )
    except Exception as e:
        logger.warning(f"Bubble planning with {vision.model} failed; using default placement: {e}")
        return None


def default_plan(num_lines: int) -> BubblePlan:
    """Fallback placement: bubbles across the top, tails pointing down."""
    bubbles = [((i + 0.5) / max(1, num_lines), 0.18) for i in range(num_lines)]
    return BubblePlan(speakers=[None] * num_lines, bubbles=bubbles)
