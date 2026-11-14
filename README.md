# spelfortva.com

Statisk sajt på GitHub Pages (samma upplägg som nba-grid.com).

## Publicera en artikel
1. Skapa en fil i `content/posts/`, t.ex. `nya-spel-for-tva-december.md`:
   ```
   ---
   title: Rubrik
   description: Kort beskrivning (meta description)
   date: 2026-12-01
   category: bradspel  # bradspel | konsol | mobil | par | guider | nyheter
   sponsored: false    # true = gästinlägg, externa länkar får rel="sponsored"
   image: 1585504198199-20277593b94f   # valfritt: Unsplash-id eller bild-URL
   ---
   Texten i Markdown...
   ```
   Description får vara max 155 tecken – bygget varnar annars.

### Spelruta i en artikel
```
:::spel
namn: 7 Wonders Duel
spelare: 2
speltid: 30 min
alder: 10+
passar: Er som gillar strategi.
omdome: Kort omdöme.
lank: TODO          # affiliate-länk; "Se pris" är inaktiv tills länken finns
:::
```
Artiklar med minst fyra H2-rubriker får automatiskt en innehållsförteckning.
2. Commit + push. GitHub Actions bygger sajten och uppdaterar startsidan, kategorin, RSS och sitemap automatiskt.
3. Datum i framtiden publiceras automatiskt den dagen (bygget körs varje morgon).

## Lokalt
`pip install markdown && python build.py` → färdig sajt i `dist/`.
