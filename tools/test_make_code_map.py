"""Tests of the code map (docs/spec/code-map.md): python3 -m unittest discover -s tools -p 'test_*.py'."""
import pathlib
import tempfile
import unittest

import make_code_map as cm


class CodeMapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.write("app/__init__.py", "")
        self.write("app/models.py", """class Task:
    def total(self):
        return 0


def _hidden():
    pass


async def fetch():
    pass
""")
        self.write("app/config.py", "def get_settings():\n    return {}\n")
        self.write("app/clients/__init__.py", "from .gitlab import GitLabClient\n")
        self.write("app/clients/gitlab.py", """import httpx

from ..models import Task
from . import redmine


class GitLabClient:
    def update(self):
        from app.config import get_settings  # function-level import still counts
        return get_settings()
""")
        self.write("app/clients/redmine.py", "class RedmineClient:\n    pass\n")
        # Tests are not production modules, but specs may cite them.
        self.write("tests/test_models.py", "def test_task():\n    pass\n")
        self.write(".venv/lib/site.py", "x = 1\n")
        self.write("docs/spec/sync.md", "# Sync\n\nStatus: implemented.\n\nFiles: `app/clients/gitlab.py`, "
                   "`app/.../clients/redmine.py`. Tests: `tests/test_models.py::test_task`.\n")
        self.write("docs/spec/models.md", "# Models\n\nThe model lives in `models.py` (`models.py::Task.total`). "
                   "Globs and extensions are not citations: `test_*.py`, `.py`.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def modules(self):
        return {m.name: m for m in cm.build(self.root)[0]}

    def test_reads_modules_and_public_declarations(self):
        modules = self.modules()
        self.assertEqual(["app", "app.clients", "app.clients.gitlab", "app.clients.redmine", "app.config", "app.models"],
                         sorted(modules))  # neither tests/ nor .venv/
        self.assertEqual(["class Task", "async def fetch"], modules["app.models"].decls)  # _hidden is private
        self.assertEqual(11, modules["app.models"].lines)
        self.assertEqual("app.clients", modules["app.clients.gitlab"].package)
        self.assertEqual("app.clients", modules["app.clients"].package)  # a package's __init__ sits in its own column

    def test_relative_absolute_and_nested_imports_resolve(self):
        modules = self.modules()
        # `from ..models`, `from . import redmine`, the function-level `from app.config`; httpx is external.
        self.assertEqual(["app.clients.redmine", "app.config", "app.models"], modules["app.clients.gitlab"].imports)
        self.assertEqual(["app.clients.gitlab"], modules["app.clients"].imports)  # `from .gitlab` inside __init__
        self.assertEqual([], modules["app.models"].imports)

    def test_links_files_to_specs(self):
        modules = self.modules()
        self.assertEqual(["sync.md"], modules["app.clients.gitlab"].specs)
        self.assertEqual(["sync.md"], modules["app.clients.redmine"].specs)  # path abbreviated with "..."
        self.assertEqual(["models.md"], modules["app.models"].specs)  # bare file name
        self.assertEqual("Sync", cm.read_specs(self.root)["sync.md"]["title"])

    def test_index_filter_and_unlinked_modules(self):
        modules = cm.build(self.root)[0]
        text = cm.index(modules, "clients/")
        self.assertIn("## app.clients · 3 modules", text)
        self.assertNotIn("app/models.py", text)
        self.assertIn("imports app.clients.redmine, app.config, app.models · specs sync.md", text)
        whole = cm.index(modules)
        self.assertIn("(2 packages, 6 modules)", whole)
        self.assertIn("`app/config.py` (2) def get_settings · no spec", whole)

    def test_check_passes_on_a_consistent_tree(self):
        modules, specs = cm.build(self.root)
        errors, warnings = cm.check(self.root, modules, specs)
        self.assertEqual([], errors)
        self.assertIn("app/config.py: cited by no spec", warnings)

    def test_check_reports_code_the_spec_describes_but_does_not_exist(self):
        self.write("docs/spec/ghost.md", "# Ghost\n\n`app/ghost.py`, `tests/test_models.py::test_gone`, "
                   "`models.py::Task.missing`.\n")
        errors = cm.check(self.root, *cm.build(self.root))[0]
        self.assertEqual([
            "docs/spec/ghost.md: `app/ghost.py` matches no file",
            "docs/spec/ghost.md: `tests/test_models.py::test_gone` not found in tests/test_models.py",
            "docs/spec/ghost.md: `models.py::Task.missing` not found in app/models.py",
        ], errors)

    def test_check_skips_specs_not_implemented_yet(self):
        self.write("docs/spec/next.md", "# Next\n\nStatus: specified on 2026-11-25, not implemented.\n\n`app/next.py`.\n")
        self.assertEqual([], cm.check(self.root, *cm.build(self.root))[0])

    def test_main_check_exit_code(self):
        self.assertEqual(0, cm.main(["--root", str(self.root), "--check"]))
        self.write("docs/spec/ghost.md", "# Ghost\n\n`app/ghost.py`.\n")
        self.assertEqual(1, cm.main(["--root", str(self.root), "--check"]))

    def test_output_is_deterministic(self):
        modules, specs = cm.build(self.root)
        first = cm.page(cm.data(modules, specs, None))
        modules, specs = cm.build(self.root)
        self.assertEqual(first, cm.page(cm.data(modules, specs, None)))
        self.assertIn("Commit 0123456789ab.", cm.page(cm.data(modules, specs, "0123456789abcdef")))

    def test_page_is_self_contained(self):
        page = cm.page(cm.data(*cm.build(self.root), None))
        # No third-party resource: only links (a href) to GitHub, and the logo published next to the page.
        for marker in ("<script src", "<link rel=\"stylesheet\"", "@import", "url(\"http", "url(http"):
            self.assertNotIn(marker, page)
        self.assertIn('data-from="app.clients.gitlab" data-to="app.models"', page)
        self.assertIn("https://github.com/SKOHscripts/hermes/blob/main/docs/spec/sync.md", page)


if __name__ == "__main__":
    unittest.main()
