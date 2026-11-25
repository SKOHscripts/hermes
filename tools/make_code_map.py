"""HERMES code map (docs/spec/code-map.md): modules, declarations, imports and the specs that cite them.

One source, several outputs:

    python3 tools/make_code_map.py --index [filter]       # compact Markdown for Claude Code (standard output)
    python3 tools/make_code_map.py --check                # spec/code bijectivity check (CI)
    python3 tools/make_code_map.py --html _site/code/index.html --stamp "$GITHUB_SHA"   # public page
    python3 tools/make_code_map.py --json map.json        # raw data

Standard library only; Python sources are read with `ast` (docs/spec/code-map.md § Decisions).
"""
from __future__ import annotations

import argparse
import ast
import html
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field

GITHUB = "https://github.com/SKOHscripts/hermes/blob/main/"
DEFAULT_SRC = ["app", "tools"]
# Directories never read, wherever they are (virtual environments, caches, build output, VCS).
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist", "_site"}
# A backticked token ending in `.py`, optionally followed by `::name` (test or declaration), e.g.
# `app/sync.py`, `sync.py`, `tests/test_sync.py::test_idempotent`, `app/.../gitlab.py::GitLabClient.update_issue`.
# A glob (`test_*.py`) or a bare extension (`.py`) is not a citation.
SPEC_TOKEN_RE = re.compile(r"`([^`\s*]*?\w\.py)(?:::([\w.]+))?`")
NOT_IMPLEMENTED_RE = re.compile(r"^Status:.*\bnot implemented\b", re.IGNORECASE | re.MULTILINE)


@dataclass
class Module:
    path: str  # relative to the repository, with "/"
    name: str  # dotted name, e.g. app.clients.gitlab ("app.clients" for app/clients/__init__.py)
    package: str  # containing package, e.g. app.clients (the graph column)
    lines: int
    decls: list[str] = field(default_factory=list)  # "class GitLabClient", "def sync", "async def fetch"
    imports: list[str] = field(default_factory=list)  # project modules it imports, sorted
    specs: list[str] = field(default_factory=list)  # file names in docs/spec/


def is_test(path: pathlib.Path) -> bool:
    return path.name == "conftest.py" or path.name.startswith("test_") or path.stem.endswith("_test") or "tests" in path.parts


def py_files(base: pathlib.Path) -> list[pathlib.Path]:
    """Every `.py` file under [base], sorted, outside SKIP_DIRS."""
    return sorted(p for p in base.rglob("*.py") if not SKIP_DIRS.intersection(p.relative_to(base).parts[:-1]))


def count_lines(text: str) -> int:
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1)


