import pytest

from wissen import schema


def test_slugify_behandelt_umlaute():
    assert schema.slugify("Übung: Schlüssel & Wörter") == "uebung-schluessel-woerter"


def test_slugify_kuerzt_ohne_bindestrich_am_ende():
    slug = schema.slugify("a" * 40 + " " + "b" * 40, maxlen=41)
    assert slug == "a" * 40
    assert not slug.endswith("-")


def test_slugify_faellt_auf_platzhalter_zurueck():
    assert schema.slugify("!!!") == "ohne-titel"


def test_kurz_hash_ist_stabil():
    assert schema.kurz_hash("https://example.org") == schema.kurz_hash("https://example.org")
    assert schema.kurz_hash("a") != schema.kurz_hash("b")


# -- Dateinamen aus URLs -------------------------------------------------


def test_dateiname_nennt_host_und_pfadende():
    name = schema.dateiname_fuer_url(
        "https://campus.thinkspace.ac.uk/courses/329/lessons/how-to-write-a-melody"
    )
    assert name.startswith("campus-thinkspace-ac-uk_")
    assert "how-to-write-a-melody" in name
    # Kein "https-" am Anfang -- das Schema trägt nichts zur Unterscheidung bei.
    assert not name.startswith("https")


def test_dateiname_unterscheidet_aehnliche_lektionen():
    # Lektionen eines Kurses teilen den Anfang der URL; beim Kürzen des
    # ganzen URL-Slugs fielen genau die unterscheidenden Enden weg.
    basis = "https://campus.thinkspace.ac.uk/courses/329/lessons/"
    a = schema.dateiname_fuer_url(basis + "how-to-write-a-melody")
    b = schema.dateiname_fuer_url(basis + "how-to-write-a-long-arc-melody")
    assert a != b


def test_dateiname_bleibt_kurz():
    lang = "https://campus.thinkspace.ac.uk/" + "/".join(["sehr-langes-segment"] * 8)
    assert len(schema.dateiname_fuer_url(lang)) <= 80


def test_dateiname_ist_stabil():
    url = "https://campus.thinkspace.ac.uk/c/329/m/2/l/4471"
    assert schema.dateiname_fuer_url(url) == schema.dateiname_fuer_url(url)


def test_dateiname_ohne_pfad():
    name = schema.dateiname_fuer_url("https://campus.thinkspace.ac.uk/")
    assert name.startswith("campus-thinkspace-ac-uk_")
    assert name.count("_") == 1


def test_dateiname_unterscheidet_nach_abfrageteil():
    # Gleicher Pfad, andere Abfrage -- der Hash deckt die ganze URL ab.
    a = schema.dateiname_fuer_url("https://kurs.de/l?id=1")
    b = schema.dateiname_fuer_url("https://kurs.de/l?id=2")
    assert a != b


def test_dateiname_ohne_host():
    assert schema.dateiname_fuer_url("nicht-mal-eine-url")


@pytest.mark.parametrize(
    "eingabe,erwartet",
    [("4:12", 252), ("1:02:03", 3723), ("252", 252), ("0:00", 0), ("1:30.5", 90)],
)
def test_zeit_zu_sekunden(eingabe, erwartet):
    assert schema.zeit_zu_sekunden(eingabe) == erwartet


@pytest.mark.parametrize("eingabe", ["vier", "4:xx", "1:2:3:4", ""])
def test_zeit_zu_sekunden_meldet_unsinn(eingabe):
    with pytest.raises(ValueError):
        schema.zeit_zu_sekunden(eingabe)


@pytest.mark.parametrize(
    "sekunden,erwartet", [(252, "04:12"), (3723, "01:02:03"), (0, "00:00"), (59, "00:59")]
)
def test_sekunden_zu_zeit_ist_gepolstert(sekunden, erwartet):
    assert schema.sekunden_zu_zeit(sekunden) == erwartet


