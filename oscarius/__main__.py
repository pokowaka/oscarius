"""Command-line entrypoint for launching the Oscarius backend server."""

import argparse
import sys
import uvicorn


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command line arguments for the Oscarius server."""
    parser = argparse.ArgumentParser(
        prog="oscarius",
        description="Oscarius: Web-based CPAP and sleep therapy analysis backend.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port to listen on (default: 8000).",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reloading when source files change (development only).",
    )
    return parser.parse_args(args if args is not None else sys.argv[1:])


def main() -> None:
    """Main execution function."""
    args = parse_args()
    uvicorn.run(
        "oscarius.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
