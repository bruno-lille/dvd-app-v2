"""DVD APP V2 migration draft.

This draft is intentionally analysis-only by default. It opens films.db read-only,
does not call external services, and does not write collection.db unless a future
validated implementation explicitly adds an apply mode.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

def normalise(value: str | None) -> str:
    value = unicodedata.normalize('NFD', (value or '').strip().lower())
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn')

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def audit(source: Path) -> dict:
    connection = sqlite3.connect(f'file:{source.resolve()}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    rows = [dict(row) for row in connection.execute('SELECT * FROM films ORDER BY id')]
    connection.close()
    exceptions, outcomes = [], []
    by_tmdb_title = defaultdict(list)
    by_tmdb = defaultdict(set)
    for row in rows:
        tmdb = (row['tmdb_id'] or '').strip()
        title = (row['titre'] or '').strip()
        if not title:
            exceptions.append({'id': row['id'], 'code': 'EMPTY_TITLE', 'severity': 'BLOCKING'})
        if tmdb and not tmdb.isdigit():
            exceptions.append({'id': row['id'], 'code': 'MALFORMED_TMDB_ID', 'severity': 'WARNING', 'value': tmdb})
        if tmdb.isdigit():
            by_tmdb_title[(tmdb, normalise(title))].append(row['id'])
            by_tmdb[tmdb].add(normalise(title))
        outcomes.append({'v1_film_id': row['id'], 'disc_id': row['disc_id'], 'raw_record': row})
    for tmdb, titles in by_tmdb.items():
        if len(titles) > 1:
            exceptions.append({'tmdb_id': tmdb, 'code': 'TMDB_TITLE_CONFLICT', 'severity': 'BLOCKING', 'titles': sorted(titles)})
    return {
        'mode': 'DRY_RUN_ONLY', 'source': str(source), 'source_sha256': sha256(source),
        'source_rows': len(rows), 'distinct_disc_id': len({r['disc_id'] for r in rows}),
        'safe_entity_groups': len(by_tmdb_title), 'exceptions': exceptions, 'source_rows_trace': outcomes,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='films.db', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.source)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Dry-run report created: {args.report}")

if __name__ == '__main__':
    main()
