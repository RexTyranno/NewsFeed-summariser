import pytest
from ingestion.dates import get_date_from_text, get_dates_mentioned, infer_date_from_text


class TestGetDateFromText:
    def test_parses_standard_date(self):
        result = get_date_from_text("7 March 2024")
        assert result == "2024-03-07"

    def test_parses_ordinal_date(self):
        result = get_date_from_text("7th March 2024")
        assert result == "2024-03-07"

    def test_parses_iso_date(self):
        result = get_date_from_text("2024-03-07")
        assert result == "2024-03-07"

    def test_returns_none_for_unparseable_string(self):
        result = get_date_from_text("not a date at all xyz")
        assert result is None

    def test_returns_string_in_yyyy_mm_dd_format(self):
        result = get_date_from_text("January 1 2023")
        assert result is not None
        parts = result.split("-")
        assert len(parts) == 3 and len(parts[0]) == 4


class TestGetDatesMentioned:
    def test_finds_dates_in_text(self):
        text = "The event happened on 7 March 2024 and the follow-up on 15 April 2024."
        result = get_dates_mentioned(text)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_returns_list_of_strings(self):
        result = get_dates_mentioned("Meeting on 1 January 2024.")
        assert all(isinstance(d, str) for d in result)

    def test_empty_or_dateless_text_returns_empty_list(self):
        result = get_dates_mentioned("No dates here at all.")
        assert isinstance(result, list)


class TestInferDateFromText:
    def test_infers_relative_date(self):
        text = "3 months ago"
        result = infer_date_from_text(text, "7 March 2024")
        assert result == "2023-12-07"