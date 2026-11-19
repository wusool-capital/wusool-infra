"""Text in the lead tools stays readable. The tools draw secondary text as navy at low
opacity; at 28% it was 1.9:1 on white, and the valuation tool's #888 grey was 3.5:1.
WCAG AA asks 4.5:1 for small text, checked here on every background the text can sit on."""

import re
from pathlib import Path

import pytest

_STATIC = Path(__file__).parents[2] / "static"
_AA = 4.5
_NAVY = (0, 5, 35)
_WHITE = (255, 255, 255)
Rgb = tuple[float, float, float]


def _blend(fg: Rgb, alpha: float, bg: Rgb) -> Rgb:
    return (
        fg[0] * alpha + bg[0] * (1 - alpha),
        fg[1] * alpha + bg[1] * (1 - alpha),
        fg[2] * alpha + bg[2] * (1 - alpha),
    )


def _luminance(rgb: Rgb) -> float:
    def channel(value: float) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])


def _contrast(a: Rgb, b: Rgb) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _hex(value: str) -> Rgb:
    digits = value.lstrip("#")
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


# The page, a card, a tint behind a note or pill, and the sky-blue pills.
_BACKGROUNDS: dict[str, Rgb] = {
    "white": _WHITE,
    "paper": (247, 245, 240),
    "mist": (245, 245, 245),
    "navy 5%": _blend(_NAVY, 0.05, _WHITE),
    "sky": (198, 225, 238),
    "sky 30%": _blend((198, 225, 238), 0.30, _WHITE),
    "sky 70%": _blend((198, 225, 238), 0.70, _WHITE),
}
_GREY_BACKGROUNDS: dict[str, Rgb] = {
    "white": _WHITE,
    "paper": (247, 245, 240),
    "#f8f8f8": (248, 248, 248),
    "#f0f0f0": (240, 240, 240),
    "#e8e8e8": (232, 232, 232),
}


def _css(tool: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (_STATIC / tool / "00-styles.css").read_text(), flags=re.S)


def _navy_text_rules(css: str) -> list[tuple[str, float]]:
    """(selector, opacity) for every rule whose text colour is navy at under 80%."""
    tokens = {
        name: float(alpha)
        for name, alpha in re.findall(r"(--navy-\d+):rgba\(0,5,35,([.\d]+)\)", css)
    }
    found: list[tuple[str, float]] = []
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        color = re.search(r"(?<![-\w])color\s*:\s*([^;}]+)", rule.group(2))
        if color is None:
            continue
        value = color.group(1).strip()
        token = re.fullmatch(r"var\((--navy-\d+)\)", value)
        literal = re.fullmatch(r"rgba\(\s*0\s*,\s*5\s*,\s*35\s*,\s*([.\d]+)\s*\)", value)
        alpha = (
            tokens.get(token.group(1)) if token else float(literal.group(1)) if literal else None
        )
        if alpha is not None and alpha < 0.8:
            found.append((rule.group(1).strip(), alpha))
    return found


_NAVY_TOOLS = ["benchmark", "buyers", "get-started", "readiness", "report"]


@pytest.mark.parametrize("tool", _NAVY_TOOLS)
def test_faint_navy_text_is_readable_on_every_background(tool: str) -> None:
    rules = _navy_text_rules(_css(tool))

    assert rules, "the check found no faint text; the stylesheet format may have changed"
    weak = {
        selector: round(worst, 2)
        for selector, alpha in rules
        if (worst := min(_contrast(_blend(_NAVY, alpha, bg), bg) for bg in _BACKGROUNDS.values()))
        < _AA
    }
    assert weak == {}


def test_the_metric_row_labels_in_the_benchmark_are_readable() -> None:
    by_selector = dict(_navy_text_rules(_css("benchmark")))

    for selector in (".medlab", ".qlabels span", ".pill.q1", ".cover"):
        assert selector in by_selector, selector
        assert _contrast(_blend(_NAVY, by_selector[selector], _WHITE), _WHITE) >= _AA


def test_the_valuation_grey_is_readable_on_the_backgrounds_it_is_used_on() -> None:
    css = _css("valuation")
    token = re.search(r"--gg:(#[0-9a-fA-F]{3,6})", css)
    assert token is not None
    grey = _hex(token.group(1))

    weak = {n: round(_contrast(grey, bg), 2) for n, bg in _GREY_BACKGROUNDS.items()}
    assert min(weak.values()) >= _AA, weak


def test_the_valuation_green_badges_are_readable_on_their_tint() -> None:
    css = _css("valuation")
    badges = re.findall(r"\.(?:ok-badge|dcf-auto-badge)\{[^}]*?color:(#[0-9a-fA-F]{6})", css)

    assert len(badges) == 2
    assert all(_contrast(_hex(color), _hex("#f0fff8")) >= _AA for color in badges)
