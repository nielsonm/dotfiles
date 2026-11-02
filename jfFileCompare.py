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
    # ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".tiff", ".webp",
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
    src: Path | str,
    dst: Path | str | list[Path | str] | tuple[Path | str, ...],
    mirror: bool = False,
    compare_mode: str = "mtime_size",
    include_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_patterns: set[str] | tuple[str, ...] | list[str] | None = None,
    copy_new_only: bool = False,
):
    """Generates optimal OS-level sync commands."""
    if isinstance(dst, (list, tuple)):
        dst_list = [Path(d) for d in dst]
    else:
        dst_list = [Path(dst)]

    src_path = Path(src)

    if exclude_extensions is None:
        exclude_extensions = DEFAULT_EXCLUDE_EXTENSIONS
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

    normalized_includes = _normalize_extensions(include_extensions)
    normalized_excludes = _normalize_extensions(exclude_extensions)
    normalized_patterns = _normalize_patterns(exclude_patterns)

    # Linux / macOS (rsync)
    delete_flag = " --delete" if mirror else ""
    ignore_existing_flag = " --ignore-existing" if copy_new_only else ""
    src_str = str(src_path).rstrip("/") + "/"

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
    new_only_flag = " /XC /XN /XO" if copy_new_only else ""
    robocopy_files = (" " + " ".join(f"*{ext}" for ext in normalized_includes)) if normalized_includes else ""

    robocopy_xd = [f"*{pat}*" for pat in normalized_patterns] + [f"*{d}*" for d in DEFAULT_EXCLUDE_DIR_NAMES]
    robocopy_xf = [f"*{ext}" for ext in normalized_excludes] + [f"*{pat}*" for pat in normalized_patterns]

    robocopy_xd_str = (" /XD " + " ".join(robocopy_xd)) if robocopy_xd else ""
    robocopy_xf_str = (" /XF " + " ".join(robocopy_xf)) if robocopy_xf else ""

    print("\n" + "=" * 60)
    print("NATIVE CLI COMMAND EQUIVALENTS:")
    print("=" * 60)
    for target_dst in dst_list:
        dst_str = str(target_dst).rstrip("/") + "/"
        if len(dst_list) > 1:
            print(f"\n--- Destination: {target_dst} ---")
        print("POSIX / Linux (rsync):")
        print(f"  rsync -avh --progress{delete_flag}{rsync_mode_flag}{ignore_existing_flag}{rsync_args} \"{src_str}\" \"{dst_str}\"")
        print("\nWindows (Robocopy):")
        print(f"  robocopy \"{src_path}\" \"{target_dst}\"{robocopy_files} /E /Z /FFT /R:2 /W:3{purge_flag}{new_only_flag}{robocopy_xd_str}{robocopy_xf_str}")
    print("=" * 60)


# ----------------- COMPARISON & SYNC ENGINE ----------------- #

