import pytest
from pydantic import ValidationError

from rag.config import PROJECT_DIR, Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_settings(cached_dependencies):
    pass


class TestSettings:
    def test_reads_and_types_values_from_dotenv(self):
        settings = Settings()

        assert settings.content_dir == PROJECT_DIR / "content/ru"
        assert str(settings.qdrant_url) == "http://rag-qdrant:6333/"
        assert str(settings.llm_url) == "https://api.openai.com/v1"
        assert settings.llm_model == "gpt-6-luna"
        assert settings.llm_timeout == 300.0
        assert settings.llm_reasoning_effort == "medium"
        assert settings.llm_api_key.get_secret_value() == "test-api-key"
        assert settings.qdrant_grpc_port == 6334
        assert settings.candidate_k == 20
        assert settings.top_k == 5

    def test_environment_overrides_dotenv_values(self, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "custom-model")
        monkeypatch.setenv("LLM_URL", "https://llm.example/v1")
        monkeypatch.setenv("LLM_API_KEY", "custom-key")
        monkeypatch.setenv("LLM_TIMEOUT", "30")
        monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
        monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:6335")
        monkeypatch.setenv("TOP_K", "3")

        settings = Settings()

        assert settings.llm_model == "custom-model"
        assert str(settings.llm_url) == "https://llm.example/v1"
        assert settings.llm_api_key.get_secret_value() == "custom-key"
        assert settings.llm_timeout == 30.0
        assert settings.llm_reasoning_effort == "low"
        assert str(settings.qdrant_url) == "http://127.0.0.1:6335/"
        assert settings.top_k == 3

    def test_requires_all_runtime_settings_when_no_dotenv_or_environment_exists(self, monkeypatch):
        monkeypatch.delenv("LLM_API_KEY")

        with pytest.raises(ValidationError) as exc:
            Settings(_env_file=None)

        errors = exc.value.errors()
        assert {error["loc"][0] for error in errors} == set(Settings.model_fields)
        assert {error["type"] for error in errors} == {"missing"}

    @pytest.mark.parametrize(
        ("name", "value", "field"),
        [
            ("QDRANT_URL", "not-a-url", "qdrant_url"),
            ("QDRANT_GRPC_PORT", "65536", "qdrant_grpc_port"),
            ("LLM_URL", "not-a-url", "llm_url"),
            ("LLM_MODEL", "", "llm_model"),
            ("LLM_API_KEY", "", "llm_api_key"),
            ("LLM_API_KEY", " \t", "llm_api_key"),
            ("QDRANT_TIMEOUT", "0", "qdrant_timeout"),
            ("LLM_TIMEOUT", "0", "llm_timeout"),
            ("LLM_TIMEOUT", "-1", "llm_timeout"),
            ("LLM_REASONING_EFFORT", "", "llm_reasoning_effort"),
            ("LLM_REASONING_EFFORT", "invalid", "llm_reasoning_effort"),
            ("LLM_REASONING_EFFORT", "minimal", "llm_reasoning_effort"),
            ("RERANKER_BATCH_SIZE", "0", "reranker_batch_size"),
            ("RERANKER_MAX_LENGTH", "0", "reranker_max_length"),
            ("CANDIDATE_K", "0", "candidate_k"),
            ("TOP_K", "0", "top_k"),
            ("INIT_TIMEOUT", "0", "init_timeout"),
        ],
    )
    def test_rejects_invalid_settings(self, monkeypatch, name, value, field):
        monkeypatch.setenv(name, value)

        with pytest.raises(ValidationError) as exc:
            Settings()

        assert exc.value.errors()[0]["loc"] == (field,)

    def test_rejects_candidate_pool_smaller_than_final_result_count(self, monkeypatch):
        monkeypatch.setenv("CANDIDATE_K", "4")

        with pytest.raises(ValidationError, match="candidate_k must be greater than or equal"):
            Settings()

    def test_hides_api_key_in_settings_representation_and_json(self):
        settings = Settings()

        assert "test-api-key" not in repr(settings)
        assert "test-api-key" not in settings.model_dump_json()

    def test_requires_api_key_when_dotenv_contains_empty_example(self, monkeypatch):
        monkeypatch.delenv("LLM_API_KEY")

        with pytest.raises(ValidationError, match="llm_api_key must not be empty"):
            Settings()

    def test_resolves_content_relative_to_project_from_another_working_directory(self, monkeypatch):
        monkeypatch.chdir(PROJECT_DIR.parent)

        settings = Settings()

        assert settings.content_dir == PROJECT_DIR / "content/ru"


class TestGetSettings:
    def test_reuses_settings_until_cache_is_cleared(self, monkeypatch):
        first = get_settings()
        monkeypatch.setenv("TOP_K", "2")

        assert get_settings() is first
        assert get_settings().top_k == 5
        get_settings.cache_clear()
        assert get_settings().top_k == 2
