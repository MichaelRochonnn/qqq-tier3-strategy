#!/usr/bin/env python3
"""Update a GitHub repository About description, homepage, and topics."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any


API_BASE = "https://api.github.com"
DEFAULT_API_VERSION = "2022-11-28"


def token_from_env() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit(
            "Missing GitHub token. Set GH_TOKEN or GITHUB_TOKEN with repo administration write access."
        )
    return token


def normalize_topic(topic: str) -> str:
    normalized = topic.strip().lower()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError(f"Invalid topic: {topic!r}")
    if len(normalized) > 35:
        raise ValueError(f"Topic is too long after normalization: {normalized!r}")
    return normalized


def parse_topics(value: str | None) -> list[str] | None:
    if value is None:
        return None
    topics = [normalize_topic(item) for item in value.split(",") if item.strip()]
    seen: set[str] = set()
    unique_topics: list[str] = []
    for topic in topics:
        if topic not in seen:
            unique_topics.append(topic)
            seen.add(topic)
    return unique_topics


def request_json(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
    api_version: str = DEFAULT_API_VERSION,
) -> dict[str, Any]:
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "qqq-tier3-strategy-about-updater",
            "X-GitHub-Api-Version": api_version,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed: HTTP {exc.code}: {detail}") from exc

    if not text:
        return {}
    return json.loads(text)


def update_repo_about(
    repo: str,
    description: str | None,
    homepage: str | None,
    topics: list[str] | None,
    token: str,
    api_version: str,
    dry_run: bool,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if description is not None:
        updates["description"] = description
    if homepage is not None:
        updates["homepage"] = homepage

    result: dict[str, Any] = {"repo": repo}

    if dry_run:
        result["dry_run"] = True
        result["repository_payload"] = updates
        result["topics_payload"] = {"names": topics} if topics is not None else None
        return result

    if updates:
        result["repository"] = request_json(
            "PATCH", f"/repos/{repo}", token, updates, api_version=api_version
        )

    if topics is not None:
        result["topics"] = request_json(
            "PUT", f"/repos/{repo}/topics", token, {"names": topics}, api_version=api_version
        )

    if not updates and topics is None:
        result["message"] = "No changes requested."

    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update GitHub repository About description, homepage, and topics."
    )
    parser.add_argument("--repo", required=True, help="Repository in owner/name form.")
    parser.add_argument("--description", help="GitHub About description.")
    parser.add_argument("--homepage", help="GitHub About website URL.")
    parser.add_argument(
        "--topics",
        help="Comma-separated repository topics. Existing topics will be replaced.",
    )
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if "/" not in args.repo:
        print("--repo must use owner/name format", file=sys.stderr)
        return 2

    try:
        topics = parse_topics(args.topics)
        token = "dry-run-token" if args.dry_run else token_from_env()
        result = update_repo_about(
            repo=args.repo,
            description=args.description,
            homepage=args.homepage,
            topics=topics,
            token=token,
            api_version=args.api_version,
            dry_run=args.dry_run,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