def sync_directories(
    src_dir: str | Path,
    dst_dir: str | Path | list[str | Path] | tuple[str | Path, ...] | None = None,
    direction: str = "push",            # "push" (Local -> CIFS) or "pull" (CIFS -> Local)
    compare_mode: str = "mtime_size",   # "mtime_size" (instant), "sample_hash" (fast), "full_hash" (slow), "size_only"
    mtime_tolerance: float = 2.0,       # Timestamp tolerance in seconds (handles FAT/NTFS/CIFS rounding)
    sync: bool = False,                 # Perform real file operations
    dry_run: bool = True,               # If True, prints actions without executing
    delete_orphan_dst: bool = False,    # Mirror mode: deletes files in destination not in source
    include_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_extensions: set[str] | tuple[str, ...] | list[str] | None = None,
    exclude_patterns: set[str] | tuple[str, ...] | list[str] | None = None,
    dst_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
    default_dst_dir: str | Path | None = None,
    match_by_filename: bool = True,
    copy_new_only: bool = False,
):
    if direction not in ("push", "pull"):
        raise ValueError(f"Unknown direction: {direction}. Must be 'push' or 'pull'.")

    if dst_dirs is not None:
        raw_targets = dst_dirs if isinstance(dst_dirs, (list, tuple)) else [dst_dirs]
    elif dst_dir is not None:
        raw_targets = dst_dir if isinstance(dst_dir, (list, tuple)) else [dst_dir]
    else:
        raise ValueError("Either dst_dir or dst_dirs must be provided.")

    if not raw_targets:
        raise ValueError("At least one destination directory must be provided.")

    target_roots = [Path(d).resolve() for d in raw_targets]

    if direction == "pull":
        if len(target_roots) == 1:
            source_root = target_roots[0]
            target_roots = [Path(src_dir).resolve()]
            default_target_root = target_roots[0]
            direction = "push"
        else:
            local_target = Path(src_dir).resolve()
            for r_root in target_roots:
                print(f"\n[*] Pulling from library directory: {r_root}")
                sync_directories(
                    src_dir=r_root,
                    dst_dir=local_target,
                    direction="push",
                    compare_mode=compare_mode,
                    mtime_tolerance=mtime_tolerance,
                    sync=sync,
                    dry_run=dry_run,
                    delete_orphan_dst=delete_orphan_dst,
                    include_extensions=include_extensions,
                    exclude_extensions=exclude_extensions,
                    exclude_patterns=exclude_patterns,
                    match_by_filename=match_by_filename,
                    copy_new_only=copy_new_only,
                )
            return
    else:
        source_root = Path(src_dir).resolve()
        default_target_root = Path(default_dst_dir).resolve() if default_dst_dir else target_roots[0]

    t_start = time.perf_counter()
    if len(target_roots) == 1:
        print(f"[*] Direction: {source_root}  ==>  {target_roots[0]}")
    else:
        target_list_str = ", ".join(str(t) for t in target_roots)
        print(f"[*] Direction: {source_root}  ==>  [{target_list_str}]")

    print(f"[*] Compare Mode: {compare_mode}")
    if copy_new_only:
        print("[*] Mode: Copy net-new files only (skipping updates to existing files)")
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

    dst_metas: dict[Path, dict[str, FileInfo]] = {}

    if len(target_roots) == 1 and not delete_orphan_dst and not match_by_filename:
        t0 = time.perf_counter()
        print(f"[*] Probing target metadata for {len(src_keys)} candidate files...")
        dst_metas[target_roots[0]] = probe_metadata(target_roots[0], src_keys)
        t_dst = time.perf_counter() - t0
        print(f"[*] Target scan/probe completed in {t_dst:.2f}s.")
    elif len(target_roots) == 1 and not delete_orphan_dst:
        t0 = time.perf_counter()
        print(f"[*] Probing target metadata for {len(src_keys)} candidate files...")
        probed = probe_metadata(target_roots[0], src_keys)
        missing_probed = src_keys - set(probed.keys())
        if missing_probed:
            print(f"[*] {len(missing_probed)} candidate(s) not at relative path, scanning target directory tree...")
            dst_metas[target_roots[0]] = scan_metadata(
                target_roots[0],
                include_extensions=include_extensions,
                exclude_extensions=exclude_extensions,
                exclude_patterns=exclude_patterns,
            )
        else:
            dst_metas[target_roots[0]] = probed
        t_dst = time.perf_counter() - t0
        print(f"[*] Target scan/probe completed in {t_dst:.2f}s.")
    else:
        for tr in target_roots:
            if not tr.exists():
                print(f"[!] WARNING: Target directory does not exist or is unmounted: {tr}")
                dst_metas[tr] = {}
                continue

            t0 = time.perf_counter()
            print(f"[*] Scanning target directory tree: {tr}...")
            dst_metas[tr] = scan_metadata(
                tr,
                include_extensions=include_extensions,
                exclude_extensions=exclude_extensions,
                exclude_patterns=exclude_patterns,
            )
            t_dst = time.perf_counter() - t0
            print(f"[*] Target scan for {tr.name or tr} completed in {t_dst:.2f}s (found {len(dst_metas[tr])} files).")

    # Build filename lookup table for fallback matching across all library directories
    filename_to_dst: dict[str, list[tuple[Path, str, FileInfo]]] = {}
    if match_by_filename:
        for tr in target_roots:
            for rel, info in dst_metas[tr].items():
                fname = Path(rel).name.lower()
                filename_to_dst.setdefault(fname, []).append((tr, rel, info))

    to_copy_missing: list[tuple[str, Path, str]] = []
    matched_dst_entries: set[tuple[Path, str]] = set()
    size_mismatches: list[tuple[str, Path, str, str, FileInfo]] = []
    same_size_candidates: list[tuple[str, Path, str, str, FileInfo]] = []

    for src_rel in sorted(src_meta.keys()):
        src_info = src_meta[src_rel]
        matched: tuple[Path, str, FileInfo, str] | None = None

        # Step 1: Check exact relative path match
        for tr in target_roots:
            if src_rel in dst_metas[tr]:
                matched = (tr, src_rel, dst_metas[tr][src_rel], "rel_path")
                break

        # Step 2: Fallback to filename/basename matching across all targets
        if matched is None and match_by_filename:
            src_fname = Path(src_rel).name.lower()
            candidates = filename_to_dst.get(src_fname, [])
            if candidates:
                size_matched = [c for c in candidates if c[2].size == src_info.size]
                best = size_matched[0] if size_matched else candidates[0]
                matched = (best[0], best[1], best[2], "filename")

        if matched is None:
            to_copy_missing.append((src_rel, default_target_root, src_rel))
        else:
            tr, dst_rel, dst_info, match_reason = matched
            matched_dst_entries.add((tr, dst_rel))
            if not copy_new_only:
                if src_info.size != dst_info.size:
                    size_mismatches.append((src_rel, tr, dst_rel, match_reason, dst_info))
                else:
                    same_size_candidates.append((src_rel, tr, dst_rel, match_reason, dst_info))

    # Detect updates based on compare_mode
    to_update: list[tuple[str, Path, str, str, FileInfo]] = []
    if not copy_new_only:
        if compare_mode == "size_only":
            to_update = sorted(size_mismatches, key=lambda x: x[0])
        elif compare_mode == "mtime_size":
            mtime_mismatches = [
                c for c in same_size_candidates
                if abs(src_meta[c[0]].mtime - c[4].mtime) > mtime_tolerance
            ]
            to_update = sorted(size_mismatches + mtime_mismatches, key=lambda x: x[0])
        elif compare_mode in ("sample_hash", "full_hash"):
            print(f"[*] Verifying checksums ({compare_mode}) on {len(same_size_candidates)} matching files...")
            src_hashes = hash_candidates_parallel(
                source_root,
                [c[0] for c in same_size_candidates],
                mode=compare_mode
            )
            dst_hashes: dict[tuple[Path, str], str] = {}
            for tr in target_roots:
                tr_rels = [c[2] for c in same_size_candidates if c[1] == tr]
                if tr_rels:
                    h = hash_candidates_parallel(tr, tr_rels, mode=compare_mode, max_workers=4)
                    for rel, fhash in h.items():
                        dst_hashes[(tr, rel)] = fhash

            hash_mismatches = [
                c for c in same_size_candidates
                if src_hashes.get(c[0]) != dst_hashes.get((c[1], c[2]))
            ]
            to_update = sorted(size_mismatches + hash_mismatches, key=lambda x: x[0])
        else:
            raise ValueError(
                f"Unknown compare_mode: {compare_mode}. Choose from 'mtime_size', 'sample_hash', 'full_hash', 'size_only'"
            )
    else:
        if compare_mode not in ("size_only", "mtime_size", "sample_hash", "full_hash"):
            raise ValueError(
                f"Unknown compare_mode: {compare_mode}. Choose from 'mtime_size', 'sample_hash', 'full_hash', 'size_only'"
            )

    orphans_in_dst: list[tuple[Path, str]] = []
    if delete_orphan_dst:
        for tr in target_roots:
            for rel in sorted(dst_metas[tr].keys()):
                if (tr, rel) not in matched_dst_entries:
                    orphans_in_dst.append((tr, rel))

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

    # 1. Copy Missing Files
    for src_rel, tr, dst_rel in to_copy_missing:
        s_file = source_root / src_rel
        d_file = tr / dst_rel
        target_info = f" -> {tr.name}/{dst_rel}" if len(target_roots) > 1 else ""
        print(f"  {action_label} CREATE: {src_rel}{target_info}")

        if sync and not dry_run:
            d_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s_file, d_file)  # copy2 preserves timestamps and metadata

    # 2. Update Modified Files (skipped if copy_new_only)
    if not copy_new_only:
        for src_rel, tr, dst_rel, reason, _ in to_update:
            s_file = source_root / src_rel
            d_file = tr / dst_rel
            if reason == "filename":
                target_info = f" (matched by filename -> {tr.name}/{dst_rel})"
            elif len(target_roots) > 1:
                target_info = f" -> {tr.name}/{dst_rel}"
            else:
                target_info = ""
            print(f"  {action_label} UPDATE: {src_rel}{target_info}")

            if sync and not dry_run:
                d_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s_file, d_file)

    # 3. Handle Extra Files in Destination (Mirroring)
    if delete_orphan_dst:
        for tr, rel_path in orphans_in_dst:
            d_file = tr / rel_path
            target_info = f" ({tr.name}/{rel_path})" if len(target_roots) > 1 else f": {rel_path}"
            print(f"  {action_label} DELETE{target_info}")

            if sync and not dry_run:
                if d_file.is_file():
                    d_file.unlink()

    if not sync or dry_run:
        print(f"\n[!] Dry run complete. Pass `sync=True, dry_run=False` to execute these changes.")


