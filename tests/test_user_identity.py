from core.user_identity import get_display_name


def test_display_name_has_a_nonempty_fallback():
    assert get_display_name().strip()
