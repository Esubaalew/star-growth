from __future__ import annotations

import io
import math
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Sequence
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

try:
    from tqdm import tqdm
except Exception:
    tqdm = None

from .config import StarsAnimationConfig
from .github import GitHubAPIError, fetch_repo_and_stargazers

# Layout constants tuned to mimic reference UI
CARD_MARGIN_X = 140
CARD_TOP = 62
CARD_RADIUS = 26
CARD_PADDING_X = 42
CARD_PADDING_Y = 30
BUTTON_WIDTH = 208
BUTTON_HEIGHT = 50
BUTTON_RADIUS = 16
COUNT_RADIUS = 14
AVATAR_DIAMETER = 60

# Palette pulled from screenshot cues
BG_TOP = (8, 12, 22)
BG_BOTTOM = (22, 27, 40)
CARD_BG = (255, 255, 255, 248)
CARD_BORDER = (233, 237, 243, 255)
DIVIDER_COLOR = (232, 235, 240, 255)
LINK_COLOR = (22, 111, 227, 255)
TEXT_PRIMARY = (33, 38, 45, 255)
TEXT_SECONDARY = (114, 121, 133, 255)
BUTTON_BG = (249, 250, 252, 255)
BUTTON_BORDER = (214, 221, 229, 255)
STAR_ICON_COLOR = (240, 176, 0, 255)
AVATAR_PLACEHOLDER = (236, 239, 244, 255)
DEFAULT_OUTPUT_NAME = "star_growth.mp4"
DEFAULT_GIF_OUTPUT_NAME = "star_growth.gif"


def vertical_gradient(size, top_color, bottom_color):
    width, height = size
    if height <= 0:
        return Image.new("RGBA", size, top_color + (255,))
    data = []
    for y in range(height):
        ratio = y / (height - 1) if height > 1 else 0
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        data.extend([(r, g, b, 255)] * width)
    gradient = Image.new("RGBA", size)
    gradient.putdata(data)
    return gradient


def draw_star_shape(draw_obj, center, radius, fill):
    cx, cy = center
    points = []
    for idx in range(10):
        angle = math.pi / 2 + idx * math.pi / 5
        r = radius if idx % 2 == 0 else radius * 0.45
        x = cx + r * math.cos(angle)
        y = cy - r * math.sin(angle)
        points.append((x, y))
    draw_obj.polygon(points, fill=fill)


def draw_text_chain(draw_obj, xy, segments):
    x, y = xy
    for text, font, color in segments:
        if not text:
            continue
        draw_obj.text((x, y), text, font=font, fill=color)
        try:
            bbox = draw_obj.textbbox((x, y), text, font=font)
            x = bbox[2]
        except Exception:
            try:
                advance, _ = font.getsize(text)
                x += advance
            except Exception:
                x += len(text) * 8


def _download_avatar(url: str, timeout: float) -> Image.Image | None:
    if not url:
        return None
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except Exception:
        return None


def prefetch_avatars(urls: Sequence[str], config: StarsAnimationConfig) -> Dict[str, Image.Image | None]:
    cache: Dict[str, Image.Image | None] = {}
    unique_urls = [url for url in dict.fromkeys(urls) if url]
    if not unique_urls:
        return cache

    timeout = config.request_timeout
    workers = config.avatar_worker_count

    if workers <= 1 or len(unique_urls) == 1:
        for url in unique_urls:
            cache[url] = _download_avatar(url, timeout)
        return cache

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(
            _download_avatar, url, timeout): url for url in unique_urls}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                cache[url] = future.result()
            except Exception as exc:
                print(f"Warning: avatar fetch failed for {url}: {exc}")
                cache[url] = None
    return cache


def _is_directory_hint(raw_path: str) -> bool:
    if raw_path.endswith(os.sep):
        return True
    try:
        return Path(raw_path).expanduser().exists() and Path(raw_path).is_dir()
    except Exception:
        return False


def _ensure_extension(path: Path, suffix: str) -> Path:
    if path.suffix:
        return path
    if not suffix.startswith("."):
        suffix = "." + suffix
    return path.with_suffix(suffix)


def _unique_output_path(base_path: Path) -> Path:
    candidate = base_path
    counter = 1
    suffix = "".join(base_path.suffixes)
    if suffix:
        name_without_suffix = base_path.name[: -len(suffix)]
    else:
        name_without_suffix = base_path.name

    while candidate.exists():
        numbered_name = f"{name_without_suffix} ({counter}){suffix}"
        candidate = base_path.parent / numbered_name
        counter += 1
    return candidate


