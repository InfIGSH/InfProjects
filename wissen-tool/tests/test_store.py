import pytest

from wissen import schema
from wissen.store import Ablage


@pytest.fixture
def ablage(tmp_path):
    """Eine Ablage, die wie der vorhandene buch/-Ordner aussieht."""
    root = tmp_path / "buch"
    root.mkdir(parents=True)
    (root / "ANLEITUNG.md").write_text("# Anleitung", encoding="utf-8")
    (root / "quellen.md").write_text("# Quellenverzeichnis", encoding="utf-8")
    a = Ablage(root)
    a.init()
    return a


def test_init_legt_nur_die_eingangsordner_an(ablage):
    assert ablage.eingang.is_dir()
    assert ablage.verarbeitet.is_dir()
    assert ablage.media.is_dir()
    # Nichts anderes: keine eigene Struktur neben der vorhandenen.
    vorhanden = sorted(p.name for p in ablage.root.iterdir())
    assert vorhanden == ["ANLEITUNG.md", "eingang", "quellen.md"]


def test_init_ist_wiederholbar(ablage):
    assert ablage.init() == []


def test_pruefe_meldet_fehlende_ablage(tmp_path):
    with pytest.raises(FileNotFoundError):
        Ablage(tmp_path / "gibt-es-nicht").pruefe()


def test_warnung_wenn_es_nicht_der_buch_ordner_ist(tmp_path):
    root = tmp_path / "irgendwas"
    root.mkdir()
    warnungen = Ablage(root).warnungen()
    assert len(warnungen) == 1
    assert "ANLEITUNG.md" in warnungen[0]


def test_keine_warnung_beim_echten_buch_ordner(ablage):
    assert ablage.warnungen() == []


def test_eingang_pfad_folgt_der_anleitung(ablage):
    # ANLEITUNG, Ablauf C 2: eingang/<genre>_<video-id>.md
    pfad = ablage.eingang_pfad("synthwave", "9QkIYDESems")
    assert ablage.rel(pfad) == "eingang/synthwave_9QkIYDESems.md"


def test_eingang_pfad_slugged_den_praefix(ablage):
    pfad = ablage.eingang_pfad("Thinkspace: Cinematic Music", "m2-melodie")
    assert ablage.rel(pfad) == "eingang/thinkspace-cinematic-music_m2-melodie.md"


def test_media_ordner_liegt_im_eingang(ablage):
    ordner = ablage.media_ordner("9QkIYDESems")
    assert ablage.rel(ordner) == "eingang/media/9qkiydesems"


def test_rel_von_baut_relativen_markdown_link(ablage):
    dok = ablage.eingang / "synthwave_abc.md"
    bild = ablage.media / "abc" / "04-12.jpg"
    assert ablage.rel_von(bild, dok) == "media/abc/04-12.jpg"


def test_schreiben_und_wiederfinden(ablage):
    felder = {"Titel": "Teil 1", "URL": "https://youtu.be/abc"}
    pfad = ablage.schreibe(felder, "[00:00] x", ablage.eingang_pfad("synthwave", "abc"))
    assert pfad.is_file()
    assert ablage.finde_nach_url("https://youtu.be/abc") == pfad
    assert ablage.finde_nach_url("https://youtu.be/anders") is None


def test_finde_nach_url_ignoriert_schlussstrich(ablage):
    felder = {"Titel": "T", "URL": "https://kurs.de/lektion-1"}
    pfad = ablage.schreibe(felder, "x", ablage.eingang_pfad("kurs", "l1"))
    assert ablage.finde_nach_url("https://kurs.de/lektion-1/") == pfad


def test_bekannte_urls_umfasst_auch_eingearbeitete(ablage):
    # Entscheidend gegen Dubletten: eine Lektion, die schon eingearbeitet und
    # nach verarbeitet/ verschoben wurde, darf nicht erneut erfasst werden.
    offen = ablage.schreibe(
        {"Titel": "offen", "URL": "https://kurs.de/l1"},
        "x", ablage.eingang_pfad("kurs", "l1"),
    )
    fertig = ablage.schreibe(
        {"Titel": "fertig", "URL": "https://kurs.de/l2"},
        "x", ablage.verarbeitet / "kurs_l2.md",
    )
    bekannt = ablage.bekannte_urls()
    assert bekannt["https://kurs.de/l1"] == offen
    assert bekannt["https://kurs.de/l2"] == fertig
    assert ablage.finde_nach_url("https://kurs.de/l2") == fertig


