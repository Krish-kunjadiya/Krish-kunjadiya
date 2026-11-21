#!/usr/bin/env python3
"""Render every profile card to cards/*.svg and rebuild README.md.

Inputs: profile.json (your words), data/github.json (live numbers) and
data/portrait.json (ASCII avatar). GitHub shows these SVGs through <img>, so they
use only inline CSS, SMIL and embedded fonts.
"""
import base64
import datetime as dt
import json
import re
from html import escape
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
FONTS = ROOT / "fonts"

ACCENT = "#FA4400"
PAPER = "#f3f3f1"
PAPER_DEEP = "#e2e2de"
INK = "#111111"
INK_SOFT = "#3a3a3c"
MUTED = "#66666b"
RULE = "#dcdcd7"
PARTIAL = "#c9c9c4"
YELLOW = "#ffc81a"

W = 880
GAP = 12
THIRD_W = W / 3 - 8

SERIF = "'Instrument Serif', Georgia, serif"
SANS = "Geist, system-ui, -apple-system, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

FONT_FILES = {
    "serif": ("Instrument Serif", "normal", 400, "serif-400.woff"),
    "serif-i": ("Instrument Serif", "italic", 400, "serif-italic.woff"),
    "sans": ("Geist", "normal", 400, "geist-400.woff"),
    "sans-b": ("Geist", "normal", 600, "geist-600.woff"),
    "mono": ("Geist Mono", "normal", 400, "geistmono-400.woff"),
}

CSS = """
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes pop{0%{opacity:0;transform:scale(.3)}70%{opacity:1;transform:scale(1.12)}100%{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes nudge{0%,100%{transform:none}50%{transform:translateX(4px)}}
.r{animation:rise .75s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
.f{animation:fade .8s ease-out both}
.g{animation:grow .75s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box;transform-origin:bottom}
.p{animation:pop .38s ease-out both;transform-box:fill-box;transform-origin:center}
.live{animation:pulse 1.6s ease-in-out infinite}
.n{animation:nudge 1.8s ease-in-out infinite;transform-box:fill-box}
@media (prefers-reduced-motion:reduce){.r,.f,.g,.p,.live,.n{animation:none!important}}
"""

_metrics = {}


def clean(text):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text or "").strip()


def text_width(text, font, size):
    if font not in _metrics:
        loaded = TTFont(FONTS / FONT_FILES[font][3])
        _metrics[font] = (loaded.getBestCmap(), loaded["hmtx"], loaded["head"].unitsPerEm)
    cmap, hmtx, upem = _metrics[font]
    units = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upem * 0.6 for c in text)
    return units * size / upem


def wrap(text, font, size, width, max_lines):
    lines, line = [], ""
    words = clean(text).split()
    for index, word in enumerate(words):
        candidate = f"{line} {word}".strip()
        if text_width(candidate, font, size) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
        if len(lines) == max_lines:
            line = ""
            words = words[index:]
            break
    else:
        words = []
    if line:
        lines.append(line)
    if words or len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and text_width(last + "...", font, size) > width:
            last = last[:-1].rstrip()
        lines[-1] = last.rstrip(",.;:") + "..."
    return lines


def mix(a, b, amount):
    channels = []
    for i in (1, 3, 5):
        start, end = int(a[i : i + 2], 16), int(b[i : i + 2], 16)
        channels.append(round(start + (end - start) * amount))
    return "#" + "".join(f"{c:02x}" for c in channels)


HEAT = [PAPER_DEEP, mix(PAPER, ACCENT, 0.26), mix(PAPER, ACCENT, 0.5), mix(PAPER, ACCENT, 0.75), ACCENT]


def delay(seconds):
    return f'style="animation-delay:{seconds:.2f}s"'


def plural(count, word):
    return word if count == 1 else f"{word}s"


def pretty_name(name):
    return re.sub(r"[-_]+", " ", name).strip()


def write_svg(name, width, height, body, fonts, label, left=0, right=0, bottom=GAP):
    faces = []
    for key in fonts:
        family, style, weight, filename = FONT_FILES[key]
        encoded = base64.b64encode((FONTS / filename).read_bytes()).decode()
        faces.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"src:url(data:font/woff;base64,{encoded}) format('woff')}}"
        )
    if left:
        body = f'<g transform="translate({left:.3f} 0)">{body}</g>'
    full_w, full_h = width + left + right, height + bottom
    safe = escape(label, quote=True)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{full_w:.3f}" height="{full_h}" '
        f'viewBox="0 0 {full_w:.3f} {full_h}" role="img" aria-label="{safe}"><title>{safe}</title>'
        f'<style>{"".join(faces)}{CSS}</style>{body}</svg>\n'
    )
    CARDS.mkdir(exist_ok=True)
    (CARDS / name).write_text(svg, encoding="utf-8", newline="\n")


