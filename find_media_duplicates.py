#!/usr/bin/env python3
"""
Find Duplicate Files and Generate Safe Cleanup Commands
=======================================================
Scans a target directory (such as /media/mike/Media) to identify:
1. Exact byte-for-byte duplicates (SHA-256 hash verified).
2. Cross-format duplicates (e.g. .epub vs .azw3, .mkv vs .mp4).
3. Similar filenames / title variants (fuzzy token matching and SequenceMatcher).
4. Mangled extensions and incomplete downloads (.filepart, stripped extensions).

IMPORTANT: This script is strictly READ-ONLY. It will NEVER delete any files.
It generates an inspectable shell script with safely commented-out removal commands.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import difflib
import hashlib
import os
from pathlib import Path
import re
import shlex
import sys
import time
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

# System and metadata directories to prune from scans
DEFAULT_EXCLUDE_DIR_NAMES = {
    "$recycle.bin",
    "system volume information",
    ".trashes",
    ".fseventsd",
    "__pycache__",
    ".git",
    "node_modules",
}

# System files to ignore
DEFAULT_EXCLUDE_FILES = {
    "pagefile.sys",
    "dumpstack.log.tmp",
    "swapfile.sys",
    "hiberfil.sys",
    "thumbs.db",
    ".ds_store",
}

MEDIA_DOMAINS = {
    "video": {
        "extensions": {".mkv", ".mp4", ".m4v", ".webm", ".avi", ".mov", ".flv", ".ts", ".vob", ".wmv"},
        "preference": [".mkv", ".mp4", ".m4v", ".webm", ".mov", ".avi", ".flv", ".ts", ".vob", ".wmv"],
    },
    "ebooks": {
        "extensions": {".epub", ".azw3", ".azw", ".mobi", ".pdf"},
        "preference": [".epub", ".azw3", ".mobi", ".azw", ".pdf"],
    },
    "audio": {
        "extensions": {".flac", ".m4a", ".mp3", ".opus", ".ogg", ".wav", ".wma", ".aac", ".aiff", ".alac", ".m4b"},
        "preference": [".flac", ".alac", ".m4a", ".mp3", ".m4b", ".opus", ".ogg", ".wav", ".aac", ".wma", ".aiff"],
    },
    "subtitles": {
        "extensions": {".srt", ".sub", ".idx", ".vtt", ".ass", ".ssa"},
        "preference": [".srt", ".vtt", ".ass", ".ssa", ".sub", ".idx"],
    },
}

LEFTOVER_EXTENSIONS = {".filepart", ".crdownload", ".tmp", ".part", ".download"}

COMMON_TAGS_REGEX = re.compile(
    r"\b(2160p|1080p|1080i|720p|576p|480p|4k|uhd|bluray|bdrip|brrip|webrip|web-dl|web|hdtv|dvdrip|dvd|x264|x265|hevc|h264|aac|ac3|eac3|dts|remastered|extended|unrated|directors cut|proper|repack|retail|yts(\.mx|\.lt|\.am|\.bz)?|rarbg|eztv|galaxytv|tgx|bluespots|garshasp|memento|ezv)\b",
    re.IGNORECASE,
)
YEAR_REGEX = re.compile(r"\b(19\d\d|20\d\d)\b")
NON_ALPHANUM_REGEX = re.compile(r"[^a-z0-9]+")
STOP_WORDS = {"the", "a", "an", "and", "or", "of", "in", "to", "for", "with", "by"}

GENERIC_STEMS = {
    "english", "eng", "spanish", "spa", "french", "fre", "fra", "german", "ger",
    "deu", "italian", "ita", "japanese", "jap", "jpn", "subs", "subtitles",
    "sdh", "hi", "cc", "forced", "hearing_impaired",
    "sample", "trailer", "featurette", "bonus", "extra", "poster", "fanart",
    "banner", "landscape", "clearart", "logo", "disc", "discart", "cover",
}

BUFFER_SIZE = 4 * 1024 * 1024  # 4 MB read buffer
SAMPLE_CHUNK_SIZE = 1024 * 1024  # 1 MB chunk for sample hashing


class FileEntry(NamedTuple):
    path: Path
    size: int
    mtime: float


def human_readable_size(num_bytes: int) -> str:
    """Formats bytes into human-readable B, KB, MB, GB, TB."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024.0 or unit == "TB":
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def resolve_directory(path_str: str) -> Path:
    """Resolves target directory, handling case differences (e.g. Mike vs mike)."""
    p = Path(path_str).expanduser()
    if p.exists() and p.is_dir():
        return p.resolve()

    parent = p.parent
    if parent.exists() and parent.is_dir():
        for entry in parent.iterdir():
            if entry.name.lower() == p.name.lower() and entry.is_dir():
                return entry.resolve()

    if str(p).lower() in ("/media/mike/media", "/media/mike/media/"):
        for candidate in (Path("/media/mike/Media"), Path("/media/Mike/Media")):
            if candidate.exists() and candidate.is_dir():
                return candidate.resolve()

    return p.resolve()