def top_level_names(tree: ast.Module) -> set[str]:
    """Top-level classes and functions, plus `Class.method`, for `::name` references."""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            if isinstance(node, ast.ClassDef):
                names.update(f"{node.name}.{n.name}" for n in node.body
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    return names


def declarations(tree: ast.Module) -> list[str]:
    """Public top-level declarations, in source order (a leading underscore means private)."""
    kinds = {ast.ClassDef: "class", ast.FunctionDef: "def", ast.AsyncFunctionDef: "async def"}
    return [f"{kinds[type(n)]} {n.name}" for n in tree.body if type(n) in kinds and not n.name.startswith("_")]


def raw_imports(tree: ast.Module, module: str, is_package: bool) -> set[tuple[str, str | None]]:
    """(name, fallback) for every import anywhere in the module (function-level imports included).

    `from pkg import name` imports either the module pkg.name or an attribute of pkg: (pkg.name, pkg)."""
    package = module.split(".") if is_package else module.split(".")[:-1]
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update((alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: `from ..models import X` climbs level - 1 packages
                if node.level - 1 > len(package):
                    continue
                parts = package[:len(package) - (node.level - 1)]
                base = ".".join(parts + (node.module.split(".") if node.module else []))
            else:
                base = node.module or ""
            found.update((f"{base}.{alias.name}", base) if alias.name != "*" else (base, None) for alias in node.names)
    return found


def read_sources(root: pathlib.Path, src: list[str]) -> list[Module]:
    """Production modules under the [src] directories of [root], sorted by path; tests are left out."""
    modules: list[Module] = []
    imported: dict[str, set[str]] = {}
    for top in src:
        base = root / top
        if not base.is_dir():
            continue
        for py in py_files(base):
            if is_test(py.relative_to(root)):
                continue
            rel = py.relative_to(root)
            parts = list(rel.with_suffix("").parts)
            is_package = parts[-1] == "__init__"
            name = ".".join(parts[:-1] if is_package else parts)
            text = py.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(rel))
            modules.append(Module(
                path=rel.as_posix(), name=name, package=name if is_package else ".".join(parts[:-1]),
                lines=count_lines(text), decls=declarations(tree),
            ))
            imported[name] = raw_imports(tree, name, is_package)
    known = sorted({m.name for m in modules}, key=len, reverse=True)
    for m in modules:
        resolved = set()
        for target, fallback in imported[m.name]:
            if target not in known and fallback is not None:
                target = fallback
            match = next((k for k in known if target == k or target.startswith(k + ".")), None)
            if match is not None and match != m.name:
                resolved.add(match)
        m.imports = sorted(resolved)
    return sorted(modules, key=lambda m: m.path)


def spec_tokens(text: str) -> list[tuple[str, str | None]]:
    """(path token, `::name` or None) cited by a spec, in order, without duplicates; "..." abbreviations are cut."""
    tokens = []
    for path, name in SPEC_TOKEN_RE.findall(text):
        path = re.split(r"\.\.\.|…", path)[-1].lstrip("/")
        token = (path, name or None)
        if path and token not in tokens:
            tokens.append(token)
    return tokens


def read_specs(root: pathlib.Path) -> dict[str, dict]:
    """docs/spec/*.md → title, cited tokens, and whether the spec is still "not implemented"."""
    specs = {}
    spec_dir = root / "docs" / "spec"
    for md in sorted(spec_dir.glob("*.md")) if spec_dir.is_dir() else []:
        text = md.read_text(encoding="utf-8")
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), md.stem)
        specs[md.name] = {"title": title, "tokens": spec_tokens(text), "implemented": not NOT_IMPLEMENTED_RE.search(text)}
    return specs


def matches(path: str, token: str) -> bool:
    """A token is a full path, a path tail (`clients/gitlab.py`) or a bare file name (`gitlab.py`)."""
    return path == token or path.endswith("/" + token)


def link_specs(modules: list[Module], specs: dict[str, dict]) -> None:
    for m in modules:
        m.specs = [name for name, spec in specs.items() if any(matches(m.path, t) for t, _ in spec["tokens"])]


def build(root: pathlib.Path, src: list[str] | None = None) -> tuple[list[Module], dict[str, dict]]:
    modules = read_sources(root, src or DEFAULT_SRC)
    specs = read_specs(root)
    link_specs(modules, specs)
    return modules, specs


# ---- Bijectivity check ----------------------------------------------------------------------------------------------

def check(root: pathlib.Path, modules: list[Module], specs: dict[str, dict]) -> tuple[list[str], list[str]]:
    """(errors, warnings). Error: an implemented spec cites a `.py` file, or a `::name` in it, that does not exist.
    Warning: a production module that no spec cites."""
    files = {p.relative_to(root).as_posix(): p for p in py_files(root)}
    names_cache: dict[str, set[str]] = {}

    def names(path: str) -> set[str]:
        if path not in names_cache:
            names_cache[path] = top_level_names(ast.parse(files[path].read_text(encoding="utf-8")))
        return names_cache[path]

    errors = []
    for spec_name, spec in specs.items():
        if not spec["implemented"]:
            continue  # cites code to come; checked once its Status says it is implemented
        for token, name in spec["tokens"]:
            hits = [p for p in files if matches(p, token)]
            if not hits:
                errors.append(f"docs/spec/{spec_name}: `{token}` matches no file")
            elif name and not any(name in names(p) for p in hits):
                errors.append(f"docs/spec/{spec_name}: `{token}::{name}` not found in {', '.join(hits)}")
    # An __init__.py that declares nothing only re-exports: it carries no behaviour to specify.
    warnings = [f"{m.path}: cited by no spec" for m in modules
                if not m.specs and (m.decls or not m.path.endswith("__init__.py"))]
    return errors, warnings


# ---- Index for Claude Code -------------------------------------------------------------------------------------------

