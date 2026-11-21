#!/usr/bin/env python3
"""Fetch public GitHub activity and repos into data/github.json.

Only public endpoints are read, so local runs and the daily Action produce the
same numbers and private repository names can never reach the README. If GitHub
returns anything unexpected the script exits non-zero and the old data stays.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "github.json"
USER_AGENT = "profile-readme-refresh"


def get(url, api=False):
    headers = {"User-Agent": USER_AGENT}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def attr(tag, name):
    match = re.search(rf'\b{name}="([^"]*)"', tag)
    return match.group(1) if match else None


def fetch_days(username):
    page = get(f"https://github.com/users/{username}/contributions")
    tips = {
        target: unescape(re.sub(r"<[^>]+>", "", text)).strip()
        for target, text in re.findall(
            r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>(.*?)</tool-tip>', page, re.S
        )
    }
    days = []
    for tag in re.findall(r"<td\b[^>]*\bdata-date=[^>]*>", page):
        tip = tips.get(attr(tag, "id"), "")
        if tip.lower().startswith("no contributions"):
            count = 0
        else:
            match = re.match(r"([\d,]+) contributions?\b", tip)
            if not match:
                raise ValueError(f"unreadable contribution tooltip: {tip!r}")
            count = int(match.group(1).replace(",", ""))
        days.append(
            {"date": attr(tag, "data-date"), "count": count, "level": int(attr(tag, "data-level") or 0)}
        )
    if len(days) < 300:
        raise ValueError(f"expected a full year of days, found {len(days)}")
    return sorted(days, key=lambda day: day["date"])


def main_language(repo):
    """GitHub sometimes leaves `language` empty even when the byte breakdown exists."""
    languages = json.loads(get(repo["languages_url"], api=True))
    return max(languages, key=languages.get) if languages else ""


def fetch_repos(username):
    repos, page = [], 1
    while True:
        batch = json.loads(
            get(
                f"https://api.github.com/users/{username}/repos"
                f"?type=owner&sort=pushed&per_page=100&page={page}",
                api=True,
            )
        )
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    return [
        {
            "name": repo["name"],
            "description": repo.get("description") or "",
            "language": repo.get("language") or main_language(repo),
            "stars": repo.get("stargazers_count", 0),
            "fork": repo.get("fork", False),
            "archived": repo.get("archived", False),
            "pushed_at": repo.get("pushed_at") or "",
            "url": repo["html_url"],
        }
        for repo in repos
        if not repo.get("private")
    ]


def streaks(days):
    longest = run = 0
    for day in days:
        run = run + 1 if day["count"] else 0
        longest = max(longest, run)
    index = len(days) - 1
    if days[index]["count"] == 0:  # today may simply not have happened yet
        index -= 1
    current = 0
    while index >= 0 and days[index]["count"]:
        current += 1
        index -= 1
    return current, longest


def monthly(days):
    totals = {}
    for day in days:
        totals[day["date"][:7]] = totals.get(day["date"][:7], 0) + day["count"]
    return [{"month": month, "total": total} for month, total in sorted(totals.items())]


def main():
    config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    username = config["username"]
    days = fetch_days(username)
    user = json.loads(get(f"https://api.github.com/users/{username}", api=True))
    current, longest = streaks(days)
    best = max(days, key=lambda day: day["count"])
    data = {
        "username": username,
        "updated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "followers": user.get("followers", 0),
        "total_contributions": sum(day["count"] for day in days),
        "active_days": sum(1 for day in days if day["count"]),
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly(days),
        "repos": fetch_repos(username),
        "days": days,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(
        f"{data['total_contributions']} contributions, {len(data['repos'])} repos, "
        f"streak {current}, longest {longest}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"fetch failed, keeping previous data: {error}", file=sys.stderr)
        sys.exit(1)
