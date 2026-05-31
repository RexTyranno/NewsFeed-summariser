import pytest
from ingestion.dedup import normalise_url, content_fingerprint, dedup_key, is_duplicate


class TestNormaliseUrl:
    def test_lowercases(self):
        assert normalise_url("HTTP://Example.COM/Path") == "http://example.com/path"

    def test_strips_whitespace(self):
        assert normalise_url("  https://example.com  ") == "https://example.com"

    def test_already_clean(self):
        assert normalise_url("https://example.com") == "https://example.com"


class TestContentFingerprint:
    def test_same_text_same_hash(self):
        assert content_fingerprint("hello world") == content_fingerprint("hello world")

    def test_different_text_different_hash(self):
        assert content_fingerprint("hello world") != content_fingerprint("hello world!")

    def test_returns_hex_string(self):
        fp = content_fingerprint("test")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


class TestDedupKey:
    def test_returns_tuple(self):
        key = dedup_key("https://example.com", "abc123")
        assert isinstance(key, tuple)
        assert len(key) == 2

    def test_contains_correct_values(self):
        url, fp = "https://example.com", "abc123"
        assert dedup_key(url, fp) == (url, fp)


class TestIsDuplicate:
    def test_first_occurrence_is_not_duplicate(self):
        seen = set()
        assert is_duplicate("https://example.com", "unique text", seen) is False

    def test_first_occurrence_adds_to_seen(self):
        seen = set()
        is_duplicate("https://example.com", "unique text", seen)
        assert len(seen) == 1

    def test_second_occurrence_same_url_same_body_is_duplicate(self):
        seen = set()
        is_duplicate("https://example.com", "same body", seen)
        assert is_duplicate("https://example.com", "same body", seen) is True

    def test_same_url_different_body_is_not_duplicate(self):
        seen = set()
        is_duplicate("https://example.com", "body one", seen)
        assert is_duplicate("https://example.com", "body two", seen) is False

    def test_url_normalised_before_keying(self):
        seen = set()
        is_duplicate("HTTPS://EXAMPLE.COM", "same body", seen)
        # lowercase variant should be recognised as duplicate
        assert is_duplicate("https://example.com", "same body", seen) is True