def hero(config, portrait):
    height = 420
    box = 300
    cell = box / portrait["cols"]
    line = cell * 1.875
    size = cell / 0.6
    px, py = 540, (height - portrait["rows"] * line) / 2
    layers = []
    for layer, color, stroke in (("ink", INK, ""), ("accent", ACCENT, f' stroke="{ACCENT}" stroke-width=".32"')):
        for index, row in enumerate(portrait[layer]):
            if not row.strip():
                continue
            layers.append(
                f'<text class="f" style="animation-delay:{0.25 + index * 0.02:.2f}s;animation-duration:.35s" '
                f'xml:space="preserve" x="{px}" y="{py + (index + 0.8) * line:.2f}" fill="{color}"{stroke} '
                f'font-size="{size:.3f}" textLength="{len(row) * cell:.2f}" lengthAdjust="spacing">{escape(row)}</text>'
            )
    tagline = wrap(config["tagline"], "sans", 18, 450, 2)
    tagline_svg = "".join(
        f'<text x="48" y="{338 + i * 27}" font-family="{SANS}" font-size="18" fill="{INK_SOFT}">{escape(t)}</text>'
        for i, t in enumerate(tagline)
    )
    handle = f"github.com/{config['username']}"
    arrow_x = 48 + text_width(handle, "mono", 13) + 8
    body = f"""
<defs><linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="600" y2="0">
<stop offset="0" stop-color="{INK}"/><stop offset=".42" stop-color="{INK}"/><stop offset=".5" stop-color="{ACCENT}"/>
<stop offset=".58" stop-color="{INK}"/><stop offset="1" stop-color="{INK}"/>
<animateTransform attributeName="gradientTransform" type="translate" values="-600 0;600 0;600 0" keyTimes="0;.45;1" dur="7s" begin="1.6s" repeatCount="indefinite"/>
</linearGradient></defs>
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<g class="f"><rect class="live" x="48" y="49" width="8" height="8" rx="2" fill="{ACCENT}"/>
<text x="66" y="57" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">{escape(config["eyebrow"])}</text></g>
<text class="r" {delay(.15)} x="44" y="190" font-family="{SERIF}" font-size="116" letter-spacing="-2.5" fill="{INK}">{escape(config["first_name"])}</text>
<text class="r" {delay(.3)} x="44" y="290" font-family="{SERIF}" font-style="italic" font-size="116" letter-spacing="-2.5" fill="url(#shine)">{escape(config["last_name"])}</text>
<g class="r" {delay(.55)}>{tagline_svg}</g>
<g class="f" {delay(.8)}><text x="48" y="400" font-family="{MONO}" font-size="13" fill="{INK}">{escape(handle)}</text>
<text x="{arrow_x:.1f}" y="400" font-family="{MONO}" font-size="13" fill="{ACCENT}">&#8599;</text></g>
<g font-family="{MONO}">{"".join(layers)}</g>
"""
    label = f'{config["first_name"]} {config["last_name"]}. {config["tagline"]}'
    write_svg("hero.svg", W, height, body, ["serif", "serif-i", "sans", "mono"], label)
    return label


