import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from jfFileCompare import (
    DEFAULT_EXCLUDE_EXTENSIONS,
    DEFAULT_EXCLUDE_PATTERNS,
    MEDIA_EXTENSIONS,
    NON_MEDIA_EXCLUDE_EXTENSIONS,
    FileInfo,
    probe_metadata,
    scan_metadata,
    print_cli_command,
    sync_directories,
)


class TestJfFileCompare(unittest.TestCase):
    def test_probe_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "file1.mp4").write_text("12345")
            sub = root / "sub"
            sub.mkdir()
            (sub / "file2.mkv").write_text("1234567890")

            meta = probe_metadata(root, ["file1.mp4", "sub/file2.mkv", "nonexistent.mp4"])
            self.assertIn("file1.mp4", meta)
            self.assertIn("sub/file2.mkv", meta)
            self.assertNotIn("nonexistent.mp4", meta)
            self.assertEqual(meta["file1.mp4"].size, 5)
            self.assertEqual(meta["sub/file2.mkv"].size, 10)

    def test_presets(self):
        self.assertIn(".js", DEFAULT_EXCLUDE_EXTENSIONS)
        self.assertIn(".json", DEFAULT_EXCLUDE_EXTENSIONS)
        self.assertIn(".sql", DEFAULT_EXCLUDE_EXTENSIONS)

        self.assertIn("antigravity", DEFAULT_EXCLUDE_PATTERNS)

        self.assertIn(".mp4", MEDIA_EXTENSIONS)
        self.assertIn(".mkv", MEDIA_EXTENSIONS)
        self.assertIn(".mp3", MEDIA_EXTENSIONS)
        self.assertIn(".flac", MEDIA_EXTENSIONS)
        self.assertIn(".jpg", MEDIA_EXTENSIONS)
        self.assertIn(".srt", MEDIA_EXTENSIONS)

        self.assertIn(".txt", NON_MEDIA_EXCLUDE_EXTENSIONS)
        self.assertIn(".pdf", NON_MEDIA_EXCLUDE_EXTENSIONS)
        self.assertIn(".zip", NON_MEDIA_EXCLUDE_EXTENSIONS)
        self.assertIn(".exe", NON_MEDIA_EXCLUDE_EXTENSIONS)

    def test_scan_metadata_excludes_by_default(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')")
            (root / "bundle.js").write_text("console.log('test')")
            (root / "config.json").write_text('{"key": "val"}')
            (root / "dump.sql").write_text("SELECT 1;")
            (root / "script.JS").write_text("console.log('upper')")
            (root / "data.JSON").write_text('{"a": 1}')
            (root / "schema.SQL").write_text("CREATE TABLE t;")

            subdir = root / "sub"
            subdir.mkdir()
            (subdir / "nested.txt").write_text("text")
            (subdir / "nested.js").write_text("code")

            meta = scan_metadata(root)

            self.assertIn("app.py", meta)
            self.assertIsInstance(meta["app.py"], FileInfo)
            self.assertIn("sub/nested.txt", meta)
            self.assertNotIn("bundle.js", meta)
            self.assertNotIn("config.json", meta)
            self.assertNotIn("dump.sql", meta)
            self.assertNotIn("script.JS", meta)
            self.assertNotIn("data.JSON", meta)
            self.assertNotIn("schema.SQL", meta)
            self.assertNotIn("sub/nested.js", meta)

    def test_scan_metadata_excludes_antigravity(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ag_dir = root / "Antigravity" / "Antigravity-x64"
            ag_dir.mkdir(parents=True)
            (ag_dir / "v8_context_snapshot.bin").write_text("bin data")
            (ag_dir / "antigravity.exe").write_text("exe data")
            (root / "normal_file.txt").write_text("text")

            meta = scan_metadata(root)

            self.assertIn("normal_file.txt", meta)
            self.assertNotIn("Antigravity/Antigravity-x64/v8_context_snapshot.bin", meta)
            self.assertNotIn("Antigravity/Antigravity-x64/antigravity.exe", meta)

    def test_scan_metadata_include_media_only(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "movie.mkv").write_text("video")
            (root / "song.mp3").write_text("audio")
            (root / "cover.JPG").write_text("image")
            (root / "subs.srt").write_text("subtitle")
            (root / "notes.txt").write_text("text")
            (root / "config.json").write_text("{}")
            (root / "script.py").write_text("py")

            ag_dir = root / "Antigravity"
            ag_dir.mkdir()
            (ag_dir / "trailer.mp4").write_text("media inside antigravity")

            meta = scan_metadata(root, include_extensions=MEDIA_EXTENSIONS)

            self.assertIn("movie.mkv", meta)
            self.assertIn("song.mp3", meta)
            self.assertIn("cover.JPG", meta)
            self.assertIn("subs.srt", meta)
            self.assertNotIn("notes.txt", meta)
            self.assertNotIn("config.json", meta)
            self.assertNotIn("script.py", meta)
            self.assertNotIn("Antigravity/trailer.mp4", meta)

    def test_scan_metadata_both_include_and_exclude(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "movie.mp4").write_text("video")
            (root / "sample.mp4").write_text("sample video")
            (root / "cover.jpg").write_text("image")
            (root / "notes.txt").write_text("text")

            # Include media, but exclude .jpg
            meta = scan_metadata(
                root,
                include_extensions=[".mp4", ".jpg"],
                exclude_extensions=[".jpg"],
            )

            self.assertIn("movie.mp4", meta)
            self.assertIn("sample.mp4", meta)
            self.assertNotIn("cover.jpg", meta)
            self.assertNotIn("notes.txt", meta)

    def test_scan_metadata_non_media_exclude_preset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "movie.mkv").write_text("video")
            (root / "readme.txt").write_text("readme")
            (root / "archive.zip").write_text("zip")
            (root / "doc.pdf").write_text("pdf")

            meta = scan_metadata(root, exclude_extensions=NON_MEDIA_EXCLUDE_EXTENSIONS)

            self.assertIn("movie.mkv", meta)
            self.assertNotIn("readme.txt", meta)
            self.assertNotIn("archive.zip", meta)
            self.assertNotIn("doc.pdf", meta)

    def test_print_cli_command_includes_excludes(self):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            print_cli_command(Path("/tmp/src"), Path("/tmp/dst"))
        finally:
            sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn('--exclude="*antigravity*"', output)
        self.assertIn('--exclude="*.js"', output)
        self.assertIn('--exclude="*.json"', output)
        self.assertIn('--exclude="*.sql"', output)
        self.assertIn('/XD *antigravity*', output)
        self.assertIn('/XF *.js *.json *.sql *antigravity*', output)

    def test_print_cli_command_include_filter(self):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            print_cli_command(
                Path("/tmp/src"),
                Path("/tmp/dst"),
                include_extensions=[".mp4", ".mkv"],
                compare_mode="full_hash",
            )
        finally:
            sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn('--exclude="*antigravity*"', output)
        self.assertIn('--include="*/"', output)
        self.assertIn('--include="*.mkv"', output)
        self.assertIn('--include="*.mp4"', output)
        self.assertIn('--exclude="*"', output)
        self.assertIn(' -c', output)
        self.assertIn('robocopy "/tmp/src" "/tmp/dst" *.mkv *.mp4', output)

    def test_sync_directories_mtime_size_mode(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)

            (src / "video.mp4").write_text("video content")
            (dst / "video.mp4").write_text("video content")

            # Same size and identical mtime -> no changes
            now = time.time()
            os.utime(src / "video.mp4", (now, now))
            os.utime(dst / "video.mp4", (now, now))

            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=str(src),
                    dst_dir=str(dst),
                    direction="push",
                    compare_mode="mtime_size",
                    include_extensions=[".mp4"],
                    sync=False,
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("Directories are perfectly synchronized", output)

            # Change mtime on source by 10 seconds -> detected as to update
            os.utime(src / "video.mp4", (now + 10, now + 10))
            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=str(src),
                    dst_dir=str(dst),
                    direction="push",
                    compare_mode="mtime_size",
                    include_extensions=[".mp4"],
                    sync=False,
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("[DRY-RUN] UPDATE: video.mp4", output)

    def test_sync_directories_sample_and_full_hash_modes(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)

            # Same size, different content
            (src / "sample.mp4").write_text("AAAA" * 1000)
            (dst / "sample.mp4").write_text("BBBB" * 1000)

            # Sample hash
            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=str(src),
                    dst_dir=str(dst),
                    compare_mode="sample_hash",
                    include_extensions=[".mp4"],
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            self.assertIn("[DRY-RUN] UPDATE: sample.mp4", captured_output.getvalue())

            # Full hash
            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=str(src),
                    dst_dir=str(dst),
                    compare_mode="full_hash",
                    include_extensions=[".mp4"],
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            self.assertIn("[DRY-RUN] UPDATE: sample.mp4", captured_output.getvalue())

    def test_sync_directories_size_only_mode(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)

            # Same size, different content and different mtime
            (src / "same_size.mp4").write_text("12345")
            (dst / "same_size.mp4").write_text("abcde")

            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=str(src),
                    dst_dir=str(dst),
                    compare_mode="size_only",
                    include_extensions=[".mp4"],
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("Directories are perfectly synchronized", output)


if __name__ == "__main__":
    unittest.main()
