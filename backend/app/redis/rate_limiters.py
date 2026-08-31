from app.redis.deps import limit
from app.redis.service import RateLimitPolicy

PROFILE_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="profile",
    requests=60,
    window_seconds=60,
)
AUTH_LOGIN_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="auth:login",
    requests=10,
    window_seconds=60,
)
AUTH_ACTIONS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="auth:actions",
    requests=60,
    window_seconds=60,
)
AUTH_SESSIONS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="auth:sessions",
    requests=60,
    window_seconds=60,
)
REGISTRATION_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="users:registration",
    requests=5,
    window_seconds=60 * 60,
)
PUBLIC_USERS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="users:public",
    requests=120,
    window_seconds=60,
)
USERS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="users:authenticated",
    requests=120,
    window_seconds=60,
)
PASSWORD_CHANGE_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="users:password-change",
    requests=10,
    window_seconds=60 * 60,
)
CARDS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="cards",
    requests=120,
    window_seconds=60,
)
PUBLIC_DECKS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="decks:public",
    requests=180,
    window_seconds=60,
)
DECKS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="decks:authenticated",
    requests=120,
    window_seconds=60,
)
DECK_IMPORT_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="decks:import",
    requests=20,
    window_seconds=60,
)
PUBLIC_TRAINING_SESSIONS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="training-sessions:public",
    requests=120,
    window_seconds=60,
)
TRAINING_SESSIONS_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="training-sessions:authenticated",
    requests=120,
    window_seconds=60,
)
SUBMIT_ANSWER_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="training-sessions:submit-answer",
    requests=300,
    window_seconds=60,
)
BFF_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="bff",
    requests=120,
    window_seconds=60,
)
START_PRACTICE_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="bff:start-practice",
    requests=20,
    window_seconds=60,
)


profile_rate_limit = limit(
    policy=PROFILE_RATE_LIMIT_POLICY,
    by_identity="user",
)

login_rate_limit = limit(AUTH_LOGIN_RATE_LIMIT_POLICY, by_identity="ip")
auth_actions_rate_limit = limit(AUTH_ACTIONS_RATE_LIMIT_POLICY, by_identity="ip")
auth_sessions_rate_limit = limit(AUTH_SESSIONS_RATE_LIMIT_POLICY, by_identity="user")

registration_rate_limit = limit(REGISTRATION_RATE_LIMIT_POLICY, by_identity="ip")
public_users_rate_limit = limit(PUBLIC_USERS_RATE_LIMIT_POLICY, by_identity="ip")
users_rate_limit = limit(USERS_RATE_LIMIT_POLICY, by_identity="user")
password_change_rate_limit = limit(
    PASSWORD_CHANGE_RATE_LIMIT_POLICY,
    by_identity="user",
)

cards_rate_limit = limit(CARDS_RATE_LIMIT_POLICY, by_identity="user")

public_decks_rate_limit = limit(PUBLIC_DECKS_RATE_LIMIT_POLICY, by_identity="ip")
decks_rate_limit = limit(DECKS_RATE_LIMIT_POLICY, by_identity="user")
deck_import_rate_limit = limit(DECK_IMPORT_RATE_LIMIT_POLICY, by_identity="user")

public_training_sessions_rate_limit = limit(
    PUBLIC_TRAINING_SESSIONS_RATE_LIMIT_POLICY,
    by_identity="ip",
)
training_sessions_rate_limit = limit(
    TRAINING_SESSIONS_RATE_LIMIT_POLICY,
    by_identity="user",
)
submit_answer_rate_limit = limit(
    SUBMIT_ANSWER_RATE_LIMIT_POLICY,
    by_identity="user",
)

bff_rate_limit = limit(BFF_RATE_LIMIT_POLICY, by_identity="user")
start_practice_rate_limit = limit(
    START_PRACTICE_RATE_LIMIT_POLICY,
    by_identity="user",
)
