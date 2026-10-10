import base64
from datetime import UTC, datetime
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec

from altcha import Challenge, Payload, Solution, solve_challenge
import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.auth.errors import CaptchaError
from app.auth.service import CaptchaService

HMAC_KEY = "test-hmac-key"
# The service signs a real expiry, so the fixed "now" must stay in the future.
NOW = datetime(2099, 1, 1, 12, 0, tzinfo=UTC)
NOW_TIMESTAMP = 4070952000
HEX_16_BYTES = re.compile(r"[0-9a-f]{32}")
HEX_32_BYTES = re.compile(r"[0-9a-f]{64}")


@pytest.fixture
def settings():
    return SimpleNamespace(
        altcha_hmac_key=HMAC_KEY,
        altcha_cost=1,
        altcha_min_counter=3,
        altcha_max_counter=3,
    )


@pytest.fixture
def redis():
    redis = create_autospec(Redis, instance=True)
    redis.set = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def captcha_service(redis, settings, monkeypatch):
    monkeypatch.setattr("app.auth.service.utcnow", lambda: NOW)
    return CaptchaService(redis=redis, settings=settings)


@pytest.fixture
def challenge(captcha_service) -> Challenge:
    return Challenge.from_dict(captcha_service.create_challenge())


@pytest.fixture
def solution(challenge) -> Solution:
    return solve_challenge(challenge)


class TestCreateChallenge:
    def test_returns_signed_challenge_with_configured_parameters(
        self,
        captcha_service: CaptchaService,
    ):
        challenge = captcha_service.create_challenge()

        parameters = challenge["parameters"]
        assert HEX_16_BYTES.fullmatch(parameters.pop("nonce"))
        assert HEX_16_BYTES.fullmatch(parameters.pop("salt"))
        assert HEX_16_BYTES.fullmatch(parameters.pop("keyPrefix"))
        assert HEX_32_BYTES.fullmatch(challenge.pop("signature"))
        assert challenge == {
            "parameters": {
                "algorithm": "PBKDF2/SHA-256",
                "cost": 1,
                "keyLength": 32,
                "expiresAt": NOW_TIMESTAMP + 300,
            },
        }

    def test_creates_unique_challenges(
        self,
        captcha_service: CaptchaService,
    ):
        first = captcha_service.create_challenge()
        second = captcha_service.create_challenge()

        assert first["parameters"]["nonce"] != second["parameters"]["nonce"]
        assert first["signature"] != second["signature"]

    def test_requires_configured_counter_to_solve(
        self,
        solution: Solution,
    ):
        assert solution.counter == 3


class TestVerify:
    async def test_accepts_solved_challenge_and_marks_it_used(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        challenge: Challenge,
        solution: Solution,
    ):
        payload = Payload(challenge, solution).to_base64()

        result = await captcha_service.verify(payload)

        assert result is None
        redis.set.assert_awaited_once_with(
            f"altcha:used:{challenge.signature}",
            value=1,
            nx=True,
            ex=300,
        )

    async def test_rejects_already_used_challenge(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        challenge: Challenge,
        solution: Solution,
    ):
        payload = Payload(challenge, solution).to_base64()
        redis.set.return_value = None

        with pytest.raises(CaptchaError):
            await captcha_service.verify(payload)

    async def test_propagates_redis_error_when_replay_check_is_unavailable(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        challenge: Challenge,
        solution: Solution,
    ):
        payload = Payload(challenge, solution).to_base64()
        failure = RedisError("redis is down")
        redis.set.side_effect = failure

        with pytest.raises(RedisError) as error:
            await captcha_service.verify(payload)

        assert error.value is failure
        redis.set.assert_awaited_once()

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(None, id="missing"),
            pytest.param("", id="empty"),
            pytest.param("not-base64!", id="not_base64"),
            pytest.param(
                base64.b64encode(b"not json").decode(),
                id="not_json",
            ),
            pytest.param(
                base64.b64encode(b'{"challenge": {}}').decode(),
                id="incomplete",
            ),
        ],
    )
    async def test_rejects_malformed_payload(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        payload: str | None,
    ):
        with pytest.raises(CaptchaError):
            await captcha_service.verify(payload)

        redis.set.assert_not_awaited()

    async def test_rejects_wrong_solution(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        challenge: Challenge,
        solution: Solution,
    ):
        wrong_solution = Solution(counter=4, derived_key=solution.derived_key)
        payload = Payload(challenge, wrong_solution).to_base64()

        with pytest.raises(CaptchaError):
            await captcha_service.verify(payload)

        redis.set.assert_not_awaited()

    async def test_rejects_challenge_with_changed_parameters(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        challenge: Challenge,
        solution: Solution,
    ):
        challenge.parameters.expires_at = NOW_TIMESTAMP + 3600
        payload = Payload(challenge, solution).to_base64()

        with pytest.raises(CaptchaError):
            await captcha_service.verify(payload)

        redis.set.assert_not_awaited()

    async def test_rejects_challenge_signed_with_another_key(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        settings: SimpleNamespace,
        challenge: Challenge,
        solution: Solution,
    ):
        payload = Payload(challenge, solution).to_base64()
        settings.altcha_hmac_key = "another-hmac-key"

        with pytest.raises(CaptchaError):
            await captcha_service.verify(payload)

        redis.set.assert_not_awaited()

    async def test_rejects_expired_challenge(
        self,
        captcha_service: CaptchaService,
        redis: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # Issued in the past: the signed expiry is already behind the real clock.
        issued_at = datetime(2020, 1, 1, tzinfo=UTC)
        monkeypatch.setattr("app.auth.service.utcnow", lambda: issued_at)
        challenge = Challenge.from_dict(captcha_service.create_challenge())
        payload = Payload(challenge, solve_challenge(challenge)).to_base64()

        with pytest.raises(CaptchaError):
            await captcha_service.verify(payload)

        redis.set.assert_not_awaited()
