"""Preserve explicit limb and detail-shot restrictions independently of model extraction."""
import re


_HAND_FOCUS = re.compile(
    r"\b(hands?)[ -]detail\b|\bdetail (?:shot )?of (?:\w+'s |his |her |their |the |a |one )?(?:right |left )?(hands?)\b"
    r"|\bclose-up of (?:\w+'s |his |her |their |the |a |one )?(?:right |left )?(hands?)\b", re.I)
_BODY_WORDS = re.compile(r"\b(face|faces|head|eyes|torso|chest|shoulders?|waist|body|expression|smile|smiles)\b", re.I)
_NEGATED_BODY = re.compile(r"\b(?:no|without|not|excluding|never)\b[^.!?]{0,40}?$", re.I)


class _Tag:
    """A tagged-crop match standing in for the hands-only regex match."""
    def __init__(self, kind):
        self.kind = kind

    def group(self, _):
        return self.kind


def _hand_focus(scene):
    """A hand detail named as such ("hand detail", "close-up of Hero's hand"), when no body part is shown too.

    A face, head, torso or expression mentioned positively anywhere in the scene keeps the shot a normal
    close-up; "no face" or "without the torso" does not.
    """
    match = _HAND_FOCUS.search(scene)
    if not match:
        return None
    for body in _BODY_WORDS.finditer(scene):
        if not _NEGATED_BODY.search(scene[:body.start()]):
            return None
    return _Tag(next(g for g in match.groups() if g))


def scene_requirements(scene, requirements=()):
    result = list(requirements)
    sides = set(re.findall(r'\b(right|left)\s+hand\b', scene, re.I))
    sides = {s.lower() for s in sides}
    derived = []
    if len(sides) == 1:
        derived.append({'subject': 'Hero', 'attribute': 'hand', 'expected': sides.pop()})
    detail = re.search(r'\bonly\b([^.!?]{0,180}?)\b(?:in frame|visible)\b', scene, re.I)
    detail = detail or re.search(r'\bonly\b([^.!?]{1,180})', scene, re.I)
    tagged = re.search(r'\b(hands?|feet|foot)[ -]only\b', scene, re.I) or _hand_focus(scene)
    if tagged:
        kind = 'hand' if tagged.group(1).lower().startswith('hand') else 'feet'
        derived.append({'subject': 'frame', 'attribute': 'framing', 'expected': f'{kind}_detail_only'})
    elif detail:
        allowed = detail.group(1).lower()
        # Restrict anatomy only for an explicit limb-only crop, never a general close-up.
        if not re.search(r'\b(face|head|torso|body|shoulder|waist)\b', allowed):
            kind = 'hand' if re.search(r'\bhands?\b', allowed) else 'feet' if re.search(r'\b(feet|foot|legs?|boots?)\b', allowed) else None
            if kind:
                derived.append({'subject': 'frame', 'attribute': 'framing', 'expected': f'{kind}_detail_only'})
    for item in derived:
        result = [r for r in result if not (r['subject'] == item['subject'] and r['attribute'] == item['attribute'])]
        result.append(item)
    return result
