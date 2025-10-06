from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(slots=True)
class StarsAnimationConfig:
    """Runtime configuration for rendering a star growth animation."""

    owner: str = "Esubaalew"
    repo: str = "run"
    title: Optional[str] = None
    output: str = "star_growth.mp4"
    output_format: str = "mp4"
    fps: int = 24
    duration_seconds: float = 8.0
    max_entries: int = 30
    width: int = 940
    viewport_height: int = 520
    entry_height: int = 108
    frames_dir: Optional[str] = None
    cleanup_frames: bool = True
    token: Optional[str] = None
    request_timeout: float = 10.0
    max_retries: int = 3
    retry_backoff: float = 2.0
    easing: str = "ease-out"
    avatar_workers: int = 4
    show_progress: bool = True
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None

    def resolved_frames_dir(self) -> str:
        """Directory to render frame images to, creating it if necessary."""

        if self.frames_dir:
            os.makedirs(self.frames_dir, exist_ok=True)
            return self.frames_dir
        return tempfile.mkdtemp(prefix="star_growth_frames_")

    @property
    def repo_label(self) -> str:
        return self.title or f"{self.owner}/{self.repo}"

    @property
    def auth_token(self) -> Optional[str]:
        return self.token or os.getenv("GITHUB_TOKEN")

    @property
    def avatar_worker_count(self) -> int:
        return max(1, self.avatar_workers)

    @property
    def normalized_output_format(self) -> str:
        fmt = (self.output_format or "mp4").lower()
        return "gif" if fmt == "gif" else "mp4"

    @staticmethod
    def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @property
    def start_at_utc(self) -> Optional[datetime]:
        return self._as_utc(self.start_datetime)

    @property
    def end_at_utc(self) -> Optional[datetime]:
        return self._as_utc(self.end_datetime)
