"""Preserve explicit limb and detail-shot restrictions independently of model extraction."""
import re


def scene_requirements(scene, requirements=()):
    result = list(requirements)
    sides = set(re.findall(r'\b(right|left)\s+hand\b', scene, re.I))
    sides = {s.lower() for s in sides}
    derived = []
    if len(sides) == 1:
        derived.append({'subject': 'Hero', 'attribute': 'hand', 'expected': sides.pop()})
    detail = re.search(r'\bonly\b([^.!?]{0,180}?)\b(?:in frame|visible)\b', scene, re.I)
    detail = detail or re.search(r'\bonly\b([^.!?]{1,180})', scene, re.I)
    tagged = re.search(r'\b(hands?|feet|foot)[ -]only\b', scene, re.I)
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
