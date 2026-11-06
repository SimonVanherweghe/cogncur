"""Create the decision issues (Dutch) with sample images, idempotently.

    python scripts/issues.py            # render images + create missing issues
    python scripts/issues.py --dry-run  # only render images, print what would be created
    python scripts/issues.py --files    # also add the designer-files comment (see below)

Each issue carries a hidden marker <!-- beslissing:<id> -->; issues whose
marker already exists are skipped. Designer issues get one comment linking their
editable SVG/EPS files (scripts/designer_files.py -> docs/ontwerper/<slug>/),
marked <!-- bestanden:<id> --> so it is posted only once. Images are rendered from the current build
(fonts/ttf/Vtex-Regular.ttf) into docs/img/ and must be committed and pushed
before the issue is created (the issue links to them in the repo).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from render_sample import render_lines, render_rows  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from compare import Font  # noqa: E402

REPO = "SimonVanherweghe/cogncur-tex"
FONT = ROOT / "fonts" / "ttf" / "Vtex-Regular.ttf"
IMG = ROOT / "docs" / "img"
IMG_URL = f"https://github.com/{REPO}/blob/main/docs/img"
TOOL_URL = "https://claude.ai/artifact/VMeKGZgUarp7qicDM7stXy"  # private artifact (make artifact)

# Default letterforms: one comment per variant, so a 👍 means exactly one thing.
# (id, title, description, features, sample) - descriptions follow the designer's documentation.
FEATURE_OPTIONS = [
    ("origineel", "Alles zoals het origineel", "Geen extra opties: de vormen zoals Cogncur ze standaard heeft.", [], "toot puddle yummy wow"),
    ("ss01", "Geen instreken vanaf de basislijn", "Korte instreken aan het begin van een woord; geen instreek bij a, c, d, g, o, q.", ["ss01"], "abcde dag"),
    ("ss02", "Geen uithalen aan s, p en ß", "Het ‘staartje’ aan het einde van s, p en ß verdwijnt.", ["ss02"], "kiss rap fuß"),
    ("ss03", "Kortere stokken", "Stokken boven en onder de lijnen zijn 2/3 zo lang als lussen.", ["ss03"], "puddle"),
    ("ss04", "f en q: andere verbinding", "f verbindt met een boog vanuit het midden, q vanaf onderaan.", ["ss04"], "ffqu fijn"),
    ("ss05", "f en q: met penlift", "Na f en q wordt de pen opgetild.", ["ss05"], "ffqu fijn"),
    ("ss04-ss05", "f en q: andere verbinding én penlift", "De combinatie van ss04 en ss05.", ["ss04", "ss05"], "ffqu fijn"),
    ("ss06", "s met een buikje", "Een s met een bolle onderkant in plaats van de slanke s.", ["ss06"], "kiss zus"),
    ("ss07", "Drukletter-r", "Een r die meer op de drukletter lijkt.", ["ss07"], "err rood"),
    ("ss08", "Moderne t (met boogje)", "De bekende drukletter-t. Standaard volgt de t de Duitse en Nederlandse traditie.", ["ss08"], "toot tante"),
    ("ss08-ss09", "Moderne t met rechte verbinding", "Moderne t met een rechte verbinding, zoals in veel Nederlandse methodes.", ["ss08", "ss09"], "toot tante"),
    ("ss11", "r en z beginnen met een hoek", "r, z en Z beginnen met een hoek in plaats van een boog.", ["ss11"], "rz Z zero"),
    ("ss12", "Ronde verbindingen (onderbogen)", "Rechte stukjes in verbindingen worden bogen. **De ontwerper raadt dit af.**", ["ss12"], "impunity"),
    ("ss13", "y begint met een hoek", "y begint met een hoek, zoals i; geldt ook voor de ij.", ["ss13"], "yummy bij"),
    ("ss14", "w begint met een boog", "w begint met een boog, zoals v.", ["ss14"], "wow water"),
    ("ss15", "p begint met een boog", "p begint met een boog, zoals n.", ["ss15"], "pup appel"),
    ("ss16", "Open p", "p zonder gesloten lus; verbindt zoals de n.", ["ss16"], "pup appel"),
    ("ss15-ss16", "Open p die met een boog begint", "De combinatie van ss15 en ss16.", ["ss15", "ss16"], "pup appel"),
    ("ss19", "C, G en L zonder beginlus", "Eenvoudigere hoofdletters C, G en L.", ["ss19"], "Cc Gg Ll"),
    ("ss20", "A, M en N als grote schrijfletters", "A, M en N lijken op vergrote kleine letters.", ["ss20"], "Aa Mm Nn"),
    ("ss17", "Cijfervarianten 1", "Andere vormen voor sommige cijfers.", ["ss17"], "1234567890"),
    ("ss18", "Cijfervarianten 2", "Andere vormen voor sommige cijfers.", ["ss18"], "1234567890"),
    ("ss17-ss18", "Cijfervarianten 1 en 2 samen", "Met beide samen krijgen 4 en 7 nog een andere vorm.", ["ss17", "ss18"], "1234567890"),
    ("tnum", "Even brede cijfers", "Alle cijfers even breed, handig voor rekenopgaven onder elkaar.", ["tnum"], "1111 2020"),
    ("onum", "Mediaevalcijfers", "Cijfers met stokken boven en onder de lijn.", ["onum"], "1234567890"),
]

FEATURES_BODY = f"""<!-- beslissing:standaardvormen -->
## Waarover gaat het?

