# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.32.0",
#   "rich>=14.3.3",
# ]
# ///
"""
Kroki Diagram Renderer - renders D2 diagram source to SVG/PNG.

Connects to an explicitly configured Kroki instance or local Docker and
renders D2 diagram-as-code source into SVG or PNG images.

Endpoint resolution (tiered):
  1. KROKI_URL env var or --url flag (explicit opt-in)
  2. Auto-detect local Docker: http://localhost:8000
  3. Fail gracefully if none available

Usage:
    uv run kroki_diagram.py -i diagram.d2 -o output/diagrams/arch.svg
    uv run kroki_diagram.py --inline 'a -> b: HTTPS' -o flow.svg
    uv run kroki_diagram.py -i diagram.d2 -o arch.png --format png
    uv run kroki_diagram.py -i diagram.d2 -o arch.svg --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from rich.console import Console

from read_env import config_path, read_env_value

console = Console(stderr=True)

LOCAL_KROKI = "http://localhost:8000"


def resolve_endpoint(explicit_url: str | None = None) -> tuple[str, str]:
    """Resolve Kroki endpoint. Returns (url, source_label)."""
    # 1. Explicit URL (flag or env var)
    url = (
        explicit_url
        or os.environ.get("KROKI_URL")
        or read_env_value(config_path(), "KROKI_URL")
    )
    if url and url.lower() == "disabled":
        return "", "disabled"
    if url:
        url = url.rstrip("/")
        try:
            r = requests.get(f"{url}/health", timeout=5)
            if r.ok:
                if not url.startswith(("http://localhost", "http://127.0.0.1")):
                    console.print(
                        "[yellow]⚠ Diagram content will be sent to the configured Kroki endpoint.[/yellow]"
                    )
                return url, f"explicit ({url})"
        except requests.ConnectionError:
            console.print(f"[yellow]⚠ Configured KROKI_URL={url} unreachable[/yellow]")

    # 2. Auto-detect local Docker
    try:
        r = requests.get(f"{LOCAL_KROKI}/health", timeout=3)
        if r.ok:
            return LOCAL_KROKI, f"local Docker ({LOCAL_KROKI})"
    except requests.ConnectionError:
        pass

    return "", "none"


def render_d2(
    endpoint: str,
    source: str,
    output_format: str = "svg",
    timeout: int = 30,
) -> bytes:
    """POST D2 source to Kroki, return rendered bytes."""
    url = f"{endpoint}/d2/{output_format}"
    resp = requests.post(
        url,
        data=source.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.content


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Render D2 diagrams via Kroki (self-hosted or remote).",
    )
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-i", "--input", type=str, help="D2 source file path"
    )
    input_group.add_argument(
        "--inline", type=str, help="Inline D2 source string"
    )
    p.add_argument(
        "-o", "--output", required=True, help="Output file path (.svg or .png)"
    )
    p.add_argument(
        "--format",
        choices=["svg", "png"],
        default=None,
        help="Output format (default: inferred from output extension)",
    )
    p.add_argument(
        "--url", type=str, default=None, help="Explicit Kroki endpoint URL"
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()

    # Resolve D2 source
    if args.input:
        source_path = Path(args.input)
        if not source_path.exists():
            console.print(f"[red]✗ Input file not found: {source_path}[/red]")
            sys.exit(1)
        source = source_path.read_text(encoding="utf-8")
    else:
        source = args.inline

    if not source.strip():
        console.print("[red]✗ Empty D2 source[/red]")
        sys.exit(1)

    # Resolve output format
    out_path = Path(args.output)
    if args.format:
        fmt = args.format
    elif out_path.suffix.lower() == ".png":
        fmt = "png"
    else:
        fmt = "svg"

    # Resolve endpoint
    endpoint, label = resolve_endpoint(args.url)
    if not endpoint:
        console.print("[red]✗ No Kroki endpoint available.[/red]")
        console.print("[dim]  Self-host: docker run -d -p 8000:8000 yuzutech/kroki[/dim]")
        console.print("[dim]  Or set KROKI_URL in ~/.config/aws-deep-research/config.env[/dim]")
        sys.exit(1)

    console.print(f"[bold]Rendering D2 → {fmt.upper()} via {label}[/bold]")

    # Render
    try:
        content = render_d2(endpoint, source, fmt, args.timeout)
    except requests.HTTPError as e:
        console.print(f"[red]✗ Kroki render failed: {e}[/red]")
        if e.response is not None:
            console.print(f"[dim]{e.response.text[:500]}[/dim]")
        sys.exit(1)

    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(content)

    console.print(f"[green]✓ {out_path} ({len(content):,} bytes)[/green]")
    # Minimal stdout for calling agent
    print(f'{{"status":"success","output":"{out_path}","bytes":{len(content)},"format":"{fmt}","endpoint":"{label}"}}')


if __name__ == "__main__":
    main()