# ----------------- ENTRY POINT ----------------- #

if __name__ == "__main__":
    LOCAL_PATH = "/home/mike/Downloads/"       # e.g., "C:/LocalProject"

    # Single path or list of multiple Jellyfin library directories
    CIFS_MOUNTS = [
        "/media/mike/Media",
        #"/run/user/1000/gvfs/smb-share:server=192.168.86.210,share=f",
        #"/run/user/1000/gvfs/smb-share:server=192.168.86.210,share=jellyfin",
        # Or individual library subdirectories:
        # "/run/user/1000/gvfs/smb-share:server=192.168.86.210,share=jellyfin/Movies",
        # "/run/user/1000/gvfs/smb-share:server=192.168.86.210,share=jellyfin/Television",
        # "/run/user/1000/gvfs/smb-share:server=192.168.86.210,share=f",
    ]

    # Step 1: Print Native OS Commands (Optional)
    print_cli_command(
        Path(LOCAL_PATH),
        CIFS_MOUNTS,
        mirror=False,
        compare_mode="mtime_size",
        include_extensions=MEDIA_EXTENSIONS,
        copy_new_only=True,
    )

    # Step 2: Compare & Sync via Python
    sync_directories(
        src_dir=LOCAL_PATH,
        dst_dirs=CIFS_MOUNTS,      # Checks across all library directories
        direction="push",          # "push" sends Local -> CIFS
        compare_mode="mtime_size", # "mtime_size" (instant), "sample_hash" (fast), "full_hash" (slow), "size_only"
        include_extensions=MEDIA_EXTENSIONS,
        match_by_filename=True,    # Match by relative path first, fallback to filename
        copy_new_only=True,        # Only copy net new files, never update existing files
        sync=False,                # Set to True to apply changes
        dry_run=True,              # Set to False to disable preview safety
        delete_orphan_dst=False    # Set to True to delete remote files not on local
    )