@pytest.mark.parametrize(
    "sekunden,erwartet", [(0, "0:00"), (777, "12:57"), (783, "13:03"), (3723, "1:02:03")]
)
def test_zeit_kurz_ohne_polsterung(sekunden, erwartet):
    assert schema.zeit_kurz(sekunden) == erwartet


def test_zeit_fuer_dateiname_ohne_doppelpunkt():
    assert schema.zeit_fuer_dateiname(3723) == "01-02-03"


# -- Abdeckung (ANLEITUNG, Ablauf C Schritt 1) ---------------------------


def test_abdeckung_entspricht_dem_format_in_quellen_md():
    # Vorbild: "Transkript 0:00–12:57 von 13:03 (Auto-Captions)"
    assert schema.abdeckung(777, 783, True) == (
        "Transkript 0:00–12:57 von 13:03 (Auto-Captions)"
    )


def test_abdeckung_nennt_manuelle_untertitel():
    assert "Untertitel vom Kanal" in schema.abdeckung(100, 120, False)


def test_abdeckung_ohne_bekannte_gesamtlaenge():
    assert schema.abdeckung(100, None, True) == "Transkript 0:00–1:40 (Auto-Captions)"


@pytest.mark.parametrize(
    "letzte,gesamt,erwartet", [(777, 783, 6), (100, 600, 500), (800, 783, 0)]
)
def test_abdeckung_luecke(letzte, gesamt, erwartet):
    assert schema.abdeckung_luecke(letzte, gesamt) == erwartet


def test_abdeckung_luecke_ohne_gesamtlaenge():
    assert schema.abdeckung_luecke(100, None) is None


# -- Dateikopf -----------------------------------------------------------


def test_kopf_rundlauf():
    felder = {
        "Titel": "Getting Inspired and Recording First Ideas",
        "Kanal": "Cubase",
        "URL": "https://www.youtube.com/watch?v=9QkIYDESems",
        "Veröffentlicht": "2024-08-30",
        "Erfassungsdatum": "2026-10-19",
        "Abdeckung": "Transkript 0:00–12:57 von 13:03 (Auto-Captions)",
    }
    text = schema.dokument(felder, "[00:00] Hallo.")
    zurueck = schema.kopf_lesen(text)
    for name, wert in felder.items():
        assert zurueck[name] == wert


def test_kopf_haelt_die_feldreihenfolge():
    kopf = schema.kopf_bauen({
        "Titel": "T", "Abdeckung": "A", "Kanal": "K", "URL": "U",
    })
    assert kopf.index("- Kanal:") < kopf.index("- URL:") < kopf.index("- Abdeckung:")


def test_kopf_laesst_leere_felder_weg():
    kopf = schema.kopf_bauen({"Titel": "T", "Kanal": None, "Kurs": "", "Modul": []})
    assert "Kanal" not in kopf
    assert "Kurs" not in kopf
    assert "Modul" not in kopf


def test_kopf_behaelt_unbekannte_felder():
    kopf = schema.kopf_bauen({"Titel": "T", "Original": "eingang/media/x/a.pdf"})
    assert "- Original: eingang/media/x/a.pdf" in kopf


def test_kopf_enthaelt_rohmaterial_hinweis():
    # ANLEITUNG, Ablauf C Schritt 2: "Rohmaterial -- wird nicht ins Buch zitiert."
    assert "Rohmaterial" in schema.kopf_bauen({"Titel": "T"})
    assert "Rohmaterial" not in schema.kopf_bauen({"Titel": "T"}, hinweis=None)


def test_kopf_lesen_stoppt_an_der_trennlinie():
    # Nach '---' beginnt das Transkript; dort darf nichts mehr als Feld gelten.
    text = schema.dokument({"Titel": "T", "Kanal": "K"}, "- Kanal: falsch\n\n[00:00] x")
    assert schema.kopf_lesen(text)["Kanal"] == "K"


def test_kopf_lesen_ohne_kopf():
    assert schema.kopf_lesen("[00:00] nur Text") == {}


def test_dokument_endet_mit_zeilenumbruch():
    assert schema.dokument({"Titel": "T"}, "Inhalt").endswith("Inhalt\n")
