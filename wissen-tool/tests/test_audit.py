from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from wissen import audit, web

URL = 'https://player.vimeo.com/video/123'


@pytest.mark.parametrize('inhalt,erwartet', [
    ('## Transkript\n[00:00] Wort', 'fehlt'),
    (f'- Video: {URL}\n## Transkript\nFont size Font family Background color', 'Einstellungsdialog'),
    (f'- Video: {URL}\n## Transkript\nKeine Spur', 'Kein zugeordnetes'),
    (f'- Video: {URL}\n## Transkript\n[00:00] Anfang\n[00:30] Ende', 'Lücken ungeprüft'),
])
def test_bewertung_unterscheidet_quelle_dialog_und_zeitmarken(inhalt, erwartet):
    assert erwartet in audit.bewerte(inhalt, [(URL, 'Vimeo')])[0]['status']


def test_mehrere_videos_brauchen_eigenen_transkriptabschnitt():
    text = (f'- Video: {URL}; {URL}4\n## Transkript\n'
            f'### Video 1\n- Video: {URL}\n[00:00] Anfang\n'
            f'### Video 2\n- Video: {URL}4\nKEIN Transkript\n')
    result = audit.bewerte(text, [(URL, 'Vimeo'), (URL + '4', 'Vimeo')])
    assert 'Zeitmarken vorhanden' in result[0]['status']
    assert 'Kein zugeordnetes' in result[1]['status']


def test_audit_berichtet_alle_eintraege_auch_bei_abruffehler(tmp_path, monkeypatch):
    liste = tmp_path / 'liste.txt'
    liste.write_text('https://kurs.de/1\nhttps://kurs.de/2\n')
    def goto(url, **kwargs):
        if url.endswith('/2'):
            raise RuntimeError('Timeout')
    seite = SimpleNamespace(goto=goto, url='https://kurs.de/1', frames=[],
                            wait_for_load_state=lambda *a, **k: None,
                            wait_for_timeout=lambda *a: None, close=lambda: None)
    monkeypatch.setattr(web, 'browser', lambda *a, **k: nullcontext(
        SimpleNamespace(new_page=lambda: seite)))
    ablage = SimpleNamespace(bekannte_urls=lambda: {}, url_marke=lambda url: url)
    bericht = audit.pruefe_kurs(SimpleNamespace(warte_ms=0), ablage, liste, tmp_path / 'audit')
    text = bericht.read_text()
    assert '2 Listeneinträge, 1 Abruffehler' in text
    assert 'ABRUFFEHLER: RuntimeError: Timeout' in text
    assert 'Kein bekannter Player' in text
    assert 'Keine vorhandene Lektionsdatei' in text
