"""Tests der netzunabhaengigen Teile des YouTube-Moduls."""

import pytest

from wissen import youtube


def _beste_spur(info, sprachen):
    """Die Spur, die `spur_laden` zuerst versuchen wuerde.

    Der Abruf probiert alle Kandidaten der Reihe nach; welcher vorn steht,
    entscheidet aber weiterhin ueber Sprache, Format und die Einordnung als
    maschinell -- darum hier gezielt der erste.
    """
    kandidaten = youtube.spur_kandidaten(info, sprachen)
    if not kandidaten:
        vorhanden = sorted(
            set(info.get("subtitles") or {}) | set(info.get("automatic_captions") or {})
        )
        raise youtube.YoutubeFehler(
            f"Keine Spur fuer {sprachen}. Vorhanden: {', '.join(vorhanden) or 'keine'}."
        )
    return kandidaten[0]


def test_waehle_spur_bevorzugt_manuelle_untertitel():
    info = {
        "subtitles": {"de": [{"ext": "vtt", "url": "https://m/de.vtt"}]},
        "automatic_captions": {"de": [{"ext": "vtt", "url": "https://a/de.vtt"}]},
    }
    sprache, ext, url, automatisch = _beste_spur(info, ["de", "en"])
    assert (sprache, ext, url, automatisch) == ("de", "vtt", "https://m/de.vtt", False)


def test_waehle_spur_nimmt_automatische_wenn_nichts_anderes_da_ist():
    info = {"automatic_captions": {"de": [{"ext": "json3", "url": "https://a/de.json"}]}}
    sprache, ext, _, automatisch = _beste_spur(info, ["de"])
    assert (sprache, ext, automatisch) == ("de", "json3", True)


def test_waehle_spur_haelt_die_sprachreihenfolge_ein():
    info = {
        "subtitles": {
            "en": [{"ext": "vtt", "url": "https://m/en.vtt"}],
            "de": [{"ext": "vtt", "url": "https://m/de.vtt"}],
        }
    }
    assert _beste_spur(info, ["de", "en"])[0] == "de"
    assert _beste_spur(info, ["en", "de"])[0] == "en"


def test_waehle_spur_akzeptiert_grundsprache_statt_regionalvariante():
    info = {"subtitles": {"de": [{"ext": "vtt", "url": "https://m/de.vtt"}]}}
    assert _beste_spur(info, ["de-DE"])[0] == "de"


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
    sprache, ext, url, automatisch = _beste_spur(
        VIMEO_INFO, ["en", "en-US", "de", "de-DE"]
    )
    assert sprache == "en-x-autogen"
    assert ext == "vtt"
    assert url == "https://v/en.vtt"


def test_vimeos_autogen_spur_gilt_als_automatisch():
    # Sonst stünde "Untertitel vom Kanal" im Kopf und der Text wirkte
    # verlässlicher als er ist -- relevant für die (?)-Markierungen.
    assert _beste_spur(VIMEO_INFO, ["en"])[3] is True


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
    sprache, _, url, automatisch = _beste_spur(info, ["en"])
    assert (sprache, url, automatisch) == ("en", "https://v/echt.vtt", False)


def test_regionalvariante_gewinnt_gegen_autogen():
    info = {
        "subtitles": {
            "en-x-autogen": [{"ext": "vtt", "url": "https://v/auto.vtt"}],
            "en-GB": [{"ext": "vtt", "url": "https://v/gb.vtt"}],
        }
    }
    assert _beste_spur(info, ["en"])[0] == "en-GB"


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


# -- Mehrere Kandidaten, Rückfall und Diagnose ---------------------------

VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHallo Welt.\n"


def test_spur_kandidaten_haelt_die_reihenfolge():
    info = {
        "subtitles": {
            "en-x-autogen": [{"ext": "vtt", "url": "u-auto"}],
            "en": [{"ext": "json3", "url": "u-json"}, {"ext": "vtt", "url": "u-vtt"}],
        },
        "automatic_captions": {"en": [{"ext": "vtt", "url": "u-asr"}]},
    }
    kandidaten = youtube.spur_kandidaten(info, ["en"])
    # Exakte Sprache vor autogen; vtt vor json3; manuell vor maschinell.
    assert [(k[0], k[2]) for k in kandidaten] == [
        ("en", "u-vtt"), ("en", "u-json"), ("en-x-autogen", "u-auto"), ("en", "u-asr"),
    ]


def test_spur_kandidaten_ohne_passende_sprache():
    info = {"subtitles": {"fr": [{"ext": "vtt", "url": "u"}]}}
    assert youtube.spur_kandidaten(info, ["de"]) == []


