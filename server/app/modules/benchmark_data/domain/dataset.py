"""The benchmark peer dataset as framework-free values, and the rules an edit
must satisfy before it is saved. Pure."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal
from uuid import UUID

Mode = Literal["sme", "tech"]

# [p10, p25, p50, p75, p90]
Anchors = tuple[float, float, float, float, float]

# The metric weights of a mode must add up to this, so a score stays a weighted
# average of percentiles.
WEIGHT_TOTAL = 100


# The metric keys the scoring code computes per mode. A new metric is a code change, so
# these are fixed. An integration test checks them against the stored rules and anchors.
METRIC_KEYS: Mapping[Mode, tuple[str, ...]] = {
    "sme": ("ebitda", "growth", "revEmp", "conc", "gm", "rent", "recur"),
    "tech": ("growth", "capEff", "revScale", "gm", "recur", "conc"),
}
# Peer cuts also carry anchors for these, but nothing scores them and they have no weight:
# `dso` (sme) and `fwdMult` (tech, the forward revenue multiple behind the implied value).
ANCHOR_ONLY_KEYS: Mapping[Mode, tuple[str, ...]] = {"sme": ("dso",), "tech": ("fwdMult",)}


class InvalidEditError(ValueError):
    """An edit that would leave the dataset inconsistent."""


class UnknownRecordError(LookupError):
    """The band, metric or peer cut an edit names does not exist."""


@dataclass(frozen=True)
class Editor:
    """The signed-in person making an edit."""

    slack_user_id: str
    name: str | None = None

    @property
    def label(self) -> str:
        """What rows show as `updated_by`: their name, so it reads as a person."""
        return self.name or self.slack_user_id


@dataclass(frozen=True)
class Band:
    """A revenue peer band. `max_usd` is None on the open-ended top band."""

    id: UUID
    code: str
    label: str
    max_usd: float | None
    ebitda_adj: float
    rev_emp_mult: float
    rent_mult: float
    # Who last changed the row, by name, and when.
    updated_by: str
    updated_at: datetime


@dataclass(frozen=True)
class Metric:
    id: UUID
    key: str
    label: str
    unit: str
    higher_is_better: bool
    weight: int
    observed: bool | None
    updated_by: str
    updated_at: datetime


@dataclass(frozen=True)
class PeerCut:
    """One sector (`sme`) or funding stage (`tech`) and the anchors a
    submission is ranked against."""

    id: UUID
    mode: Mode
    key: str
    label: str
    sample_size: int | None
    multi_site: bool
    b2b: bool
    anchors: Mapping[str, Anchors]
    updated_by: str
    updated_at: datetime


@dataclass(frozen=True)
class BenchmarkDataset:
    updated_at: datetime
    bands: tuple[Band, ...]
    metrics: Mapping[Mode, Mapping[str, Metric]]
    cuts: Mapping[Mode, Mapping[str, PeerCut]]


@dataclass(frozen=True)
class PercentileEdit:
    """New values for some of one metric's five anchors. The rest keep their value."""

    p10: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p90: float | None = None

    def onto(self, metric: str, current: Anchors | None) -> Anchors:
        """`current` with these percentiles replaced, or InvalidEditError."""
        sent = (self.p10, self.p25, self.p50, self.p75, self.p90)
        if all(value is None for value in sent):
            raise InvalidEditError(f"{metric}: name at least one percentile to change")
        if current is None:
            raise InvalidEditError(f"{metric}: it has no anchors yet, so send all five")
        p10, p25, p50, p75, p90 = (
            old if new is None else new for old, new in zip(current, sent, strict=True)
        )
        return (p10, p25, p50, p75, p90)


@dataclass(frozen=True)
class PeerCutEdit:
    """Fields left None are unchanged. Anchors are all five values for a metric, or a
    `PercentileEdit` naming only the ones to change."""

    sample_size: int | None = None
    multi_site: bool | None = None
    b2b: bool | None = None
    anchors: Mapping[str, Anchors | PercentileEdit] | None = None


@dataclass(frozen=True)
class BandEdit:
    """Fields left None are unchanged. The top band stays open-ended."""

    label: str | None = None
    max_usd: float | None = None
    ebitda_adj: float | None = None
    rev_emp_mult: float | None = None
    rent_mult: float | None = None


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvalidEditError(f"{name} must be a finite number, got {value}")


