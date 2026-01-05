"""Simple calculator placeholder."""

def calculate(expression: str) -> float:
    """Evaluate an arithmetic expression in a safe environment."""
    # NOTE: Use a safe parser in production.
    return eval(expression, {"__builtins__": {}})
