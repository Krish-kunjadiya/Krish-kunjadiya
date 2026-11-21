#!/usr/bin/env python3
"""Render every profile card to cards/*.svg and rebuild README.md.

Inputs: profile.json (your words), data/github.json (live numbers) and
assets/portrait.png. GitHub shows these SVGs through <img>, so they use only
inline CSS, SMIL and embedded fonts and images.
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
PORTRAIT = ROOT / "assets" / "portrait.png"

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

FAMILY = "'Space Grotesk', system-ui, -apple-system, 'Segoe UI', sans-serif"
FONT_FILES = {weight: f"space-grotesk-{weight}.woff" for weight in (400, 600, 700)}

# Tracking taken from the portfolio's type styles.
TIGHT = -0.045
GIANT = -0.075
MIDDLE = 'text-anchor="middle"'

CSS = """
text{font-variant-numeric:tabular-nums}
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


def text_width(text, weight, size, track=0):
    if weight not in _metrics:
        loaded = TTFont(FONTS / FONT_FILES[weight])
        _metrics[weight] = (loaded.getBestCmap(), loaded["hmtx"], loaded["head"].unitsPerEm)
    cmap, hmtx, upem = _metrics[weight]
    units = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upem * 0.6 for c in text)
    return units * size / upem + len(text) * track * size


def wrap(text, weight, size, width, max_lines, track=0):
    lines, line = [], ""
    words = clean(text).split()
    for index, word in enumerate(words):
        candidate = f"{line} {word}".strip()
        if text_width(candidate, weight, size, track) <= width:
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
        while last and text_width(last + "...", weight, size, track) > width:
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


def label_text(x, y, content, fill=MUTED, attrs=""):
    return txt(x, y, escape(content), 12, 600, fill, 0.08, attrs)


def txt(x, y, content, size, weight=400, fill=INK, track=0, attrs=""):
    spacing = f' letter-spacing="{track}em"' if track else ""
    extra = f" {attrs}" if attrs else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{FAMILY}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}"{spacing}{extra}>{content}</text>'
    )


def arrow_right(x, y, color, at):
    return (
        f'<g transform="translate({x:.1f} {y})"><path class="n" style="animation-delay:{at:.2f}s" d="M0 6h12M8 2l4 4-4 4" '
        f'fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></g>'
    )


def arrow_up_right(x, y, color):
    return (
        f'<path transform="translate({x:.1f} {y})" d="M1 10 10 1M3 1h7v7" fill="none" stroke="{color}" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def star(x, y, color):
    return (
        f'<path transform="translate({x:.1f} {y})" fill="{color}" '
        'd="M6 .8l1.6 3.4 3.7.5-2.7 2.6.7 3.7L6 9.2 2.7 11l.7-3.7L.7 4.7l3.7-.5z"/>'
    )


def write_svg(name, width, height, body, weights, label, left=0, right=0, bottom=GAP, extra_css=""):
    faces = []
    for weight in weights:
        encoded = base64.b64encode((FONTS / FONT_FILES[weight]).read_bytes()).decode()
        faces.append(
            f"@font-face{{font-family:'Space Grotesk';font-style:normal;font-weight:{weight};"
            f"src:url(data:font/woff;base64,{encoded}) format('woff')}}"
        )
    if left:
        body = f'<g transform="translate({left:.3f} 0)">{body}</g>'
    full_w, full_h = width + left + right, height + bottom
    safe = escape(label, quote=True)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{full_w:.3f}" height="{full_h}" '
        f'viewBox="0 0 {full_w:.3f} {full_h}" role="img" aria-label="{safe}"><title>{safe}</title>'
        f'<style>{"".join(faces)}{CSS}{extra_css}</style>{body}</svg>\n'
    )
    CARDS.mkdir(exist_ok=True)
    (CARDS / name).write_text(svg, encoding="utf-8", newline="\n")


