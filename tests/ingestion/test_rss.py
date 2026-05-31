import pytest
from unittest.mock import patch, MagicMock
from ingestion.rss import (
    parse_rss,
    normalise_feed_entries,
    unwrap_content,
    is_plain_text_long_enough,
    fetch_html_string,
    get_embedded_html_string,
    get_plain_text_from_embedded_html_string,
)


# ---------------------------------------------------------------------------
# parse_rss
# ---------------------------------------------------------------------------

class TestParseRss:
    def test_bozo_feed_returns_empty_list(self):
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("bad feed")
        with patch("ingestion.rss.feedparser.parse", return_value=mock_feed):
            assert parse_rss("http://bad-feed.example.com") == []

    def test_exception_during_parse_returns_empty_list(self):
        with patch("ingestion.rss.feedparser.parse", side_effect=Exception("network error")):
            assert parse_rss("http://example.com/feed") == []

    def test_healthy_feed_returns_entries(self):
        entry1 = {"title": "Article One", "link": "http://example.com/1"}
        entry2 = {"title": "Article Two", "link": "http://example.com/2"}
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [entry1, entry2]
        with patch("ingestion.rss.feedparser.parse", return_value=mock_feed):
            result = parse_rss("http://example.com/feed")
        assert result == [entry1, entry2]

    def test_healthy_feed_returns_raw_entries_not_normalised(self):
        """parse_rss returns raw feedparser entries; source_name is NOT present."""
        entry = {"title": "T", "link": "http://example.com/1"}
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [entry]
        with patch("ingestion.rss.feedparser.parse", return_value=mock_feed):
            result = parse_rss("http://example.com/feed")
        assert "source_name" not in result[0]


# ---------------------------------------------------------------------------
# normalise_feed_entries
# ---------------------------------------------------------------------------

class TestNormaliseFeedEntries:
    def _make_entry(self, **kwargs):
        defaults = {
            "title": "Test Title",
            "link": "http://example.com/article",
            "published_parsed": None,
            "summary": "A short summary.",
            "content": [],
            "author": "Jane Doe",
        }
        defaults.update(kwargs)
        return defaults

    def test_maps_link_to_url(self):
        entries = [self._make_entry(link="http://example.com/article")]
        result = normalise_feed_entries(entries, source_name="TestSource")
        assert result[0]["url"] == "http://example.com/article"

    def test_attaches_source_name(self):
        entries = [self._make_entry()]
        result = normalise_feed_entries(entries, source_name="MySource")
        assert result[0]["source_name"] == "MySource"

    def test_optional_summary_is_none_when_missing(self):
        entry = self._make_entry()
        entry["summary"] = None
        result = normalise_feed_entries([entry], source_name="S")
        assert result[0]["summary"] is None

    def test_optional_author_is_none_when_missing(self):
        entry = self._make_entry()
        entry["author"] = None
        result = normalise_feed_entries([entry], source_name="S")
        assert result[0]["author"] is None

    def test_content_is_unwrapped(self):
        entry = self._make_entry(content=[{"value": "<p>Hello</p>"}])
        result = normalise_feed_entries([entry], source_name="S")
        assert result[0]["content"] == "<p>Hello</p>"

    def test_empty_entries_returns_empty_list(self):
        assert normalise_feed_entries([], source_name="S") == []


# ---------------------------------------------------------------------------
# unwrap_content
# ---------------------------------------------------------------------------

class TestUnwrapContent:
    def test_empty_list_returns_none(self):
        assert unwrap_content([]) is None

    def test_list_with_value_returns_first_value(self):
        assert unwrap_content([{"value": "<p>text</p>"}, {"value": "other"}]) == "<p>text</p>"

    def test_list_with_missing_value_key_returns_none(self):
        assert unwrap_content([{"type": "text/html"}]) is None


# ---------------------------------------------------------------------------
# is_plain_text_long_enough
# ---------------------------------------------------------------------------

class TestIsPlainTextLongEnough:
    def test_none_returns_false(self):
        assert is_plain_text_long_enough(None) is False

    def test_short_text_returns_false(self):
        assert is_plain_text_long_enough("short") is False

    def test_exactly_100_chars_returns_false(self):
        assert is_plain_text_long_enough("x" * 100) is False

    def test_101_chars_returns_true(self):
        assert is_plain_text_long_enough("x" * 101) is True


# ---------------------------------------------------------------------------
# fetch_html_string
# ---------------------------------------------------------------------------

class TestFetchHtmlString:
    def test_returns_response_text(self):
        mock_response = MagicMock()
        mock_response.text = "<html>content</html>"
        with patch("ingestion.rss.httpx.get", return_value=mock_response):
            assert fetch_html_string("http://example.com") == "<html>content</html>"


# ---------------------------------------------------------------------------
# get_embedded_html_string
# ---------------------------------------------------------------------------

class TestGetEmbeddedHtmlString:
    def test_joins_content_from_entries(self):
        entries = [{"content": "<p>One</p>"}, {"content": "<p>Two</p>"}]
        assert get_embedded_html_string(entries) == "<p>One</p>\n<p>Two</p>"

    def test_skips_entries_without_content(self):
        entries = [{"content": "<p>One</p>"}, {"content": None}, {"title": "No content"}]
        result = get_embedded_html_string(entries)
        assert "<p>One</p>" in result
        assert "None" not in result


# ---------------------------------------------------------------------------
# get_plain_text_from_embedded_html_string
# ---------------------------------------------------------------------------

class TestGetPlainTextFromEmbeddedHtmlString:
    def test_delegates_to_trafilatura(self):
        with patch("ingestion.rss.trafilatura.extract", return_value="Extracted text") as mock_extract:
            result = get_plain_text_from_embedded_html_string("<html>...</html>")
        mock_extract.assert_called_once_with("<html>...</html>")
        assert result == "Extracted text"