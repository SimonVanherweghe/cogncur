"""Generate the test-bank corpora in tests/corpus/.

The calt logic decides each letter's shape from (previous glyph class,
whether a letter follows). So to cover every join systematically we need:
  - every letter alone                         -> start-alone
  - every letter X followed by Y (pairs)       -> start-continued + after-X-end
  - every X Y followed by a letter (triples)   -> after-X-continued
  - the same for uppercase starts and accented letters
  - starts after space / punctuation / digits  (the 'space' placeholder fix)
One item per line. Items on one line separated by spaces are shaped together.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "corpus"

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = LOWER.upper()
# GF Latin Core-ish accented lowercase/uppercase that Cogncur supports
ACC_LOWER = "áàâäãåāăçéèêëēĕěíìîïĩīĭñóòôöõōŏøúùûüũūŭůýỳŷÿỹȳšžßæœ"
ACC_UPPER = "ÁÀÂÄÃÅĀĂÇÉÈÊËĒĔÍÌÎÏĪĬÑÓÒÔÖÕŌŎØÚÙÛÜŨŪŬŮÝŶŸŠŽÆŒ"

WORDS = {
    "nl": "Amsterdam bijzonder vrijdag ijs IJsland zeeën geëerd reünie "
          "Pa's wijn cadeautje schrijven Quiz Zwolle Groningen",
    "en": "The quick brown fox jumps over the lazy dog. "
          "Sphinx of black quartz, judge my vow! don't it's queen yellow",
    "fr": "Voix ambiguë d'un cœur qui au zéphyr préfère les jattes de kiwis. "
          "naïve façade élève Noël",
    "de": "Falsches Üben von Xylophonmusik quält jeden größeren Zwerg. "
          "Straße Mädchen Öl",
}

CONTEXT = [
    # line start / after punctuation / digits: must use start forms
    "(hallo) [test] {abc} \"quote\" 'single' «guillemets» „dutch“",
    "word. word, word; word: word! word? word…",
    "a-b e-mail co-op 1st 2nd 3rd 4th 2024 h2o A4 x2",
    "don't l'été d'accord rock'n'roll",
    "a i o u e  I A O",  # single letters
    "ABC USA NATO OK",   # uppercase runs
    "0123456789 1/2 3.14 €5 $5 £5 50% #1 @home",
]


def write(name, items):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.txt").write_text("\n".join(items) + "\n", encoding="utf-8")
    print(f"{name}: {len(items)} lines")


def main():
    write("singles", list(LOWER + UPPER + ACC_LOWER + ACC_UPPER))
    write("pairs_lower", [a + b for a in LOWER for b in LOWER])
    write("triples_lower", [a + b + "n" for a in LOWER for b in LOWER])
    write("upper_lower", [A + b for A in UPPER for b in LOWER] + [A + b + "n" for A in UPPER for b in LOWER])
    acc = []
    for c in ACC_LOWER:
        acc += [c + "n", "n" + c, "n" + c + "n", "o" + c + "o", "s" + c, "v" + c]
    for C in ACC_UPPER:
        acc += [C + "n", C + "a"]
    write("accents", acc)
    write("words", [w for lang in WORDS.values() for w in [lang]] + [w for lang in WORDS.values() for w in lang.split()])
    write("context", CONTEXT)


if __name__ == "__main__":
    main()
