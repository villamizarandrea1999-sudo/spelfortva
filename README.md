# spelfortva.com

Statisk sajt på GitHub Pages (samma upplägg som nba-grid.com).

## Publicera en artikel
1. Skapa en fil i `content/posts/`, t.ex. `nya-spel-for-tva-december.md`:
   ```
   ---
   title: Rubrik
   description: Kort beskrivning (meta description)
   date: 2026-12-01
   category: nyheter   # nyheter | co-op | sallskapsspel | mobil | erbjudanden | guider
   sponsored: false    # true = gästinlägg, externa länkar får rel="sponsored"
   ---
   Texten i Markdown...
   ```
2. Commit + push. GitHub Actions bygger sajten och uppdaterar startsidan, kategorin, RSS och sitemap automatiskt.
3. Datum i framtiden publiceras automatiskt den dagen (bygget körs varje morgon).

## Lokalt
`pip install markdown && python build.py` → färdig sajt i `dist/`.
