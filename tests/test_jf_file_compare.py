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

    def test_sync_directories_real_copy_and_delete_execution(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)

            (src / "new_video.mp4").write_text("fresh video content")
            (dst / "old_orphan.mp4").write_text("old orphan file")

            # Execute real sync with orphan deletion
            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=str(src),
                    dst_dir=str(dst),
                    direction="push",
                    compare_mode="mtime_size",
                    include_extensions=[".mp4"],
                    sync=True,
                    dry_run=False,
                    delete_orphan_dst=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("[EXECUTING] CREATE: new_video.mp4", output)
            self.assertIn("[EXECUTING] DELETE: old_orphan.mp4", output)
            self.assertTrue((dst / "new_video.mp4").exists())
            self.assertFalse((dst / "old_orphan.mp4").exists())

    def test_sync_directories_pull_direction(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)

            (dst / "remote.mp4").write_text("remote content")

            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=str(src),
                    dst_dir=str(dst),
                    direction="pull",
                    compare_mode="size_only",
                    include_extensions=[".mp4"],
                    sync=False,
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("[DRY-RUN] CREATE: remote.mp4", output)

    def test_sync_directories_invalid_compare_mode(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            with self.assertRaises(ValueError):
                sync_directories(
                    src_dir=src_dir,
                    dst_dir=dst_dir,
                    compare_mode="unsupported_mode",
                )

    def test_sync_directories_multiple_destinations_rel_path_match(self):
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as lib1_dir, \
             tempfile.TemporaryDirectory() as lib2_dir:
            src = Path(src_dir)
            lib1 = Path(lib1_dir)
            lib2 = Path(lib2_dir)

            (src / "movie1.mp4").write_text("movie 1 content")
            (src / "movie2.mp4").write_text("movie 2 content")
            (lib1 / "movie1.mp4").write_text("movie 1 content")
            (lib2 / "movie2.mp4").write_text("movie 2 content")

            now = time.time()
            for p in (src / "movie1.mp4", src / "movie2.mp4", lib1 / "movie1.mp4", lib2 / "movie2.mp4"):
                os.utime(p, (now, now))

            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=src,
                    dst_dirs=[lib1, lib2],
                    compare_mode="mtime_size",
                    include_extensions=[".mp4"],
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("Directories are perfectly synchronized", output)

    def test_sync_directories_multiple_destinations_filename_fallback(self):
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as movies_dir, \
             tempfile.TemporaryDirectory() as tv_dir:
            src = Path(src_dir)
            movies = Path(movies_dir)
            tv = Path(tv_dir)

            # In src, flat file
            (src / "Inception.mkv").write_text("film data")
            # In library, nested in subfolder
            movie_sub = movies / "Inception (2010)"
            movie_sub.mkdir()
            (movie_sub / "Inception.mkv").write_text("film data")

            now = time.time()
            os.utime(src / "Inception.mkv", (now, now))
            os.utime(movie_sub / "Inception.mkv", (now, now))

            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=src,
                    dst_dirs=[movies, tv],
                    compare_mode="mtime_size",
                    match_by_filename=True,
                    include_extensions=[".mkv"],
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("Directories are perfectly synchronized", output)

    def test_sync_directories_multiple_destinations_missing_and_modified(self):
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as lib1_dir, \
             tempfile.TemporaryDirectory() as lib2_dir:
            src = Path(src_dir)
            lib1 = Path(lib1_dir)
            lib2 = Path(lib2_dir)

            (src / "exists_in_lib1.mp4").write_text("lib1 version new")
            (lib1 / "exists_in_lib1.mp4").write_text("lib1 version old different size")

            (src / "exists_in_lib2.mp4").write_text("lib2 exact")
            (lib2 / "exists_in_lib2.mp4").write_text("lib2 exact")

            (src / "completely_missing.mp4").write_text("brand new")

            now = time.time()
            os.utime(src / "exists_in_lib2.mp4", (now, now))
            os.utime(lib2 / "exists_in_lib2.mp4", (now, now))

            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=src,
                    dst_dirs=[lib1, lib2],
                    compare_mode="size_only",
                    include_extensions=[".mp4"],
                    dry_run=True,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("Missing on Target (To Create) : 1", output)
            self.assertIn("Modified on Source (To Update): 1", output)
            self.assertIn("[DRY-RUN] CREATE: completely_missing.mp4", output)
            self.assertIn("[DRY-RUN] UPDATE: exists_in_lib1.mp4", output)

    def test_print_cli_command_multiple_destinations(self):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            print_cli_command(
                Path("/tmp/src"),
                [Path("/tmp/movies"), Path("/tmp/tv")],
                include_extensions=[".mp4"],
            )
        finally:
            sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn('--- Destination: /tmp/movies ---', output)
        self.assertIn('--- Destination: /tmp/tv ---', output)
        self.assertIn('rsync -avh --progress --exclude="*antigravity*" --include="*/" --include="*.mp4" --exclude="*" "/tmp/src/" "/tmp/movies/"', output)
        self.assertIn('rsync -avh --progress --exclude="*antigravity*" --include="*/" --include="*.mp4" --exclude="*" "/tmp/src/" "/tmp/tv/"', output)

    def test_sync_directories_copy_new_only(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)

            # Modified file: same name, different content
            (src / "existing.mp4").write_text("updated content in source")
            (dst / "existing.mp4").write_text("old content in dst")

            # Brand new file: only in src
            (src / "brand_new.mp4").write_text("brand new file")

            captured_output = io.StringIO()
            sys.stdout = captured_output
            try:
                sync_directories(
                    src_dir=src,
                    dst_dir=dst,
                    compare_mode="mtime_size",
                    copy_new_only=True,
                    include_extensions=[".mp4"],
                    sync=True,
                    dry_run=False,
                )
            finally:
                sys.stdout = sys.__stdout__

            output = captured_output.getvalue()
            self.assertIn("Missing on Target (To Create) : 1", output)
            self.assertIn("Modified on Source (To Update): 0", output)
            self.assertIn("[EXECUTING] CREATE: brand_new.mp4", output)
            self.assertNotIn("UPDATE:", output)

            # Verify brand new was copied, existing was untouched
            self.assertEqual((dst / "brand_new.mp4").read_text(), "brand new file")
            self.assertEqual((dst / "existing.mp4").read_text(), "old content in dst")

    def test_print_cli_command_copy_new_only(self):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            print_cli_command(
                Path("/tmp/src"),
                Path("/tmp/dst"),
                copy_new_only=True,
            )
        finally:
            sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn("--ignore-existing", output)
        self.assertIn("/XC /XN /XO", output)


if __name__ == "__main__":
    unittest.main()
