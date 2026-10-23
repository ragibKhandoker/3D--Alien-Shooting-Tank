"""PostgreSQL (Neon) access for the users and scores tables."""
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import config

_pool: ConnectionPool | None = None

USER_PUBLIC_FIELDS = "id, username, email, created_at"


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError("Database is not configured. Fill DATABASE_URL in backend/.env")
        # check_connection: Neon closes idle connections, so test each one before use
        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            check=ConnectionPool.check_connection,
            open=True,
        )
    return _pool


def _clean(row: dict | None) -> dict | None:
    """Make rows JSON friendly (ISO dates, string uuids)."""
    if row is None:
        return None
    for key, value in row.items():
        if isinstance(value, datetime):
            row[key] = value.isoformat()
        elif key == "session_id" and value is not None:
            row[key] = str(value)
    return row


def _fetch_one(sql: str, params=()):
    with get_pool().connection() as conn:
        return _clean(conn.execute(sql, params).fetchone())


def _fetch_all(sql: str, params=()):
    with get_pool().connection() as conn:
        return [_clean(r) for r in conn.execute(sql, params).fetchall()]


def init_schema():
    """Create tables if they don't exist (runs database/schema.sql)."""
    with get_pool().connection() as conn:
        conn.execute(config.SCHEMA_FILE.read_text(encoding="utf-8"))


def check_connection() -> dict:
    """Small summary of the live database, used for the startup log."""
    with get_pool().connection() as conn:
        info = conn.execute(
            """select current_database() as database, current_user as "user",
                      split_part(version(), ' ', 2) as version,
                      (select count(*) from users)  as users,
                      (select count(*) from scores) as scores"""
        ).fetchone()
        info["host"] = conn.info.host
    return info


# ---------- Users ----------
def create_user(username: str, email: str, password_hash: str):
    return _fetch_one(
        f"insert into users (username, email, password_hash) values (%s, %s, %s) returning {USER_PUBLIC_FIELDS}",
        (username, email, password_hash),
    )


def find_user_for_login(username_or_email: str):
    """Returns the user row including password_hash, or None."""
    field = "email" if "@" in username_or_email else "username"
    return _fetch_one(f"select * from users where {field} = %s limit 1", (username_or_email,))


def user_exists(username: str, email: str) -> str | None:
    """Returns which field is already taken ('username' / 'email'), or None."""
    if _fetch_one("select 1 from users where username = %s", (username,)):
        return "username"
    if _fetch_one("select 1 from users where email = %s", (email,)):
        return "email"
    return None


def get_user(user_id: int):
    return _fetch_one(f"select {USER_PUBLIC_FIELDS} from users where id = %s", (user_id,))


# ---------- Scores ----------
def save_score(user_id: int, player_name: str, score: int, duration_seconds: int,
               session_id: str | None, difficulty: str):
    return _fetch_one(
        """insert into scores (user_id, player_name, score, duration_seconds, session_id, difficulty)
           values (%s, %s, %s, %s, %s, %s)
           returning id, player_name, score, duration_seconds, difficulty, created_at""",
        (user_id, player_name, score, duration_seconds, session_id, difficulty),
    )


def top_scores(limit: int = 10, difficulty: str | None = None):
    """Best scores overall, or only for one difficulty."""
    if difficulty:
        return _fetch_all(
            """select player_name, score, duration_seconds, difficulty, created_at from scores
               where difficulty = %s order by score desc limit %s""",
            (difficulty, limit),
        )
    return _fetch_all(
        "select player_name, score, duration_seconds, difficulty, created_at from scores order by score desc limit %s",
        (limit,),
    )


def user_stats(user_id: int):
    """Games played, best/average score and global rank (by personal best) for one user."""
    return _fetch_one(
        """with bests as (select user_id, max(score) as best from scores
                          where user_id is not null group by user_id),
                mine as (select count(*) as games, coalesce(max(score), 0) as best,
                                coalesce(round(avg(score)), 0)::int as average
                         from scores where user_id = %s)
           select mine.games, mine.best, mine.average,
                  case when mine.games = 0 then null
                       else (select count(*) from bests where best > mine.best) + 1 end as rank,
                  (select count(*) from bests) as players
           from mine""",
        (user_id,),
    )


def user_scores(user_id: int, limit: int = 10):
    return _fetch_all(
        """select score, duration_seconds, difficulty, created_at from scores
           where user_id = %s order by created_at desc limit %s""",
        (user_id, limit),
    )
