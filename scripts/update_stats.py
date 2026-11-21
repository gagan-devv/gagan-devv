#!/usr/bin/env python3
"""Regenerate assets/stats.svg and assets/langs.svg for the profile README.

Data sources:
  - GitHub REST API (repos + languages) using GITHUB_TOKEN
  - https://github.com/users/<user>/contributions for the contribution graph
    (contributions this year, active days, current weekly streak)

Runs nightly via .github/workflows/readme-stats.yml.
"""
import collections
import datetime as dt
import html
import json
import os
import re
import urllib.request

USER = "gagan-devv"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
E = html.escape


def gh_json(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "readme-stats",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "readme-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# ------------------------------------------------------------- repos + languages
repos = []
page = 1
while True:
    batch = gh_json(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}")
    if not batch:
        break
    repos.extend(batch)
    page += 1
own = [r for r in repos if not r.get("fork")]
n_projects = len(own)

lang_bytes = collections.Counter()
for r in own:
    try:
        langs = gh_json(r["languages_url"])
        for k, v in langs.items():
            lang_bytes[k] += v
    except Exception:
        pass
total = sum(lang_bytes.values()) or 1
LANG_COLORS = {
    "TypeScript": "#3178c6", "Python": "#3572A5", "JavaScript": "#f1e05a",
    "Go": "#00ADD8", "C++": "#f34b7d", "C": "#555555", "HTML": "#e34c26",
    "CSS": "#563d7c", "Jupyter Notebook": "#DA5B0B", "Shell": "#89e051",
    "Rust": "#dea584", "Java": "#b07219",
}
top_langs = [(k, round(v * 100 / total, 1)) for k, v in lang_bytes.most_common(5)]

# ------------------------------------------------------------- contribution graph
year = dt.date.today().year
contrib_html = get_text(f"https://github.com/users/{USER}/contributions?from={year}-01-01&to={year}-12-31")
# day cells: <td ... data-date="2026-03-14" ...> ... <tool-tip ...>N contributions on ...
day_counts = {}
for m in re.finditer(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*>.*?<tool-tip[^>]*>([^<]+)</tool-tip>',
                     contrib_html, re.S):
    date_s, tip = m.group(1), m.group(2)
    nm = re.match(r"(\d+)", tip.strip())
    day_counts[date_s] = int(nm.group(1)) if nm else 0

today = dt.date.today()
contributions_year = sum(v for d, v in day_counts.items() if d.startswith(str(year)))
active_days = sum(1 for d, v in day_counts.items() if v > 0 and d <= today.isoformat())

# current weekly streak: consecutive weeks (Sun-Sat) with >= 1 contribution,
# ending with the current week (the current partial week counts if it has any)
def week_key(d):
    return (d - dt.timedelta(days=(d.weekday() + 1) % 7)).isoformat()  # Sunday of that week

weeks = collections.Counter()
for d, v in day_counts.items():
    if v > 0:
        weeks[week_key(dt.date.fromisoformat(d))] += 1
streak = 0
wk = dt.date.fromisoformat(week_key(today))
while weeks.get(wk.isoformat(), 0) > 0:
    streak += 1
    wk -= dt.timedelta(days=7)

# ------------------------------------------------------------- stats.svg
cards = [
    (f"{contributions_year:,}", f"contributions in {year}", "#22d3ee"),
    (str(active_days), "active days this year", "#ff4fa3"),
    (f"{streak} wk", "current commit streak", "#a3e635"),
    (str(n_projects), "projects built &amp; shipped", "#fbbf24"),
]
cw, ch, gap, x0 = 210, 110, 16, 12
parts = []
for i, (num, label, color) in enumerate(cards):
    cx = x0 + i * (cw + gap)
    parts.append(f'''
  <g>
    <rect x="{cx}" y="12" width="{cw}" height="{ch}" rx="12" fill="#0a0e16" stroke="{color}" stroke-opacity="0.85" stroke-width="1.5"/>
    <rect x="{cx}" y="12" width="{cw}" height="3" rx="1.5" fill="{color}" opacity="0.9"/>
    <text x="{cx + cw/2}" y="62" text-anchor="middle" font-family="'Segoe UI',system-ui,sans-serif"
          font-size="34" font-weight="800" fill="{color}">{num}</text>
    <text x="{cx + cw/2}" y="90" text-anchor="middle" font-family="'Segoe UI',system-ui,sans-serif"
          font-size="12.5" fill="#c2d0e5">{label}</text>
  </g>''')
stats = f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="134" viewBox="0 0 900 134">
  <rect width="900" height="134" fill="none"/>
  {''.join(parts)}
</svg>'''
with open(os.path.join(OUT, "stats.svg"), "w") as f:
    f.write(stats)

# ------------------------------------------------------------- langs.svg
langs5 = [(name, pct, LANG_COLORS.get(name, "#8b949e")) for name, pct in top_langs]
bar_x, bar_y, bar_w, bar_h = 20, 18, 860, 20
segs, cx = [], bar_x
for name, pct, color in langs5:
    w = round(bar_w * pct / 100, 1)
    segs.append(f'<rect x="{cx}" y="{bar_y}" width="{w}" height="{bar_h}" fill="{color}"/>')
    cx += w
legend, lx = [], 20
for name, pct, color in langs5:
    label = f"{name} {pct}%"
    tw = 9 + len(label) * 7.2 + 22
    legend.append(f'''
    <g>
      <circle cx="{lx + 6}" cy="66" r="6" fill="{color}"/>
      <text x="{lx + 20}" y="71" font-family="'Segoe UI',system-ui,sans-serif" font-size="14" fill="#dbe6f4">{label}</text>
    </g>''')
    lx += tw
langs_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="92" viewBox="0 0 900 92">
  <rect width="900" height="92" rx="10" fill="#0a0e16"/>
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="10" fill="#05070d"/>
  <g>{''.join(segs)}</g>
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="10" fill="none" stroke="#1c2536" stroke-width="1"/>
  {''.join(legend)}
</svg>'''
with open(os.path.join(OUT, "langs.svg"), "w") as f:
    f.write(langs_svg)

print(f"stats: {contributions_year} contributions, {active_days} active days, {streak} wk streak, {n_projects} projects")
print(f"langs: {top_langs}")
