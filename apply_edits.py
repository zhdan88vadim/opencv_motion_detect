#!/usr/bin/env python3
"""apply_edits.py — apply text edits to source files described in a
files-to-prompt dump.

Usage:
    python apply_edits.py DUMP EDITS [--dry-run] [--verbose]
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

GUTTER = re.compile(r"^ *\d+  ?")

def strip_gutter(line: str) -> str:
    return GUTTER.sub("", line, count=1)

def parse_dump(text: str) -> dict[str, list[str]]:
    files: dict[str, list[str]] = {}
    current: str | None = None
    in_body = False
    for raw in text.splitlines(keepends=False):
        if raw.startswith("./"):
            if current is not None:
                files[current] = files.get(current, [])
            current = raw[2:].strip()
            in_body = False
            files[current] = []
            continue
        if raw.strip() == "---":
            in_body = True
            continue
        if current is None or not in_body:
            continue
        files[current].append(strip_gutter(raw))
    return files

def normalize_for_match(text: str) -> str:
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)

def find_block(haystack: str, needle: str) -> tuple[int, int] | None:
    hay_lines = haystack.split("\n")
    needle_lines = needle.split("\n")
    if not needle_lines:
        return None
    n = len(needle_lines)
    hay_stripped = [ln.rstrip() for ln in hay_lines]
    for i in range(len(hay_stripped) - n + 1):
        if hay_stripped[i:i + n] == needle_lines:
            start = sum(len(hay_lines[j]) + 1 for j in range(i))
            end = start + sum(len(hay_lines[j]) + 1 for j in range(i, i + n))
            if end > 0 and haystack[end - 1:end] == "\n":
                end -= 1
            return start, end
    return None

def apply_edit(content: str, old: str, new: str) -> tuple[str | None, str]:
    old_n = normalize_for_match(old)
    new_n = normalize_for_match(new)
    if not old_n:
        return None, "empty `old`"
    span = find_block(content, old_n)
    if span is not None:
        start, end = span
        return content[:start] + new_n + content[end:], ""
    if new_n and find_block(content, new_n) is not None:
        return content, ""
    return None, f"old block not found ({len(old_n.splitlines())} lines)"

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("dump"); ap.add_argument("edits")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    dump_text = sys.stdin.read() if args.dump == "-" else Path(args.dump).read_text()
    dump = parse_dump(dump_text)
    if not dump:
        print("error: no files parsed from dump", file=sys.stderr); return 2
    edits = json.loads(Path(args.edits).read_text())
    if not isinstance(edits, list):
        print("error: edits file must be a JSON list", file=sys.stderr); return 2
    by_file: dict[str, list[dict]] = {}
    for e in edits:
        by_file.setdefault(e["file"], []).append(e)
    rc = 0
    for path_str, file_edits in by_file.items():
        path = Path(path_str)
        if not path.exists():
            print(f"error: {path} does not exist on disk", file=sys.stderr)
            rc = 1; continue
        content = path.read_text()
        failed = False
        for idx, e in enumerate(file_edits):
            new_content, why = apply_edit(content, e["old"], e["new"])
            if new_content is None:
                print(f"FAIL  {path}  edit #{idx}: {why}", file=sys.stderr)
                failed = True; rc = 1; continue
            content = new_content
            if args.verbose:
                print(f"ok    {path}  edit #{idx}")
        if failed:
            print(f"      {path}: not written (has failures)", file=sys.stderr); continue
        if args.dry_run:
            print(f"would write {path} ({len(file_edits)} edit(s))")
        else:
            path.write_text(content)
            print(f"wrote {path} ({len(file_edits)} edit(s))")
    return rc

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))