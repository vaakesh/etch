import pytest
from starlette.requests import Request

from app.auth.deps import get_client_info
from app.auth.schemas import ClientInfo


def make_request(
    *,
    client: tuple[str, int] | None = ("203.0.113.7", 51234),
    user_agent: str | None = "Mozilla/5.0",
) -> Request:
    headers = []
    if user_agent is not None:
        headers.append((b"user-agent", user_agent.encode("latin1")))

    return Request({"type": "http", "client": client, "headers": headers})


class TestGetClientInfo:
    async def test_returns_client_address_and_user_agent(self):
        request = make_request()

        result = await get_client_info(request)

        assert result == ClientInfo(ip="203.0.113.7", user_agent="Mozilla/5.0")

    async def test_returns_ipv6_address_unchanged(self):
        request = make_request(client=("2001:db8:85a3::8a2e:370:7334", 51234))

        result = await get_client_info(request)

        assert result == ClientInfo(
            ip="2001:db8:85a3::8a2e:370:7334", user_agent="Mozilla/5.0",
        )

    async def test_returns_none_ip_when_connection_has_no_client(self):
        request = make_request(client=None)

        result = await get_client_info(request)

        assert result == ClientInfo(ip=None, user_agent="Mozilla/5.0")

    @pytest.mark.parametrize(
        "user_agent",
        [
            pytest.param(None, id="missing"),
            pytest.param("", id="empty"),
        ],
    )
    async def test_returns_none_user_agent_when_header_is_absent(self, user_agent):
        request = make_request(user_agent=user_agent)

        result = await get_client_info(request)

        assert result == ClientInfo(ip="203.0.113.7", user_agent=None)

    @pytest.mark.parametrize(
        ("user_agent", "expected"),
        [
            pytest.param("a" * 512, "a" * 512, id="at_limit"),
            pytest.param("a" * 513, "a" * 512, id="above_limit"),
        ],
    )
    async def test_truncates_user_agent_to_512_characters(self, user_agent, expected):
        request = make_request(user_agent=user_agent)

        result = await get_client_info(request)

        assert result == ClientInfo(ip="203.0.113.7", user_agent=expected)

    async def test_truncates_client_address_to_column_size(self):
        request = make_request(client=("a" * 65, 51234))

        result = await get_client_info(request)

        assert result == ClientInfo(ip="a" * 64, user_agent="Mozilla/5.0")