In **Google Docs, Google Slides** en op de meeste websites kan je de extra opties van een lettertype (de "stijlvarianten") niet aan- of uitzetten. **Wat standaard aan staat, krijgt iedereen.**

Cogncur heeft veel varianten, bijvoorbeeld een moderne t, een drukletter-r of kortere stokken. Ze staan nu allemaal uit. Welke vormen moeten in Vtex standaard zijn?

## Zelf uitproberen

In de **vergelijkingstool** typ je je eigen tekst en zet je varianten aan of uit. Je ziet meteen het resultaat op schrijflijnen. Bovenaan rechts staat je keuze als **code** (bijvoorbeeld `vtex: ss03 ss08 ss09`), met een knop om ze te kopiëren.

👉 {TOOL_URL}
_(Opent de link niet? Vraag Simon om toegang.)_

## Hoe stemmen?

1. Hieronder staat **voor elke variant een aparte reactie**, met een voorbeeld: blauw zonder, rood met.
2. Geef een 👍 bij **elke variant die je standaard wilt**. Meerdere mag. Varianten van dezelfde letter sluiten elkaar uit: kies er per letter één (bv. één keuze voor de t).
3. Wil je je volledige keuze delen? Kopieer de code uit de tool en plak ze in een reactie onderaan. Zet erbij voor welk leerjaar of welke schrijfmethode, en waarom.

## Wat gebeurt er met het resultaat?

De gekozen vormen worden de standaardvormen van Vtex. Google doet dat ook bij zijn eigen schoolschrift **Playwrite** (bijvoorbeeld *Playwrite BE VLG* voor Vlaanderen): vaste vormen per land. In Word of LibreOffice kan je de andere vormen nog altijd zelf kiezen.

_Werknaam van het lettertype: Vtex. De naam "Cogncur" is voorbehouden aan de oorspronkelijke ontwerper._
"""


VOTE_DRAFT = [
    ("Akkoord", "Deze schets mag zo in het lettertype."),
    ("Aanpassen", "Er moet iets veranderen. Schrijf in een reactie wat, of laat de ontwerper het hertekenen."),
]

STYLES_BODY = """<!-- beslissing:stijlen -->
## Waarover gaat het?

Het originele lettertype Cogncur bestaat in **vijf stijlen**. Op dit moment zetten we alleen **Regular** om voor Google Fonts. Elke extra stijl is extra werk: alle nieuwe tekens en verbindingen moeten ook in die stijl gemaakt en getest worden.

