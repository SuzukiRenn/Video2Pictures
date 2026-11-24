import re
from dataclasses import dataclass
from itertools import chain
from typing import Iterator


@dataclass(frozen=True)
class FramePlan:
    total: int
    count: int
    spans: tuple[range, ...] = ()

    def __iter__(self) -> Iterator[int]:
        if self.spans:
            return chain.from_iterable(self.spans)
        if self.count == self.total:
            return iter(range(1, self.total + 1))
        if self.count == 1:
            return iter((1,))
        steps = self.count - 1
        return (1 + (i * (self.total - 1) + steps // 2) // steps for i in range(self.count))


def _number(value: str, message: str) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(message)
    try:
        return int(value)
    except ValueError:
        raise ValueError(message) from None


def select_frames(total: int, mode: str, value: str = "") -> FramePlan:
    if total < 1:
        raise ValueError("源文件没有可导出的帧。")
    if mode == "all":
        return FramePlan(total, total)
    if mode == "uniform":
        message = f"抽取张数必须是 1 至 {total} 之间的整数。"
        count = _number(value.strip(), message)
        if not 1 <= count <= total:
            raise ValueError(message)
        return FramePlan(total, count)
    if mode != "ranges":
        raise ValueError("请选择帧选择方式。")

    message = "请输入帧号或范围，例如 1,3-5。"
    bounds = []
    for part in value.replace("，", ",").split(","):
        match = re.fullmatch(r"\s*([0-9]+)(?:\s*-\s*([0-9]+))?\s*", part)
        if match is None:
            raise ValueError(message)
        start = _number(match[1], message)
        end = _number(match[2], message) if match[2] is not None else start
        if not 1 <= start <= end <= total:
            raise ValueError(f"范围须按从小到大填写，帧号须在 1 至 {total} 之间。")
        bounds.append((start, end))

    merged: list[range] = []
    for start, end in sorted(bounds):
        if merged and start <= merged[-1].stop:
            previous = merged.pop()
            merged.append(range(previous.start, max(previous.stop, end + 1)))
        else:
            merged.append(range(start, end + 1))
    return FramePlan(total, sum(len(span) for span in merged), tuple(merged))
