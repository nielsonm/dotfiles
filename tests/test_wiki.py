"""Unit tests for building and validating GitHub Wiki documentation."""

from pathlib import Path
import re
import unittest

try:
    import markdown
except ImportError:
    markdown = None


class TestWikiBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.wiki_dir = cls.repo_root / "wiki"
        cls.wiki_files = list(cls.wiki_dir.glob("*.md"))

    def test_wiki_directory_and_required_files_exist(self):
        self.assertTrue(self.wiki_dir.exists(), "wiki/ directory does not exist")
        self.assertTrue(self.wiki_dir.is_dir(), "wiki/ is not a directory")

        required_files = ["Home.md", "_Sidebar.md", "_Footer.md"]
        for req in required_files:
            req_path = self.wiki_dir / req
            self.assertTrue(req_path.exists(), f"Required wiki file {req} is missing")
            self.assertGreater(req_path.stat().st_size, 0, f"{req} is empty")

    @unittest.skipUnless(markdown is not None, "markdown package is not installed")
    def test_wiki_markdown_compiles_to_html(self):
        """Verifies that all wiki pages cleanly compile to HTML without syntax errors."""
        self.assertGreater(len(self.wiki_files), 0, "No markdown files found in wiki/")

        for md_file in self.wiki_files:
            with self.subTest(file=md_file.name):
                text = md_file.read_text(encoding="utf-8")
                html = markdown.markdown(
                    text,
                    extensions=["extra", "fenced_code", "tables", "toc"],
                )
                self.assertIsInstance(html, str)
                self.assertGreater(len(html), 0, f"Rendered HTML for {md_file.name} is empty")

    def test_wiki_internal_and_file_links(self):
        """Verifies that internal wiki links, repository GitHub URLs, and file references resolve to existing targets."""
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        gh_blob_prefix = "https://github.com/nielsonm/dotfiles/blob/main/"
        gh_tree_prefix = "https://github.com/nielsonm/dotfiles/tree/main/"

        for md_file in self.wiki_files:
            with self.subTest(file=md_file.name):
                text = md_file.read_text(encoding="utf-8")
                for label, target in link_pattern.findall(text):
                    # Check GitHub repository blob & tree links to ensure they point to real repo files
                    if target.startswith(gh_blob_prefix) or target.startswith(gh_tree_prefix):
                        prefix = gh_blob_prefix if target.startswith(gh_blob_prefix) else gh_tree_prefix
                        rel_path = target[len(prefix):].split("#")[0]
                        target_file = self.repo_root / rel_path
                        self.assertTrue(
                            target_file.exists(),
                            f"Broken repo link in {md_file.name}: '{target}' -> path '{target_file}' does not exist in repository",
                        )
                    # Skip other external web URLs
                    elif target.startswith("http://") or target.startswith("https://"):
                        continue
                    # Check local absolute file links (supporting both local and CI paths)
                    elif target.startswith("file://"):
                        clean_path = target.split("#")[0].replace("file://", "")
                        if "dotfiles/" in clean_path:
                            rel_subpath = clean_path.split("dotfiles/", 1)[1]
                            resolved = self.repo_root / rel_subpath
                        else:
                            resolved = Path(clean_path)
                        self.assertTrue(
                            resolved.exists(),
                            f"Broken file link in {md_file.name}: '{target}' -> path '{resolved}' does not exist",
                        )
                    # Check internal wiki links
                    else:
                        page_target = target.split("#")[0]
                        wiki_page = self.wiki_dir / f"{page_target}.md"
                        self.assertTrue(
                            wiki_page.exists(),
                            f"Broken wiki link in {md_file.name}: link target '{target}' does not match any wiki page ({wiki_page})",
                        )

    def test_wiki_code_block_fences_balanced(self):
        """Ensures all markdown code blocks (triple backticks) are properly closed."""
        fence = chr(96) * 3
        for md_file in self.wiki_files:
            with self.subTest(file=md_file.name):
                text = md_file.read_text(encoding="utf-8")
                fence_count = text.count(fence)
                self.assertEqual(
                    fence_count % 2,
                    0,
                    f"Unbalanced code block fences in {md_file.name}: found {fence_count} occurrences of {fence}",
                )

    def test_sidebar_links_point_to_valid_pages(self):
        """Ensures every navigation entry in _Sidebar.md corresponds to an existing wiki page."""
        sidebar = self.wiki_dir / "_Sidebar.md"
        text = sidebar.read_text(encoding="utf-8")
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

        for label, target in link_pattern.findall(text):
            if not target.startswith("http://") and not target.startswith("https://"):
                page_path = self.wiki_dir / f"{target}.md"
                self.assertTrue(
                    page_path.exists(),
                    f"_Sidebar.md link '{target}' does not exist at {page_path}",
                )


if __name__ == "__main__":
    unittest.main()