Welke stijlen hebben leerkrachten echt nodig in de klas?

## Hoe stemmen?

Hieronder staat **voor elke stijl een aparte reactie** met een voorbeeld.

- Geef een 👍 bij **elke stijl die je wilt** (meerdere mag).
- Waarom wel of niet? Schrijf het in een reactie onderaan, bijvoorbeeld welk leerjaar of welke leermethode die stijl gebruikt.

## Achtergrond

- **Regular** helt licht (7,5°), **Oblique** helt sterker (15°) en **Vertical** staat rechtop.
- **Edged** heeft een lijn met dik en dun, zoals met een beitelpen.
- Alle voorbeelden komen uit de *originele* lettertypes van Cogncur.

_Werknaam van het nieuwe lettertype: Vtex. De naam "Cogncur" is voorbehouden aan de oorspronkelijke ontwerper._
"""

LABELS = [("beslissing", "5319E7", "Open vraag waarover gestemd wordt"),
          ("ontwerper", "D93F0B", "Vooral voor de grafisch ontwerper"),
          ("leerkrachten", "0E8A16", "Vooral voor het team leerkrachten"),
          ("iedereen", "FBCA04", "Voor ontwerper en leerkrachten")]

DECISIONS = [
    {
        "id": "stijlen", "labels": ["leerkrachten"],
        "titel": "Welke stijlen willen we op Google Fonts?",
        "body": STYLES_BODY,
        "options": [
            ("Regular", "Licht hellend (7,5°). Deze stijl wordt nu omgezet.", "stijlen-regular.png"),
            ("Vertical", "Rechtop, zonder helling.", "stijlen-vertical.png"),
            ("Oblique", "Sterker hellend (15°).", "stijlen-oblique.png"),
            ("Edged", "Met dik en dun, zoals een beitelpen, licht hellend.", "stijlen-edged.png"),
            ("Edged Vertical", "Met dik en dun, rechtop.", "stijlen-edged-vertical.png"),
        ],
        "option_style": "multi",
    },
    {
        "id": "schets-eth", "labels": ["ontwerper"],
        "bestanden": "ð",
        "titel": "Schets: ð (eth)",
        "context": "De **ð** komt voor in het IJslands en het Faeröers. Cogncur heeft deze letter niet. "
                   "De schets gebruikt de buik van haar **d**, een steel die bovenaan naar links buigt, en een schuine streep. "
                   "Alles is getekend als middenlijn en daarna met haar pen (rond, 68 eenheden, 7,5° helling) uitgezet.\n\n"
                   "De ð verbindt zich precies zoals de **d** (getest).",
        "glyphs": ["ð d ð"], "words": ["aða eðe bróðir með"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "schets-thorn", "labels": ["ontwerper"],
        "bestanden": "þ",
        "titel": "Schets: þ (thorn)",
        "context": "De **þ** komt voor in het IJslands. De schets combineert de lus bovenaan van haar **b** met de "
                   "staart en de buik van haar **p**.\n\nDe þ verbindt zich precies zoals de **p** (getest).",
        "glyphs": ["þ p b þ"], "words": ["þú þetta aþa"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "schets-Thorn", "labels": ["ontwerper"],
        "slug": "schets-thorn-hoofdletter", "bestanden": "Þ",
        "titel": "Schets: Þ (hoofdletter thorn)",
        "context": "De **Þ** is de hoofdletter van þ (IJslands). De schets is haar **P** met de buik naar het midden verschoven.\n\n"
                   "De Þ verbindt zich precies zoals de **P** (getest).",
        "glyphs": ["Þ P Þ"], "words": ["Þór Þingvellir"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "schets-scharfes-s", "labels": ["ontwerper"],
        "bestanden": "ẞ",
        "titel": "Schets: ẞ (hoofdletter ringel-s)",
        "context": "De **ẞ** is de Duitse hoofdletter van ß. De schets gebruikt de steel en de onderste buik van haar **B**, "
                   "met een vlakke bovenkant en een schuine lijn. Van alle schetsen is dit de ruwste.\n\n"
                   "De ẞ verbindt zich precies zoals de **B** (getest).",
        "glyphs": ["ẞ B ß ẞ"], "words": ["STRAẞE GROẞ Fuẞ"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-ogonek", "labels": ["ontwerper"],
        "bestanden": "ąęįųĄĘĮŲ",
        "titel": "Nieuw accent: ogonek (ą ę į ų)",
        "context": "Het haakje onder **ą ę į ų** (Pools, Litouws) bestaat niet in Cogncur. Het is nieuw getekend als middenlijn en met haar pen uitgezet. "
                   "Het hangt aan de onderkant van de laatste stok van de letter. Die plaats is geschat.\n\n"
                   "De letters verbinden zich precies zoals a, e, i, u (getest).",
        "glyphs": ["ą ę į ų Ą Ę Į Ų"], "words": ["mąka ręka gęś ąžuolas"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-dubbele-aigu", "labels": ["ontwerper"],
        "bestanden": "őűŐŰ",
        "titel": "Nieuw accent: dubbele accent aigu (ő ű)",
        "context": "Het dubbele accent op **ő ű** (Hongaars) bestaat uit twee van haar eigen accents aigus, "
                   "elk 20 % smaller en naast elkaar gezet.",
        "glyphs": ["ő ű Ő Ű  ó ú"], "words": ["idő tűz Őrség Ügyes"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-komma-onder", "labels": ["ontwerper"],
        "bestanden": "șțķļņģȘȚĶĻŅ",
        "titel": "Nieuw accent: komma onder (ș ț ķ ļ ņ) en boven (ģ)",
        "context": "De komma onder **ș ț** (Roemeens) en **ķ ļ ņ** (Lets) is haar eigen komma, op 80 % van de grootte. "
                   "Voor de **ģ** staat de komma, zoals in het Lets gebruikelijk, omgekeerd *boven* de letter.\n\n"
                   "_De Ģ (hoofdletter) is een aparte vraag: daar botst de komma met de lus van de G._",
        "glyphs": ["ș ț ķ ļ ņ ģ  Ș Ț Ķ Ļ Ņ"], "words": ["școală țară ķirsis ļoti ģimene"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-punt-boven", "labels": ["ontwerper"],
        "bestanden": "ċėġżĊĖĠŻİ",
        "titel": "Nieuw accent: punt boven (ċ ė ġ ż İ)",
        "context": "De punt op **ċ ė ġ ż** (Pools, Litouws, Maltees) en de **İ** (Turks) is exact de punt van haar **i**.",
        "glyphs": ["ċ ė ġ ż  Ċ Ė Ġ Ż İ  i"], "words": ["żaba ėsti ġurnata İzmir"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-apostrof-haacek", "labels": ["ontwerper"],
        "bestanden": "ďľťĽ",
        "titel": "Nieuw accent: haček als apostrof (ď ľ ť Ľ)",
        "context": "Bij **ď ľ ť Ľ** (Tsjechisch, Slowaaks) staat de haček niet boven de lange stok maar ernaast, als een apostrof. "
                   "Daarvoor is haar eigen apostrof (zoals in *don't*) gebruikt, rechts van de stok. De plaats is per letter geschat.\n\n"
                   "_Voor de ľ in stijlvariant ss01 is er een aparte vraag, want daar raakt de apostrof bijna de instreek._",
        "glyphs": ["ď ľ ť Ľ  č"], "words": ["ďakujem ľahký ťava Ľubica"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "streep-letters", "labels": ["ontwerper"],
        "bestanden": "ĐÐđĦħŁł",
        "titel": "Schets: letters met een streep (Đ Ð đ Ħ ħ Ł ł)",
        "context": "**Đ đ** (Kroatisch, Vietnamees), **Ð** (IJslands), **Ħ ħ** (Maltees) en **Ł ł** (Pools) zijn haar letter "
                   "met een rechte streep (of schuine streep bij Ł ł). Die streep is met haar pen getekend. De hoogte van de streep is geschat.",
        "glyphs": ["Đ Ð đ Ħ ħ Ł ł"], "words": ["Đorđe ħobż łódka Łódź"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "losse-tekens", "labels": ["ontwerper"],
        "bestanden": "¯ˆˇ˘˙˚˛˜˝…−",
        "titel": "Schets: losse accenten, … en −",
        "context": "Google Fonts vraagt ook **losse accenten** (¯ ˆ ˇ ˘ ˙ ˚ ˛ ˜ ˝), het **beletselteken** (…) en het **minteken** (−). "
                   "De losse accenten zijn haar eigen accenten met ruimte ernaast. … bestaat uit drie van haar punten. − is de liggende streep van haar +.",
        "glyphs": ["¯ ˆ ˇ ˘ ˙ ˚ ˛ ˜ ˝"], "words": ["en zo… 5 − 3 = 2"],
        "options": VOTE_DRAFT,
    },
]


DECISIONS.append({
    "id": "standaardvormen", "labels": ["leerkrachten"],
    "titel": "Welke lettervormen moeten standaard zijn?",
    "body": FEATURES_BODY,
    "feature_options": FEATURE_OPTIONS,
})


def render_feature_options(font):
    for oid, title, _desc, feats, sample in FEATURE_OPTIONS:
        rows = [("zonder" if feats else "standaard", sample, {}, "1E4FB8")]
        if feats:
            rows.append(("met " + " + ".join(feats), sample, {f: True for f in feats}, "B42318"))
        render_rows(font, rows, 72).save(IMG / f"standaard-{oid}.png", optimize=True)


def gh(*args, input=None):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, input=input).stdout


def existing_markers():
    out = gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "500", "--json", "number,body")
    found = {}
    for issue in json.loads(out):
        body = issue["body"] or ""
        if "<!-- beslissing:" in body:
            key = body.split("<!-- beslissing:", 1)[1].split("-->", 1)[0].strip()
            found[key] = issue["number"]
    return found


def slug(d):
    """File name for an issue's images/files. Must not differ from another slug only
    in case (macOS is case-insensitive: schets-thorn vs schets-Thorn collided)."""
    return d.get("slug", d["id"])


def render(d, font):
    if "glyphs" not in d:
        return []
    paths = []
    for kind, lines, size in (("tekens", d["glyphs"], 120), ("woorden", d["words"], 80)):
        p = IMG / f"{slug(d)}-{kind}.png"
        render_lines(font, lines, size, {}, "1E4FB8").save(p, optimize=True)
        paths.append(p)
    return paths


def body(d):
    imgs = "\n\n".join(f"![{d['titel']}]({IMG_URL}/{slug(d)}-{k}.png?raw=true)" for k in ("tekens", "woorden"))
    return f"""<!-- beslissing:{d['id']} -->
