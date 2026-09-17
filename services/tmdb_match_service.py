"""Deterministic, read-only ranking of already retrieved TMDB candidates."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal


MatchLevel = Literal["CERTAIN", "VERY_HIGH", "HIGH", "MEDIUM", "LOW"]


@dataclass(frozen=True, slots=True)
class EntityMatchInput:
    """Known optional film information; absent values are treated as unknown."""

    name: str
    original_name: str | None = None
    year: int | str | None = None
    objective_reference_text: str | None = None
    description: str | None = None
    tmdb_id: int | str | None = None


@dataclass(frozen=True, slots=True)
class TmdbCandidate:
    """TMDB data already available to the caller; this service performs no I/O."""

    tmdb_id: int | str
    title: str | None = None
    original_title: str | None = None
    release_date: str | int | None = None
    result_type: str | None = None
    popularity: float | None = None


@dataclass(frozen=True, slots=True)
class MatchEvidence:
    exact_title: bool
    exact_original_title: bool
    year_matches: bool | None
    existing_tmdb_id_matches: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RankedTmdbCandidate:
    candidate: TmdbCandidate
    level: MatchLevel
    evidence: MatchEvidence


def rank_candidates(entity: EntityMatchInput, candidates: list[TmdbCandidate] | tuple[TmdbCandidate, ...]) -> tuple[RankedTmdbCandidate, ...]:
    """Rank compatible film candidates without selecting or persisting one.

    Results whose explicit type is incompatible with a film are omitted.  The
    internal score is used only for deterministic ordering and is not exposed.
    """

    if not isinstance(entity.name, str) or not entity.name.strip():
        raise ValueError("Entity name is required for TMDB matching.")
    ranked: list[tuple[int, RankedTmdbCandidate]] = []
    for candidate in candidates:
        if _explicitly_non_film(candidate.result_type):
            continue
        score, evidence = _score(entity, candidate)
        ranked.append((score, RankedTmdbCandidate(candidate, _level(score, evidence), evidence)))
    ranked.sort(
        key=lambda item: (
            -item[0],
            -int(item[1].evidence.exact_title),
            -int(item[1].evidence.year_matches is True),
            normalize_title(item[1].candidate.title or item[1].candidate.original_title or ""),
            str(item[1].candidate.tmdb_id),
        )
    )
    return tuple(item[1] for item in ranked)


def normalize_title(value: str | None) -> str:
    """Normalize presentation differences while retaining title words and numbers."""

    if not value:
        return ""
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _score(entity: EntityMatchInput, candidate: TmdbCandidate) -> tuple[int, MatchEvidence]:
    entity_title = normalize_title(entity.name)
    entity_original = normalize_title(entity.original_name)
    candidate_title = normalize_title(candidate.title)
    candidate_original = normalize_title(candidate.original_title)
    candidate_titles = tuple(title for title in (candidate_title, candidate_original) if title)
    exact_title = bool(entity_title and any(entity_title == title for title in candidate_titles))
    exact_original = bool(entity_original and any(entity_original == title for title in candidate_titles))
    id_match = entity.tmdb_id is not None and str(entity.tmdb_id) == str(candidate.tmdb_id)
    known_year, candidate_year = _year(entity.year), _year(candidate.release_date)
    year_matches = None if known_year is None or candidate_year is None else known_year == candidate_year

    score = 0
    reasons: list[str] = []
    if id_match:
        score += 1000
        reasons.append("identifiant TMDB existant identique")
    if exact_title:
        score += 100
        reasons.append("titre identique")
    if exact_original:
        score += 85
        reasons.append("titre original identique")
    if not exact_title and not exact_original:
        closeness = max((_title_closeness(entity_title, title) for title in candidate_titles), default=0)
        score += closeness
        if closeness >= 35:
            reasons.append("titre proche mais différent")
        elif closeness > 0:
            reasons.append("similarité partielle de titre")
    if year_matches is True:
        score += 30
        reasons.append("année identique")
    elif year_matches is False:
        score -= min(30, 8 + abs(known_year - candidate_year) * 2)
        reasons.append("année différente")
    return score, MatchEvidence(exact_title, exact_original, year_matches, id_match, tuple(reasons))


def _title_closeness(left: str, right: str) -> int:
    if not left or not right:
        return 0
    if left in right or right in left:
        return 35 if left != right else 0
    left_words, right_words = set(left.split()), set(right.split())
    if not left_words or not right_words:
        return 0
    return int(30 * len(left_words & right_words) / len(left_words | right_words))


def _year(value: int | str | None) -> int | None:
    if isinstance(value, int) and 1000 <= value <= 9999:
        return value
    if isinstance(value, str):
        match = re.search(r"\b(\d{4})\b", value)
        return int(match.group(1)) if match else None
    return None


def _explicitly_non_film(result_type: str | None) -> bool:
    return result_type is not None and result_type.casefold() not in {"movie", "film"}


def _level(score: int, evidence: MatchEvidence) -> MatchLevel:
    if evidence.existing_tmdb_id_matches:
        return "CERTAIN"
    if score >= 120:
        return "VERY_HIGH"
    if score >= 75:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"
