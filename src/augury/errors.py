class ResolutionError(Exception):
    """Base error for the resolution engine."""

    error_code = "resolution_error"


class ValidationError(ResolutionError):
    """Raised when a task document is structurally invalid."""

    error_code = "validation_error"

    def __init__(self, message: str, *, issues: list[dict[str, str | None]] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


class ExecutionError(ResolutionError):
    """Raised when a step fails during execution."""

    error_code = "execution_error"


class TargetingRangeError(ExecutionError):
    """Raised when target or origin selection exceeds the declared range."""

    error_code = "target_out_of_range"


class StatePathError(ResolutionError):
    """Raised when a dotted state path cannot be read or written."""

    error_code = "state_path_error"


class DiceError(ResolutionError):
    """Raised when a dice specification is invalid."""

    error_code = "dice_error"
