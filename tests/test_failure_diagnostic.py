from PIL import Image
import pytest

from book_comic.art_check import ArtCheckError
from book_comic.render import PageRenderer, RenderOptions
from conftest import FakeImages, FakeVision


def test_failed_panel_diagnostic_is_allowlisted_and_numbered(tmp_path):
    def review(prompt, image):
        failed = 'Close-up:' in prompt
        return {'has_text': False, 'bad_anatomy': failed, 'identity_mismatch': False,
                'design_mismatch': False, 'scene_mismatch': False,
                'private_observation': 'never log a private character or scene'}
    renderer = PageRenderer({'characters': []}, FakeImages([Image.new('RGB', (64, 64))]),
                            FakeVision(review), options=RenderOptions(check_art=True))
    with pytest.raises(ArtCheckError):
        renderer.render_page([{'scene': scene} for scene in ['Wide shot: room.', 'Medium shot: lamp.', 'Close-up: hand.']], tmp_path / 'page.png')
    assert renderer.failure_diagnostic() == {'stage': 'panel', 'panel': 3,
                                           'failedChecks': ['bad_anatomy'], 'uncheckedChecks': []}
    # A cover which failed before inspection must not inherit the last panel's flags.
    assert renderer.failure_diagnostic(cover=True)['failedChecks'] == []
