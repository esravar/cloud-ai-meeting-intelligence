import uuid
from pathlib import Path
from typing import Protocol

from openai import OpenAI
from pypdf import PdfReader

from app.config import Settings


class FileProcessingError(RuntimeError):
    pass


class AudioTranscriber(Protocol):
    def transcribe(self, path: Path) -> str: ...


class OpenAITranscriber:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise FileProcessingError(
                "OPENAI_API_KEY is required for audio transcription."
            )
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )
        self._model = settings.transcription_model

    def transcribe(self, path: Path) -> str:
        with path.open("rb") as audio:
            result = self._client.audio.transcriptions.create(
                model=self._model,
                file=audio,
            )
        text = result.text.strip()
        if not text:
            raise FileProcessingError("Audio transcription was empty.")
        return text


def extract_pdf_text(path: Path) -> str:
    try:
        reader = PdfReader(path)
        pages = [
            f"[Page {number}]\n{page.extract_text() or ''}"
            for number, page in enumerate(reader.pages, start=1)
        ]
    except Exception as exc:
        raise FileProcessingError("The PDF could not be read.") from exc
    text = "\n\n".join(pages).strip()
    if len(text) < 20:
        raise FileProcessingError(
            "The PDF contains no extractable text; OCR is required."
        )
    return text


def safe_upload_path(
    upload_dir: Path, original_filename: str, allowed_suffixes: set[str]
) -> Path:
    suffix = Path(original_filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise FileProcessingError(f"Unsupported file type: {suffix or 'none'}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir / f"{uuid.uuid4()}{suffix}"
