"""Compatibility entry point: use the same implementation as the CLI."""

from shoplakehouse.cli import app

if __name__ == "__main__":
    app(["generate", *__import__("sys").argv[1:]])
