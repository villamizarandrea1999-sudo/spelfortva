#!/usr/bin/env python3
"""Bygger spelfortva.com: content/posts/*.md -> dist/ (startsida, kategorier, artiklar, RSS, sitemap)."""
import hashlib
import html, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path
import markdown

SITE = {
    "name": "Spel för två",
    "url": "https://spelfortva.com",
    "tagline": "Vi hjälper er att hitta rätt spel för två – brädspel, kortspel, co-op och mobilspel.",
    # Namngiven skribent: fyll i när ni har en riktig person, t.ex.
    # {"name": "För Efternamn", "bio": "Kort bio …", "url": "/om-oss/"}. Så länge det är None används redaktionen.
    "author": None,
    "home_description": "Guider till spel för två: brädspel, kortspel, konsolspel och appar för par, vänner och syskon – topplistor, julklappstips och co-op.",
    "lang": "sv-SE",       # svenska, riktad mot Sverige
    "country": "SE",
    # Google Analytics 4: byt ut mot ert riktiga mät-ID. Så länge det står XXXXXXX laddas ingen spårning.
    "ga_id": "G-XXXXXXX",
}
ACTIVE_CATS = set()  # kategorier med minst en publicerad artikel (sätts i build())
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
MISSING_LINKS = {}  # artikel -> spelrutor utan köplänk


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
    facts = [("Spelare", f.get("spelare")), ("Speltid", f.get("speltid")), ("Ålder", f.get("alder") or f.get("ålder")),
             ("Nivå", f.get("niva") or f.get("nivå")), ("Delad skärm", f.get("delad")), ("Online", f.get("online")),
             ("Friend's Pass", f.get("friendspass"))]
    facts_html = "".join(f"<div><dt>{k}</dt><dd>{esc(v)}</dd></div>" for k, v in facts if v)
    link = f.get("lank") or f.get("länk") or ""
    if not link or link.upper() == "TODO":
        MISSING_LINKS.setdefault(slug, []).append(name)
        button = ""  # ingen köplänk än: visa ingen knapp alls (hellre ingen knapp än en död länk)
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
    # Valfritt: updated: YYYY-MM-DD när en artikel skrivits om (visas i artikeln, sitemap och schema)
    meta["updated"] = datetime.strptime(meta["updated"], "%Y-%m-%d") if meta.get("updated") else meta["date"]
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
# Logga: två spelkort (samma som favicon) bredvid textloggan "SPEL FÖR TVÅ"
LOGO_ICON = """<svg class="logo-icon" viewBox="0 0 62 60" aria-hidden="true"><g transform="rotate(-14 22 34)"><rect x="6" y="10" width="30" height="42" rx="4" fill="#2f7a52"/><rect x="10" y="14" width="22" height="34" rx="2" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width="1.5"/></g><g transform="rotate(10 38 30)"><rect x="22" y="6" width="30" height="42" rx="4" fill="#fff" stroke="#1f1b16" stroke-width="2.5"/><text x="27" y="22" font-family="Playfair Display,Georgia,serif" font-weight="700" font-size="13" fill="#b4532a">2</text><path d="M37 33c-3-3.5-7-1-5 2.5l5 5 5-5c2-3.5-2-6-5-2.5z" fill="#b4532a"/></g></svg>"""


def logo(cls="logo"):
    return f'<a class="{cls}" href="/">{LOGO_ICON}<span>Spel för två</span></a>'


def ga_tag():
    gid = SITE["ga_id"]
    if "XXXX" in gid:
        return "<!-- GA4: sätt SITE['ga_id'] i build.py till ert mät-ID (G-...) så läggs taggen in här -->"
    return f"""<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{gid}');</script>"""


# Versionsnummer för style.css: ändras när filen ändras, så att webbläsare hämtar den nya versionen direkt
CSS_VER = hashlib.md5((ROOT / "static" / "style.css").read_bytes()).hexdigest()[:8]


