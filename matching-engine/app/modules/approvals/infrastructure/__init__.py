"""Approval persistence adapters.

No model, no repository, no test: no backing table exists in the real
schema (no `approvals` table, no `matches.status` column either, since
there's no `matches` table). This is a documented consequence of the schema
gap covered in the Phase 2 plan and `PRD.md` §3.3, not an omission —
approval persistence is out of scope until a future migration adds a table.
"""
