# FILE: errors.py - NEW (v2). Small shared exception types so modules do not import each other in circles.
class Unsupported(Exception):
    """The question is understood but FloatChat cannot answer it (forecast, other variable, no region ...)."""


class Blocked(Exception):
    """The input guardrail refused the text (empty, too long, looks like an instruction-override attempt)."""
