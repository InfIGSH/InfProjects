"""Tests der netzunabhaengigen Teile des YouTube-Moduls."""

import pytest

from wissen import youtube


def test_waehle_spur_bevorzugt_manuelle_untertitel():
    info = {
        "subtitles": {"de": [{"ext": "vtt", "url": "https://m/de.vtt"}]},
        "automatic_captions": {"de": [{"ext": "vtt", "url": "https://a/de.vtt"}]},
    }
    sprache, ext, url, automatisch = youtube._waehle_spur(info, ["de", "en"])
    assert (sprache, ext, url, automatisch) == ("de", "vtt", "https://m/de.vtt", False)


def test_waehle_spur_nimmt_automatische_wenn_nichts_anderes_da_ist():
    info = {"automatic_captions": {"de": [{"ext": "json3", "url": "https://a/de.json"}]}}
    sprache, ext, _, automatisch = youtube._waehle_spur(info, ["de"])
    assert (sprache, ext, automatisch) == ("de", "json3", True)


def test_waehle_spur_haelt_die_sprachreihenfolge_ein():
    info = {
        "subtitles": {
            "en": [{"ext": "vtt", "url": "https://m/en.vtt"}],
            "de": [{"ext": "vtt", "url": "https://m/de.vtt"}],
        }
    }
    assert youtube._waehle_spur(info, ["de", "en"])[0] == "de"
    assert youtube._waehle_spur(info, ["en", "de"])[0] == "en"


def test_waehle_spur_akzeptiert_grundsprache_statt_regionalvariante():
    info = {"subtitles": {"de": [{"ext": "vtt", "url": "https://m/de.vtt"}]}}
    assert youtube._waehle_spur(info, ["de-DE"])[0] == "de"


# -- Vimeos Spurbenennung ------------------------------------------------
# Echter Fall aus einer Thinkspace-Lektion: die einzige Spur heißt
# 'en-x-autogen' und steht unter den regulären Untertiteln, nicht unter den
# automatischen.

VIMEO_INFO = {
    "title": "HTWCM VT0.1 - Intro",
    "duration": 509,
    "subtitles": {"en-x-autogen": [{"ext": "vtt", "url": "https://v/en.vtt"}]},
    "automatic_captions": {},
}


def test_waehle_spur_findet_vimeos_autogen_spur():
    # Ein exakter Vergleich auf 'en'/'en-US' übersieht sie -- und der Abruf
    # bräche ab, obwohl die Spur vorhanden ist.
    sprache, ext, url, automatisch = youtube._waehle_spur(
        VIMEO_INFO, ["en", "en-US", "de", "de-DE"]
    )
    assert sprache == "en-x-autogen"
    assert ext == "vtt"
    assert url == "https://v/en.vtt"


def test_vimeos_autogen_spur_gilt_als_automatisch():
    # Sonst stünde "Untertitel vom Kanal" im Kopf und der Text wirkte
    # verlässlicher als er ist -- relevant für die (?)-Markierungen.
    assert youtube._waehle_spur(VIMEO_INFO, ["en"])[3] is True


@pytest.mark.parametrize(
    "schluessel", ["en-x-autogen", "de-x-autogen", "EN-X-AUTOGEN", "en-auto", "en-asr"]
)
def test_ist_autogen_erkennt_maschinenspuren(schluessel):
    assert youtube.ist_autogen(schluessel)


@pytest.mark.parametrize("schluessel", ["en", "en-US", "de-DE", "", None])
def test_ist_autogen_bei_echten_spuren(schluessel):
    assert not youtube.ist_autogen(schluessel)


def test_echte_spur_gewinnt_gegen_autogen():
    info = {
        "subtitles": {
            "en-x-autogen": [{"ext": "vtt", "url": "https://v/auto.vtt"}],
            "en": [{"ext": "vtt", "url": "https://v/echt.vtt"}],
        }
    }
    sprache, _, url, automatisch = youtube._waehle_spur(info, ["en"])
    assert (sprache, url, automatisch) == ("en", "https://v/echt.vtt", False)


def test_regionalvariante_gewinnt_gegen_autogen():
    info = {
        "subtitles": {
            "en-x-autogen": [{"ext": "vtt", "url": "https://v/auto.vtt"}],
            "en-GB": [{"ext": "vtt", "url": "https://v/gb.vtt"}],
        }
    }
    assert youtube._waehle_spur(info, ["en"])[0] == "en-GB"


def test_passende_schluessel_reihenfolge():
    vorhanden = ["en-x-autogen", "en-GB", "en", "de"]
    assert youtube.passende_schluessel(vorhanden, "en") == [
        "en", "en-GB", "en-x-autogen",
    ]


def test_passende_schluessel_ohne_treffer():
    assert youtube.passende_schluessel(["fr", "it"], "de") == []


