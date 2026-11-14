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
- Homepage intro: `content/home.md` (shown at the bottom of the homepage).
- Category intros: `content/categories/<slug>.md` (title = H1, description = meta).
- FAQ sections titled "Vanliga frågor …" with H3 questions automatically get FAQPage JSON-LD
  (first paragraph after each H3 = answer).
- Rewritten articles: add `updated: YYYY-MM-DD` (shown on page, sitemap lastmod, dateModified).
- Page titles get " | Spel för två" only if the total stays ≤ 60 characters; build warns on longer titles.
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

## Article plan
Done: /spel-for-tva/ (main guide) · /sallskapsspel-for-tva/ (retargeted to "brädspel för två vuxna";
must NOT reuse games from the main guide) · /co-op-spel-ps5/ (12 games) · /julklapp-spel-for-tva/.
Full briefs for the next articles: `docs/briefs.md`.

Next, in priority order:
1. /spel-for-tva-pa-distans/ | mobil
2. /switch-spel-for-tva/ | konsol
3. /spel-for-par/ (300) | par – clearly non-adult
4. Reviews: 7 Wonders Duel, Patchwork, Jaipur, Codenames Duet, It Takes Two, Split Fiction

Dropped/merged (would cannibalize existing pages): "brädspel för två – topplista" → /sallskapsspel-for-tva/;
"PS5-spel för två" → /co-op-spel-ps5/. Do NOT write card-game or rules guides ("kortspel för två",
regler) – allakortspel.se, kortspel.se, regler.io etc. own that SERP.
Other ideas from the original plan (spel för 2 gratis online, roliga spel för två, spel för två personer)
overlap with the main guide and the distans article – check before writing.

## Workflow rules
- Always run `python build.py` and check it builds without errors.
- Always publish: once the build passes, commit and push to main without waiting for an OK
  (owner's standing instruction, 14 Nov 2026). Then confirm the change on the live site.
- Never publish facts marked [VERIFIERA] / unverified (see the owner's verification rules).
- Keep commits small, with clear messages (write the message to a file and use
  `git commit -F` – PowerShell breaks quotes in `-m`).
