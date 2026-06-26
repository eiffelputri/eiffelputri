import json
import os
import re
import statistics
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

USER = "eiffelputri"
SKIP = {f"{USER}/{USER}"}
DAYS = 90
MAX_PATCHES = 60
TZ = ZoneInfo("Asia/Jakarta")
OUT = ".github/metrics/metrics-habits.svg"
RENDERS = ".github/metrics"
GAP = 6
TOKEN = os.environ["GH_TOKEN"]


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def parse(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


since = datetime.now(timezone.utc) - timedelta(days=DAYS)
repos = api("/user/repos?per_page=100&affiliation=owner&sort=pushed")
repos = [r for r in repos if r["full_name"] not in SKIP and r["pushed_at"] and parse(r["pushed_at"]) > since]

commits = []
for repo in repos:
    page = 1
    while True:
        try:
            items = api(f"/repos/{repo['full_name']}/commits?author={USER}&since={since.isoformat()}&per_page=100&page={page}")
        except Exception:
            break
        commits += [(parse(c["commit"]["author"]["date"]).astimezone(TZ), repo["full_name"], c["sha"]) for c in items]
        if len(items) < 100:
            break
        page += 1
commits.sort(reverse=True)

sizes, lengths = [], []
for _, repo, sha in commits[:MAX_PATCHES]:
    try:
        files = api(f"/repos/{repo}/commits/{sha}").get("files", [])
    except Exception:
        continue
    sizes.append(sum(f.get("additions", 0) + f.get("deletions", 0) for f in files))
    for f in files:
        if re.search(r"\.(lock|min\.js|svg|json|map)$|package-lock", f["filename"]):
            continue
        for line in (f.get("patch") or "").splitlines():
            if line.startswith("+") and not line.startswith("+++") and line[1:].strip():
                lengths.append(len(line[1:].rstrip()))

facts = []
if commits:
    hour = Counter(w.hour for w, _, _ in commits).most_common(1)[0][0]
    day = Counter(w.strftime("%A") for w, _, _ in commits).most_common(1)[0][0]
    weekdays = 100 * sum(1 for w, _, _ in commits if w.weekday() < 5) / len(commits)
    facts += [
        ("clock", f"Mostly pushes code around {hour:02d}:00"),
        ("calendar", f"Mostly active on {day}"),
        ("briefcase", f"Pushes {weekdays:.0f}% of commits on weekdays" if weekdays >= 50 else f"Pushes {100 - weekdays:.0f}% of commits on weekends"),
    ]
if sizes:
    facts.append(("diff", f"Has approximately {statistics.median(sizes):g} lines changed per commit"))
if lengths:
    facts.append(("ruler", f"Has approximately {sum(lengths) / len(lengths):.1f} characters per line of code written"))
if not facts:
    facts.append(("clock", f"No commits in the last {DAYS} days"))

ICONS = {
    "bulb": '<path d="M8 1.5a4.5 4.5 0 0 0-2.6 8.2c.4.3.6.7.6 1.1V12h4v-1.2c0-.4.2-.8.6-1.1A4.5 4.5 0 0 0 8 1.5ZM6 13.5h4M6.5 15h3" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
    "clock": '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M8 4.5V8l2.3 1.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
    "calendar": '<rect x="2" y="3" width="12" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2 6.5h12M5 1.5v3M11 1.5v3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
    "briefcase": '<rect x="1.5" y="4.5" width="13" height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5.5 4.5V3a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.5M1.5 8.5h13" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "ruler": '<rect x="1.5" y="5" width="13" height="6" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M4.5 5v2.5M7.5 5v3M10.5 5v2.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
    "diff": '<path d="M5 2v6M2 5h6M9 12.5h5M3 14l10-12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
}
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def icon(name, x, y, color):
    return f'<g transform="translate({x} {y})" color="{color}">{ICONS[name]}</g>'


def svg_height(path):
    try:
        return int(re.search(r'height="(\d+)"', open(path).read())[1])
    except (OSError, TypeError):
        return None


# samain tinggi kolom kiri (kalender + habits) dengan kanan (stats):
# kolom yang lebih pendek ditambah ruang kosong di bawah
FIRST, STEP = 44, 22
height = FIRST + STEP * len(facts) - 6
calendar = svg_height(f"{RENDERS}/metrics-calendar.svg")
stats = svg_height(f"{RENDERS}/metrics-stats.svg")
if calendar and stats:
    left = calendar + height + GAP
    if left > stats:
        path = f"{RENDERS}/metrics-stats.svg"
        content = open(path).read()
        content = re.sub(r'height="\d+"', f'height="{left}"', content, count=1)
        open(path, "w").write(content)
    else:
        height = stats - calendar - GAP

rows = []
y = FIRST
for name, text in facts:
    rows.append(icon(name, 10, round(y - 12, 1), "#8d8580"))
    rows.append(f'<text x="34" y="{round(y, 1)}" font-family="{FONT}" font-size="14" fill="#c5beb5">{text}</text>')
    y += STEP
sample = f"(computed from last {len(commits)} commits)" if commits else ""
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{height}" viewBox="0 0 480 {height}">
  {icon("bulb", 10, 5, "#d4af37")}
  <text x="34" y="18" font-family="{FONT}" font-size="16" fill="#d4af37">Recent coding habits <tspan font-size="12" fill="#8d8580">{sample}</tspan></text>
  {"".join(rows)}
</svg>
"""
with open(OUT, "w") as f:
    f.write(svg)
print(f"{len(commits)} commits from {len(repos)} repos -> {OUT}")
for _, text in facts:
    print(" -", text)