def index(modules: list[Module], query: str | None = None) -> str:
    """Compact Markdown, one section per package; [query] filters on the dotted name or the path."""
    shown = [m for m in modules if not query or query in m.name or query in m.path]
    packages = sorted({m.package for m in shown})
    out = [f"# Code map ({len(packages)} packages, {len(shown)} modules)" + (f" · filter \"{query}\"" if query else "")]
    for package in packages:
        members = [m for m in shown if m.package == package]
        out += ["", f"## {package} · {len(members)} modules, {sum(m.lines for m in members)} lines"]
        for m in members:
            decls = ", ".join(m.decls[:8]) + (" …" if len(m.decls) > 8 else "")
            imports = f" · imports {', '.join(m.imports)}" if m.imports else ""
            spec = f" · specs {', '.join(m.specs)}" if m.specs else " · no spec"
            out.append(f"- `{m.path}` ({m.lines})" + (f" {decls}" if decls else "") + imports + spec)
    return "\n".join(out) + "\n"


# ---- Data and page ---------------------------------------------------------------------------------------------------

def data(modules: list[Module], specs: dict[str, dict], stamp: str | None) -> dict:
    return {
        "stamp": stamp,
        "packages": sorted({m.package for m in modules}),
        "specs": {name: spec["title"] for name, spec in specs.items()},
        "modules": [{"id": m.name, "path": m.path, "package": m.package, "lines": m.lines, "decls": m.decls,
                     "imports": m.imports, "specs": m.specs} for m in modules],
    }


BOX_W, BOX_H, GAP_Y, COL_W, PAD = 200, 26, 8, 260, 20


def layout(model: dict) -> tuple[dict[str, tuple[int, int]], int, int]:
    """Position (x, y) of each module: one column per package, modules sorted by name."""
    pos, height = {}, 0
    for c, package in enumerate(model["packages"]):
        column = sorted((m for m in model["modules"] if m["package"] == package), key=lambda m: m["id"])
        for r, m in enumerate(column):
            pos[m["id"]] = (PAD + c * COL_W, PAD + 30 + r * (BOX_H + GAP_Y))
        height = max(height, PAD + 30 + len(column) * (BOX_H + GAP_Y))
    width = PAD * 2 + max(len(model["packages"]) - 1, 0) * COL_W + BOX_W
    return pos, width, height + PAD


def label(module: dict) -> str:
    """The module name inside its column: `gitlab` in column app.clients, `app.clients` for a package itself."""
    name = module["id"][len(module["package"]) + 1:] if module["id"] != module["package"] else "__init__"
    return name if len(name) <= 26 else "…" + name[-25:]


def svg(model: dict) -> str:
    pos, width, height = layout(model)
    parts = [f'<svg id="graph" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" '
             f'aria-label="Module dependency graph">']
    for c, package in enumerate(model["packages"]):
        parts.append(f'<text class="col" x="{PAD + c * COL_W}" y="{PAD + 12}">{html.escape(package)}</text>')
    for m in model["modules"]:
        x1, y1 = pos[m["id"]]
        for d in m["imports"]:
            x2, y2 = pos[d]
            a, b = y1 + BOX_H / 2, y2 + BOX_H / 2
            if x2 < x1:  # towards a column on the left: from the left edge of the source to the right edge of the target
                sx, ex = x1, x2 + BOX_W
                mid = (sx + ex) / 2
                path = f"M{sx},{a} C{mid},{a} {mid},{b} {ex},{b}"
            else:  # same column (or to the right): an arc on the right, bounded by the gap between two columns
                sx, ex = x1 + BOX_W, x2 + BOX_W
                bulge = max(sx, ex) + min(COL_W - BOX_W - 8, 16 + abs(b - a) / 12)
                path = f"M{sx},{a} C{bulge},{a} {bulge},{b} {ex},{b}"
            parts.append(f'<path class="edge" data-from="{m["id"]}" data-to="{d}" d="{path}"/>')
    for m in model["modules"]:
        x, y = pos[m["id"]]
        parts.append(
            f'<g class="node" data-id="{m["id"]}" tabindex="0" role="button" aria-label="{html.escape(m["id"])}">'
            f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="6"/>'
            f'<text x="{x + 10}" y="{y + 17}">{html.escape(label(m))}</text></g>'
        )
    parts.append("</svg>")
    return "".join(parts)


