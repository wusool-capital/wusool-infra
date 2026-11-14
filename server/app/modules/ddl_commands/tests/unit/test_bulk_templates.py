"""The committed template files are what Terraform uploads, so they must match
the field definitions. Fails the build the day a field changes without them."""

import pytest

from app.modules.ddl_commands.api.bulk_columns import template_csv, template_filename
from app.modules.ddl_commands.api.bulk_store import UploadKind
from app.modules.ddl_commands.scripts.generate_bulk_templates import KINDS, TEMPLATES_DIR

CARRIAGE_RETURN = b"\r"


@pytest.mark.parametrize("kind", KINDS)
def test_the_committed_template_matches_the_field_definitions(kind: UploadKind) -> None:
    committed = (TEMPLATES_DIR / template_filename(kind)).read_bytes()

    assert committed == template_csv(kind), (
        "Template out of date. Run: "
        "uv run python -m app.modules.ddl_commands.scripts.generate_bulk_templates"
    )


@pytest.mark.parametrize("kind", KINDS)
def test_the_committed_template_has_no_windows_line_endings(kind: UploadKind) -> None:
    # Terraform uploads the file byte for byte; a CRLF checkout would show as a change.
    assert CARRIAGE_RETURN not in (TEMPLATES_DIR / template_filename(kind)).read_bytes()


@pytest.mark.parametrize("kind", KINDS)
def test_the_committed_template_opens_in_excel_with_arabic_support(kind: UploadKind) -> None:
    assert (TEMPLATES_DIR / template_filename(kind)).read_bytes().startswith(b"\xef\xbb\xbf")
