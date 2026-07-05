import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

RESET = "\x1b[0m"

COLORS = {
    logging.DEBUG: "\x1b[37m",      # white
    logging.INFO: "\x1b[32m",       # green
    logging.WARNING: "\x1b[33m",    # yellow
    logging.ERROR: "\x1b[31m",      # red
    logging.CRITICAL: "\x1b[1;31m", # bold red
}

class ColoredFormatter(logging.Formatter):
    RESET = RESET
    COLORS = COLORS

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)

        record.levelname = f"{color}{record.levelname}{self.RESET}"

        # перекрашивание сообщения
        # full_msg = record.getMessage()
        # colored_lines = f"\n".join(
        #     f"{color}{line}{self.RESET}" for line in full_msg.splitlines()
        # )
        # record.msg = colored_lines
        # record.args = None

        return super().format(record)


def setup_logging(sql_debug: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "sqlalchemy.engine", "sqlalchemy.pool"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    if sql_debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)