def chunk_text(text: str, size_words: int, overlap_words: int) -> list[str]:
    if size_words <= 0:
        raise ValueError("size_words must be positive.")
    if overlap_words < 0 or overlap_words >= size_words:
        raise ValueError("overlap_words must be between 0 and size_words - 1.")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = size_words - overlap_words
    for start in range(0, len(words), step):
        chunk_words = words[start : start + size_words]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + size_words >= len(words):
            break
    return chunks