def hero(config):
    height = 420
    panel_x = 500
    panel_w = W - panel_x
    photo = base64.b64encode(PORTRAIT.read_bytes()).decode()
    first, last = config["first_name"], config["last_name"]
    longest = max(text_width(first, 700, 1, GIANT), text_width(last, 700, 1, GIANT))
    name_size = round(min(112, 424 / longest), 1)
    first_y = 178
    last_y = round(first_y + name_size * 0.92, 1)
    tagline = wrap(config["tagline"], 400, 18, 420, 2, -0.02)
    tagline_svg = "".join(
        txt(48, 338 + i * 25, escape(line), 18, 400, INK_SOFT, -0.02) for i, line in enumerate(tagline)
    )
    handle = re.sub(r"^https?://", "", config["website"]).rstrip("/")
    arrow_x = 48 + text_width(handle, 600, 14, -0.01) + 8
    body = f"""
<defs><linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="600" y2="0" gradientTransform="translate(-600 0)">
<stop offset="0" stop-color="{INK}"/><stop offset=".4" stop-color="{INK}"/><stop offset=".5" stop-color="{mix(INK, ACCENT, 0.3)}"/>
<stop offset=".6" stop-color="{INK}"/><stop offset="1" stop-color="{INK}"/>
<animateTransform attributeName="gradientTransform" type="translate" values="-600 0;600 0" keyTimes="0;1" calcMode="spline" keySplines=".45 0 .55 1" dur="2.2s" begin="1s" fill="freeze"/>
</linearGradient></defs>
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<g class="f"><rect class="live" x="48" y="47" width="9" height="9" rx="2" fill="{ACCENT}"/>
{txt(66, 58, escape(config["eyebrow"]), 20, 600, INK_SOFT, TIGHT)}</g>
<g class="r" {delay(.15)}>{txt(44, first_y, escape(first), name_size, 700, "url(#shine)", GIANT)}</g>
<g class="r" {delay(.3)}>{txt(44, last_y, escape(last), name_size, 700, "url(#shine)", GIANT)}</g>
<g class="r" {delay(.55)}>{tagline_svg}</g>
<g class="f" {delay(.8)}>{txt(48, 400, escape(handle), 14, 600, INK, -0.01)}{arrow_up_right(arrow_x, 389, ACCENT)}</g>
<clipPath id="panel"><path d="M{panel_x} 0H{W - 14}a14 14 0 0 1 14 14V{height - 14}a14 14 0 0 1-14 14H{panel_x}Z"/></clipPath>
<g clip-path="url(#panel)"><rect x="{panel_x}" width="{panel_w}" height="{height}" fill="{ACCENT}"/>
<image class="f" {delay(.2)} href="data:image/png;base64,{photo}" x="{panel_x}" y="0" width="{panel_w}" height="{height}" preserveAspectRatio="xMidYMid slice"/></g>
"""
    label = f'{first} {last}. {config["tagline"]}'
    write_svg("hero.svg", W, height, body, [400, 600, 700], label)
    return label


