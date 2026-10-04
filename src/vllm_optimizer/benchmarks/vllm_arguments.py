"""Resolve benchmark CLI spellings without changing JSON field names."""

import json
import re
from collections.abc import Mapping

from vllm_optimizer.config.arguments import canonical_argument_name


def normalized_benchmark_arguments(run: Mapping[str, object]) -> dict[str, object]:
    raw = run.get("args", {})
    if not isinstance(raw, Mapping):
        raise ValueError("vLLM benchmark args must be an object")
    arguments: dict[str, object] = {}
    sources: dict[str, str] = {}
    dotted_body: dict[str, object] = {}
    for raw_name, value in raw.items():
        if not isinstance(raw_name, str):
            raise ValueError("vLLM argument names must be non-empty strings")
        name, inline, embedded = raw_name.partition("=")
        root, dotted, field = name.partition(".")
        name = canonical_argument_name(root) + dotted + field
        if inline:
            if value is False:
                continue
            if value is not True:
                raise ValueError("inline vLLM benchmark arguments must use a boolean true or false value")
            value = embedded
        if name in sources:
            raise ValueError(
                f"vLLM benchmark arguments contain duplicate aliases for '{name}': '{sources[name]}' and '{raw_name}'"
            )
        sources[name] = raw_name
        if name.startswith("extra-body."):
            if value is False and field.split(".")[0].rstrip("+") not in {"temperature", "n"}:
                continue
            if value is True:
                raise ValueError(f"vLLM benchmark '{name}' requires a field value")
            if isinstance(value, list):
                if not value:
                    continue
                if len(value) != 1:
                    raise ValueError(f"vLLM benchmark '{name}' requires one field value")
                value = value[0]
            if value is None or not isinstance(value, str | int | float):
                raise ValueError(f"vLLM benchmark '{name}' requires a scalar or JSON string field value")
            _add_field(dotted_body, field, str(value))
        else:
            arguments[name] = value
    if dotted_body:
        # vLLM appends the dotted object last, replacing a separately supplied JSON body.
        extra_body(arguments)
        arguments["extra-body"] = json.dumps(dotted_body)
    return arguments


def extra_body(args: Mapping[str, object]) -> Mapping[str, object]:
    if "extra-body" not in args:
        return {}
    try:
        value = args["extra-body"]
        body = json.loads(value) if isinstance(value, str) else None
    except (ValueError, TypeError) as error:
        raise ValueError("vLLM benchmark extra-body must be a JSON object string") from error
    if not isinstance(body, dict):
        raise ValueError("vLLM benchmark extra-body must be a JSON object string")
    return body


def _add_field(body: dict[str, object], name: str, value: str) -> None:
    decoded: object = value
    if name.endswith("+"):
        name, decoded = name[:-1], value.split(",")
    else:
        decoded = _field_value(value)
    keys = name.split(".")
    if any(not key for key in keys):
        raise ValueError("vLLM benchmark extra-body fields must have non-empty names")
    for key in reversed(keys):
        decoded = {key: decoded}
    assert isinstance(decoded, dict)
    _merge_fields(body, decoded, "extra-body")


def _field_value(value: str) -> object:
    try:
        return json.loads(value)
    except ValueError:
        pass
    # FlexibleArgumentParser also accepts integer suffixes in dotted JSON fields.
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([kKmMgGtT])", value)
    try:
        if match:
            number, suffix = match.groups()
            power = "kmgt".index(suffix.lower()) + 1
            if suffix.islower():
                return int(float(number) * 1000**power)
            return int(number) * 1024**power
        return int(value)
    except ValueError:
        return value
    except OverflowError as error:
        raise ValueError("vLLM benchmark extra-body integer is too large") from error


def _merge_fields(body: dict[str, object], update: dict[str, object], path: str) -> None:
    for key, value in update.items():
        previous = body.get(key)
        if key not in body:
            body[key] = value
        elif isinstance(previous, dict) and isinstance(value, dict):
            _merge_fields(previous, value, f"{path}.{key}")
        elif isinstance(previous, list) and isinstance(value, list):
            body[key] = previous + value
        else:
            raise ValueError(f"vLLM benchmark arguments contain duplicate aliases for '{path}.{key}'")