def page(title, description, path, content, extra_head="", compact=False):
    canonical = SITE["url"] + path
    cur = ' aria-current="page"'
    nav = f'<a href="/"{cur if path == "/" else ""}>Start</a>' + "".join(
        f'<a href="/kategori/{k}/"{cur if path == f"/kategori/{k}/" else ""}>{v}</a>'
        for k, v in CATEGORIES.items() if k in ACTIVE_CATS)
    year = datetime.now().year
    return f"""<!doctype html>
<html lang="{SITE['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<!-- Språk och marknad: svenska (sv-SE), riktat mot Sverige -->
<link rel="alternate" hreflang="sv-SE" href="{canonical}">
<link rel="alternate" hreflang="x-default" href="{canonical}">
<meta http-equiv="content-language" content="sv-SE">
<meta name="geo.region" content="SE">
<meta name="geo.placename" content="Sverige">
<meta name="google-site-verification" content="Zprru_ZR1gODB0m-LE_dF5SMq6rU0swovOLRqRPxP6Y">
<meta name="google-site-verification" content="I1RhgXVY6W6usKxYv5zp2bj4XfguUQC7Zv__YNJBrbc">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="sv_SE">
<meta property="og:site_name" content="{SITE['name']}">
<link rel="alternate" type="application/rss+xml" title="{SITE['name']}" href="/rss.xml">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<!-- Typsnitten laddas utan att blockera renderingen -->
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" media="print" onload="this.media='all'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap"></noscript>
<link rel="stylesheet" href="/style.css?v={CSS_VER}">
{ga_tag()}
{extra_head}
</head>
<body>
<header class="masthead{' compact' if compact else ''}">
  {'' if compact else '<div class="wrap mast-top"><a class="btn-sub" href="/kontakt/">Prenumerera</a></div>'}
  <div class="wrap mast-brand">
    {logo()}
    {'' if compact else '<p class="mast-tag"><span class="orn">~</span> Brädspel / Kortspel / Co-op / Mobil <span class="orn">~</span></p>'}
  </div>
</header>
<nav class="nav{' compact' if compact else ''}" aria-label="Kategorier"><div class="wrap nav-inner">{nav}</div></nav>
<main class="wrap">
{content}
</main>
<footer class="foot">
  <div class="wrap foot-inner">
    <div>{logo("logo small")}
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
    if img.startswith("http"):
        return img
    if img.startswith("/"):
        return SITE["url"] + img  # lokal bild (t.ex. /img/...) – absolut för og:image och schema
    return f"{UNSPLASH}{img}?auto=format&fit=crop&w={w}&q=75"


def thumb(p, w=800, eager=False):
    url = image_url(p, w)
    if url.startswith(SITE["url"] + "/"):
        url = url[len(SITE["url"]):]  # egna bilder: relativ sökväg på sidan (absolut bara i og:image/schema)
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
    # Utvalt kort på startsidan kan ha en egen rubrik (home_title) så att den inte upprepar artikelns titel
    heading = p.get("home_title") if kind == "feature" and p.get("home_title") else p["title"]
    return f"""<article class="card card-{kind}"><a href="/{p['slug']}/" class="card-link">
  {thumb(p, w, eager=kind == "feature")}
  <div class="card-body">{tag(p)}<{h}>{esc(heading)}</{h}><p class="excerpt">{esc(p.get('description', ''))}</p><p class="meta">{date} · {p['reading']} min läsning</p></div>
