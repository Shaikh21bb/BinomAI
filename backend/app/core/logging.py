import logging
import sys
import structlog

def setup_logging(is_production: bool = False):
    """
    Configures structured logging for the application.
    Uses structlog for JSON formatting in production, and pretty console logs in development.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO if is_production else logging.DEBUG,
    )

    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Intercept standard library logging
    for logger_name in ["uvicorn.access", "uvicorn.error", "fastapi"]:
        logger = logging.getLogger(logger_name)
        logger.handlers = [logging.StreamHandler(sys.stdout)]
        logger.propagate = False
