from typing import Generic, Optional

from roleml.shared.types import T

__all__ = ['SegmentedList']


class SegmentedList(Generic[T]):

    def __init__(self, num_segments: int = 1):
        self.segments = tuple([] for _ in range(num_segments))

    def get_segment(self, idx: int) -> list[T]:
        return self.segments[idx]

    def iter(self, start: Optional[int] = None, end: Optional[int] = None, *, range: Optional[tuple[int, int]] = None):
        if start is None:
            start = range[0] if range is not None else 0
        if end is None:
            end = range[1] if range is not None else len(self.segments)
        sub_segments = self.segments[start:end]
        for segment in sub_segments:
            for item in segment:
                yield item

    def __getitem__(self, idx: int) -> list[T]:
        return self.segments[idx]

    def __str__(self) -> str:
        return str(self.segments)
