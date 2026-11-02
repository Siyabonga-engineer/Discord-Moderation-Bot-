CREATE TABLE guild_settings (
    guild_id             BIGINT PRIMARY KEY,
    enabled              BOOLEAN     NOT NULL DEFAULT TRUE,
    action               TEXT        NOT NULL DEFAULT 'kick'
                         CHECK (action IN ('warn', 'timeout', 'kick')),
    strike_limit         INT         NOT NULL DEFAULT 3
                         CHECK (strike_limit >= 1),
    strike_window_hours  INT         NOT NULL DEFAULT 24
                         CHECK (strike_window_hours >= 1),
    log_channel_id       BIGINT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE blocked_words (
    id         BIGSERIAL PRIMARY KEY,
    guild_id   BIGINT NOT NULL REFERENCES guild_settings(guild_id) ON DELETE CASCADE,
    word       TEXT   NOT NULL,
    added_by   BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (guild_id, word)
);

CREATE TABLE violations (
    id               BIGSERIAL PRIMARY KEY,
    guild_id         BIGINT NOT NULL REFERENCES guild_settings(guild_id) ON DELETE CASCADE,
    user_id          BIGINT NOT NULL,
    username_at_time TEXT,
    matched_word     TEXT   NOT NULL,
    message_id       BIGINT,
    action_taken     TEXT   NOT NULL
                     CHECK (action_taken IN ('none', 'warn', 'timeout', 'kick')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_violations_guild_user_time
    ON violations (guild_id, user_id, created_at DESC);

CREATE TABLE blocked_users (
    guild_id   BIGINT NOT NULL REFERENCES guild_settings(guild_id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL,
    reason     TEXT,
    added_by   BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, user_id)
);