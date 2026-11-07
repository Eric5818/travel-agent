from __future__ import annotations


class ToolError(RuntimeError):
    """A tool failure with a machine-readable kind for the agent to relay."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


class ItineraryGenerationError(RuntimeError):
    """Raised when the LLM cannot produce a valid itinerary after one repair."""
