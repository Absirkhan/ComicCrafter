"""Cropped owners must not be inferred to have extra limbs from a zero people count."""
import pytest
from PIL import Image

from book_comic.art_check import ArtCheckError, draw_checked
from conftest import FakeImages, FakeVision


@pytest.mark.parametrize('hands', [1, 2])
def test_cropped_hands_are_accepted_on_first_draw(hands):
    images = FakeImages([Image.new('RGB', (64, 64))])
    vision = FakeVision(lambda p, i: {
        'has_text': False, 'bad_anatomy': False, 'people': 0, 'hands_visible': hands,
        'identity_mismatch': False, 'design_mismatch': False, 'scene_mismatch': False,
    })
    draw_checked(images, vision, 'Close-up: only the hands holding a device.', [], '3:2')
    assert len(images.calls) == 1


@pytest.mark.parametrize('people,hands,explicit_defect', [(1, 3, False), (0, 3, True)])
def test_actual_extra_limbs_are_still_rejected(people, hands, explicit_defect):
    images = FakeImages([Image.new('RGB', (64, 64))])
    vision = FakeVision(lambda p, i: {
        'has_text': False, 'bad_anatomy': explicit_defect, 'people': people, 'hands_visible': hands,
        'identity_mismatch': False, 'design_mismatch': False, 'scene_mismatch': False,
    })
    with pytest.raises(ArtCheckError, match='comic_art_rejected'):
        draw_checked(images, vision, 'A hand detail.', [], '3:2')
    assert len(images.calls) == 3
