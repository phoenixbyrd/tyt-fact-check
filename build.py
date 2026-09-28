#!/usr/bin/env python3
"""Build the TYT Fact Check static site.

Reads editions/<YYYY-MM-DD>/checks.json (+ optional episode.mp3) and
generates docs/index.html (latest edition + archive + about) and
docs/<YYYY-MM-DD>.html per edition.

The unit of analysis is the NON-TRUTHFUL SEGMENT: a moment in a video that
misleads — selective omission, false implication, cherry-picked data,
strawman, deceptive framing, loaded language implying something false, or an
outright false claim. Each segment is called out and its dishonesty explained.
Each video gets a sliding 0-100 truthfulness score.

checks.json schema:
{
  "date": "2026-09-29",
  "videos": [
    {
      "title": "...", "url": "https://www.youtube.com/watch?v=...",
      "video_id": "...", "published": "2026-09-28T18:04:00-04:00",
      "truth_score": 64, "truth_label": "Mixed",   // null score + "Unverifiable" label when no transcript exists
      "summary": "...",
      "segments": [
        {"segment": "quote or description (+ approx timestamp)",
         "issue": "Omission", "severity": "Moderate",
         "explanation": "what is misleading + the fuller accurate picture",
         "sources": [{"name": "AP", "url": "https://..."}]}
      ]
    }
  ],
  "podcast": {"file": "episode.mp3", "duration_sec": 1234}
}

Severity: Minor (-5), Moderate (-15), Severe (-30).
Score bands: 90-100 Honest, 70-89 Mostly honest, 50-69 Mixed,
             30-49 Misleading, 0-29 Deceptive.
"""

import html
import json
import os
import shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
EDITIONS = os.path.join(ROOT, "editions")
DOCS = os.path.join(ROOT, "docs")
STATIC = os.path.join(ROOT, "static")

CSS_V = 2
JS_V = 1

