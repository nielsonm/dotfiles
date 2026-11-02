"""Unit tests for find_media_duplicates.py."""

from pathlib import Path
import tempfile
import unittest

from find_media_duplicates import (
    FileEntry,
    canonical_tokens,
    clean_media_stem,
    extract_episode,
    find_cross_format_duplicates,
    find_exact_duplicates,
    find_fuzzy_similar_titles,
    find_mangled_and_incomplete_files,
    generate_cleanup_script,
    human_readable_size,
    resolve_directory,
    scan_files,
)


class TestFindMediaDuplicates(unittest.TestCase):
    def test_human_readable_size(self):
        self.assertEqual(human_readable_size(500), "500.00 B")
        self.assertEqual(human_readable_size(1024), "1.00 KB")
        self.assertEqual(human_readable_size(1024 * 1024 * 5), "5.00 MB")
        self.assertEqual(human_readable_size(1024 * 1024 * 1024 * 2), "2.00 GB")

    def test_clean_media_stem(self):
        self.assertEqual(
            clean_media_stem("Movie.Title.2021.1080p.BluRay.x264.mkv"),
            "movie title",
        )
        self.assertEqual(
            clean_media_stem("Show.Name.S01E05.720p.WEBRip.mkv"),
            "show name s01e05",
        )
        self.assertEqual(
            clean_media_stem("Book Title [retail] (2018).epub"),
            "book title",
        )

    def test_canonical_tokens(self):
        # Inverted words should produce identical canonical tokens
        tokens_a = canonical_tokens("dan simmons hyperion")
        tokens_b = canonical_tokens("hyperion dan simmons")
        self.assertEqual(tokens_a, tokens_b)

    def test_extract_episode(self):
        self.assertEqual(extract_episode("Show.S01E08.720p.mkv"), (1, 8))
        self.assertEqual(extract_episode("Show.1x05.mkv"), (1, 5))
        self.assertIsNone(extract_episode("Movie.Title.2020.mkv"))

    def test_scan_and_exact_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            content = b"Exact duplicate content" * 1000
            file_a = root / "file_a.mkv"
            file_b = root / "file_b.mkv"
            file_c = root / "file_c.mkv"

            file_a.write_bytes(content)
            file_b.write_bytes(content)
            file_c.write_bytes(b"Different content")

            entries = scan_files(root)
            self.assertEqual(len(entries), 3)

            exact_dups = find_exact_duplicates(entries, max_workers=2)
            self.assertEqual(len(exact_dups), 1)

            group = list(exact_dups.values())[0]
            paths = {e.path for e in group}
            self.assertIn(file_a, paths)
            self.assertIn(file_b, paths)
            self.assertNotIn(file_c, paths)

    def test_cross_format_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epub = root / "Hyperion - Dan Simmons.epub"
            azw3 = root / "Hyperion - Dan Simmons.azw3"
            epub.write_bytes(b"epub data")
            azw3.write_bytes(b"azw3 data")

            entries = scan_files(root)
            exact_paths = set()
            cross_dups = find_cross_format_duplicates(entries, exact_paths)
            self.assertEqual(len(cross_dups), 1)
            domain, title, keep_f, review_list = cross_dups[0]
            self.assertEqual(domain, "ebooks")
            self.assertEqual(keep_f.path, epub)  # epub is preferred
            self.assertEqual(review_list[0].path, azw3)

    def test_vobsub_subtitles_not_marked_duplicate(self):
        # .sub and .idx are companions, not duplicates
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "movie.sub"
            idx = root / "movie.idx"
            sub.write_bytes(b"sub")
            idx.write_bytes(b"idx")

            entries = scan_files(root)
            cross_dups = find_cross_format_duplicates(entries, set())
            self.assertEqual(len(cross_dups), 0)

    def test_fuzzy_similar_episodes_separated(self):
        # S01E01 and S01E02 must NOT match as duplicates
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ep1 = root / "Long.Show.Title.Name.S01E01.720p.mkv"
            ep2 = root / "Long.Show.Title.Name.S01E02.720p.mkv"
            ep1.write_bytes(b"ep1")
            ep2.write_bytes(b"ep2")

            entries = scan_files(root)
            fuzzy = find_fuzzy_similar_titles(entries, set(), set(), threshold=0.85)
            self.assertEqual(len(fuzzy), 0)

    def test_mangled_and_incomplete_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            valid = root / "video.mkv"
            mangled = root / "video"
            incomplete = root / "video.mkv.filepart"

            valid.write_bytes(b"valid")
            mangled.write_bytes(b"mangled")
            incomplete.write_bytes(b"part")

            entries = scan_files(root)
            mangled_files = find_mangled_and_incomplete_files(entries, set())
            self.assertEqual(len(mangled_files), 2)

    def test_generate_cleanup_script_is_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script_out = root / "cleanup.sh"
            entry_keep = FileEntry(path=root / "keep.mkv", size=1000, mtime=100)
            entry_dup = FileEntry(path=root / "dup.mkv", size=1000, mtime=200)

            generate_cleanup_script(
                exact_duplicates={"dummy_hash": [entry_keep, entry_dup]},
                cross_format=[],
                fuzzy_matches=[],
                mangled_files=[],
                script_path=script_out,
                root_dir=root,
            )

            self.assertTrue(script_out.exists())
            content = script_out.read_text()
            self.assertIn("# rm -v --", content)
            self.assertNotIn("\nrm -v", content)


if __name__ == "__main__":
    unittest.main()
