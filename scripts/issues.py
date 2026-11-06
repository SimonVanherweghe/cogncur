"""Create the decision issues (Dutch) with sample images, idempotently.

    python scripts/issues.py            # render images + create missing issues
    python scripts/issues.py --dry-run  # only render images, print what would be created

Each issue carries a hidden marker <!-- beslissing:<id> -->; issues whose
marker already exists are skipped. Images are rendered from the current build
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
from render_sample import render_lines  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from compare import Font  # noqa: E402

REPO = "SimonVanherweghe/cogncur-tex"
FONT = ROOT / "fonts" / "ttf" / "Vtex-Regular.ttf"
IMG = ROOT / "docs" / "img"
IMG_URL = f"https://github.com/{REPO}/blob/main/docs/img"

VOTE_DRAFT = [
    ("Akkoord", "Deze schets mag zo in het lettertype."),
    ("Aanpassen", "Er moet iets veranderen. Schrijf in een reactie wat, of laat de ontwerper het hertekenen."),
]

DECISIONS = [
    {
        "id": "schets-eth", "labels": ["ontwerper"],
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
        "titel": "Schets: þ (thorn)",
        "context": "De **þ** komt voor in het IJslands. De schets combineert de lus bovenaan van haar **b** met de "
                   "staart en de buik van haar **p**.\n\nDe þ verbindt zich precies zoals de **p** (getest).",
        "glyphs": ["þ p b þ"], "words": ["þú þetta aþa"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "schets-Thorn", "labels": ["ontwerper"],
        "titel": "Schets: Þ (hoofdletter thorn)",
        "context": "De **Þ** is de hoofdletter van þ (IJslands). De schets is haar **P** met de buik naar het midden verschoven.\n\n"
                   "De Þ verbindt zich precies zoals de **P** (getest).",
        "glyphs": ["Þ P Þ"], "words": ["Þór Þingvellir"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "schets-scharfes-s", "labels": ["ontwerper"],
        "titel": "Schets: ẞ (hoofdletter ringel-s)",
        "context": "De **ẞ** is de Duitse hoofdletter van ß. De schets gebruikt de steel en de onderste buik van haar **B**, "
                   "met een vlakke bovenkant en een schuine lijn. Van alle schetsen is dit de ruwste.\n\n"
                   "De ẞ verbindt zich precies zoals de **B** (getest).",
        "glyphs": ["ẞ B ß ẞ"], "words": ["STRAẞE GROẞ Fuẞ"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-ogonek", "labels": ["ontwerper"],
        "titel": "Nieuw accent: ogonek (ą ę į ų)",
        "context": "Het haakje onder **ą ę į ų** (Pools, Litouws) bestaat niet in Cogncur. Het is nieuw getekend als middenlijn en met haar pen uitgezet. "
                   "Het hangt aan de onderkant van de laatste stok van de letter. Die plaats is geschat.\n\n"
                   "De letters verbinden zich precies zoals a, e, i, u (getest).",
        "glyphs": ["ą ę į ų Ą Ę Į Ų"], "words": ["mąka ręka gęś ąžuolas"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-dubbele-aigu", "labels": ["ontwerper"],
        "titel": "Nieuw accent: dubbele accent aigu (ő ű)",
        "context": "Het dubbele accent op **ő ű** (Hongaars) bestaat uit twee van haar eigen accents aigus, "
                   "elk 20 % smaller en naast elkaar gezet.",
        "glyphs": ["ő ű Ő Ű  ó ú"], "words": ["idő tűz Őrség Ügyes"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-komma-onder", "labels": ["ontwerper"],
        "titel": "Nieuw accent: komma onder (ș ț ķ ļ ņ) en boven (ģ)",
        "context": "De komma onder **ș ț** (Roemeens) en **ķ ļ ņ** (Lets) is haar eigen komma, op 80 % van de grootte. "
                   "Voor de **ģ** staat de komma, zoals in het Lets gebruikelijk, omgekeerd *boven* de letter.\n\n"
                   "_De Ģ (hoofdletter) is een aparte vraag: daar botst de komma met de lus van de G._",
        "glyphs": ["ș ț ķ ļ ņ ģ  Ș Ț Ķ Ļ Ņ"], "words": ["școală țară ķirsis ļoti ģimene"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-punt-boven", "labels": ["ontwerper"],
        "titel": "Nieuw accent: punt boven (ċ ė ġ ż İ)",
        "context": "De punt op **ċ ė ġ ż** (Pools, Litouws, Maltees) en de **İ** (Turks) is exact de punt van haar **i**.",
        "glyphs": ["ċ ė ġ ż  Ċ Ė Ġ Ż İ  i"], "words": ["żaba ėsti ġurnata İzmir"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "accent-apostrof-haacek", "labels": ["ontwerper"],
        "titel": "Nieuw accent: haček als apostrof (ď ľ ť Ľ)",
        "context": "Bij **ď ľ ť Ľ** (Tsjechisch, Slowaaks) staat de haček niet boven de lange stok maar ernaast, als een apostrof. "
                   "Daarvoor is haar eigen apostrof (zoals in *don't*) gebruikt, rechts van de stok. De plaats is per letter geschat.\n\n"
                   "_Voor de ľ in stijlvariant ss01 is er een aparte vraag, want daar raakt de apostrof bijna de instreek._",
        "glyphs": ["ď ľ ť Ľ  č"], "words": ["ďakujem ľahký ťava Ľubica"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "streep-letters", "labels": ["ontwerper"],
        "titel": "Schets: letters met een streep (Đ Ð đ Ħ ħ Ł ł)",
        "context": "**Đ đ** (Kroatisch, Vietnamees), **Ð** (IJslands), **Ħ ħ** (Maltees) en **Ł ł** (Pools) zijn haar letter "
                   "met een rechte streep (of schuine streep bij Ł ł). Die streep is met haar pen getekend. De hoogte van de streep is geschat.",
        "glyphs": ["Đ Ð đ Ħ ħ Ł ł"], "words": ["Đorđe ħobż łódka Łódź"],
        "options": VOTE_DRAFT,
    },
    {
        "id": "losse-tekens", "labels": ["ontwerper"],
        "titel": "Schets: losse accenten, … en −",
        "context": "Google Fonts vraagt ook **losse accenten** (¯ ˆ ˇ ˘ ˙ ˚ ˛ ˜ ˝), het **beletselteken** (…) en het **minteken** (−). "
                   "De losse accenten zijn haar eigen accenten met ruimte ernaast. … bestaat uit drie van haar punten. − is de liggende streep van haar +.",
        "glyphs": ["¯ ˆ ˇ ˘ ˙ ˚ ˛ ˜ ˝"], "words": ["en zo… 5 − 3 = 2"],
        "options": VOTE_DRAFT,
    },
]


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


def render(d, font):
    paths = []
    for kind, lines, size in (("tekens", d["glyphs"], 120), ("woorden", d["words"], 80)):
        p = IMG / f"{d['id']}-{kind}.png"
        render_lines(font, lines, size, {}, "1E4FB8").save(p, optimize=True)
        paths.append(p)
    return paths


def body(d):
    imgs = "\n\n".join(f"![{d['titel']}]({IMG_URL}/{d['id']}-{k}.png?raw=true)" for k in ("tekens", "woorden"))
    return f"""<!-- beslissing:{d['id']} -->
