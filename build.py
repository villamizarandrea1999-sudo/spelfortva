#!/usr/bin/env python3
"""Bygger spelfortva.com: content/posts/*.md -> dist/ (startsida, kategorier, artiklar, RSS, sitemap)."""
import html, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path
import markdown

SITE = {
    "name": "Spel för två",
    "url": "https://spelfortva.com",
    "tagline": "Nyheter, tips och guider om spel för två – digitalt och på bordet.",
    "lang": "sv",
}
CATEGORIES = {
    "nyheter": "Nyheter",
    "co-op": "Co-op & konsol",
    "sallskapsspel": "Sällskapsspel",
    "mobil": "Mobil & online",
    "erbjudanden": "Erbjudanden",
    "guider": "Guider",
}
ROOT = Path(__file__).parent
DIST = ROOT / "dist"
MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli",
          "augusti", "september", "oktober", "november", "december"]


def parse(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    meta, body = {}, raw
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
        body = m.group(2)
    meta["slug"] = meta.get("slug") or path.stem
    meta["date"] = datetime.strptime(meta.get("date", "2026-01-01"), "%Y-%m-%d")
    meta["category"] = meta.get("category", "nyheter")
    meta["sponsored"] = meta.get("sponsored", "false").lower() == "true"
    md = markdown.Markdown(extensions=["extra", "toc"])
    body_html = md.convert(body)
    # Sponsrade inlägg: alla externa länkar får rel="sponsored noopener"
    if meta["sponsored"]:
        body_html = re.sub(r'<a href="(https?://(?!spelfortva\.com)[^"]+)"',
                           r'<a href="\1" rel="sponsored noopener" target="_blank"', body_html)
    meta["html"] = body_html
    meta["reading"] = max(1, len(re.sub("<[^>]+>", "", body_html).split()) // 200)
    return meta


def sv_date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def esc(s):
    return html.escape(s, quote=True)


def page(title, description, path, content, extra_head=""):
    canonical = SITE["url"] + path
    nav = "".join(f'<a href="/kategori/{k}/">{v}</a>' for k, v in CATEGORIES.items())
    year = datetime.now().year
    return f"""<!doctype html>
<html lang="{SITE['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="sv_SE">
<meta property="og:site_name" content="{SITE['name']}">
<link rel="alternate" type="application/rss+xml" title="{SITE['name']}" href="/rss.xml">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
{extra_head}
</head>
<body>
<header class="top">
  <div class="wrap top-inner">
    <a class="logo" href="/"><span class="dice">⚄⚂</span> Spel<span>för</span>två</a>
    <nav class="nav">{nav}</nav>
  </div>
</header>
<main class="wrap">
{content}
</main>
<footer class="foot">
  <div class="wrap foot-inner">
    <div><a class="logo small" href="/"><span class="dice">⚄⚂</span> Spel<span>för</span>två</a>
    <p>{SITE['tagline']}</p></div>
    <div class="foot-links">
      <a href="/om-oss/">Om oss</a><a href="/skriv-for-oss/">Skriv för oss</a>
      <a href="/kontakt/">Kontakt</a><a href="/integritetspolicy/">Integritetspolicy</a>
      <a href="/rss.xml">RSS</a>
    </div>
  </div>
  <p class="wrap copy">© {year} {SITE['name']}</p>
</footer>
</body>
</html>"""


def card(p, big=False):
    cat = CATEGORIES.get(p["category"], p["category"])
    return f"""<article class="card{' big' if big else ''}">
  <a href="/{p['slug']}/" class="card-link">
    <span class="tag tag-{p['category']}">{cat}</span>
    <h{2 if big else 3}>{esc(p['title'])}</h{2 if big else 3}>
    <p>{esc(p.get('description', ''))}</p>
    <time datetime="{p['date']:%Y-%m-%d}">{sv_date(p['date'])}</time>
  </a>
</article>"""


def write(path, text):
    out = DIST / path.strip("/") / "index.html" if not path.endswith((".xml", ".txt", ".html")) else DIST / path.strip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    for f in (ROOT / "static").iterdir():
        shutil.copy(f, DIST / f.name)

    posts = sorted((parse(p) for p in (ROOT / "content/posts").glob("*.md")),
                   key=lambda p: p["date"], reverse=True)
    today = datetime.now()
    posts = [p for p in posts if p["date"] <= today]  # framtida datum publiceras automatiskt senare

    # Artiklar
    for i, p in enumerate(posts):
        cat = CATEGORIES.get(p["category"], p["category"])
        related = [q for q in posts if q["category"] == p["category"] and q is not p][:3]
        rel_html = "".join(card(q) for q in related)
        notice = '<p class="sponsored-note">Samarbete: Detta inlägg innehåller sponsrade länkar.</p>' if p["sponsored"] else ""
        schema = json.dumps({
            "@context": "https://schema.org", "@type": "NewsArticle" if p["category"] == "nyheter" else "Article",
            "headline": p["title"], "description": p.get("description", ""),
            "datePublished": f"{p['date']:%Y-%m-%d}", "inLanguage": "sv-SE",
            "author": {"@type": "Organization", "name": SITE["name"]},
            "publisher": {"@type": "Organization", "name": SITE["name"]},
            "mainEntityOfPage": f"{SITE['url']}/{p['slug']}/",
        }, ensure_ascii=False)
        content = f"""<article class="post">
  <nav class="crumbs"><a href="/">Start</a> › <a href="/kategori/{p['category']}/">{cat}</a></nav>
  <span class="tag tag-{p['category']}">{cat}</span>
  <h1>{esc(p['title'])}</h1>
  <p class="lead">{esc(p.get('description', ''))}</p>
  <p class="meta"><time datetime="{p['date']:%Y-%m-%d}">{sv_date(p['date'])}</time> · {p['reading']} min läsning</p>
  {notice}
  <div class="prose">{p['html']}</div>
</article>
{'<section class="related"><h2>Läs också</h2><div class="grid">' + rel_html + '</div></section>' if related else ''}"""
        write(f"/{p['slug']}/", page(f"{p['title']} | {SITE['name']}", p.get("description", ""), f"/{p['slug']}/",
                                     content, f'<script type="application/ld+json">{schema}</script>'))

    # Startsida
    hero = card(posts[0], big=True) if posts else ""
    latest = "".join(card(p) for p in posts[1:13])
    cats = "".join(f'<a class="cat-pill tag-{k}" href="/kategori/{k}/">{v}</a>' for k, v in CATEGORIES.items())
    home = f"""<section class="hero">
  <div class="hero-text">
    <h1>Spel för två – <em>bättre tillsammans</em></h1>
    <p>{SITE['tagline']} Vi testar co-op-spel, sällskapsspel och appar som är gjorda för två spelare.</p>
    <div class="pills">{cats}</div>
  </div>
  {hero}
</section>
<section><h2 class="section-title">Senaste</h2><div class="grid">{latest}</div></section>"""
    write("/", page(f"{SITE['name']} – nyheter, tips och guider om spel för två", SITE["tagline"], "/", home))

    # Kategorier
    for k, v in CATEGORIES.items():
        items = [p for p in posts if p["category"] == k]
        body = "".join(card(p) for p in items) or '<p class="empty">Inga artiklar ännu – snart här!</p>'
        write(f"/kategori/{k}/", page(f"{v} | {SITE['name']}", f"Allt om {v.lower()} för två spelare.",
                                      f"/kategori/{k}/", f'<h1 class="page-title">{v}</h1><div class="grid">{body}</div>'))

    # Statiska sidor
    for f in sorted((ROOT / "content/pages").glob("*.md")):
        p = parse(f)
        write(f"/{p['slug']}/", page(f"{p['title']} | {SITE['name']}", p.get("description", ""), f"/{p['slug']}/",
                                     f'<article class="post"><h1>{esc(p["title"])}</h1><div class="prose">{p["html"]}</div></article>'))

    # 404
    (DIST / "404.html").write_text(page("Sidan finns inte | " + SITE["name"], "Sidan hittades inte.", "/404.html",
        '<div class="post"><h1>Hoppsan! Sidan finns inte.</h1><p><a href="/">Tillbaka till startsidan</a></p></div>'), encoding="utf-8")

    # RSS
    items = "".join(f"""<item><title>{esc(p['title'])}</title><link>{SITE['url']}/{p['slug']}/</link>
<guid>{SITE['url']}/{p['slug']}/</guid><pubDate>{p['date'].replace(tzinfo=timezone.utc):%a, %d %b %Y 08:00:00 +0000}</pubDate>
<description>{esc(p.get('description', ''))}</description></item>""" for p in posts[:30])
    write("/rss.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{SITE['name']}</title><link>{SITE['url']}</link>
<description>{SITE['tagline']}</description><language>sv-SE</language>{items}</channel></rss>""")

    # Sitemap
    urls = ["/"] + [f"/kategori/{k}/" for k in CATEGORIES] + [f"/{p['slug']}/" for p in posts] + \
           [f"/{parse(f)['slug']}/" for f in (ROOT / "content/pages").glob("*.md")]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{SITE['url']}{u}</loc></url>" for u in urls) + "</urlset>")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\n")
    print(f"Byggt: {len(posts)} artiklar -> {DIST}")


if __name__ == "__main__":
    build()
