"""Tests for error types."""

from tslocal._errors import (
    AccessDeniedError,
    ConnectionError,
    DaemonNotRunningError,
    HttpError,
    PeerNotFoundError,
    PreconditionsFailedError,
    TailscaleError,
    error_message_from_body,
)


def test_error_hierarchy() -> None:
    assert issubclass(AccessDeniedError, TailscaleError)
    assert issubclass(PreconditionsFailedError, TailscaleError)
    assert issubclass(PeerNotFoundError, TailscaleError)
    assert issubclass(ConnectionError, TailscaleError)
    assert issubclass(DaemonNotRunningError, ConnectionError)
    assert issubclass(HttpError, TailscaleError)


def test_access_denied_error() -> None:
    err = AccessDeniedError("not authorized")
    assert isinstance(err, TailscaleError)
    assert str(err) == "not authorized"


def test_preconditions_failed_error() -> None:
    err = PreconditionsFailedError("state mismatch")
    assert isinstance(err, TailscaleError)
    assert str(err) == "state mismatch"


def test_peer_not_found_error() -> None:
    err = PeerNotFoundError("no such peer")
    assert isinstance(err, TailscaleError)


def test_http_error() -> None:
    err = HttpError(500, "internal error")
    assert err.status == 500
    assert "500" in str(err)
    assert "internal error" in str(err)


def test_daemon_not_running_is_connection_error() -> None:
    err = DaemonNotRunningError("not running")
    assert isinstance(err, ConnectionError)
    assert isinstance(err, TailscaleError)


def test_error_message_from_body_valid_json() -> None:
    body = b'{"error": "something went wrong"}'
    assert error_message_from_body(body) == "something went wrong"


def test_error_message_from_body_no_error_field() -> None:
    body = b"{}"
    assert error_message_from_body(body) is None


def test_error_message_from_body_invalid_json() -> None:
    body = b"not json"
    assert error_message_from_body(body) is None