def heatmap(data):
    days = data["days"]
    first = dt.date.fromisoformat(days[0]["date"])
    lead = (first.weekday() + 1) % 7
    cell, step, gx, gy = 12, 15, 44, 96
    cells, months, seen = [], [], set()
    for index, day in enumerate(days):
        col, row = divmod(index + lead, 7)
        date = dt.date.fromisoformat(day["date"])
        key = (date.year, date.month)
        if key not in seen:
            seen.add(key)
            months.append((col if row == 0 else col + 1, date.strftime("%b")))
        count = day["count"]
        cells.append(
            f'<rect class="p" style="animation-delay:{.7 + col * .025 + row * .02:.2f}s" x="{gx + col * step}" '
            f'y="{gy + row * step}" width="{cell}" height="{cell}" rx="3" fill="{HEAT[day["level"]]}">'
            f'<title>{day["date"]}: {count} {plural(count, "contribution")}</title></rect>'
        )
    columns = (len(days) + lead + 6) // 7
    right = gx + columns * step - 3
    labels = "".join(
        f'<text x="{gx + col * step}" y="{gy + 7 * step + 16}" font-family="{MONO}" font-size="11" fill="{MUTED}">{name}</text>'
        for i, (col, name) in enumerate(months)
        if (i + 1 == len(months) or months[i + 1][0] - col >= 3) and col < columns - 1
    )
    legend_y = 50
    legend_x = right - len(HEAT) * 14 - 28
    legend = "".join(
        f'<rect x="{legend_x + i * 14}" y="{legend_y}" width="11" height="11" rx="2.5" fill="{color}"/>'
        for i, color in enumerate(HEAT)
    )
    updated = dt.datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
    stamp = f"UPDATED {updated.day} {updated.strftime('%b %Y').upper()}"
    height = gy + 7 * step + 44
    body = f"""
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<text class="r" {delay(.5)} x="42" y="62" font-family="{SERIF}" font-size="34" fill="{INK}">Every day, <tspan font-style="italic" fill="{ACCENT}">in orange</tspan></text>
<g class="f" {delay(.6)}>
<text x="{legend_x - 8}" y="{legend_y + 10}" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">less</text>{legend}
<text x="{legend_x + len(HEAT) * 14 + 2}" y="{legend_y + 10}" font-family="{MONO}" font-size="11" fill="{MUTED}">more</text>
<text x="{legend_x - 52}" y="{legend_y + 10}" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="1" fill="{MUTED}">{stamp}</text>
</g>
{"".join(cells)}
<g class="f" {delay(1.8)}>{labels}</g>
"""
    write_svg("heatmap.svg", W, height, body, ["serif", "serif-i", "mono"],
              f'Contribution graph: {data["total_contributions"]:,} contributions in the last year')


def activity(data):
    height = 340
    months = data["monthly"][-12:]
    best = max(months, key=lambda m: m["total"])
    top = max(best["total"], 1)
    x0, x1, base, max_h, gap = 40, 600, 292, 140, 10
    bar = (x1 - x0 - gap * (len(months) - 1)) / len(months)
    bars = []
    for index, month in enumerate(months):
        partial = index == len(months) - 1
        bar_h = max(4, round(month["total"] / top * max_h))
        x = x0 + index * (bar + gap)
        fill = ACCENT if month is best and month["total"] else PARTIAL if partial else INK
        name = dt.date.fromisoformat(month["month"] + "-01").strftime("%b")
        at = 1.5 + index * .06
        bars.append(
            f'<rect class="g" {delay(at)} x="{x:.1f}" y="{base - bar_h}" width="{bar:.1f}" height="{bar_h}" rx="4" fill="{fill}">'
            f'<title>{name}: {month["total"]:,}</title></rect>'
            f'<text class="f" {delay(at)} x="{x + bar / 2:.1f}" y="{base + 22}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{MUTED}">{name}</text>'
        )
        if month is best and month["total"]:
            bars.append(
                f'<text class="p" {delay(2.4)} x="{x + bar / 2:.1f}" y="{base - bar_h - 10}" text-anchor="middle" '
                f'font-family="{MONO}" font-size="11" fill="{INK}">{month["total"]:,}</text>'
            )
    current, longest = data["current_streak"], data["longest_streak"]
    if current:
        streak = current
        note = "current streak, and the longest" if current >= longest else f"current streak, longest {longest}"
    else:
        streak, note = longest, "longest streak this year"
    stats = [
        (f'{streak} <tspan font-style="italic">{plural(streak, "day")}</tspan>', note),
        (f'{data["active_days"]}<tspan fill="#8e8e93"> / {len(data["days"])}</tspan>', "days with a contribution"),
        (f'{data["best_day"]["count"]}', "on the busiest day"),
    ]
    side = []
    for index, (big, small) in enumerate(stats):
        y = 104 + index * 92
        side.append(
            f'<g class="r" {delay(1.9 + index * .14)}><text x="650" y="{y}" font-family="{SERIF}" font-size="40" fill="{INK}">{big}</text>'
            f'<text x="650" y="{y + 24}" font-family="{SANS}" font-size="13" fill="{MUTED}">{small}</text></g>'
        )
        if index < 2:
            side.append(f'<rect class="f" {delay(1.9)} x="650" y="{y + 44}" width="190" height="1" fill="{RULE}"/>')
    total = data["total_contributions"]
    body = f"""
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<text class="f" {delay(1.2)} x="40" y="58" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">THE LAST 12 MONTHS ON GITHUB</text>
<text class="r" {delay(1.3)} x="38" y="114" font-family="{SERIF}" font-size="52" fill="{INK}">{total:,} <tspan font-style="italic">{plural(total, "contribution")}</tspan></text>
{"".join(bars)}{"".join(side)}
"""
    write_svg("activity.svg", W, height, body, ["serif", "serif-i", "sans", "mono"],
              f"{total:,} contributions in the last 12 months, best streak {max(current, longest)} days")


