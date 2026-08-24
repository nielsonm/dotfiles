from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import hashlib
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from typing import NamedTuple

# ----------------- CONFIGURATION & EXTENSION PRESETS ----------------- #

# Default basic exclusions
DEFAULT_EXCLUDE_EXTENSIONS = (".js", ".json", ".sql")

# Default name / directory patterns to exclude (case-insensitive substring)
DEFAULT_EXCLUDE_PATTERNS = ("antigravity",)

# Default system / metadata directory names to prune immediately
DEFAULT_EXCLUDE_DIR_NAMES = (
    "$recycle.bin",
    "system volume information",
    ".trashes",
    ".fseventsd",
    "__pycache__",
    ".git",
    "node_modules",
)

# Standard media file extensions (Video, Audio, Images, Subtitles)
MEDIA_EXTENSIONS = (
    # Video
    ".avi", ".flv", ".m2ts", ".m4v", ".mkv", ".mov", ".mp4", ".ts", ".vob", ".webm", ".wmv",
    # Audio
    ".aac", ".aiff", ".alac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".wma",
    # Images
    ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".tiff", ".webp",
    # Subtitles
    ".ass", ".idx", ".ssa", ".srt", ".sub", ".vtt",
    # Ebooks
    ".azw", ".epub", ".mobi",
)

# Comprehensive non-media file exclusions
NON_MEDIA_EXCLUDE_EXTENSIONS = (
    # Code & Scripts
    ".bat", ".c", ".cpp", ".css", ".h", ".html", ".java", ".js", ".php", ".ps1", ".py", ".sh",
    ".ts", ".vb", ".xml", ".xsl", ".yaml", ".yml", ".pak",
    # Data & Config
    ".cfg", ".conf", ".csv", ".db", ".env", ".ini", ".json", ".sql", ".sqlite", ".toml",
    ".tsv",
    # Documents & Text
    ".doc", ".docx", ".md", ".pdf", ".ppt", ".pptx", ".rtf", ".txt", ".xls", ".xlsx", ".odt",
    ".ods", ".odp", ".pages",
    # Archives & Binaries & Logs
    ".7z", ".bak", ".bin", ".bz2", ".dll", ".exe", ".gz", ".iso", ".log", ".msi", ".rar", ".so",
    ".tar", ".tmp", ".zip", ".xz", ".deb", ".pkg", ".rpm", ".dmg", ".appimage",
)

BUFFER_SIZE = 4 * 1024 * 1024  # 4 MB read buffer for network shares
SAMPLE_CHUNK_SIZE = 1024 * 1024  # 1 MB chunk for sample hashing


class FileInfo(NamedTuple):
    size: int
    mtime: float


