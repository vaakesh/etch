from fastapi import Request

from app.redis.deps import RedisRateLimiterDeps
from app.redis.service import RateLimit, RateLimitIdentity, RateLimitPolicy
from app.auth.deps import CurrentUser
from app.tracing import traced

def limit(
    policy: RateLimitPolicy,
    by_identity: RateLimitIdentity,
):
    if by_identity == "user":
        async def user_dependency(
            user: CurrentUser,
            rate_limiter: RedisRateLimiterDeps,
        ):
            limiter = RateLimit(
                policy=policy,
                rate_limiter=rate_limiter,
                by_identity=by_identity,
                identity_key=user.id,
            )
            await limiter()

        return user_dependency

    if by_identity == "ip":
        async def ip_dependency(
            request: Request,
            rate_limiter: RedisRateLimiterDeps,
        ):
            host = (
                request.client.host
                if request.client and request.client.host
                else "unknown"
            ) 
            limiter = RateLimit(
                policy=policy,
                rate_limiter=rate_limiter,
                by_identity=by_identity,
                identity_key=host,
            )
            await limiter()

        return ip_dependency

    raise ValueError(f"{by_identity} identity not found")

PROFILE_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="profile",
    requests=60,
    window_seconds=60,
)
AUTH_LOGIN_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="auth:login",
    requests=20,
    window_seconds=10 * 60,
)
AUTH_CHALLENGE_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="auth:challenge",
    requests=30,
    window_seconds=10 * 60,
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
TRAINING_SESSION_ACTIVITY_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="training-sessions:activity",
    requests=20,
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

ASK_RATE_LIMIT_POLICY = RateLimitPolicy(
    route="ask",
    requests=5,
    window_seconds=60 * 60 * 24,
)


profile_rate_limit = limit(
    policy=PROFILE_RATE_LIMIT_POLICY,
    by_identity="user",
)

login_rate_limit = limit(AUTH_LOGIN_RATE_LIMIT_POLICY, by_identity="ip")
challenge_rate_limit = limit(AUTH_CHALLENGE_RATE_LIMIT_POLICY, by_identity="ip")
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
training_session_activity_rate_limit = limit(
    TRAINING_SESSION_ACTIVITY_RATE_LIMIT_POLICY,
    by_identity="user",
)

bff_rate_limit = limit(BFF_RATE_LIMIT_POLICY, by_identity="user")
start_practice_rate_limit = limit(
    START_PRACTICE_RATE_LIMIT_POLICY,
    by_identity="user",
)

ask_rate_limit = limit(
    ASK_RATE_LIMIT_POLICY,
    by_identity="user",
)