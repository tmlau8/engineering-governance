"""Allowlisted Codex structured-event adapter; not a stable billing/audit API."""
import collections
import datetime as dt
import json
from pathlib import Path
import re
from common import UTC, fingerprint, identifier, integer, seconds, timestamp

MAX_LINE = 8 * 1024 * 1024
MAX_FILE = 256 * 1024 * 1024
MAX_FILES = 2000
MAX_SCAN_BYTES = 512 * 1024 * 1024
MAX_EVENTS = 50000
FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")
UUID = re.compile(r"[0-9a-f-]{36}\Z")


def safe_file(path, root):
    root = Path(root).resolve()
    path = Path(path)
    if not path.resolve().is_relative_to(root) or not path.is_file() or path.stat().st_size > MAX_FILE:
        return False
    return not any(p.is_symlink() for p in [path, *path.parents] if p != root.parent and p.is_relative_to(root))


def lines(path):
    with Path(path).open() as handle:
        while True:
            line = handle.readline(MAX_LINE + 1)
            if not line:
                return
            if len(line) > MAX_LINE:
                while line and not line.endswith("\n"):
                    line = handle.readline(MAX_LINE + 1)
                yield None
                continue
            try:
                value = json.loads(line)
                yield value if isinstance(value, dict) else None
            except ValueError:
                yield None


def repository(cwd, scopes):
    if not isinstance(cwd, str):
        return None
    value = Path(cwd).resolve()
    # Longest scope first; broad parent directories do not match child scopes.
    for scope in sorted(scopes, key=lambda x: len(x["cwd"]), reverse=True):
        if value.is_relative_to(Path(scope["cwd"]).resolve()):
            return scope["repository"]
    return None


def interval_union(intervals):
    ordered = sorted((a, b) for a, b in intervals if b >= a)
    total = 0.0
    if not ordered:
        return 0.0
    start, end = ordered[0]
    for a, b in ordered[1:]:
        if a <= end:
            end = max(end, b)
        else:
            total += end - start
            start, end = a, b
    return total + end - start


def agent_source(source):
    subagent = source.get("subagent") if isinstance(source, dict) else None
    subagent = subagent if isinstance(subagent, dict) else {}
    spawn = subagent.get("thread_spawn")
    return subagent, spawn if isinstance(spawn, dict) else {}


def normalise(records, meta, repo, invalid_records=0):
    unique = {}
    models, snapshots, starts, ends = set(), [], {}, {}
    event_times, intervals, reported = [], [], []
    aborts = 0
    invalid_usage = 0
    for r in records:
        when = timestamp(r.get("timestamp"))
        if not when:
            continue
        kind, q = r.get("type"), r.get("payload")
        if not isinstance(q, dict):
            continue
        if kind == "turn_context":
            model = identifier(q.get("model"))
            if model != "unknown":
                models.add(model)
            continue
        if kind != "event_msg" or q.get("type") not in ("token_count", "task_started", "task_complete", "turn_aborted"):
            continue
        subtype = q["type"]
        if subtype == "token_count":
            raw = (q.get("info") or {}).get("total_token_usage") if isinstance(q.get("info"), dict) else None
            usage = {k: integer(raw.get(k)) for k in FIELDS} if isinstance(raw, dict) else None
            selected = {"at": when, "type": subtype, "usage": usage}
        else:
            selected = {"at": when, "type": subtype, "turn": identifier(q.get("turn_id")), "start": timestamp(q.get("started_at")), "end": timestamp(q.get("completed_at")), "duration_ms": integer(q.get("duration_ms"))}
        unique[fingerprint(selected)] = selected
    for selected in sorted(unique.values(), key=lambda x: x["at"]):
        when, subtype = selected["at"], selected["type"]
        event_times.append(when)
        if subtype == "token_count":
            usage = selected["usage"]
            if not usage or any(usage[k] is None for k in FIELDS):
                invalid_usage += 1
                continue
            if usage["cached_input_tokens"] > usage["input_tokens"] or usage["reasoning_output_tokens"] > usage["output_tokens"] or usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
                invalid_usage += 1
                continue
            snapshots.append(usage)
        elif selected["turn"] != "unknown":
            turn = selected["turn"]
            if subtype == "task_started":
                starts.setdefault(turn, selected["start"] or when)
            else:
                ends[turn] = selected
    for turn, end in ends.items():
        start = end["start"] or starts.get(turn)
        stop = end["end"] or end["at"]
        if start and stop >= start:
            a = dt.datetime.fromisoformat(start.replace("Z", "+00:00")).timestamp()
            b = dt.datetime.fromisoformat(stop.replace("Z", "+00:00")).timestamp()
            intervals.append((a, b))
        if end["duration_ms"] is not None:
            reported.append(end["duration_ms"] / 1000)
        aborts += end["type"] == "turn_aborted"
    resets = sum(any(b[k] < a[k] for k in FIELDS) for a, b in zip(snapshots, snapshots[1:]))
    # A peak is only a lower bound if reset/fork semantics are unresolved.
    usage = max(snapshots, key=lambda x: x["total_tokens"]) if snapshots else {k: None for k in FIELDS}
    fork = identifier(meta.get("forked_from_id"), "")
    quality = "reported_cumulative" if snapshots else "unavailable"
    if resets or invalid_usage or invalid_records or fork:
        quality = "partial_lower_bound" if snapshots else "unavailable"
    source = meta.get("source")
    subagent, spawn = agent_source(source)
    parent = identifier(spawn.get("parent_thread_id"), "")
    role = identifier(spawn.get("agent_role") or spawn.get("agent_path"), "").rsplit("/", 1)[-1]
    if not role:
        role = "approval-reviewer" if subagent.get("other") == "guardian" else "main"
    return {
        "session": meta["id"], "repository": repo, "pr": None,
        "association": "configured_workspace_scope", "pr_association": "unlinked",
        "tool": "codex", "agent_role": role, "model": next(iter(models)) if len(models) == 1 else "mixed" if models else "unknown",
        "client_version": identifier(meta.get("cli_version")), "parent_session": parent or None,
        "fork_parent": fork or None, "usage_source": "local_structured_events_experimental",
        **usage, "uncached_input_tokens": usage["input_tokens"] - usage["cached_input_tokens"] if usage["input_tokens"] is not None else None,
        "usage_quality": quality, "included_in_exact_rollup": quality == "reported_cumulative",
        "reset_count": resets, "invalid_usage_records": invalid_usage,
        "invalid_records": invalid_records, "started_at": timestamp(meta.get("timestamp")),
        "last_event_at": max(event_times) if event_times else None,
        "session_elapsed_seconds": seconds(meta.get("timestamp"), max(event_times)) if event_times else None,
        "reported_turn_seconds": sum(reported) if reported else None,
        "observed_turn_seconds": sum(b-a for a,b in intervals) if intervals else None,
        "turn_interval_union_seconds": interval_union(intervals) if intervals else None,
        "completed_turns": len(ends) - aborts, "aborted_turns": aborts,
        "open_turns": len(set(starts) - set(ends)), "duration_kind": "turn_elapsed_including_tools_and_waiting_not_compute",
        "billing_cost": None,
    }


