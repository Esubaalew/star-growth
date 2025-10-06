from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .config import StarsAnimationConfig
from .generator import generate_scrolling_stars


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="star-growth",
        description="Turn your GitHub star growth into a scrolling MP4 or GIF.",
    )
    parser.add_argument("-u", "--owner", default="Esubaalew",
                        help="GitHub repository owner (default: %(default)s)")
    parser.add_argument("-r", "--repo", default="run",
                        help="GitHub repository name (default: %(default)s)")
    parser.add_argument(
        "-t", "--title", help="Override the header label (defaults to owner/repo)")
    parser.add_argument(
        "-o", "--output",
        default="star_growth.mp4",
        help=(
            "Destination path or directory. Uses '.mp4' or '.gif' extension "
            "based on --format or the provided file name and avoids overwrites "
            "by appending a numeric suffix."
        ),
    )
    parser.add_argument(
        "-f", "--format",
        choices=["mp4", "gif"],
        default="mp4",
        help="Choose the export format (mp4 for video, gif for animated image)",
    )
    parser.add_argument("-p", "--fps", type=int, default=24,
                        help="Frames per second for the video")
    parser.add_argument(
        "-d", "--duration",
        type=float,
        default=8.0,
        help="Animation duration in seconds (controls scroll speed)",
    )
    parser.add_argument(
        "-m", "--max-entries",
        type=int,
        default=30,
        help="Maximum number of stargazers to display",
    )
    parser.add_argument(
        "-s", "--start-date",
        help="Only include stars on/after this date (UTC). Accepts YYYY-MM-DD or ISO 8601",
    )
    parser.add_argument(
        "-E", "--end-date",
        help="Only include stars on/before this date (UTC). Accepts YYYY-MM-DD or ISO 8601",
    )
    parser.add_argument(
        "--viewport-height",
        type=int,
        default=520,
        help="Viewport height for the scrolling window in pixels",
    )
    parser.add_argument(
        "--entry-height",
        type=int,
        default=108,
        help="Row height for each stargazer entry in pixels",
    )
    parser.add_argument("--width", type=int, default=940,
                        help="Canvas width in pixels")
    parser.add_argument(
        "-e", "--easing",
        choices=["ease-out", "linear"],
        default="ease-out",
        help="Easing curve for scroll progress",
    )
    parser.add_argument(
        "-F", "--frames-dir", help="Directory to store intermediate frames")
    parser.add_argument("-k", "--keep-frames", action="store_true",
                        help="Keep frame PNGs after rendering")
    parser.add_argument(
        "-T", "--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)")
    parser.add_argument(
        "-w", "--timeout",
        type=float,
        default=10.0,
        help="Timeout in seconds for each GitHub API request",
    )
    parser.add_argument(
        "-R", "--max-retries",
        type=int,
        default=3,
        help="Maximum retries for GitHub API requests when rate limited or transient errors occur",
    )
    parser.add_argument(
        "-b", "--retry-backoff",
        type=float,
        default=2.0,
        help="Base number of seconds to back off between retries",
    )
    parser.add_argument(
        "-a", "--avatar-workers",
        type=int,
        default=4,
        help="Number of concurrent workers to download avatar images",
    )
    parser.add_argument(
        "-q", "--no-progress",
        dest="show_progress",
        action="store_false",
        help="Disable the frame rendering progress bar",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the installed version and exit",
    )
    parser.set_defaults(show_progress=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> str:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    def _parse_date(value: Optional[str], *, end: bool = False) -> Optional[datetime]:
        if not value:
            return None
        original = value
        try:
            dt = datetime.fromisoformat(value)
            full_day = len(value) <= 10
        except ValueError:
            if len(value) == 10:
                dt = datetime.strptime(value, "%Y-%m-%d")
                full_day = True
            else:
                parser.error(
                    f"Invalid date '{value}'. Use YYYY-MM-DD or a full ISO 8601 timestamp."
                )
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        if full_day and end:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt

    output_format = args.format.lower()
    output_arg = args.output
    if output_arg:
        suffix = Path(output_arg).suffix.lower()
        if suffix in {".mp4", ".gif"}:
            output_format = suffix.lstrip(".")

    start_dt = _parse_date(args.start_date, end=False)
    end_dt = _parse_date(args.end_date, end=True)
    if start_dt and end_dt and start_dt > end_dt:
        parser.error("--start-date must be before or equal to --end-date")

    config_kwargs = dict(
        owner=args.owner,
        repo=args.repo,
        title=args.title,
        fps=args.fps,
        duration_seconds=args.duration,
        max_entries=args.max_entries,
        viewport_height=args.viewport_height,
        entry_height=args.entry_height,
        width=args.width,
        frames_dir=args.frames_dir,
        cleanup_frames=not args.keep_frames,
        token=args.token,
        request_timeout=args.timeout,
        max_retries=args.max_retries,
        retry_backoff=args.retry_backoff,
        easing=args.easing,
        avatar_workers=args.avatar_workers,
        show_progress=args.show_progress,
        output_format=output_format,
        start_datetime=start_dt,
        end_datetime=end_dt,
    )
    if output_arg is not None:
        config_kwargs["output"] = output_arg

    config = StarsAnimationConfig(**config_kwargs)

    return generate_scrolling_stars(config)


if __name__ == "__main__":
    main()