def _normalize_extensions(extensions: set[str] | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if not extensions:
        return ()
    return tuple(sorted({
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in extensions
    }))


def _normalize_patterns(patterns: set[str] | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if not patterns:
        return ()
    return tuple(sorted({
        p.lower().strip()
        for p in patterns
        if p and p.strip()
    }))


# ----------------- HASHING WORKERS ----------------- #

def _sample_hash_worker(file_path_str: str, root_str: str) -> tuple[str, str]:
    """Fast 3-point sample hash (head, middle, tail) + file size."""
    file_path = Path(file_path_str)
    root = Path(root_str)
    rel_path = file_path.relative_to(root).as_posix()

    hasher = hashlib.sha256()
    stat_res = file_path.stat()
    file_size = stat_res.st_size
    hasher.update(str(file_size).encode("ascii"))

    with open(file_path, "rb") as f:
        if file_size <= SAMPLE_CHUNK_SIZE * 3:
            while chunk := f.read(BUFFER_SIZE):
                hasher.update(chunk)
        else:
            # 1. Head (first 1 MB)
            hasher.update(f.read(SAMPLE_CHUNK_SIZE))
            # 2. Middle (1 MB)
            f.seek((file_size - SAMPLE_CHUNK_SIZE) // 2)
            hasher.update(f.read(SAMPLE_CHUNK_SIZE))
            # 3. Tail (last 1 MB)
            f.seek(file_size - SAMPLE_CHUNK_SIZE)
            hasher.update(f.read(SAMPLE_CHUNK_SIZE))

    return rel_path, hasher.hexdigest()


def _full_hash_worker(file_path_str: str, root_str: str) -> tuple[str, str]:
    """Full-file SHA-256 hash using 4 MB chunks."""
    file_path = Path(file_path_str)
    root = Path(root_str)
    rel_path = file_path.relative_to(root).as_posix()

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(BUFFER_SIZE):
            hasher.update(chunk)

    return rel_path, hasher.hexdigest()


def hash_candidates_parallel(
    root: Path,
    rel_paths: list[str],
    mode: str = "sample_hash",
    max_workers: int = 6
) -> dict[str, str]:
    if not rel_paths:
        return {}

    root_str = str(root)
    full_paths = [str(root / p) for p in rel_paths]
    worker_fn = _sample_hash_worker if mode == "sample_hash" else _full_hash_worker
    results = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker_fn, f, root_str) for f in full_paths]
        for fut in as_completed(futures):
            rel, file_hash = fut.result()
            results[rel] = file_hash

    return results


def probe_metadata(
    directory_root: Path,
    rel_paths: set[str] | list[str],
    max_workers: int = 16,
) -> dict[str, FileInfo]:
    """Fast directory-batched metadata query:
    Groups candidate paths by their parent directory and scans each parent once via scandir.
    This replaces hundreds of individual network stat() roundtrips with a handful of single-roundtrip directory listings.
    """
    if not rel_paths:
        return {}

    root = Path(directory_root)
    files_by_parent: dict[str, set[str]] = {}
    for rel in rel_paths:
        parent = str(Path(rel).parent.as_posix())
        if parent == ".":
            parent = ""
        files_by_parent.setdefault(parent, set()).add(rel)

    index: dict[str, FileInfo] = {}
    lock = threading.Lock()

    def _scan_parent(parent_rel: str) -> None:
        parent_full = (root / parent_rel) if parent_rel else root
        if not parent_full.exists() or not parent_full.is_dir():
            return

        expected_rel_set = files_by_parent[parent_rel]
        found = {}
        try:
            with os.scandir(parent_full) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        rel = f"{parent_rel}/{entry.name}" if parent_rel else entry.name
                        if rel in expected_rel_set:
                            try:
                                st = entry.stat()
                                found[rel] = FileInfo(size=st.st_size, mtime=st.st_mtime)
                            except (OSError, PermissionError):
                                pass
        except (PermissionError, OSError):
            pass

        if found:
            with lock:
                index.update(found)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(_scan_parent, files_by_parent.keys()))

    return index


def scan_metadata(
    directory_root: Path,
    include_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_patterns: set[str] | tuple[str, ...] | list[str] | None = None,
    max_workers: int = 16,
) -> dict[str, FileInfo]:
    if exclude_extensions is None:
        exclude_extensions = DEFAULT_EXCLUDE_EXTENSIONS
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

    normalized_includes = _normalize_extensions(include_extensions)
    normalized_excludes = _normalize_extensions(exclude_extensions)
    normalized_patterns = _normalize_patterns(exclude_patterns)

    index: dict[str, FileInfo] = {}
    root_str = str(directory_root)
    lock = threading.Lock()

    def _scan_single_dir(current_path: str) -> list[str]:
        subdirs = []
        local_entries = []
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    entry_lower = entry.name.lower()
                    if entry_lower in DEFAULT_EXCLUDE_DIR_NAMES:
                        continue
                    if normalized_patterns and any(pat in entry_lower for pat in normalized_patterns):
                        continue

                    if entry.is_file(follow_symlinks=False):
                        if normalized_includes and not entry_lower.endswith(normalized_includes):
                            continue
                        if normalized_excludes and entry_lower.endswith(normalized_excludes):
                            continue
                        rel = os.path.relpath(entry.path, root_str).replace("\\", "/")
                        if normalized_patterns and any(pat in rel.lower() for pat in normalized_patterns):
                            continue
                        try:
                            stat_res = entry.stat()
                            local_entries.append((rel, FileInfo(size=stat_res.st_size, mtime=stat_res.st_mtime)))
                        except (OSError, PermissionError):
                            continue
                    elif entry.is_dir(follow_symlinks=False):
                        subdirs.append(entry.path)
        except (PermissionError, OSError):
            pass

        if local_entries:
            with lock:
                for rel, info in local_entries:
                    index[rel] = info

        return subdirs

    # Parallel directory walking
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scan_single_dir, root_str)}
        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for fut in done:
                futures.remove(fut)
                try:
                    new_subdirs = fut.result()
                    for sd in new_subdirs:
                        futures.add(executor.submit(_scan_single_dir, sd))
                except Exception:
                    pass

    return index


# ----------------- CLI COMMAND GENERATOR ----------------- #

