"""Tests for CLI module entrypoint."""

from oscarius.__main__ import parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.reload is False


def test_parse_args_custom():
    args = parse_args(["--host", "0.0.0.0", "--port", "9000", "--reload"])
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.reload is True
