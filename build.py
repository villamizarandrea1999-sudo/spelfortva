#!/usr/bin/env python3
"""Bygger spelfortva.com: content/posts/*.md -> dist/ (startsida, kategorier, artiklar, RSS, sitemap)."""
import html, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path
import markdown

SITE = {
    "name": "Spel för två",
    "url": "https://spelfortva.com",
    "tagline": "Vi hjälper er att hitta rätt spel för två – brädspel, kortspel, co-op och mobilspel.",
    "lang": "sv",
}
# Ordningen här styr menyn
CATEGORIES = {
    "bradspel": "Brädspel & kortspel",
    "konsol": "Konsol & PC",
    "mobil": "Mobil & online",
    "par": "För par",
    "guider": "Guider",
    "nyheter": "Nyheter",
}
# Gamla kategoriadresser som redan kan vara indexerade -> ny adress
OLD_CATEGORY_REDIRECTS = {
    "co-op": "/kategori/konsol/",
    "sallskapsspel": "/kategori/bradspel/",
    "erbjudanden": "/",
}
# Standardfoton per kategori (Unsplash, fri licens) när en artikel saknar egen `image:`
UNSPLASH = "https://images.unsplash.com/photo-"
CAT_IMAGES = {
    "bradspel": "1763875067516-e947790c74ac",
    "konsol": "1509198397868-475647b2a1e5",
    "mobil": "1564049489314-60d154ff107d",
    "par": "1629760946220-5693ee4c46ac",
    "guider": "1585504198199-20277593b94f",
    "nyheter": "1769288361820-898812b71482",
}
ROOT = Path(__file__).parent
DIST = ROOT / "dist"
MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli",
          "augusti", "september", "oktober", "november", "december"]
MAX_DESC = 155
WARNINGS = []


def sv_date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def esc(s):
    return html.escape(s or "", quote=True)


# ---------- Spelrutor ----------
# I Markdown:
# :::spel
# namn: 7 Wonders Duel
# spelare: 2
# speltid: 30 min
# alder: 10+
# passar: Er som gillar strategi
# omdome: Kort omdöme.
# lank: https://... (affiliate-länk; lämna tom eller TODO tills den finns)
# bild: (valfritt) Unsplash-id eller URL
# :::
GAME_RE = re.compile(r"^:::spel[ \t]*\n(.*?)\n:::[ \t]*$", re.M | re.S)


def game_box(m, slug):
    f = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            f[k.strip().lower()] = v.strip()
    name = f.get("namn", "")
    facts = [("Spelare", f.get("spelare")), ("Speltid", f.get("speltid")), ("Ålder", f.get("alder") or f.get("ålder"))]
    facts_html = "".join(f"<div><dt>{k}</dt><dd>{esc(v)}</dd></div>" for k, v in facts if v)
    link = f.get("lank") or f.get("länk") or ""
    if not link or link.upper() == "TODO":
        WARNINGS.append(f"{slug}: spelrutan '{name}' saknar köplänk (lank: TODO)")
        button = '<a class="btn-price is-todo" href="#" aria-disabled="true">Se pris</a>'
    else:
        button = f'<a class="btn-price" href="{esc(link)}" rel="sponsored nofollow noopener" target="_blank">Se pris</a>'
    img = f.get("bild", "")
    img_html = ""
    if img:
        src = img if img.startswith(("http", "/")) else f"{UNSPLASH}{img}?auto=format&fit=crop&w=400&q=75"
        img_html = f'<div class="gb-img"><img src="{esc(src)}" alt="{esc(name)}" loading="lazy"></div>'
    suits = f'<p class="gb-suits"><strong>Passar för:</strong> {esc(f["passar"])}</p>' if f.get("passar") else ""
    verdict = f'<p class="gb-verdict"><strong>Vårt omdöme:</strong> {esc(f["omdome"])}</p>' if f.get("omdome") else ""
    # Hela rutan på en rad, så att Markdown lämnar den orörd
    return ("\n\n" + f'<aside class="game-box{" has-img" if img_html else ""}">{img_html}<div class="gb-main">'
            f'<p class="gb-label">Spelfakta</p><p class="gb-name">{esc(name)}</p>'
            f'<dl class="gb-facts">{facts_html}</dl>{suits}{verdict}{button}</div></aside>' + "\n\n")