def print_cli_command(
    src: Path,
    dst: Path,
    mirror: bool = False,
    compare_mode: str = "mtime_size",
    include_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_patterns: set[str] | tuple[str, ...] | list[str] | None = None,
):
    """Generates optimal OS-level sync commands."""
    if exclude_extensions is None:
        exclude_extensions = DEFAULT_EXCLUDE_EXTENSIONS
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

    normalized_includes = _normalize_extensions(include_extensions)
    normalized_excludes = _normalize_extensions(exclude_extensions)
    normalized_patterns = _normalize_patterns(exclude_patterns)

    # Linux / macOS (rsync)
    delete_flag = " --delete" if mirror else ""
    src_str = str(src).rstrip("/") + "/"
    dst_str = str(dst).rstrip("/") + "/"

    rsync_filters = []
    for pat in normalized_patterns:
        rsync_filters.append(f"--exclude=\"*{pat}*\"")

    if normalized_includes:
        rsync_filters.append("--include=\"*/\"")
        for ext in normalized_includes:
            rsync_filters.append(f"--include=\"*{ext}\"")
        rsync_filters.append("--exclude=\"*\"")
    elif normalized_excludes:
        for ext in normalized_excludes:
            rsync_filters.append(f"--exclude=\"*{ext}\"")

    rsync_mode_flag = ""
    if compare_mode == "full_hash":
        rsync_mode_flag = " -c"
    elif compare_mode == "size_only":
        rsync_mode_flag = " --size-only"

    rsync_args = (" " + " ".join(rsync_filters)) if rsync_filters else ""

    # Windows (Robocopy)
    purge_flag = " /PURGE" if mirror else ""
    robocopy_files = (" " + " ".join(f"*{ext}" for ext in normalized_includes)) if normalized_includes else ""

    robocopy_xd = [f"*{pat}*" for pat in normalized_patterns] + [f"*{d}*" for d in DEFAULT_EXCLUDE_DIR_NAMES]
    robocopy_xf = [f"*{ext}" for ext in normalized_excludes] + [f"*{pat}*" for pat in normalized_patterns]

    robocopy_xd_str = (" /XD " + " ".join(robocopy_xd)) if robocopy_xd else ""
    robocopy_xf_str = (" /XF " + " ".join(robocopy_xf)) if robocopy_xf else ""

    print("\n" + "=" * 60)
    print("NATIVE CLI COMMAND EQUIVALENTS:")
    print("=" * 60)
    print("POSIX / Linux (rsync):")
    print(f"  rsync -avh --progress{delete_flag}{rsync_mode_flag}{rsync_args} \"{src_str}\" \"{dst_str}\"")
    print("\nWindows (Robocopy):")
    print(f"  robocopy \"{src}\" \"{dst}\"{robocopy_files} /E /Z /FFT /R:2 /W:3{purge_flag}{robocopy_xd_str}{robocopy_xf_str}")
    print("=" * 60)


# ----------------- COMPARISON & SYNC ENGINE ----------------- #

