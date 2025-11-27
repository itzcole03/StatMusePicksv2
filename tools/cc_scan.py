#!/usr/bin/env python3
"""Simple cyclomatic-complexity scanner for Python files.

Walks the repo (skips virtual envs/node_modules) and reports top functions
by an approximate McCabe complexity metric.
"""
import ast
import os
import sys
from collections import defaultdict


BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
    ast.BoolOp,
    ast.IfExp,
    ast.Lambda,
)


def complexity_of_node(node: ast.AST) -> int:
    """Approximate complexity contribution for a node."""
    if isinstance(node, ast.BoolOp):
        # each boolean operation with N values adds N-1
        return max(0, len(node.values) - 1)
    if isinstance(node, ast.If):
        # if + any elif/else handled via nested If in orelse
        return 1
    if isinstance(node, (ast.For, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.ExceptHandler, ast.IfExp, ast.Lambda)):
        return 1
    return 0


class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current = []
        self.results = []  # (name, lineno, complexity)

    def visit_FunctionDef(self, node):
        complexity = 1
        for child in ast.walk(node):
            complexity += complexity_of_node(child)
        name = node.name
        qual = name
        if self.current:
            qual = ".".join(self.current + [name])
        self.results.append((qual, node.lineno, complexity))
        # record nested
        self.current.append(name)
        self.generic_visit(node)
        self.current.pop()

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)


def scan_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception:
        return []
    try:
        tree = ast.parse(src, filename=path)
    except Exception:
        return []
    v = ComplexityVisitor()
    v.visit(tree)
    return [(path, n, l, c) for (n, l, c) in v.results]


def walk_repo(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip common large folders
        if any(p in dirpath for p in (".venv", "venv", "node_modules", "__pycache__", "artifacts", "mlruns")):
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            out.extend(scan_file(path))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    results = walk_repo(root)
    if not results:
        print("No functions found.")
        return
    # sort by complexity desc
    results.sort(key=lambda x: x[3], reverse=True)
    top = results[:50]
    for path, name, lineno, comp in top:
        print(f"{comp:3d} {path}:{lineno} {name}")


if __name__ == "__main__":
    main()
