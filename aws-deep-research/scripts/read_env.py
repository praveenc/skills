#!/usr/bin/env python3
"""Read one dotenv value literally without evaluating shell syntax."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

_VALID_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INLINE_COMMENT = re.compile(r"\s+#")


def config_path() -> Path:
    """Return the external machine-local config path."""
    configured = os.environ.get("AWS_DEEP_RESEARCH_CONFIG")
    return (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config/aws-deep-research/config.env"
    )


def read_env_value(path: Path, key: str) -> str:
    """Return the last literal value assigned to key, or an empty string."""
    if not _VALID_KEY.fullmatch(key) or not path.is_file():
        return ""

    result = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()

        name, separator, raw_value = line.partition("=")
        if not separator or name.strip() != key:
            continue

        value = raw_value.strip()
        if value[:1] in {"'", '"'}:
            quote = value[0]
            closing = value.rfind(quote)
            remainder = value[closing + 1 :] if closing > 0 else ""
            if closing > 0 and re.fullmatch(r"\s*(?:#.*)?", remainder):
                value = value[1:closing]
        else:
            comment = _INLINE_COMMENT.search(value)
            if comment:
                value = value[: comment.start()].rstrip()
        result = value

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read one dotenv value without shell expansion.",
    )
    parser.add_argument("env_file", type=Path)
    parser.add_argument("key")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(read_env_value(args.env_file, args.key))


if __name__ == "__main__":
    main()
