"""Draw comic pages from page scripts using ComicCrafter's image, layout and lettering code."""

import base64
import logging
import math
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageOps, ImageDraw
from PIL.PngImagePlugin import PngInfo

from book_comic.scene_requirements import scene_requirements
from book_comic.art_check import ArtCheckError, draw_checked, request_art
from book_comic.rejected_art import RejectedArtSaver
from book_comic.image_prompts import NO_TEXT, panel_prompt, sheet_prompt  # noqa: F401  (NO_TEXT re-exported)
from generation.openrouter_image_client import OpenRouterImageClient, closest_aspect_ratio
from generation.vision_client import VisionClient
from layout.bubble_planner import plan_bubbles
from layout.captions import NOTE_SIZE, draw_note, note_corner, text_box
from layout.comic_bubbles import head_box, is_rtl, render_dialogue
from layout.lettering import overlap_area
from layout.panel_layout import LayoutManager, LayoutType

logger = logging.getLogger(__name__)

# Print comic page: 6.625 x 10.25 in trim plus 0.125 in bleed per edge = 6.875 x 10.5 in, at 300 DPI
PRINT_DPI = 300
PRINT_PAGE_SIZE = (math.ceil(6.875 * PRINT_DPI), math.ceil(10.5 * PRINT_DPI))  # (2063, 3150)
RTL_LANGUAGES = {"he", "ar", "fa", "ur", "yi"}


@dataclass
class RenderOptions:
    """How pages are drawn. The defaults reproduce the plain one-call-per-panel renderer.

    Attributes:
        font_path: Lettering font file for bubbles, captions and notes (default: bundled + system fonts)
        fail_on_image_error: Raise when an image call fails instead of drawing a gray placeholder
        check_art: Ask the vision model whether the art (and the character sheet) has painted-in writing or extra
            hands or design/scene drift, with at most three draws; unchecked or rejected art raises
        chain_panels: Send the previous panel of the page as a reference, for continuity
        photo: Reference photo of the main character (http or data: URL)
        sheet_path: Where the main character's sheet is drawn once (and reused); it is then a reference
            for every panel. None draws no sheet
        dpi: DPI tag for saved page PNGs (e.g. PRINT_DPI); None leaves PIL's default
        rejected_dir: When set, every draw the art check rejects (panel, cover, sheet) is saved there as
            <stage>_p<panel>_d<draw>.png plus a .json of failed check names and reasons (at most 12 per renderer)
    """
    font_path: Optional[str] = None
    fail_on_image_error: bool = False
    check_art: bool = False
    chain_panels: bool = False
    photo: Optional[str] = None
    sheet_path: Optional[Path] = None
    dpi: Optional[int] = None
    rejected_dir: Optional[Path] = None


def image_url(image: Image.Image) -> str:
    """PNG data URL for a reference image."""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def print_layouts() -> LayoutManager:
    """Layout manager for the print comic page size."""
    return LayoutManager(page_width=PRINT_PAGE_SIZE[0], page_height=PRINT_PAGE_SIZE[1])