def test_bekannte_urls_ohne_url_feld(ablage):
    ablage.schreibe({"Titel": "PDF ohne URL"}, "x", ablage.eingang_pfad("kurs", "p"))
    assert ablage.bekannte_urls() == {}


def test_bekannte_urls_bei_leerem_eingang(ablage):
    assert ablage.bekannte_urls() == {}


def test_dokumente_zeigt_nur_den_offenen_rueckstand(ablage):
    offen = ablage.schreibe({"Titel": "offen"}, "x", ablage.eingang_pfad("a", "1"))
    fertig = ablage.schreibe({"Titel": "fertig"}, "x", ablage.verarbeitet / "b_2.md")
    assert [p for p, _ in ablage.dokumente()] == [offen]
    assert fertig in [p for p, _ in ablage.dokumente(auch_verarbeitet=True)]


def test_verschiebe_verarbeitet(ablage):
    pfad = ablage.schreibe({"Titel": "T"}, "x", ablage.eingang_pfad("synthwave", "abc"))
    ziel = ablage.verschiebe_verarbeitet(pfad)
    assert ablage.rel(ziel) == "eingang/verarbeitet/synthwave_abc.md"
    assert not pfad.exists()


def test_verschiebe_verarbeitet_zieht_bildlinks_mit(ablage):
    # Die Datei rutscht eine Ebene tiefer -- sonst zeigen die Bilder ins Leere.
    pfad = ablage.schreibe(
        {"Titel": "T"}, "![Screenshot](media/abc/04-12.jpg)",
        ablage.eingang_pfad("synthwave", "abc"),
    )
    ziel = ablage.verschiebe_verarbeitet(pfad)
    assert "](../media/abc/04-12.jpg)" in ziel.read_text(encoding="utf-8")


def test_verschiebe_verarbeitet_ist_wiederholbar(ablage):
    pfad = ablage.schreibe({"Titel": "T"}, "x", ablage.eingang_pfad("a", "1"))
    ziel = ablage.verschiebe_verarbeitet(pfad)
    assert ablage.verschiebe_verarbeitet(ziel) == ziel


def test_verschiebe_verarbeitet_meldet_kollision(ablage):
    ablage.schreibe({"Titel": "alt"}, "x", ablage.verarbeitet / "a_1.md")
    neu = ablage.schreibe({"Titel": "neu"}, "x", ablage.eingang_pfad("a", "1"))
    with pytest.raises(FileExistsError):
        ablage.verschiebe_verarbeitet(neu)


def test_verschiebe_verarbeitet_lehnt_fremde_pfade_ab(ablage, tmp_path):
    fremd = tmp_path / "woanders.md"
    fremd.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        ablage.verschiebe_verarbeitet(fremd)


def test_quellen_eintrag_folgt_dem_stil_in_quellen_md(ablage):
    felder = {
        "Titel": "Getting Inspired and Recording First Ideas",
        "Kanal": "Cubase",
        "URL": "https://www.youtube.com/watch?v=9QkIYDESems",
        "Veröffentlicht": "2024-08-30",
        "Abdeckung": "Transkript 0:00–12:57 von 13:03 (Auto-Captions)",
    }
    pfad = ablage.schreibe(felder, "x", ablage.eingang_pfad("synthwave", "9QkIYDESems"))
    eintrag = ablage.quellen_eintrag(pfad, felder)
    assert eintrag.startswith("- „Getting Inspired")
    assert "<https://www.youtube.com/watch?v=9QkIYDESems>" in eintrag
    assert "veröffentlicht 2024-08-30" in eintrag
    assert "Transkript 0:00–12:57 von 13:03 (Auto-Captions)" in eintrag
    assert "`eingang/synthwave_9QkIYDESems.md`" in eintrag


def test_quellen_eintrag_bei_duerftigen_feldern(ablage):
    felder = {"Titel": "Ohne alles"}
    pfad = ablage.schreibe(felder, "x", ablage.eingang_pfad("a", "1"))
    eintrag = ablage.quellen_eintrag(pfad, felder)
    assert "Ohne alles" in eintrag
    assert "`eingang/a_1.md`" in eintrag