def module_list(model: dict) -> str:
    out = []
    for m in model["modules"]:
        specs = " ".join(f'<a href="{GITHUB}docs/spec/{s}">{html.escape(model["specs"].get(s, s))}</a>' for s in m["specs"])
        imports = ", ".join(html.escape(i) for i in m["imports"])
        text = html.escape((m["id"] + " " + m["path"] + " " + " ".join(m["decls"])).lower())
        out.append(
            f'<details class="mod" id="{html.escape(m["id"])}" data-id="{html.escape(m["id"])}" data-text="{text}">'
            f'<summary><strong>{html.escape(m["id"])}</strong> <span class="meta">{m["lines"]} lines</span></summary>'
            f'<p class="row"><span class="k">File</span> <a href="{GITHUB}{m["path"]}">{html.escape(m["path"])}</a></p>'
            + (f'<p class="row"><span class="k">Declares</span> {html.escape(", ".join(m["decls"]))}</p>' if m["decls"] else "")
            + (f'<p class="row"><span class="k">Imports</span> {imports}</p>' if imports else "")
            + f'<p class="row"><span class="k">Specs</span> {specs or "<span class=none>none</span>"}</p></details>'
        )
    return "".join(out)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HERMES code map</title>
<meta name="description" content="How the HERMES code is organised: packages, modules, imports and the specs that describe them.">
<link rel="icon" href="../logo.svg" type="image/svg+xml">
<style>
:root { --bg: #eaedf1; --surface: #ffffff; --text: #141b24; --muted: #47515e; --line: #d8dde4; --edge: #c3cad3;
  --primary: #3f4d5f; --on-primary: #ffffff; --mark: #0a8b95; color-scheme: light dark; }
@media (prefers-color-scheme: dark) { :root { --bg: #11161d; --surface: #1a212b; --text: #e6e9ee; --muted: #a9b2bf;
  --line: #2f3946; --edge: #3a4553; --primary: #a9b8cc; --on-primary: #11161d; --mark: #27a3ac; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
header, main { max-width: 1200px; margin: 0 auto; padding: 0 16px; }
header { display: flex; align-items: center; gap: 12px; padding-top: 24px; }
header img { width: 40px; height: 40px; }
header .name { font-size: 24px; font-weight: 600; }
main { padding-bottom: 48px; }
h1 { font-size: 24px; font-weight: 600; margin: 16px 0 8px; }
p.lead { color: var(--muted); margin: 0 0 16px; max-width: 760px; }
a { color: var(--mark); }
code { font-family: ui-monospace, "IBM Plex Mono", monospace; }
input[type=search] { width: 100%; max-width: 480px; font: inherit; padding: 10px 12px; border: 1px solid var(--edge);
  border-radius: 4px; background: var(--surface); color: var(--text); min-height: 44px; }
.scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); margin: 16px 0 24px; }
svg text { font: 12px ui-monospace, "IBM Plex Mono", monospace; fill: var(--text); }
svg text.col { font: 600 12px system-ui, sans-serif; fill: var(--muted); }
.node { cursor: pointer; }
.node rect { fill: var(--surface); stroke: var(--edge); }
.node:focus { outline: none; }
.node:focus rect, .node:hover rect { stroke: var(--mark); }
.edge { fill: none; stroke: var(--edge); stroke-width: 1; }
svg.active .node, svg.active .edge { opacity: 0.18; }
svg.active .node.on, svg.active .edge.on { opacity: 1; }
svg.active .edge.on { stroke: var(--mark); stroke-width: 2; }
svg.active .node.self rect { fill: var(--primary); stroke: var(--primary); }
svg.active .node.self text { fill: var(--on-primary); }
svg .node.hidden { opacity: 0.18; }
.mod { border: 1px solid var(--line); border-radius: 8px; background: var(--surface); margin: 8px 0; padding: 0 12px; }
.mod[open] { padding-bottom: 8px; }
.mod.target { border-color: var(--mark); }
summary { cursor: pointer; padding: 12px 0; min-height: 44px; overflow-wrap: anywhere; }
.meta, .none { color: var(--muted); }
.row { margin: 4px 0; overflow-wrap: anywhere; }
.k { font-weight: 600; margin-right: 6px; }
footer { color: var(--muted); margin-top: 32px; font-size: 13px; }
</style>
</head>
<body>
<header><img src="../logo.svg" alt=""><span class="name">HERMES</span></header>
<main>
<h1>Code map</h1>
<p class="lead">How the code is organised: one column per package, one box per module, a line for each module that
imports another. Select a module to see what it imports and what imports it; the list below gives its file, its public
top-level declarations and the specifications that describe it. Generated from <code>main</code>.</p>
<input type="search" id="q" placeholder="Search a module, a file or a declaration" aria-label="Search">
<div class="scroll">@@SVG@@</div>
<section id="list">@@LIST@@</section>
<footer>@@STAMP@@ Generated by <a href="https://github.com/SKOHscripts/hermes/blob/main/tools/make_code_map.py">tools/make_code_map.py</a>
(<a href="https://github.com/SKOHscripts/hermes/blob/main/docs/spec/code-map.md">spec</a>).</footer>
</main>
<script type="application/json" id="data">@@DATA@@</script>
<script>
(() => {
  const model = JSON.parse(document.getElementById("data").textContent);
  const graph = document.getElementById("graph");
  const deps = new Map(model.modules.map(m => [m.id, new Set(m.imports)]));
  const users = new Map(model.modules.map(m => [m.id, new Set()]));
  model.modules.forEach(m => m.imports.forEach(d => users.get(d).add(m.id)));
  let current = null;
  function select(id) {
    current = current === id ? null : id;
    graph.classList.toggle("active", current !== null);
    graph.querySelectorAll(".node").forEach(n => {
      const nid = n.dataset.id;
      n.classList.toggle("self", nid === current);
      n.classList.toggle("on", current !== null && (nid === current || deps.get(current).has(nid) || users.get(current).has(nid)));
    });
    graph.querySelectorAll(".edge").forEach(e => {
      e.classList.toggle("on", current !== null && (e.dataset.from === current || e.dataset.to === current));
    });
    document.querySelectorAll(".mod").forEach(d => d.classList.toggle("target", d.dataset.id === current));
    if (current) { document.getElementById(current).open = true; }
  }
  graph.querySelectorAll(".node").forEach(n => {
    n.addEventListener("click", () => select(n.dataset.id));
    n.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(n.dataset.id); } });
  });
  document.getElementById("q").addEventListener("input", e => {
    const q = e.target.value.trim().toLowerCase();
    document.querySelectorAll(".mod").forEach(d => {
      const hit = !q || d.dataset.text.includes(q);
      d.hidden = !hit;
      const node = graph.querySelector(`.node[data-id="${CSS.escape(d.dataset.id)}"]`);
      if (node) node.classList.toggle("hidden", !hit);
    });
  });
})();
</script>
</body>
</html>
"""


def page(model: dict) -> str:
    stamp = f"Commit {html.escape(model['stamp'][:12])}." if model.get("stamp") else ""
    # The script only needs the links between modules; the rest is already in the HTML. "</" in the JSON would close
    # the script element: escape it.
    links = {"modules": [{"id": m["id"], "imports": m["imports"]} for m in model["modules"]]}
    payload = json.dumps(links, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return (PAGE.replace("@@SVG@@", svg(model)).replace("@@LIST@@", module_list(model))
            .replace("@@STAMP@@", stamp).replace("@@DATA@@", payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--src", nargs="+", default=DEFAULT_SRC, help="source directories, relative to --root")
    parser.add_argument("--index", nargs="?", const="", metavar="FILTER", help="Markdown index, filtered by name or path")
    parser.add_argument("--check", action="store_true", help="fail when a spec cites code that does not exist")
    parser.add_argument("--html", type=pathlib.Path, help="write the public page")
    parser.add_argument("--json", type=pathlib.Path, help="write the data")
    parser.add_argument("--stamp", help="commit shown on the page")
    args = parser.parse_args(argv)
    modules, specs = build(args.root, args.src)
    status = 0
    if args.index is not None:
        sys.stdout.write(index(modules, args.index or None))
    if args.check:
        errors, warnings = check(args.root, modules, specs)
        # shortcut: modules without a spec only warn, so the migration from dotfiles can land; make them errors once
        # every migrated module is cited (docs/spec/code-map.md § Decisions).
        for line in warnings:
            print(f"warning: {line}", file=sys.stderr)
        for line in errors:
            print(f"error: {line}", file=sys.stderr)
        print(f"code map check: {len(errors)} error(s), {len(warnings)} module(s) without spec", file=sys.stderr)
        status = 1 if errors else 0
    model = data(modules, specs, args.stamp)
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(page(model), encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(model, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.index is None and not (args.check or args.html or args.json):
        parser.print_help()
    return status


if __name__ == "__main__":
    sys.exit(main())
