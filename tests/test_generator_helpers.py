import os

import pytest

from star_growth import generator
from star_growth.config import StarsAnimationConfig


@pytest.fixture
def config_factory():
    def _factory(**overrides):
        config = StarsAnimationConfig()
        for key, value in overrides.items():
            setattr(config, key, value)
        return config

    return _factory


def test_config_factory_defaults_show_progress(config_factory):
    config = config_factory()

    assert config.show_progress is True


def test_final_star_count_clamps_negative():
    assert generator._final_star_count(-50) == 0


def test_final_star_count_returns_positive():
    assert generator._final_star_count(120) == 120


def test_resolve_output_path_adds_extension(tmp_path, config_factory):
    config = config_factory(output=str(tmp_path / "video_output"))

    resolved = generator.resolve_output_path(config)

    assert resolved == tmp_path / "video_output.mp4"
    assert resolved.suffix == ".mp4"


def test_resolve_output_path_directory_hint(tmp_path, config_factory):
    target_dir = tmp_path / "exports" / "nested"
    config = config_factory(output=str(target_dir) + os.sep)

    resolved = generator.resolve_output_path(config)

    assert resolved == target_dir / generator.DEFAULT_OUTPUT_NAME
    assert resolved.parent.exists()


def test_resolve_output_path_collision(tmp_path, config_factory):
    desired = tmp_path / "clip.mp4"
    desired.parent.mkdir(parents=True, exist_ok=True)
    desired.touch()

    config = config_factory(output=str(desired))

    resolved = generator.resolve_output_path(config)

    assert resolved != desired
    assert resolved.name == "clip (1).mp4"
    assert not resolved.exists()


def test_unique_output_path_handles_multiple_suffixes(tmp_path):
    base = tmp_path / "archive.tar.gz"
    base.touch()
    (tmp_path / "archive (1).tar.gz").touch()

    candidate = generator._unique_output_path(base)

    assert candidate.name == "archive (2).tar.gz"


def test_prefetch_avatars_deduplicates(monkeypatch, config_factory):
    calls = []

    def fake_download(url, timeout):
        calls.append((url, timeout))
        return f"image-{url}"

    monkeypatch.setattr(generator, "_download_avatar", fake_download)

    urls = [
        "https://avatars.com/a.png",
        "https://avatars.com/b.png",
        "https://avatars.com/a.png",
        None,
    ]
    config = config_factory(avatar_workers=4)

    cache = generator.prefetch_avatars(urls, config)

    assert cache["https://avatars.com/a.png"] == "image-https://avatars.com/a.png"
    assert cache["https://avatars.com/b.png"] == "image-https://avatars.com/b.png"
    assert None not in cache
    assert [call[0] for call in calls] == [
        "https://avatars.com/a.png",
        "https://avatars.com/b.png",
    ]


def test_prefetch_avatars_handles_empty(monkeypatch, config_factory):
    monkeypatch.setattr(generator, "_download_avatar",
                        lambda url, timeout: "x")

    cache = generator.prefetch_avatars([], config_factory())

    assert cache == {}
