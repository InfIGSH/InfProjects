import pytest

from wissen import schema
from wissen.store import Ablage


@pytest.fixture
def ablage(tmp_path):
    a = Ablage(tmp_path / "Wissensbasis")
    a.root.mkdir(parents=True)
    a.init()
    return a


def test_init_legt_struktur_an(ablage):
    for rel in ["raw/youtube", "raw/kurse", "raw/pdf", "assets", "compendia", "inbox"]:
        assert (ablage.root / rel).is_dir()
    assert (ablage.root / "README.md").is_file()
    assert (ablage.root / ".gitignore").is_file()


def test_init_legt_die_kompendium_skill_mit_ab(ablage):
    skill = ablage.root / ".claude" / "skills" / "kompendium" / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: kompendium" in text


def test_init_ist_wiederholbar(ablage):
    (ablage.root / "README.md").write_text("von Hand geaendert", encoding="utf-8")
    assert ablage.init() == []
    assert (ablage.root / "README.md").read_text(encoding="utf-8") == "von Hand geaendert"


def test_pruefe_meldet_fehlende_ablage(tmp_path):
    with pytest.raises(FileNotFoundError):
        Ablage(tmp_path / "gibt-es-nicht").pruefe()


def test_dokument_pfad_youtube(ablage):
    meta = schema.neues_frontmatter(id="yt:abc123", typ="youtube", titel="Übung mit Listen")
    pfad = ablage.dokument_pfad(meta)
    assert ablage.rel(pfad) == "raw/youtube/abc123--uebung-mit-listen.md"


def test_dokument_pfad_kurs_mit_lektionsnummer(ablage):
    meta = schema.neues_frontmatter(
        id="web:x", typ="kurs", titel="Erste Schritte", kurs="python-grundkurs", lektion=3
    )
    assert ablage.rel(ablage.dokument_pfad(meta)) == (
        "raw/kurse/python-grundkurs/03--erste-schritte.md"
    )


def test_dokument_pfad_pdf_ohne_kurs(ablage):
    meta = schema.neues_frontmatter(id="pdf:x", typ="pdf", titel="Einheit 1")
    assert ablage.rel(ablage.dokument_pfad(meta)) == "raw/pdf/ohne-kurs/einheit-1.md"


def test_schreiben_und_wiederfinden(ablage):
    meta = schema.neues_frontmatter(id="yt:abc", typ="youtube", titel="Test")
    pfad = ablage.schreibe(meta, "# Test\n\n[00:00] Inhalt")
    assert pfad.is_file()
    assert ablage.finde_nach_id("yt:abc") == pfad
    assert ablage.finde_nach_id("yt:fehlt") is None


def test_dokumente_liefert_frontmatter_und_text(ablage):
    meta = schema.neues_frontmatter(id="yt:abc", typ="youtube", titel="Test")
    ablage.schreibe(meta, "# Test\n\nInhalt")
    (ablage.root / "raw" / "youtube" / "ohne-kopf.md").write_text("nur Text", encoding="utf-8")
    gefunden = list(ablage.dokumente())
    # Dateien ohne Frontmatter werden uebersprungen.
    assert len(gefunden) == 1
    _, gelesen, body = gefunden[0]
    assert gelesen["titel"] == "Test"
    assert "Inhalt" in body


def test_rel_von_baut_relativen_markdown_link(ablage):
    doc = ablage.root / "raw" / "kurse" / "kurs" / "01--seite.md"
    bild = ablage.root / "assets" / "kurs-x" / "04-12.jpg"
    assert ablage.rel_von(bild, doc) == "../../../assets/kurs-x/04-12.jpg"


def test_kopiere_original_legt_datei_neben_dokument(ablage, tmp_path):
    quelle = tmp_path / "Einheit.PDF"
    quelle.write_bytes(b"%PDF-1.4 test")
    meta = schema.neues_frontmatter(id="pdf:x", typ="pdf", titel="Einheit 1", kurs="training")
    rel = ablage.kopiere_original(quelle, meta)
    assert rel == "raw/pdf/training/einheit-1.pdf"
    assert (ablage.root / rel).read_bytes() == b"%PDF-1.4 test"


def test_index_gruppiert_nach_typ_und_kurs(ablage):
    ablage.schreibe(schema.neues_frontmatter(
        id="yt:a", typ="youtube", titel="Tutorial A", quelle="https://y/a", dauer=252,
        assets=["assets/yt-a/04-12.jpg"],
    ), "x")
    ablage.schreibe(schema.neues_frontmatter(
        id="web:b", typ="kurs", titel="Lektion B", quelle="https://k/b",
        kurs="python-grundkurs", lektion=2,
    ), "x")
    ablage.schreibe(schema.neues_frontmatter(
        id="pdf:c", typ="pdf", titel="Einheit C", kurs="training", seiten=12,
    ), "x")
    (ablage.root / "compendia" / "python-grundkurs.md").write_text(
        schema.dokument(schema.neues_frontmatter(
            id="komp:python", typ="kompendium", titel="Python-Grundkurs"), "x"),
        encoding="utf-8",
    )

    text = ablage.baue_index().read_text(encoding="utf-8")
    assert "3 Quellen, 1 Kompendium" in text
    assert "## Kompendien" in text
    assert "[Python-Grundkurs](compendia/python-grundkurs.md)" in text
    assert "## YouTube-Tutorials" in text
    assert "Dauer 04:12" in text
    assert "1 Screenshot," in text
    assert "### python-grundkurs" in text
    assert "Lektion 2" in text
    assert "12 Seiten" in text
    # Web-Quellen werden verlinkt, ...
    assert "([Quelle](https://y/a))" in text


def test_index_verlinkt_bei_pdf_das_original_statt_des_dateinamens(ablage):
    ablage.schreibe(schema.neues_frontmatter(
        id="pdf:c", typ="pdf", titel="Einheit C", kurs="training", seiten=1,
        quelle="Einheit C.pdf", original="raw/pdf/training/einheit-c.pdf",
    ), "x")
    text = ablage.baue_index().read_text(encoding="utf-8")
    # ... ein bloßer Dateiname nicht -- sonst entstehen tote Links.
    assert "([Original](raw/pdf/training/einheit-c.pdf))" in text
    assert "(Einheit C.pdf)" not in text
    assert "1 Seite," in text


def test_index_markiert_pdfs_ohne_textlayer(ablage):
    ablage.schreibe(schema.neues_frontmatter(
        id="pdf:d", typ="pdf", titel="Scan", kurs="training", seiten=3,
    ) | {"braucht_ocr": True}, "x")
    assert "OCR nötig" in ablage.baue_index().read_text(encoding="utf-8")


def test_index_sortiert_lektionen_numerisch(ablage):
    for nr in (10, 2, 1):
        ablage.schreibe(schema.neues_frontmatter(
            id=f"web:{nr}", typ="kurs", titel=f"Lektion {nr}", kurs="k", lektion=nr,
        ), "x")
    text = ablage.baue_index().read_text(encoding="utf-8")
    assert text.index("Lektion 1]") < text.index("Lektion 2]") < text.index("Lektion 10]")


def test_index_auch_bei_leerer_ablage(ablage):
    text = ablage.baue_index().read_text(encoding="utf-8")
    assert "0 Quellen" in text