## Waarover gaat het?

{d['context']}

{imgs}

## Hoe stemmen?

Hieronder staat **voor elke keuze een aparte reactie**. Geef een 👍 bij de keuze die je wilt.
Wil je iets aanpassen? Schrijf in een reactie onderaan wat er anders moet. Een schets of foto mag ook.

_Dit is een schets op basis van de vormen en de pen van Cogncur. Niets is al definitief. Werknaam van het lettertype: Vtex._
"""


REPO_URL = f"https://github.com/{REPO}"


def files_comment(d):
    """Comment for a designer issue, linking its editable files."""
    folder = f"docs/ontwerper/{slug(d)}"
    rows = []
    for ch in d["bestanden"]:
        stem = next(p.stem for p in (ROOT / folder).glob(f"{ord(ch):04X}-*.svg"))
        rows.append(f"| {ch} | [SVG]({REPO_URL}/blob/main/{folder}/{stem}.svg) | "
                    f"[EPS]({REPO_URL}/raw/main/{folder}/{stem}.eps) |")
    return f"""<!-- bestanden:{d['id']} -->
### Bestanden om aan te passen

Elk teken als vectorbestand, rechtop en in de eenheden van het lettertype (2048 per em).

- **SVG**: voor Illustrator of Inkscape, met lagen voor hulplijnen, omtrek, middenlijn en vlakken (punten, komma's).
- **EPS**: alleen de middenlijn en vlakken, om in FontForge te importeren op de laag *Skeleton*.

| Teken | Illustrator / Inkscape | FontForge |
|---|---|---|
{chr(10).join(rows)}

Overzicht van de voorbeeldregels (met verbindingen): [SVG]({REPO_URL}/blob/main/{folder}/overzicht.svg) · [EPS]({REPO_URL}/raw/main/{folder}/overzicht.eps)

Alles in één map: [{folder}]({REPO_URL}/tree/main/{folder}) · uitleg: [README]({REPO_URL}/blob/main/docs/ontwerper/README.md)

Een aangepaste versie mag je als bijlage in een reactie hieronder zetten.
"""


def post_files_comments(have):
    for d in DECISIONS:
        if "bestanden" not in d or d["id"] not in have:
            continue
        num = str(have[d["id"]])
        bodies = gh("issue", "view", num, "-R", REPO, "--json", "comments", "-q", ".comments[].body")
        if f"<!-- bestanden:{d['id']} -->" in bodies:
            print(f"files comment exists: #{num}")
            continue
        gh("issue", "comment", num, "-R", REPO, "--body-file", "-", input=files_comment(d))
        print(f"files comment added: #{num}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--files", action="store_true", help="add the designer-files comment to designer issues")
    a = ap.parse_args()
    IMG.mkdir(parents=True, exist_ok=True)
    font = Font(FONT)
    for d in DECISIONS:
        render(d, font)
    render_feature_options(font)
    print(f"rendered {2 * sum(1 for d in DECISIONS if 'glyphs' in d)} images into {IMG}")
    if a.dry_run:
        for d in DECISIONS:
            print("would create:", d["titel"])
        return
    for name, color, desc in LABELS:
        gh("label", "create", name, "--color", color, "--description", desc, "-R", REPO, "--force")
    have = existing_markers()
    for d in DECISIONS:
        if d["id"] in have:
            print(f"exists: #{have[d['id']]} {d['titel']}")
            continue
        labels = ",".join(["beslissing"] + d["labels"])
        url = gh("issue", "create", "-R", REPO, "--title", d["titel"], "--label", labels, "--body-file", "-",
                 input=d.get("body") or body(d)).strip()
        num = url.rsplit("/", 1)[1]
        for oid, title, desc, feats, _sample in d.get("feature_options", []):
            code = ("`vtex: " + " ".join(feats) + "`") if feats else "`vtex: standaard`"
            gh("issue", "comment", num, "-R", REPO, "--body-file", "-",
               input=f"### {title}\n\n{desc}\n\nCode: {code}\n\n"
                     f"![{title}]({IMG_URL}/standaard-{oid}.png?raw=true)\n\n👍 = dit wil ik standaard")
        for i, opt in enumerate(d.get("options", [])):
            label, text = opt[0], opt[1]
            if d.get("option_style") == "multi":
                img = f"\n\n![{label}]({IMG_URL}/{opt[2]}?raw=true)" if len(opt) > 2 else ""
                msg = f"### {label}\n\n{text}{img}\n\n👍 = deze stijl wil ik op Google Fonts"
            else:
                letter = "ABCDEFG"[i]
                msg = f"### Optie {letter}: {label}\n\n{text}\n\n👍 = ik kies optie {letter}"
            gh("issue", "comment", num, "-R", REPO, "--body-file", "-", input=msg)
        print(f"created: {url}")
        have[d["id"]] = int(num)
    if a.files:
        post_files_comments(have)


if __name__ == "__main__":
    main()