</a></article>"""


POPULAR = ["spel-for-tva", "sanka-skepp", "kortspel-for-tva"]  # handplockade guider i sidopanelen


def sidebar(posts, current=None):
    by_slug = {q["slug"]: q for q in posts}
    popular = [by_slug[s] for s in POPULAR if s in by_slug and by_slug[s] is not current]
    pop_list = "".join(f'<li><a href="/{q["slug"]}/">{esc(q.get("crumb") or q["title"])}</a></li>' for q in popular)
    popular_html = f'<div class="widget"><h2 class="widget-title">Populära guider</h2><ul class="cat-list">{pop_list}</ul></div>' if popular else ""
    latest = [q for q in posts if q is not current][:5]
    items = "".join(f"""<li><a href="/{q['slug']}/"><span class="num">{i}.</span>
  <span class="pop-text"><strong>{esc(q['title'])}</strong><time datetime="{q['date']:%Y-%m-%d}">{sv_date(q['date'])}</time></span>
  {thumb(q, 240)}</a></li>""" for i, q in enumerate(latest, 1))
    counts = {k: sum(q["category"] == k for q in posts) for k in CATEGORIES}
    cats = "".join(f'<li><a href="/kategori/{k}/"><span class="dot t-{k}"></span>{v}<span class="count">{counts[k]}</span></a></li>'
                   for k, v in CATEGORIES.items() if k in ACTIVE_CATS)
    pop = f'<div class="widget"><h2 class="widget-title">Senaste artiklar</h2><ol class="pop">{items}</ol></div>' if latest else ""
    return f"""<aside class="sidebar">{popular_html}{pop}
  <div class="widget"><h2 class="widget-title">Kategorier</h2><ul class="cat-list">{cats}</ul></div>
  <div class="widget widget-about"><h2 class="widget-title">Om sajten</h2>
    <p>Vi jämför spel för två och berättar vem varje spel passar för – så att ni slipper chansa i butiken.</p>
    <a class="btn-sub" href="/om-oss/">Läs mer om oss</a></div>
</aside>"""


def author_name():
    return SITE["author"]["name"] if SITE.get("author") else "redaktionen"


def author_schema():
    a = SITE.get("author")
    if a:
        return {"@type": "Person", "name": a["name"], "url": SITE["url"] + a.get("url", "/om-oss/")}
    return {"@type": "Organization", "name": SITE["name"]}


def author_box():
    a = SITE.get("author")
    if a:
        initials = "".join(w[0] for w in a["name"].split()[:2]).upper()
        return f"""<aside class="author-box">
  <div class="author-avatar" aria-hidden="true">{esc(initials)}</div>
  <div><p class="author-name">Skrivet av {esc(a['name'])}</p>
  <p>{esc(a['bio'])} <a href="{esc(a.get('url', '/om-oss/'))}">Läs mer om oss och hur vi väljer spel</a>.</p></div>
</aside>"""
    return """<aside class="author-box">
  <div class="author-avatar" aria-hidden="true">SFT</div>
  <div><p class="author-name">Skrivet av Spel för två-redaktionen</p>
  <p>Vi jämför brädspel, kortspel, konsolspel och appar för två spelare och berättar vem varje spel passar för.
  <a href="/om-oss/">Läs mer om oss och hur vi väljer spel</a>.</p></div>
