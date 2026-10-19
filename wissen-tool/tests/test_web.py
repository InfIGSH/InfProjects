"""Tests der netzunabhängigen Teile des Kursseiten-Moduls."""

import pytest

from wissen import web


# -- Sperrliste ----------------------------------------------------------
# ANLEITUNG.md: "keine Fortschritts-/'Mark as done'-Buttons anklicken".
# Die Sperrliste greift auch dann, wenn ein konfigurierter Selektor
# versehentlich auf so einen Knopf passt.


@pytest.mark.parametrize(
    "text",
    [
        "Mark as complete",
        "Mark as Done",
        "Lektion abgeschlossen",
        "Als gelesen markieren",
        "Complete and continue",
        "Next lesson",
        "Nächste Lektion",
        "Weiter zu Modul 3",
        "Submit quiz",
        "Enroll now",
        "Log out",
        "Löschen",
    ],
)
def test_fortschritts_und_navigationsknoepfe_sind_gesperrt(text):
    assert web.ist_verboten(text)


@pytest.mark.parametrize(
    "text",
    [
        "Transkript anzeigen",
        "Show transcript",
        "Transcript",
        "Untertitel einblenden",
        "Play",
        "",
        "   ",
    ],
)
def test_harmlose_knoepfe_sind_erlaubt(text):
    assert not web.ist_verboten(text)


def test_sperrliste_ignoriert_gross_schreibung():
    assert web.ist_verboten("MARK AS COMPLETE")
    assert web.ist_verboten("  Abgeschlossen  ")


def test_sperrliste_vertraegt_none():
    assert not web.ist_verboten(None)


# -- Hilfsfunktionen -----------------------------------------------------


def test_letzte_zeitmarke_nimmt_die_groesste():
    text = "0:00 Anfang\n4:12 Mitte\n12:57 Ende"
    assert web._letzte_zeitmarke(text) == 777


def test_letzte_zeitmarke_mit_stunden():
    assert web._letzte_zeitmarke("0:30 x\n1:02:03 y") == 3723


def test_letzte_zeitmarke_ohne_marken():
    assert web._letzte_zeitmarke("nur Text ohne Zeiten") is None


def test_aufraeumen_fasst_leerzeilen_zusammen():
    assert web._aufraeumen("a\n\n\n\nb\n  \n") == "a\n\nb"


def test_aufraeumen_trimmt_aussen_und_behaelt_einrueckung_innen():
    # Außen abschneiden, aber Einrückung innerhalb des Textes nicht antasten --
    # in Transkripten trägt sie manchmal Struktur (Sprecherwechsel, Listen).
    assert web._aufraeumen("  a   \n    b  \n\n") == "a\n    b"


def test_host_ohne_www():
    assert web._host("https://www.youtube.com/watch?v=x") == "youtube.com"
    assert web._host("https://campus.thinkspace.ac.uk/c/329") == "campus.thinkspace.ac.uk"


# -- Frames ---------------------------------------------------------------


class _FakeElement:
    def __init__(self, text):
        self._text = text

    def inner_text(self):
        return self._text


class _FakeFrame:
    """Nachbildung eines Playwright-Frames, soweit die Tests ihn brauchen."""

    def __init__(self, url="", texte=None, html=""):
        self.url = url
        self._texte = texte or {}
        self._html = html

    def query_selector(self, selektor):
        text = self._texte.get(selektor)
        return _FakeElement(text) if text else None

    def content(self):
        return self._html


class _FakeSeite:
    def __init__(self, frames):
        self.frames = frames


def test_rahmen_zaehlt_das_hauptdokument_nicht_doppelt():
    # page.frames enthält den Hauptframe bereits an Position 0.
    haupt = _FakeFrame(url="https://kurs.de/lektion")
    eingebettet = _FakeFrame(url="https://player.vimeo.com/video/1")
    rahmen = web.rahmen_von(_FakeSeite([haupt, eingebettet]))
    assert rahmen == [haupt, eingebettet]


