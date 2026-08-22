#!/usr/bin/env python3
"""
Edits applied to content/ after the WordPress import, kept so the whole pipeline stays
reproducible: import_wxr.py -> post_import_edits.py -> the committed content tree.

Each change is here because mirroring WordPress verbatim would have shipped something
broken or untrue. Run after tools/import_wxr.py.
"""
# NOTE: keep every paragraph on a single line. The renderer uses hard wraps so that
# the imported WordPress content keeps its wpautop line breaks, which means a wrapped
# source line here would render as a <br> mid-sentence.
import pathlib
import re
import sys

CHANGES = []


def edit(path, fn):
    CHANGES.append((path, fn))


# -- The two Replit embeds are dead and the projects are gone from Replit entirely. Both
#    Python programs survive in the archive's own screenshots (pyt1/pyt2), so they are
#    restored as code rather than lost.

ALIEN = '''*Här är hela programmet. Kopiera in det i en Python-miljö om ni vill köra det och se vad som händer.*

```python
print("Hello World!")
ourMessage = 7 * 3
if ourMessage == 21:
  print("We come in peace!")
else:
  print("Peace? There can be no peace!")
```'''

PASSWORD = '''Här är hela programmet. Kör det i en Python-miljö och prova att skriva in de lösenordsförslag som eleverna kommer fram till.

```python
print("If you can guess the secret password,")
print("we will give you all of our technology.")
print("Guess the password: ")

lostPassword = 1234
secretPassword = 1277
password = 1256

answer = int(input(""))

if answer == secretPassword:
  print("Congratulation. You are wise!")
  print("We will give you our technology.")
else:
  print("We are sorry. You are not ready yet.")
  print("We will be back in another millenia.")
```'''

IFRAME_RE = re.compile(r'(?:^[^\n]*\n\n)?<iframe src="https://repl\.it/[^"]*"[^>]*>\s*</iframe>',
                       re.M)


def restore_python(text):
    """Replace each dead Replit embed -- and the sentence introducing it -- with the code."""
    blocks = [ALIEN, PASSWORD]
    out, last, n = [], 0, 0
    for m in IFRAME_RE.finditer(text):
        if n >= len(blocks):
            break
        out.append(text[last:m.start()])
        out.append(blocks[n])
        last, n = m.end(), n + 1
    if n != len(blocks):
        raise SystemExit(f'expected {len(blocks)} Replit embeds, replaced {n}')
    out.append(text[last:])
    return ''.join(out)


edit('content/ak-6/ak-6-aktivitet-06-python-ett-frammande-sprak.md', restore_python)


# -- kodknack.se no longer resolves, and the file it named is now served locally.
def fix_scratchjr_link(text):
    return text.replace('[kodknack.se/gb.sjr](/media/doc/gb.sjr)',
                        '[ScratchJr-projektet (gb.sjr)](/media/doc/gb.sjr)')


edit('content/ak-1/ak-1-aktivitet-04-giftiga-blomman-scratchjr.md', fix_scratchjr_link)


# -- The privacy pages described WordPress comments, Gravatar, Mailchimp, newsletter signup
#    and login logs. None of that exists any more, so leaving them verbatim would have made
#    the site's own privacy statement false.
INTEGRITET = '''---
title: "Integritetspolicy"
slug: "integritetspolicy"
kind: page
date: 2026-08-22
authors: ["Micke Kring"]
---

## Kort version

Kodknäck är ett arkiv med färdiga, statiska sidor. Sajten sätter inga kakor, använder inget analysverktyg och samlar inte in några personuppgifter om dig.

## Vad sajten är

Kodknäck skapades av Micke Kring och Jonas Johansson under tiden på [Årstaskolan](https://arstaskolan.stockholm.se) i Stockholm. Sedan 2023 uppdateras den inte längre. Den ligger kvar som ett arkiv, eftersom många lärare hört av sig om att de fortfarande använder materialet.

Allt innehåll är förgenererade HTML-sidor. Det finns ingen databas, inga formulär, ingen inloggning och ingen kommentarsfunktion.

## Personuppgifter

Vi samlar inte in några personuppgifter. Det finns inget nyhetsbrev, inga kommentarer och inga konton — det som fanns på den gamla WordPress-sajten är borttaget.

Webbservern loggar anrop, precis som alla webbservrar gör. De loggarna används bara för drift och felsökning.

## Kakor

Sajten sätter inga kakor. Mer om det på [Kakor och integritet](/kakor-och-integritet/).

## Inbäddat innehåll

En sida i arkivet innehåller en film från UR. Den laddas **inte** automatiskt — du måste klicka på "Visa filmen" först. Först då kontaktas ur.se, som i sin tur kan sätta egna kakor. Klickar du inte kontaktas ingen annan webbplats.

Länkar till Scratch, Microsoft MakeCode och andra sajter är vanliga länkar. De följs bara om du klickar på dem.

## Material och licens

Allt material som vi skapat själva delas enligt [CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/deed.sv) om inget annat anges.

## Kontakt

Frågor om sajten går till Micke Kring, [jag@mickekring.se](mailto:jag@mickekring.se).
'''

KAKOR = '''---
title: "Kakor och Integritet"
slug: "kakor-och-integritet"
kind: page
date: 2026-08-22
authors: ["Micke Kring"]
---

## Sajten använder inga kakor

Kodknäck sätter inga kakor (cookies). Det finns inget att stänga av och inget att samtycka till.

## Inget analysverktyg

Vi använder inget analysverktyg — varken Google Analytics eller något annat. Vi räknar inte klick och vi mäter inte besök.

## Allt material ligger här

Bilder, filmer och PDF:er ligger på Kodknäcks egen server. Sajten hämtar inga typsnitt, skript eller bilder från någon annan webbplats.

## Ett undantag: filmen från UR

En sida i arkivet innehåller en film från UR. Den laddas först när du klickar på "Visa filmen". Innan dess hämtas ingenting från ur.se. Det är den enda inbäddningen på hela sajten.

## Du kan kontrollera det själv

Öppna webbläsarens utvecklarverktyg. Under **Lagring** ser du att inga kakor sätts, och under **Nätverk** ser du att sidan bara hämtar filer från den här domänen.

## Två typer av kakor

- En **permanent kaka** ligger kvar på din dator under en bestämd tid.
- En **sessionskaka** lagras tillfälligt medan du är inne på en webbsida, och försvinner när du stänger webbläsaren.

Kodknäck använder ingendera.

## Tillsynsmyndighet

Post- och telestyrelsen är tillsynsmyndighet för kakor och lämnar ytterligare information på [sin webbplats](https://www.pts.se/).
'''

edit('content/pages/integritetspolicy.md', lambda _: INTEGRITET)
edit('content/pages/kakor-och-integritet.md', lambda _: KAKOR)


def main():
    for rel, fn in CHANGES:
        p = pathlib.Path(rel)
        if not p.exists():
            print(f'missing: {rel}', file=sys.stderr)
            return 1
        before = p.read_text(encoding='utf-8')
        after = fn(before)
        p.write_text(after, encoding='utf-8')
        print(f'{"unchanged" if after == before else "edited   "}  {rel}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
