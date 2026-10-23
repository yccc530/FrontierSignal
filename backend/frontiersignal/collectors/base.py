from dataclasses import dataclass, field
from typing import Protocol

from ..models import Source
from ..normalizer import RawItem


@dataclass
class Collection:
    items: list[RawItem]
    cursor: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    filtered: int = 0
    advance_on_partial: bool = False


class Collector(Protocol):
    async def collect(self, source: Source) -> Collection: ...
