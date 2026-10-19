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


def test_frame_name_kuerzt_lange_urls():
    lang = "https://kurs.de/" + "a" * 200
    name = pruefen._frame_name(type("F", (), {"url": lang})(), 2)
    assert name.startswith("Frame 2: ")
    assert name.endswith("...")
    assert len(name) < 120


def test_frame_name_ohne_url():
    name = pruefen._frame_name(type("F", (), {"url": ""})(), 1)
    assert "ohne URL" in name
