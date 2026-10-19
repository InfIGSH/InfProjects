"""Transkript-Panels in einer Seite finden -- auch in fremden Frames.

Zwei Wege, absichtlich in dieser Reihenfolge:

1. **Zeitmarken-Dichte.** Ein Transkript-Panel besteht aus vielen kurzen
   Elementen, deren ganzer Text eine Zeitangabe ist (`0:42`, `12:57`). Ein
   Container mit genuegend solchen Kindern ist fast immer das Panel --
   unabhaengig davon, wie die Plattform ihre Klassen nennt.
2. **Benennung.** Erst danach wird auf `transcript`/`transkript`/`caption`
   in id, class, data-* oder aria-label geschaut.

Weg 1 zuerst, weil Weg 2 bei jeder Plattform anders raet und bei
Eigenentwicklungen regelmaessig daneben liegt.

Cross-Origin ist hier kein Hindernis: Playwright steuert den Browser von
aussen und erreicht jeden Frame. Die Sperre, die eine Browser-Erweiterung
aufhaelt, gilt fuer Skripte *in* der Seite.
"""

from __future__ import annotations

#: Mindestzahl an Zeitmarken, damit ein Container als Transkript zaehlt.
MIN_ZEITMARKEN = 5

#: Wortteile, die auf ein Transkript hindeuten (Weg 2).
NAMENSTEILE = ["transcript", "transkript", "caption", "untertitel"]

# JavaScript laeuft im Frame und liefert Kandidaten samt fertigem Selektor
# zurueck. Bewusst nur lesend -- es wird nichts geklickt und nichts geaendert.
KANDIDATEN_JS = """
(opts) => {
  const minMarken = opts.minMarken;
  const namensteile = opts.namensteile;
  const istZeit = (t) => /^\\s*\\d{1,2}:\\d{2}(:\\d{2})?\\s*$/.test(t || '');

  const selektor = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    for (const attr of ['data-purpose', 'data-testid', 'data-test', 'aria-label']) {
      const wert = el.getAttribute(attr);
      if (wert && wert.length < 60) {
        return el.tagName.toLowerCase() + '[' + attr + '="' + wert.replace(/"/g, '\\\\"') + '"]';
      }
    }
    const klassen = [...el.classList].filter(c => c.length < 40);
    if (klassen.length) {
      return el.tagName.toLowerCase() + '.' + klassen.map(c => CSS.escape(c)).join('.');
    }
    return el.tagName.toLowerCase();
  };

  const sichtbar = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  const infos = (el, grund, marken) => ({
    grund,
    selektor: selektor(el),
    eindeutig: (() => {
      try { return document.querySelectorAll(selektor(el)).length; } catch (e) { return -1; }
    })(),
    zeitmarken: marken,
    textlaenge: (el.innerText || '').length,
    sichtbar: sichtbar(el),
    vorschau: (el.innerText || '').replace(/\\s+/g, ' ').slice(0, 300),
  });

  const ergebnis = [];

  // Weg 1: Container nach Zeitmarken-Dichte.
  const zaehler = new Map();
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length === 0 && istZeit(el.textContent)) {
      let p = el.parentElement, tiefe = 0;
      while (p && tiefe < 6) {
        zaehler.set(p, (zaehler.get(p) || 0) + 1);
        p = p.parentElement;
        tiefe++;
      }
    }
  }
  const nachMarken = [...zaehler.entries()]
    .filter(([, n]) => n >= minMarken)
    .sort((a, b) => b[1] - a[1] || (a[0].innerText || '').length - (b[0].innerText || '').length);
  for (const [el, n] of nachMarken.slice(0, 8)) {
    ergebnis.push(infos(el, 'zeitmarken', n));
  }

  // Weg 2: Container nach Benennung.
  const gesehen = new Set(ergebnis.map(e => e.selektor));
  for (const el of document.querySelectorAll('*')) {
    const heuhaufen = [
      el.id, el.className, el.getAttribute('aria-label'),
      el.getAttribute('data-purpose'), el.getAttribute('data-testid'),
    ].filter(Boolean).join(' ').toLowerCase();
    if (!namensteile.some(t => heuhaufen.includes(t))) continue;
    const text = el.innerText || '';
    if (text.length < 100) continue;
    const sel = selektor(el);
    if (gesehen.has(sel)) continue;
    gesehen.add(sel);
    ergebnis.push(infos(el, 'benennung', zaehler.get(el) || 0));
    if (ergebnis.length > 20) break;
  }

  return ergebnis;
}
"""

# Liefert alle Frames der Seite mit URL und Groesse -- fuer `wissen inspect`.
FRAME_JS = """
() => [...document.querySelectorAll('iframe')].map(f => ({
  src: f.getAttribute('src') || '',
  name: f.getAttribute('name') || '',
  breite: f.getBoundingClientRect().width,
  hoehe: f.getBoundingClientRect().height,
}))
"""


def kandidaten(frame) -> list[dict]:
    """Fragt einen Frame nach Transkript-Kandidaten. Fehler ergeben []."""
    try:
        return frame.evaluate(
            KANDIDATEN_JS,
            {"minMarken": MIN_ZEITMARKEN, "namensteile": NAMENSTEILE},
        ) or []
    except Exception:
        return []


def bester_kandidat(frames, min_zeichen: int = 200) -> tuple[dict | None, object]:
    """Sucht in allen Frames den besten Transkript-Kandidaten.

    Vorrang hat die Zeitmarken-Erkennung; innerhalb eines Grundes gewinnt der
    Kandidat mit den meisten Zeitmarken, dann der mit mehr Text.
    """
    treffer: list[tuple[tuple, dict, object]] = []
    for frame in frames:
        for kandidat in kandidaten(frame):
            if kandidat["textlaenge"] < min_zeichen:
                continue
            rang = (
                0 if kandidat["grund"] == "zeitmarken" else 1,
                -kandidat["zeitmarken"],
                -kandidat["textlaenge"],
            )
            treffer.append((rang, kandidat, frame))
    if not treffer:
        return None, None
    treffer.sort(key=lambda t: t[0])
    _, kandidat, frame = treffer[0]
    return kandidat, frame
