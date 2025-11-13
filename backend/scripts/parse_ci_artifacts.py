#!/usr/bin/env python3
"""Parse CI artifacts directory for Alembic logs and JUnit XML and print a concise summary.

Usage: python backend/scripts/parse_ci_artifacts.py ./ci_artifacts
"""
import sys
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def summarize_alembic_log(path: Path):
    text = path.read_text(errors='ignore')
    lines = text.splitlines()
    # Find migration prints and errors
    migrations = []
    errors = []
    skipped = []
    for i, l in enumerate(lines):
        if re.search(r"Running upgrade", l) or re.search(r"Running downgrade", l):
            migrations.append(l.strip())
        if re.search(r"ERROR|Traceback|alembic.util.exc", l, re.I):
            # capture a few lines context
            ctx = "\n".join(lines[max(0, i-2):i+3])
            errors.append(ctx)
        if re.search(r"skipp(ed|ing)|not supported|will be skipped|IF NOT EXISTS", l, re.I):
            skipped.append(l.strip())

    print(f"Alembic log: {path}")
    print(f"  migrations run lines: {len(migrations)}")
    for m in migrations[-10:]:
        print(f"    - {m}")
    if errors:
        print(f"  ERRORS ({len(errors)}):")
        for e in errors:
            print('---')
            print(e)
    if skipped:
        print(f"  Skipped/Notice lines ({len(skipped)}), sample: {skipped[:5]}")


def summarize_alembic_text(text: str, source: str = '<string>'):
    # Reuse the same logic but for raw text blobs (e.g., full workflow logs)
    lines = text.splitlines()
    migrations = []
    errors = []
    skipped = []
    for i, l in enumerate(lines):
        if re.search(r"Running upgrade|Running downgrade|alembic.runtime.migration", l):
            migrations.append(l.strip())
        if re.search(r"ERROR|Traceback|alembic.util.exc", l, re.I):
            ctx = "\n".join(lines[max(0, i-2):i+3])
            errors.append(ctx)
        if re.search(r"skipp(ed|ing)|not supported|will be skipped|IF NOT EXISTS|Will assume non-transactional DDL", l, re.I):
            skipped.append(l.strip())

    print(f"Alembic log (extracted): {source}")
    print(f"  migrations run lines: {len(migrations)}")
    for m in migrations[-10:]:
        print(f"    - {m}")
    if errors:
        print(f"  ERRORS ({len(errors)}):")
        for e in errors:
            print('---')
            print(e)
    if skipped:
        print(f"  Skipped/Notice lines ({len(skipped)}), sample: {skipped[:5]}")


def summarize_junit_xml(path: Path):
    print(f"JUnit XML: {path}")
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        print(f"  Failed to parse XML: {e}")
        return
    # handle both <testsuites> and single <testsuite>
    suites = []
    if root.tag == 'testsuites':
        suites = list(root.findall('testsuite'))
    elif root.tag == 'testsuite':
        suites = [root]
    total = 0
    failures = 0
    errors = 0
    skipped = 0
    for s in suites:
        total += int(s.attrib.get('tests', 0))
        failures += int(s.attrib.get('failures', 0))
        errors += int(s.attrib.get('errors', 0))
        skipped += int(s.attrib.get('skipped', 0) or s.attrib.get('skip', 0) or 0)
    print(f"  tests={total} failures={failures} errors={errors} skipped={skipped}")
    # print failing test cases
    if failures or errors:
        print("  Failing tests (sample):")
        for case in root.findall('.//testcase'):
            if case.find('failure') is not None or case.find('error') is not None:
                name = case.attrib.get('name')
                cls = case.attrib.get('classname')
                print(f"    - {cls}.{name}")


def main(root_dir: str):
    p = Path(root_dir)
    if not p.exists():
        print(f"Path not found: {p}")
        return 2
    for run_dir in sorted(p.iterdir()):
        if not run_dir.is_dir():
            continue
        print(f"\n=== Run dir: {run_dir} ===")
        for f in run_dir.rglob('*'):
            if f.is_file():
                name = f.name.lower()
                # direct alembic log files
                if 'alembic' in name and f.suffix in ('', '.log', '.txt'):
                    summarize_alembic_log(f)
                # detect embedded alembic output inside larger run logs
                elif f.suffix in ('.txt', '.log'):
                    try:
                        text = f.read_text(errors='ignore')
                        if re.search(r"Running upgrade|alembic.runtime.migration|Will assume non-transactional DDL", text, re.I):
                            summarize_alembic_text(text, str(f))
                    except Exception:
                        pass
                # junit xml files
                if f.suffix == '.xml' and 'junit' in name:
                    summarize_junit_xml(f)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: parse_ci_artifacts.py <artifacts_root_dir>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
