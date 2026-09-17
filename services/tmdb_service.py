"""Read-only TMDB movie search and hand-off to the V2 matching service."""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from services.tmdb_match_service import EntityMatchInput, RankedTmdbCandidate, TmdbCandidate, rank_candidates


_SEARCH_MOVIE_URL = "https://api.themoviedb.org/3/search/movie"
_MOVIE_DETAILS_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}"
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


class TmdbNotFoundError(TmdbHttpError):
    """Raised when the requested TMDB movie does not exist."""


class TmdbResponseError(TmdbServiceError):
    """Raised when a TMDB response cannot be interpreted safely."""


@dataclass(frozen=True, slots=True)
class TmdbCastMember:
    name: str
    character: str | None
    cast_order: int | None


@dataclass(frozen=True, slots=True)
class TmdbMovieDetails:
    tmdb_id: int | str
    title: str | None
    original_title: str | None
    release_date: str | None
    overview: str | None
    genres: tuple[str, ...]
    directors: tuple[str, ...]
    cast: tuple[TmdbCastMember, ...]


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
    payload = _request_json(_SEARCH_MOVIE_URL, parameters)
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


def get_movie_details(tmdb_id: int | str, *, cast_limit: int = _DEFAULT_LIMIT) -> TmdbMovieDetails:
    """Read localized movie details and TMDB credits without persisting anything."""
    clean_id = _tmdb_id(tmdb_id)
    if not 1 <= cast_limit <= _MAX_LIMIT:
        raise ValueError(f"cast_limit must be between 1 and {_MAX_LIMIT}.")
    payload = _request_json(
        _MOVIE_DETAILS_URL.format(tmdb_id=clean_id),
        {"api_key": _get_api_key(), "language": "fr-FR", "append_to_response": "credits"},
    )
    if payload.get("id") is None:
        raise TmdbResponseError("TMDB returned movie details without an identifier.")
    genres = tuple(
        genre["name"] for genre in payload.get("genres", [])
        if isinstance(genre, dict) and isinstance(genre.get("name"), str) and genre["name"]
    )
    credits = payload.get("credits") if isinstance(payload.get("credits"), dict) else {}
    directors = tuple(
        member["name"] for member in credits.get("crew", [])
        if isinstance(member, dict) and member.get("job") == "Director"
        and isinstance(member.get("name"), str) and member["name"]
    )
    cast = _cast_members(credits.get("cast"), cast_limit)
    return TmdbMovieDetails(
        tmdb_id=payload["id"],
        title=_text_or_none(payload.get("title")),
        original_title=_text_or_none(payload.get("original_title")),
        release_date=_text_or_none(payload.get("release_date")),
        overview=_text_or_none(payload.get("overview")),
        genres=genres,
        directors=directors,
        cast=cast,
    )


def _get_api_key() -> str:
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key or not api_key.strip():
        raise TmdbConfigurationError("TMDB_API_KEY is required to search TMDB.")
    return api_key.strip()


def _request_json(endpoint_url: str, parameters: dict[str, Any]) -> dict[str, Any]:
    request_url = f"{endpoint_url}?{urlencode(parameters)}"
    try:
        with urlopen(request_url, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:
            raw_payload = response.read()
    except HTTPError as exc:
        if exc.code == 404:
            raise TmdbNotFoundError("TMDB movie was not found.") from exc
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


def _tmdb_id(value: int | str) -> str:
    clean_value = str(value).strip()
    if not clean_value.isdigit() or int(clean_value) <= 0:
        raise ValueError("tmdb_id must be a positive identifier.")
    return clean_value


def _cast_members(raw_cast: object, limit: int) -> tuple[TmdbCastMember, ...]:
    if not isinstance(raw_cast, list):
        return ()
    indexed_members: list[tuple[int, int, TmdbCastMember]] = []
    for index, member in enumerate(raw_cast):
        if not isinstance(member, dict) or not isinstance(member.get("name"), str) or not member["name"]:
            continue
        order = member.get("order")
        cast_order = order if isinstance(order, int) else None
        indexed_members.append((cast_order if cast_order is not None else index, index, TmdbCastMember(member["name"], _text_or_none(member.get("character")), cast_order)))
    indexed_members.sort(key=lambda item: (item[0], item[1]))
    return tuple(item[2] for item in indexed_members[:limit])
