"""Thin boundaries for the currently human-operated AI generation backends."""

from .image import IMAGE_BACKEND, compile_image_prompt, prepare_image_job, register_image_candidate
from .video import VIDEO_BACKEND, approve_video_candidate, prepare_video_job, register_video_candidate

__all__ = [
    "IMAGE_BACKEND",
    "VIDEO_BACKEND",
    "compile_image_prompt",
    "prepare_image_job",
    "prepare_video_job",
    "register_image_candidate",
    "register_video_candidate",
    "approve_video_candidate",
]