SEV_CLASS = {"Minor": "s-minor", "Moderate": "s-moderate", "Severe": "s-severe"}
SCORE_CLASS = {
    "Honest": "v-accurate",
    "Mostly honest": "v-mostly",
    "Mixed": "v-mixed",
    "Misleading": "v-misleading",
    "Deceptive": "v-false",
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def fmt_date(datestr):
    try:
        return datetime.strptime(datestr, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        return datestr


def load_editions():
    editions = []
    if not os.path.isdir(EDITIONS):
        return editions
    for name in sorted(os.listdir(EDITIONS), reverse=True):
        path = os.path.join(EDITIONS, name, "checks.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            data = json.load(f)
        data["_date"] = data.get("date", name)
        mp3 = os.path.join(EDITIONS, name, "episode.mp3")
        data["_has_audio"] = os.path.isfile(mp3)
        editions.append(data)
    return editions


def slider_html(score, label):
    if score is None:
        return (
            '<div class="truth"><div class="truth-score">'
            '<span class="verdict v-unverifiable">Unverifiable</span></div>'
            '<p class="empty">No transcript available — honesty could not be assessed.</p></div>'
        )
    score = max(0, min(100, int(score)))
    cls = SCORE_CLASS.get(label, "v-mixed")
    return (
        '<div class="truth">'
        '<div class="truth-score"><span class="score-num">%d</span>'
        '<span class="verdict %s">%s</span></div>'
        '<div class="slider" role="img" aria-label="Truthfulness score %d out of 100: %s">'
        '<div class="s-track"><div class="s-marker" style="left:%d%%"></div></div>'
        '<div class="s-ends"><span>Deceptive</span><span>Honest</span></div>'
        "</div></div>"
        % (score, cls, esc(label), score, esc(label), score)
    )


def segment_html(seg):
    sources = "".join(
        '<a class="src" href="%s" target="_blank" rel="noopener">%s</a>'
        % (esc(s.get("url", "#")), esc(s.get("name", "source")))
        for s in seg.get("sources", [])
    )
    src_block = ('<div class="sources">Sources: %s</div>' % sources) if sources else ""
    sev = seg.get("severity", "Moderate")
    sev_cls = SEV_CLASS.get(sev, "s-moderate")
    return (
        '<div class="segment">'
        '<div class="seg-head"><span class="sev %s">%s</span>'
        '<span class="seg-issue">%s</span></div>'
        '<blockquote class="seg-quote">%s</blockquote>'
        '<p class="seg-why">%s</p>%s</div>'
        % (sev_cls, esc(sev), esc(seg.get("issue", "Misleading segment")),
           esc(seg.get("segment", "")), esc(seg.get("explanation", "")), src_block)
    )


def video_card(v):
    segs = "".join(segment_html(s) for s in v.get("segments", []))
    if not segs:
        segs = '<p class="empty">No misleading segments found in this video.</p>'
    n = len(v.get("segments", []))
    seg_title = "Key non-truthful segment%s" % ("s" if n != 1 else "")
    pub = esc(v.get("published", ""))
    return (
        '<article class="card">'
        '<a class="card-title" href="%s" target="_blank" rel="noopener">%s</a>'
        '<div class="card-meta">Published %s &middot; <a class="yt" href="%s" target="_blank" rel="noopener">Watch on YouTube</a></div>'
        "%s"
        '<p class="card-summary">%s</p>'
        '<h3 class="seg-h">%s (%d)</h3>'
        '<div class="segments">%s</div>'
        "</article>"
        % (esc(v.get("url", "#")), esc(v.get("title", "Untitled")),
           pub, esc(v.get("url", "#")),
           slider_html(v.get("truth_score", 0), v.get("truth_label", "Mixed")),
           esc(v.get("summary", "")), seg_title, n, segs)
    )


def tally(ed):
    vids = ed.get("videos", [])
    if not vids:
        return "No videos checked"
    scored = [int(v["truth_score"]) for v in vids if v.get("truth_score") is not None]
    if not scored:
        return "%d videos checked &middot; no videos verifiable" % len(vids)
    avg = sum(scored) / len(scored)
    worst = min((v for v in vids if v.get("truth_score") is not None),
                key=lambda v: int(v["truth_score"]))
    return (
        "%d videos checked &middot; average truthfulness <strong>%d/100</strong> "
        "&middot; lowest: %s (%d)"
        % (len(vids), round(avg), esc(worst.get("title", "")[:60]),
           int(worst.get("truth_score", 0)))
    )


def edition_body(ed, standalone):
    date = ed["_date"]
    audio = ""
    if ed.get("_has_audio"):
        audio = (
            '<div class="podcast"><div class="pod-h">Daily podcast</div>'
            '<audio controls preload="none" src="audio/%s.mp3"></audio>'
            '<p class="pod-note">Alex and Jordan walk through every video&#x2019;s '
            "score and its key misleading segments.</p></div>" % esc(date)
        )
    cards = "".join(video_card(v) for v in ed.get("videos", []))
    if not cards:
        cards = '<p class="empty">No videos were checked for this edition.</p>'
    head_link = "" if standalone else '<p class="back"><a href="index.html">&larr; All editions</a></p>'
    return (
        '%s<h1>Truth-check: TYT videos from %s</h1>'
        '<p class="tally">%s</p>%s<div class="cards">%s</div>'
        % (head_link, esc(fmt_date(date)), tally(ed), audio, cards)
    )


BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="style.css?v={css_v}">
</head>
<body>
<header class="site">
  <a class="brand" href="index.html"><span class="brand-mark">&#x1F50D;</span> TYT Fact Check</a>
  <span class="tagline">How honest was today's TYT?</span>
</header>
<button id="menuBtn" aria-label="Open menu"><span></span><span></span><span></span></button>
<div id="scrim"></div>
<aside id="drawer" aria-label="Site menu">
  <div class="d-sec"><div class="d-h">Menu</div>
    <a href="index.html">Home</a>
    {latest_link}
    <a href="index.html#archive">Archive</a>
    <a href="index.html#about">About &amp; methodology</a>
  </div>
  <div class="d-sec"><div class="d-h">Editions</div>
    {edition_links}
  </div>
</aside>
<main class="wrap">
{body}
</main>
<footer class="foot">
  <p>Not affiliated with The Young Turks or TYT Network. Scores reflect the evidence available at publication time; <a href="index.html#about">corrections policy</a> in About.</p>
</footer>
<script src="site.js?v={js_v}"></script>
</body>
</html>
"""


def _avg(ed):
    scored = [int(v["truth_score"]) for v in ed.get("videos", [])
              if v.get("truth_score") is not None]
    return round(sum(scored) / len(scored)) if scored else None


def archive_html(editions):
    if not editions:
        return '<p class="empty">Past editions will appear here.</p>'
    items = ""
    for ed in editions:
        avg = _avg(ed)
        avg_txt = "avg %d/100 &middot; " % avg if avg is not None else ""
        items += (
            '<a class="arch-item" href="%s.html"><span>%s</span>'
            '<span class="arch-n">%s%d videos</span></a>'
            % (esc(ed["_date"]), esc(fmt_date(ed["_date"])),
               avg_txt, len(ed.get("videos", [])))
        )
    return '<div class="archive">%s</div>' % items


ABOUT_HTML = """
<section id="about" class="about">
<h2>About &amp; methodology</h2>
<p><strong>TYT Fact Check</strong> watches every full-length video The Young Turks
post to YouTube each day and rates its <em>honesty</em> — not with a checklist of
trivia, but by pulling out the key non-truthful segments and explaining what makes
each one misleading.</p>
<ul>
<li><strong>The unit is the misleading segment.</strong> Selective omission, false
implication, cherry-picked data, strawmen, deceptive framing, loaded language that
implies something false, or an outright false claim — each gets called out with the
fuller, accurate picture.</li>
<li><strong>Sliding truthfulness score.</strong> Every video scores 0&ndash;100.
Each segment deducts by severity: Minor &minus;5, Moderate &minus;15, Severe
&minus;30. Bands: 90&ndash;100 Honest, 70&ndash;89 Mostly honest, 50&ndash;69 Mixed,
30&ndash;49 Misleading, 0&ndash;29 Deceptive.</li>
<li><strong>Evidence first.</strong> Every segment explanation cites named sources
(primary documents, official data, wire reporting) you can open yourself.</li>
<li><strong>Corrections:</strong> if new evidence changes a score, the edition is
updated and the change is noted. No stealth edits.</li>
<li><strong>One edition per day,</strong> plus a daily podcast episode walking through
each video&#x2019;s score and misleading segments. Not affiliated with The Young Turks.</li>
</ul>
</section>
"""


def build():
    os.makedirs(DOCS, exist_ok=True)
    editions = load_editions()

    for name in ("style.css", "site.js"):
        src = os.path.join(STATIC, name)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(DOCS, name))

    audio_dir = os.path.join(DOCS, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    for ed in editions:
        src = os.path.join(EDITIONS, ed["_date"], "episode.mp3")
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(audio_dir, ed["_date"] + ".mp3"))

    edition_links = "".join(
        '<a href="%s.html">%s</a>' % (esc(ed["_date"]), esc(fmt_date(ed["_date"])))
        for ed in editions
    ) or '<a href="index.html">No editions yet</a>'
    latest_link = (
        '<a href="%s.html">Latest edition</a>' % esc(editions[0]["_date"])
        if editions else ""
    )

    def page(title, body):
        return BASE.format(title=esc(title), css_v=CSS_V, js_v=JS_V,
                           body=body, edition_links=edition_links,
                           latest_link=latest_link)

    for ed in editions:
        with open(os.path.join(DOCS, ed["_date"] + ".html"), "w") as f:
            f.write(page("TYT Fact Check — " + fmt_date(ed["_date"]),
                         edition_body(ed, standalone=True)))

    if editions:
        index_body = (
            edition_body(editions[0], standalone=False)
            + '<h2 id="archive">Past editions</h2>'
            + archive_html(editions[1:])
            + ABOUT_HTML
        )
    else:
        index_body = (
            "<h1>TYT Fact Check</h1>"
            '<p class="lede">Every full-length video The Young Turks post to '
            "YouTube, rated daily for honesty — the key non-truthful segments pulled "
            "out and explained, with a sliding 0&ndash;100 truthfulness score per video, "
            "plus a daily podcast walking through it all.</p>"
            '<p class="empty">The first edition publishes tomorrow morning. Check back then.</p>'
            + '<h2 id="archive">Past editions</h2>'
            + archive_html([])
            + ABOUT_HTML
        )
    with open(os.path.join(DOCS, "index.html"), "w") as f:
        f.write(page("TYT Fact Check — daily honesty rating of The Young Turks", index_body))

    print("Built %d editions -> %s" % (len(editions), DOCS))


if __name__ == "__main__":
    build()
