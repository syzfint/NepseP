import logging
import os
import re
import warnings

from urllib3.exceptions import InsecureRequestWarning


def _resolve_level(level_name: str, fallback: int) -> int:
    return getattr(logging, level_name.upper(), fallback)


class SensitiveDataFilter(logging.Filter):
    """Redacts known sensitive values from emitted log messages."""

    def __init__(self, secrets: list[str]):
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 4]

    @staticmethod
    def _mask_url_passwords(text: str) -> str:
        # Example: postgresql://user:password@host/db -> postgresql://user:***@host/db
        return re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s]+:)([^@/\s]+)@", r"\1***@", text)

    def _mask_text(self, text: str) -> str:
        masked = self._mask_url_passwords(text)
        for secret in self._secrets:
            masked = masked.replace(secret, "***")
        return masked

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Force message formatting once, mask it, then overwrite msg/args.
            rendered = record.getMessage()
            record.msg = self._mask_text(rendered)
            record.args = ()
        except Exception:
            # Never break logging due to masking logic.
            pass
        return True


def configure_logging() -> None:
    """Configure app logging once with sane defaults and quieter third-party logs."""
    root_level_name = os.getenv("LOG_LEVEL", "INFO")
    root_level = _resolve_level(root_level_name, logging.INFO)

    log_format = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s|%(levelname)s|%(name)s|%(message)s",
    )
    log_datefmt = os.getenv("LOG_DATEFMT", "%Y-%m-%d %H:%M:%S")

    logging.basicConfig(
        level=root_level,
        format=log_format,
        datefmt=log_datefmt,
        force=True,
    )

    sensitive_env_keys = [
        "DB_PASSWORD",
        "DB_USER",
        "DB_HOST",
        "DB_NAME",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_BUCKET_NAME",
        "AWS_S3_ENDPOINT",
        "RABBITMQ_USER",
        "RABBITMQ_PASSWORD",
        "RABBITMQ_HOST",
        "RABBITMQ_VHOST",
        "GEMINI_API_KEY",
        "GEMINI_API_KEY_2",
        "GEMINI_API_KEY_3",
        "TWITTER_BEARER_TOKEN",
    ]
    secret_values = [os.getenv(k, "") for k in sensitive_env_keys]
    sensitive_filter = SensitiveDataFilter(secret_values)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)

    # Keep noisy dependencies readable unless explicitly overridden.
    noisy_loggers = {
        "pika": "WARNING",
        "urllib3": "WARNING",
        "nepse_scraper": "WARNING",
        "google": "WARNING",
    }
    for logger_name, default_level_name in noisy_loggers.items():
        env_key = f"LOG_LEVEL_{logger_name.upper().replace('.', '_')}"
        level_name = os.getenv(env_key, default_level_name)
        logging.getLogger(logger_name).setLevel(
            _resolve_level(level_name, _resolve_level(default_level_name, logging.WARNING))
        )

    suppress_insecure_warning = os.getenv(
        "SUPPRESS_INSECURE_REQUEST_WARNING", "true"
    ).lower() in {"1", "true", "yes", "on"}
    if suppress_insecure_warning:
        warnings.filterwarnings("ignore", category=InsecureRequestWarning)
