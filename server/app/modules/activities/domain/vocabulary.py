"""The closed vocabulary for `activities` rows.

`EventType` is `domain.verb`; the database enforces only that format
(`activities_event_type_format`), so adding an event type needs no migration.
`ActorType` and `SubjectType` are also closed in the database
(`activities_actor_type_check`, `activities_subject_type_check`), so a new value
there needs a migration; a unit test keeps the enums and the model's CHECKs in step.
"""

from enum import StrEnum


class SubjectType(StrEnum):
    ORGANIZATION = "Organization"
    PERSON = "Person"
    DEAL = "Deal"
    BUYER_ROLE = "BuyerRole"
    SELLER_ROLE = "SellerRole"
    NOTE = "Note"
    MEETING = "Meeting"


class EventType(StrEnum):
    CRM_RECORD_CREATED = "crm.record_created"
    CRM_RECORD_UPDATED = "crm.record_updated"
    CRM_RECORD_DELETED = "crm.record_deleted"
    DEAL_STAGE_CHANGED = "deal.stage_changed"
    SELLER_ADDED = "seller.added"
    SELLER_EDITED = "seller.edited"
    BUYER_ADDED = "buyer.added"
    BUYER_EDITED = "buyer.edited"
    MATCH_RUN_COMPLETED = "match.run_completed"
    MATCH_APPROVED = "match.approved"
    MATCH_REJECTED = "match.rejected"
    MEETING_PUBLISHED = "meeting.published"
    MEETING_DELETED = "meeting.deleted"
    LEAD_MAGNET_SUBMITTED = "lead_magnet.submitted"
    # Written only by the AZM-150 migration and the one-off backfill script.
    LEGACY_RECORD_SYNCED = "legacy.record_synced"
    LEGACY_INTERACTION = "legacy.interaction"


class ActorType(StrEnum):
    ATTIO_MEMBER = "attio_member"
    ATTIO_API_TOKEN = "attio_api_token"
    ATTIO_SYSTEM = "attio_system"
    SLACK_USER = "slack_user"
    SCRIBE_INSTALL = "scribe_install"
    WEBSITE_VISITOR = "website_visitor"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ActivitySource(StrEnum):
    ATTIO_WEBHOOK = "attio_webhook"
    SLACK = "slack"
    DISCOVERY = "discovery"
    MATCHING_ENGINE = "matching_engine"
    MEETINGS = "meetings"
    LEAD_MAGNET = "lead_magnet"
