from wissen import vtt

# So sehen YouTubes automatische Untertitel aus: ein rollendes Fenster, in dem
# jede Kachel die vorige Zeile wiederholt, plus Wort-Zeitstempel als Tags.
AUTO_VTT = """WEBVTT
Kind: captions
Language: de

00:00:00.120 --> 00:00:02.500 align:start position:0%
heute geht es um

00:00:02.500 --> 00:00:05.000 align:start position:0%
heute geht es um <00:00:03.100>Variablen <00:00:04.200>in Python

00:00:05.000 --> 00:00:08.000 align:start position:0%
Variablen in Python

00:00:08.000 --> 00:00:11.000 align:start position:0%
und wie man sie benennt
"""

MANUELL_VTT = """WEBVTT

1
00:00:01.000 --> 00:00:03.000
Erster Satz.

2
00:00:40.000 --> 00:00:43.000
Zweiter Satz, viel spaeter.
"""

JSON3 = """{"events": [
  {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Hallo"}, {"utf8": " Welt"}]},
  {"tStartMs": 2000, "dDurationMs": 2000, "segs": [{"utf8": "\\n"}]},
  {"tStartMs": 4000, "dDurationMs": 2000, "segs": [{"utf8": "zweiter Teil"}]}
]}"""


def test_parse_vtt_liest_zeiten_und_entfernt_tags():
    kacheln = vtt.parse_vtt(AUTO_VTT)
    assert len(kacheln) == 4
    assert kacheln[0].start == 0.12
    assert kacheln[1].text == "heute geht es um Variablen in Python"


def test_parse_erkennt_json3():
    kacheln = vtt.parse(JSON3)
    assert [k.text for k in kacheln] == ["Hallo Welt", "zweiter Teil"]
    assert kacheln[1].start == 4.0


def test_parse_erkennt_srt_mit_komma():
    srt = "1\n00:00:01,000 --> 00:00:02,000\nHallo\n"
    kacheln = vtt.parse(srt)
    assert kacheln[0].start == 1.0
    assert kacheln[0].text == "Hallo"


def test_entdoppeln_entfernt_rollende_wiederholungen():
    texte = [k.text for k in vtt.entdoppeln(vtt.parse_vtt(AUTO_VTT))]
    zusammen = " ".join(texte)
    # "heute geht es um" darf genau einmal vorkommen, nicht zweimal.
    assert zusammen.count("heute geht es um") == 1
    assert zusammen.count("Variablen in Python") == 1
    assert "und wie man sie benennt" in zusammen


def test_entdoppeln_verlaengert_die_endzeit_des_gewachsenen_fensters():
    kacheln = vtt.entdoppeln(vtt.parse_vtt(AUTO_VTT))
    # Das gewachsene Fenster behaelt seinen Start, bekommt aber das spaetere Ende.
    assert kacheln[0].start == 0.12
    assert kacheln[0].ende == 5.0


def test_entdoppeln_laesst_echte_wiederholung_nach_abstand_stehen():
    kacheln = [
        vtt.Kachel(0, 2, "merken wir uns"),
        vtt.Kachel(2, 4, "und weiter"),
        vtt.Kachel(4, 6, "merken wir uns"),
    ]
    texte = [k.text for k in vtt.entdoppeln(kacheln)]
    assert texte == ["merken wir uns", "und weiter", "merken wir uns"]


def test_zu_text_setzt_zeitmarken():
    text = vtt.zu_text(vtt.parse_vtt(MANUELL_VTT), marke_alle=30)
    assert text.startswith("[00:01] Erster Satz.")
    assert "[00:40] Zweiter Satz" in text
    assert text.count("[") == 2


def test_zu_text_fasst_innerhalb_des_fensters_zusammen():
    kacheln = [vtt.Kachel(i * 5, i * 5 + 4, f"Satz {i}") for i in range(4)]
    text = vtt.zu_text(kacheln, marke_alle=30)
    # Alle vier liegen in denselben 30 Sekunden -> ein Absatz, eine Marke.
    assert text.count("[") == 1
    assert "Satz 0 Satz 1 Satz 2 Satz 3" in text


def test_zu_text_bei_leerer_spur():
    assert vtt.zu_text([]) == ""
