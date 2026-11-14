"""Writes the `/bulk-buyer` and `/bulk-seller` template files into
`ddl_commands/bulk_templates/`. Terraform uploads those files to the public
templates bucket (`infrastructure/terraform/stacks/assets`), and a unit test
fails when the committed files differ from the field definitions, so run this
after changing any field and commit the result.

    uv run python -m app.modules.ddl_commands.scripts.generate_bulk_templates
"""

from pathlib import Path

from app.modules.ddl_commands.api.bulk_columns import template_csv, template_filename
from app.modules.ddl_commands.api.bulk_store import UploadKind

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "bulk_templates"
KINDS: tuple[UploadKind, ...] = ("buyer", "seller")


def main() -> None:
    TEMPLATES_DIR.mkdir(exist_ok=True)
    for kind in KINDS:
        path = TEMPLATES_DIR / template_filename(kind)
        path.write_bytes(template_csv(kind))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
