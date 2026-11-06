"""PageRenderer and the script writer with fake clients: references, art checks, fallbacks, old scripts."""

import pytest
from PIL import Image

from book_comic.art_check import draw_checked, inspect_art
from book_comic.book_text import Chapter
from book_comic.render import PageRenderer, RenderOptions
from book_comic.script import ScriptWriter
from conftest import FakeImages, FakeVision
from layout.panel_layout import LayoutManager

CAST = {
    "style": "comic",
    "characters": [{"name_en": "Dana", "look": "red coat"}, {"name_en": "Omer", "look": "green cap"}],
    "props": [{"name": "the brass lantern", "look": "small brass hurricane lantern"}],
}
OLD_PANEL = {"scene": "Dana and Omer at the gate", "characters": ["Dana", "Omer"], "caption": "Morning.",
             "dialogue": [{"speaker": "Omer", "text": "Hi"}]}
SMALL = LayoutManager(page_width=400, page_height=600, margin=10, gutter=10)


def renderer(images, vision=None, **options):
    return PageRenderer(CAST, images, vision or FakeVision(), SMALL, RenderOptions(**options))


def test_an_old_script_renders_with_the_defaults(tmp_path):
    images = FakeImages([Image.new("RGB", (64, 64), "white")])
    vision = FakeVision(lambda p, i: {"lines": [{"mouth": [500, 500], "bubble": [500, 200]}], "protected": []})
    path = renderer(images, vision).render_page([OLD_PANEL] * 3, tmp_path / "page_01.png")
    assert Image.open(path).size == (400, 600)
    assert len(images.calls) == 3 and all(c["references"] == [] for c in images.calls)  # one plain call per panel
    assert "small brass hurricane lantern" in images.calls[0]["prompt"] and "180-degree rule" in images.calls[0]["prompt"]
    assert "Omer (green cap)" in vision.prompts[0]  # the speaker's own look, not the first character's
    assert sorted(p.name for p in tmp_path.glob("art_*")) == [f"art_page_01_{n}.png" for n in (1, 2, 3)]


def test_a_failed_image_is_gray_by_default_and_fails_the_job_when_asked(tmp_path):
    error = RuntimeError("HTTP 402")
    path = renderer(FakeImages(error=error)).render_page([{"scene": "s"}], tmp_path / "page_01.png")
    assert Image.open(path).getpixel((200, 300)) == (200, 200, 200)
    with pytest.raises(RuntimeError):
        renderer(FakeImages(error=error), fail_on_image_error=True).render_page([{"scene": "s"}], tmp_path / "p.png")


def test_sheet_photo_and_previous_panel_are_references(tmp_path):
    images = FakeImages([Image.new("RGB", (64, 64), "white")])
    r = renderer(images, photo="data:photo", sheet_path=tmp_path / "sheet.png", chain_panels=True, dpi=300)
    path = r.render_page([{"scene": "Wide shot: a"}, {"scene": "Close-up: b"}, {"scene": "Medium shot: c"}],
                         tmp_path / "page_01.png")
    sheet, first, second, third = images.calls
    assert "three-quarter pose" in sheet["prompt"] and sheet["references"] == ["data:photo"]
    assert len(first["references"]) == 2 and first["references"][0] == "data:photo"
    assert len(second["references"]) == 3 and "reference image 3 is the previous panel" in second["prompt"]
    assert "the previous panel of this page" not in first["prompt"]
    assert round(Image.open(path).info["dpi"][0]) == 300
    assert len(third["references"]) == 3
    r.render_page([{"scene": "Wide shot: d"}], tmp_path / "page_02.png")
    assert len(images.calls) == 5  # the sheet is drawn once per book