def scan_files(
    root: Path,
    min_size_bytes: int = 1,
    include_extensions: Optional[Set[str]] = None,
) -> List[FileEntry]:
    """Recursively scans directory tree using os.scandir, skipping system folders."""
    results: List[FileEntry] = []
    stack = [root]

    norm_includes = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in include_extensions} if include_extensions else None

    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    name_lower = entry.name.lower()
                    if entry.is_dir(follow_symlinks=False):
                        if name_lower in DEFAULT_EXCLUDE_DIR_NAMES or name_lower.startswith(".trash-"):
                            continue
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        if name_lower in DEFAULT_EXCLUDE_FILES or name_lower.startswith("._"):
                            continue
                        if norm_includes and not any(name_lower.endswith(ext) for ext in norm_includes):
                            continue
                        try:
                            st = entry.stat()
                            if st.st_size >= min_size_bytes:
                                results.append(
                                    FileEntry(
                                        path=Path(entry.path),
                                        size=st.st_size,
                                        mtime=st.st_mtime,
                                    )
                                )
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError) as err:
            print(f"[!] Warning: Cannot access {current_dir}: {err}", file=sys.stderr)

    return results


# ----------------- HASHING HELPERS ----------------- #

def _compute_sample_hash(path_str: str, file_size: int) -> str:
    """Computes fast 3-point sample hash (head, middle, tail) + size."""
    hasher = hashlib.sha256()
    hasher.update(str(file_size).encode("ascii"))

    with open(path_str, "rb") as f:
        if file_size <= SAMPLE_CHUNK_SIZE * 3:
            while chunk := f.read(BUFFER_SIZE):
                hasher.update(chunk)
        else:
            hasher.update(f.read(SAMPLE_CHUNK_SIZE))
            f.seek((file_size - SAMPLE_CHUNK_SIZE) // 2)
            hasher.update(f.read(SAMPLE_CHUNK_SIZE))
            f.seek(file_size - SAMPLE_CHUNK_SIZE)
            hasher.update(f.read(SAMPLE_CHUNK_SIZE))

    return hasher.hexdigest()


def _compute_full_hash(path_str: str) -> str:
    """Computes full SHA-256 hash using streaming buffer."""
    hasher = hashlib.sha256()
    with open(path_str, "rb") as f:
        while chunk := f.read(BUFFER_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def _hash_worker(args: Tuple[str, int, str]) -> Tuple[str, str]:
    path_str, size, mode = args
    try:
        if mode == "sample":
            h = _compute_sample_hash(path_str, size)
        else:
            h = _compute_full_hash(path_str)
        return path_str, h
    except (OSError, PermissionError):
        return path_str, ""


def find_exact_duplicates(
    entries: List[FileEntry],
    max_workers: int = 4,
) -> Dict[str, List[FileEntry]]:
    """Two-stage exact duplicate detection (Size -> Sample Hash -> Full SHA-256)."""
    size_map: Dict[int, List[FileEntry]] = defaultdict(list)
    for entry in entries:
        size_map[entry.size].append(entry)

    potential_candidates: List[FileEntry] = [
        item for items in size_map.values() if len(items) > 1 for item in items
    ]

    if not potential_candidates:
        return {}

    print(f"[*] Hashing {len(potential_candidates)} candidate files with identical sizes...")

    sample_tasks = [(str(e.path), e.size, "sample") for e in potential_candidates]
    path_to_entry = {str(e.path): e for e in potential_candidates}
    sample_hash_map: Dict[Tuple[int, str], List[FileEntry]] = defaultdict(list)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_hash_worker, t) for t in sample_tasks]
        for fut in as_completed(futures):
            path_str, s_hash = fut.result()
            if s_hash:
                entry = path_to_entry[path_str]
                sample_hash_map[(entry.size, s_hash)].append(entry)

    full_hash_tasks: List[Tuple[str, int, str]] = []
    for (size, _), group in sample_hash_map.items():
        if len(group) > 1:
            for e in group:
                full_hash_tasks.append((str(e.path), e.size, "full"))

    if not full_hash_tasks:
        return {}

    exact_duplicates: Dict[str, List[FileEntry]] = defaultdict(list)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_hash_worker, t) for t in full_hash_tasks]
        for fut in as_completed(futures):
            path_str, f_hash = fut.result()
            if f_hash:
                exact_duplicates[f_hash].append(path_to_entry[path_str])

    return {h: group for h, group in exact_duplicates.items() if len(group) > 1}


