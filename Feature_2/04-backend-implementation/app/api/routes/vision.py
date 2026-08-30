from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from app.api.dependencies import SettingsDependency
from app.errors import ConflictError, InvalidOperationError, ResourceNotFoundError
from app.schemas.vision import (
    VideoUploadResponse,
    VisionRuntimeStatus,
    VisionSourceType,
    VisionStartRequest,
)
from app.vision.vision_runtime import VisionRuntime, VisionSource

router = APIRouter(prefix="/vision", tags=["Vision"])

ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
UPLOAD_CHUNK_BYTES = 1024 * 1024


def get_runtime(request: Request) -> VisionRuntime:
    return request.app.state.vision_runtime


def resolve_video(settings: SettingsDependency, video_id: str) -> Path:
    path = (settings.video_upload_dir / video_id).resolve()
    if path.parent != settings.video_upload_dir.resolve():
        raise InvalidOperationError("Invalid video identifier")
    if not path.is_file():
        raise ResourceNotFoundError(f"Validation video {video_id} was not found")
    return path


@router.post(
    "/videos",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a validation video",
)
async def upload_video(
    file: Annotated[UploadFile, File(description="Recorded garment workflow")],
    settings: SettingsDependency,
) -> VideoUploadResponse:
    original_name = Path(file.filename or "video").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise InvalidOperationError("Video must use MP4, MOV, AVI, MKV or M4V format")

    settings.video_upload_dir.mkdir(parents=True, exist_ok=True)
    video_id = f"{uuid4()}{suffix}"
    destination = settings.video_upload_dir / video_id
    size = 0
    try:
        with destination.open("xb") as output:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                size += len(chunk)
                if size > settings.vision_upload_max_bytes:
                    raise InvalidOperationError("Uploaded video exceeds the size limit")
                output.write(chunk)
        if size == 0:
            raise InvalidOperationError("Uploaded video is empty")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return VideoUploadResponse(
        video_id=video_id,
        original_name=original_name,
        size_bytes=size,
    )


@router.delete(
    "/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a stored validation video",
)
def delete_video(
    video_id: str,
    request: Request,
    settings: SettingsDependency,
) -> Response:
    path = resolve_video(settings, video_id)
    runtime_status = get_runtime(request).status
    if (
        runtime_status.state in VisionRuntime.ACTIVE_STATES
        and runtime_status.source_label == f"video:{video_id}"
    ):
        raise ConflictError("Cannot delete a video while it is being analyzed")
    path.unlink()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sessions/{session_id}/start",
    response_model=VisionRuntimeStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start camera or recorded-video analysis",
)
def start_vision(
    session_id: int,
    payload: VisionStartRequest,
    request: Request,
    settings: SettingsDependency,
) -> VisionRuntimeStatus:
    if payload.source_type == VisionSourceType.VIDEO:
        assert payload.video_id is not None
        source = VisionSource(
            source_type=payload.source_type,
            video_path=resolve_video(settings, payload.video_id),
        )
    else:
        source = VisionSource(
            source_type=payload.source_type,
            camera_index=payload.camera_index,
        )
    return get_runtime(request).start(session_id, source)


@router.get(
    "/status",
    response_model=VisionRuntimeStatus,
    summary="Read live inference status",
)
def vision_status(request: Request) -> VisionRuntimeStatus:
    return get_runtime(request).status


@router.post(
    "/stop",
    response_model=VisionRuntimeStatus,
    summary="Stop and release the active capture source",
)
def stop_vision(request: Request) -> VisionRuntimeStatus:
    return get_runtime(request).stop()


@router.get(
    "/preview",
    summary="Attach to the latest-frame MJPEG preview",
    responses={200: {"content": {"multipart/x-mixed-replace": {}}}},
)
def preview_stream(request: Request) -> StreamingResponse:
    runtime = get_runtime(request)
    current = runtime.status
    if current.state not in VisionRuntime.ACTIVE_STATES:
        raise ConflictError("Vision preview is not running")
    return StreamingResponse(
        runtime.publisher.iter_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/preview/frame",
    summary="Read one authenticated preview frame through Electron IPC",
    responses={200: {"content": {"image/jpeg": {}}}},
)
def preview_frame(request: Request) -> Response:
    runtime = get_runtime(request)
    current = runtime.status
    if current.state not in VisionRuntime.ACTIVE_STATES:
        raise ConflictError("Vision preview is not running")
    runtime.publisher.mark_preview_attached()
    jpeg = runtime.publisher.latest_jpeg()
    if jpeg is None:
        raise ConflictError("The first preview frame is not ready")
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )
