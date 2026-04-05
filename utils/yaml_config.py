from pathlib import Path


def _parse_scalar(token: str) -> str:
    """간단한 YAML 스칼라 문자열 값을 안전하게 해석한다."""
    value = token.strip()
    if not value:
        raise ValueError("YAML scalar cannot be empty.")

    if value[0] in {'"', "'"}:
        if len(value) < 2 or value[-1] != value[0]:
            raise ValueError(f"Unterminated quoted scalar: {token}")
        return value[1:-1]

    return value


def load_string_mapping(path: Path, section: str) -> dict[str, str]:
    """지정 섹션의 문자열 매핑만 YAML에서 읽어온다."""
    current_section = None
    mapping: dict[str, str] = {}

    with path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.rstrip()
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if not line.startswith(" "):
                if ":" not in stripped:
                    raise ValueError(f"Invalid YAML entry at line {line_number}: {raw_line!r}")

                key, remainder = stripped.split(":", 1)
                if remainder.strip():
                    raise ValueError(
                        f"Top-level YAML entries must be sections only at line {line_number}: {raw_line!r}"
                    )
                current_section = key.strip()
                continue

            if current_section != section:
                continue

            if not line.startswith("  "):
                raise ValueError(
                    f"Expected two-space indentation for section '{section}' at line {line_number}: {raw_line!r}"
                )

            entry = line[2:]
            if ":" not in entry:
                raise ValueError(
                    f"Expected key/value pair in section '{section}' at line {line_number}: {raw_line!r}"
                )

            key, value = entry.split(":", 1)
            parsed_key = _parse_scalar(key)
            parsed_value = _parse_scalar(value)
            mapping[parsed_key] = parsed_value

    if not mapping:
        raise ValueError(f"Section '{section}' was not found or was empty in {path}.")

    return mapping