# ----------------- BROADENED SEARCH ALGORITHMS ----------------- #

def clean_media_stem(filename: str) -> str:
    """Strips resolutions, codec, bracketed info, year tags, and punctuation."""
    stem = Path(filename).stem.lower()
    cleaned = re.sub(r"\[.*?\]|\(.*?\)", " ", stem)
    cleaned = COMMON_TAGS_REGEX.sub(" ", cleaned)
    cleaned = YEAR_REGEX.sub(" ", cleaned)
    cleaned = re.sub(r"[._\-+]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def canonical_tokens(clean_title: str) -> str:
    """Extracts alphabetized tokens to match inverted titles (e.g. Author - Title vs Title - Author)."""
    words = [
        w for w in NON_ALPHANUM_REGEX.split(clean_title)
        if len(w) > 1 and w not in STOP_WORDS
    ]
    return " ".join(sorted(set(words)))


def find_cross_format_duplicates(
    entries: List[FileEntry],
    exact_duplicate_paths: Set[Path],
) -> List[Tuple[str, str, FileEntry, List[FileEntry]]]:
    """
    Identifies files sharing the same normalized content stem across different extensions
    within the same media domain (e.g., .epub vs .azw3, .mkv vs .mp4).
    Returns list of: (domain, clean_title, keep_file, [files_to_review])
    """
    results = []

    for domain_name, domain_info in MEDIA_DOMAINS.items():
        ext_set = domain_info["extensions"]
        pref_order = {ext: idx for idx, ext in enumerate(domain_info["preference"])}

        # Group by clean stem
        stem_groups: Dict[str, List[FileEntry]] = defaultdict(list)
        for e in entries:
            if e.path in exact_duplicate_paths:
                continue
            ext = e.path.suffix.lower()
            if ext in ext_set:
                clean = clean_media_stem(e.path.name)
                if len(clean) >= 3:
                    stem_groups[clean].append(e)

        for clean_title, group in stem_groups.items():
            distinct_exts = {e.path.suffix.lower() for e in group}
            # Skip VobSub subtitle companions (.sub and .idx belong together)
            if domain_name == "subtitles" and distinct_exts.issubset({".sub", ".idx"}):
                continue
            if len(distinct_exts) > 1:
                # Sort group by preference order, then by file size (descending)
                def _sort_key(entry: FileEntry):
                    pref_idx = pref_order.get(entry.path.suffix.lower(), 999)
                    return (pref_idx, -entry.size, entry.mtime)

                sorted_group = sorted(group, key=_sort_key)
                keep_file = sorted_group[0]
                review_files = sorted_group[1:]
                results.append((domain_name, clean_title, keep_file, review_files))

    return results


EPISODE_REGEX = re.compile(r"(?:s(\d+)[._\- ]*e(\d+)|(\d+)x(\d+))", re.IGNORECASE)


def extract_episode(text: str) -> Optional[Tuple[int, int]]:
    """Extracts (season, episode) number from filename or stem."""
    m = EPISODE_REGEX.search(text)
    if m:
        if m.group(1) and m.group(2):
            return int(m.group(1)), int(m.group(2))
        if m.group(3) and m.group(4):
            return int(m.group(3)), int(m.group(4))
    return None


def find_fuzzy_similar_titles(
    entries: List[FileEntry],
    exact_duplicate_paths: Set[Path],
    cross_format_paths: Set[Path],
    threshold: float = 0.85,
) -> List[Tuple[str, FileEntry, List[Tuple[FileEntry, float]]]]:
    """
    Finds titles with inverted word order or high string similarity (difflib >= threshold)
    strictly within the same media domain (e.g. video vs video, ebook vs ebook).
    """
    grouped_results = []
    seen_in_fuzzy: Set[Path] = set()

    for domain_name, domain_info in MEDIA_DOMAINS.items():
        domain_exts = domain_info["extensions"]
        candidates: List[Tuple[FileEntry, str, str, Optional[Tuple[int, int]]]] = []

        for e in entries:
            if e.path in exact_duplicate_paths or e.path in cross_format_paths or e.path in seen_in_fuzzy:
                continue
            if e.path.suffix.lower() not in domain_exts:
                continue
            # Skip generic featurette / bonus files from cross-movie comparisons
            if any(part.lower() in ("featurettes", "extras", "bonus") for part in e.path.parts):
                continue
            clean = clean_media_stem(e.path.name)
            tokens = canonical_tokens(clean)
            if len(tokens) >= 4 and tokens not in GENERIC_STEMS and len(tokens.split()) >= 2:
                ep = extract_episode(e.path.name)
                candidates.append((e, clean, tokens, ep))

        # 1. Cluster by exact canonical tokens within the domain
        token_clusters: Dict[Tuple, List[Tuple[FileEntry, str]]] = defaultdict(list)
        for entry, clean, tokens, ep in candidates:
            # Subtitles should only match within the same movie/show directory
            folder_scope = entry.path.parent.parent if domain_name == "subtitles" else None
            token_clusters[(tokens, ep, folder_scope)].append((entry, clean))

        for (tokens, ep, _scope), group in token_clusters.items():
            if len(group) > 1:
                # If domain is subtitles and group is only .sub and .idx companions, skip
                if domain_name == "subtitles":
                    distinct_exts = {item[0].path.suffix.lower() for item in group}
                    if distinct_exts.issubset({".sub", ".idx"}):
                        continue
                sorted_group = sorted(group, key=lambda item: (item[0].mtime, len(str(item[0].path))))
                master = sorted_group[0][0]
                others = [(item[0], 1.0) for item in sorted_group[1:]]
                ep_tag = f" S{ep[0]:02d}E{ep[1]:02d}" if ep else ""
                grouped_results.append((f"[{domain_name.upper()}] Exact Match: '{tokens}'{ep_tag}", master, others))
                for item in group:
                    seen_in_fuzzy.add(item[0].path)

        # 2. Difflib Sequence Matcher within directory clusters for this domain
        dir_clusters: Dict[Path, List[Tuple[FileEntry, str, Optional[Tuple[int, int]]]]] = defaultdict(list)
        for entry, clean, tokens, ep in candidates:
            if entry.path not in seen_in_fuzzy:
                cluster_key = entry.path.parent if entry.path.parent.name != "Media" else entry.path
                dir_clusters[cluster_key].append((entry, clean, ep))

        for parent_dir, items in dir_clusters.items():
            if len(items) < 2 or len(items) > 300:
                continue
            n = len(items)
            matched_in_dir: Set[int] = set()

            for i in range(n):
                if i in matched_in_dir:
                    continue
                e1, clean1, ep1 = items[i]
                matches: List[Tuple[FileEntry, float]] = []

                for j in range(i + 1, n):
                    if j in matched_in_dir:
                        continue
                    e2, clean2, ep2 = items[j]

                    # Never match different episodes together!
                    if ep1 is not None or ep2 is not None:
                        if ep1 != ep2:
                            continue

                    # If domain is subtitles and this pair is .sub and .idx companions, skip
                    if domain_name == "subtitles":
                        if {e1.path.suffix.lower(), e2.path.suffix.lower()}.issubset({".sub", ".idx"}):
                            continue

                    len_ratio = min(len(clean1), len(clean2)) / max(len(clean1), len(clean2))
                    if len_ratio < 0.70:
                        continue

                    sim = difflib.SequenceMatcher(None, clean1, clean2).quick_ratio()
                    if sim >= threshold:
                        sim_real = difflib.SequenceMatcher(None, clean1, clean2).ratio()
                        if sim_real >= threshold:
                            matches.append((e2, round(sim_real, 2)))
                            matched_in_dir.add(j)

                if matches:
                    matched_in_dir.add(i)
                    grouped_results.append((f"[{domain_name.upper()}] Fuzzy Match: '{clean1}'", e1, matches))
                    for m_entry, _ in matches:
                        seen_in_fuzzy.add(m_entry.path)
                    seen_in_fuzzy.add(e1.path)

    return grouped_results


def find_mangled_and_incomplete_files(
    entries: List[FileEntry],
    exact_duplicate_paths: Set[Path],
) -> List[Tuple[str, FileEntry, Optional[FileEntry]]]:
    """
    Identifies:
    1. Incomplete download remnants (.filepart, .crdownload, .tmp).
    2. Stripped extensions where a file with valid extension exists alongside it.
    """
    results = []
    dir_entries: Dict[Path, List[FileEntry]] = defaultdict(list)
    for e in entries:
        dir_entries[e.path.parent].append(e)

    for parent, files in dir_entries.items():
        name_map = {f.path.name: f for f in files}

        for f in files:
            if f.path in exact_duplicate_paths:
                continue

            suffix = f.path.suffix.lower()

            # 1. Incomplete / leftover
            if suffix in LEFTOVER_EXTENSIONS or ".filepart" in f.path.name.lower():
                results.append(("Incomplete / Leftover Download", f, None))
                continue

            # 2. Stripped / mangled extension
            # E.g. "Episode.720p" without .mkv, when "Episode.720p.mkv" exists alongside it
            for ext in (".mkv", ".mp4", ".avi", ".epub", ".azw3", ".mp3", ".flac"):
                companion_name = f"{f.path.name}{ext}"
                if companion_name in name_map:
                    results.append(("Mangled / Missing Extension (Companion exists)", f, name_map[companion_name]))
                    break

    return results


# ----------------- OUTPUT GENERATION ----------------- #

def generate_cleanup_script(
    exact_duplicates: Dict[str, List[FileEntry]],
    cross_format: List[Tuple[str, str, FileEntry, List[FileEntry]]],
    fuzzy_matches: List[Tuple[str, FileEntry, List[Tuple[FileEntry, float]]]],
    mangled_files: List[Tuple[str, FileEntry, Optional[FileEntry]]],
    script_path: Path,
    root_dir: Path,
) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "# =====================================================================",
        "# Generated Broadened Media Cleanup Script",
        f"# Target Directory: {root_dir}",
        f"# Generated At    : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "# =====================================================================",
        "# SAFETY NOTICE:",
        "# 1. All deletion commands are strictly COMMENTED OUT by default.",
        "# 2. Review each item before taking action.",
        "# 3. Never execute blindly without confirming file contents.",
        "# =====================================================================",
        "",
        "set -euo pipefail",
        "",
        'echo "Running duplicate cleanup script..."',
        "",
    ]

    total_exact_wasted = 0

    # 1. Exact Duplicates (Highest Confidence)
    lines.append("# =====================================================================")
    lines.append("# CATEGORY 1: EXACT DUPLICATES (Identical SHA-256 Hashes)")
    lines.append("# =====================================================================")
    lines.append("")

    group_num = 1
    for file_hash, group in sorted(exact_duplicates.items(), key=lambda x: -x[1][0].size * (len(x[1]) - 1)):
        sorted_group = sorted(group, key=lambda e: (e.mtime, len(str(e.path))))
        keep_file = sorted_group[0]
        duplicates_to_remove = sorted_group[1:]

        file_size_hr = human_readable_size(keep_file.size)
        wasted = keep_file.size * len(duplicates_to_remove)
        total_exact_wasted += wasted

        lines.append(f"# --- Exact Duplicate Group {group_num} ({file_size_hr} each, {human_readable_size(wasted)} reclaimable) ---")
        lines.append(f"# [KEEP]   : {keep_file.path}")
        for dup in duplicates_to_remove:
            escaped_path = shlex.quote(str(dup.path))
            lines.append(f"# [REMOVE] : {dup.path}")
            lines.append(f"# rm -v -- {escaped_path}")
        lines.append("")
        group_num += 1

    # 2. Cross-Format Duplicates
    if cross_format:
        lines.append("# =====================================================================")
        lines.append("# CATEGORY 2: CROSS-FORMAT DUPLICATES (Different Extensions / Same Content)")
        lines.append("# Review carefully to confirm which format/container you prefer.")
        lines.append("# =====================================================================")
        lines.append("")

        for idx, (domain, title, keep_f, review_list) in enumerate(cross_format, start=1):
            lines.append(f"# --- Cross-Format Group {idx} [{domain.upper()}]: '{title}' ---")
            lines.append(f"# [RECOMMENDED KEEP] ({keep_f.path.suffix}): {keep_f.path} ({human_readable_size(keep_f.size)})")
            for rev in review_list:
                escaped = shlex.quote(str(rev.path))
                lines.append(f"# [ALTERNATIVE]      ({rev.path.suffix}): {rev.path} ({human_readable_size(rev.size)})")
                lines.append(f"# rm -v -- {escaped}")
            lines.append("")

    # 3. Mangled / Incomplete Files
    if mangled_files:
        lines.append("# =====================================================================")
        lines.append("# CATEGORY 3: INCOMPLETE DOWNLOADS & MANGLED EXTENSIONS")
        lines.append("# =====================================================================")
        lines.append("")

        for idx, (reason, target, companion) in enumerate(mangled_files, start=1):
            escaped = shlex.quote(str(target.path))
            lines.append(f"# --- Artifact {idx}: {reason} ---")
            if companion:
                lines.append(f"# [COMPANION EXISTS]: {companion.path} ({human_readable_size(companion.size)})")
            lines.append(f"# [TARGET CANDIDATE]: {target.path} ({human_readable_size(target.size)})")
            lines.append(f"# rm -v -- {escaped}")
            lines.append("")

    # 4. Fuzzy Similar Filenames
    if fuzzy_matches:
        lines.append("# =====================================================================")
        lines.append("# CATEGORY 4: SIMILAR FILENAMES / QUALITY VARIANTS (Manual Review Only)")
        lines.append("# =====================================================================")
        lines.append("")

        for idx, (label, master, sims) in enumerate(fuzzy_matches, start=1):
            lines.append(f"# --- Similar Group {idx}: {label} ---")
            lines.append(f"# [BASE ITEM] : {master.path} ({human_readable_size(master.size)})")
            for sim_entry, score in sims:
                escaped = shlex.quote(str(sim_entry.path))
                lines.append(f"# [SIMILAR ({int(score*100)}%)]: {sim_entry.path} ({human_readable_size(sim_entry.size)})")
                lines.append(f"# rm -v -- {escaped}")
            lines.append("")

    lines.append(f'echo "Cleanup script completed. Exact duplicate potential reclaimed: {human_readable_size(total_exact_wasted)}"')
    lines.append("")

    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("\n".join(lines), encoding="utf-8")
    script_path.chmod(0o755)


