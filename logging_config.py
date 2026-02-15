import logging
import sys
import structlog
from structlog.processors import JSONRenderer, add_log_level
from structlog.dev import ConsoleRenderer


shared_processors = [add_log_level]
renderer = ConsoleRenderer() if sys.stderr.isatty() else JSONRenderer(sort_keys=True)


def configure_logging():
    structlog.configure(processors=shared_processors + [renderer])

    stdlib_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            *shared_processors,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.ExtraAdder(["pathname", "lineno", "funcName"]),
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        keep_exc_info=True,
        keep_stack_info=True,
        # pass_foreign_args=True,
    )
    stdlib_handler = logging.StreamHandler()
    stdlib_handler.setFormatter(stdlib_formatter)

    # Make Uvicorn's logs go through structlog
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = [stdlib_handler]

    # Make anything else that uses `logging` go through structlog
    root_logger = logging.getLogger()
    root_logger.handlers = [stdlib_handler]
