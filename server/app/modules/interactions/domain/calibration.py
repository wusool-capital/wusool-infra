"""Comparing our connection-strength labels with the ones Attio computed for Companies.

Pure: the caller supplies both sides. A Company is compared only when Attio's label is a fair
reference, so every other case lands in a named bucket and is counted, never silently dropped.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.modules.interactions.domain.addresses import team_member_of
from app.modules.interactions.domain.linking import RecordDirectory, organization_by_domain
from app.modules.interactions.domain.model import StrengthLabel

EXACT_GATE = 0.80
WITHIN_ONE_GATE = 0.95
TECH_ADDRESS = "tech@wusoolcapital.com"

_LEVELS = list(StrengthLabel)


class Bucket(StrEnum):
    COMPARED = "compared"
    NO_ATTIO_LABEL = "Attio has no label"
    TECH_USER = "Attio's strongest user is tech@"
    UNREAD_MAILBOX = "Attio's strongest user is a mailbox we don't read"
    NO_ORGANIZATION = "no Organization has the Company's domain"
    AMBIGUOUS = "domain or Organization shared by several records"
    NO_TOUCHES = "Attio has a label, we have no interactions"


@dataclass(frozen=True)
class CompanyInput:
    record_id: str
    domains: tuple[str, ...]
    attio_label: StrengthLabel | None
    # Attio's strongest user as an address; None when Attio names nobody.
    strongest_user: str | None


@dataclass(frozen=True)
class CalibrationReport:
    compared: int
    exact: int
    within_one: int
    # Rows are Attio's label, columns ours, both weakest to strongest.
    matrix: tuple[tuple[int, ...], ...]
    excluded: Mapping[Bucket, int]
    mismatch_ids: tuple[str, ...] = field(default=())

    @property
    def exact_rate(self) -> float | None:
        return self.exact / self.compared if self.compared else None

    @property
    def within_one_rate(self) -> float | None:
        return self.within_one / self.compared if self.compared else None

    @property
    def passes_gate(self) -> bool:
        return (
            self.exact_rate is not None
            and self.within_one_rate is not None
            and self.exact_rate >= EXACT_GATE
            and self.within_one_rate >= WITHIN_ONE_GATE
        )


def parse_label(raw: str | None) -> StrengthLabel | None:
    try:
        return StrengthLabel(raw) if raw else None
    except ValueError:
        return None


def calibrate(
    companies: Sequence[CompanyInput],
    directory: RecordDirectory,
    ours: Mapping[str, StrengthLabel | None],
    read_mailboxes: frozenset[str],
    internal_domains: tuple[str, ...],
) -> CalibrationReport:
    """`ours` maps an Organization id to our label; a missing id or None means no interactions."""
    matched = {c.record_id: _match(c, directory) for c in companies}
    organizations = Counter(m[0] for m in matched.values() if m[0] is not None)

    excluded: Counter[Bucket] = Counter()
    pairs: list[tuple[str, StrengthLabel, StrengthLabel]] = []
    for company in companies:
        attio_label = company.attio_label
        if attio_label is None:
            excluded[Bucket.NO_ATTIO_LABEL] += 1
            continue
        org_id, ambiguous = matched[company.record_id]
        bucket = _exclusion(
            company, org_id, ambiguous, organizations, read_mailboxes, internal_domains
        )
        if bucket is not None:
            excluded[bucket] += 1
            continue
        our_label = ours.get(org_id) if org_id is not None else None
        if our_label is None:
            excluded[Bucket.NO_TOUCHES] += 1
            continue
        pairs.append((company.record_id, attio_label, our_label))

    size = len(_LEVELS)
    matrix = [[0] * size for _ in range(size)]
    exact = within_one = 0
    mismatches: list[str] = []
    for record_id, attio_label, our_label in pairs:
        attio_level, our_level = _LEVELS.index(attio_label), _LEVELS.index(our_label)
        matrix[attio_level][our_level] += 1
        exact += attio_level == our_level
        within_one += abs(attio_level - our_level) <= 1
        if attio_level != our_level:
            mismatches.append(record_id)
    return CalibrationReport(
        compared=len(pairs),
        exact=exact,
        within_one=within_one,
        matrix=tuple(tuple(row) for row in matrix),
        excluded=dict(excluded),
        mismatch_ids=tuple(mismatches),
    )


def _match(company: CompanyInput, directory: RecordDirectory) -> tuple[str | None, bool]:
    """The one Organization the Company's domains point to, and whether they were ambiguous."""
    found: set[str] = set()
    ambiguous = False
    for domain in company.domains:
        org_id, ambiguity = organization_by_domain(domain.lower().removeprefix("www."), directory)
        if ambiguity is not None:
            ambiguous = True
        if org_id is not None:
            found.add(org_id)
    if len(found) > 1:
        return None, True
    return (next(iter(found)) if found else None), ambiguous


def _exclusion(
    company: CompanyInput,
    org_id: str | None,
    ambiguous: bool,
    organizations: Counter[str | None],
    read_mailboxes: frozenset[str],
    internal_domains: tuple[str, ...],
) -> Bucket | None:
    user = (
        team_member_of(company.strongest_user, internal_domains) if company.strongest_user else None
    )
    if user == team_member_of(TECH_ADDRESS, internal_domains):
        return Bucket.TECH_USER
    if user is None or user not in read_mailboxes:
        return Bucket.UNREAD_MAILBOX
    if ambiguous or (org_id is not None and organizations[org_id] > 1):
        return Bucket.AMBIGUOUS
    if org_id is None:
        return Bucket.NO_ORGANIZATION
    return None
