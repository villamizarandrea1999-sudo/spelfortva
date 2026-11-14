# spelfortva.com – project brief

## What this site is
A Swedish article site (magazine/blog) about games for two players: board games, card games,
console/PC co-op and mobile games. Language: Swedish (sv-SE). Market: Sweden.
Business goal: rank in Google Sweden, then sell guest posts and earn affiliate commissions
from Swedish game shops.

## Search intent (Ahrefs, Google Sweden, Nov 2026)
- Main keyword: "spel för två" – 1.0K/month, KD 0, informational + commercial.
- Parent topic: "sällskapsspel för två" (500/month).
- Google's top 10 is almost all shops showing products. Users want help choosing games for
  two. Our articles fill that gap: compare games, say who each game suits, help the reader decide.

## How the site works (do not break)
- Static site on GitHub Pages, built by `build.py` (Python + markdown). Custom domain
  spelfortva.com, HTTPS enforced.
- Articles: `content/posts/*.md` with front matter: title, description (max 155 chars),
  date (YYYY-MM-DD), category, sponsored (true/false), image (optional Unsplash id or URL).
- Pages: `content/pages/*.md` (give them a `date` – used for sitemap lastmod).
- Homepage intro: `content/home.md`.
- Game boxes in articles: a `:::spel` … `:::` block with namn, spelare, speltid, alder,
  passar, omdome, lank (affiliate link; `TODO` keeps the "Se pris" button inactive).
- Articles with 4+ H2 headings get an automatic table of contents.
- Empty categories are hidden from the menu, sidebar and sitemap (page exists, noindex).
- GA4: set `SITE["ga_id"]` in build.py; while it is `G-XXXXXXX` no tag is loaded.
- `python build.py` → `dist/`. Pushing to main triggers GitHub Actions (build + deploy).
- Future-dated articles publish automatically on their date (daily rebuild).
- `sponsored: true` adds a "Samarbete" notice and rel="sponsored" to external links.
- Preview locally with `python -m http.server 8000 --directory dist` (root-relative links
  do not work from file://).

## Categories (slug: name)
bradspel: Brädspel & kortspel · konsol: Konsol & PC · mobil: Mobil & online ·
par: För par · guider: Guider · nyheter: Nyheter

## Writing guidelines for every article
- Swedish, natural and friendly, for real people (no keyword stuffing).
- Main keyword in the title, the first paragraph, one H2 and the meta description.
- Structure: short intro answering the search right away, then H2/H3 sections,
  a "Så väljer ni" section, and an FAQ with 3–5 questions.
- Length: main guides 2,000–3,000 words; reviews 800–1,200; other articles 800–1,500.
- Only state facts you are sure of (player count, play time, age). Never invent prices,
  release dates or quotes. If unsure, leave it out or mark it TODO.
- Link internally: every article links to the main guide `/spel-for-tva/` and to 1–3 related
  articles. Never link to articles that don't exist yet.
- No casino, betting, loans or adult content – ever.

## Article plan (write in this order)
1. Spel för två – 20 bästa spelen för två spelare | spel för två (1.0K) | guider  ✅
2. Sällskapsspel för två – bästa brädspelen | sällskapsspel för två (500) | bradspel
3. Spel för par – roliga spel för dejtkvällen | spel för par (300) | par
4. Brädspel för två – topplista | brädspel för två (250) | bradspel
5. PS5-spel för två – bästa co-op i soffan | ps5 spel för två (150) | konsol
6. Spel för 2 – gratis online | spel för 2 (150) | mobil
7. Roliga spel för två på mobilen | roliga spel för två på mobilen (100) | mobil
8. Roliga spel för två – inomhus och utan bräde | roliga spel för två (100) | guider
9. Spel för två personer – kortspel och klassiker | spel för två personer (90) | bradspel
10–15. Reviews: 7 Wonders Duel, Patchwork, Jaipur, Codenames Duet, It Takes Two, Split Fiction

## Workflow rules
- Always run `python build.py` and check it builds without errors.
- Show the result (local preview) before publishing.
- Never commit or push until the owner says OK. When they do, push to main.
- Keep commits small, with clear messages (write the message to a file and use
  `git commit -F` – PowerShell breaks quotes in `-m`).
