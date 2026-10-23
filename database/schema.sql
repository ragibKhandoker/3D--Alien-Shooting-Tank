-- PostgreSQL (Neon) schema.
-- The backend runs this automatically on startup, so you normally don't need to.
-- To run it by hand: Neon Console -> SQL Editor -> paste -> Run.
-- Safe to run again (uses "if not exists").

-- ---------- Users ----------
create table if not exists users (
    id            bigint generated always as identity primary key,
    username      text        not null unique check (char_length(username) between 3 and 32),
    email         text        not null unique,
    password_hash text        not null,
    created_at    timestamptz not null default now()
);

-- ---------- Scores ----------
create table if not exists scores (
    id               bigint generated always as identity primary key,
    user_id          bigint      references users (id) on delete cascade,
    player_name      text        not null check (char_length(player_name) between 1 and 32),
    score            integer     not null,
    duration_seconds integer     not null default 0,
    session_id       uuid,
    created_at       timestamptz not null default now()
);

-- Added later: game difficulty (existing rows become 'medium')
alter table scores add column if not exists difficulty text not null default 'medium'
    check (difficulty in ('easy', 'medium', 'hard'));

create index if not exists scores_score_idx on scores (score desc);
create index if not exists scores_user_idx  on scores (user_id);
