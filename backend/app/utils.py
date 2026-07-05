from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)

def format_duration(duration: float) -> str:
    if duration > 1.0:
        color = "\x1b[31m"
    elif duration > 0.3:
        color = "\x1b[33m"
    else:
        color = "\x1b[32m"
    reset = "\x1b[0m"
    return f"{color}{duration:.3f}s{reset}"