## Waarover gaat het?

{d['context']}

{imgs}

## Hoe stemmen?

Hieronder staat **voor elke keuze een aparte reactie**. Geef een 👍 bij de keuze die je wilt.
Wil je iets aanpassen? Schrijf in een reactie onderaan wat er anders moet. Een schets of foto mag ook.

_Dit is een schets op basis van de vormen en de pen van Cogncur. Niets is al definitief. Werknaam van het lettertype: Vtex._
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    IMG.mkdir(parents=True, exist_ok=True)
    font = Font(FONT)
    for d in DECISIONS:
        render(d, font)
    print(f"rendered {2 * len(DECISIONS)} images into {IMG}")
    if a.dry_run:
        for d in DECISIONS:
            print("would create:", d["titel"])
        return
    have = existing_markers()
    for d in DECISIONS:
        if d["id"] in have:
            print(f"exists: #{have[d['id']]} {d['titel']}")
            continue
        labels = ",".join(["beslissing"] + d["labels"])
        url = gh("issue", "create", "-R", REPO, "--title", d["titel"], "--label", labels, "--body-file", "-",
                 input=body(d)).strip()
        num = url.rsplit("/", 1)[1]
        for i, (label, text) in enumerate(d["options"]):
            letter = "ABCDEFG"[i]
            gh("issue", "comment", num, "-R", REPO, "--body-file", "-",
               input=f"### Optie {letter}: {label}\n\n{text}\n\n👍 = ik kies optie {letter}")
        print(f"created: {url}")


if __name__ == "__main__":
    main()
