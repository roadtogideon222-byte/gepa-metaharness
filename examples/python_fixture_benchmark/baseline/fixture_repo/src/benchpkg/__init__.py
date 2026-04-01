def add(a: int, b: int) -> int:
    return a + b


def normalize_title(value: str) -> str:
    parts = value.split()
    return " ".join(part.capitalize() for part in parts)
