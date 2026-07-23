from __future__ import annotations

from dataclasses import dataclass


CHANNEL_LIMITS = {
    "facebook_instagram": 2200,
    "linkedin": 3000,
    "youtube": 5000,
    "gbp": 1500,
    "reddit": 40000,
}
REQUIRED_CHANNELS = frozenset(CHANNEL_LIMITS)


@dataclass(frozen=True)
class GenerationValidation:
    valid: bool
    errors: tuple[str, ...]


def validate_generated_output(output: object, prohibited_words: tuple[str, ...] = ()) -> GenerationValidation:
    if not isinstance(output, dict):
        return GenerationValidation(False, ("Output must be a JSON object.",))

    errors: list[str] = []
    missing = REQUIRED_CHANNELS.difference(output.keys())
    if missing:
        errors.append(f"Missing channels: {', '.join(sorted(missing))}.")

    lowered_prohibited = tuple(word.lower() for word in prohibited_words)
    for channel, limit in CHANNEL_LIMITS.items():
        value = output.get(channel)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{channel} must contain non-empty text.")
            continue
        if len(value) > limit:
            errors.append(f"{channel} exceeds the {limit} character limit.")
        if any(word and word in value.lower() for word in lowered_prohibited):
            errors.append(f"{channel} contains a prohibited term.")

    values = [str(output[channel]).strip() for channel in REQUIRED_CHANNELS if channel in output]
    if len(values) != len(set(values)):
        errors.append("At least two channels contain duplicated copy.")
    return GenerationValidation(not errors, tuple(errors))