class PageRenderer:
    """Renders one page per script and tracks image and vision spend."""

    def __init__(
        self,
        cast: Dict,
        images: Optional[OpenRouterImageClient] = None,
        vision: Optional[VisionClient] = None,
        layouts: Optional[LayoutManager] = None,
        options: Optional[RenderOptions] = None,
    ):
        self.cast = cast
        self.looks = {c["name_en"].lower(): c for c in cast["characters"]}
        self.images = images or OpenRouterImageClient()
        self.vision = vision or VisionClient()
        self.layouts = layouts or LayoutManager()
        self.options = options or RenderOptions()
        self._sheet: Optional[str] = None
        self._previous: Optional[Image.Image] = None
        self.prop_anchors = {}
        self.audit = []
        self.current_stage = "unknown"
        self.current_panel = None
        self._diagnostic_start = 0
        self.lettering_checks = set()
        names = [c.get(k) for c in cast.get("characters", []) for k in ("name_en", "name") if isinstance(c.get(k), str)]
        names += [p["name"] for p in cast.get("props", []) if isinstance(p.get("name"), str)]
        self.rejected = RejectedArtSaver(self.options.rejected_dir, names)

    def failure_diagnostic(self, cover=False):
        """Only fixed identifiers and scalar fields may leave private attempt diagnostics."""
        flags = ("has_text", "bad_anatomy", "identity_mismatch", "design_mismatch", "scene_mismatch",
                 "requirement_mismatch", "prop_mismatch", "prop_shape_mismatch")
        stage = "cover" if cover else self.current_stage
        report = self.audit[-1] if len(self.audit) > self._diagnostic_start else {}
        if cover and report.get("kind") != "cover":
            report = {}
        checks = report.get("checks", {}) if stage in ("sheet", "panel", "cover") else {}
        failed = [key for key in flags if checks.get(key) is True]
        unchecked = [key for key in flags if key in checks and checks[key] is None]
        if stage == 'lettering':
            failed += [key for key in ('lettering_space', 'lettering_overflow') if key in self.lettering_checks]
            unchecked += ['lettering_plan'] if 'lettering_plan' in self.lettering_checks else []
        return {"stage": stage, "panel": self.current_panel if stage in ("panel", "lettering") else None,
                "failedChecks": failed, "uncheckedChecks": unchecked}

    @property
    def total_cost(self) -> float:
        return self.images.total_cost + self.vision.total_cost

    def _character(self, name: str) -> Dict:
        return self.looks.get(name.strip().lower(), {"name_en": name, "look": ""})

    def _rtl(self, texts: List[str]) -> bool:
        """Reading direction: cast["language"] when set, else detected from the text."""
        language = (self.cast.get("language") or "").lower()
        return language in RTL_LANGUAGES if language else any(is_rtl(t) for t in texts)

    def _art(self, prompt: str, references: List[str], aspect_ratio: str, size=None, requirements=()) -> Image.Image:
        if self.options.check_art:
            return draw_checked(self.images, self.vision, prompt, references, aspect_ratio, size=size,
                                requirements=requirements, props=self.cast.get("props", []), anchors=self.prop_anchors, audit=self.audit,
                                on_reject=self.rejected.hook("panel", self.current_panel or 0))
        return request_art(self.images, prompt, references, aspect_ratio)

    def character_sheet(self) -> Optional[str]:
        """Data URL of the main character's sheet, drawn on first use when options.sheet_path is set."""
        path = self.options.sheet_path
        if self._sheet or not path:
            return self._sheet
        if not Path(path).exists():
            self.current_stage = "sheet"
            self._diagnostic_start = len(self.audit)
            references = [self.options.photo] if self.options.photo else []
            prompt = sheet_prompt(self.cast, self.cast["characters"][0], ["photo"] if references else [])
            try:
                if self.options.check_art:
                    sheet = draw_checked(self.images, self.vision, prompt, references, "2:3", audit=self.audit,
                                         on_reject=self.rejected.hook("sheet"))
                else:
                    sheet = request_art(self.images, prompt, references, "2:3")
                sheet.save(path)
            except Exception as e:
                if self.options.fail_on_image_error or isinstance(e, ArtCheckError):
                    raise
                logger.warning(f"Character sheet failed; drawing panels without it: {e}")
                return None
        with Image.open(path) as sheet:
            try:
                stored = json.loads(sheet.info.get("comic_prop_anchors", "{}"))
                names = {p["name"] for p in self.cast.get("props", [])}
                if isinstance(stored, dict):
                    self.prop_anchors.update({k: v for k, v in stored.items() if k in names and isinstance(v, str) and len(v) <= 600})
            except (ValueError, TypeError):
                pass
            self._sheet = image_url(sheet.convert("RGB"))
        return self._sheet

    def _image_prompt(self, panel: Dict, roles: tuple = ()) -> str:
        people = "; ".join(
            f"{c['name_en']}: {c['look']}" for c in map(self._character, panel.get("characters", []))
        )
        return panel_prompt({**self.cast, "prop_anchors": self.prop_anchors}, panel, people, roles)

    def _draw_panel(self, panel: Dict, size: tuple) -> Image.Image:
        roles, references = [], []
        for role, url in (("photo", self.options.photo), ("sheet", self.character_sheet())):
            if url:
                roles.append(role)
                references.append(url)
        if self.options.chain_panels and self._previous is not None:
            roles.append("previous")
            references.append(image_url(self._previous))
        requirements = scene_requirements(panel["scene"], panel.get("requirements", []))
        self.current_stage = "panel"
        self._diagnostic_start = len(self.audit)
        try:
            art = self._art(self._image_prompt(panel, tuple(roles)), references, closest_aspect_ratio(*size), size=size, requirements=requirements)
            for prop in art.info.get("comic_verification", {}).get("prop_checks", []):
                if prop["visible"]:
                    self.prop_anchors.setdefault(prop["name"], prop["observed"])
            return ImageOps.fit(art, size, Image.Resampling.LANCZOS)
        except Exception as e:
            if self.options.fail_on_image_error or isinstance(e, ArtCheckError):
                raise
            logger.warning(f"Panel image failed, using a gray placeholder: {e}")
            return Image.new("RGB", size, (200, 200, 200))

    def _letter(self, image: Image.Image, panel: Dict) -> Image.Image:
        self.lettering_checks = set()
        dialogue = [d for d in panel.get("dialogue", []) if d.get("text")]
        caption = panel.get("caption", "")
        note = panel.get("note", "")
        if not dialogue and not caption and not note:
            return image

        texts = [d["text"] for d in dialogue]
        kinds = [d.get("bubble") or "speech" for d in dialogue]
        rtl = self._rtl(texts + [caption, note])
        # Telling the vision model what each speaker looks like keeps tails on the right character
        speakers = [
            f"{c['name_en']} ({c['look'][:160]})" for c in (self._character(d.get("speaker", "")) for d in dialogue)
        ]
        reserved = [note_corner(rtl)] if note else []
        font = self.options.font_path
        for precise in (False, True):
            plan = plan_bubbles(image, list(zip(speakers, texts)), bool(caption), rtl,
                                vision=self.vision, reserved_corners=reserved, precise=precise)
            if plan is None or not plan.protected_checked:
                self.lettering_checks.add('lettering_plan')
                continue
            try:
                reserved_boxes = []
                if note:
                    box = text_box(ImageDraw.Draw(image), image.size, note, max(14, int(image.height * NOTE_SIZE)),
                                   note_corner(rtl), font, dry=True)
                    subjects = [(int(x * image.width), int(y * image.height), int(w * image.width), int(h * image.height))
                                for x, y, w, h in plan.protected]
                    subjects += [head_box(p, image.size) for p in plan.speakers if p]
                    if any(overlap_area(box, subject) for subject in subjects):
                        raise ValueError("comic_lettering_no_space")
                    reserved_boxes.append(box)
                lettered = render_dialogue(image, texts, caption, plan, kinds=kinds, rtl=rtl,
                                           font_path=font, reserved=reserved_boxes)
                return draw_note(lettered, note, rtl=rtl, font_path=font)
            except ValueError as error:
                if str(error) not in ("comic_lettering_no_space", "comic_lettering_overflow"):
                    raise
                self.lettering_checks.add('lettering_overflow' if str(error) == 'comic_lettering_overflow' else 'lettering_space')
        raise ValueError("comic_lettering_no_space")

    def render_page(self, panels: List[Dict], path: Path) -> Path:
        """Draw, letter and compose one page. Unlettered art is kept as art_<page>_<n>.png beside it."""
        layout = self.layouts.create_layout(LayoutType.VERTICAL_STRIP, num_panels=len(panels))
        images = []
        self._previous = None
        for number, (panel, slot) in enumerate(zip(panels, layout), 1):
            self.current_panel = number
            size = tuple(slot.get_content_area()[2:])
            art = self._draw_panel(panel, size)
            art.save(path.parent / f"art_{path.stem}_{number}.png", format="PNG")
            self._previous = art
            self.current_stage = "lettering"
            images.append(self._letter(art, panel))

        if self.options.sheet_path and Path(self.options.sheet_path).exists() and self.prop_anchors:
            with Image.open(self.options.sheet_path) as sheet:
                metadata = PngInfo()
                metadata.add_text("comic_prop_anchors", json.dumps(self.prop_anchors))
                saved = sheet.convert("RGB")
            saved.save(self.options.sheet_path, format="PNG", pnginfo=metadata)
        page = self.layouts.compose_page(panels=images, layout=layout)
        dpi = {"dpi": (self.options.dpi, self.options.dpi)} if self.options.dpi else {}
        page.save(path, format="PNG", optimize=True, **dpi)
        logger.info(f"Saved page {path}")
        return path


def save_pdf(pages: List[Path], path: Path) -> Path:
    """Bundle page images into one PDF, in the given order."""
    images = [Image.open(p).convert("RGB") for p in pages]
    images[0].save(path, save_all=True, append_images=images[1:], resolution=300)
    return path
