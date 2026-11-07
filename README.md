# Cogncur → Google Fonts (werknaam: Vtex)

Dit project zet het verbonden schrijfletterfont [Cogncur](https://github.com/syboor/cogncur) van Liesbeth Flobbe om naar een versie die bij Google Fonts ingediend kan worden. Zo kan het ook gebruikt worden in Google Docs, Google Slides en op websites, zonder installatie.

**Over de naam.** De licentie van het origineel (SIL Open Font License, zie `LICENSE.txt`) reserveert de naam "Cogncur". Liesbeth Flobbe, de ontwerper, vindt het goed dat de Google Fonts-versie de naam Cogncur houdt, met een toevoeging voor de varianten. De precieze naam is nog niet gekozen; tot dan is "Vtex" de werknaam.

## Wat zit erin

- **Een automatische build**: van het originele FontForge-bestand naar een UFO-bron en een TTF via `gftools builder`. De handmatige stappen uit het origineel (`howto.txt`) zitten nu in scripts.
- **Een testbank**: vergelijkt de nieuwe build met het originele lettertype. Ze controleert vooral de verbindingen tussen de letters en checkt dat elke nieuwe letter zich gedraagt als de letter waarop hij gebaseerd is.
- **Nieuwe tekens** voor de tekenset die Google Fonts vraagt. `docs/new-glyphs.md` beschrijft per teken waar het van afgeleid is. Een deel ervan zijn nog schetsen die op een beslissing wachten.
- **Een vergelijkingstool**: het origineel en de nieuwe versie over elkaar of onder elkaar, met tekst die je zelf intypt.

## Gebruik

Vereist: Python 3.13, FontForge (met Python) en HarfBuzz (`hb-shape`, `hb-view`). Voor de website: Node 24 met npm.

```sh
make venv        # Python-omgeving met de font-tools
make upstream    # haalt het origineel op (vastgezette versie in upstream.lock)
make all         # bron maken → bouwen → testen → Google Fonts-controles
make web-data    # lettertype en gegevens voor de website naar web/public/ (daarna committen)
make serve       # de website lokaal op http://localhost:4321/cogncur-tex/
make designer    # bestanden voor de ontwerper opnieuw maken (zie hieronder)
```

Rapporten komen in `tests/report/`. Meer uitleg voor ontwikkelaars staat in `CLAUDE.md`.

## Na een wijziging aan een teken

De issues voor de ontwerper (label `ontwerper`) linken naar bewerkbare SVG- en EPS-bestanden in
`docs/ontwerper/`. Die worden niet vanzelf bijgewerkt. Na elke wijziging aan een teken:

1. `make designer`: bouwt het lettertype opnieuw en maakt de bestanden opnieuw.
2. Commit en push `docs/ontwerper/` naar `main`. De links in de issues wijzen altijd naar `main`,
   dus de ontwerper ziet dan meteen de nieuwe versie. Je hoeft in de issues niets aan te passen.

Komt er een nieuw issue voor de ontwerper bij? Zet de tekens in `"bestanden"` in
`scripts/issues.py`, doe stap 1 en 2, en daarna `.venv/bin/python scripts/issues.py --files`
(dat plaatst de reactie met de links, maar nooit twee keer).

## Een nieuwe versie uitbrengen

De website toont standaard de nieuwste versie. Wat er nog in ontwikkeling is, staat ernaast en
oudere versies blijven bekijkbaar (pagina **Versies**).

1. Maak een mijlpaal: `.venv/bin/python scripts/release.py milestone 1.001`. Zet op GitHub de
   issues die in die versie komen in de mijlpaal "Versie 1.001", en sluit ze als ze klaar zijn.
2. `make release V=1.001`: verhoogt het versienummer, bouwt en test het lettertype, bewaart een
   kopie voor de website, schrijft de lijst met afgesloten issues en de veranderde tekens, en
   maakt een commit en een tag. Dit blijft op je eigen computer.
3. `make publish V=1.001`: zet alles op GitHub, maakt de release met het lettertype en sluit de
   mijlpaal. De website wordt daarna vanzelf bijgewerkt.
