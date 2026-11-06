# Bestanden voor de ontwerper

Per vraag (GitHub-issue met label `ontwerper`) staat hier een map met de nieuwe tekens als
bewerkbare vectorbestanden. Ze worden gemaakt door `scripts/designer_files.py` uit het huidige
lettertype; pas ze dus niet hier aan, maar stuur je aanpassing terug (in het issue of als bestand).

## Wat zit er in een map?

| Bestand | Inhoud | Om te gebruiken in |
|---|---|---|
| `<code>-<naam>.svg` | Eén teken, **rechtop** (zonder de helling van 7,5°), in de eenheden van het lettertype (2048 per em, oorsprong = oorsprong van het teken). Lagen: `hulplijnen` (onderlijn −682, basislijn 0, x-hoogte 682, bovenlijn 1364, breedte), `omtrek` (grijs, ter referentie), `middenlijn` (rood, jouw *Skeleton*-laag) en `vlakken` (punten, komma's: jouw *Extra*-laag). | Illustrator, Inkscape, browser |
| `<code>-<naam>.eps` | Alleen de middenlijn en de vlakken, rechtop, 1:1 in eenheden van het lettertype. | FontForge: *File → Import* op de laag **Skeleton** |
| `overzicht.svg` / `.eps` | De voorbeeldregels uit het issue zoals het lettertype ze zet (hellend, met verbindingen), op schrijflijnen, met omtrek en middenlijn. | Om in te schetsen of te annoteren |

`<code>` is de Unicode-code van het teken (bv. `00F0` = ð).

## Goed om te weten

- **FontForge en de EPS**: de middenlijnen zijn *open* paden. Ze staan in de EPS als `fill` in plaats
  van `stroke`, want FontForge zet een `stroke` bij het importeren om in een omtrek. Zo blijven ze
  open, net zoals je ze tekent. In Illustrator zien ze er daardoor uit als gevulde vlakken; gebruik
  daar de SVG.
- De **omtrek** in de SVG per teken is rechtgezet (de helling eruit gehaald), zodat hij over de
  middenlijn valt. In het lettertype helt hij 7,5°.
- Accenttekens (zoals ą) zijn in het lettertype samengesteld uit letter + accent. In de bestanden
  staan ze samengevoegd.
