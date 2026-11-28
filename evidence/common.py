"""Small allowlisted evidence primitives. Never copy source envelopes."""
import datetime as dt
import hashlib
import json
import re

UTC = dt.timezone.utc
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IDENT = re.compile(r"[A-Za-z0-9_.:/+\[\]-]{1,120}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


def now():
    return dt.datetime.now(UTC).isoformat().replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except ValueError:
        return None


def seconds(start, end):
    a, b = timestamp(start), timestamp(end)
    if not a or not b:
        return None
    elapsed = (dt.datetime.fromisoformat(b.replace("Z", "+00:00")) - dt.datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds()
    return elapsed if elapsed >= 0 else None


def identifier(value, fallback="unknown"):
    return value if isinstance(value, str) and IDENT.fullmatch(value) else fallback


def integer(value):
    return value if type(value) is int and 0 <= value <= 10**15 else None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def github_url(repo, suffix=""):
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise ValueError("INVALID_REPOSITORY")
    return "https://github.com/" + repo + suffix
