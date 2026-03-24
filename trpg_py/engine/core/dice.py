from __future__ import annotations

import random
import re
from dataclasses import dataclass

from trpg_py.errors import DiceError


_DICE_SPEC_RE = re.compile(r"^(?P<count>[1-9]\d*)d(?P<sides>[1-9]\d*)$")


@dataclass(frozen=True, slots=True)
class DiceSpec:
    raw: str
    count: int
    sides: int


class DiceRoller:
    def roll(self, spec: str) -> list[int]:
        raise NotImplementedError


class RandomDiceRoller(DiceRoller):
    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def roll(self, spec: str) -> list[int]:
        parsed = parse_dice_spec(spec)
        return [self._random.randint(1, parsed.sides) for _ in range(parsed.count)]


class FixedDiceRoller(DiceRoller):
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def roll(self, spec: str) -> list[int]:
        parsed = parse_dice_spec(spec)
        needed = parsed.count
        if len(self._values) < needed:
            raise DiceError(
                f"Not enough fixed dice values for {spec!r}: need {needed}, have {len(self._values)}"
            )
        values = [self._values.pop(0) for _ in range(needed)]
        for value in values:
            if value < 1 or value > parsed.sides:
                raise DiceError(f"Fixed dice value {value} is invalid for {spec!r}")
        return values


def parse_dice_spec(spec: str) -> DiceSpec:
    match = _DICE_SPEC_RE.match(spec)
    if not match:
        raise DiceError(f"Invalid dice specification: {spec!r}")
    count = int(match.group("count"))
    sides = int(match.group("sides"))
    return DiceSpec(raw=spec, count=count, sides=sides)