def test_spuren_auflisten_weist_autogen_als_automatisch_aus(monkeypatch):
    # Der Bericht von `wissen inspect` soll nicht behaupten, Vimeo habe die
    # Spur selbst erstellt.
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: VIMEO_INFO)
    spuren = youtube.spuren_auflisten("https://player.vimeo.com/video/1")
    assert spuren["titel"] == "HTWCM VT0.1 - Intro"
    assert spuren["dauer"] == 509
    assert spuren["manuell"] == []
    assert spuren["automatisch"] == ["en-x-autogen"]


def test_spuren_auflisten_fasst_beide_quellen_zusammen(monkeypatch):
    info = {
        "title": "T", "duration": 60,
        "subtitles": {"en": [{}], "de-x-autogen": [{}]},
        "automatic_captions": {"fr": [{}]},
    }
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: info)
    spuren = youtube.spuren_auflisten("https://x")
    assert spuren["manuell"] == ["en"]
    assert spuren["automatisch"] == ["de-x-autogen", "fr"]


def test_referer_wird_als_kopfzeile_gesetzt():
    # Domainbeschränkte Embeds antworten ohne passenden Referer nicht.
    assert youtube._referer_opts("https://kurs.de/l") == {
        "http_headers": {"Referer": "https://kurs.de/l"}
    }
    assert youtube._referer_opts(None) == {}


def test_waehle_spur_bevorzugt_vtt_vor_json3():
    info = {
        "subtitles": {
            "de": [
                {"ext": "json3", "url": "https://m/de.json"},
                {"ext": "vtt", "url": "https://m/de.vtt"},
            ]
        }
    }
    assert youtube._waehle_spur(info, ["de"])[1] == "vtt"


def test_waehle_spur_nennt_vorhandene_sprachen_im_fehler():
    info = {"subtitles": {"fr": [{"ext": "vtt", "url": "x"}]}, "automatic_captions": {}}
    with pytest.raises(youtube.YoutubeFehler, match="fr"):
        youtube._waehle_spur(info, ["de"])


def test_waehle_format_bleibt_unter_der_hoehengrenze():
    info = {
        "formats": [
            {"vcodec": "none", "acodec": "mp4a", "url": "a", "height": None},
            {"vcodec": "avc1", "url": "v360", "height": 360, "tbr": 500},
            {"vcodec": "avc1", "url": "v720", "height": 720, "tbr": 1500},
            {"vcodec": "avc1", "url": "v1080", "height": 1080, "tbr": 3000},
        ]
    }
    assert youtube._waehle_format(info, max_hoehe=720)["url"] == "v720"
    assert youtube._waehle_format(info, max_hoehe=400)["url"] == "v360"


def test_waehle_format_nimmt_notfalls_ein_groesseres():
    info = {"formats": [{"vcodec": "avc1", "url": "v1080", "height": 1080, "tbr": 3000}]}
    assert youtube._waehle_format(info, max_hoehe=720)["url"] == "v1080"


def test_waehle_format_ueberspringt_fragmentierte_streams():
    info = {
        "formats": [
            {"vcodec": "avc1", "url": "hls", "height": 720, "fragments": [{}]},
            {"vcodec": "avc1", "url": "direkt", "height": 480},
        ]
    }
    assert youtube._waehle_format(info)["url"] == "direkt"


def test_waehle_format_ohne_video_meldet_fehler():
    with pytest.raises(youtube.YoutubeFehler):
        youtube._waehle_format({"formats": [{"vcodec": "none", "url": "a"}]})


BODY = """# Titel

## Transkript

[00:00] Anfang.

[00:30] Mitte.

[01:00] Ende.
"""


def test_bild_einfuegen_setzt_bild_hinter_den_passenden_absatz():
    neu = youtube._bild_einfuegen(BODY, "../assets/x/00-35.jpg", 35)
    absaetze = [a.strip() for a in neu.split("\n\n") if a.strip()]
    nr = absaetze.index("![Screenshot bei 00:35](../assets/x/00-35.jpg)")
    assert absaetze[nr - 1].startswith("[00:30]")
    assert absaetze[nr + 1].startswith("[01:00]")


def test_bild_einfuegen_haengt_hinten_an_wenn_zeit_hinter_dem_text_liegt():
    neu = youtube._bild_einfuegen(BODY, "bild.jpg", 5000)
    assert neu.rstrip().endswith("![Screenshot bei 01:23:20](bild.jpg)")


def test_bild_einfuegen_ist_wiederholbar():
    einmal = youtube._bild_einfuegen(BODY, "bild.jpg", 35)
    zweimal = youtube._bild_einfuegen(einmal, "bild.jpg", 35)
    assert einmal == zweimal


def test_bild_einfuegen_ohne_zeitmarken():
    neu = youtube._bild_einfuegen("# Nur Text\n\nOhne Marken.", "bild.jpg", 35)
    assert neu.rstrip().endswith("![Screenshot bei 00:35](bild.jpg)")
