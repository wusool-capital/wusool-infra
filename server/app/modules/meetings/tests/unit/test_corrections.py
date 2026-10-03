"""CorrectionService against a fake CorrectorLLM: chunking and the filtering
that protects the client from hallucinated or no-op suggestions."""

from app.modules.meetings.application.corrections import CorrectionService
from app.modules.meetings.domain.corrections import CorrectionSuggestion, TranscriptSegment


class _FakeLLM:
    def __init__(self, suggestions: list[CorrectionSuggestion]) -> None:
        self.suggestions = suggestions
        self.prompts: list[str] = []

    async def suggest_corrections(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> list[CorrectionSuggestion]:
        self.prompts.append(prompt)
        return self.suggestions


def _service(llm: _FakeLLM, *, max_chars: int = 1000) -> CorrectionService:
    return CorrectionService(llm, model_id="m", max_tokens=100, max_chars_per_batch=max_chars)


def _s(segment_id: str, original: str, suggested: str) -> CorrectionSuggestion:
    return CorrectionSuggestion(
        segment_id=segment_id, original=original, suggested=suggested, reason="r"
    )


async def test_keeps_valid_and_drops_invalid_suggestions() -> None:
    segments = [
        TranscriptSegment("a", "we met wusul capital"),
        TranscriptSegment("b", "fine as is"),
        TranscriptSegment("c", "hello wurld"),
    ]
    llm = _FakeLLM(
        [
            _s("a", "we met wusul capital", "we met Wusool Capital"),
            _s("zzz", "x", "y"),  # unknown id
            _s("b", "paraphrased original", "something else"),  # original mismatch
            _s("b", "fine as is", "fine as is"),  # no-op
            _s("c", "hello wurld", "  "),  # empty
        ]
    )

    result = await _service(llm).suggest(segments)

    assert [r.segment_id for r in result] == ["a"]
    assert result[0].suggested == "we met Wusool Capital"


async def test_splits_into_batches_by_char_budget() -> None:
    segments = [TranscriptSegment(str(i), "x" * 40) for i in range(5)]
    llm = _FakeLLM([])

    await _service(llm, max_chars=100).suggest(segments)

    assert len(llm.prompts) == 3  # 2 + 2 + 1 segments
    assert all("@@@TRANSCRIPT_START@@@" in p for p in llm.prompts)


async def test_suggestion_for_other_batch_is_dropped() -> None:
    segments = [TranscriptSegment("a", "x" * 60), TranscriptSegment("b", "y" * 60)]
    # Fake returns the same suggestion for every batch; only the batch owning "a" may keep it.
    llm = _FakeLLM([_s("a", "x" * 60, "z" * 60)])

    result = await _service(llm, max_chars=100).suggest(segments)

    assert len(result) == 1


async def test_empty_input_makes_no_llm_call() -> None:
    llm = _FakeLLM([])

    assert await _service(llm).suggest([]) == []
    assert llm.prompts == []