def test_art_with_painted_text_is_drawn_once_more():
    red, blue = Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")
    images = FakeImages([red, blue])
    art = draw_checked(images, FakeVision(lambda p, i: {"has_text": i.getpixel((0, 0)) == (255, 0, 0), "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}), "scene", ["ref"], "2:3")
    assert art.getpixel((0, 0)) == (0, 0, 255) and len(images.calls) == 2
    assert "no letters, words, numbers, symbols or glyphs anywhere" in images.calls[1]["prompt"]  # draw 2 revises draw 1
    images = FakeImages([red, blue])
    def broken(prompt, image):
        raise RuntimeError("down")
    with pytest.raises(ValueError, match="comic_art_check_unavailable"):
        draw_checked(images, FakeVision(broken), "scene", [], "2:3")
    assert len(images.calls) == 1  # a failed check blocks without spending another image call


def test_art_with_a_third_hand_is_drawn_once_more_with_the_anatomy_rule():
    red, blue = Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")
    images = FakeImages([red, blue])
    art = draw_checked(images, FakeVision(lambda p, i: {"has_text": False, "bad_anatomy": i.getpixel((0, 0)) == (255, 0, 0), "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}), "scene", [], "2:3")
    assert art.getpixel((0, 0)) == (0, 0, 255) and len(images.calls) == 2
    assert images.calls[1]["prompt"].startswith("REVISE the last attached image") and "exactly two arms and two hands" in images.calls[1]["prompt"]
    assert "no letters, words, numbers, symbols or glyphs anywhere" not in images.calls[1]["prompt"]  # only the broken rule is asked for
    images = FakeImages([red, blue])
    assert draw_checked(images, FakeVision(lambda p, i: {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}), "scene", [], "2:3") \
        .getpixel((0, 0)) == (255, 0, 0) and len(images.calls) == 1


def test_every_drawing_of_a_person_asks_for_ordinary_human_anatomy():
    from book_comic.image_prompts import panel_prompt, sheet_prompt
    rule = "exactly two arms and two hands"
    assert rule in panel_prompt(CAST, {"scene": "Medium shot: Dana works"}, "Dana: red coat")
    assert rule in sheet_prompt(CAST, CAST["characters"][0])


def test_bubble_kinds_and_notes_reach_the_lettering(tmp_path):
    panel = {**OLD_PANEL, "dialogue": [{"speaker": "Omer", "text": "Hi", "bubble": "shout"}], "note": "With love"}
    vision = FakeVision(lambda p, i: {"lines": [{"mouth": [500, 500], "bubble": [500, 200]}], "protected": []})
    plain = renderer(FakeImages([Image.new("RGB", (64, 64), "white")]), vision)
    art = Image.new("RGB", (380, 180), "white")
    assert plain._letter(art, panel).tobytes() != plain._letter(art, OLD_PANEL).tobytes()
    assert "bottom-right corners" in vision.prompts[0]  # the note's corner is kept bubble-free


def test_language_overrides_text_direction():
    r = renderer(FakeImages([Image.new("RGB", (8, 8))]))
    assert r._rtl(["שלום"]) and not r._rtl(["hello"])
    r.cast = {**CAST, "language": "he"}
    assert r._rtl(["hello"])


def test_the_writer_retries_once_for_the_camera_rule():
    flat = {"panels": [{"scene": "Wide shot: a"}] * 3}
    varied = {"panels": [{"scene": "Wide shot: a"}, {"scene": "Close-up: b"}, {"scene": "Medium shot: c"}]}
    writer = ScriptWriter.__new__(ScriptWriter)
    prompts, answers = [], [flat, varied]
    writer._ask_json = lambda prompt: prompts.append(prompt) or answers.pop(0)
    cast = {"characters": [{"name": "דנה", "name_en": "Dana", "look": "red coat"}]}
    assert writer.script_chapter(Chapter(1, "Start", "text"), cast) == varied["panels"]
    assert '"bubble"' in prompts[0] and "shots_not_varied" in prompts[1]
    answers[:] = [flat, flat]
    assert writer.script_chapter(Chapter(1, "Start", "text"), cast) == flat["panels"]  # kept, not lost


def colours(*names):
    return [Image.new("RGB", (10, 10), n) for n in names]


def judge(flags):
    """Vision fake: the answer for each colour of art, by its top-left pixel."""
    return FakeVision(lambda p, i: {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False, **flags.get(i.getpixel((0, 0)), {})})


RED, GREEN, BLUE = (255, 0, 0), (0, 128, 0), (0, 0, 255)
HANDS, TEXT, CLEAN = {"bad_anatomy": True}, {"has_text": True}, {}


def test_a_third_draw_happens_when_the_second_is_still_bad():
    images = FakeImages(colours("red", "green", "blue"))
    art = draw_checked(images, judge({RED: HANDS, GREEN: HANDS, BLUE: CLEAN}), "scene", [], "2:3")
    assert art.getpixel((0, 0)) == BLUE and len(images.calls) == 3


def test_all_rejected_draws_fail_instead_of_returning_the_least_bad():
    images = FakeImages(colours("red", "green", "blue"))
    with pytest.raises(ValueError, match="comic_art_rejected"):
        draw_checked(images, judge({RED: HANDS, GREEN: TEXT, BLUE: HANDS}), "scene", [], "2:3")
    assert len(images.calls) == 3


def test_a_clean_first_draw_costs_one_image_and_one_vision_call():
    images, vision = FakeImages(colours("red")), judge({})
    draw_checked(images, vision, "scene", [], "2:3")
    assert len(images.calls) == 1 and len(vision.prompts) == 1


def test_only_redraws_carry_the_negative_prompt():
    images = FakeImages(colours("red", "blue"))
    draw_checked(images, judge({RED: HANDS}), "scene", [], "2:3")
    first, second = images.calls
    assert first["negative_prompt"] is None and first["prompt"] == "scene"
    assert "third hand" in second["negative_prompt"]


@pytest.mark.parametrize("answer, bad", [
    ({"has_text": False, "bad_anatomy": False, "people": 1, "hands_visible": 3}, True),
    ({"has_text": False, "bad_anatomy": False, "people": 2, "hands_visible": 4}, False),
    ({"has_text": False, "bad_anatomy": False, "people": 1, "hands_visible": 2}, False),
    ({"has_text": False, "bad_anatomy": True, "people": 1, "hands_visible": 2}, True),
    ({"has_text": False, "bad_anatomy": False}, False),
    ({"bad_anatomy": False, "people": "one", "hands_visible": 9}, False),
])
def test_more_than_two_hands_per_person_is_bad_anatomy(answer, bad):
    found = inspect_art(Image.new("RGB", (2000, 1000)), FakeVision(lambda p, i: answer))
    assert found["bad_anatomy"] is bad and set(found) == {"head_top", "text_prominent", "text_seen", "has_text", "bad_anatomy"}


def test_the_sheet_is_redrawn_when_flagged_and_drawn_once_when_clean(tmp_path):
    images = FakeImages(colours("red", "blue"))
    r = renderer(images, judge({RED: HANDS}), check_art=True, sheet_path=tmp_path / "bad.png")
    r.character_sheet()
    assert len(images.calls) == 2 and Image.open(tmp_path / "bad.png").getpixel((0, 0)) == BLUE
    images = FakeImages(colours("red"))
    r = renderer(images, judge({}), check_art=True, sheet_path=tmp_path / "ok.png")
    r.character_sheet()
    assert len(images.calls) == 1
    images = FakeImages(colours("red"))  # without check_art the sheet is never inspected
    vision = judge({RED: HANDS})
    renderer(images, vision, sheet_path=tmp_path / "plain.png").character_sheet()
    assert len(images.calls) == 1 and vision.prompts == []


def test_reference_priority_preserves_design_but_allows_new_shots():
    from book_comic.image_prompts import panel_prompt, cover_prompt
    for prompt in (panel_prompt(CAST, {'scene': 'Close-up: Dana holds the lantern'}, 'Dana: red coat', ('photo', 'sheet', 'previous')),
                   cover_prompt(CAST, {'scene': 'Dana on the cliff'}, ('photo', 'sheet', 'panels'))):
        assert 'Reference priority:' in prompt
        assert 'head-to-body proportions' in prompt
        assert 'exact garment construction' in prompt
        assert 'do not copy a prior composition' in prompt


@pytest.mark.parametrize('defect', ['identity_mismatch', 'design_mismatch', 'scene_mismatch'])
def test_identity_design_and_shot_mismatches_are_rejected(defect):
    images = FakeImages(colours('red', 'blue'))
    art = draw_checked(images, judge({RED: {defect: True}}), 'scene', ['data:sheet'], '2:3')
    assert art.getpixel((0, 0)) == BLUE
    assert len(images.calls) == 2


def test_inspection_passes_actual_references_to_vision():
    class Vision:
        def ask_json(self, prompt, images):
            assert len(images) == 2 and images[1] == 'data:sheet'
            assert 'head/body proportions' in prompt and 'wrong planned shot' in prompt
            return {'has_text': False, 'bad_anatomy': False, 'identity_mismatch': False, 'design_mismatch': False, 'scene_mismatch': False}
    inspect_art(Image.new('RGB', (10, 10)), Vision(), references=['data:sheet'], context='Reference image 1 is the sheet')


@pytest.mark.parametrize('language, caption, dialogue', [('en', 'The owl stirred.', 'What happened?'), ('he', 'הינשוף התעורר.', 'מה קרה כאן?')])
def test_crowded_art_rejects_without_shrinking_or_another_image_call(language, caption, dialogue):
    from layout.lettering import LETTERING_FONT
    images = FakeImages(colours('red'))
    vision = FakeVision(lambda p, i: {'lines': [{'mouth': [500, 500], 'bubble': [500, 500]}], 'protected': [[0, 0, 1000, 1000]]})
    r = renderer(images, vision, font_path=str(LETTERING_FONT))
    r.cast = {**r.cast, 'language': language}
    original = Image.new('RGB', (1837, 944), 'red')
    panel = {'caption': caption, 'dialogue': [{'speaker': 'Dana', 'text': dialogue}], 'note': 'With love'}
    with pytest.raises(ValueError, match='comic_lettering_no_space'):
        r._letter(original, panel)
    assert len(vision.prompts) == 2 and len(images.calls) == 0  # one precise retry; never shrink or redraw artwork


@pytest.mark.parametrize('attribute, expected, observed', [('pose','standing','kneeling'),('state','closed','open'),('state','flat','upright'),('hand','right','left'),('hand','right','ambiguous')])
def test_literal_state_mismatch_cannot_pass_even_if_model_sets_matches_true(attribute, expected, observed):
    from book_comic.art_check import require_checked
    requirements = [{'subject':'Hero' if attribute == 'pose' else 'book', 'attribute':attribute, 'expected':expected}]
    answer = {'has_text':False,'bad_anatomy':False, 'requirement_checks':[{'index':0,'observed':observed,'matches':True}]}
    found = inspect_art(Image.new('RGB',(100,100)), FakeVision(lambda p,i:answer), requirements=requirements)
    assert found['requirement_mismatch'] is True
    assert require_checked(found) is False


def test_a_limb_only_crop_is_observed_but_never_rejects_the_draw():
    """No image model holds a hands-only crop (production 2026-11-05: three draws of a close-up rejected for showing
    the hero over the relic); the fuller draw is what a reader wants, so framing is reported, never enforced."""
    from book_comic.art_check import require_checked
    requirements = [{'subject':'frame', 'attribute':'framing', 'expected':'hand_detail_only'}]
    answer = {'has_text':False,'bad_anatomy':False, 'requirement_checks':[{'index':0,'observed':'body_visible','matches':False}]}
    found = inspect_art(Image.new('RGB',(100,100)), FakeVision(lambda p,i:answer), requirements=requirements)
    assert found['requirement_mismatch'] is False and found['requirement_checks'][0]['observed'] == 'body_visible'
    assert require_checked(found) is True


def test_missing_requirement_evidence_is_not_a_pass():
    from book_comic.art_check import require_checked
    answer = {'has_text':False,'bad_anatomy':False,'requirement_checks':[]}
    found = inspect_art(Image.new('RGB',(100,100)), FakeVision(lambda p,i:answer),
                        requirements=[{'subject':'book','attribute':'state','expected':'closed'}])
    with pytest.raises(ValueError, match='comic_art_check_unavailable'):
        require_checked(found)


def test_canonical_prop_mismatch_is_rejected():
    from book_comic.art_check import require_checked
    answer = {'has_text':False,'bad_anatomy':False,'prop_checks':[{'name':'owl','visible':True,'observed':'turquoise disk','matches':False}]}
    found = inspect_art(Image.new('RGB',(100,100)), FakeVision(lambda p,i:answer),
                        props=[{'name':'owl','look':'brass owl with round dial'}], anchors={'owl':'cream clock face with a dark pointer'})
    assert found['prop_mismatch'] is True and require_checked(found) is False


def test_first_observed_prop_design_is_kept_in_existing_sheet_asset(tmp_path):
    import json
    description = 'small brass lantern with a clear glass chimney and black handle'
    def answer(prompt, image):
        return {'head_top':400,'has_text':False,'bad_anatomy':False,'identity_mismatch':False,'design_mismatch':False,'scene_mismatch':False,
                'lines':[{'mouth':[700,600],'bubble':[200,120]}], 'protected':[],
                'prop_checks':[{'name':'the brass lantern','visible':True,'observed':description,'matches':True}]}
    sheet = tmp_path / 'sheet.png'
    r = renderer(FakeImages(colours('red')), FakeVision(answer), check_art=True, sheet_path=sheet)
    r.render_page([OLD_PANEL], tmp_path / 'page.png')
    assert r.prop_anchors['the brass lantern'] == description
    with Image.open(sheet) as image:
        assert json.loads(image.info['comic_prop_anchors'])['the brass lantern'] == description
    loaded = renderer(FakeImages(colours('blue')), sheet_path=sheet)
    loaded.character_sheet()
    assert loaded.prop_anchors == r.prop_anchors
    assert r.audit and r.audit[-1]['accepted'] is True


def test_explicit_hand_and_crop_survive_missing_model_requirements():
    from book_comic.scene_requirements import scene_requirements
    scene = "Close-up: Hero holds the key in the right hand. Only the right hand, teal sleeve and keyhole are in frame, no face."
    requirements = scene_requirements(scene, [])
    assert {r['attribute']: r['expected'] for r in requirements} == {'hand': 'right', 'framing': 'hand_detail_only'}
    assert scene_requirements("Medium shot: Hero raises both hands.", []) == []
    assert scene_requirements("Only Hero's face and right hand are visible.", []) == [{'subject':'Hero', 'attribute':'hand', 'expected':'right'}]


def test_direct_panel_prompt_preserves_explicit_crop_without_preflight():
    from book_comic.image_prompts import panel_prompt
    scene = "Only the left hand and sleeve are visible."
    prompt = panel_prompt(CAST, {'scene': scene}, 'Dana')
    assert prompt.startswith('LIMB-ONLY MACRO DETAIL')
    assert "anatomical left hand" in prompt
    assert "Exclude head, neck, shoulders, torso" in prompt


@pytest.mark.parametrize('scene', ['Hand-only close-up of the right hand holding a compass.', 'Close-up showing only Hero\'s right hand.', 'Only the right hand and sleeve are visible.', 'Only the right hand and socket are in frame.'])
def test_limb_only_crop_wording_is_preserved(scene):
    from book_comic.scene_requirements import scene_requirements
    assert {'subject':'frame', 'attribute':'framing', 'expected':'hand_detail_only'} in scene_requirements(scene)


@pytest.mark.parametrize('shape, rejected', [('triangular_prism',False),('other',True),('uncertain',True)])
def test_prism_shape_is_checked_independently_of_matches(shape, rejected):
    from book_comic.art_check import require_checked
    answer = {'has_text':False,'bad_anatomy':False,'prop_checks':[{'name':'Blue Prism','visible':True,'observed':'a blue crystal','observed_shape':shape,'matches':True}]}
    found = inspect_art(Image.new('RGB',(100,100)), FakeVision(lambda p,i:answer), props=[{'name':'Blue Prism','look':'a triangular optical prism'}])
    assert found['prop_shape_mismatch'] is rejected
    assert require_checked(found) is (not rejected)


def test_missing_visible_prism_shape_evidence_is_not_a_pass():
    from book_comic.art_check import require_checked
    answer = {'has_text':False,'bad_anatomy':False,'prop_checks':[{'name':'Blue Prism','visible':True,'observed':'a blue crystal','matches':True}]}
    found = inspect_art(Image.new('RGB',(100,100)), FakeVision(lambda p,i:answer), props=[{'name':'Blue Prism','look':'a triangular optical prism'}])
    with pytest.raises(ValueError, match='comic_art_check_unavailable'):
        require_checked(found)
