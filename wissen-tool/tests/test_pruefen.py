"""Tests der netzunabhängigen Teile von `wissen inspect` und `wissen links`."""

import pytest

from wissen import pruefen


@pytest.mark.parametrize(
    "url,erwartet",
    [
        # Lektionen eines Kurses fallen zu einer Form zusammen ...
        (
            "https://campus.thinkspace.ac.uk/student/course/view/329/item/43336/0/709",
            "/student/course/view/#/item/#/#/#",
        ),
        (
            "https://campus.thinkspace.ac.uk/student/course/view/329/item/44001/0/712",
            "/student/course/view/#/item/#/#/#",
        ),
        # ... und heben sich von Navigation und Fußzeile ab.
        ("https://campus.thinkspace.ac.uk/student/dashboard", "/student/dashboard"),
        ("https://campus.thinkspace.ac.uk/", "/"),
    ],
)
def test_muster_ersetzt_zahlen(url, erwartet):
    assert pruefen._muster(url) == erwartet


def test_muster_fasst_lektionen_zusammen():
    basis = "https://campus.thinkspace.ac.uk/student/course/view/329/item/"
    formen = {pruefen._muster(basis + f"{n}/0/{n + 100}") for n in range(43336, 43340)}
    assert len(formen) == 1


def test_muster_laesst_sprechende_segmente_stehen():
    # Nur Zahlen werden ersetzt -- '709-htwcm-introduction' bleibt erkennbar.
    assert pruefen._muster(
        "https://campus.thinkspace.ac.uk/student/document/view/709-htwcm-introduction"
    ) == "/student/document/view/709-htwcm-introduction"


def test_muster_ohne_pfad():
    assert pruefen._muster("https://kurs.de") == "/"


# -- Mitgeschnittene Datenabrufe -----------------------------------------


class _Antwort:
    """Nachbildung einer Playwright-Response."""

    def __init__(self, url, inhalt, typ="application/json", status=200, platzt=False):
        self.url = url
        self.status = status
        self.headers = {"content-type": typ}
        self._inhalt = inhalt
        self._platzt = platzt

    def text(self):
        if self._platzt:
            raise RuntimeError("Inhalt nicht mehr verfügbar")
        return self._inhalt


KURSSTRUKTUR = (
    '{"modules":[{"id":1,"title":"Module 1","items":['
    '{"itemId":43336,"documentId":709,"title":"Welcome To The Course!"}]}]}'
)


def test_struktur_wird_an_woertern_und_kennungen_erkannt(tmp_path):
    daten = pruefen._schneide_antworten(
        [_Antwort("https://kurs.de/api/course/329", KURSSTRUKTUR)],
        tmp_path, "marke", "kurs.de",
    )
    assert len(daten) == 1
    assert daten[0]["struktur"] is True
    assert daten[0]["datei"].suffix == ".json"
    assert "Welcome To The Course!" in daten[0]["datei"].read_text(encoding="utf-8")


def test_belanglose_antwort_gilt_nicht_als_struktur(tmp_path):
    daten = pruefen._schneide_antworten(
        [_Antwort("https://kurs.de/api/ping", '{"ok":true}')],
        tmp_path, "marke", "kurs.de",
    )
    assert daten[0]["struktur"] is False


def test_strukturwoerter_ohne_kennungen_reichen_nicht(tmp_path):
    # Ein Übersetzungspaket nennt zwar "module" und "lesson", enthält aber
    # keine Kennungen -- es ist nicht die Struktur.
    daten = pruefen._schneide_antworten(
        [_Antwort("https://kurs.de/i18n/de", '{"module":"Modul","lesson":"Lektion"}')],
        tmp_path, "marke", "kurs.de",
    )
    assert daten[0]["struktur"] is False


def test_fremde_hosts_werden_nicht_mitgeschnitten(tmp_path):
    daten = pruefen._schneide_antworten(
        [_Antwort("https://cdn.fremd.de/app.js", KURSSTRUKTUR)],
        tmp_path, "marke", "kurs.de",
    )
    assert daten == []


def test_unlesbare_antwort_wird_vermerkt_statt_verschluckt(tmp_path):
    daten = pruefen._schneide_antworten(
        [_Antwort("https://kurs.de/api/x", "", platzt=True)],
        tmp_path, "marke", "kurs.de",
    )
    assert daten[0]["datei"] is None
    assert "nicht mehr verfügbar" in daten[0]["fehler"]


def test_zu_grosse_antwort_wird_nicht_gespeichert(tmp_path):
    riesig = "x" * (pruefen.MAX_ANTWORT + 1)
    daten = pruefen._schneide_antworten(
        [_Antwort("https://kurs.de/api/gross", riesig)], tmp_path, "marke", "kurs.de",
    )
    assert daten[0]["datei"] is None
    assert "zu gross" in daten[0]["fehler"]
    assert not list(tmp_path.glob("*.json"))


