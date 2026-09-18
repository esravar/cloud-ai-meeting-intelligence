import pytest

from app.chunking import chunk_text


def test_chunks_with_overlap() -> None:
    text = "one two three four five six seven eight nine ten"

    chunks = chunk_text(text, size_words=4, overlap_words=1)

    assert chunks == [
        "one two three four",
        "four five six seven",
        "seven eight nine ten",
    ]


def test_short_text_creates_one_chunk() -> None:
    assert chunk_text("short meeting transcript", 10, 2) == ["short meeting transcript"]


def test_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="overlap_words"):
        chunk_text("some text", size_words=5, overlap_words=5)
