class ApplicationError(Exception):
    """Base domain exception."""


class ClinicNotFoundError(ApplicationError):
    pass


class ModelNotReadyError(ApplicationError):
    pass


class DataValidationError(ApplicationError):
    pass


class AgentProviderError(ApplicationError):
    pass
