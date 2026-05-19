from __future__ import annotations

from typing import Optional

from rich.color import Color, blend_rgb
from rich.color_triplet import ColorTriplet
from rich.progress import ProgressColumn, Task
from rich.progress_bar import ProgressBar
from rich.style import Style
from rich.table import Column
from rich.text import Text

_RED = ColorTriplet(215, 55, 55)
_YELLOW = ColorTriplet(255, 210, 55)
_GREEN = ColorTriplet(55, 195, 105)


def _style_for_progress_ratio(p: float) -> Style:
    """Map completion ratio in ``[0, 1]`` to red → yellow → green (两段线性插值)."""
    p = max(0.0, min(1.0, p))
    if p <= 0.5:
        rgb = blend_rgb(_RED, _YELLOW, cross_fade=p * 2.0)
    else:
        rgb = blend_rgb(_YELLOW, _GREEN, cross_fade=(p - 0.5) * 2.0)
    return Style(color=Color.from_triplet(rgb))


def _ratio_from_task(task: Task) -> float:
    if task.total is not None and task.total > 0:
        return min(1.0, max(0.0, float(task.completed) / float(task.total)))
    if task.finished:
        return 1.0
    return 0.0


class CompletedTotalColumn(ProgressColumn):
    """右对齐显示 ``completed/total`` 计数，替代百分比。"""

    def render(self, task: Task) -> Text:
        c = int(task.completed)
        if task.total is None:
            body = f"{c}/?"
        else:
            body = f"{c}/{int(task.total)}"
        return Text(body, style="grey70", justify="right")


class AdaptiveHueBarColumn(ProgressColumn):
    """条形填充色随 ``completed/total`` 在红—黄—绿之间过渡；不使用 Rich 启动脉冲段。"""

    def __init__(
        self,
        bar_width: Optional[int] = 28,
        *,
        track_style: str = "bar.back",
        table_column: Optional[Column] = None,
    ) -> None:
        self.bar_width = bar_width
        self.track_style = track_style
        super().__init__(table_column=table_column)

    def render(self, task: Task) -> ProgressBar:
        p = _ratio_from_task(task)
        hue = _style_for_progress_ratio(p)
        hue_done = _style_for_progress_ratio(1.0)
        return ProgressBar(
            total=max(0, task.total) if task.total is not None else None,
            completed=max(0, task.completed),
            width=None if self.bar_width is None else max(1, self.bar_width),
            pulse=False,
            animation_time=task.get_time(),
            style=self.track_style,
            complete_style=hue,
            finished_style=hue_done,
            pulse_style=hue,
        )
