#!/usr/bin/env python3
"""Build the TYT Fact Check static site.

Reads editions/<YYYY-MM-DD>/checks.json (+ optional episode.mp3) and
generates docs/index.html (latest edition + archive + about) and
docs/<YYYY-MM-DD>.html per edition.

checks.json schema:
{
  "date": "2026-09-29",
  "videos": [
    {
      "title": "...", "url": "https://www.youtube.com/watch?v=...",
      "video_id": "...", "published": "2026-09-28T18:04:00-04:00",
      "verdict": "Mixed", "summary": "...",
      "claims": [
        {"claim": "...", "verdict": "False", "explanation": "...",
         "sources": [{"name": "AP", "url": "https://..."}]}
      ]
    }
  ],
  "podcast": {"file": "episode.mp3", "duration_sec": 1234}
}

Verdicts: Accurate, Mostly accurate, Mixed, Misleading, False,
          Unverifiable, No checkable claims
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

CSS_V = 1
JS_V = 1

VERDICT_CLASS = {
    "Accurate": "v-accurate",
    "Mostly accurate": "v-mostly",
    "Mixed": "v-mixed",
    "Misleading": "v-misleading",
    "False": "v-false",
    "Unverifiable": "v-unverifiable",
    "No checkable claims": "v-unverifiable",
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


def verdict_badge(verdict):
    cls = VERDICT_CLASS.get(verdict, "v-unverifiable")
    return '<span class="verdict %s">%s</span>' % (cls, esc(verdict))


def claim_html(claim):
    sources = "".join(
        '<a class="src" href="%s" target="_blank" rel="noopener">%s</a>'
        % (esc(s.get("url", "#")), esc(s.get("name", "source")))
        for s in claim.get("sources", [])
    )
    src_block = ('<div class="sources">Sources: %s</div>' % sources) if sources else ""
    return (
        '<div class="claim">'
        '<div class="claim-head">%s<span class="claim-text">%s</span></div>'
        '<p class="claim-why">%s</p>%s</div>'
        % (verdict_badge(claim.get("verdict", "Unverifiable")),
           esc(claim.get("claim", "")),
           esc(claim.get("explanation", "")), src_block)
    )


def video_card(v):
    claims = "".join(claim_html(c) for c in v.get("claims", []))
    pub = esc(v.get("published", ""))
    return (
        '<article class="card">'
        '<div class="card-top">%s'
        '<a class="card-title" href="%s" target="_blank" rel="noopener">%s</a></div>'
        '<div class="card-meta">Published %s &middot; <a class="yt" href="%s" target="_blank" rel="noopener">Watch on YouTube</a></div>'
        '<p class="card-summary">%s</p>'
        '<div class="claims">%s</div>'
        '</article>'
        % (verdict_badge(v.get("verdict", "Unverifiable")),
           esc(v.get("url", "#")), esc(v.get("title", "Untitled")),
           pub, esc(v.get("url", "#")), esc(v.get("summary", "")), claims)
    )


def tally(ed):
    counts = {}
    for v in ed.get("videos", []):
        counts[v.get("verdict", "Unverifiable")] = counts.get(v.get("verdict", "Unverifiable"), 0) + 1
    order = ["False", "Misleading", "Mixed", "Mostly accurate", "Accurate",
             "Unverifiable", "No checkable claims"]
    bits = []
    for k in order:
        if counts.get(k):
            bits.append('%s: %d' % (k, counts[k]))
    return " &middot; ".join(bits) if bits else "No videos checked"


def edition_body(ed, standalone):
    date = ed["_date"]
    audio = ""
    if ed.get("_has_audio"):
        audio = (
            '<div class="podcast"><div class="pod-h">Daily podcast</div>'
            '<audio controls preload="none" src="audio/%s.mp3"></audio>'
            '<p class="pod-note">Alex and Jordan walk through every video and verdict.</p></div>'
            % esc(date)
        )
    cards = "".join(video_card(v) for v in ed.get("videos", []))
    if not cards:
        cards = '<p class="empty">No videos were checked for this edition.</p>'
    head_link = "" if standalone else '<p class="back"><a href="index.html">&larr; All editions</a></p>'
    return (
        '%s<h1>Fact-check: TYT videos from %s</h1>'
        '<p class="tally">%d videos checked &middot; %s</p>%s'
        '<div class="cards">%s</div>'
        % (head_link, esc(fmt_date(date)), len(ed.get("videos", [])),
           tally(ed), audio, cards)
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
  <span class="tagline">Every TYT video, fact-checked daily</span>
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
  <p>Not affiliated with The Young Turks or TYT Network. Verdicts reflect the evidence available at publication time; <a href="index.html#about">corrections policy</a> in About.</p>
</footer>
<script src="site.js?v={js_v}"></script>
</body>
</html>
"""


def archive_html(editions):
    if not editions:
        return '<p class="empty">Past editions will appear here.</p>'
    items = "".join(
        '<a class="arch-item" href="%s.html"><span>%s</span><span class="arch-n">%d videos</span></a>'
        % (esc(ed["_date"]), esc(fmt_date(ed["_date"])), len(ed.get("videos", [])))
        for ed in editions
    )
    return '<div class="archive">%s</div>' % items


ABOUT_HTML = """
<section id="about" class="about">
<h2>About &amp; methodology</h2>
<p><strong>TYT Fact Check</strong> watches every full-length video The Young Turks
post to YouTube each day and checks the factual claims in it — for accuracy and
honesty, no matter which direction the verdict lands.</p>
<ul>
<li><strong>Claims, not opinions.</strong> Only checkable factual claims are rated.
Opinion, predictions, and rhetoric are left alone.</li>
<li><strong>Evidence first.</strong> Every claim gets a short evidence walkthrough
with named sources (primary documents, official data, wire reporting). Nothing is
asserted without a source you can open.</li>
<li><strong>Verdicts:</strong> Accurate, Mostly accurate, Mixed, Misleading, False,
Unverifiable. A video's overall verdict follows its most severe claim.</li>
<li><strong>Corrections:</strong> if new evidence changes a verdict, the edition is
updated and the change is noted. No stealth edits.</li>
<li><strong>No feed, no spin.</strong> One edition per day, plus a daily podcast
episode at the top of each edition page. This project is not affiliated with
The Young Turks.</li>
</ul>
</section>
"""


def build():
    os.makedirs(DOCS, exist_ok=True)
    editions = load_editions()

    # static assets
    for name in ("style.css", "site.js"):
        src = os.path.join(STATIC, name)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(DOCS, name))

    # podcast audio
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

    # per-edition pages
    for ed in editions:
        with open(os.path.join(DOCS, ed["_date"] + ".html"), "w") as f:
            f.write(page("TYT Fact Check — " + fmt_date(ed["_date"]),
                         edition_body(ed, standalone=True)))

    # index: latest edition + archive + about
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
            "YouTube, fact-checked daily for honesty and accuracy — with a daily "
            "podcast walking through every verdict.</p>"
            '<p class="empty">The first edition publishes tomorrow morning. Check back then.</p>'
            + '<h2 id="archive">Past editions</h2>'
            + archive_html([])
            + ABOUT_HTML
        )
    with open(os.path.join(DOCS, "index.html"), "w") as f:
        f.write(page("TYT Fact Check — daily fact-check of The Young Turks", index_body))

    print("Built %d editions -> %s" % (len(editions), DOCS))


if __name__ == "__main__":
    build()
