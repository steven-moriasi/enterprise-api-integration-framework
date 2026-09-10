import pytest

from app.pagination import CursorPage, next_link, next_page_number


def test_page_number_and_cursor_models() -> None:
    assert next_page_number(1, 2) == 2
    assert next_page_number(2, 2) is None
    assert CursorPage[str](items=["one"], next_cursor="cursor").next_cursor == "cursor"

    with pytest.raises(ValueError):
        next_page_number(3, 2)


def test_link_pagination_accepts_only_expected_origin() -> None:
    headers = {
        "link": (
            '<https://api.example.test/resources?page=1>; rel="prev", '
            '<https://api.example.test/resources?page=3>; rel="next"'
        )
    }
    assert next_link(headers, expected_origin="https://api.example.test") == (
        "https://api.example.test/resources?page=3"
    )
    assert next_link({}, expected_origin="https://api.example.test") is None

    with pytest.raises(ValueError, match="Cross-origin"):
        next_link(
            {"link": '<https://attacker.test/resources>; rel="next"'},
            expected_origin="https://api.example.test",
        )
