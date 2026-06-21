import io
import pytest
from unittest.mock import MagicMock
from helpers.utility_helper import UtilityHelper


# ── generate_unique_filename ─────────────────────────────────────────────────

def test_generate_unique_filename_preserves_extension():
    name = UtilityHelper.generate_unique_filename("photo.jpg")
    assert name.endswith(".jpg")


def test_generate_unique_filename_is_unique():
    a = UtilityHelper.generate_unique_filename("photo.png")
    b = UtilityHelper.generate_unique_filename("photo.png")
    assert a != b


def test_generate_unique_filename_no_original_name_in_output():
    name = UtilityHelper.generate_unique_filename("original_name.jpg")
    assert "original_name" not in name


def test_generate_unique_filename_handles_unsafe_chars():
    name = UtilityHelper.generate_unique_filename("bad file name!@#.jpg")
    assert " " not in name
    assert "!" not in name


# ── is_valid_image ───────────────────────────────────────────────────────────

def _make_file(filename, content):
    f = MagicMock()
    f.filename = filename
    f.stream = io.BytesIO(content)
    return f


JPEG_HEADER = b'\xff\xd8\xff' + b'\x00' * 9
PNG_HEADER = b'\x89PNG\r\n\x1a\n' + b'\x00' * 4
WEBP_HEADER = b'RIFF' + b'\x00' * 4 + b'WEBP'


def test_is_valid_image_jpeg():
    assert UtilityHelper.is_valid_image(_make_file("photo.jpg", JPEG_HEADER))


def test_is_valid_image_jpeg_uppercase_extension():
    assert UtilityHelper.is_valid_image(_make_file("photo.JPG", JPEG_HEADER))


def test_is_valid_image_png():
    assert UtilityHelper.is_valid_image(_make_file("photo.png", PNG_HEADER))


def test_is_valid_image_webp():
    assert UtilityHelper.is_valid_image(_make_file("photo.webp", WEBP_HEADER))


def test_is_valid_image_wrong_extension():
    assert not UtilityHelper.is_valid_image(_make_file("photo.gif", JPEG_HEADER))


def test_is_valid_image_txt_extension():
    assert not UtilityHelper.is_valid_image(_make_file("file.txt", JPEG_HEADER))


def test_is_valid_image_valid_extension_wrong_magic():
    garbage = b'\x00' * 12
    assert not UtilityHelper.is_valid_image(_make_file("photo.jpg", garbage))


def test_is_valid_image_cross_format_magic_accepted():
    # is_valid_image checks magic bytes against any supported format, not against the extension.
    # A .png file with JPEG magic bytes is accepted — content wins over extension name.
    assert UtilityHelper.is_valid_image(_make_file("photo.png", JPEG_HEADER)) is True


def test_is_valid_image_resets_stream():
    f = _make_file("photo.jpg", JPEG_HEADER)
    UtilityHelper.is_valid_image(f)
    assert f.stream.tell() == 0


# ── check_password_complexity ────────────────────────────────────────────────

@pytest.fixture
def app_ctx():
    """Minimal Flask context so flash() can run."""
    from flask import Flask
    a = Flask(__name__)
    a.config['TESTING'] = True
    a.config['SECRET_KEY'] = 'test'
    with a.test_request_context('/'):
        with a.test_client() as c:
            with c.session_transaction():
                pass
        yield


def test_check_password_complexity_valid(app_ctx):
    assert UtilityHelper.check_password_complexity("Abcdef1!") is True


def test_check_password_complexity_strong(app_ctx):
    assert UtilityHelper.check_password_complexity("$ecureP4ssw0rd!") is True


def test_check_password_complexity_too_short(app_ctx):
    assert UtilityHelper.check_password_complexity("Ab1!") is False


def test_check_password_complexity_no_uppercase(app_ctx):
    assert UtilityHelper.check_password_complexity("abcdef1!") is False


def test_check_password_complexity_no_lowercase(app_ctx):
    assert UtilityHelper.check_password_complexity("ABCDEF1!") is False


def test_check_password_complexity_no_digit(app_ctx):
    assert UtilityHelper.check_password_complexity("Abcdefg!") is False


def test_check_password_complexity_no_special(app_ctx):
    assert UtilityHelper.check_password_complexity("Abcdef12") is False


def test_check_password_complexity_too_long(app_ctx):
    long_pass = "Aa1!" + "x" * 125
    assert len(long_pass) > 128
    assert UtilityHelper.check_password_complexity(long_pass) is False


def test_check_password_complexity_exactly_8_chars(app_ctx):
    assert UtilityHelper.check_password_complexity("Abcde1!x") is True


def test_check_password_complexity_underscore_as_special(app_ctx):
    assert UtilityHelper.check_password_complexity("Abcdef1_") is True
