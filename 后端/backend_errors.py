class ConfigurationError(ValueError):
    """Raised when local runtime configuration is invalid."""


class MissingConfigurationError(ConfigurationError):
    """Raised when a required runtime setting is absent."""

