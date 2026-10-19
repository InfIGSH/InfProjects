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
def test_sekunden_zu_zeit(sekunden, erwartet):
    assert schema.sekunden_zu_zeit(sekunden) == erwartet


def test_zeit_fuer_dateiname_ohne_doppelpunkt():
    assert schema.zeit_fuer_dateiname(3723) == "01-02-03"


def test_frontmatter_rundlauf():
    meta = schema.neues_frontmatter(
        id="yt:abc", typ="youtube", titel="Schlüssel & Wörter", quelle="https://x",
        tags=["krypto"],
    )
    text = schema.dokument(meta, "# Titel\n\nInhalt")
    zurueck, body = schema.frontmatter_load(text)
    assert zurueck["id"] == "yt:abc"
    assert zurueck["titel"] == "Schlüssel & Wörter"
    assert zurueck["tags"] == ["krypto"]
    assert body.strip() == "# Titel\n\nInhalt"


def test_frontmatter_feldreihenfolge_bleibt_stabil():
    meta = schema.neues_frontmatter(id="x", typ="pdf", titel="T", quelle="q")
    meta["eigenes_feld"] = "wert"
    kopf = schema.frontmatter_dump(meta)
    assert kopf.index("id:") < kopf.index("typ:") < kopf.index("titel:")
    # Unbekannte Felder gehen nicht verloren, landen aber hinten.
    assert kopf.index("lizenz_hinweis:") < kopf.index("eigenes_feld:")


def test_frontmatter_load_ohne_kopf():
    meta, body = schema.frontmatter_load("# Nur Text")
    assert meta == {}
    assert body == "# Nur Text"


def test_frontmatter_load_bei_unvollstaendigem_kopf():
    # Oeffnendes '---' ohne schliessendes: Text unveraendert zurueckgeben.
    meta, body = schema.frontmatter_load("---\nid: x\nkein Ende")
    assert meta == {}
    assert body.startswith("---")


def test_frontmatter_dump_laesst_none_weg():
    meta = schema.neues_frontmatter(id="x", typ="pdf", titel="T", quelle="q")
    kopf = schema.frontmatter_dump(meta)
    assert "kurs:" not in kopf
    assert "lektion:" not in kopf