</aside>"""


def page_title(title):
    """Lägg till sajtnamnet bara om hela titeln ryms inom ~60 tecken (det Google visar)."""
    full = f"{title} | {SITE['name']}"
    return full if len(full) <= 60 else title


def faq_schema(p):
    """FAQPage-schema från avsnittet 'Vanliga frågor …': varje H3 = fråga, första stycket efter = svar."""
    m = re.search(r'<h2[^>]*>\s*Vanliga frågor.*?</h2>(.*?)(?=<h2|\Z)', p["html"], re.S)
    if not m:
        return ""
    items = []
    for q, rest in re.findall(r'<h3[^>]*>(.*?)</h3>(.*?)(?=<h3|\Z)', m.group(1), re.S):
        a = re.search(r'<p>(.*?)</p>', rest, re.S)
        if not a:
            continue
        text = lambda s: " ".join(html.unescape(re.sub("<[^>]+>", "", s)).split())
        items.append({"@type": "Question", "name": text(q),
                      "acceptedAnswer": {"@type": "Answer", "text": text(a.group(1))}})
    if not items:
        return ""
    data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items}
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


def howto_schema(p):
    """HowTo-schema: front matter `howto: <H2-rubrik>` – stegen är punkterna i första numrerade listan efter rubriken."""
    heading = p.get("howto")
    if not heading:
        return ""
    text = lambda x: " ".join(html.unescape(re.sub("<[^>]+>", "", x)).split())
    for m in re.finditer(r'<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|\Z)', p["html"], re.S):
        if text(m.group(1)) != heading:
            continue
        ol = re.search(r"<ol>(.*?)</ol>", m.group(2), re.S)
        if not ol:
            break
        steps = [{"@type": "HowToStep", "position": i, "text": text(li)}
                 for i, li in enumerate(re.findall(r"<li>(.*?)</li>", ol.group(1), re.S), 1)]
        data = {"@context": "https://schema.org", "@type": "HowTo", "name": heading,
                "inLanguage": "sv-SE", "step": steps}
        return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'
    WARNINGS.append(f"{p['slug']}: howto-rubriken '{heading}' eller dess numrerade lista hittades inte")
    return ""


def breadcrumb_schema(trail):
    """trail: [(namn, sökväg), ...] – samma steg som den synliga brödsmulan."""
    items = [{"@type": "ListItem", "position": i, "name": name, "item": f"{SITE['url']}{path}"}
             for i, (name, path) in enumerate(trail, 1)]
    data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


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
        if f.is_dir():
            shutil.copytree(f, DIST / f.name)
        else:
            shutil.copy(f, DIST / f.name)

    posts = sorted((parse(p) for p in (ROOT / "content/posts").glob("*.md")),
                   key=lambda p: p["date"], reverse=True)
    today = datetime.now()
    posts = [p for p in posts if p["date"] <= today]  # framtida datum publiceras automatiskt senare
    ACTIVE_CATS.clear()
    ACTIVE_CATS.update(p["category"] for p in posts)  # tomma kategorier döljs i meny, sidopanel och sitemap

    # Artiklar
    for p in posts:
        cat = CATEGORIES.get(p["category"], p["category"])
        same = [q for q in posts if q["category"] == p["category"] and q is not p]
        related = (same + [q for q in posts if q is not p and q not in same])[:3]
        notice = '<p class="sponsored-note">Samarbete: Detta inlägg innehåller sponsrade länkar.</p>' if p["sponsored"] else ""
        schema = json.dumps({
            "@context": "https://schema.org", "@type": "NewsArticle" if p["category"] == "nyheter" else "Article",
            "headline": p["title"], "description": p.get("description", ""),
            "image": image_url(p, 1200), "datePublished": f"{p['date']:%Y-%m-%d}",
            "dateModified": f"{p['updated']:%Y-%m-%d}", "inLanguage": "sv-SE",
            "author": author_schema(),
            "publisher": {"@type": "Organization", "name": SITE["name"]},
            "mainEntityOfPage": f"{SITE['url']}/{p['slug']}/",
        }, ensure_ascii=False)
        crumb = p.get("crumb") or p["title"]
        h1 = p.get("h1") or p["title"]
        meta_line = (f'<p class="meta"><span>Av {esc(author_name())}</span><time datetime="{p["date"]:%Y-%m-%d}">{sv_date(p["date"])}</time>'
                     + (f'<span>Uppdaterad <time datetime="{p["updated"]:%Y-%m-%d}">{sv_date(p["updated"])}</time></span>' if p["updated"] > p["date"] else "")
                     + f'<span>{p["reading"]} min läsning</span></p>')
        extra = ""
        if p.get("game"):
            # Artikel med inbäddat spel: spelet först (fullbredd), artikeln under
            g = p["game"]
            game_css = (ROOT / "static" / "games" / f"{g}.css").read_text(encoding="utf-8")
            extra = f'<style>{game_css}</style>\n<script src="/games/{g}.js" defer></script>\n'
            hero = p.get("hero") or image_url(p, 1200)
            content = f"""<nav class="crumbs" aria-label="Brödsmulor"><a href="/">Start</a> / <a href="/kategori/{p['category']}/">{cat}</a> / <span>{esc(crumb)}</span></nav>
<section class="ss-section">
  <header class="ss-head"><a class="tag t-{p['category']}" href="/kategori/{p['category']}/">{cat}</a><h1>{esc(h1)}</h1>{meta_line}</header>
  <div id="{g}" class="ss-app"><noscript><p class="ss-noscript">Aktivera JavaScript i webbläsaren för att spela.</p></noscript></div>
