from __future__ import annotations

import argparse
from typing import Optional, Sequence

from . import __version__
from .config import StarsAnimationConfig
from .generator import generate_scrolling_stars


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="star-growth",
        description="Turn your GitHub star growth into a scrolling video.",
    )
    parser.add_argument("--owner", default="Esubaalew",
                        help="GitHub repository owner (default: %(default)s)")
    parser.add_argument("--repo", default="run",
                        help="GitHub repository name (default: %(default)s)")
    parser.add_argument(
        "--title", help="Override the header label (defaults to owner/repo)")
    parser.add_argument(
        "--output",
        default="star_growth.mp4",
        help=(
            "Destination video path or directory ('.mp4' added when missing). "
            "Existing files are preserved by generating a numbered filename."
        ),
    )
    parser.add_argument("--fps", type=int, default=24,
                        help="Frames per second for the video")
    parser.add_argument(
        "--duration",
        type=float,
        default=8.0,
        help="Animation duration in seconds (controls scroll speed)",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        default=30,
        help="Maximum number of stargazers to display",
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
        "--easing",
        choices=["ease-out", "linear"],
        default="ease-out",
        help="Easing curve for scroll progress",
    )
    parser.add_argument(
        "--frames-dir", help="Directory to store intermediate frames")
    parser.add_argument("--keep-frames", action="store_true",
                        help="Keep frame PNGs after rendering")
    parser.add_argument(
        "--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout in seconds for each GitHub API request",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries for GitHub API requests when rate limited or transient errors occur",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=2.0,
        help="Base number of seconds to back off between retries",
    )
    parser.add_argument(
        "--avatar-workers",
        type=int,
        default=4,
        help="Number of concurrent workers to download avatar images",
    )
    parser.add_argument(
        "--no-progress",
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

    config = StarsAnimationConfig(
        owner=args.owner,
        repo=args.repo,
        title=args.title,
        output=args.output,
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
    )

    return generate_scrolling_stars(config)


if __name__ == "__main__":
    main()
