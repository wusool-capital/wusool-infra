"""Compose meetings application use cases behind one module facade.

`summarize.py`'s `SummarizationService` stays outside this facade — it's a
collaborator object `PublishMixin.summarize_and_publish` calls internally,
not a concern anything else in this module calls directly (see
`bootstrap.py` for how it's assembled and handed to `ServiceBase`).
"""

from app.modules.meetings.application.ingest import IngestMixin
from app.modules.meetings.application.publish import PublishMixin
from app.modules.meetings.application.status import StatusMixin


class MeetingsService(IngestMixin, StatusMixin, PublishMixin):
    """No business logic of its own — combines every concern mixin above
    into one composed class. Add a new use-case area as its own
    `ServiceBase` mixin and list it here, rather than growing this class or
    a mixin file directly.
    """