def tile(position, name, label, bg, fg, number, word, blurb, at):
    height = 210
    lines = wrap(blurb, "sans", 14, THIRD_W - 48, 3)
    blurb_svg = "".join(
        f'<text class="r" {delay(at + .4 + i * .08)} x="24" y="{150 + i * 20}" font-family="{SANS}" font-size="14" fill="{fg}">{escape(t)}</text>'
        for i, t in enumerate(lines)
    )
    edge = ' stroke="#30363d"' if bg == INK else ""  # keeps the black tile visible on GitHub's dark theme
    body = f"""
<rect x=".5" y=".5" width="{THIRD_W - 1}" height="{height - 1}" rx="14" fill="{bg}"{edge}/>
<text class="f" {delay(at)} x="24" y="38" font-family="{MONO}" font-size="12" letter-spacing="1.2" fill="{fg}">{label}</text>
<text class="n" style="animation-delay:{at + 1:.2f}s" x="{THIRD_W - 36:.1f}" y="38" font-family="{MONO}" font-size="14" fill="{fg}">&#8594;</text>
<text class="r" {delay(at + .2)} x="22" y="112" font-family="{SERIF}" font-size="44" fill="{fg}">{number} <tspan font-style="italic">{escape(word)}</tspan></text>
{blurb_svg}
"""
    alt = f"{label}: {number} {word}. {blurb}"
    write_svg(f"{name}.svg", THIRD_W, height, body, ["serif", "serif-i", "sans", "mono"], alt,
              left=4 * position, right=8 - 4 * position)
    return alt


def repo_card(position, repo, description):
    height = 176
    at = 3.4 + position * .12
    title = wrap(pretty_name(repo["name"]), "sans-b", 18, THIRD_W - 64, 2)
    title_svg = "".join(
        f'<text x="40" y="{39 + i * 23}" font-family="{SANS}" font-weight="600" font-size="18" fill="{INK}">{escape(t)}</text>'
        for i, t in enumerate(title)
    )
    first_y = 39 + (len(title) - 1) * 23 + 33
    lines = wrap(description, "sans", 14, THIRD_W - 48, 3 if len(title) == 1 else 2)
    desc_svg = "".join(
        f'<text x="24" y="{first_y + i * 21}" font-family="{SANS}" font-size="14" fill="{INK_SOFT}">{escape(t)}</text>'
        for i, t in enumerate(lines)
    )
    meta = "  ·  ".join(part for part in [repo["language"], f'★ {repo["stars"]}' if repo["stars"] else ""] if part)
    color = (ACCENT, INK, YELLOW)[position]
    body = f"""
<rect width="{THIRD_W}" height="{height}" rx="14" fill="{PAPER}"/>
<g class="r" {delay(at)}><rect x="24" y="30" width="8" height="8" rx="2" fill="{color}"/>{title_svg}{desc_svg}
<text x="24" y="{height - 22}" font-family="{MONO}" font-size="12" fill="{MUTED}" xml:space="preserve">{escape(meta)}</text></g>
"""
    alt = f'{pretty_name(repo["name"])}: {description}'
    write_svg(f"repo-{position + 1}.svg", THIRD_W, height, body, ["sans", "sans-b", "mono"], alt,
              left=4 * position, right=8 - 4 * position)
    return alt


def section_title(theme):
    color = "#e6edf3" if theme == "dark" else INK
    body = (
        f'<text class="r" {delay(3.2)} x="2" y="46" font-family="{SERIF}" font-size="34" fill="{color}">'
        f'What I\'m <tspan font-style="italic">coding</tspan></text>'
    )
    write_svg(f"title-coding-{theme}.svg", W, 64, body, ["serif", "serif-i"], "What I'm coding", bottom=0)


def own_repos(config, data):
    hidden = set(config["hidden_repos"]) | {config["username"]}
    return [r for r in data["repos"] if not r["fork"] and not r["archived"] and r["name"] not in hidden]


