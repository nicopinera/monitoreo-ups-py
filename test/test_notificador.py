import logging

import pytest

import infraestructura.notificador as modulo_notificador
from infraestructura.notificador import Notificador


class RespuestaFalsa:
    def __init__(self, status):
        self.status = status


def http_falso(status=200, contenido=b"", excepcion=None):
    """Reemplazo de httplib2.Http que devuelve una respuesta fija o lanza una excepcion."""

    class HttpFalso:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, **kwargs):
            if excepcion:
                raise excepcion
            return RespuestaFalsa(status), contenido

    return HttpFalso


@pytest.fixture
def notificador(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo_notificador.time, "sleep", lambda segundos: None)
    notificador = Notificador(str(tmp_path / ".env-inexistente"))
    notificador.url = "https://chat.example/webhook"
    return notificador


def test_respuesta_distinta_de_200_se_registra(monkeypatch, caplog, notificador):
    monkeypatch.setattr(
        modulo_notificador, "Http", http_falso(status=500, contenido=b"error interno")
    )

    with caplog.at_level(logging.ERROR):
        notificador.enviar_mensajes("hola")

    assert "status=500" in caplog.text
    assert "error interno" in caplog.text


def test_excepcion_al_enviar_se_registra(monkeypatch, caplog, notificador):
    monkeypatch.setattr(modulo_notificador, "Http", http_falso(excepcion=OSError("sin red")))

    with caplog.at_level(logging.ERROR):
        notificador.enviar_mensajes("hola")

    assert "Excepción al enviar mensaje a Google Chat" in caplog.text


def test_sin_url_se_registra(caplog, notificador):
    notificador.url = None

    with caplog.at_level(logging.ERROR):
        notificador.enviar_mensajes("hola")

    assert "URL de Google Chat no configurada" in caplog.text
