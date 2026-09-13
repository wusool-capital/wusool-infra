"""Builds an `EnrichmentProposal` for a target: read current values, skip
fields that are already populated, try structured company-data providers
(organization fields only, for either role — see `_structured_lookup`),
then research + extract via the LLM path for whatever's still missing.
Never writes anything — see `ReviewMixin` for that.
"""

import json
from datetime import date

from app.modules.enrichment.application.base import ServiceBase
from app.modules.enrichment.domain.field_plans import (
    EnrichableField,
    WriteTarget,
    enrichable_fields_by_name_for,
    enrichable_fields_for,
)
from app.modules.enrichment.domain.proposals import (
    EnrichmentProposal,
    FieldValue,
    ProposedFieldValue,
)
from app.modules.enrichment.domain.research_context import (
    CompanyContext,
    build_known_facts_block,
    build_research_query,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.utilities.domain.json_types import JsonObject

_CONFIDENCE_SCORE = {"high": 0.9, "medium": 0.6, "low": 0.3}

# A structured company-data provider's own database is at least as
# trustworthy as the LLM's own "high" narrative-confidence tier — it's a
# directly-typed field, not an inference over prose.
_STRUCTURED_PROVIDER_CONFIDENCE = 0.9


def _is_missing(value: FieldValue | None) -> bool:
    """A field counts as missing only when it's genuinely empty — a
    legitimately-zero number or an already-populated `False` must not be
    re-researched just because they're falsy in Python.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    if isinstance(value, dict):
        # Currency fields store `{"amount": ..., "currency": "USD"}` — a
        # legitimate zero amount (e.g. a pre-revenue seller) must not be
        # re-researched, same as the bare-number case below.
        return value.get("amount") is None
    return False


def _coerce_proposed_value(kind: str, raw_value: str) -> FieldValue:
    """The extraction schema only ever gives back a `str` (the LLM's own
    output shape); this converts it into what `write_payload.py`'s
    Attio/Postgres serializers for that `kind` actually expect —
    `serialize_date`/`to_postgres_money` etc. take a native `date`/`float`,
    never a bare string.
    """
    if kind == "currency" or kind == "number" or kind == "percent":
        return float(raw_value)
    if kind == "bool":
        return raw_value.strip().lower() in ("true", "yes", "1")
    if kind == "date":
        return date.fromisoformat(raw_value.strip())
    if kind == "multi_select_text":
        # The extraction schema's `value` is always one `str` per field —
        # never a real list — so a multi-value answer (e.g. `target_geography`)
        # comes back comma-separated; without this split, `normalize_prefill`'s
        # `isinstance(value, list)` check fails and the whole field is
        # silently dropped from the review form.
        return [v.strip() for v in raw_value.split(",") if v.strip()]
    return raw_value


def _constrain_to_options(field: EnrichableField, value: FieldValue) -> FieldValue | None:
    """A `select`/`multi_select_text` field's proposed value must already be
    one of its fixed options, or `normalize_prefill` drops it — silently,
    after the operator has already seen it in the Slack proposal message
    (`ddl_commands.api.slack.views.dynamic_fields.normalize_prefill`). The
    prompt (`_field_line`) asks the model to stick to the vocabulary, but
    this is the actual enforcement: matched case-insensitively (LLM casing
    is unreliable), never by synonym — "Saudi Arabia" is not silently
    rewritten to "KSA", it's dropped. For `multi_select_text`, a partial
    match keeps the surviving subset rather than dropping the whole field.
    Fields with no fixed vocabulary (`options == ()`) pass through
    unchanged, including `multi_select_as_text` (e.g. `hq_country`), which
    intentionally accepts free text.

    A shape that disagrees with `field.kind` (a `select` field somehow
    handed a list, say) is passed through unconstrained rather than
    raising — every caller's whole point in calling this is to drop one bad
    field without aborting the rest of the proposal, so this must never be
    the thing that aborts it; `normalize_prefill`'s own backstop is still
    there downstream if the unconstrained value turns out to be invalid.
    """
    if not field.options:
        return value
    canonical_by_casefold = {o.casefold(): o for o in field.options}
    if field.kind == "multi_select_text":
        if not isinstance(value, list):
            return value
        kept = [
            canonical_by_casefold[v.casefold()]
            for v in value
            if isinstance(v, str) and v.casefold() in canonical_by_casefold
        ]
        return kept or None
    if not isinstance(value, str):
        return value
    return canonical_by_casefold.get(value.casefold())


def _field_line(field: EnrichableField) -> str:
    """A field with no fixed vocabulary is free text — just its hint. One
    with `options` gets those exact labels folded in too, since the hint
    alone (e.g. "a fixed employee-count band") doesn't tell the model what
    the bands actually are, and an unmatched proposal is silently dropped
    before the operator ever sees the review form (`normalize_prefill`).
    """
    if not field.options:
        return f"- {field.name}: {field.prompt_hint}"
    allowed = " | ".join(field.options)
    multi = " Comma-separate if more than one applies." if field.kind == "multi_select_text" else ""
    return (
        f"- {field.name}: {field.prompt_hint} Choose ONLY from these exact labels: "
        f"{allowed}. Do not invent or paraphrase a label; omit the field entirely "
        f"if none of them apply.{multi}"
    )


def _build_prompt(
    org_name: str,
    missing: list[EnrichableField],
    sources: list[str],
    context: CompanyContext,
) -> str:
    field_lines = "\n".join(_field_line(f) for f in missing)
    source_lines = "\n\n".join(sources) if sources else "(no source material found)"
    known_facts_block = build_known_facts_block(context)
    return (
        f"You are researching the company '{org_name}' from public sources only.\n"
        f"{known_facts_block}"
        "Propose a value for each of the following fields, ONLY when the source "
        "material below actually supports it. Never invent a value. Skip any source "
        "that is clearly about a different company than the one described above. "
        "Cite the exact source URL you drew each value from.\n\n"
        f"Fields to fill:\n{field_lines}\n\n"
        f"Source material:\n{source_lines}"
    )


def _repair_prompt(raw: JsonObject, error: str) -> str:
    return (
        "Your previous response did not match the required schema.\n"
        f"Error: {error}\n"
        f"Previous response: {json.dumps(raw)}\n"
        "Return corrected, schema-valid JSON only."
    )


class EnrichMixin(ServiceBase):
    async def propose(self, target: EnrichmentTarget) -> EnrichmentProposal:
        current_values, context = await self._role_reader.load(target)
        missing = [
            field
            for field in enrichable_fields_for(target.kind.value)
            if _is_missing(current_values.get(field.name))
        ]

        proposed: list[ProposedFieldValue] = []
        proposed.extend(await self._structured_lookup(target, missing, current_values))
        resolved_names = {v.field_name for v in proposed}
        still_missing = [f for f in missing if f.name not in resolved_names]

        if not still_missing or self._research_client is None:
            return EnrichmentProposal(
                target=target, values=tuple(proposed), generated_by_model=self._model_id
            )

        proposed.extend(
            await self._research_and_extract(target, still_missing, current_values, context)
        )
        return EnrichmentProposal(
            target=target, values=tuple(proposed), generated_by_model=self._model_id
        )

    async def _structured_lookup(
        self,
        target: EnrichmentTarget,
        missing: list[EnrichableField],
        current_values: JsonObject,
    ) -> list[ProposedFieldValue]:
        """A company-data provider's schema is firmographic — revenue,
        employee count, HQ country, socials, years active, location count
        — a seller target's `missing` fields already are entirely that
        (`SELLER_ROLE`/`ORGANIZATION`, never anything else). A buyer
        target's `missing` can also include `BUYER_ROLE` fields (AUM,
        investment strategy, check sizes, deal structure tolerance, ...),
        which no such provider's schema tracks, so those are filtered out
        here first — leaving only the `ORGANIZATION` fields a buyer's
        organization shares the same row shape for as a seller's.
        """
        if target.kind is EnrichmentTargetKind.BUYER:
            missing = [f for f in missing if f.write_target is WriteTarget.ORGANIZATION]
        if not missing:
            return []

        proposed: list[ProposedFieldValue] = []
        remaining = list(missing)
        for client in self._company_data_clients:
            if not remaining:
                break
            fields = await client.lookup(org_name=target.org_name, fields=tuple(remaining))
            for field in fields:
                if field.field_name not in {f.name for f in remaining}:
                    continue
                enrichable = enrichable_fields_by_name_for(target.kind.value)[field.field_name]
                # Today's clients only ever emit `employee_range` among
                # option-bearing fields (via `bucket_employee_count`, always
                # a valid band) — but `sector_focus`/`estimated_arr` are
                # also option-bearing `ORGANIZATION` fields reachable
                # through this same path, so a future/other provider
                # returning one of those still gets constrained here rather
                # than silently vanishing between the proposal and the
                # review form the way the LLM path's values used to.
                constrained_value = _constrain_to_options(enrichable, field.value)
                if constrained_value is None:
                    continue
                proposed.append(
                    ProposedFieldValue(
                        field_name=field.field_name,
                        write_target=enrichable.write_target,
                        current=current_values.get(field.field_name),
                        proposed=constrained_value,
                        source_url=field.source_url,
                        confidence=_STRUCTURED_PROVIDER_CONFIDENCE,
                        rationale=f"Sourced from {field.provider}.",
                    )
                )
            resolved_now = {f.field_name for f in fields}
            remaining = [f for f in remaining if f.name not in resolved_now]
        return proposed

    async def _research_and_extract(
        self,
        target: EnrichmentTarget,
        missing: list[EnrichableField],
        current_values: JsonObject,
        context: CompanyContext,
    ) -> list[ProposedFieldValue]:
        # Only ever called from `propose` after it's already confirmed
        # `self._research_client is not None` — asserted here since that
        # narrowing doesn't carry across the method boundary.
        assert self._research_client is not None
        fields_by_name = enrichable_fields_by_name_for(target.kind.value)
        documents = await self._research_client.search(build_research_query(context), limit=5)
        sources = [f"[{doc.url}] {doc.title}\n{doc.content}" for doc in documents]

        raw = await self._extraction_client.extract_fields(
            model_id=self._model_id,
            prompt=_build_prompt(target.org_name, missing, sources, context),
            repair_prompt_builder=_repair_prompt,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

        proposed: list[ProposedFieldValue] = []
        for entry in raw.get("fields", []):
            field = fields_by_name.get(entry.get("field_name", ""))
            if field is None:
                continue
            confidence = _CONFIDENCE_SCORE.get(entry.get("confidence"), 0.0)
            if confidence < self._min_confidence:
                continue
            try:
                proposed_value = _coerce_proposed_value(field.kind, entry.get("value", ""))
            except ValueError:
                # LLM returned something that doesn't parse as this field's
                # kind (e.g. a non-numeric string for a currency field) —
                # drop it rather than propose a value that would fail at
                # write time with a much less clear error.
                continue
            constrained_value = _constrain_to_options(field, proposed_value)
            if constrained_value is None:
                # A `select`/`multi_select_text` field whose value(s) don't
                # match the fixed vocabulary — proposing it anyway would show
                # the operator a value the review form silently can't prefill.
                continue
            proposed_value = constrained_value
            proposed.append(
                ProposedFieldValue(
                    field_name=field.name,
                    write_target=field.write_target,
                    current=current_values.get(field.name),
                    proposed=proposed_value,
                    source_url=entry.get("source_url", ""),
                    confidence=confidence,
                    rationale=entry.get("rationale", ""),
                )
            )
        return proposed
