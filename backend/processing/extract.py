from typing import Optional
from fastapi import UploadFile
from PyPDF2 import PdfReader
from io import BytesIO
from pdfminer.high_level import extract_text as pdfminer_extract_text

#TODO make PDF more readable

async def read_pdf_text(upload_file: UploadFile) -> str:
    """Extract text from PDF, trying PyPDF2 first, then pdfminer as fallback."""
    content = await upload_file.read()
    if not content:
        return ""

    # 1) PyPDF2
    try:
        reader = PdfReader(BytesIO(content))
        pages_text = []
        for page in reader.pages:
            try:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            except Exception:
                continue
        text = "\n\n".join(pages_text).strip()
        # If we got something non-trivial, use it
        if len(text) > 100:
            return text
    except Exception:
        pass

    # 2) pdfminer fallback
    try:
        text = pdfminer_extract_text(BytesIO(content)) or ""
        return text.strip()
    except Exception:
        return ""


async def extract_text_from_inputs(
    file: Optional[UploadFile], text: str
) -> str:
    """
    Priority:
    1) If PDF file provided and we can read something -> use that.
    2) Else, if `text` non-empty -> use that.
    3) Else -> error.
    """
    extracted = ""

    if file is not None:
        extracted = await read_pdf_text(file)

    # If file is empty or not provided, fall back to text
    if not extracted and text:
        extracted = text.strip()

    if not extracted:
        raise ValueError("No usable content provided (PDF or text).")

    # Basic cleanup
    extracted = clean_extracted_text(extracted)
    return extracted

import re

def clean_extracted_text(raw: str) -> str:
    # Normalize line endings
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Fix hyphenated line breaks: "some-\nthing" -> "something"
    text = re.sub(r"-\s*\n\s*", "", text)

    # Collapse multiple spaces *per line*, keep newlines
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        # collapse internal whitespace but keep one space between tokens
        collapsed = " ".join(line.split())
        cleaned_lines.append(collapsed)

    # Rejoin lines
    text = "\n".join(cleaned_lines)

    # Remove more than 2 empty lines in a row
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Trim spaces around punctuation (", ." -> ",", etc.)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)

    # Final strip
    return text.strip()