</section>
<div class="post-layout">
<article class="post">
  <figure class="game-hero"><img src="{esc(hero)}" width="1200" height="630" alt="{esc(p.get('hero_alt') or h1)}"></figure>
  {notice}
  {toc_html(p)}
  <div class="prose">{p['html']}</div>
  <footer class="post-foot"><span>Kategori:</span> <a href="/kategori/{p['category']}/">{cat}</a></footer>
  {author_box()}
</article>
{sidebar(posts, p)}
</div>
{'<section class="related">' + section_head('Läs också') + '<div class="grid grid-3">' + "".join(card(q) for q in related) + '</div></section>' if related else ''}"""
        else:
            content = f"""<nav class="crumbs" aria-label="Brödsmulor"><a href="/">Start</a> / <a href="/kategori/{p['category']}/">{cat}</a> / <span>{esc(crumb)}</span></nav>
<div class="post-layout">
<article class="post">
  <header class="post-head">
    <a class="tag t-{p['category']}" href="/kategori/{p['category']}/">{cat}</a>
    <h1>{esc(h1)}</h1>
    <p class="lead">{esc(p.get('description', ''))}</p>
    {meta_line}
  </header>
  <div class="post-hero">{thumb(p, 1400, eager=True)}</div>
  {notice}
  {toc_html(p)}
  <div class="prose">{p['html']}</div>
  <footer class="post-foot"><span>Kategori:</span> <a href="/kategori/{p['category']}/">{cat}</a></footer>
  {author_box()}
</article>
{sidebar(posts, p)}
</div>
{'<section class="related">' + section_head('Läs också') + '<div class="grid grid-3">' + "".join(card(q) for q in related) + '</div></section>' if related else ''}"""
        if len(p["title"]) > 60:
            WARNINGS.append(f"{p['slug']}: titeln är {len(p['title'])} tecken (Google visar ca 60)")
        write(f"/{p['slug']}/", page(page_title(p["title"]), p.get("description", ""), f"/{p['slug']}/",
                                     content, extra + f'<meta property="og:image" content="{esc(image_url(p, 1200))}">\n'
                                     f'<script type="application/ld+json">{schema}</script>\n{faq_schema(p)}\n{howto_schema(p)}\n'
                                     + breadcrumb_schema([("Start", "/"), (cat, f"/kategori/{p['category']}/"),
                                                          (crumb, f"/{p['slug']}/")]), compact=bool(p.get("game"))))

    # Startsida: ett utvalt inlägg + rutnät med senaste
    featured = next((p for p in posts if p["slug"] == "spel-for-tva"), posts[0] if posts else None)
    # Spelsidor visas bara i blocket "Spela direkt" på startsidan, inte i listorna
    listed = [p for p in posts if not p.get("game")]
    rest = [p for p in listed if p is not featured]
    sections = ""
    for k, v in CATEGORIES.items():
        items = [p for p in listed if p["category"] == k][:3]
        if len(items) >= 3:  # kategorisektioner först när det finns tillräckligt att fylla dem
            sections += f'<section class="cat-section">{section_head(v, f"/kategori/{k}/")}<div class="grid grid-3">{"".join(card(p) for p in items)}</div></section>'
    intro = ""
    home_md = ROOT / "content" / "home.md"
    if home_md.exists():
        h = parse(home_md)
        intro = f'<section class="home-intro"><h2>{esc(h["title"])}</h2><div class="prose">{h["html"]}</div></section>'
    game_post = next((p for p in posts if p.get("game")), None)
    play = ""
    if game_post:
        play = f"""<section class="play-block"><a href="/{game_post['slug']}/" tabindex="-1" aria-hidden="true"><img src="{esc(game_post.get('hero') or image_url(game_post))}" width="1200" height="630" alt="" loading="lazy"></a>
  <div><p class="play-kicker">Spela direkt – gratis</p><h2>{esc(game_post.get('h1') or game_post['title'])}</h2>
  <p>Utmana en vän på samma mobil eller spela mot datorn. Ingen nedladdning, ingen inloggning.</p>
  <a class="btn-play" href="/{game_post['slug']}/">Spela Sänka skepp</a></div></section>"""
    home = f"""<h1 class="sr-only">{SITE['name']} – guider och tips om spel för två spelare</h1>