def heatmap(config, data):
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
            f'<rect class="p" style="animation-delay:{.15 + col * .012 + row * .01:.2f}s" x="{gx + col * step}" '
            f'y="{gy + row * step}" width="{cell}" height="{cell}" rx="3" fill="{HEAT[day["level"]]}">'
            f'<title>{day["date"]}: {count} {plural(count, "contribution")}</title></rect>'
        )
    columns = (len(days) + lead + 6) // 7
    right = gx + columns * step - 3
    labels = "".join(
        txt(gx + col * step, gy + 7 * step + 16, name, 12, 400, MUTED)
        for i, (col, name) in enumerate(months)
        if (i + 1 == len(months) or months[i + 1][0] - col >= 3) and col < columns - 1
    )
    legend_y = 50
    legend_x = right - len(HEAT) * 14 - 34
    legend = "".join(
        f'<rect x="{legend_x + i * 14}" y="{legend_y}" width="11" height="11" rx="2.5" fill="{color}"/>'
        for i, color in enumerate(HEAT)
    )
    local_time = dt.timezone(dt.timedelta(minutes=config["utc_offset_minutes"]))
    updated = dt.datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")).astimezone(local_time)
    stamp = f"UPDATED {updated.day} {updated.strftime('%b %Y').upper()}"
    height = gy + 7 * step + 44
    body = f"""
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<g class="r" {delay(.05)}>{txt(42, 66, f'Every day, <tspan fill="{ACCENT}">in orange</tspan>', 34, 600, INK, TIGHT)}</g>
<g class="f" {delay(.1)}>
{txt(legend_x - 8, legend_y + 10, "less", 12, 400, MUTED, 0, 'text-anchor="end"')}{legend}
{txt(legend_x + len(HEAT) * 14 + 2, legend_y + 10, "more", 12, 400, MUTED)}
{label_text(legend_x - 56, legend_y + 10, stamp, MUTED, 'text-anchor="end"')}
</g>
{"".join(cells)}
<g class="f" {delay(.7)}>{labels}</g>
"""
    write_svg("heatmap.svg", W, height, body, [400, 600],
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
        at = .2 + index * .05
        center = f"{x + bar / 2:.1f}"
        bars.append(
            f'<rect class="g" {delay(at)} x="{x:.1f}" y="{base - bar_h}" width="{bar:.1f}" height="{bar_h}" rx="4" fill="{fill}">'
            f'<title>{name}: {month["total"]:,}</title></rect>'
            f'<g class="f" {delay(at)}>{txt(center, base + 22, name, 12, 400, MUTED, 0, MIDDLE)}</g>'
        )
        if month is best and month["total"]:
            bars.append(
                f'<g class="p" {delay(.9)}>'
                + txt(center, base - bar_h - 10, f'{month["total"]:,}', 12, 600, INK, 0, MIDDLE)
                + "</g>"
            )
    current, longest = data["current_streak"], data["longest_streak"]
    if current:
        streak = current
        note = "current streak, and the longest" if current >= longest else f"current streak, longest {longest}"
    else:
        streak, note = longest, "longest streak this year"
    stats = [
        (f'{streak} {plural(streak, "day")}', note),
        (f'{data["active_days"]}<tspan fill="#8e8e93"> / {len(data["days"])}</tspan>', "days with a contribution"),
        (f'{data["best_day"]["count"]}', "on the busiest day"),
    ]
    side = []
    for index, (big, small) in enumerate(stats):
        y = 104 + index * 92
        side.append(
            f'<g class="r" {delay(.4 + index * .12)}>{txt(650, y, big, 38, 700, INK, -0.03)}'
            f'{txt(650, y + 24, small, 13, 400, MUTED)}</g>'
        )
        if index < 2:
            side.append(f'<rect class="f" {delay(.4)} x="650" y="{y + 44}" width="190" height="1" fill="{RULE}"/>')
    total = data["total_contributions"]
    body = f"""
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<g class="f" {delay(.05)}>{label_text(40, 58, "THE LAST 12 MONTHS ON GITHUB")}</g>
<g class="r" {delay(.1)}>{txt(38, 114, f'{total:,} {plural(total, "contribution")}', 46, 700, INK, -0.05)}</g>
{"".join(bars)}{"".join(side)}
"""
    write_svg("activity.svg", W, height, body, [400, 600, 700],
              f"{total:,} contributions in the last 12 months, best streak {max(current, longest)} days")


def tile(position, name, label, bg, fg, number, word, blurb, at):
    height = 210
    lines = wrap(blurb, 400, 14, THIRD_W - 48, 3)
    blurb_svg = "".join(
        f'<g class="r" {delay(at + .4 + i * .08)}>{txt(24, 150 + i * 20, escape(line), 14, 400, fg)}</g>'
        for i, line in enumerate(lines)
    )
    body = f"""
<rect width="{THIRD_W}" height="{height}" rx="14" fill="{bg}"/>
<g class="f" {delay(at)}>{label_text(24, 38, label, fg)}</g>
{arrow_right(THIRD_W - 38, 27, fg, at + 1)}
<g class="r" {delay(at + .2)}>{txt(23, 112, f"{number} {escape(word)}", 40, 700, fg, -0.06)}</g>
{blurb_svg}
"""
    alt = f"{label}: {number} {word}. {blurb}"
    write_svg(f"{name}.svg", THIRD_W, height, body, [400, 600, 700], alt,
              left=4 * position, right=8 - 4 * position)
    return alt


PIXEL_FONT = {
    " ": ("00000",) * 7,
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    ",": ("00000", "00000", "00000", "00000", "00110", "00100", "01000"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
}
BOT_OUTLINE = ("000010000", "000010000", "111111111", "100000001", "101000101", "100000001", "100111001", "111111111")
BOT_SOLID = ("000010000", "000111000", "111111111", "110111011", "111111111", "110000011", "111111111", "011000110")
POINTER = ("1000000", "1100000", "1110000", "1111000", "1111100", "1111110", "1111111", "1111000", "1001100", "0001100")
PIXEL_ARROW = ("0000100", "0000010", "1111111", "0000010", "0000100")

ARCADE_CSS = """
@keyframes march{0%{transform:translateX(-18px)}25%{transform:translateX(-6px)}50%{transform:translateX(12px)}75%{transform:translateX(-6px)}100%{transform:none}}
@keyframes aim{from{transform:translateX(-72px)}to{transform:none}}
@keyframes shot{0%{opacity:1;transform:translateY(15px)}99%{opacity:1;transform:none}100%{opacity:0;transform:none}}
@keyframes hit{0%,83%{opacity:1}86%{opacity:0}90%{opacity:1}93%{opacity:0}96%{opacity:1}100%{opacity:0}}
@keyframes burst{0%{opacity:1;transform:scale(.4)}100%{opacity:0;transform:scale(1.5)}}
.march{animation:march 1.4s steps(1,end) both}
.aim{animation:aim 1.2s steps(6,end) .2s both}
.shot{opacity:0;animation:shot .24s steps(3,end) 1.5s forwards}
.hit{opacity:0;animation:hit 2.1s steps(1,end) both}
.burst{opacity:0;transform-box:fill-box;transform-origin:center;animation:burst .35s steps(3,end) 1.74s forwards}
@media (prefers-reduced-motion:reduce){.march,.aim,.shot,.hit,.burst{animation:none!important}}
"""


def pixel_path(rows, x, y, size):
    parts = []
    for row_index, row in enumerate(rows):
        for match in re.finditer("1+", row):
            run = len(match.group()) * size
            parts.append(f"M{x + match.start() * size} {y + row_index * size}h{run}v{size}h-{run}z")
    return "".join(parts)


def pixel_text(text, x, y, size):
    return "".join(pixel_path(PIXEL_FONT[c], x + i * 6 * size, y, size) for i, c in enumerate(text))


def arcade_card(position):
    height = 210
    lines = ("CHILL, OR", "WANNA PLAY", "A GAME?")
    copy = "".join(
        f'<path class="f" {delay(.05 + i * .1)} d="{pixel_text(line, 24, 20 + i * 27, 3)}" fill="#ffffff"/>'
        for i, line in enumerate(lines)
    )
    bots, target = [], ""
    for row, y in enumerate((119, 139)):
        for col in range(6):
            sprite = BOT_OUTLINE if (row + col) % 2 == 0 else BOT_SOLID
            path = pixel_path(sprite, 44 + col * 36, y, 2)
            if (row, col) == (1, 3):
                target = f'<path class="hit" d="{path}" fill="{ACCENT}"/>'
            else:
                bots.append(path)
    sparks = "M153 139h4v4h-4zM165 139h4v4h-4zM153 151h4v4h-4zM165 151h4v4h-4zM159 145h4v4h-4z"
    body = f"""
<defs><pattern id="grid" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M8 0H0V8" fill="none" stroke="#1e1e1e"/></pattern>
<clipPath id="screen"><rect x=".5" y=".5" width="{THIRD_W - 1}" height="{height - 1}" rx="14"/></clipPath></defs>
<rect x=".5" y=".5" width="{THIRD_W - 1}" height="{height - 1}" rx="14" fill="{INK}"/>
<g clip-path="url(#screen)"><rect y="108" width="{THIRD_W}" height="102" fill="url(#grid)"/>
<rect y="107" width="{THIRD_W}" height="1" fill="#3a3a3a"/></g>
<rect x=".5" y=".5" width="{THIRD_W - 1}" height="{height - 1}" rx="14" fill="none" stroke="#30363d"/>
<g shape-rendering="crispEdges">
{copy}
<path d="{pixel_path(PIXEL_ARROW, round(THIRD_W - 38), 26, 2)}" fill="#ffffff"/>
<g class="march"><path d="{"".join(bots)}" fill="{ACCENT}"/>{target}</g>
<rect class="shot" x="160" y="155" width="2" height="6" fill="#ffffff"/>
<path class="burst" d="{sparks}" fill="#ffffff"/>
<path class="aim" d="{pixel_path(POINTER, 160, 176, 2)}" fill="#ffffff"/>
</g>
"""
    alt = "Chill, or wanna play a game?"
    write_svg("play.svg", THIRD_W, height, body, [], alt, left=4 * position, right=8 - 4 * position, extra_css=ARCADE_CSS)
    return alt


def repo_card(position, repo, description):
    height = 176
    at = .05 + position * .12
    title = wrap(pretty_name(repo["name"]), 600, 18, THIRD_W - 64, 2, -0.03)
    title_svg = "".join(txt(40, 39 + i * 23, escape(line), 18, 600, INK, -0.03) for i, line in enumerate(title))
    first_y = 39 + (len(title) - 1) * 23 + 33
    lines = wrap(description, 400, 14, THIRD_W - 48, 3 if len(title) == 1 else 2)
    desc_svg = "".join(txt(24, first_y + i * 21, escape(line), 14, 400, INK_SOFT) for i, line in enumerate(lines))
    meta_y = height - 22
    meta = txt(24, meta_y, escape(repo["language"]), 12, 400, MUTED) if repo["language"] else ""
    if repo["stars"]:
        star_x = 24 + (text_width(repo["language"], 400, 12) + 14 if repo["language"] else 0)
        meta += star(star_x, meta_y - 10, MUTED) + txt(f"{star_x + 16:.1f}", meta_y, str(repo["stars"]), 12, 400, MUTED)
    color = (ACCENT, INK, YELLOW)[position]
    body = f"""
<rect width="{THIRD_W}" height="{height}" rx="14" fill="{PAPER}"/>
<g class="r" {delay(at)}><rect x="24" y="30" width="8" height="8" rx="2" fill="{color}"/>{title_svg}{desc_svg}{meta}</g>
"""
    alt = f'{pretty_name(repo["name"])}: {description}'
    write_svg(f"repo-{position + 1}.svg", THIRD_W, height, body, [400, 600], alt,
              left=4 * position, right=8 - 4 * position)
    return alt


def section_title(theme):
    color = "#e6edf3" if theme == "dark" else INK
    content = f'What I\'m <tspan fill="{ACCENT}">coding</tspan>'
    body = f'<g class="r" {delay(0)}>{txt(2, 46, content, 34, 600, color, TIGHT)}</g>'
    write_svg(f"title-coding-{theme}.svg", W, 64, body, [600], "What I'm coding", bottom=0)


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


def tiles(config, repos):
    base = f'https://github.com/{config["username"]}'
    latest = max(repos, key=lambda r: r["pushed_at"])
    alts = [tile(0, "build", "BUILD", ACCENT, INK, len(repos), plural(len(repos), "project"),
                 f'Public repos, most recently {pretty_name(latest["name"])}.', .05)]
    alts.append(arcade_card(1))
    counts = {}
    for repo in repos:
        if repo["language"]:
            counts[repo["language"]] = counts.get(repo["language"], 0) + 1
    languages = sorted(counts, key=lambda l: (-counts[l], l))
    blurb = f"Mostly {languages[0]}" + (f", plus {join_words(languages[1:])}." if len(languages) > 1 else ".")
    alts.append(tile(2, "stack", "STACK", YELLOW, INK, len(languages), plural(len(languages), "language"), blurb, .35))
    return alts, [f"{base}?tab=repositories", config.get("game_url"), f"{base}?tab=repositories&sort=stargazers"]


def image(src, alt, width="100%"):
    return f'<img src="./cards/{src}" width="{width}" alt="{escape(alt, quote=True)}" />'


def linked(url, inner):
    return f'<a href="{escape(url, quote=True)}">{inner}</a>'


def write_readme(config, data, hero_alt, tile_alts, tile_urls, picks, repo_alts):
    tile_row = "".join(
        linked(url, image(f"{name}.svg", alt, "33.333%")) if url else image(f"{name}.svg", alt, "33.333%")
        for name, alt, url in zip(("build", "play", "stack"), tile_alts, tile_urls)
    )
    repo_row = "".join(
        linked(repo["url"], image(f"repo-{i + 1}.svg", repo_alts[i], "33.333%")) for i, repo in enumerate(picks)
    )
    links = " &nbsp;/&nbsp; ".join(linked(l["url"], escape(l["label"])) for l in config["links"])
    readme = f"""<!-- Generated by scripts/render_cards.py. Edit profile.json, not this file. -->
<div align="center">
{linked(config["website"], image("hero.svg", hero_alt))}<br>
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
    repos = own_repos(config, data)
    hero_alt = hero(config)
    heatmap(config, data)
    activity(data)
    tile_alts, tile_urls = tiles(config, repos)
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
