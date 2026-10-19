import pytest

from wissen import pdfs, schema
from wissen.config import Konfig
from wissen.store import Ablage


@pytest.fixture
def umgebung(tmp_path):
    root = tmp_path / "buch"
    root.mkdir(parents=True)
    (root / "ANLEITUNG.md").write_text("# Anleitung", encoding="utf-8")
    ablage = Ablage(root)
    ablage.init()
    cfg = Konfig(ablage=root, browser_profil=tmp_path / "profil")
    return cfg, ablage


def _leeres_pdf(pfad, seiten=1):
    """PDF ohne Textlayer -- wie ein Scan."""
    from pypdf import PdfWriter

    schreiber = PdfWriter()
    for _ in range(seiten):
        schreiber.add_blank_page(width=595, height=842)
    with open(pfad, "wb") as fh:
        schreiber.write(fh)
    return pfad


def _text_pdf(pfad, zeilen):
    """Einseitiges PDF mit echtem Textlayer, von Hand gebaut."""
    inhalt = (
        "BT /F1 14 Tf 50 780 Td 16 TL\n"
        + "\n".join(f"({z}) Tj T*" for z in zeilen)
        + "\nET"
    )
    objekte = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(inhalt)} >>\nstream\n{inhalt}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    aus = "%PDF-1.4\n"
    offsets = []
    for nr, objekt in enumerate(objekte, start=1):
        offsets.append(len(aus))
        aus += f"{nr} 0 obj\n{objekt}\nendobj\n"
    start = len(aus)
    aus += f"xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n"
    aus += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    aus += (
        f"trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\n"
        f"startxref\n{start}\n%%EOF\n"
    )
    pfad.write_bytes(aus.encode("latin-1"))
    return pfad


def test_lade_pdf_legt_text_und_original_ab(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "Trainingseinheit 1.pdf", seiten=2)

    pfad, felder, _ = pdfs.lade_pdf(
        cfg, ablage, quelle, praefix="training", lektion="1"
    )

    assert ablage.rel(pfad) == "eingang/training_trainingseinheit-1.md"
    assert felder["Lektion"] == "1"
    assert (ablage.root / felder["Original"]).is_file()
    assert felder["Original"].startswith("eingang/media/")

    text = pfad.read_text(encoding="utf-8")
    assert "[Seite 1]" in text and "[Seite 2]" in text
    assert "2 Seiten" in felder["Abdeckung"]


def test_lade_pdf_erkennt_fehlenden_textlayer(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "Scan.pdf")

    pfad, felder, braucht_ocr = pdfs.lade_pdf(cfg, ablage, quelle, praefix="kurs")

    assert braucht_ocr is True
    assert "OCR nötig" in felder["Abdeckung"]
    assert "ocrmypdf" in pfad.read_text(encoding="utf-8")


def test_lade_pdf_zaehlt_eine_seite_richtig(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "Einzelblatt.pdf", seiten=1)
    _, felder, _ = pdfs.lade_pdf(cfg, ablage, quelle, praefix="kurs")
    assert "1 Seite" in felder["Abdeckung"]
    assert "1 Seiten" not in felder["Abdeckung"]


def test_kurzer_text_gilt_nicht_als_scan():
    # Ein Titel- oder Übungsblatt hat wenig Text, ist aber sauber auslesbar.
    # Gemessen wird der Anteil leerer Seiten, nicht der Durchschnitt.
    seiten = ["Action Cue Walkthrough\nOstinato in 7/8"]
    leere = sum(1 for t in seiten if len(t) < pdfs.MIN_ZEICHEN_PRO_SEITE)
    assert leere / len(seiten) < pdfs.MAX_LEERE_SEITEN