def check_anchors(metric: str, anchors: Anchors) -> None:
    for value in anchors:
        _finite(metric, value)
    if any(later < earlier for earlier, later in zip(anchors, anchors[1:], strict=False)):
        raise InvalidEditError(f"{metric}: anchors must rise from p10 to p90, got {list(anchors)}")


def apply_peer_cut_edit(cut: PeerCut, edit: PeerCutEdit, metrics: Mapping[str, Metric]) -> PeerCut:
    """The cut after the edit, or InvalidEditError."""
    anchors = dict(cut.anchors)
    for metric, change in (edit.anchors or {}).items():
        if metric not in cut.anchors and metric not in metrics:
            raise InvalidEditError(f"{metric}: not a metric of {cut.mode} mode")
        values = (
            change.onto(metric, cut.anchors.get(metric))
            if isinstance(change, PercentileEdit)
            else change
        )
        check_anchors(metric, values)
        anchors[metric] = values
    if edit.sample_size is not None and edit.sample_size < 0:
        raise InvalidEditError("sample_size cannot be negative")
    return replace(
        cut,
        sample_size=cut.sample_size if edit.sample_size is None else edit.sample_size,
        multi_site=cut.multi_site if edit.multi_site is None else edit.multi_site,
        b2b=cut.b2b if edit.b2b is None else edit.b2b,
        anchors=anchors,
    )


def apply_band_edit(bands: tuple[Band, ...], code: str, edit: BandEdit) -> tuple[Band, ...]:
    """All bands after the edit, or InvalidEditError.

    Bands are checked together because the ceilings must keep rising and only
    the last band may be open-ended.
    """
    if code not in {b.code for b in bands}:
        raise UnknownRecordError(f"No revenue band '{code}'")
    updated = tuple(
        replace(
            b,
            label=b.label if edit.label is None else edit.label,
            max_usd=b.max_usd if edit.max_usd is None else edit.max_usd,
            ebitda_adj=b.ebitda_adj if edit.ebitda_adj is None else edit.ebitda_adj,
            rev_emp_mult=b.rev_emp_mult if edit.rev_emp_mult is None else edit.rev_emp_mult,
            rent_mult=b.rent_mult if edit.rent_mult is None else edit.rent_mult,
        )
        if b.code == code
        else b
        for b in bands
    )
    for b in updated:
        _finite(f"{b.code} ebitda_adj", b.ebitda_adj)
        _finite(f"{b.code} rev_emp_mult", b.rev_emp_mult)
        _finite(f"{b.code} rent_mult", b.rent_mult)
        if b.max_usd is not None:
            _finite(f"{b.code} max_usd", b.max_usd)
            if b.max_usd <= 0:
                raise InvalidEditError(f"{b.code}: the revenue ceiling must be above zero")
        if b.rev_emp_mult <= 0 or b.rent_mult <= 0:
            raise InvalidEditError(f"{b.code}: multipliers must be above zero")
    ceilings = [b.max_usd for b in updated[:-1]]
    if updated[-1].max_usd is not None or None in ceilings:
        raise InvalidEditError("Only the top band is open-ended")
    known = [c for c in ceilings if c is not None]
    if any(later <= earlier for earlier, later in zip(known, known[1:], strict=False)):
        raise InvalidEditError("Band ceilings must rise from the smallest band to the largest")
    return updated


def check_weights(current: Mapping[str, Metric], weights: Mapping[str, int]) -> None:
    """Weights must name exactly the mode's metrics and add up to 100."""
    if set(weights) != set(current):
        raise InvalidEditError(f"Give a weight for every metric: {sorted(current)}")
    if any(w < 0 for w in weights.values()):
        raise InvalidEditError("Weights cannot be negative")
    total = sum(weights.values())
    if total != WEIGHT_TOTAL:
        raise InvalidEditError(f"Weights must add up to {WEIGHT_TOTAL}, got {total}")


def changed_peer_cut_fields(before: PeerCut, after: PeerCut) -> tuple[str, ...]:
    """Field names that differ, with one `anchors.<metric>` entry per changed metric."""
    names = [
        name
        for name in ("sample_size", "multi_site", "b2b")
        if getattr(before, name) != getattr(after, name)
    ]
    names += [
        f"anchors.{metric}"
        for metric in sorted(after.anchors)
        if before.anchors.get(metric) != after.anchors[metric]
    ]
    return tuple(names)


def changed_band_fields(before: Band, after: Band) -> tuple[str, ...]:
    return tuple(
        name
        for name in ("label", "max_usd", "ebitda_adj", "rev_emp_mult", "rent_mult")
        if getattr(before, name) != getattr(after, name)
    )
