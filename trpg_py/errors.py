class ResolutionError(Exception):
    """Base error for the resolution engine."""


class ValidationError(ResolutionError):
    """Raised when a task document is structurally invalid."""


class ExecutionError(ResolutionError):
    """Raised when a step fails during execution."""


class StatePathError(ResolutionError):
    """Raised when a dotted state path cannot be read or written."""


class DiceError(ResolutionError):
    """Raised when a dice specification is invalid."""