@pytest.mark.parametrize(
    "url,anbieter",
    [
        ("https://player.vimeo.com/video/957204710?h=4f2cb2a359", "Vimeo"),
        ("https://www.youtube.com/embed/abc123", "YouTube"),
        ("https://www.youtube-nocookie.com/embed/abc123", "YouTube"),
        ("https://fast.wistia.net/embed/iframe/abc1234567", "Wistia"),
    ],
)
def test_finde_video_erkennt_die_gaengigen_player(url, anbieter):
    rahmen = [_FakeFrame(url="https://kurs.de/lektion"), _FakeFrame(url=url)]
    assert web.finde_video(rahmen) == (url, anbieter)


def test_erkannte_player_haben_einen_yt_dlp_extraktor():
    """Die Muster nützen nur, wenn yt-dlp die URL danach auch annimmt."""
    from yt_dlp.extractor import gen_extractor_classes

    klassen = [k for k in gen_extractor_classes() if k.IE_NAME != "generic"]
    beispiele = [
        "https://player.vimeo.com/video/957204710?h=4f2cb2a359",
        "https://www.youtube.com/embed/abc12345678",
        "https://fast.wistia.net/embed/iframe/abc1234567",
    ]
    for url in beispiele:
        assert web.finde_video([_FakeFrame(url=url)]) is not None, url
        assert any(k.suitable(url) for k in klassen), url


def test_finde_video_entfernt_den_zeitanker():
    # Der Anker ist nur die Abspielposition und verwirrt manche Extraktoren.
    url = "https://player.vimeo.com/video/957204710?h=4f2cb2a359#t=00h07m05s"
    gefunden, _ = web.finde_video([_FakeFrame(url=url)])
    assert gefunden == "https://player.vimeo.com/video/957204710?h=4f2cb2a359"


def test_finde_video_ohne_player():
    assert web.finde_video([_FakeFrame(url="https://kurs.de/lektion")]) is None


def test_hauptinhalt_nimmt_den_textreichsten_frame():
    # Kursplattformen laden den Lektionstext in ein eigenes iframe; im
    # Hauptdokument steht dann nur die Navigationshülle.
    huelle = _FakeFrame(url="https://kurs.de/lektion", texte={"body": "Navigation " * 12})
    inhalt = _FakeFrame(
        url="https://kurs.de/document/view/709",
        texte={"body": "Der eigentliche Lektionstext. " * 40},
    )
    text = web._hauptinhalt([huelle, inhalt], {})
    assert "eigentliche Lektionstext" in text
    assert "Navigation" not in text


def test_hauptinhalt_bevorzugt_den_konfigurierten_selektor():
    # Auch wenn sein Text kürzer ist als die Navigationsspalte: wer den
    # Selektor einträgt, weiß besser, wo der Lektionstext steht.
    frame = _FakeFrame(
        url="https://kurs.de/l",
        texte={"body": "alles inklusive Navigation " * 20,
               "div.lesson": "kurz"},
    )
    text = web._hauptinhalt([frame], {"inhalt": ["div.lesson"]})
    assert text == "kurz"


def test_hauptinhalt_sucht_den_konfigurierten_selektor_in_allen_frames():
    huelle = _FakeFrame(url="https://kurs.de/l", texte={"body": "Navigation " * 20})
    inhalt = _FakeFrame(
        url="https://kurs.de/document/view/709",
        texte={"div.lesson": "Der Lektionstext."},
    )
    assert web._hauptinhalt([huelle, inhalt], {"inhalt": ["div.lesson"]}) == (
        "Der Lektionstext."
    )


def test_hauptinhalt_faellt_auf_heuristik_zurueck_wenn_selektor_nicht_passt():
    frame = _FakeFrame(url="https://kurs.de/l", texte={"body": "Lektionstext " * 20})
    text = web._hauptinhalt([frame], {"inhalt": ["div.gibt-es-nicht"]})
    assert "Lektionstext" in text


def test_hauptinhalt_ohne_text():
    assert web._hauptinhalt([_FakeFrame(url="https://kurs.de/l")], {}) == ""
