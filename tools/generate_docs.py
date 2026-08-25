"""Generate the register and polling-group documentation from ``REGISTERS``."""

from __future__ import annotations

import argparse
from pathlib import Path

from custom_components.solvis_control.const import REGISTERS


REPOSITORY_ROOT = Path(__file__).parents[1]
REGISTER_TABLE_PATH = REPOSITORY_ROOT / "supported-entities.md"
POLLING_GROUP_TABLE_PATH = REPOSITORY_ROOT / "polling-groups.md"

PLATFORMS = {
    0: "sensor",
    1: "select",
    2: "number",
    3: "switch",
    4: "binary_sensor",
    5: "update",
    6: "block",
}
POLLING_GROUPS = {0: "default", 1: "slow", 2: "high"}
REGISTER_TYPES = {1: "input", 2: "holding"}


def _cell(value: object | None) -> str:
    """Render a value safely inside a Markdown table cell."""
    if value is None or value == "":
        return "—"
    return str(value).replace("|", r"\|")


def render_register_table() -> str:
    """Render every register definition as a Markdown table."""
    lines = [
        "# SolvisLeo 180 register table",
        "",
        "This file is generated from `custom_components/solvis_control/const.py`. Do not edit it by hand; run `python -m tools.generate_docs --write` after changing `REGISTERS`. Implementation identifiers are raw code keys, not display names.",
        "",
        "| Address | Implementation identifier | Register type | Platform | Data type | Count | Byte swap | Multiplier | Unit | Enabled by default |",
        "| ---: | --- | --- | --- | --- | ---: | --- | ---: | --- | --- |",
    ]

    for register in REGISTERS:
        lines.append(
            "| "
            + " | ".join(
                (
                    _cell(register.address),
                    _cell(register.name),
                    _cell(REGISTER_TYPES[register.register]),
                    _cell(PLATFORMS[register.input_type]),
                    _cell(register.datatype),
                    _cell(register.count),
                    "yes" if register.byte_swap else "no",
                    _cell(register.multiplier),
                    _cell(register.unit),
                    "yes" if register.enabled_by_default else "no",
                )
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def render_polling_group_table() -> str:
    """Render the polling group for every register definition."""
    lines = [
        "# SolvisLeo 180 polling groups",
        "",
        "This file is generated from `custom_components/solvis_control/const.py`. Do not edit it by hand; run `python -m tools.generate_docs --write` after changing `REGISTERS`. Implementation identifiers are raw code keys, not display names.",
        "",
        "| Polling group | Address | Implementation identifier | Platform |",
        "| --- | ---: | --- | --- |",
    ]

    for register in REGISTERS:
        lines.append(
            "| "
            + " | ".join(
                (
                    POLLING_GROUPS[register.poll_rate],
                    _cell(register.address),
                    _cell(register.name),
                    PLATFORMS[register.input_type],
                )
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def render_documents() -> dict[Path, str]:
    """Return the generated contents keyed by their committed paths."""
    return {
        REGISTER_TABLE_PATH: render_register_table(),
        POLLING_GROUP_TABLE_PATH: render_polling_group_table(),
    }


def write_documents() -> None:
    """Write the current generated documentation to the repository."""
    for path, contents in render_documents().items():
        path.write_text(contents, encoding="utf-8")


def check_documents() -> list[Path]:
    """Return the committed documentation files that differ from the generator."""
    return [path for path, contents in render_documents().items() if not path.exists() or path.read_text(encoding="utf-8") != contents]


def parse_args() -> argparse.Namespace:
    """Parse the documentation generator command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail when committed documentation is stale")
    mode.add_argument("--write", action="store_true", help="update the committed documentation")
    return parser.parse_args()


def main() -> int:
    """Run the documentation generator."""
    args = parse_args()
    if args.write:
        write_documents()
        return 0

    stale = check_documents()
    if stale:
        print("Generated documentation is stale:")
        for path in stale:
            print(f"- {path.relative_to(REPOSITORY_ROOT)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