def test_spur_laden_nimmt_die_naechste_spur_wenn_die_erste_leer_ist(monkeypatch):
    # Der eigentliche Zweck des Rückfalls: eine gefundene Spur kann leer
    # zurückkommen, ohne dass der Abruf fehlschlägt.
    info = {
        "subtitles": {
            "en": [{"ext": "vtt", "url": "leer"}],
            "en-x-autogen": [{"ext": "vtt", "url": "voll"}],
        }
    }
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: info)
    monkeypatch.setattr(
        youtube, "abrufen",
        lambda u, referer=None: ("", "0 Bytes") if u == "leer" else (VTT, "48 Bytes"),
    )
    spur = youtube.spur_laden("https://x", ["en"])
    assert spur["sprache"] == "en-x-autogen"
    assert spur["automatisch"] is True
    assert [k.text for k in spur["kacheln"]] == ["Hallo Welt."]


def test_spur_laden_nennt_jeden_grund_wenn_alle_scheitern(monkeypatch):
    info = {
        "subtitles": {
            "en": [{"ext": "vtt", "url": "a"}],
            "en-x-autogen": [{"ext": "vtt", "url": "b"}],
        }
    }
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: info)
    monkeypatch.setattr(
        youtube, "abrufen",
        lambda u, referer=None: ("", f"0 Bytes, Content-Type ?, Anfang: '' ({u})"),
    )
    with pytest.raises(youtube.YoutubeFehler) as fehler:
        youtube.spur_laden("https://x", ["en"])
    meldung = str(fehler.value)
    assert "en/vtt" in meldung and "en-x-autogen/vtt" in meldung
    assert "(a)" in meldung and "(b)" in meldung


def test_spur_laden_meldet_unpassende_sprachen_getrennt(monkeypatch):
    info = {"subtitles": {"fr": [{"ext": "vtt", "url": "u"}]}}
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: info)
    with pytest.raises(youtube.YoutubeFehler, match="Vorhanden: fr"):
        youtube.spur_laden("https://x", ["de"])


def test_spur_laden_meldet_html_statt_untertitel(monkeypatch):
    # Eine Fehlerseite ist nicht dasselbe wie eine leere Antwort -- die
    # Diagnose muss das unterscheidbar machen.
    info = {"subtitles": {"en": [{"ext": "vtt", "url": "u"}]}}
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: info)
    monkeypatch.setattr(
        youtube, "abrufen",
        lambda u, referer=None: (
            "<!DOCTYPE html><html>...",
            "512 Bytes, Content-Type text/html, Anfang: '<!DOCTYPE html>'",
        ),
    )
    with pytest.raises(youtube.YoutubeFehler, match="text/html"):
        youtube.spur_laden("https://x", ["en"])


def test_abrufen_beschreibt_einen_fehlgeschlagenen_abruf(monkeypatch):
    class _Platzt:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def urlopen(self, url):
            raise OSError("Verbindung abgewiesen")

    monkeypatch.setattr(youtube, "_ydl", lambda extra=None: _Platzt())
    text, diagnose = youtube.abrufen("https://x/spur.vtt")
    assert text == ""
    assert "OSError" in diagnose
    assert "Verbindung abgewiesen" in diagnose


def test_abrufen_beschreibt_eine_erfolgreiche_antwort(monkeypatch):
    class _Antwort:
        headers = {"Content-Type": "text/vtt"}

        def read(self):
            return VTT.encode("utf-8")

    class _Ydl:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def urlopen(self, url):
            return _Antwort()

    monkeypatch.setattr(youtube, "_ydl", lambda extra=None: _Ydl())
    text, diagnose = youtube.abrufen("https://x/spur.vtt")
    assert text == VTT
    assert "text/vtt" in diagnose
    assert f"{len(VTT.encode())} Bytes" in diagnose
    assert "WEBVTT" in diagnose


# -- Vimeos dreifach angebotene Spur -------------------------------------
# Echter Fall: dieselbe Spur kommt als zwei HLS-Playlists und eine direkte
# VTT-Datei. Alle drei tragen ext "vtt".

HLS = (
    "#EXTM3U\n#EXT-X-TARGETDURATION:510\n#EXT-X-ALLOW-CACHE:YES\n"
    "#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-VERSION:3\n#EXT-X-MEDIA-SEQUENCE:1\n"
    "#EXTINF:509.680000,\n../../../texttrack/sub/180737587.vtt?pathsig=8c953e4f\n"
    "#EXT-X-ENDLIST\n"
)

VIMEO_DREIFACH = {
    "title": "HTWCM VT0.1 - Intro",
    "duration": 509,
    "subtitles": {
        "en-x-autogen": [
            {"ext": "vtt", "url": "https://vimeo.com/texttrack/playlist/1.m3u8"},
            {"ext": "vtt", "url": "https://vimeo.com/texttrack/playlist/2.m3u8"},
            {"ext": "vtt", "url": "https://vimeo.com/texttrack/sub/180737587.vtt"},
        ]
    },
}


