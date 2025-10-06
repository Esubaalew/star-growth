from __future__ import annotations

import time
from typing import Dict, List, Tuple

import requests

from .config import StarsAnimationConfig

_RATE_LIMIT_STATUS = 403
_TRANSIENT_STATUSES = {500, 502, 503, 504}


class GitHubAPIError(RuntimeError):
    pass


def _augment_headers(config: StarsAnimationConfig, headers: Dict[str, str] | None) -> Dict[str, str]:
    merged = {"User-Agent": "star-growth/1.0"}
    if headers:
        merged.update(headers)
    token = config.auth_token
    if token:
        merged.setdefault("Authorization", f"Bearer {token}")
    return merged


def _request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    config: StarsAnimationConfig,
    *,
    headers: Dict[str, str] | None = None,
    params: Dict[str, str] | None = None,
) -> requests.Response:
    attempt = 0
    headers = _augment_headers(config, headers)

    while True:
        attempt += 1
        try:
            response = session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=config.request_timeout,
            )
        except requests.RequestException as exc:
            if attempt >= config.max_retries:
                raise GitHubAPIError(f"GitHub request failed: {exc}") from exc
            sleep_seconds = config.retry_backoff * attempt
            print(f"Request error {exc}; retrying in {sleep_seconds:.1f}s...")
            time.sleep(sleep_seconds)
            continue

        if response.status_code == _RATE_LIMIT_STATUS and response.headers.get("X-RateLimit-Remaining") == "0":
            reset_at = response.headers.get("X-RateLimit-Reset")
            now = time.time()
            wait_seconds = max(config.retry_backoff * attempt,
                               float(reset_at) - now if reset_at else 0)
            if attempt >= config.max_retries:
                raise GitHubAPIError(
                    "GitHub rate limit exceeded; supply a personal access token or retry later.")
            print(
                f"Rate limited by GitHub; waiting {wait_seconds:.1f}s before retry {attempt}/{config.max_retries}...")
            time.sleep(max(wait_seconds, 1.0))
            continue

        if response.status_code in _TRANSIENT_STATUSES and attempt < config.max_retries:
            sleep_seconds = config.retry_backoff * attempt
            print(
                f"GitHub transient error {response.status_code}; retrying in {sleep_seconds:.1f}s...")
            time.sleep(sleep_seconds)
            continue

        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub request to {url} failed with status {response.status_code}: {response.text[:200]}"
            )

        return response


def fetch_repo_and_stargazers(session: requests.Session, config: StarsAnimationConfig) -> Tuple[int, List[dict]]:
    repo_url = f"https://api.github.com/repos/{config.owner}/{config.repo}"
    repo_resp = _request_with_retry(session, "GET", repo_url, config)
    repo_json = repo_resp.json()
    current_stars = int(repo_json.get("stargazers_count", 0))

    stargazers: List[dict] = []
    sg_url = f"https://api.github.com/repos/{config.owner}/{config.repo}/stargazers"
    params = {
        "per_page": str(config.max_entries),
        "sort": "created",
        "direction": "desc",
    }
    headers = {"Accept": "application/vnd.github.v3.star+json"}
    sg_resp = _request_with_retry(
        session, "GET", sg_url, config, headers=headers, params=params)
    for item in sg_resp.json():
        if isinstance(item, dict) and "user" in item:
            user = item["user"]
            login = user.get("login")
            avatar_url = user.get("avatar_url")
            starred_at = item.get("starred_at")
        else:
            login = item.get("login")
            avatar_url = item.get("avatar_url")
            starred_at = None
        stargazers.append(
            {"login": login, "starred_at": starred_at, "avatar_url": avatar_url})

    stargazers.sort(key=lambda sg: sg.get("starred_at") or "", reverse=True)
    return current_stars, stargazers
