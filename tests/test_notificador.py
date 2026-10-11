import io
import json
import logging
from email.message import Message
from pathlib import Path
from types import TracebackType
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

import config.configuracion as c
import infraestructura.notificador as modulo_notificador
from infraestructura.notificador import Notificador

URL = "https://chat.example/webhook"


class RespuestaFalsa:
    """Lo minimo de la respuesta de urlopen: se usa como context manager."""

    def __enter__(self) -> "RespuestaFalsa":
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        excepcion: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class UrlopenFalso:
    """Reemplazo de urllib.request.urlopen: registra los pedidos y responde o lanza la excepcion."""

    def __init__(self, excepcion: Exception | None = None) -> None:
        self.excepcion = excepcion
        self.pedidos: list[tuple[Request, float | None]] = []

    def __call__(self, pedido: Request, timeout: float | None = None) -> RespuestaFalsa:
        self.pedidos.append((pedido, timeout))
        if self.excepcion:
            raise self.excepcion
        return RespuestaFalsa()


@pytest.fixture
def notificador(tmp_path: Path) -> Notificador:
    notificador = Notificador(str(tmp_path / ".env-inexistente"))
    notificador.url = URL
    return notificador


def usar_urlopen(
    monkeypatch: pytest.MonkeyPatch, excepcion: Exception | None = None
) -> UrlopenFalso:
    urlopen = UrlopenFalso(excepcion)
    monkeypatch.setattr(modulo_notificador, "urlopen", urlopen)
    return urlopen


def test_envia_un_post_json_con_timeout(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, notificador: Notificador
) -> None:
    urlopen = usar_urlopen(monkeypatch)

    with caplog.at_level(logging.ERROR):
        assert notificador.enviar_mensajes("hola ñandú") is True

    [(pedido, timeout)] = urlopen.pedidos
    assert pedido.full_url == URL
    assert pedido.get_method() == "POST"
    assert pedido.get_header("Content-type") == "application/json; charset=UTF-8"
    assert isinstance(pedido.data, bytes)
    assert json.loads(pedido.data.decode("utf-8")) == {"text": "hola ñandú"}
    assert timeout == c.HTTP_TIMEOUT  # sin timeout, un chat colgado deja el hilo esperando
    assert caplog.text == ""


def test_respuesta_de_error_se_registra(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, notificador: Notificador
) -> None:
    error = HTTPError(URL, 429, "Too Many Requests", Message(), io.BytesIO(b"limite de envio"))
    usar_urlopen(monkeypatch, excepcion=error)

    with caplog.at_level(logging.ERROR):
        assert notificador.enviar_mensajes("hola") is False

    assert "status=429" in caplog.text
    assert "limite de envio" in caplog.text


@pytest.mark.parametrize(
    "excepcion",
    [URLError("sin red"), TimeoutError("timed out")],
)
def test_excepcion_al_enviar_se_registra(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    notificador: Notificador,
    excepcion: Exception,
) -> None:
    usar_urlopen(monkeypatch, excepcion=excepcion)

    with caplog.at_level(logging.ERROR):
        assert notificador.enviar_mensajes("hola") is False

    assert "Excepción al enviar mensaje a Google Chat" in caplog.text


def test_sin_url_se_registra(caplog: pytest.LogCaptureFixture, notificador: Notificador) -> None:
    notificador.url = None

    with caplog.at_level(logging.ERROR):
        assert notificador.enviar_mensajes("hola") is False

    assert "URL de Google Chat no configurada" in caplog.text


@pytest.mark.parametrize("url", ["http://chat.example/webhook", "file:///etc/passwd"])
def test_url_que_no_es_https_no_se_usa(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    notificador: Notificador,
    url: str,
) -> None:
    urlopen = usar_urlopen(monkeypatch)
    notificador.url = url

    with caplog.at_level(logging.ERROR):
        assert notificador.enviar_mensajes("hola") is False

    assert urlopen.pedidos == []
    assert "debe empezar con https://" in caplog.text