def test_nicht_json_bekommt_txt_endung(tmp_path):
    daten = pruefen._schneide_antworten(
        [_Antwort("https://kurs.de/app.js", "window.kurs=" + KURSSTRUKTUR,
                  typ="application/javascript")],
        tmp_path, "marke", "kurs.de",
    )
    assert daten[0]["datei"].suffix == ".txt"


def test_frame_name_kuerzt_lange_urls():
    lang = "https://kurs.de/" + "a" * 200
    name = pruefen._frame_name(type("F", (), {"url": lang})(), 2)
    assert name.startswith("Frame 2: ")
    assert name.endswith("...")
    assert len(name) < 120


def test_frame_name_ohne_url():
    name = pruefen._frame_name(type("F", (), {"url": ""})(), 1)
    assert "ohne URL" in name


# Thinkspace rendert Lektionsziele als div statt als a[href].
KURS_URL = "https://campus.thinkspace.ac.uk/student/course/view/329"


@pytest.mark.parametrize("typ", ["cd", "ic", "qz"])
@pytest.mark.parametrize("umbruch", ["<br>", "<br/>"])
def test_thinkspace_navigation_ohne_klick_auch_versteckt(typ, umbruch):
    html = (f'<div style="display:none"><div class="btn goViewItem" '
            f'courseitemid="43336" vtype="{typ}" coursereaderid="709">'
            f'<i class="icon"></i>Welcome &amp; overview{umbruch}Introduction</div></div>')
    assert pruefen.thinkspace_links(html, KURS_URL) == [{
        "href": KURS_URL + "/item/43336/0/709",
        "text": "Welcome & overview Introduction",
    }]


@pytest.mark.parametrize("typ,item,dokument", [
    ("b", "43333", "0"), ("unknown", "1", "2"),
    ("cd", "x", "709"), ("cd", "43336", ""),
    ("cd", "43336", "0"), ("cd", "0", "709"),
])
def test_thinkspace_ignoriert_ordner_und_ungueltige_ziele(typ, item, dokument):
    html = (f'<div class="goViewItem" vtype="{typ}" '
            f'courseitemid="{item}" coursereaderid="{dokument}">Titel</div>')
    assert pruefen.thinkspace_links(html, KURS_URL) == []


@pytest.mark.parametrize("url", [
    "https://example.org/student/course/view/329",
    "https://campus.thinkspace.ac.uk/student/dashboard",
])
def test_thinkspace_parser_ist_auf_kursseiten_begrenzt(url):
    html = '<div class="goViewItem" vtype="cd" courseitemid="1" coursereaderid="2">L</div>'
    assert pruefen.thinkspace_links(html, url) == []


def test_thinkspace_lektion_als_startseite_und_dom_reihenfolge():
    html = ''.join(
        f'<div class="goViewItem" vtype="cd" courseitemid="{i}" '
        f'coursereaderid="{d}">Lektion {i}</div>'
        for i, d in [(43336, 709), (54102, 1594)]
    )
    links = pruefen.thinkspace_links(html, KURS_URL + "/item/43336/0/709")
    assert [e["href"] for e in links] == [
        KURS_URL + "/item/43336/0/709", KURS_URL + "/item/54102/0/1594",
    ]


def test_sammle_links_bevorzugt_lektion_vor_groesserem_menue(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    html = ('<div class="goViewItem" vtype="cd" courseitemid="43336" '
            'coursereaderid="709">Introduction</div>')
    lektion = KURS_URL + '/item/43336/0/709'
    menue = [{"href": f"https://campus.thinkspace.ac.uk/menu/{n}", "text": "Menü"}
             for n in range(10)]
    # Ein echter Link auf dasselbe Ziel darf keine Dublette erzeugen.
    frame = SimpleNamespace(content=lambda: html,
                            evaluate=lambda js: menue + [{"href": lektion, "text": "Intro"}])
    seite = SimpleNamespace(
        on=lambda *a: None, goto=lambda *a, **k: None,
        wait_for_load_state=lambda *a, **k: None,
        wait_for_timeout=lambda *a: None, frames=[frame], close=lambda: None,
    )
    monkeypatch.setattr(pruefen.web, 'browser',
                        lambda *a, **k: nullcontext(SimpleNamespace(new_page=lambda: seite)))
    bericht, liste, gruppen = pruefen.sammle_links(
        SimpleNamespace(warte_ms=0), KURS_URL, tmp_path,
    )
    assert gruppen[0] == ('/student/course/view/#/item/#/#/#', 1)
    assert liste is not None
    assert pruefen.web.lies_liste(liste) == [(lektion, 'Introduction')]
    assert bericht.exists()
