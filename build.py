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
    meta["image"] = meta.get("image", "")  # valfri bild-URL, annars färgad platshållare
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
    cur = ' aria-current="page"'
    nav = f'<a href="/"{cur if path == "/" else ""}>Start</a>' + "".join(
        f'<a href="/kategori/{k}/"{cur if path == f"/kategori/{k}/" else ""}>{v}</a>' for k, v in CATEGORIES.items())
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
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
{extra_head}
</head>
<body>
<header class="masthead">
  <div class="wrap mast-top">
    <span>Nyheter · Tips · Guider</span>
    <a class="btn-sub" href="/rss.xml">Prenumerera</a>
  </div>
  <div class="wrap mast-brand">
    <a class="logo" href="/">Spel för två</a>
    <p class="mast-tag">{SITE['tagline']}</p>
  </div>
  <nav class="nav" aria-label="Kategorier"><div class="wrap nav-inner">{nav}</div></nav>
</header>
<main class="wrap">
{content}
</main>
<footer class="foot">
  <div class="wrap foot-inner">
    <div><a class="logo small" href="/">Spel för två</a>
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


def thumb(p):
    cat = CATEGORIES.get(p["category"], p["category"])
    if p.get("image"):
        return f'<div class="thumb"><img src="{esc(p["image"])}" alt="" loading="lazy"></div>'
    return f'<div class="thumb ph ph-{p["category"]}" aria-hidden="true"><span>{cat}</span></div>'


def card(p, kind="grid"):
    """kind: grid (bild + utdrag), side (bild utan utdrag), mini (lista med liten bild), feature (stor)."""
    cat = CATEGORIES.get(p["category"], p["category"])
    date = f'<time datetime="{p["date"]:%Y-%m-%d}">{sv_date(p["date"])}</time>'
    kicker = f'<span class="kicker k-{p["category"]}">{cat}</span>'
    h = "h2" if kind == "feature" else "h3"
    excerpt = f'<p>{esc(p.get("description", ""))}</p>' if kind in ("grid", "feature") else ""
    if kind == "mini":
        return f"""<article class="card mini"><a href="/{p['slug']}/" class="card-link">
  <div class="mini-text"><h3>{esc(p['title'])}</h3>{date}</div>{thumb(p)}</a></article>"""
    return f"""<article class="card card-{kind}"><a href="/{p['slug']}/" class="card-link">
  {thumb(p)}
  <div class="card-body">{kicker}<{h}>{esc(p['title'])}</{h}>{excerpt}<p class="meta">{date} · {p['reading']} min</p></div>
</a></article>"""


def section_head(title, href=None):
    more = f'<a class="more" href="{href}">Visa alla ›</a>' if href else ""
    return f'<div class="section-head"><h2>{title}</h2>{more}</div>'


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
  <header class="post-head">
    <nav class="crumbs"><a href="/">Start</a> › <a href="/kategori/{p['category']}/">{cat}</a></nav>
    <span class="kicker k-{p['category']}">{cat}</span>
    <h1>{esc(p['title'])}</h1>
    <p class="lead">{esc(p.get('description', ''))}</p>
    <p class="meta">Av redaktionen · <time datetime="{p['date']:%Y-%m-%d}">{sv_date(p['date'])}</time> · {p['reading']} min läsning</p>
  </header>
  <div class="post-hero">{thumb(p)}</div>
  {notice}
  <div class="prose">{p['html']}</div>
</article>
{'<section class="related">' + section_head('Läs också') + '<div class="grid">' + rel_html + '</div></section>' if related else ''}"""
        write(f"/{p['slug']}/", page(f"{p['title']} | {SITE['name']}", p.get("description", ""), f"/{p['slug']}/",
                                     content, f'<script type="application/ld+json">{schema}</script>'))

    # Startsida
    feature = card(posts[0], "feature") if posts else ""
    side = "".join(card(p, "side") for p in posts[1:3])
    latest = posts[3:8]
    if latest:
        right = '<h2 class="rail-title">Senaste</h2>' + "".join(card(p, "mini") for p in latest)
    else:  # få artiklar ännu: visa kategorierna i högerspalten
        counts = {k: sum(p["category"] == k for p in posts) for k in CATEGORIES}
        right = '<h2 class="rail-title">Kategorier</h2><ul class="cat-list">' + "".join(
            f'<li><a href="/kategori/{k}/"><span class="dot k-{k}"></span>{v}<span class="count">{counts[k]}</span></a></li>'
            for k, v in CATEGORIES.items()) + "</ul>"
    sections = ""
    for k, v in CATEGORIES.items():
        items = [p for p in posts if p["category"] == k][:4]
        if items:
            sections += f'<section class="cat-section">{section_head(v, f"/kategori/{k}/")}<div class="grid">{"".join(card(p) for p in items)}</div></section>'
    home = f"""<h1 class="sr-only">{SITE['name']} – nyheter, tips och guider om spel för två</h1>
<section class="top-stories">
  <div class="col-side">{side}</div>
  <div class="col-feature">{feature}</div>
  <aside class="col-rail">{right}</aside>
</section>
{sections}"""
    write("/", page(f"{SITE['name']} – nyheter, tips och guider om spel för två", SITE["tagline"], "/", home))

    # Kategorier
    for k, v in CATEGORIES.items():
        items = [p for p in posts if p["category"] == k]
        body = "".join(card(p) for p in items) or '<p class="empty">Inga artiklar ännu – snart här!</p>'
        write(f"/kategori/{k}/", page(f"{v} | {SITE['name']}", f"Allt om {v.lower()} för två spelare.",
                                      f"/kategori/{k}/", f'<div class="section-head page-head"><h1>{v}</h1></div><div class="grid">{body}</div>'))

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
