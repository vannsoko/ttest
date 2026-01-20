import logging
import sys

def setup_logger():
    logger = logging.Logger("instancer-plugin", logging.DEBUG)
    # Check if the logger already has handlers to prevent adding multiple handlers
    if not logger.hasHandlers():
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logger.level)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)
    return logger