def collect(root, scopes, days=30):
    if Path(root).is_symlink():
        raise ValueError("UNSAFE_SOURCE_ROOT")
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("SOURCE_ROOT_UNAVAILABLE")
    grouped = {}
    cutoff = dt.datetime.now(UTC) - dt.timedelta(days=days)
    files_seen = scanned_bytes = selected_events = 0
    for path in root.rglob("*.jsonl"):
        files_seen += 1
        if files_seen > MAX_FILES:
            raise ValueError("USAGE_FILE_LIMIT")
        if not safe_file(path, root):
            raise ValueError("USAGE_DISCOVERY_INCOMPLETE")
        stat = path.stat()
        # A resumed session updates its file; only demonstrably old files skip parsing.
        if stat.st_mtime < cutoff.timestamp():
            continue
        scanned_bytes += stat.st_size
        if scanned_bytes > MAX_SCAN_BYTES:
            raise ValueError("USAGE_SCAN_LIMIT")
        iterator = lines(path)
        first = next(iterator, None)
        meta = first.get("payload") if isinstance(first, dict) and first.get("type") == "session_meta" else None
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str) or not UUID.fullmatch(meta["id"]):
            raise ValueError("USAGE_HEADER_INVALID")
        repo = repository(meta.get("cwd"), scopes)
        if repo is None:
            continue
        source = meta.get("source")
        subagent, spawn = agent_source(source)
        selected_meta = {k: meta.get(k) for k in ("id", "timestamp", "cli_version", "forked_from_id")}
        selected_meta["source"] = {"subagent": {"other": "guardian" if subagent.get("other") == "guardian" else None, "thread_spawn": {k: spawn.get(k) for k in ("parent_thread_id", "agent_path", "agent_role")}}}
        item = grouped.setdefault(meta["id"], {"meta": selected_meta, "repo": repo, "records": [], "invalid": 0})
        for r in iterator:
            selected_events += 1
            if selected_events > MAX_EVENTS:
                raise ValueError("USAGE_EVENT_LIMIT")
            if r is None:
                item["invalid"] += 1
            elif r.get("type") == "turn_context" and isinstance(r.get("payload"), dict):
                item["records"].append({"timestamp": r.get("timestamp"), "type": "turn_context", "payload": {"model": r["payload"].get("model")}})
            elif r.get("type") == "event_msg" and isinstance(r.get("payload"), dict):
                q = r["payload"]
                if q.get("type") not in ("token_count", "task_started", "task_complete", "turn_aborted"):
                    continue
                selected = {k: q.get(k) for k in ("type", "turn_id", "started_at", "completed_at", "duration_ms")}
                if q.get("type") == "token_count":
                    raw = (q.get("info") or {}).get("total_token_usage") if isinstance(q.get("info"), dict) else None
                    selected["info"] = {"total_token_usage": {k: raw.get(k) for k in FIELDS} if isinstance(raw, dict) else None}
                item["records"].append({"timestamp": r.get("timestamp"), "type": "event_msg", "payload": selected})
    result = {}
    signals = collections.defaultdict(set)
    for session, item in grouped.items():
        for r in item["records"]:
            q = r.get("payload", {})
            if q.get("type") == "token_count":
                signals[fingerprint({"timestamp": r.get("timestamp"), "usage": q.get("info")})].add(session)
    shared = set().union(*(ids for ids in signals.values() if len(ids) > 1)) if signals else set()
    for session, item in grouped.items():
        value = normalise(item["records"], item["meta"], item["repo"], item["invalid"])
        value["shared_prefix_ambiguous"] = session in shared
        if session in shared:
            value["included_in_exact_rollup"] = False
            value["usage_quality"] = "partial_shared_prefix"
        last = value["last_event_at"]
        if last and dt.datetime.fromisoformat(last.replace("Z", "+00:00")) >= cutoff:
            result[session] = value
    return result