# ---------- Inläsning ----------
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
    meta["image"] = meta.get("image", "")
    body = GAME_RE.sub(lambda mm: game_box(mm, meta["slug"]), body)
    md = markdown.Markdown(extensions=["extra", "toc"], extension_configs={"toc": {"slugify": slugify}})
    body_html = md.convert(body)
    # Sponsrade inlägg: alla externa länkar får rel="sponsored noopener"
    if meta["sponsored"]:
        body_html = re.sub(r'<a href="(https?://(?!spelfortva\.com)[^"]+)"(?! rel=)',
                           r'<a href="\1" rel="sponsored noopener" target="_blank"', body_html)
    meta["html"] = body_html
    meta["toc"] = [t for t in md.toc_tokens if t["level"] == 2] or \
                  [c for t in md.toc_tokens for c in t.get("children", []) if c["level"] == 2]
    meta["words"] = len(re.sub("<[^>]+>", " ", body_html).split())
    meta["reading"] = max(1, meta["words"] // 200)
    desc = meta.get("description", "")
    if len(desc) > MAX_DESC:
        WARNINGS.append(f"{meta['slug']}: description är {len(desc)} tecken (max {MAX_DESC})")
    if path.parent.name == "posts" and meta["category"] not in CATEGORIES:
        WARNINGS.append(f"{meta['slug']}: okänd kategori '{meta['category']}'")
    return meta


def slugify(value, separator="-"):
    value = value.lower()
    for a, b in (("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e"), ("ü", "u")):
        value = value.replace(a, b)
    return re.sub(r"[^a-z0-9]+", separator, value).strip(separator)


# ---------- Mallar ----------
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
<meta name="google-site-verification" content="Zprru_ZR1gODB0m-LE_dF5SMq6rU0swovOLRqRPxP6Y">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="sv_SE">
<meta property="og:site_name" content="{SITE['name']}">
<link rel="alternate" type="application/rss+xml" title="{SITE['name']}" href="/rss.xml">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
{extra_head}
</head>
<body>
<header class="masthead">
  <div class="wrap mast-top">
    <a class="btn-sub" href="/rss.xml">Prenumerera</a>
  </div>
  <div class="wrap mast-brand">
    <a class="logo" href="/">Spel för två</a>
    <p class="mast-tag"><span class="orn">~</span> Brädspel / Kortspel / Co-op / Mobil <span class="orn">~</span></p>
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
  <p class="wrap copy">© {year} {SITE['name']} · Foton: <a href="https://unsplash.com/" rel="noopener">Unsplash</a></p>
</footer>
</body>
</html>"""


def redirect_page(target):
    url = SITE["url"] + target
    return f"""<!doctype html><html lang="sv"><head><meta charset="utf-8"><title>Flyttad</title>
<link rel="canonical" href="{url}"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={target}">
</head><body><p>Sidan har flyttat: <a href="{target}">{url}</a></p></body></html>"""


def image_url(p, w=800):
    img = p.get("image") or CAT_IMAGES.get(p["category"], "")
    if not img:
        return ""
    if img.startswith(("http", "/")):
        return img
    return f"{UNSPLASH}{img}?auto=format&fit=crop&w={w}&q=75"


def thumb(p, w=800, eager=False):
    url = image_url(p, w)
    if not url:
        return f'<div class="thumb ph" aria-hidden="true"><span>{esc(CATEGORIES.get(p["category"], ""))}</span></div>'
    lazy = "" if eager else ' loading="lazy"'
    return f'<div class="thumb"><img src="{esc(url)}" alt="{esc(p["title"])}"{lazy}></div>'


def tag(p):
    return f'<span class="tag t-{p["category"]}">{esc(CATEGORIES.get(p["category"], p["category"]))}</span>'


def card(p, kind="grid"):
    """kind: grid (standardkort) eller feature (stort utvalt kort på startsidan)."""
    date = f'<time datetime="{p["date"]:%Y-%m-%d}">{sv_date(p["date"])}</time>'
    h = "h2" if kind == "feature" else "h3"
    w = 1400 if kind == "feature" else 800
    return f"""<article class="card card-{kind}"><a href="/{p['slug']}/" class="card-link">
  {thumb(p, w, eager=kind == "feature")}
  <div class="card-body">{tag(p)}<{h}>{esc(p['title'])}</{h}><p class="excerpt">{esc(p.get('description', ''))}</p><p class="meta">{date} · {p['reading']} min läsning</p></div>
</a></article>"""


def sidebar(posts, current=None):
    latest = [q for q in posts if q is not current][:5]
    items = "".join(f"""<li><a href="/{q['slug']}/"><span class="num">{i}.</span>
  <span class="pop-text"><strong>{esc(q['title'])}</strong><time datetime="{q['date']:%Y-%m-%d}">{sv_date(q['date'])}</time></span>
  {thumb(q, 240)}</a></li>""" for i, q in enumerate(latest, 1))
    counts = {k: sum(q["category"] == k for q in posts) for k in CATEGORIES}
    cats = "".join(f'<li><a href="/kategori/{k}/"><span class="dot t-{k}"></span>{v}<span class="count">{counts[k]}</span></a></li>'
                   for k, v in CATEGORIES.items())
    pop = f'<div class="widget"><h2 class="widget-title">Senaste artiklar</h2><ol class="pop">{items}</ol></div>' if latest else ""
    return f"""<aside class="sidebar">{pop}
  <div class="widget"><h2 class="widget-title">Kategorier</h2><ul class="cat-list">{cats}</ul></div>
  <div class="widget widget-about"><h2 class="widget-title">Om sajten</h2>
    <p>Vi jämför spel för två och berättar vem varje spel passar för – så att ni slipper chansa i butiken.</p>
    <a class="btn-sub" href="/om-oss/">Läs mer om oss</a></div>
</aside>"""


def toc_html(p):
    if len(p["toc"]) < 4:  # innehållsförteckning bara för längre artiklar
        return ""
    # Listan numreras själv, så ta bort "1. " i rubriker som redan är numrerade
    names = [re.sub(r"^\d+\.\s*", "", html.unescape(t["name"])) for t in p["toc"]]
    items = "".join(f'<li><a href="#{t["id"]}">{esc(n)}</a></li>' for t, n in zip(p["toc"], names))
    return f'<details class="toc" open><summary>Innehåll</summary><ol>{items}</ol></details>'


def section_head(title, href=None):
    more = f'<a class="more" href="{href}">Visa alla ›</a>' if href else ""
    return f'<div class="section-head"><h2>{title}</h2>{more}</div>'


def write(path, text):
    out = DIST / path.strip("/") / "index.html" if not path.endswith((".xml", ".txt", ".html")) else DIST / path.strip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


# ---------- Bygge ----------
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
    for p in posts:
        cat = CATEGORIES.get(p["category"], p["category"])
        same = [q for q in posts if q["category"] == p["category"] and q is not p]
        related = (same + [q for q in posts if q is not p and q not in same])[:3]
        notice = '<p class="sponsored-note">Samarbete: Detta inlägg innehåller sponsrade länkar.</p>' if p["sponsored"] else ""
        schema = json.dumps({
            "@context": "https://schema.org", "@type": "NewsArticle" if p["category"] == "nyheter" else "Article",
            "headline": p["title"], "description": p.get("description", ""),
            "image": image_url(p, 1200), "datePublished": f"{p['date']:%Y-%m-%d}", "inLanguage": "sv-SE",
            "author": {"@type": "Organization", "name": SITE["name"]},
            "publisher": {"@type": "Organization", "name": SITE["name"]},
            "mainEntityOfPage": f"{SITE['url']}/{p['slug']}/",
        }, ensure_ascii=False)
        content = f"""<nav class="crumbs" aria-label="Brödsmulor"><a href="/">Start</a> / <a href="/kategori/{p['category']}/">{cat}</a> / <span>{esc(p['title'])}</span></nav>
<div class="post-layout">
<article class="post">
  <header class="post-head">
    <a class="tag t-{p['category']}" href="/kategori/{p['category']}/">{cat}</a>
    <h1>{esc(p['title'])}</h1>
    <p class="lead">{esc(p.get('description', ''))}</p>
    <p class="meta"><span>Av redaktionen</span><time datetime="{p['date']:%Y-%m-%d}">{sv_date(p['date'])}</time><span>{p['reading']} min läsning</span></p>
  </header>
  <div class="post-hero">{thumb(p, 1400, eager=True)}</div>
  {notice}
  {toc_html(p)}
  <div class="prose">{p['html']}</div>
  <footer class="post-foot"><span>Kategori:</span> <a href="/kategori/{p['category']}/">{cat}</a></footer>
</article>
{sidebar(posts, p)}
</div>
{'<section class="related">' + section_head('Läs också') + '<div class="grid grid-3">' + "".join(card(q) for q in related) + '</div></section>' if related else ''}"""
        write(f"/{p['slug']}/", page(f"{p['title']} | {SITE['name']}", p.get("description", ""), f"/{p['slug']}/",
                                     content, f'<meta property="og:image" content="{esc(image_url(p, 1200))}">\n'
                                     f'<script type="application/ld+json">{schema}</script>'))

    # Startsida: ett utvalt inlägg + rutnät med senaste
    featured = next((p for p in posts if p["slug"] == "spel-for-tva"), posts[0] if posts else None)
    rest = [p for p in posts if p is not featured]
    sections = ""
    for k, v in CATEGORIES.items():
        items = [p for p in posts if p["category"] == k][:3]
        if len(items) >= 3:  # kategorisektioner först när det finns tillräckligt att fylla dem
            sections += f'<section class="cat-section">{section_head(v, f"/kategori/{k}/")}<div class="grid grid-3">{"".join(card(p) for p in items)}</div></section>'
    home = f"""<h1 class="sr-only">{SITE['name']} – guider och tips om spel för två spelare</h1>
<section class="featured">{card(featured, "feature") if featured else ""}</section>
{'<section>' + section_head("Senaste artiklar") + '<div class="grid grid-3">' + "".join(card(p) for p in rest[:12]) + '</div></section>' if rest else ''}
{sections}"""
    write("/", page(f"{SITE['name']} – guider och tips om spel för två spelare", SITE["tagline"], "/", home))

    # Kategorier
    for k, v in CATEGORIES.items():
        items = [p for p in posts if p["category"] == k]
        body = "".join(card(p) for p in items) or '<p class="empty">Inga artiklar ännu – snart här!</p>'
        write(f"/kategori/{k}/", page(f"{v} | {SITE['name']}", f"Guider och tips om {v.lower()} för två spelare.",
                                      f"/kategori/{k}/", f'<div class="section-head page-head"><h1>{v}</h1></div><div class="grid grid-3">{body}</div>'))
    for old, target in OLD_CATEGORY_REDIRECTS.items():
        write(f"/kategori/{old}/", redirect_page(target))

    # Statiska sidor
    pages = [parse(f) for f in sorted((ROOT / "content/pages").glob("*.md"))]
    for p in pages:
        write(f"/{p['slug']}/", page(f"{p['title']} | {SITE['name']}", p.get("description", ""), f"/{p['slug']}/",
                                     f'<article class="post page"><h1>{esc(p["title"])}</h1><div class="prose">{p["html"]}</div></article>'))

    # 404
    (DIST / "404.html").write_text(page("Sidan finns inte | " + SITE["name"], "Sidan hittades inte.", "/404.html",
        '<div class="post page"><h1>Hoppsan! Sidan finns inte.</h1><p><a href="/">Tillbaka till startsidan</a></p></div>'), encoding="utf-8")

    # RSS
    items = "".join(f"""<item><title>{esc(p['title'])}</title><link>{SITE['url']}/{p['slug']}/</link>
<guid>{SITE['url']}/{p['slug']}/</guid><pubDate>{p['date'].replace(tzinfo=timezone.utc):%a, %d %b %Y 08:00:00 +0000}</pubDate>
<description>{esc(p.get('description', ''))}</description></item>""" for p in posts[:30])
    write("/rss.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{SITE['name']}</title><link>{SITE['url']}</link>
<description>{SITE['tagline']}</description><language>sv-SE</language>{items}</channel></rss>""")

    # Sitemap (utan omdirigeringar)
    urls = ["/"] + [f"/kategori/{k}/" for k in CATEGORIES] + [f"/{p['slug']}/" for p in posts] + [f"/{p['slug']}/" for p in pages]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{SITE['url']}{u}</loc></url>" for u in urls) + "</urlset>")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\n")

    print(f"Byggt: {len(posts)} artiklar -> {DIST}")
    for w in WARNINGS:
        print("  VARNING:", w)


if __name__ == "__main__":
    build()
