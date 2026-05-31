import pytest
import httpx
from unittest.mock import patch, MagicMock
from ingestion.fulltext import resolve_full_text, quality_gate

LONG_TEXT = "x" * 150


def _article(**kwargs):
    base = {"content": None, "summary": None, "url": "http://example.com/article"}
    base.update(kwargs)
    return base


class TestResolveFullText:
    def test_content_branch_used_when_extract_succeeds(self):
        article = _article(content="<p>Some embedded HTML</p>")
        with patch("ingestion.fulltext.trafilatura.extract", return_value=LONG_TEXT):
            result = resolve_full_text(article)
        assert result == LONG_TEXT

    def test_summary_branch_used_when_content_extract_fails(self):
        article = _article(content="<p>html</p>", summary="A valid summary blurb.")

        def extract_side_effect(text):
            # content extract returns None; summary extract returns text
            if text == "<p>html</p>":
                return None
            return LONG_TEXT

        with patch("ingestion.fulltext.trafilatura.extract", side_effect=extract_side_effect):
            result = resolve_full_text(article)
        assert result == LONG_TEXT

    def test_url_branch_used_when_no_content_or_summary(self):
        article = _article(url="http://example.com/article")
        mock_response = MagicMock()
        mock_response.text = "<html>full page</html>"

        with patch("ingestion.fulltext.trafilatura.extract", return_value=LONG_TEXT), \
             patch("ingestion.fulltext.httpx.get", return_value=mock_response):
            result = resolve_full_text(article)
        assert result == LONG_TEXT

    def test_returns_none_when_httpx_raises(self):
        article = _article(url="http://example.com/article")
        with patch("ingestion.fulltext.trafilatura.extract", return_value=None), \
             patch("ingestion.fulltext.httpx.get", side_effect=httpx.RequestError("timeout")):
            result = resolve_full_text(article)
        assert result is None

    def test_returns_none_when_http_non_2xx(self):
        article = _article(url="http://example.com/article")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        with patch("ingestion.fulltext.trafilatura.extract", return_value=None), \
             patch("ingestion.fulltext.httpx.get", return_value=mock_response):
            result = resolve_full_text(article)
        assert result is None

    def test_returns_none_when_all_extract_calls_fail(self):
        article = _article(content="<p>x</p>", summary="short", url="http://example.com")
        mock_response = MagicMock()
        mock_response.text = "<html/>"
        with patch("ingestion.fulltext.trafilatura.extract", return_value=None), \
             patch("ingestion.fulltext.httpx.get", return_value=mock_response):
            result = resolve_full_text(article)
        assert result is None

    def test_no_url_skips_url_branch(self):
        article = {"content": None, "summary": None, "url": None}
        with patch("ingestion.fulltext.trafilatura.extract", return_value=None) as mock_extract:
            result = resolve_full_text(article)
        assert result is None


class TestQualityGate:
    def test_none_fails(self):
        assert quality_gate(None) is False

    def test_empty_string_fails(self):
        assert quality_gate("") is False

    def test_whitespace_only_fails(self):
        assert quality_gate("   \n\t  ") is False

    def test_short_text_fails(self):
        assert quality_gate("too short") is False

    def test_exactly_100_chars_fails(self):
        assert quality_gate("x" * 100) is False

    def test_101_chars_passes(self):
        assert quality_gate("x" * 101) is True