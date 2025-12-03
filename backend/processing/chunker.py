from typing import List


def chunk_text(
    text: str,
    max_chars: int = 2000,
    overlap: int = 200,
) -> List[str]:
    """
    Very simple text chunker by characters with overlap.
    Good enough for a first version.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks
