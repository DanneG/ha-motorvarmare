"""Bounded expansion of supported local calendar recurrence rules.

Occurrences retain their local wall-clock time across daylight saving changes.
The supported RFC 5545 subset is deliberately explicit; unsupported fields
must be rejected instead of silently scheduling the wrong heating time.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from homeassistant.util import dt as dt_util

_WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
_FREQUENCIES = {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}


def parse_rule(value: str) -> dict:
    """Validate the supported RRULE subset without expanding it."""
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("recurring_unsupported")
    fields = {}
    for part in value.upper().removeprefix("RRULE:").split(";"):
        if "=" not in part:
            raise ValueError("recurring_unsupported")
        key, val = part.split("=", 1)
        if key in fields or key not in {"FREQ", "INTERVAL", "BYDAY", "UNTIL"} or not val:
            raise ValueError("recurring_unsupported")
        fields[key] = val
    frequency = fields.get("FREQ")
    if frequency not in _FREQUENCIES:
        raise ValueError("recurring_unsupported")
    try:
        interval = int(fields.get("INTERVAL", "1"))
    except ValueError as exc:
        raise ValueError("recurring_unsupported") from exc
    if not 1 <= interval <= 365:
        raise ValueError("recurring_unsupported")
    days = fields.get("BYDAY", "").split(",") if "BYDAY" in fields else []
    if days and (frequency != "WEEKLY" or len(set(days)) != len(days) or any(d not in _WEEKDAYS for d in days)):
        raise ValueError("recurring_unsupported")
    until = fields.get("UNTIL")
    if until:
        try:
            if len(until) == 8:
                until = (datetime.strptime(until, "%Y%m%d").date(), True)
            else:
                until = (datetime.strptime(until, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc), False)
        except ValueError as exc:
            raise ValueError("recurring_unsupported") from exc
    return {"frequency": frequency, "interval": interval, "days": days, "until": until}


def _expand_rule(series: dict, start: datetime, end: datetime) -> list[dict]:
    """Expand occurrences in [start, end), skipping nonexistent local times."""
    if not (start.tzinfo and end.tzinfo) or end <= start:
        return []
    start, end = dt_util.as_utc(start), dt_util.as_utc(end)
    base = dt_util.as_local(series["departure"])
    rule = parse_rule(series["rrule"])
    zone = dt_util.get_default_time_zone()
    first = max(dt_util.as_local(start).date(), base.date())
    last = dt_util.as_local(end).date()
    if (last - first).days > 370:
        raise ValueError("recurring_unsupported")
    exceptions = set(series.get("exceptions", []))
    result = []
    day = first
    while day <= last:
        delta = (day - base.date()).days
        freq, interval = rule["frequency"], rule["interval"]
        if freq == "DAILY":
            match = delta >= 0 and delta % interval == 0
        elif freq == "WEEKLY":
            base_monday = base.date() - timedelta(days=base.weekday())
            week = (day - base_monday).days // 7
            selected = rule["days"] or [_WEEKDAYS[base.weekday()]]
            match = week >= 0 and week % interval == 0 and _WEEKDAYS[day.weekday()] in selected
        elif freq == "MONTHLY":
            months = (day.year - base.year) * 12 + day.month - base.month
            match = months >= 0 and months % interval == 0 and day.day == base.day
        else:
            years = day.year - base.year
            match = years >= 0 and years % interval == 0 and day.month == base.month and day.day == base.day
        if match:
            local = datetime.combine(day, base.timetz().replace(tzinfo=None), tzinfo=zone)
            occurrence = dt_util.as_utc(local)
            valid_local = dt_util.as_local(occurrence).replace(tzinfo=None) == local.replace(tzinfo=None)
            until = rule["until"]
            within_until = not until or ((day <= until[0]) if until[1] else (occurrence <= until[0]))
            if (valid_local and within_until and occurrence >= series["departure"] and start <= occurrence < end
                    and occurrence.isoformat() not in exceptions):
                result.append({"uid": series["uid"], "departure": occurrence,
                               "summary": series.get("summary") or "Avresa", "rrule": series["rrule"],
                               "recurrence_id": occurrence.isoformat(),
                               "series_start": series["departure"].isoformat(),
                               "series_summary": series.get("summary") or "Avresa",
                               "exceptions_count": len(exceptions)})
        day += timedelta(days=1)
    return result


def expand_series(series: dict, start: datetime, end: datetime) -> list[dict]:
    """Include moved instances even when their original date is outside the window."""
    result = _expand_rule(series, start, end)
    if not (start.tzinfo and end.tzinfo) or end <= start:
        return result
    for item in series.get("overrides", []):
        if start <= item["departure"] < end:
            result.append({"uid": series["uid"], "departure": item["departure"],
                           "summary": item.get("summary") or series.get("summary") or "Avresa",
                           "rrule": series["rrule"], "recurrence_id": item["recurrence_id"],
                           "series_start": series["departure"].isoformat(),
                           "series_summary": series.get("summary") or "Avresa",
                           "exceptions_count": len(series.get("exceptions", []))})
    return sorted(result, key=lambda item: item["departure"])


def _next_rule_occurrence(series: dict, start: datetime) -> dict | None:
    """Find the next instance by jumping directly between recurrence periods."""
    if not start.tzinfo:
        return None
    start = dt_util.as_utc(start)
    base = dt_util.as_local(series["departure"])
    rule = parse_rule(series["rrule"])
    target = max(dt_util.as_local(start).date(), base.date())
    zone = dt_util.get_default_time_zone()
    limit = min(10000, 400 + len(series.get("exceptions", [])))

    def occurrence_on(day):
        if day.year >= 9999:
            return None
        begin = dt_util.as_utc(datetime.combine(day, time.min, tzinfo=zone))
        finish = dt_util.as_utc(datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone))
        if finish <= start:
            return None
        found = _expand_rule(series, max(start, begin), finish)
        return found[0] if found else None

    def after_until(day):
        until = rule["until"]
        if not until:
            return False
        last_day = until[0] if until[1] else dt_util.as_local(until[0]).date()
        return day > last_day

    try:
        interval = rule["interval"]
        freq = rule["frequency"]
        if freq == "DAILY":
            delta = (target - base.date()).days
            index = max(0, (delta + interval - 1) // interval)
            for _ in range(limit):
                day = base.date() + timedelta(days=index * interval)
                if after_until(day):
                    return None
                if found := occurrence_on(day):
                    return found
                index += 1
        elif freq == "WEEKLY":
            monday = base.date() - timedelta(days=base.weekday())
            index = max(0, (target - monday).days // (7 * interval))
            weekdays = sorted(_WEEKDAYS.index(x) for x in (rule["days"] or [_WEEKDAYS[base.weekday()]]))
            for _ in range(limit):
                first = monday + timedelta(weeks=index * interval)
                for weekday in weekdays:
                    day = first + timedelta(days=weekday)
                    if after_until(day):
                        return None
                    if day >= target and (found := occurrence_on(day)):
                        return found
                index += 1
        elif freq == "MONTHLY":
            first_month = base.year * 12 + base.month - 1
            target_month = target.year * 12 + target.month - 1
            index = max(0, (target_month - first_month) // interval)
            for _ in range(limit):
                year, month = divmod(first_month + index * interval, 12)
                if year >= 9999:
                    return None
                try:
                    day = date(year, month + 1, base.day)
                except ValueError:
                    index += 1
                    continue
                if after_until(day):
                    return None
                if day >= target and (found := occurrence_on(day)):
                    return found
                index += 1
        else:
            index = max(0, (target.year - base.year) // interval)
            for _ in range(limit):
                year = base.year + index * interval
                if year >= 9999:
                    return None
                try:
                    day = date(year, base.month, base.day)
                except ValueError:
                    index += 1
                    continue
                if after_until(day):
                    return None
                if day >= target and (found := occurrence_on(day)):
                    return found
                index += 1
    except (OverflowError, ValueError):
        return None
    return None


def next_occurrence(series: dict, start: datetime) -> dict | None:
    """Find the next unmodified or moved instance."""
    regular = _next_rule_occurrence(series, start)
    if not start.tzinfo:
        return None
    moved = [item for item in series.get("overrides", []) if item["departure"] >= start]
    if not moved:
        return regular
    item = min(moved, key=lambda value: value["departure"])
    if regular and regular["departure"] <= item["departure"]:
        return regular
    return {"uid": series["uid"], "departure": item["departure"],
            "summary": item.get("summary") or series.get("summary") or "Avresa",
            "rrule": series["rrule"], "recurrence_id": item["recurrence_id"],
            "series_start": series["departure"].isoformat(),
            "series_summary": series.get("summary") or "Avresa",
            "exceptions_count": len(series.get("exceptions", []))}
