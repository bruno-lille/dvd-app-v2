# DVD APP V2 Migration Control Report

This template is completed only after a dry run. It records facts, transformations and exceptions; it is not an approval to execute migration.

## Source integrity

- Source path:
- SHA-256:
- SQLite integrity result:
- Total V1 rows: 1,518 expected
- Distinct and non-empty V1 disc IDs: 1,518 expected

## Reconciliation

| Check | Expected | Actual | Result |
|---|---:|---:|---|
| V1 rows with a migration trace | 1,518 | | |
| V1 rows with one MEDIA or an explicit exception | 1,518 | | |
| MEDIA inventory references | 1,518 or accepted-row count | | |
| ENTITY/MEDIA foreign-key violations | 0 | | |
| Classification attribution foreign-key violations | 0 | | |
| Location hierarchy violations | 0 | | |
| Unresolved blocking exceptions | 0 before production migration | | |

## Required exception sections

- Empty titles: 4 known source records.
- Malformed TMDB identifiers: 2 known source records.
- Same TMDB identifier with different titles: 16 known groups.
- Ambiguous or empty support values.
- Location values that may encode an acquisition or sale state.
- Legacy local paths stored in the Allociné field.

## Preservation checks

- Every source row retains its raw JSON snapshot in `migration_v1_film_map`.
- Every transformation has a rule code and note.
- No DOCUMENT is manufactured from a remote URL or a missing local file.
- `films.db` was opened read-only and its SHA-256 is unchanged after the dry run.

## Approval gate

Production migration remains blocked until every BLOCKING exception has a recorded human resolution and the reconciliation table passes.