def resolve_output_path(config: StarsAnimationConfig) -> Path:
    desired_format = config.normalized_output_format
    default_name = (
        DEFAULT_OUTPUT_NAME if desired_format == "mp4" else DEFAULT_GIF_OUTPUT_NAME
    )

    raw = config.output or default_name
    path = Path(raw).expanduser()

    if _is_directory_hint(raw):
        path = path / default_name
    elif not path.suffix:
        path = _ensure_extension(path, f".{desired_format}")

    suffix = path.suffix.lower()
    if suffix in {".mp4", ".gif"}:
        resolved_format = suffix.lstrip(".")
    else:
        path = path.with_suffix(f".{desired_format}")
        resolved_format = desired_format

    if resolved_format == "gif" and path.name == DEFAULT_OUTPUT_NAME:
        path = path.with_name(DEFAULT_GIF_OUTPUT_NAME)

    config.output_format = resolved_format
    parent = path.parent if str(path.parent) else Path(".")
    os.makedirs(parent, exist_ok=True)
    return _unique_output_path(path)


def _final_star_count(current_stars: int) -> int:
    return max(0, current_stars)


def _parse_github_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _filter_stargazers_by_date(
    stargazers: Sequence[dict],
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> List[dict]:
    if not start_dt and not end_dt:
        return list(stargazers)

    filtered: List[dict] = []
    for sg in stargazers:
        ts = _parse_github_timestamp(sg.get("starred_at"))
        if ts is None:
            if start_dt or end_dt:
                continue
            filtered.append(sg)
            continue
        if start_dt and ts < start_dt:
            continue
        if end_dt and ts > end_dt:
            continue
        filtered.append(sg)
    return filtered


def build_entries(stargazers: Sequence[dict], current_stars: int, config: StarsAnimationConfig):
    entries = []
    total = max(1, len(stargazers))
    for offset, sg in enumerate(stargazers[: config.max_entries]):
        login = sg.get("login") or "unknown"
        starred_at = sg.get("starred_at")
        if starred_at:
            try:
                dt = datetime.fromisoformat(starred_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%b %d, %Y")
            except Exception:
                date_str = starred_at
        else:
            date_str = ""
        if current_stars > 0:
            rank_val = max(1, current_stars - offset)
        else:
            rank_val = max(1, total - offset)
        entries.append(
            {
                "login": login,
                "date": date_str,
                "rank": rank_val,
                "avatar_url": sg.get("avatar_url"),
            }
        )
    return entries


def _fallback_entries(config: StarsAnimationConfig) -> tuple[int, List[dict]]:
    now = datetime.utcnow()
    sample = []
    for idx in range(config.max_entries):
        sample.append(
            {
                "login": f"user{idx + 1}",
                "starred_at": now.isoformat() + "Z",
                "avatar_url": None,
            }
        )
    return config.max_entries, sample


def ease_value(name: str, t: float) -> float:
    if name == "linear":
        return t
    return 1 - (1 - t) ** 2


def generate_scrolling_stars(config: StarsAnimationConfig) -> str:
    frames_dir = config.resolved_frames_dir()
    os.makedirs(frames_dir, exist_ok=True)
    frame_files: List[str] = []
    session = requests.Session()
    created_temp_dir = config.frames_dir is None
    desired_default = (
        DEFAULT_OUTPUT_NAME
        if config.normalized_output_format == "mp4"
        else DEFAULT_GIF_OUTPUT_NAME
    )
    desired_output = Path(config.output or desired_default).expanduser()
    final_output_path = resolve_output_path(config)

    try:
        try:
            current_stars, stargazers = fetch_repo_and_stargazers(
                session, config)
        except GitHubAPIError as exc:
            print(f"Warning: {exc}. Falling back to synthetic data.")
            current_stars, stargazers = _fallback_entries(config)

        stargazers = _filter_stargazers_by_date(
            stargazers, config.start_at_utc, config.end_at_utc
        )
        entries = build_entries(stargazers, current_stars, config)
        num_entries = len(entries) or 1
        start_stars = 0
        end_stars = _final_star_count(current_stars)

        width = config.width
        viewport_height = config.viewport_height
        entry_height = config.entry_height
        fps = config.fps
        duration_seconds = max(0.1, float(config.duration_seconds))
        easing_name = config.easing.lower()

        card_left = CARD_MARGIN_X
        card_right = width - CARD_MARGIN_X
        inner_left = card_left + CARD_PADDING_X
        inner_right = card_right - CARD_PADDING_X
        header_title_y = CARD_TOP + CARD_PADDING_Y
        button_top = header_title_y - 6
        button_rect = [inner_right - BUTTON_WIDTH, button_top,
                       inner_right, button_top + BUTTON_HEIGHT]
        divider_y = button_rect[3] + 22
        rows_start_y = divider_y + 18
        content_height = rows_start_y - CARD_TOP + \
            num_entries * entry_height + CARD_PADDING_Y
        card_bottom = CARD_TOP + content_height
        canvas_height = int(card_bottom + 80)
        header_section_height = int(rows_start_y)

        layout = {
            "card_left": card_left,
            "card_right": card_right,
            "card_top": CARD_TOP,
            "card_bottom": card_bottom,
            "inner_left": inner_left,
            "inner_right": inner_right,
            "header_title_y": header_title_y,
            "button_rect": button_rect,
            "button_radius": BUTTON_RADIUS,
            "count_radius": COUNT_RADIUS,
            "divider_y": divider_y,
            "rows_start_y": rows_start_y,
            "row_height": entry_height,
            "header_height": header_section_height,
            "canvas_height": canvas_height,
        }

        tall = vertical_gradient((width, canvas_height), BG_TOP, BG_BOTTOM)
        vignette = Image.new("RGBA", (width, canvas_height), (0, 0, 0, 0))
        vig_draw = ImageDraw.Draw(vignette)
        vig_draw.rectangle([0, 0, width, canvas_height], fill=(0, 0, 0, 110))
        vig_draw.ellipse(
            [-width * 0.4, -canvas_height * 0.6, width * 1.4, canvas_height * 1.6],
            fill=(0, 0, 0, 30),
        )
        tall = Image.alpha_composite(tall, vignette)

        shadow = Image.new("RGBA", (width, canvas_height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_box = [
            layout["card_left"] + 12,
            layout["card_top"] + 18,
            layout["card_right"] + 12,
            layout["card_bottom"] + 18,
        ]
        try:
            shadow_draw.rounded_rectangle(
                shadow_box, radius=CARD_RADIUS + 6, fill=(8, 12, 24, 160))
        except Exception:
            shadow_draw.rectangle(shadow_box, fill=(8, 12, 24, 140))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        tall = Image.alpha_composite(tall, shadow)

        draw = ImageDraw.Draw(tall)
        try:
            draw.rounded_rectangle(
                [layout["card_left"], layout["card_top"],
                    layout["card_right"], layout["card_bottom"]],
                radius=CARD_RADIUS,
                fill=CARD_BG,
                outline=CARD_BORDER,
                width=1,
            )
        except Exception:
            draw.rectangle(
                [layout["card_left"], layout["card_top"],
                    layout["card_right"], layout["card_bottom"]],
                fill=CARD_BG,
                outline=CARD_BORDER,
                width=1,
            )

        draw.line((inner_left, divider_y, inner_right, divider_y),
                  fill=DIVIDER_COLOR, width=1)

        try:
            font_title_link = ImageFont.truetype("DejaVuSans.ttf", 31)
            font_title_repo = ImageFont.truetype("DejaVuSans-Bold.ttf", 31)
            font_button_label = ImageFont.truetype("DejaVuSans.ttf", 18)
            font_button_count = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
            font_entry_name = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
            font_entry_meta = ImageFont.truetype("DejaVuSans.ttf", 17)
            font_entry_meta_bold = ImageFont.truetype(
                "DejaVuSans-Bold.ttf", 17)
            font_rank_label = ImageFont.truetype("DejaVuSans.ttf", 13)
            font_rank_value = ImageFont.truetype("DejaVuSans-Bold.ttf", 21)
            font_initials = ImageFont.truetype("DejaVuSans-Bold.ttf", 21)
        except Exception:
            font_title_link = ImageFont.load_default()
            font_title_repo = ImageFont.load_default()
            font_button_label = ImageFont.load_default()
            font_button_count = ImageFont.load_default()
            font_entry_name = ImageFont.load_default()
            font_entry_meta = ImageFont.load_default()
            font_entry_meta_bold = ImageFont.load_default()
            font_rank_label = ImageFont.load_default()
            font_rank_value = ImageFont.load_default()
            font_initials = ImageFont.load_default()

        repo_label = config.repo_label

        def render_header(draw_obj, layout_map, star_count):
            left = layout_map["inner_left"]
            title_y = layout_map["header_title_y"]
            btn_left, btn_top, btn_right, btn_bottom = layout_map["button_rect"]

            if "/" in repo_label:
                owner_text, repo_text = repo_label.split("/", 1)
            else:
                owner_text, repo_text = repo_label, ""

            draw_obj.text((left, title_y), owner_text,
                          font=font_title_link, fill=LINK_COLOR)
            if hasattr(draw_obj, "textlength"):
                owner_width = draw_obj.textlength(
                    owner_text, font=font_title_link)
                slash_width = draw_obj.textlength(" / ", font=font_title_link)
            else:
                owner_width = len(owner_text) * 16
                slash_width = len(" / ") * 10

            slash_x = left + owner_width
            if repo_text:
                draw_obj.text((slash_x, title_y), " / ",
                              font=font_title_link, fill=TEXT_SECONDARY)
                repo_x = slash_x + slash_width
                draw_obj.text((repo_x, title_y), repo_text,
                              font=font_title_repo, fill=TEXT_PRIMARY)

            try:
                draw_obj.rounded_rectangle(
                    [btn_left, btn_top, btn_right, btn_bottom],
                    radius=layout_map["button_radius"],
                    fill=BUTTON_BG,
                    outline=BUTTON_BORDER,
                    width=2,
                )
            except Exception:
                draw_obj.rectangle(
                    [btn_left, btn_top, btn_right, btn_bottom],
                    fill=BUTTON_BG,
                    outline=BUTTON_BORDER,
                    width=2,
                )

            star_center = (btn_left + 22, btn_top + (btn_bottom - btn_top) / 2)
            draw_star_shape(draw_obj, star_center, 9, fill=STAR_ICON_COLOR)
            star_label_x = btn_left + 38
            draw_obj.text((star_label_x, btn_top + 12), "Star",
                          font=font_button_label, fill=TEXT_PRIMARY)

            count_text = f"{star_count:,}"
            try:
                count_bbox = draw_obj.textbbox(
                    (0, 0), count_text, font=font_button_count)
                count_w = count_bbox[2] - count_bbox[0]
                count_h = count_bbox[3] - count_bbox[1]
            except Exception:
                count_w = len(count_text) * 12
                count_h = 20
            count_x = btn_right - 14 - count_w
            count_y = btn_top + (BUTTON_HEIGHT - count_h) / 2
            divider_x = count_x - 14
            draw_obj.line((divider_x, btn_top + 10, divider_x,
                          btn_bottom - 10), fill=BUTTON_BORDER, width=1)
            draw_obj.text((count_x, count_y), count_text,
                          font=font_button_count, fill=TEXT_PRIMARY)

        avatar_cache = prefetch_avatars(
            [entry.get("avatar_url") for entry in entries], config)
        for idx, entry in enumerate(entries):
            row_top = rows_start_y + idx * entry_height
            row_bottom = row_top + entry_height
            if idx < num_entries - 1:
                draw.line((inner_left, row_bottom, inner_right,
                          row_bottom), fill=DIVIDER_COLOR, width=1)

            avatar_x = inner_left
            avatar_y = row_top + (entry_height - AVATAR_DIAMETER) // 2
            avatar_container = Image.new(
                "RGBA", (AVATAR_DIAMETER, AVATAR_DIAMETER), (0, 0, 0, 0))
            full_mask = Image.new("L", (AVATAR_DIAMETER, AVATAR_DIAMETER), 0)
            mask_draw = ImageDraw.Draw(full_mask)
            mask_draw.ellipse(
                [0, 0, AVATAR_DIAMETER, AVATAR_DIAMETER], fill=255)

            avatar_url = entry.get("avatar_url")
            avatar_img = avatar_cache.get(avatar_url) if avatar_url else None
            if avatar_img:
                resized = avatar_img.resize((AVATAR_DIAMETER, AVATAR_DIAMETER))
                avatar_container.paste(resized, (0, 0), full_mask)
            else:
                placeholder = Image.new(
                    "RGBA", (AVATAR_DIAMETER, AVATAR_DIAMETER), AVATAR_PLACEHOLDER)
                avatar_container.paste(placeholder, (0, 0), full_mask)
                initials = (entry["login"][:1] or "?").upper()
                initials_draw = ImageDraw.Draw(avatar_container)
                try:
                    init_bbox = initials_draw.textbbox(
                        (0, 0), initials, font=font_initials)
                    init_w = init_bbox[2] - init_bbox[0]
                    init_h = init_bbox[3] - init_bbox[1]
                except Exception:
                    init_w = len(initials) * 10
                    init_h = 16
                initials_draw.text(
                    (AVATAR_DIAMETER / 2 - init_w / 2,
                     AVATAR_DIAMETER / 2 - init_h / 2),
                    initials,
                    font=font_initials,
                    fill=TEXT_PRIMARY,
                )
            tall.paste(avatar_container, (avatar_x,
                       avatar_y), avatar_container)

            name_x = avatar_x + AVATAR_DIAMETER + 18
            name_y = row_top + 14
            draw.text((name_x, name_y),
                      entry["login"], font=font_entry_name, fill=TEXT_PRIMARY)

            subtitle_segments = [
                ("starred ", font_entry_meta, TEXT_SECONDARY),
                (config.repo, font_entry_meta_bold, LINK_COLOR),
            ]
            if entry["date"]:
                subtitle_segments.append(
                    (f" on {entry['date']}", font_entry_meta, TEXT_SECONDARY))
            draw_text_chain(draw, (name_x, name_y + 32), subtitle_segments)

            rank_label = "Star"
            rank_text = f"#{entry['rank']:,}"
            try:
                label_bbox = draw.textbbox(
                    (0, 0), rank_label, font=font_rank_label)
                label_w = label_bbox[2] - label_bbox[0]
            except Exception:
                label_w = len(rank_label) * 8
            label_x = inner_right - label_w
            label_y = row_top + 8
            draw.text((label_x, label_y), rank_label,
                      font=font_rank_label, fill=TEXT_SECONDARY)

            try:
                rank_bbox = draw.textbbox(
                    (0, 0), rank_text, font=font_rank_value)
                rank_w = rank_bbox[2] - rank_bbox[0]
            except Exception:
                rank_w = len(rank_text) * 12
            rank_x = inner_right - rank_w
            rank_y = label_y + 24
            draw.text((rank_x, rank_y), rank_text,
                      font=font_rank_value, fill=TEXT_PRIMARY)

        header_base = tall.crop((0, 0, width, layout["header_height"]))

        def build_header_layer(star_count):
            layer = header_base.copy()
            layer_draw = ImageDraw.Draw(layer)
            render_header(layer_draw, layout, star_count)
            return layer

        start_y = max(0, layout["canvas_height"] - viewport_height)
        end_y = 0
        frame_count = max(1, int(round(fps * duration_seconds)))

        use_progress = bool(config.show_progress and tqdm and frame_count > 1)
        iterator = (
            tqdm(
                range(frame_count),
                total=frame_count,
                desc="Rendering frames",
                unit="frame",
                leave=False,
            )
            if use_progress
            else range(frame_count)
        )

        try:
            for frame_idx in iterator:
                progress = frame_idx / \
                    (frame_count - 1) if frame_count > 1 else 1.0
                eased = ease_value(easing_name, progress)
                scroll_y = int(start_y + (end_y - start_y) * eased)
                frame = tall.crop(
                    (0, scroll_y, width, scroll_y + viewport_height))
                fimg = frame.copy()
                animated_count = int(
                    round(start_stars + (end_stars - start_stars) * eased))
                header_overlay = build_header_layer(animated_count)
                overlay_height = header_overlay.height
                if overlay_height > viewport_height:
                    overlay_slice = header_overlay.crop(
                        (0, 0, width, viewport_height))
                else:
                    overlay_slice = header_overlay
                fimg.paste(overlay_slice, (0, 0))
                fname = os.path.join(frames_dir, f"frame_{frame_idx:04d}.png")
                fimg.convert("RGB").save(fname)
                frame_files.append(fname)
        finally:
            if use_progress and hasattr(iterator, "close"):
                iterator.close()

        print("Building animation with", len(frame_files), "frames...")
        clip = ImageSequenceClip(frame_files, fps=fps)
        suffix = final_output_path.suffix.lower()
        if suffix == ".gif":
            clip.write_gif(str(final_output_path), fps=fps, loop=True)
        else:
            clip.write_videofile(str(final_output_path), codec="libx264")
        clip.close()
        if final_output_path != desired_output:
            requested = config.output or desired_default
            print(
                f"Wrote {final_output_path} (resolved from requested '{requested}')")
        else:
            print("Wrote", final_output_path)
        return str(final_output_path)
    finally:
        session.close()
        if config.cleanup_frames:
            for path in frame_files:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
            if created_temp_dir:
                shutil.rmtree(frames_dir, ignore_errors=True)
            else:
                try:
                    os.rmdir(frames_dir)
                except OSError:
                    pass
