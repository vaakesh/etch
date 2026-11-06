import pytest

from app.fsrs.params import DEFAULT_PARAMETERS, FSRSParams


class TestFSRSParams:
    def test_uses_fsrs6_defaults(self):
        params = FSRSParams()

        assert params.w == DEFAULT_PARAMETERS
        assert params.desired_retention == 0.9
        assert params.maximum_interval == 36500

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"w": DEFAULT_PARAMETERS[:20]}, "expected 21 parameters, got 20"),
            ({"w": (*DEFAULT_PARAMETERS[:20], float("nan"))}, "must be finite"),
            ({"w": (0.0, *DEFAULT_PARAMETERS[1:])}, "w0..w3 must be positive"),
            ({"w": (*DEFAULT_PARAMETERS[:20], 0.0)}, "w20 must be positive"),
            ({"desired_retention": 0.0}, "desired_retention"),
            ({"desired_retention": 1.0}, "desired_retention"),
            ({"maximum_interval": 0}, "maximum_interval"),
        ],
    )
    def test_rejects_invalid_values(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            FSRSParams(**kwargs)
