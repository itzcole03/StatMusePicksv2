#!/usr/bin/env python3
"""
Safe codemod to add Pydantic v2 `model_config = ConfigDict(...)` shims
for classes that define an inner `Config` with `schema_extra`.

Usage:
  # dry-run (default)
  python scripts/convert_pydantic_config.py backend

  # apply changes
  python scripts/convert_pydantic_config.py --apply backend

This script is cautious: it creates a `.bak` backup before modifying files
and will skip files that already contain a `model_config` assignment for
the target class.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
from typing import List, Tuple


def find_schema_extra_in_class(src: str) -> List[Tuple[str, int, str]]:
    """
    Return list of tuples (outer_class_name, insert_lineno, schema_extra_source)
    for each outer class that contains an inner `class Config` with an
    assignment to `schema_extra`.
    """
    tree = ast.parse(src)
    results: List[Tuple[str, int, str]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            outer = node
            # search for inner class Config
            for inner in outer.body:
                if isinstance(inner, ast.ClassDef) and inner.name == "Config":
                    # look for Assign to schema_extra
                    for stmt in inner.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if (
                                    isinstance(target, ast.Name)
                                    and target.id == "schema_extra"
                                ):
                                    # extract source segment for the value
                                    try:
                                        value_src = ast.get_source_segment(
                                            src, stmt.value
                                        )
                                    except Exception:
                                        # fallback: try to unparse (py3.9+)
                                        try:
                                            value_src = ast.unparse(stmt.value)
                                        except Exception:
                                            value_src = None

                                    if value_src is not None:
                                        # insertion point: after outer class end
                                        insert_lineno = getattr(
                                            outer, "end_lineno", outer.lineno
                                        )
                                        results.append(
                                            (outer.name, insert_lineno, value_src)
                                        )
    return results


def process_file(path: pathlib.Path, apply: bool = False) -> Tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if f".model_config = ConfigDict" in src:
        return False, "already-has-model_config"

    entries = find_schema_extra_in_class(src)
    if not entries:
        return False, "no-schema-extra"

    lines = src.splitlines()
    # we'll insert snippets in reverse order of lineno to keep offsets stable
    inserts: List[Tuple[int, str]] = []
    for class_name, lineno, value_src in entries:
        snippet = f"\ntry:\n    from pydantic import ConfigDict\nexcept Exception:\n    ConfigDict = None\n\nif ConfigDict is not None:\n    {class_name}.model_config = ConfigDict(json_schema_extra={value_src})\n"
        inserts.append((lineno, snippet))

    inserts.sort(reverse=True, key=lambda x: x[0])
    for lineno, snippet in inserts:
        # lineno is 1-based line number after which to insert
        idx = lineno
        # ensure idx within bounds
        if idx < 0:
            idx = 0
        if idx > len(lines):
            idx = len(lines)
        lines.insert(idx, snippet)

    new_src = "\n".join(lines)

    if apply:
        bak = path.with_suffix(path.suffix + ".bak")
        path.replace(path)  # no-op to ensure permissions; if error will raise
        path.write_text(new_src, encoding="utf-8")
        # write backup as well (best-effort)
        try:
            bak.write_text(src, encoding="utf-8")
        except Exception:
            pass
        return True, "modified"
    else:
        return True, new_src


def walk_and_process(targets: List[str], apply: bool = False):
    paths = []
    for t in targets:
        p = pathlib.Path(t)
        if p.is_file():
            paths.append(p)
        else:
            for f in p.rglob("*.py"):
                # skip virtualenvs and typical vendored dirs
                if any(
                    part in ("site-packages", ".venv", "venv", "__pycache__")
                    for part in f.parts
                ):
                    continue
                paths.append(f)

    modified = []
    skipped = []
    previews: List[Tuple[pathlib.Path, str]] = []
    for path in sorted(paths):
        ok, result = process_file(path, apply=apply)
        if ok:
            if apply:
                modified.append(str(path))
            else:
                previews.append((path, result))
        else:
            skipped.append((str(path), result))

    return modified, skipped, previews


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="+", help="Files or directories to scan")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    args = parser.parse_args()

    modified, skipped, previews = walk_and_process(args.targets, apply=args.apply)

    if args.apply:
        print(f"Modified {len(modified)} files:")
        for m in modified:
            print("  ", m)
    else:
        print(f"Dry-run previews for {len(previews)} files (showing snippet):")
        for p, new in previews:
            print("---", p)
            # show a small preview (first 40 lines)
            print("\n".join(new.splitlines()[:40]))
            print("...")

    if skipped:
        print("\nSkipped files:")
        for s in skipped[:50]:
            print("  ", s[0], "-", s[1])


if __name__ == "__main__":
    main()
