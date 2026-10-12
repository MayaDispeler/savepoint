# Contract language

```yaml
id: claimdesk.adjust_amount          # ^[a-z0-9_]+\.[a-z0-9_]+$
app: claimdesk
title: Change a claim amount and add an adjustment note
fixture: seed_a
params: { claim_id: "CL-10427", new_amount: 1250.0 }
instruction: Open claim {claim_id}, change the amount to {new_amount:.2f} ...
invariants:                           # evaluated after every step that changed state
  - { id: amount_under_cap, sql: "SELECT count(*) FROM claims WHERE amount > 100000", expect: { equals: 0 } }
goal:                                 # evaluated when the agent reports done
  - { id: amount_set, sql: "SELECT amount FROM claims WHERE id = :claim_id", expect: { equals: 1250.0 } }
frame:
  unchanged: [claims, claim_notes, policies, payees, adjusters]
  allowed:
    - { table: claims, where: "id = :claim_id", columns: [amount] }
    - { table: claim_notes, insert: 1 }
screen:                               # at most 3, advisory unless required: true
  - { id: saved_banner, ask: "Does the page say Saved?", required: false }
```

Rules: every SQL is one read-only `SELECT`, run on a read-only connection with a 2 second timeout. `expect` has
exactly one operator from `equals not_equals gte lte between in matches empty not_empty row_count`. Every
`frame.allowed` table must appear in `frame.unchanged`. Invalid contracts fail with a code, a path and a message
(`ID_FORMAT`, `EXPECT_OPERATOR`, `SQL_NOT_READONLY`, `FRAME_TABLE_NOT_UNCHANGED`, `SCREEN_TOO_MANY`, `MISSING_GOAL`,
`PARAM_UNDEFINED`, `YAML_ERROR`, `UNKNOWN_TABLE`) and no run starts.

Frame check (A4): `diff(S0, now)` over the `unchanged` tables, minus the allowed changes. A changed row must match an
allowed rule's `where` and its `columns`; inserts and deletes are counted against `insert` and `delete` budgets.
Anything left is reported as `unexpected change claims[CL-10431].adjuster_id`.

Known limit: contracts check database state, not the agent's returned value. The lookup workflow therefore checks
that nothing changed.
