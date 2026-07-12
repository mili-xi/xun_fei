class ConfigurationError(ValueError):
    """Raised when local runtime configuration is invalid."""


class MissingConfigurationError(ConfigurationError):
    """Raised when a required runtime setting is absent."""


class UpstreamServiceError(RuntimeError):
    """Safe public error for third-party service failures."""

    def __init__(self, service, message, status_code=None, correlation_id=None):
        self.service = service
        self.status_code = status_code
        self.correlation_id = correlation_id
        parts = [message]
        if status_code is not None:
            parts.append(f"status={status_code}")
        if correlation_id:
            parts.append(f"correlation_id={correlation_id}")
        super().__init__("; ".join(parts))
