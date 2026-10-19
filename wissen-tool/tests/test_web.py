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
