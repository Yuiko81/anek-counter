from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

import asyncpg


@dataclass(slots=True)
class User:
    id: int
    username: str | None
    first_name: str
    joined_at: Any


class Database:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=10)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def get_or_create_user(self, telegram_id: int, username: str | None, first_name: str) -> User:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name
                RETURNING id, username, first_name, joined_at
                """,
                telegram_id,
                username,
                first_name,
            )
        return User(id=row["id"], username=row["username"], first_name=row["first_name"], joined_at=row["joined_at"])

    async def insert_event(self, user_id: int, type_code: str, spent_minutes: int, rating: int) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            type_row = await conn.fetchrow("SELECT id FROM types WHERE code = $1", type_code)
            if type_row is None:
                raise ValueError(f"Unknown type_code: {type_code}")
            await conn.execute(
                """
                INSERT INTO events (type_id, user_id, spent_minutes, rating)
                VALUES ($1, $2, $3, $4)
                """,
                type_row["id"],
                user_id,
                spent_minutes,
                rating,
            )

    async def personal_stats(self, user_id: int, period: str) -> Sequence[asyncpg.Record]:
        assert self._pool is not None
        since = self._period_to_since(period)
        params: list[Any] = [user_id]
        clause = ""
        if since is not None:
            clause = " AND e.happened_at >= $2"
            params.append(since)

        query = f"""
            SELECT t.code,
                   COUNT(*) AS total_events,
                   COALESCE(SUM(e.spent_minutes), 0) AS total_minutes,
                   ROUND(AVG(e.rating)::numeric, 2) AS avg_rating
            FROM events e
            JOIN types t ON t.id = e.type_id
            WHERE e.user_id = $1{clause}
            GROUP BY t.code
            ORDER BY t.code
        """
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *params)

    async def global_top(self, period: str, min_records: int = 5) -> dict[str, Sequence[asyncpg.Record]]:
        assert self._pool is not None
        since = self._period_to_since(period)
        params: list[Any] = []
        clause = ""
        if since is not None:
            clause = " AND e.happened_at >= $1"
            params.append(since)

        async with self._pool.acquire() as conn:
            results: dict[str, Sequence[asyncpg.Record]] = {}
            results["joke_count"] = await conn.fetch(
                f"""
                SELECT COALESCE(u.username, u.first_name) AS display_name,
                       COUNT(*) AS total
                FROM events e
                JOIN users u ON u.id = e.user_id
                JOIN types t ON t.id = e.type_id
                WHERE t.code = 'joke'{clause}
                GROUP BY u.id
                ORDER BY total DESC
                LIMIT 10
                """,
                *params,
            )
            results["story_count"] = await conn.fetch(
                f"""
                SELECT COALESCE(u.username, u.first_name) AS display_name,
                       COUNT(*) AS total
                FROM events e
                JOIN users u ON u.id = e.user_id
                JOIN types t ON t.id = e.type_id
                WHERE t.code = 'story'{clause}
                GROUP BY u.id
                ORDER BY total DESC
                LIMIT 10
                """,
                *params,
            )
            results["time"] = await conn.fetch(
                f"""
                SELECT COALESCE(u.username, u.first_name) AS display_name,
                       SUM(e.spent_minutes) AS total_minutes
                FROM events e
                JOIN users u ON u.id = e.user_id
                WHERE TRUE{clause}
                GROUP BY u.id
                ORDER BY total_minutes DESC
                LIMIT 10
                """,
                *params,
            )

            rating_clause = clause
            rating_params = params.copy()
            if since is not None:
                rating_clause = " AND e.happened_at >= $2"
                rating_params = [min_records, since]
            else:
                rating_clause = ""
                rating_params = [min_records]

            results["rating"] = await conn.fetch(
                f"""
                SELECT COALESCE(u.username, u.first_name) AS display_name,
                       ROUND(AVG(e.rating)::numeric, 2) AS avg_rating,
                       COUNT(*) AS cnt
                FROM events e
                JOIN users u ON u.id = e.user_id
                WHERE TRUE{rating_clause}
                GROUP BY u.id
                HAVING COUNT(*) >= $1
                ORDER BY avg_rating DESC
                LIMIT 10
                """,
                *rating_params,
            )
        return results

    async def weekly_personal_summary(self, user_id: int) -> Sequence[asyncpg.Record]:
        assert self._pool is not None
        since = datetime.now(timezone.utc) - timedelta(days=7)
        query = """
            SELECT t.code,
                   COUNT(*) AS total_events,
                   COALESCE(SUM(e.spent_minutes), 0) AS total_minutes
            FROM events e
            JOIN types t ON t.id = e.type_id
            WHERE e.user_id = $1 AND e.happened_at >= $2
            GROUP BY t.code
            ORDER BY t.code
        """
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, user_id, since)

    async def weekly_global_positions(self, user_id: int) -> dict[str, int | None]:
        assert self._pool is not None
        since = datetime.now(timezone.utc) - timedelta(days=7)
        async with self._pool.acquire() as conn:
            joke_rank = await conn.fetchrow(
                """
                SELECT rank
                FROM (
                    SELECT user_id,
                           ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rank
                    FROM events e
                    JOIN types t ON t.id = e.type_id
                    WHERE t.code = 'joke' AND e.happened_at >= $1
                    GROUP BY user_id
                ) ranked
                WHERE user_id = $2
                """,
                since,
                user_id,
            )
            story_rank = await conn.fetchrow(
                """
                SELECT rank
                FROM (
                    SELECT user_id,
                           ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rank
                    FROM events e
                    JOIN types t ON t.id = e.type_id
                    WHERE t.code = 'story' AND e.happened_at >= $1
                    GROUP BY user_id
                ) ranked
                WHERE user_id = $2
                """,
                since,
                user_id,
            )
            time_rank = await conn.fetchrow(
                """
                SELECT rank
                FROM (
                    SELECT user_id,
                           ROW_NUMBER() OVER (ORDER BY SUM(spent_minutes) DESC) AS rank
                    FROM events
                    WHERE happened_at >= $1
                    GROUP BY user_id
                ) ranked
                WHERE user_id = $2
                """,
                since,
                user_id,
            )
        return {
            "joke_rank": joke_rank["rank"] if joke_rank else None,
            "story_rank": story_rank["rank"] if story_rank else None,
            "time_rank": time_rank["rank"] if time_rank else None,
        }

    def _period_to_since(self, period: str) -> datetime | None:
        now = datetime.now(timezone.utc)
        period = period or "week"
        if period == "day":
            return now - timedelta(days=1)
        if period == "week":
            return now - timedelta(days=7)
        if period == "month":
            return now - timedelta(days=30)
        if period == "all":
            return None
        raise ValueError("Unsupported period")

