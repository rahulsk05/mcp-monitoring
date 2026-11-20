import logging


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the specified module."""
    return logging.getLogger(name)


def log_debug(logger: logging.Logger, message: str, *args: object) -> None:
    logger.debug(message, *args)


def log_info(logger: logging.Logger, message: str, *args: object) -> None:
    logger.info(message, *args)


def log_warning(logger: logging.Logger, message: str, *args: object) -> None:
    logger.warning(message, *args)


def log_error(logger: logging.Logger, message: str, *args: object) -> None:
    logger.error(message, *args)


def log_exception(logger: logging.Logger, message: str, *args: object) -> None:
    logger.exception(message, *args)