<section class="featured">{card(featured, "feature") if featured else ""}</section>
{play}
{'<section>' + section_head("Senaste artiklar") + '<div class="grid grid-3">' + "".join(card(p) for p in rest[:12]) + '</div></section>' if rest else ''}
{sections}
{intro}"""
    site_schema = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "@id": f"{SITE['url']}/#website", "url": f"{SITE['url']}/", "name": SITE["name"],
             "description": SITE["tagline"], "inLanguage": SITE["lang"],
             "publisher": {"@id": f"{SITE['url']}/#organization"}},
            {"@type": "Organization", "@id": f"{SITE['url']}/#organization", "name": SITE["name"],
             "url": f"{SITE['url']}/", "logo": f"{SITE['url']}/icon-192.png",
             "areaServed": {"@type": "Country", "name": "Sverige", "identifier": SITE["country"]},
             "knowsLanguage": SITE["lang"]},
        ],
    }, ensure_ascii=False)
    write("/", page(f"{SITE['name']} – guider och tips om spel för två spelare", SITE["home_description"], "/", home,
                    f'<script type="application/ld+json">{site_schema}</script>'))

    # Kategorier
    for k, v in CATEGORIES.items():
        items = [p for p in posts if p["category"] == k]
        body = "".join(card(p) for p in items) or '<p class="empty">Inga artiklar ännu – snart här!</p>'
        noindex = "" if items else '<meta name="robots" content="noindex">'  # tom kategori: finns men indexeras inte
        # Valfri introduktion: content/categories/<slug>.md (title = H1, description = meta)
        cat_md = ROOT / "content" / "categories" / f"{k}.md"
        h1, desc, intro_html = v, f"Guider och tips om {v.lower()} för två spelare.", ""
        if cat_md.exists():
            c = parse(cat_md)
            h1, desc = c.get("title", v), c.get("description", desc)
            intro_html = f'<div class="cat-intro prose">{c["html"]}</div>'
        write(f"/kategori/{k}/", page(page_title(h1), desc, f"/kategori/{k}/",
                                      f'<nav class="crumbs" aria-label="Brödsmulor"><a href="/">Start</a> / <span>{esc(v)}</span></nav>'
                                      f'<div class="section-head page-head"><h1>{esc(h1)}</h1></div>{intro_html}<div class="grid grid-3">{body}</div>',
                                      noindex + breadcrumb_schema([("Start", "/"), (v, f"/kategori/{k}/")])))
    for old, target in OLD_CATEGORY_REDIRECTS.items():
        write(f"/kategori/{old}/", redirect_page(target))

    # Statiska sidor
    pages = [parse(f) for f in sorted((ROOT / "content/pages").glob("*.md"))]
    for p in pages:
        write(f"/{p['slug']}/", page(page_title(p["title"]), p.get("description", ""), f"/{p['slug']}/",
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

    # Sitemap med <lastmod> (utan omdirigeringar och tomma kategorier)
    def newest(items):
        return max(q["updated"] for q in items)
    entries = [("/", newest(posts))] if posts else []
    entries += [(f"/kategori/{k}/", newest([p for p in posts if p["category"] == k])) for k in CATEGORIES if k in ACTIVE_CATS]
    entries += [(f"/{p['slug']}/", p["updated"]) for p in posts]
    entries += [(f"/{p['slug']}/", p["updated"]) for p in pages]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{SITE['url']}{u}</loc><lastmod>{d:%Y-%m-%d}</lastmod></url>" for u, d in entries) + "</urlset>")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\n")

    print(f"Byggt: {len(posts)} artiklar -> {DIST}")
    for w in WARNINGS:
        print("  VARNING:", w)
    for slug, names in MISSING_LINKS.items():
        print(f"  TODO: {slug}: {len(names)} spelrutor saknar köplänk ({', '.join(names[:3])}{' …' if len(names) > 3 else ''})")


if __name__ == "__main__":
    build()
