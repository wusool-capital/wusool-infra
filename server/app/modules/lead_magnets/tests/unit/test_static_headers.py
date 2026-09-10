"""CSP and cache policy for the embeddable tool pages.

Uses a temporary directory rather than the real `static/`, since the fixture
needs to construct both a served-and-unserved case for the trailing-slash
test below — the headers and serving behaviour are independent of which
tool's content is present.
"""

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from app.modules.lead_magnets.api.static import ToolStatic


@pytest.fixture
def client(tmp_path):
    (tmp_path / "img").mkdir()
    (tmp_path / "valuation").mkdir()
    (tmp_path / "embed.js").write_text("// loader")
    (tmp_path / "img" / "abc12345.png").write_bytes(b"\x89PNG")
    (tmp_path / "valuation" / "index.html").write_text("<h1>valuation</h1>")
    (tmp_path / "valuation" / "00-styles.css").write_text("body{}")

    app = Starlette()
    app.mount("/", ToolStatic(directory=tmp_path, html=True), name="tools")
    return TestClient(app, follow_redirects=False)


def test_frame_ancestors_is_set_and_xfo_is_not(client) -> None:
    """`X-Frame-Options` has no working allow-list value, so setting it at
    all would block the Webflow embed outright."""
    response = client.get("/embed.js")
    assert response.status_code == 200
    assert "frame-ancestors" in response.headers["content-security-policy"]
    assert "wusoolcapital.com" in response.headers["content-security-policy"]
    assert "x-frame-options" not in response.headers


def test_embed_js_is_short_cached(client) -> None:
    """It is both the cutover switch and the rollback switch — a long TTL
    here is how a rollback takes an hour instead of a minute."""
    assert client.get("/embed.js").headers["cache-control"] == "public, max-age=60"


def test_content_addressed_images_are_immutable(client) -> None:
    response = client.get("/img/abc12345.png")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_tool_page_is_short_cached_and_nosniff(client) -> None:
    response = client.get("/valuation/", follow_redirects=True)
    assert response.headers["cache-control"] == "public, max-age=60"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_content_types_are_correct_for_scripts_and_stylesheets(client) -> None:
    """`nosniff` is set unconditionally — a `.js`/`.css` file served with
    the wrong (or no) content-type would be refused outright by the
    browser, breaking the page silently rather than loudly. `.jsx` would
    resolve to `None` via `mimetypes` and serve as `text/plain`, which is
    why every extracted script must be `.js`, never `.jsx`."""
    assert client.get("/embed.js").headers["content-type"] == "text/javascript; charset=utf-8"
    css = client.get("/valuation/00-styles.css")
    assert css.status_code == 200
    assert css.headers["content-type"] == "text/css; charset=utf-8"


def test_bare_tool_name_redirects_to_the_trailing_slash_form(client) -> None:
    """Folder-per-tool, `index.html` included: `/valuation` is a directory
    path, not a file, so Starlette's `html=True` 307-redirects it to
    `/valuation/` rather than 404ing the way a flat `valuation.html` would
    have. Verified against this repo's pinned Starlette (1.6.0) — both
    forms work, but `embed.js` must use the trailing-slash form to avoid
    paying this redirect on every load."""
    bare = client.get("/valuation")
    assert bare.status_code == 307
    assert bare.headers["location"].endswith("/valuation/")
    # The redirect itself still carries the module's headers — nothing
    # about the split shape weakens the CSP/cache-control guarantee.
    assert "frame-ancestors" in bare.headers["content-security-policy"]

    assert client.get("/valuation/").status_code == 200
    assert client.get("/valuation/index.html").status_code == 200
