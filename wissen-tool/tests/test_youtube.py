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
