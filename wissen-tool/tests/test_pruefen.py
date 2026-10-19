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
