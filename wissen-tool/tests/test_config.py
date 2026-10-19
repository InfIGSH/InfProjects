import pytest

from wissen import config


def _schreibe(tmp_path, inhalt):
    pfad = tmp_path / "wissen.toml"
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


def test_lade_minimal(tmp_path):
    pfad = _schreibe(tmp_path, f'[ablage]\npfad = "{tmp_path / "Basis"}"\n')
    cfg = config.lade(pfad)
    assert cfg.ablage == tmp_path / "Basis"
    assert cfg.sprachen == config.STANDARD_SPRACHEN
    assert cfg.marke_alle == 30
    assert cfg.max_luecke == 60
    assert cfg.quelle == pfad


def test_lade_mit_allen_feldern(tmp_path):
    pfad = _schreibe(tmp_path, f"""
[ablage]
pfad = "{tmp_path / "Basis"}"
[browser]
profil = "{tmp_path / "profil"}"
[youtube]
sprachen = ["de"]
marke_alle = 60
max_luecke = 90
[web]
warte_ms = 3000
""")
    cfg = config.lade(pfad)
    assert cfg.sprachen == ["de"]
    assert cfg.marke_alle == 60
    assert cfg.max_luecke == 90
    assert cfg.warte_ms == 3000
    assert cfg.browser_profil == tmp_path / "profil"


def test_lade_vertraegt_byte_order_mark(tmp_path):
    # Notepad schreibt gern eine BOM voran; tomllib allein scheitert daran.
    pfad = tmp_path / "wissen.toml"
    pfad.write_bytes(
        b"\xef\xbb\xbf" + f'[ablage]\npfad = "{tmp_path / "Basis"}"\n'.encode("utf-8")
    )
    assert config.lade(pfad).ablage == tmp_path / "Basis"


def test_kaputtes_toml_nennt_datei_und_haeufigste_ursache(tmp_path):
    pfad = _schreibe(tmp_path, '[ablage]\npfad = "C:\\Users\\Rene\\buch"\n')
    with pytest.raises(config.KonfigFehler) as fehler:
        config.lade(pfad)
    assert "wissen.toml" in str(fehler.value)
    assert "Schrägstriche" in str(fehler.value)


def test_nicht_utf8_meldet_kodierung(tmp_path):
    pfad = tmp_path / "wissen.toml"
    pfad.write_bytes('[ablage]\npfad = "Büch"\n'.encode("latin-1"))
    with pytest.raises(config.KonfigFehler, match="UTF-8"):
        config.lade(pfad)


def test_fehlende_ablage_meldet_fehler(tmp_path):
    pfad = _schreibe(tmp_path, '[youtube]\nsprachen = ["de"]\n')
    with pytest.raises(config.KonfigFehler, match="ablage"):
        config.lade(pfad)


def test_fehlende_datei_meldet_fehler(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WISSEN_CONFIG", raising=False)
    monkeypatch.setattr(config.Path, "home", staticmethod(lambda: tmp_path / "kein-home"))
    with pytest.raises(config.KonfigFehler, match="wissen.toml"):
        config.lade()


def test_env_variable_wird_beachtet(tmp_path, monkeypatch):
    pfad = _schreibe(tmp_path, f'[ablage]\npfad = "{tmp_path / "Basis"}"\n')
    monkeypatch.chdir(tmp_path / "..")
    monkeypatch.setenv("WISSEN_CONFIG", str(pfad))
    assert config.lade().quelle == pfad


def test_host_regeln_nimmt_den_genauesten_treffer(tmp_path):
    pfad = _schreibe(tmp_path, f"""
[ablage]
pfad = "{tmp_path / "Basis"}"
[hosts."lernplattform.de"]
transkript = ["allgemein"]
[hosts."kurse.lernplattform.de"]
transkript = ["genauer"]
""")
    cfg = config.lade(pfad)
    assert cfg.host_regeln("https://kurse.lernplattform.de/a")["transkript"] == ["genauer"]
    assert cfg.host_regeln("https://www.lernplattform.de/a")["transkript"] == ["allgemein"]
    assert cfg.host_regeln("https://andere.de/a") == {}


def test_host_regeln_ignoriert_gross_schreibung(tmp_path):
    pfad = _schreibe(tmp_path, f"""
[ablage]
pfad = "{tmp_path / "Basis"}"
[hosts."Lernplattform.DE"]
transkript = ["x"]
""")
    cfg = config.lade(pfad)
    assert cfg.host_regeln("https://LERNPLATTFORM.de/a")["transkript"] == ["x"]
