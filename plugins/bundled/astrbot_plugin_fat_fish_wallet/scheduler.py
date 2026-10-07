"""峰谷时段计算，不依赖 astrbot，可单独测试。

高峰时段默认：09:00-12:00、14:00-18:30（含开始，不含结束）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

DEFAULT_PEAK_PERIODS = "09:00-12:00,14:00-18:30"
DEFAULT_WEEKDAYS = "0,1,2,3,4,5,6"


@dataclass(frozen=True)
class Period:
    start: int  # 当天秒数，含
    end: int  # 当天秒数，不含

    def contains(self, t: int) -> bool:
        return self.start <= t < self.end


def _to_seconds(hhmm: str) -> int:
    h, m = hhmm.strip().split(":", 1)
    return int(h) * 3600 + int(m) * 60


def parse_periods(spec: str) -> list[Period]:
    """解析 '09:00-12:00,14:00-18:30'，非法段忽略。"""
    periods = []
    if not spec:
        return periods
    for part in spec.split(","):
        part = part.strip()
        if "-" not in part:
            continue
        try:
            start = _to_seconds(part.split("-", 1)[0])
            end = _to_seconds(part.split("-", 1)[1])
        except (ValueError, IndexError):
            continue
        if end > start:
            periods.append(Period(start, end))
    return periods


def parse_weekdays(spec: str) -> list[int]:
    """解析 '0,1,2,3,4,5,6'（0=周一…6=周日）；空列表表示每天。"""
    days = []
    if not spec:
        return days
    for part in spec.split(","):
        part = part.strip()
        if part.isdigit() and 0 <= int(part) <= 6:
            days.append(int(part))
    return days


def day_seconds(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second


def is_peak(dt: datetime, periods: list[Period], weekdays: list[int]) -> bool:
    if weekdays and dt.weekday() not in weekdays:
        return False
    t = day_seconds(dt)
    return any(p.contains(t) for p in periods)


def next_transition(
    now: datetime,
    periods: list[Period],
    weekdays: list[int],
) -> tuple[str, datetime]:
    """下一次切换：返回（切换后的时段, 切换时刻），9 天内没有则返回 30 天后。"""
    for day_offset in range(0, 10):
        base_date = now.date() + timedelta(days=day_offset)
        base = datetime(base_date.year, base_date.month, base_date.day, tzinfo=now.tzinfo)
        boundaries = [base]
        if not weekdays or base_date.weekday() in weekdays:
            for p in periods:
                boundaries.append(base + timedelta(seconds=p.start))
                boundaries.append(base + timedelta(seconds=p.end))
        for b in sorted(boundaries):
            if b <= now:
                continue
            before = b - timedelta(seconds=1)
            if is_peak(before, periods, weekdays) != is_peak(b, periods, weekdays):
                return ("peak" if is_peak(b, periods, weekdays) else "offpeak", b)
    return ("offpeak", now + timedelta(days=30))


def fmt_duration(seconds: float | int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours} 小时 {minutes} 分钟"
    if hours:
        return f"{hours} 小时"
    return f"{minutes} 分钟"


def fmt_periods_for_display(spec: str) -> str:
    periods = parse_periods(spec)
    if not periods:
        return "（未配置）"

    def _fmt(p: Period) -> str:
        sh, sm = divmod(p.start // 60, 60)
        eh, em = divmod(p.end // 60, 60)
        return f"{sh:02d}:{sm:02d}-{eh:02d}:{em:02d}"

    return " / ".join(_fmt(p) for p in periods)


def get_zoneinfo(tz_name: str | None) -> Optional[ZoneInfo]:
    if not tz_name or ZoneInfo is None:
        return None
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return None


def now_in(zone: Optional[ZoneInfo]) -> datetime:
    if zone is not None:
        return datetime.now(zone)
    return datetime.now().astimezone()
