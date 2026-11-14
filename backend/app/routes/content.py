"""Content endpoints: segment preview, upload parsing, saved submissions."""
from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import db
from ..config import get_settings
from ..file_parser import UnsupportedFile, extract_text
from ..schemas import (
    SegmentOut,
    SegmentRequest,
    SegmentResponse,
    SubmissionCreate,
    SubmissionOut,
    SubmissionSummary,
    UploadResponse,
)
from ..segmenter import segment_content

router = APIRouter(prefix="/api", tags=["content"])


def _to_out(segments) -> list[SegmentOut]:
    return [SegmentOut(**s.model_dump(), word_count=len(s.text.split())) for s in segments]


def _check_length(content: str) -> None:
    limit = get_settings().max_content_chars
    if len(content) > limit:
        raise HTTPException(
            413, f"Content is {len(content):,} characters; the limit is {limit:,}."
        )


@router.post("/segment", response_model=SegmentResponse)
def preview_segments(req: SegmentRequest) -> SegmentResponse:
    """Stateless preview used by the workspace as the user types or pastes."""
    _check_length(req.content)
    segments, truncated = segment_content(
        req.content, req.content_type, get_settings().max_segments
    )
    out = _to_out(segments)
    return SegmentResponse(
        content_type=req.content_type,
        segments=out,
        total_words=sum(s.word_count for s in out),
        truncated=truncated,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    data = await file.read()
    try:
        text = extract_text(file.filename or "", data)
    except UnsupportedFile as exc:
        raise HTTPException(400, str(exc)) from exc
    if not text.strip():
        raise HTTPException(400, "That file appears to be empty.")
    return UploadResponse(filename=file.filename or "upload", text=text)


@router.post("/submissions", response_model=SubmissionOut, status_code=201)
def create_submission(req: SubmissionCreate) -> SubmissionOut:
    """Save a work exactly as written, together with its segments."""
    _check_length(req.content)
    segments, _ = segment_content(req.content, req.content_type, get_settings().max_segments)
    if not segments:
        raise HTTPException(422, "Nothing to test: the content is empty.")
    saved = db.create_submission(req.title.strip(), req.content_type, req.content, segments)
    return SubmissionOut(**{**saved, "segments": _to_out_dicts(saved["segments"])})


def _to_out_dicts(rows: list[dict]) -> list[SegmentOut]:
    return [SegmentOut(**r, word_count=len(r["text"].split())) for r in rows]


@router.get("/submissions", response_model=list[SubmissionSummary])
def list_submissions():
    return db.list_submissions()


@router.get("/submissions/{sub_id}", response_model=SubmissionOut)
def get_submission(sub_id: str) -> SubmissionOut:
    saved = db.get_submission(sub_id)
    if saved is None:
        raise HTTPException(404, "Submission not found.")
    return SubmissionOut(**{**saved, "segments": _to_out_dicts(saved["segments"])})


@router.delete("/submissions/{sub_id}", status_code=204)
def delete_submission(sub_id: str) -> None:
    if not db.delete_submission(sub_id):
        raise HTTPException(404, "Submission not found.")
