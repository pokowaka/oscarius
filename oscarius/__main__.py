"""Command-line entrypoint for launching the Oscarius backend server and CLI tools."""

import argparse
import os
from pathlib import Path
import sys
import uvicorn


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command line arguments for Oscarius commands."""
    raw_args = list(args if args is not None else sys.argv[1:])

    # Default to 'serve' subcommand if empty or first arg is an option flag
    if not raw_args or raw_args[0].startswith("-"):
        raw_args = ["serve"] + raw_args

    parser = argparse.ArgumentParser(
        prog="oscarius",
        description="Oscarius: Web-based CPAP and sleep therapy analysis backend.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # serve subcommand
    serve_parser = subparsers.add_parser(
        "serve", help="Run the Oscarius REST API server."
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port to listen on (default: 8000).",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reloading when source files change (development only).",
    )

    # import subcommand
    import_parser = subparsers.add_parser(
        "import", help="Import CPAP SD card data into an OSCAR database."
    )
    import_parser.add_argument(
        "card_path",
        help="Path to the CPAP SD card directory.",
    )
    import_parser.add_argument(
        "--db",
        default=os.environ.get("OSCAR_DB", "oscar.db"),
        help="Path to the target OSCAR SQLite database file (default: $OSCAR_DB or oscar.db).",
    )
    import_parser.add_argument(
        "--profile",
        default="Default",
        help="Profile username to import data under (default: Default).",
    )

    return parser.parse_args(raw_args)


def main() -> None:
    """Main execution function."""
    args = parse_args()
    if args.command == "serve":
        uvicorn.run(
            "oscarius.api.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    elif args.command == "import":
        from oscarius.importers.resmed import detect_resmed_card, import_resmed_sd_card

        card_dir = Path(args.card_path)
        if not card_dir.is_dir():
            print(f"Error: SD card path '{args.card_path}' is not a directory.", file=sys.stderr)
            sys.exit(1)

        if not detect_resmed_card(card_dir):
            print(
                f"Error: Path '{args.card_path}' is not recognized as a valid ResMed SD card.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"Importing ResMed SD card from '{card_dir}' into '{args.db}' (Profile: {args.profile})..."
        )
        result = import_resmed_sd_card(
            card_path=card_dir,
            db_path=args.db,
            username=args.profile,
        )
        print("Import complete!")
        print(f"  Device: {result.brand} {result.model} (S/N: {result.serial_number})")
        print(f"  Sessions imported: {result.sessions_imported}")
        print(f"  Days updated: {result.days_updated}")


if __name__ == "__main__":
    main()
