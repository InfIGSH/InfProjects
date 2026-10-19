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


# -- URL-Listen ----------------------------------------------------------


def test_lies_liste_trennt_url_und_titel(tmp_path):
    datei = tmp_path / "modul2.txt"
    datei.write_text(
        "# Kommentarzeile wird übersprungen\n"
        "\n"
        "https://kurs.de/l1 | Introduction and Overview\n"
        "https://kurs.de/l2|How to Write a Melody\n"
        "https://kurs.de/l3\n"
        "   \n",
        encoding="utf-8",
    )
    assert web.lies_liste(datei) == [
        ("https://kurs.de/l1", "Introduction and Overview"),
        ("https://kurs.de/l2", "How to Write a Melody"),
        ("https://kurs.de/l3", None),
    ]


def test_lies_liste_bei_leerem_titel_nach_strich(tmp_path):
    datei = tmp_path / "l.txt"
    datei.write_text("https://kurs.de/l1 |  \n", encoding="utf-8")
    assert web.lies_liste(datei) == [("https://kurs.de/l1", None)]


def _ablage_mit(tmp_path, urls):
    from wissen.store import Ablage

    root = tmp_path / "buch"
    root.mkdir(parents=True)
    (root / "ANLEITUNG.md").write_text("# A", encoding="utf-8")
    ablage = Ablage(root)
    ablage.init()
    for nr, url in enumerate(urls):
        ablage.schreibe(
            {"Titel": f"L{nr}", "URL": url}, "x", ablage.eingang_pfad("kurs", str(nr))
        )
    return ablage


def test_fertige_liste_oeffnet_keinen_browser(tmp_path, monkeypatch):
    # Ein zweiter Durchlauf über eine fertige Liste soll nichts aufmachen.
    def nicht_aufrufen(*a, **k):
        raise AssertionError("Der Browser wurde geöffnet, obwohl nichts offen war.")

    monkeypatch.setattr(web, "browser", nicht_aufrufen)
    ablage = _ablage_mit(tmp_path, ["https://kurs.de/l1", "https://kurs.de/l2"])
    datei = tmp_path / "liste.txt"
    datei.write_text("https://kurs.de/l1\nhttps://kurs.de/l2/\n", encoding="utf-8")

    ergebnisse, uebersprungen = web.lade_liste(
        _cfg(tmp_path), ablage, datei, praefix="kurs"
    )
    assert ergebnisse == []
    # Der Schlussstrich in Zeile 2 darf den Abgleich nicht aushebeln.
    assert len(uebersprungen) == 2


def test_neu_laden_uebergeht_den_dublettenschutz(tmp_path, monkeypatch):
    geoeffnet = []

    class _Kontext:
        def __enter__(self):
            geoeffnet.append(True)
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(web, "browser", lambda *a, **k: _Kontext())
    monkeypatch.setattr(
        web, "lade_seite",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Abruf hier nicht nötig")),
    )
    ablage = _ablage_mit(tmp_path, ["https://kurs.de/l1"])
    datei = tmp_path / "liste.txt"
    datei.write_text("https://kurs.de/l1\n", encoding="utf-8")

    ergebnisse, uebersprungen = web.lade_liste(
        _cfg(tmp_path), ablage, datei, praefix="kurs", neu_laden=True
    )
    assert uebersprungen == []
    assert geoeffnet == [True]
    assert ergebnisse == []  # lade_seite scheitert absichtlich, wird gefangen


# -- Transkript aus dem eingebetteten Player -----------------------------

VIDEO = ("https://player.vimeo.com/video/957204710?h=4f2cb2a359", "Vimeo")
SEITE = "https://campus.thinkspace.ac.uk/student/course/view/329/item/43336/0/709"


def _cfg(tmp_path):
    from wissen.config import Konfig

    return Konfig(
        ablage=tmp_path, browser_profil=tmp_path / "p",
        sprachen=["en", "en-US", "de", "de-DE"],
    )


def _spur(bis: int, dauer: int | None):
    from wissen import vtt as vtt_modul

    kacheln = [
        vtt_modul.Kachel(i, i + 5, f"Satz {i}") for i in range(0, bis + 1, 5)
    ]
    return {
        "info": {"title": "HTWCM VT0.1 - Intro", "duration": dauer},
        "kacheln": kacheln,
        "sprache": "en-x-autogen",
        "automatisch": True,
    }


def test_player_transkript_schreibt_die_abdeckungszeile(tmp_path, monkeypatch):
    # Echte Werte der Thinkspace-Lektion: 509 s Video, Spur bis 505 s.
    from wissen import youtube

    monkeypatch.setattr(
        youtube, "spur_laden", lambda *a, **k: _spur(500, 509)
    )
    text, felder, nachricht = web._transkript_vom_player(
        _cfg(tmp_path), VIDEO, SEITE, {}
    )
    assert felder["Abdeckung"] == "Transkript 0:00–8:25 von 8:29 (Auto-Captions)"
    assert felder["Video"] == f"Vimeo: {VIDEO[0]}"
    assert text.startswith("[00:00] ")
    assert "Vimeo-Player geholt" in nachricht


def test_player_transkript_meldet_luecke_zum_videoende(tmp_path, monkeypatch):
    from wissen import youtube

    monkeypatch.setattr(youtube, "spur_laden", lambda *a, **k: _spur(200, 509))
    _, felder, _ = web._transkript_vom_player(_cfg(tmp_path), VIDEO, SEITE, {})
    assert "UNVOLLSTÄNDIG" in felder["Abdeckung"]
    # Gemessen wird ab dem Ende der letzten Kachel (205 s), nicht ab ihrem Start.
    assert "304 s fehlen" in felder["Abdeckung"]


def test_player_transkript_ohne_bekannte_videolaenge(tmp_path, monkeypatch):
    from wissen import youtube

    monkeypatch.setattr(youtube, "spur_laden", lambda *a, **k: _spur(200, None))
    _, felder, _ = web._transkript_vom_player(_cfg(tmp_path), VIDEO, SEITE, {})
    assert felder["Abdeckung"] == "Transkript 0:00–3:25 (Auto-Captions)"
    assert "UNVOLLSTÄNDIG" not in felder["Abdeckung"]


def test_player_transkript_bei_nicht_abrufbarer_spur(tmp_path, monkeypatch):
    from wissen import youtube

    def platzt(*a, **k):
        raise youtube.YoutubeFehler("Vimeo verweigert die Auskunft")

    monkeypatch.setattr(youtube, "spur_laden", platzt)
    text, felder, nachricht = web._transkript_vom_player(
        _cfg(tmp_path), VIDEO, SEITE, {}
    )
    assert text == ""
    assert "KEIN Transkript" in felder["Abdeckung"]
    # Die Player-URL bleibt im Kopf stehen, auch wenn der Abruf scheitert --
    # sonst ist später nicht nachvollziehbar, woran es lag.
    assert felder["Video"] == f"Vimeo: {VIDEO[0]}"
    assert "verweigert die Auskunft" in nachricht