def test_direkte_vtt_url_kommt_vor_der_hls_huelle():
    # Sonst drei Abrufe, wo einer reicht -- bei 40-60 Lektionen je Kurs zählt das.
    kandidaten = youtube.spur_kandidaten(VIMEO_DREIFACH, ["en"])
    assert [k[2] for k in kandidaten] == [
        "https://vimeo.com/texttrack/sub/180737587.vtt",
        "https://vimeo.com/texttrack/playlist/1.m3u8",
        "https://vimeo.com/texttrack/playlist/2.m3u8",
    ]


def test_spur_laden_braucht_nur_einen_abruf(monkeypatch):
    abrufe = []
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: VIMEO_DREIFACH)

    def abrufen(u, referer=None):
        abrufe.append(u)
        return (VTT, "x") if u.endswith(".vtt") else (HLS, "x")

    monkeypatch.setattr(youtube, "abrufen", abrufen)
    spur = youtube.spur_laden("https://player.vimeo.com/video/1", ["en"])
    assert len(spur["kacheln"]) == 1
    assert len(abrufe) == 1


@pytest.mark.parametrize(
    "url,rang",
    [
        ("https://v/texttrack/sub/1.vtt", 0),
        ("https://v/sub/1.vtt?pathsig=abc", 0),
        ("https://v/sub/1.srt", 0),
        ("https://www.youtube.com/api/timedtext?fmt=vtt", 1),
        ("https://v/playlist/1.m3u8", 2),
        ("https://v/playlist/1.m3u8?token=x", 2),
    ],
)
def test_url_rang(url, rang):
    assert youtube._url_rang(url) == rang


# -- Der HLS-Hülle folgen ------------------------------------------------


def test_hls_huelle_wird_erkannt():
    assert youtube._ist_hls(HLS)
    assert not youtube._ist_hls(VTT)
    assert not youtube._ist_hls("")


def test_hls_ziele_werden_absolut_gemacht():
    # Die Verweise in der Playlist sind relativ ('../../../texttrack/...')
    # und tragen eine Signatur im Abfrageteil, die erhalten bleiben muss.
    ziele = youtube._hls_ziele(HLS, "https://vimeo.com/a/b/c/d/playlist.m3u8")
    assert ziele == [
        "https://vimeo.com/a/texttrack/sub/180737587.vtt?pathsig=8c953e4f"
    ]


def test_hls_ziele_ignoriert_die_kommentarzeilen():
    # Alles mit '#' ist Metadaten, nur die nackten Zeilen sind Verweise.
    assert len(youtube._hls_ziele(HLS, "https://v/p.m3u8")) == 1


def test_spur_laden_folgt_der_hls_huelle_wenn_es_nichts_anderes_gibt(monkeypatch):
    # Bietet ein Video die Spur nur als Playlist an, steht der Weg zur
    # Untertiteldatei darin -- dem wird jetzt gefolgt.
    info = {
        "duration": 509,
        "subtitles": {
            "en-x-autogen": [
                {"ext": "vtt", "url": "https://vimeo.com/texttrack/playlist/1.m3u8"}
            ]
        },
    }
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: info)
    monkeypatch.setattr(
        youtube, "abrufen",
        lambda u, referer=None: (HLS, "277 Bytes") if u.endswith(".m3u8")
        else (VTT, "14203 Bytes"),
    )
    spur = youtube.spur_laden("https://player.vimeo.com/video/1", ["en"])
    assert [k.text for k in spur["kacheln"]] == ["Hallo Welt."]
    assert "HLS-Playlist gefolgt" in spur["diagnose"]


def test_hls_huelle_ohne_lesbares_ziel_wird_gemeldet(monkeypatch):
    info = {
        "subtitles": {
            "en": [{"ext": "vtt", "url": "https://v/playlist/1.m3u8"}]
        }
    }
    monkeypatch.setattr(youtube, "_info", lambda url, referer=None: info)
    monkeypatch.setattr(
        youtube, "abrufen",
        lambda u, referer=None: (HLS, "277 Bytes") if u.endswith(".m3u8")
        else ("", "0 Bytes"),
    )
    with pytest.raises(youtube.YoutubeFehler, match="HLS-Playlist verwies"):
        youtube.spur_laden("https://x", ["en"])


def test_hls_folge_laeuft_nicht_im_kreis(monkeypatch):
    # Eine Playlist, die auf sich selbst verweist, darf nicht endlos laufen.
    kreis = "#EXTM3U\n#EXTINF:1,\n1.m3u8\n"
    monkeypatch.setattr(youtube, "abrufen", lambda u, referer=None: (kreis, "x"))
    kacheln, zusatz = youtube._kacheln_aus(
        kreis, "vtt", "https://v/playlist/1.m3u8", None
    )
    assert kacheln == []
    assert "keine lesbare Spur" in zusatz


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
    assert _beste_spur(info, ["de"])[1] == "vtt"


def test_waehle_spur_nennt_vorhandene_sprachen_im_fehler():
    info = {"subtitles": {"fr": [{"ext": "vtt", "url": "x"}]}, "automatic_captions": {}}
    with pytest.raises(youtube.YoutubeFehler, match="fr"):
        _beste_spur(info, ["de"])


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
