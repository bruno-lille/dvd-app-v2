"""Read-only TMDB movie search and hand-off to the V2 matching service."""

from __future__ import annotations

import os
import re
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from services.tmdb_match_service import EntityMatchInput, RankedTmdbCandidate, TmdbCandidate, rank_candidates


_SEARCH_MOVIE_URL = "https://api.themoviedb.org/3/search/movie"
_DEFAULT_TIMEOUT_SECONDS = 10
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 20


class TmdbServiceError(RuntimeError):
    """Base error for the read-only TMDB client."""


class TmdbConfigurationError(TmdbServiceError):
    """Raised when TMDB_API_KEY is not configured."""


class TmdbNetworkError(TmdbServiceError):
    """Raised for a network-level TMDB request failure."""


class TmdbHttpError(TmdbServiceError):
    """Raised when TMDB returns an unsuccessful HTTP response."""


class TmdbResponseError(TmdbServiceError):
    """Raised when a TMDB response cannot be interpreted safely."""


def search_movies(query: str, *, year: int | str | None = None, limit: int = _DEFAULT_LIMIT) -> tuple[TmdbCandidate, ...]:
    """Search TMDB movies and transform the first requested page into candidates."""
    if not isinstance(query, str) or not (clean_query := query.strip()):
        raise ValueError("A movie title query is required.")
    if not 1 <= limit <= _MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {_MAX_LIMIT}.")
    api_key = _get_api_key()
    parameters: dict[str, Any] = {
        "api_key": api_key,
        "query": clean_query,
        "language": "fr-FR",
        "include_adult": "false",
        "page": 1,
    }
    known_year = _year(year)
    if known_year is not None:
        parameters["year"] = known_year
    payload = _request_json(parameters)
    results = payload.get("results")
    if not isinstance(results, list):
        raise TmdbResponseError("TMDB returned an invalid search response.")
    candidates: list[TmdbCandidate] = []
    for result in results[:limit]:
        if not isinstance(result, dict) or result.get("id") is None:
            continue
        popularity = result.get("popularity")
        candidates.append(
            TmdbCandidate(
                tmdb_id=result["id"],
                title=_text_or_none(result.get("title")),
                original_title=_text_or_none(result.get("original_title")),
                release_date=_text_or_none(result.get("release_date")),
                result_type=_text_or_none(result.get("media_type") or result.get("result_type")),
                popularity=float(popularity) if isinstance(popularity, (int, float)) else None,
            )
        )
    return tuple(candidates)


def match_entity(entity: EntityMatchInput, *, limit: int = _DEFAULT_LIMIT) -> tuple[RankedTmdbCandidate, ...]:
    """Search TMDB and rank proposals; this function never writes an ENTITY."""
    return rank_candidates(entity, search_movies(entity.name, year=entity.year, limit=limit))


def _get_api_key() -> str:
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key or not api_key.strip():
        raise TmdbConfigurationError("TMDB_API_KEY is required to search TMDB.")
    return api_key.strip()


def _request_json(parameters: dict[str, Any]) -> dict[str, Any]:
    request_url = f"{_SEARCH_MOVIE_URL}?{urlencode(parameters)}"
    try:
        with urlopen(request_url, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:
            raw_payload = response.read()
    except HTTPError as exc:
        raise TmdbHttpError("TMDB returned an HTTP error.") from exc
    except URLError as exc:
        raise TmdbNetworkError("Unable to contact TMDB.") from exc
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TmdbResponseError("TMDB returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise TmdbResponseError("TMDB returned an invalid JSON object.")
    return payload


def _year(value: int | str | None) -> int | None:
    if isinstance(value, int) and 1000 <= value <= 9999:
        return value
    if isinstance(value, str):
        match = re.search(r"\b(\d{4})\b", value)
        return int(match.group(1)) if match else None
    return None


def _text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
