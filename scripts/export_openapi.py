"""Export the deterministic API client contract committed under docs/."""

from __future__ import annotations

import json
from pathlib import Path

from osip_dashboard.main import app


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "openapi.json"


def render_contract() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    DEFAULT_OUTPUT.write_text(render_contract(), encoding="utf-8")
    print(f"Wrote {DEFAULT_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
