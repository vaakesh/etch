import math
from dataclasses import dataclass

PARAMETER_COUNT = 21

# Параметры FSRS-6 по умолчанию
# fmt: off
DEFAULT_PARAMETERS: tuple[float, ...] = (
    0.212, 1.2931, 2.3065, 8.2956,   # w0..w3: начальная S для Again/Hard/Good/Easy
    6.4133, 0.8334,                  # w4, w5: начальная D
    3.0194, 0.001,                   # w6: шаг изменения D, w7: возврат к среднему
    1.8722, 0.1666, 0.796,           # w8..w10: рост S при успешном ответе
    1.4835, 0.0614, 0.2629, 1.6483,  # w11..w14: S после забывания
    0.6014, 1.8729,                  # w15: штраф Hard, w16: бонус Easy
    0.5425, 0.0912, 0.0658,          # w17..w19: повторы в тот же день
    0.1542,                          # w20: форма кривой забывания (decay)
)
# fmt: on

STABILITY_MIN = 0.001
DIFFICULTY_MIN = 1.0
DIFFICULTY_MAX = 10.0


@dataclass(frozen=True, slots=True)
class FSRSParams:
    w: tuple[float, ...] = DEFAULT_PARAMETERS
    desired_retention: float = 0.9
    maximum_interval: int = 36500

    def __post_init__(self) -> None:
        # list -> tuple
        object.__setattr__(self, "w", tuple(float(x) for x in self.w))

        if len(self.w) != PARAMETER_COUNT:
            raise ValueError(f"expected {PARAMETER_COUNT} parameters, got {len(self.w)}")
        if not all(math.isfinite(x) for x in self.w):
            raise ValueError("parameters must be finite")
        if any(x <= 0 for x in self.w[:4]):
            raise ValueError("initial stabilities w0..w3 must be positive")
        if self.w[20] <= 0:
            raise ValueError("w20 must be positive")
        if not 0 < self.desired_retention < 1:
            raise ValueError("desired_retention must be in (0, 1)")
        if self.maximum_interval < 1:
            raise ValueError("maximum_interval must be >= 1")

    @property
    def decay(self) -> float:
        return -self.w[20]

    @property
    def factor(self) -> float:
        # R = (1 + factor * t / S) ^ decay
        # t = S -> R = (1 + factor) ^ decay = 0.9
        # factor = 0.9 ^ (1 / decay) - 1
        return 0.9 ** (1 / self.decay) - 1
