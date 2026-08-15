"""Attio integration boundary.

Synchronization is not implemented in this phase — the existing PostgreSQL
database (`wusool_crm`) is the runtime source for matching.
`workflows/crm-sync/scripts/` owns the actual Attio<->PostgreSQL sync
out-of-process.
"""