def sync_directories(
    src_dir: str,
    dst_dir: str,
    direction: str = "push",            # "push" (Local -> CIFS) or "pull" (CIFS -> Local)
    compare_mode: str = "mtime_size",   # "mtime_size" (instant), "sample_hash" (fast), "full_hash" (slow), "size_only"
    mtime_tolerance: float = 2.0,       # Timestamp tolerance in seconds (handles FAT/NTFS/CIFS rounding)
    sync: bool = False,                 # Perform real file operations
    dry_run: bool = True,               # If True, prints actions without executing
    delete_orphan_dst: bool = False,    # Mirror mode: deletes files in destination not in source
    include_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_patterns: set[str] | tuple[str, ...] | list[str] | None = None,
):
    source_root = Path(src_dir).resolve()
    target_root = Path(dst_dir).resolve()

    if direction == "pull":
        source_root, target_root = target_root, source_root

    t_start = time.perf_counter()
    print(f"[*] Direction: {source_root}  ==>  {target_root}")
    print(f"[*] Compare Mode: {compare_mode}")
    print(f"[*] Scanning source metadata...")

    t0 = time.perf_counter()
    src_meta = scan_metadata(
        source_root,
        include_extensions=include_extensions,
        exclude_extensions=exclude_extensions,
        exclude_patterns=exclude_patterns,
    )
    src_keys = set(src_meta.keys())
    t_src = time.perf_counter() - t0
    print(f"[*] Source scan completed in {t_src:.2f}s (found {len(src_keys)} files).")

    # Fast targeted probe when not mirroring
    t0 = time.perf_counter()
    if direction == "push" and not delete_orphan_dst:
        print(f"[*] Probing target metadata for {len(src_keys)} candidate files...")
        dst_meta = probe_metadata(target_root, src_keys)
    else:
        print(f"[*] Scanning target directory tree...")
        dst_meta = scan_metadata(
            target_root,
            include_extensions=include_extensions,
            exclude_extensions=exclude_extensions,
            exclude_patterns=exclude_patterns,
        )
    t_dst = time.perf_counter() - t0
    print(f"[*] Target scan/probe completed in {t_dst:.2f}s.")

    src_keys = set(src_meta.keys())
    dst_keys = set(dst_meta.keys())

    to_copy_missing = sorted(src_keys - dst_keys)
    orphans_in_dst = sorted(dst_keys - src_keys)
    common_files = src_keys & dst_keys

    # Check for size mismatches
    size_mismatches = []
    same_size_candidates = []

    for f in common_files:
        if src_meta[f].size != dst_meta[f].size:
            size_mismatches.append(f)
        else:
            same_size_candidates.append(f)

    # Detect updates based on compare_mode
    to_update = []
    if compare_mode == "size_only":
        to_update = sorted(size_mismatches)
    elif compare_mode == "mtime_size":
        mtime_mismatches = [
            f for f in same_size_candidates
            if abs(src_meta[f].mtime - dst_meta[f].mtime) > mtime_tolerance
        ]
        to_update = sorted(size_mismatches + mtime_mismatches)
    elif compare_mode in ("sample_hash", "full_hash"):
        print(f"[*] Verifying checksums ({compare_mode}) on {len(same_size_candidates)} matching files...")
        src_hashes = hash_candidates_parallel(source_root, same_size_candidates, mode=compare_mode)
        dst_hashes = hash_candidates_parallel(target_root, same_size_candidates, mode=compare_mode, max_workers=4)
        hash_mismatches = [
            f for f in same_size_candidates
            if src_hashes.get(f) != dst_hashes.get(f)
        ]
        to_update = sorted(size_mismatches + hash_mismatches)
    else:
        raise ValueError(f"Unknown compare_mode: {compare_mode}. Choose from 'mtime_size', 'sample_hash', 'full_hash', 'size_only'")

    # ----------------- EXECUTION PLAN REPORT ----------------- #
    print("\n" + "=" * 60)
    print("CHANGES DETECTED:")
    print(f"  Missing on Target (To Create) : {len(to_copy_missing)}")
    print(f"  Modified on Source (To Update): {len(to_update)}")
    print(f"  Extra on Target (Orphans)     : {len(orphans_in_dst)}")
    print(f"  Total Comparison Time         : {time.perf_counter() - t_start:.2f}s")
    print("=" * 60)

    total_ops = len(to_copy_missing) + len(to_update)
    if delete_orphan_dst:
        total_ops += len(orphans_in_dst)

    if total_ops == 0:
        print("[+] Directories are perfectly synchronized. No action required.")
        return

    # ----------------- EXECUTION ----------------- #
    action_label = "[DRY-RUN]" if (dry_run or not sync) else "[EXECUTING]"

    # 1. Copy Missing & Modified Files
    all_transfers = [(f, "CREATE") for f in to_copy_missing] + [(f, "UPDATE") for f in to_update]
    for rel_path, action in all_transfers:
        s_file = source_root / rel_path
        d_file = target_root / rel_path
        print(f"  {action_label} {action}: {rel_path}")

        if sync and not dry_run:
            d_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s_file, d_file)  # copy2 preserves timestamps and metadata

    # 2. Handle Extra Files in Destination (Mirroring)
    if delete_orphan_dst:
        for rel_path in orphans_in_dst:
            d_file = target_root / rel_path
            print(f"  {action_label} DELETE: {rel_path}")

            if sync and not dry_run:
                if d_file.is_file():
                    d_file.unlink()

    if not sync or dry_run:
        print(f"\n[!] Dry run complete. Pass `sync=True, dry_run=False` to execute these changes.")


# ----------------- ENTRY POINT ----------------- #

if __name__ == "__main__":
    LOCAL_PATH = "/home/mike/Downloads/"       # e.g., "C:/LocalProject"
    CIFS_MOUNT = "/run/user/1000/gvfs/smb-share:server=192.168.86.210,share=f"     # e.g., "Z:/RemoteProject"

    # Step 1: Print Native OS Commands (Optional)
    print_cli_command(
        Path(LOCAL_PATH),
        Path(CIFS_MOUNT),
        mirror=False,
        compare_mode="mtime_size",
        include_extensions=MEDIA_EXTENSIONS,
    )

    # Step 2: Compare & Sync via Python
    sync_directories(
        src_dir=LOCAL_PATH,
        dst_dir=CIFS_MOUNT,
        direction="push",          # "push" sends Local -> CIFS
        compare_mode="mtime_size", # "mtime_size" (instant), "sample_hash" (fast), "full_hash" (slow), "size_only"
        include_extensions=MEDIA_EXTENSIONS,
        sync=False,                # Set to True to apply changes
        dry_run=True,              # Set to False to disable preview safety
        delete_orphan_dst=False    # Set to True to delete remote files not on local
    )