class AnnotationError(Exception):
    """Base exception for stanza_annotator."""


class InputValidationError(AnnotationError):
    """Prepared input contract was violated."""


class ConfigurationError(AnnotationError):
    """Configuration is invalid or unsupported."""


class StanzaRuntimeError(AnnotationError):
    """External Stanza runtime failed."""
