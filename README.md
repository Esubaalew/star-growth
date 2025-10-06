# star-growth

[![PyPI](https://img.shields.io/pypi/v/star-growth.svg)](https://pypi.org/project/star-growth/)
[![Release pipeline](https://github.com/esubaalew/star-growth/actions/workflows/publish.yml/badge.svg)](https://github.com/esubaalew/star-growth/actions/workflows/publish.yml)

Turn your GitHub star growth into a scrolling MP4 video with a single command-line tool.

## Install

```bash
pip install star-growth
```

FFmpeg is pulled in automatically through `imageio-ffmpeg`, but make sure your platform can build wheels for Pillow and MoviePy.

## Quick start

Run the CLI after installing the package:

```bash
star-growth --owner esubaalew --repo run
```

The command fetches the latest stargazers, renders a GitHub-style card, and writes `star_growth.mp4` in the working directory.

### Popular options

- `--output stars.mp4` – customise the export path (a numeric suffix prevents overwrites)
- `--duration 8` and `--fps 24` – tune animation pacing
- `--max-entries 30` – limit the number of rows rendered
- `--token $GITHUB_TOKEN` – avoid public API rate limits
- `--no-progress` – hide the frame rendering progress bar

Run `star-growth --help` or `star-growth --version` for more details.

## Sample output

<video controls loop muted playsinline width="100%">
	<source src="docs/assets/run-stars.mp4" type="video/mp4" />
	Your browser does not support the video tag.
</video>

Generated from the latest stargazers on [`esubaalew/run`](https://github.com/Esubaalew/run).

## Use it from Python

```python
from star_growth import StarsAnimationConfig, generate_scrolling_stars

config = StarsAnimationConfig(
	owner="octocat",
	repo="Hello-World",
	output="stars.mp4",
)

video_path = generate_scrolling_stars(config)
print(f"Video saved to {video_path}")
```

Frames are written to a temporary directory and cleaned up automatically. Pass `cleanup_frames=False` (or `--keep-frames` on the CLI) to inspect them.

## Develop locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

The editable install keeps the CLI (`star-growth`) in sync with your workspace changes.

## Release automation

Tags that follow the `v*` pattern trigger the `Release` GitHub Actions workflow. To publish to PyPI, add a repository secret named `PYPI_API_TOKEN` containing an API token created in your PyPI account ("Publish" scope). The workflow will build the wheel and source tarball and upload them to https://pypi.org/project/star-growth/.

## Troubleshooting

- **Missing avatars** – GitHub occasionally rate-limits avatar requests; initials placeholders are rendered when that happens.
- **Fonts look off** – Install `DejaVuSans` locally or update the font paths inside `star_growth/generator.py`.
- **Large repositories** – Provide a personal access token and raise `--max-retries` / `--retry-backoff` when you expect heavy traffic.

Be mindful of GitHub's terms of service and the privacy expectations of your stargazers when sharing renders.

## License

Released under the [Apache License 2.0](./LICENSE) by [Esubalew Chekol](https://github.com/esubaalew). See the upstream copy at [github.com/esubaalew/star-growth](https://github.com/esubaalew/star-growth) for the canonical license record.
