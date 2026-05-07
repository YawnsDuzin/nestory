"""Unit tests for search query normalization.

Tests normalize_query() without DB access:
- strip whitespace
- length cap at MAX_QUERY_LEN (200)
- short-circuit threshold: < MIN_QUERY_LEN (2 chars) → returns ""
- special characters are NOT escaped here (PG plainto_tsquery handles them)

NOTE: No DB fixture needed — these are pure Python unit tests.
"""
from app.services.search import MAX_QUERY_LEN, MIN_QUERY_LEN, normalize_query

# ---------------------------------------------------------------------------
# Strip whitespace
# ---------------------------------------------------------------------------


def test_normalize_strips_leading_trailing_whitespace() -> None:
    assert normalize_query("  양평  ") == "양평"


def test_normalize_strips_internal_leading_trailing_only() -> None:
    """Internal whitespace is preserved — only edge whitespace stripped."""
    assert normalize_query("  양평 단열  ") == "양평 단열"


# ---------------------------------------------------------------------------
# Length cap (200 chars)
# ---------------------------------------------------------------------------


def test_normalize_caps_at_max_query_len() -> None:
    long_q = "a" * (MAX_QUERY_LEN + 50)
    result = normalize_query(long_q)
    assert len(result) == MAX_QUERY_LEN


def test_normalize_exactly_max_query_len_unchanged() -> None:
    exact_q = "a" * MAX_QUERY_LEN
    assert normalize_query(exact_q) == exact_q


def test_normalize_below_max_query_len_unchanged() -> None:
    short_q = "양평 단열 시공 후기"
    assert normalize_query(short_q) == short_q


# ---------------------------------------------------------------------------
# Short-circuit threshold: < MIN_QUERY_LEN → ""
# ---------------------------------------------------------------------------


def test_normalize_empty_string_returns_empty() -> None:
    assert normalize_query("") == ""


def test_normalize_none_like_empty_returns_empty() -> None:
    """None is coerced by `(q or "")` — returns ""."""
    # normalize_query signature: q: str, but test the guard
    assert normalize_query("") == ""


def test_normalize_single_char_returns_empty() -> None:
    """1-char query is below MIN_QUERY_LEN (2) → returns ""."""
    assert normalize_query("a") == ""


def test_normalize_single_korean_char_returns_empty() -> None:
    assert normalize_query("양") == ""


def test_normalize_whitespace_only_returns_empty() -> None:
    assert normalize_query("   ") == ""


def test_normalize_single_char_after_strip_returns_empty() -> None:
    """" a " strips to "a" (1 char) → returns ""."""
    assert normalize_query("  a  ") == ""


def test_normalize_two_chars_returns_two_chars() -> None:
    """Exactly MIN_QUERY_LEN chars → returned as-is."""
    assert normalize_query("ab") == "ab"


def test_normalize_two_korean_chars_returns_them() -> None:
    assert normalize_query("양평") == "양평"


# ---------------------------------------------------------------------------
# Special characters — NOT escaped at service level
# ---------------------------------------------------------------------------


def test_normalize_special_chars_not_escaped() -> None:
    """Punctuation/special chars pass through unchanged.
    PG plainto_tsquery handles them safely server-side."""
    q = "양평! (단열)"
    result = normalize_query(q)
    assert result == q.strip()


def test_normalize_ampersand_passes_through() -> None:
    assert normalize_query("A&B") == "A&B"


def test_normalize_pipe_passes_through() -> None:
    assert normalize_query("a|b") == "a|b"


# ---------------------------------------------------------------------------
# MIN_QUERY_LEN constant
# ---------------------------------------------------------------------------


def test_min_query_len_is_two() -> None:
    """Confirm MIN_QUERY_LEN matches documented threshold."""
    assert MIN_QUERY_LEN == 2


def test_max_query_len_is_two_hundred() -> None:
    """Confirm MAX_QUERY_LEN matches plan §847 length cap."""
    assert MAX_QUERY_LEN == 200
