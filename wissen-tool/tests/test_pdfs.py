import pytest

from wissen import pdfs
from wissen.config import Konfig
from wissen.store import Ablage


@pytest.fixture
def umgebung(tmp_path):
    ablage = Ablage(tmp_path / "Wissensbasis")
    ablage.root.mkdir(parents=True)
    ablage.init()
    cfg = Konfig(ablage=ablage.root, browser_profil=tmp_path / "profil")
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


def test_lade_pdf_legt_text_und_original_ab(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "Trainingseinheit 1.pdf", seiten=2)

    pfad, meta = pdfs.lade_pdf(cfg, ablage, quelle, kurs="Krafttraining", lektion=1)

    assert ablage.rel(pfad) == "raw/pdf/krafttraining/01--trainingseinheit-1.md"
    assert meta["seiten"] == 2
    assert meta["typ"] == "pdf"
    assert meta["kurs"] == "krafttraining"
    assert (ablage.root / meta["original"]).is_file()

    text = pfad.read_text(encoding="utf-8")
    assert "[Seite 1]" in text and "[Seite 2]" in text


def test_lade_pdf_erkennt_fehlenden_textlayer(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "Scan.pdf")

    pfad, meta = pdfs.lade_pdf(cfg, ablage, quelle, kurs="kurs")

    assert meta["braucht_ocr"] is True
    assert "ocrmypdf" in pfad.read_text(encoding="utf-8")


def test_lade_pdf_nimmt_titel_von_hand(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = _leeres_pdf(tmp_path / "wirrer-dateiname-x7.pdf")

    _, meta = pdfs.lade_pdf(cfg, ablage, quelle, kurs="kurs", titel="Woche 3: Ausdauer")

    assert meta["titel"] == "Woche 3: Ausdauer"


def test_lade_pdf_id_haengt_am_dateiinhalt(umgebung, tmp_path):
    cfg, ablage = umgebung
    a = _leeres_pdf(tmp_path / "a.pdf")
    b = _leeres_pdf(tmp_path / "b.pdf")

    _, meta_a = pdfs.lade_pdf(cfg, ablage, a, kurs="kurs", titel="A")
    _, meta_b = pdfs.lade_pdf(cfg, ablage, b, kurs="kurs", titel="B")

    # Gleicher Inhalt -> gleiche ID, auch bei anderem Dateinamen.
    assert meta_a["id"] == meta_b["id"]


def test_lade_pdf_meldet_fehlende_datei(umgebung, tmp_path):
    cfg, ablage = umgebung
    with pytest.raises(pdfs.PdfFehler):
        pdfs.lade_pdf(cfg, ablage, tmp_path / "gibt-es-nicht.pdf", kurs="kurs")


def test_lade_ordner_nummeriert_alphabetisch(umgebung, tmp_path):
    cfg, ablage = umgebung
    quelle = tmp_path / "Kurs"
    quelle.mkdir()
    for name in ["03 Dritte.pdf", "01 Erste.pdf", "02 Zweite.pdf"]:
        _leeres_pdf(quelle / name)
    (quelle / "notizen.txt").write_text("kein pdf", encoding="utf-8")

    ergebnisse = pdfs.lade_ordner(cfg, ablage, quelle, kurs="Onlinekurs")

    assert len(ergebnisse) == 3
    reihenfolge = [(m["lektion"], m["titel"]) for _, m in ergebnisse]
    assert [nr for nr, _ in reihenfolge] == [1, 2, 3]
    assert "Erste" in reihenfolge[0][1]
    assert "Dritte" in reihenfolge[2][1]


def test_lade_ordner_meldet_leeren_ordner(umgebung, tmp_path):
    cfg, ablage = umgebung
    leer = tmp_path / "leer"
    leer.mkdir()
    with pytest.raises(pdfs.PdfFehler):
        pdfs.lade_ordner(cfg, ablage, leer, kurs="kurs")


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