def pick_repos(config, repos):
    by_name = {r["name"]: r for r in repos}
    picked = [by_name[n] for n in config["featured_repos"] if n in by_name]
    for repo in sorted(repos, key=lambda r: r["pushed_at"], reverse=True):
        if len(picked) == 3:
            break
        if repo not in picked:
            picked.append(repo)
    return picked


def join_words(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def tiles(config, data, repos):
    base = f'https://github.com/{config["username"]}'
    latest = max(repos, key=lambda r: r["pushed_at"])
    alts = [tile(0, "build", "BUILD", ACCENT, INK, len(repos), plural(len(repos), "project"),
                 f'Public repos, most recently {pretty_name(latest["name"])}.', 2.5)]
    stars = sum(r["stars"] for r in repos)
    top = max(repos, key=lambda r: r["stars"])
    followers = data["followers"]
    star_note = f'Led by {pretty_name(top["name"])}. ' if top["stars"] else ""
    alts.append(tile(1, "community", "COMMUNITY", INK, "#ffffff", stars, plural(stars, "star"),
                     f'{star_note}{followers} {plural(followers, "follower")} on GitHub.', 2.7))
    counts = {}
    for repo in repos:
        if repo["language"]:
            counts[repo["language"]] = counts.get(repo["language"], 0) + 1
    languages = sorted(counts, key=lambda l: (-counts[l], l))
    blurb = f"Mostly {languages[0]}" + (f", plus {join_words(languages[1:])}." if len(languages) > 1 else ".")
    alts.append(tile(2, "stack", "STACK", YELLOW, INK, len(languages), plural(len(languages), "language"), blurb, 2.9))
    return alts, [f"{base}?tab=repositories", f"{base}?tab=followers", f"{base}?tab=repositories&sort=stargazers"]


def image(src, alt, width="100%"):
    return f'<img src="./cards/{src}" width="{width}" alt="{escape(alt, quote=True)}" />'


def linked(url, inner):
    return f'<a href="{escape(url, quote=True)}">{inner}</a>'


def write_readme(config, data, hero_alt, tile_alts, tile_urls, picks, repo_alts):
    tile_row = "".join(
        linked(url, image(f"{name}.svg", alt, "33.333%"))
        for name, alt, url in zip(("build", "community", "stack"), tile_alts, tile_urls)
    )
    repo_row = "".join(
        linked(repo["url"], image(f"repo-{i + 1}.svg", repo_alts[i], "33.333%")) for i, repo in enumerate(picks)
    )
    links = " &nbsp;/&nbsp; ".join(linked(l["url"], escape(l["label"])) for l in config["links"])
    profile_url = f'https://github.com/{config["username"]}'
    readme = f"""<!-- Generated by scripts/render_cards.py. Edit profile.json, not this file. -->
<div align="center">
{linked(profile_url, image("hero.svg", hero_alt))}<br>
{image("heatmap.svg", "Contribution graph in orange, refreshed daily")}<br>
{image("activity.svg", f'{data["total_contributions"]:,} contributions in the last 12 months, by month')}<br>
{tile_row}<br>
<picture><source media="(prefers-color-scheme: dark)" srcset="./cards/title-coding-dark.svg" /><img src="./cards/title-coding-light.svg" width="100%" alt="What I'm coding" /></picture><br>
{repo_row}
</div>

<p align="center">
{links}
</p>
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")


def main():
    config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    data = json.loads((ROOT / "data" / "github.json").read_text(encoding="utf-8"))
    portrait = json.loads((ROOT / "data" / "portrait.json").read_text(encoding="utf-8"))
    repos = own_repos(config, data)
    hero_alt = hero(config, portrait)
    heatmap(data)
    activity(data)
    tile_alts, tile_urls = tiles(config, data, repos)
    section_title("dark")
    section_title("light")
    picks = pick_repos(config, repos)
    repo_alts = []
    for position, repo in enumerate(picks):
        description = config["repo_descriptions"].get(repo["name"]) or repo["description"]
        description = description or f'{repo["language"] or "Code"} project on GitHub.'
        repo_alts.append(repo_card(position, repo, description))
    write_readme(config, data, hero_alt, tile_alts, tile_urls, picks, repo_alts)
    print(f"rendered {len(list(CARDS.glob('*.svg')))} cards and README.md")


if __name__ == "__main__":
    main()