def generate_text_report(
    target_dir: Path,
    entries: List[FileEntry],
    exact_duplicates: Dict[str, List[FileEntry]],
    cross_format: List[Tuple[str, str, FileEntry, List[FileEntry]]],
    fuzzy_matches: List[Tuple[str, FileEntry, List[Tuple[FileEntry, float]]]],
    mangled_files: List[Tuple[str, FileEntry, Optional[FileEntry]]],
    report_file_path: Path,
) -> None:
    total_scanned_size = sum(e.size for e in entries)
    exact_reclaimable = sum(g[0].size * (len(g) - 1) for g in exact_duplicates.values())

    report_lines = [
        "======================================================================",
        "BROADENED MEDIA DUPLICATE SCAN REPORT",
        "======================================================================",
        f"Target Directory     : {target_dir}",
        f"Scan Date            : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Scanned Files  : {len(entries)} ({human_readable_size(total_scanned_size)})",
        f"Exact Duplicate Sets : {len(exact_duplicates)} ({human_readable_size(exact_reclaimable)} reclaimable)",
        f"Cross-Format Groups  : {len(cross_format)}",
        f"Mangled / Incomplete : {len(mangled_files)}",
        f"Fuzzy Similar Groups : {len(fuzzy_matches)}",
        "======================================================================",
        "",
        "SECTION 1: EXACT DUPLICATES (Identical SHA-256 Hashes)",
        "-" * 70,
    ]

    for h, group in sorted(exact_duplicates.items(), key=lambda x: -x[1][0].size * (len(x[1]) - 1)):
        sorted_group = sorted(group, key=lambda e: (e.mtime, len(str(e.path))))
        size_str = human_readable_size(sorted_group[0].size)
        report_lines.append(f"Hash: {h} | Size: {size_str} each")
        report_lines.append(f"  [KEEP]   {sorted_group[0].path}")
        for dup in sorted_group[1:]:
            report_lines.append(f"  [REMOVE] {dup.path}")
        report_lines.append("")

    if cross_format:
        report_lines.extend([
            "=" * 70,
            "SECTION 2: CROSS-FORMAT DUPLICATES (Different Extensions)",
            "Same content title detected across multiple formats (e.g. EPUB vs AZW3, MKV vs MP4)",
            "-" * 70,
        ])
        for domain, title, keep_f, review_list in cross_format:
            report_lines.append(f"[{domain.upper()}] '{title}':")
            report_lines.append(f"  [KEEP ({keep_f.path.suffix})]   {keep_f.path} ({human_readable_size(keep_f.size)})")
            for rev in review_list:
                report_lines.append(f"  [ALT  ({rev.path.suffix})]   {rev.path} ({human_readable_size(rev.size)})")
            report_lines.append("")

    if mangled_files:
        report_lines.extend([
            "=" * 70,
            "SECTION 3: INCOMPLETE DOWNLOADS & MANGLED EXTENSIONS",
            "-" * 70,
        ])
        for reason, target, companion in mangled_files:
            comp_info = f" -> Companion: {companion.path.name}" if companion else ""
            report_lines.append(f"[{reason}] {target.path} ({human_readable_size(target.size)}){comp_info}")
        report_lines.append("")

    if fuzzy_matches:
        report_lines.extend([
            "=" * 70,
            "SECTION 4: SIMILAR FILENAMES / QUALITY VARIANTS",
            "-" * 70,
        ])
        for label, master, sims in fuzzy_matches:
            report_lines.append(f"{label}:")
            report_lines.append(f"  [BASE]    {master.path} ({human_readable_size(master.size)})")
            for s_entry, score in sims:
                report_lines.append(f"  [SIM {int(score*100)}%] {s_entry.path} ({human_readable_size(s_entry.size)})")
            report_lines.append("")

    report_file_path.write_text("\n".join(report_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely scan media directories for exact duplicates, cross-format duplicates, and similar filenames."
    )
    parser.add_argument(
        "--path",
        default="/media/mike/Media",
        help="Path to scan (default: /media/mike/Media with auto case fallback)",
    )
    parser.add_argument(
        "--output-script",
        default="cleanup_duplicates.sh",
        help="Path for generated bash cleanup script (default: cleanup_duplicates.sh)",
    )
    parser.add_argument(
        "--report-file",
        default="duplicates_report.txt",
        help="Path for detailed text summary report (default: duplicates_report.txt)",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        help="Minimum file size in bytes to inspect (default: 1)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel hash worker processes (default: 4)",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.85,
        help="Threshold for fuzzy filename matching (0.0 - 1.0, default: 0.85)",
    )
    parser.add_argument(
        "--include-ext",
        nargs="*",
        help="Filter by specific file extensions",
    )

    args = parser.parse_args()

    target_dir = resolve_directory(args.path)
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"[!] Error: Target directory does not exist or is not a directory: {args.path}", file=sys.stderr)
        return 1

    output_script_path = Path(args.output_script).resolve()
    report_file_path = Path(args.report_file).resolve()

    print("=" * 70)
    print("BROADENED MEDIA SCANNER (READ-ONLY MODE)")
    print(f"Target Directory     : {target_dir}")
    print(f"Output Script        : {output_script_path}")
    print(f"Report File          : {report_file_path}")
    print(f"Similarity Threshold : {args.similarity_threshold}")
    print("=" * 70)

    t0 = time.perf_counter()
    print("[*] Scanning directory structure...")
    entries = scan_files(
        root=target_dir,
        min_size_bytes=args.min_size,
        include_extensions=set(args.include_ext) if args.include_ext else None,
    )
    scan_duration = time.perf_counter() - t0
    total_scanned_size = sum(e.size for e in entries)
    print(f"[+] Found {len(entries)} files ({human_readable_size(total_scanned_size)}) in {scan_duration:.2f}s")

    if not entries:
        print("[!] No files found to analyze.")
        return 0

    # 1. Exact Duplicates
    print("[*] Detecting exact duplicates (SHA-256)...")
    exact_duplicates = find_exact_duplicates(entries, max_workers=args.workers)

    exact_dup_paths: Set[Path] = set()
    total_exact_files = 0
    total_exact_reclaimable = 0
    for group in exact_duplicates.values():
        total_exact_files += len(group) - 1
        total_exact_reclaimable += group[0].size * (len(group) - 1)
        for e in group:
            exact_dup_paths.add(e.path)

    # 2. Cross-Format Duplicates
    print("[*] Detecting cross-format duplicates (.epub vs .azw3, .mkv vs .mp4, etc.)...")
    cross_format = find_cross_format_duplicates(entries, exact_dup_paths)
    cross_format_paths: Set[Path] = set()
    for _, _, keep_f, rev_list in cross_format:
        cross_format_paths.add(keep_f.path)
        for r in rev_list:
            cross_format_paths.add(r.path)

    # 3. Mangled / Incomplete Files
    print("[*] Detecting incomplete downloads and mangled extensions...")
    mangled_files = find_mangled_and_incomplete_files(entries, exact_dup_paths)
    for _, t, _ in mangled_files:
        cross_format_paths.add(t.path)

    # 4. Fuzzy Similar Filenames
    print("[*] Detecting similar filenames & title variations...")
    fuzzy_matches = find_fuzzy_similar_titles(
        entries,
        exact_dup_paths,
        cross_format_paths,
        threshold=args.similarity_threshold,
    )

    # Output Summary
    print("\n" + "=" * 70)
    print("SCAN SUMMARY:")
    print(f"  Total Files Indexed       : {len(entries)}")
    print(f"  Exact Duplicate Sets      : {len(exact_duplicates)} ({human_readable_size(total_exact_reclaimable)} reclaimable)")
    print(f"  Cross-Format Groups       : {len(cross_format)}")
    print(f"  Incomplete / Mangled      : {len(mangled_files)}")
    print(f"  Fuzzy Similar Groups      : {len(fuzzy_matches)}")
    print(f"  Total Elapsed Time        : {time.perf_counter() - t0:.2f}s")
    print("=" * 70)

    # Generate cleanup script
    generate_cleanup_script(
        exact_duplicates,
        cross_format,
        fuzzy_matches,
        mangled_files,
        output_script_path,
        target_dir,
    )
    print(f"[+] Safe cleanup script written to: {output_script_path}")
    print("    (All removal commands are safely commented out with '#')")

    # Generate text report
    generate_text_report(
        target_dir,
        entries,
        exact_duplicates,
        cross_format,
        fuzzy_matches,
        mangled_files,
        report_file_path,
    )
    print(f"[+] Detailed text report written to: {report_file_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
