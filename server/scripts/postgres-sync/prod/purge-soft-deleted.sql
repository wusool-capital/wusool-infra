-- Hard-delete the soft-deleted (`removed_at IS NOT NULL`) rows from the six
-- mirrored tables.
--
-- WHY THIS IS NOT JUST `DELETE ... WHERE removed_at IS NOT NULL`
--
-- `removed_at` is a tombstone, not corruption. It is stamped when a record
-- disappears from Attio and cleared again if it reappears, so a re-created
-- record comes back live instead of staying flagged. The soft delete was
-- deliberate -- see app/models/buyer_role.py:112-119:
--
--   "Soft rather than a hard DELETE for two reasons: match_results cascades
--    off this row and exists nowhere in Attio, and notes.buyer_role_id /
--    tool_runs.buyer_role_id declare no ON DELETE, so a hard delete raises a
--    foreign-key violation once either references it."
--
-- Both still apply:
--
--   1. CASCADE LOSSES THAT CANNOT BE RECOVERED. `match_results` is the
--      advisors' approval history and exists ONLY in Postgres -- re-running
--      the Attio resync will not bring it back. It cascades off both
--      `buyer_roles.id` and `organizations.attio_id`. Deleting one removed
--      organization can take buyer_intel, buyer_roles, match_results (x2
--      FKs), match_scores (x2) and investor_lender_role with it.
--
--   2. FK VIOLATIONS. `notes.buyer_role_id` and `tool_runs.buyer_role_id`
--      have no ON DELETE, so a delete ABORTS if either still points at the
--      row. STEP 2 below clears those first; both are nullable and neither
--      is read anywhere in server/ (write-only provenance).
--
-- RUN STEP 1 FIRST AND READ IT. If `match_results_lost` is not zero, that is
-- approval history being destroyed. Stop and decide deliberately.
--
-- Usage: open the RDS tunnel (see ../rds-tunnel-runbook.md), then run STEP 1,
-- read the output, and only then run STEP 2.


-- ===========================================================================
-- STEP 1 -- REPORT ONLY. Changes nothing. Read before going further.
-- ===========================================================================

\echo '--- soft-deleted rows per table ---'
SELECT 'organizations' AS tbl,
       count(*) FILTER (WHERE removed_at IS NULL)     AS live,
       count(*) FILTER (WHERE removed_at IS NOT NULL) AS soft_deleted FROM organizations
UNION ALL SELECT 'person',       count(*) FILTER (WHERE removed_at IS NULL), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM person
UNION ALL SELECT 'deals',        count(*) FILTER (WHERE removed_at IS NULL), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM deals
UNION ALL SELECT 'notes',        count(*) FILTER (WHERE removed_at IS NULL), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM notes
UNION ALL SELECT 'buyer_roles',  count(*) FILTER (WHERE removed_at IS NULL), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM buyer_roles
UNION ALL SELECT 'seller_roles', count(*) FILTER (WHERE removed_at IS NULL), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM seller_roles
ORDER BY 1;

\echo ''
\echo '--- IRRECOVERABLE: approval history that would cascade away ---'
SELECT
  (SELECT count(*) FROM match_results mr
     JOIN buyer_roles br ON br.id = mr.buyer_role_id
    WHERE br.removed_at IS NOT NULL)                       AS lost_via_buyer_role,
  (SELECT count(*) FROM match_results mr
     JOIN organizations o ON o.attio_id = mr.buyer_attio_id
    WHERE o.removed_at IS NOT NULL)                        AS lost_via_buyer_org,
  (SELECT count(*) FROM match_results mr
     JOIN organizations o ON o.attio_id = mr.seller_attio_id
    WHERE o.removed_at IS NOT NULL)                        AS lost_via_seller_org,
  (SELECT count(*) FROM match_results mr
     JOIN seller_roles sr ON sr.id = mr.seller_role_id
    WHERE sr.removed_at IS NOT NULL)                       AS lost_via_seller_role;

\echo ''
\echo '--- references that would ABORT the delete unless cleared (step 2 handles these) ---'
SELECT
  (SELECT count(*) FROM notes n
     JOIN buyer_roles br ON br.id = n.buyer_role_id
    WHERE br.removed_at IS NOT NULL)                       AS notes_blocking,
  (SELECT count(*) FROM tool_runs t
     JOIN buyer_roles br ON br.id = t.buyer_role_id
    WHERE br.removed_at IS NOT NULL)                       AS tool_runs_blocking;

\echo ''
\echo '--- how old are the tombstones? recent ones may just be Attio lag ---'
SELECT 'deals' AS tbl, min(removed_at) AS oldest, max(removed_at) AS newest FROM deals WHERE removed_at IS NOT NULL
UNION ALL SELECT 'organizations', min(removed_at), max(removed_at) FROM organizations WHERE removed_at IS NOT NULL
UNION ALL SELECT 'person',        min(removed_at), max(removed_at) FROM person        WHERE removed_at IS NOT NULL
UNION ALL SELECT 'buyer_roles',   min(removed_at), max(removed_at) FROM buyer_roles   WHERE removed_at IS NOT NULL
UNION ALL SELECT 'seller_roles',  min(removed_at), max(removed_at) FROM seller_roles  WHERE removed_at IS NOT NULL
UNION ALL SELECT 'notes',         min(removed_at), max(removed_at) FROM notes         WHERE removed_at IS NOT NULL;


-- ===========================================================================
-- STEP 2 -- THE DELETE. Run only after reading STEP 1.
--
-- Wrapped in a transaction that ends in ROLLBACK. Read the row counts it
-- prints, and only then change the last line to COMMIT and run it again.
-- ===========================================================================

BEGIN;

-- Clear the two nullable references that would otherwise abort the delete.
-- Neither is read anywhere in server/ -- both are write-only provenance.
UPDATE notes n SET buyer_role_id = NULL
  FROM buyer_roles br WHERE br.id = n.buyer_role_id AND br.removed_at IS NOT NULL;

UPDATE tool_runs t SET buyer_role_id = NULL
  FROM buyer_roles br WHERE br.id = t.buyer_role_id AND br.removed_at IS NOT NULL;

UPDATE tool_runs t SET seller_role_id = NULL
  FROM seller_roles sr WHERE sr.id = t.seller_role_id AND sr.removed_at IS NOT NULL;

-- Children before parents. organizations last: it cascades the widest.
DELETE FROM notes        WHERE removed_at IS NOT NULL;
DELETE FROM deals        WHERE removed_at IS NOT NULL;
DELETE FROM buyer_roles  WHERE removed_at IS NOT NULL;
DELETE FROM seller_roles WHERE removed_at IS NOT NULL;
DELETE FROM person       WHERE removed_at IS NOT NULL;
DELETE FROM organizations WHERE removed_at IS NOT NULL;

-- Confirm nothing soft-deleted survives, and that the live counts still
-- match Attio production: organizations 3439, person 4899, deals 82,
-- notes 397, buyer_roles 990, seller_roles 269.
SELECT 'organizations' AS tbl, count(*) AS live, count(*) FILTER (WHERE removed_at IS NOT NULL) AS leftover FROM organizations
UNION ALL SELECT 'person',       count(*), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM person
UNION ALL SELECT 'deals',        count(*), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM deals
UNION ALL SELECT 'notes',        count(*), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM notes
UNION ALL SELECT 'buyer_roles',  count(*), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM buyer_roles
UNION ALL SELECT 'seller_roles', count(*), count(*) FILTER (WHERE removed_at IS NOT NULL) FROM seller_roles
ORDER BY 1;

ROLLBACK;  -- <<< change to COMMIT once the counts above look right
