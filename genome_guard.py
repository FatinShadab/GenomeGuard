"""Thin root entry-point shim — delegates to the installed package CLI."""

from genomeguard.cli import main

if __name__ == "__main__":
    main()
