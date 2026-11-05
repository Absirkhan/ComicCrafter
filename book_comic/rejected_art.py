"""Opt-in record of art the vision check rejected, for reviewing why images fail.

Each rejected draw becomes <stage>_p<panel>_d<draw>.png and a .json beside it holding only fixed
check names and the vision check's own short observations of the failed checks. A rejected draw the
renderer kept anyway (book_comic.best_draw fallback) gets "selected": true in its .json. Prompt text,
requirement text and character names never reach the JSON. Saving never changes the render.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

CHECK_NAMES = ("has_text", "bad_anatomy", "identity_mismatch", "design_mismatch", "scene_mismatch",
               "requirement_mismatch", "prop_mismatch", "prop_shape_mismatch", "figure_visible")
UNAVAILABLE = "check_unavailable"
MAX_SAVED = 12
MAX_REASONS = 8
REASON_CHARS = 300


def failed_checks(found: Dict, unavailable: bool = False) -> List[str]:
    """Names of the truthy check flags, plus check_unavailable when the check could not run."""
    names = [k for k in CHECK_NAMES if found.get(k)]
    return names + [UNAVAILABLE] if unavailable else names


def _requirement_failed(check: Dict, requirement: Dict) -> bool:
    observed = str(check.get("observed", "")).strip().lower()
    expected = str(requirement.get("expected", "")).strip().lower()
    if observed == "not_visible" and requirement.get("attribute") == "design":
        return False
    if requirement.get("attribute") == "framing":
        return False  # a limb-only framing row is observed only, never a reason (art_check.inspect_art)
    # A literal contradiction the checker waved through with matches=true: a hand side, or a vocabulary pose/state
    # word other than the expected one ("standing" for kneeling; free text like "the door is wide open" is not one).
    literal = (requirement.get("attribute") == "hand"
               or (requirement.get("attribute") in ("pose", "state") and expected in LITERAL_STATES and observed in LITERAL_STATES))
    return check.get("matches") is not True or observed == "not_visible" or (literal and observed != expected)


# A pose or state the checker cannot wave through with matches=true (art_check.inspect_art uses the same set).
LITERAL_STATES = {"standing", "kneeling", "seated", "crouching", "open", "closed", "flat", "upright"}
# The checker's fixed answers for pose, state, hand side and framing: safe to show next to each other.
VOCABULARY = {"standing", "kneeling", "seated", "crouching", "open", "closed", "flat", "upright", "right", "left",
              "ambiguous", "not_visible", "hand_detail_only", "feet_detail_only", "body_visible"}
VOCABULARY_ATTRIBUTES = ("pose", "state", "hand", "framing")


def _requirement_reason(check: Dict, requirement: Dict) -> object:
    """"state: expected open, saw closed" when both sides are fixed vocabulary; otherwise the observation as written."""
    observed = check.get("observed")
    expected = str(requirement.get("expected", "")).strip().lower()
    seen = str(observed or "").strip().lower()
    attribute = requirement.get("attribute")
    if attribute in VOCABULARY_ATTRIBUTES and expected in VOCABULARY and seen in VOCABULARY:
        return f"{attribute}: expected {expected.replace('_', ' ')}, saw {seen.replace('_', ' ')}"
    return observed


def unmet_requirements(found: Dict, requirements: Sequence[Dict]) -> List[Tuple[Dict, Dict]]:
    """(check, requirement) for every row the check saw unmet, the rows paired by the check's own index.

    The one definition shared by the rejected-art reasons, the revision and the fresh third draw: a row fails when
    the checker says so, when the state is hidden, or when a literal contradiction (hand side, pose, state) was waved
    through with matches=true; a framing row never fails (observed only)."""
    pairs = []
    for position, check in enumerate(found.get("requirement_checks") or []):
        if not isinstance(check, dict):
            continue
        index = check.get("index") if type(check.get("index")) is int else position  # a raw list is in the brief's order
        if 0 <= index < len(requirements) and _requirement_failed(check, requirements[index]):
            pairs.append((check, requirements[index]))
    return pairs


def _candidates(found: Dict, requirements: Sequence[Dict]) -> Iterable[object]:
    if found.get("requirement_mismatch"):
        for check, requirement in unmet_requirements(found, requirements):
            yield _requirement_reason(check, requirement)
    if found.get("prop_mismatch") or found.get("prop_shape_mismatch"):
        for check in found.get("prop_checks") or []:
            if isinstance(check, dict) and check.get("visible") is True and check.get("matches") is False:
                yield check.get("observed")
    if any(found.get(k) for k in CHECK_NAMES):
        yield from found.get("corrections") or []


def failure_reasons(found: Dict, prompt: str = "", requirements: Sequence[Dict] = (), names: Sequence[str] = ()) -> List[str]:
    """The vision check's own short observations for failed checks only, without echoes of the brief.

    A string that repeats the prompt or a requirement, or mentions a character or prop name, is left out.
    """
    brief = prompt.lower()
    echoes = {str(r.get(k, "")).strip().lower() for r in requirements for k in ("subject", "expected")}
    blocked = [n.strip().lower() for n in names if n and n.strip()]
    reasons: List[str] = []
    for text in _candidates(found, requirements):
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.strip()[:REASON_CHARS]
        low = text.lower()
        if low in brief or low in echoes or any(n in low for n in blocked) or text in reasons:
            continue
        reasons.append(text)
        if len(reasons) == MAX_REASONS:
            break
    if not reasons and failed_checks(found):
        # The check failed the draw without a usable observation: say so, so the rejection can still be reviewed.
        reasons.append("no observation returned for: " + ", ".join(failed_checks(found)))
    return reasons


class RejectedArtSaver:
    """Writes at most MAX_SAVED rejected draws into one directory; errors are logged and swallowed."""

    def __init__(self, directory: Optional[Path], names: Sequence[str] = (), limit: int = MAX_SAVED):
        self.directory = Path(directory) if directory else None
        self.names = tuple(names)
        self.limit = limit
        self.saved = 0

    def hook(self, stage: str, panel: int = 0):
        """A callback for one draw loop, or None when nothing is recorded."""
        if self.directory is None:
            return None

        def on_reject(draw: int, art: Image.Image, found: Dict, unavailable: bool = False,
                      prompt: str = "", requirements: Sequence[Dict] = ()) -> None:
            self.save(stage, panel, draw, art, found, unavailable, prompt, requirements)
        return on_reject

    def select_hook(self, stage: str, panel: int = 0):
        """A callback marking which rejected draw of one loop was kept, or None when nothing is recorded."""
        if self.directory is None:
            return None
        return lambda draw: self.mark_selected(stage, panel, draw)

    def mark_selected(self, stage, panel, draw) -> None:
        """Add "selected": true to a saved draw's .json; a draw that was not saved is left alone."""
        path = self.directory / f"{stage}_p{int(panel)}_d{int(draw)}.json" if self.directory else None
        try:
            if path is None or not path.is_file():
                return
            record = json.loads(path.read_text(encoding="utf-8"))
            record["selected"] = True
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # never let review bookkeeping change the render
            logger.debug(f"Could not mark the selected draw: {e}")

    def save(self, stage, panel, draw, art, found, unavailable=False, prompt="", requirements=()) -> None:
        if self.directory is None or self.saved >= self.limit:
            return
        self.saved += 1
        try:
            stem = f"{stage}_p{int(panel)}_d{int(draw)}"
            record = {"stage": stage, "panel": int(panel), "draw": int(draw),
                      "failed_checks": failed_checks(found, unavailable),
                      "reasons": failure_reasons(found, prompt, requirements, self.names)}
            self.directory.mkdir(parents=True, exist_ok=True)
            art.convert("RGB").save(self.directory / f"{stem}.png", format="PNG")
            (self.directory / f"{stem}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # never let review bookkeeping change the render
            logger.debug(f"Could not save rejected art: {e}")


def report(on_reject, draw, art, found, unavailable=False, prompt="", requirements=()) -> None:
    """Call an optional reject hook without ever raising."""
    if on_reject is None:
        return
    try:
        on_reject(draw, art, found, unavailable, prompt, requirements)
    except Exception as e:
        logger.debug(f"Rejected-art hook failed: {e}")


def report_selected(on_select, draw) -> None:
    """Call an optional selected-draw hook without ever raising."""
    if on_select is None:
        return
    try:
        on_select(draw)
    except Exception as e:
        logger.debug(f"Selected-draw hook failed: {e}")