def test_lade_pdf_meldet_gemischtes_pdf_nicht_als_scan(umgebung, tmp_path):
    from pypdf import PdfReader, PdfWriter

    cfg, ablage = umgebung
    # Ein Textblatt plus ein Leerblatt: 50 % leer ist genau die Grenze,
    # zwei Textblätter plus ein Leerblatt dürfen nicht als Scan gelten.
    mit_text = _text_pdf(tmp_path / "text.pdf", ["Harmony Basics", "Chords I IV V"])
    leer = _leeres_pdf(tmp_path / "leer.pdf")
    schreiber = PdfWriter()
    for quelle in (mit_text, mit_text, leer):
        for seite in PdfReader(str(quelle)).pages:
            schreiber.add_page(seite)
    gemischt = tmp_path / "gemischt.pdf"
    with open(gemischt, "wb") as fh:
        schreiber.write(fh)

    _, felder, braucht_ocr = pdfs.lade_pdf(cfg, ablage, gemischt, praefix="kurs")
    assert braucht_ocr is False
    assert "1 ohne Text" in felder["Abdeckung"]


def test_lade_pdf_nimmt_titel_von_hand(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "wirrer-dateiname-x7.pdf")

    pfad, felder, _ = pdfs.lade_pdf(
        cfg, ablage, quelle, praefix="kurs", titel="Woche 3: Ausdauer"
    )

    assert felder["Titel"] == "Woche 3: Ausdauer"
    assert ablage.rel(pfad) == "eingang/kurs_woche-3-ausdauer.md"


def test_lade_pdf_schreibt_lesbaren_kopf(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "Einheit.pdf")
    pfad, felder, _ = pdfs.lade_pdf(cfg, ablage, quelle, praefix="kurs", kurs="Statik")
    zurueck = schema.kopf_lesen(pfad.read_text(encoding="utf-8"))
    assert zurueck["Kurs"] == "Statik"
    assert zurueck["Abdeckung"] == felder["Abdeckung"]


def test_lade_pdf_meldet_fehlende_datei(umgebung, tmp_path):
    cfg, ablage = umgebung
    with pytest.raises(pdfs.PdfFehler):
        pdfs.lade_pdf(cfg, ablage, tmp_path / "gibt-es-nicht.pdf", praefix="kurs")


def test_lade_ordner_nummeriert_alphabetisch(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = tmp_path / "Kurs"
    quelle.mkdir()
    for name in ["03 Dritte.pdf", "01 Erste.pdf", "02 Zweite.pdf"]:
        _leeres_pdf(quelle / name)
    (quelle / "notizen.txt").write_text("kein pdf", encoding="utf-8")

    ergebnisse = pdfs.lade_ordner(cfg, ablage, quelle, praefix="onlinekurs")

    assert len(ergebnisse) == 3
    reihenfolge = [(f["Lektion"], f["Titel"]) for _, f, _ in ergebnisse]
    assert [nr for nr, _ in reihenfolge] == ["1", "2", "3"]
    assert "Erste" in reihenfolge[0][1]
    assert "Dritte" in reihenfolge[2][1]


def test_lade_ordner_meldet_leeren_ordner(umgebung, tmp_path):
    cfg, ablage = umgebung
    leer = tmp_path / "leer"
    leer.mkdir()
    with pytest.raises(pdfs.PdfFehler):
        pdfs.lade_ordner(cfg, ablage, leer, praefix="kurs")


class _FakeReader:
    def __init__(self, titel):
        self.metadata = {"/Title": titel} if titel is not None else {}


@pytest.mark.parametrize("roh", ["Untitled", "unbenannt", "Microsoft Word - foo.docx", "Dokument1"])
def test_titel_verwirft_generische_metadaten(roh, tmp_path):
    seiten = ["Lektion 4: Rekursion\nweiterer Text"]
    titel = pdfs._titel(_FakeReader(roh), seiten, tmp_path / "datei.pdf")
    assert titel == "Lektion 4: Rekursion"


def test_titel_nimmt_gute_metadaten(tmp_path):
    titel = pdfs._titel(_FakeReader("Handbuch Statik"), ["egal"], tmp_path / "x.pdf")
    assert titel == "Handbuch Statik"


def test_titel_faellt_auf_dateinamen_zurueck(tmp_path):
    titel = pdfs._titel(_FakeReader(None), [""], tmp_path / "mein_skript.pdf")
    assert titel == "mein skript"
