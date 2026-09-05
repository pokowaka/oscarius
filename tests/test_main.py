"""Tests for CLI module entrypoint."""

from oscarius.__main__ import parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.reload is False


def test_parse_args_custom():
    args = parse_args(["--host", "0.0.0.0", "--port", "9000", "--reload"])
    assert args.command == "serve"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.reload is True


def test_parse_args_serve_subcommand():
    args = parse_args(["serve", "--port", "8888"])
    assert args.command == "serve"
    assert args.port == 8888
    assert args.host == "127.0.0.1"


def test_parse_args_import_subcommand():
    args = parse_args(["import", "/tmp/sdcard", "--db", "custom.db", "--profile", "Alice"])
    assert args.command == "import"
    assert args.card_path == "/tmp/sdcard"
    assert args.db == "custom.db"
    assert args.profile == "Alice"


def test_parse_args_import_defaults():
    args = parse_args(["import", "/tmp/sdcard"])
    assert args.command == "import"
    assert args.card_path == "/tmp/sdcard"
    assert args.db == "oscar.db"
    assert args.profile == "Default"


def test_main_serve(monkeypatch):
    from unittest.mock import MagicMock
    from oscarius import __main__

    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.run", mock_run)
    monkeypatch.setattr("sys.argv", ["oscarius", "serve", "--port", "9999"])

    __main__.main()
    mock_run.assert_called_once_with(
        "oscarius.api.app:app",
        host="127.0.0.1",
        port=9999,
        reload=False,
    )


def test_main_import(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    from oscarius import __main__
    from oscarius.importers.resmed import ImportResult

    card_dir = tmp_path / "card"
    card_dir.mkdir()

    mock_detect = MagicMock(return_value=True)
    mock_import = MagicMock(
        return_value=ImportResult(
            sessions_imported=3,
            days_updated=2,
            brand="ResMed",
            model="AirSense 11 AutoSet",
            serial_number="23249988776",
        )
    )

    monkeypatch.setattr("oscarius.importers.resmed.detect_resmed_card", mock_detect)
    monkeypatch.setattr("oscarius.importers.resmed.import_resmed_sd_card", mock_import)
    monkeypatch.setattr("sys.argv", ["oscarius", "import", str(card_dir), "--profile", "Erwin"])

    __main__.main()
    mock_detect.assert_called_once_with(card_dir)
    mock_import.assert_called_once_with(
        card_path=card_dir,
        db_path="oscar.db",
        username="Erwin",
    )
