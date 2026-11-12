"""bbkos-zones: the time zones of the date popup's world clocks (docs/modules/calendar.md, "World clocks").

`bbkos-zones list` prints every real place (continent/city and UTC) as JSON for the zone picker; `bbkos-zones now ZONE...` prints
each zone's offset from UTC in minutes at this moment (daylight saving included), so the shell can show the time there without
a time zone library of its own. Names come from the system's tz database (zoneinfo) and are checked against it."""
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones

REGIONS = ("Africa", "America", "Antarctica", "Arctic", "Asia", "Atlantic", "Australia", "Europe", "Indian", "Pacific")
MAX_ZONES = 8


TAB = "/usr/share/zoneinfo/zone.tab"


def valid_names():
    """Every name that works: REGION/City (the legacy aliases such as Australia/ACT too, so a saved one is never dropped) and UTC."""
    return {n for n in available_timezones() if n == "UTC" or n.split("/", 1)[0] in REGIONS}


def all_names():
    """The places a person would pick: the canonical ones listed in the tz database's zone.tab (one per place, no aliases like
    Australia/ACT) and UTC. Without that file, every valid name."""
    valid = valid_names()
    try:
        with open(TAB, encoding="utf-8") as f:
            listed = {line.rstrip("\n").split("\t")[2] for line in f if line.strip() and not line.startswith("#")}
    except (OSError, IndexError):
        return sorted(valid)
    return sorted((listed & valid) | {"UTC"})


def city(name):
    return name.rsplit("/", 1)[-1].replace("_", " ")


def now(names, at=None):
    at = at or datetime.now(timezone.utc)
    out = []
    for n in names:
        off = at.astimezone(ZoneInfo(n)).utcoffset()
        out.append({"zone": n, "city": city(n), "offset": int(off.total_seconds() // 60)})
    return out


def main(argv):
    valid = valid_names()
    if argv == ["list"]:
        print(json.dumps([{"zone": n, "city": city(n), "region": n.split("/", 1)[0]} for n in all_names()]))
        return 0
    if len(argv) >= 1 and argv[0] == "now":
        names = argv[1:]
        if any(n not in valid for n in names):
            print("not a time zone name", file=sys.stderr)
            return 1
        print(json.dumps(now(names)))
        return 0
    print("usage: bbkos-zones list | now ZONE...", file=sys.stderr)
    return 2
