from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import os
from pathlib import Path
import shutil
import sys

# ----------------- HASHING WORKER ----------------- #

def _hash_worker(file_path_str: str, root_str: str) -> tuple[str, str]:
    file_path = Path(file_path_str)
    root = Path(root_str)
    rel_path = file_path.relative_to(root).as_posix()

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(262144):  # 256 KB buffer for network shares
            hasher.update(chunk)

    return rel_path, hasher.hexdigest()

def hash_candidates_parallel(root: Path, rel_paths: list[str], max_workers: int = 6) -> dict[str, str]:
    if not rel_paths:
        return {}

    root_str = str(root)
    full_paths = [str(root / p) for p in rel_paths]
    results = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_hash_worker, f, root_str) for f in full_paths]
        for fut in as_completed(futures):
            rel, file_hash = fut.result()
            results[rel] = file_hash

    return results

# ----------------- METADATA SCANNING ----------------- #

def scan_metadata(directory_root: Path) -> dict[str, int]:
    index = {}
    root_str = str(directory_root)

    def _walk(current_path: str):
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        rel = os.path.relpath(entry.path, root_str).replace("\\", "/")
                        index[rel] = entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        _walk(entry.path)
        except PermissionError:
            print(f"Permission denied: {current_path}")

    _walk(root_str)
    return index

# ----------------- CLI COMMAND GENERATOR ----------------- #

def print_cli_command(src: Path, dst: Path, mirror: bool = False):
    """Generates optimal OS-level sync commands."""
    print("\n" + "=" * 60)
    print("NATIVE CLI COMMAND EQUIVALENTS:")
    print("=" * 60)

    # Linux / macOS (rsync)
    delete_flag = " --delete" if mirror else ""
    src_str = str(src).rstrip("/") + "/"
    dst_str = str(dst).rstrip("/") + "/"
    print("POSIX / Linux (rsync):")
    print(f"  rsync -avh --progress{delete_flag} \"{src_str}\" \"{dst_str}\"")

    # Windows (Robocopy)
    purge_flag = " /PURGE" if mirror else ""
    print("\nWindows (Robocopy):")
    print(f"  robocopy \"{src}\" \"{dst}\" /E /Z /R:2 /W:3{purge_flag}")
    print("=" * 60)

# ----------------- COMPARISON & SYNC ENGINE ----------------- #

def sync_directories(
    src_dir: str,
    dst_dir: str,
    direction: str = "push",       # "push" (Local -> CIFS) or "pull" (CIFS -> Local)
    sync: bool = False,            # Perform real file operations
    dry_run: bool = True,          # If True, prints actions without executing
    delete_orphan_dst: bool = False # Mirror mode: deletes files in destination not in source
):
    source_root = Path(src_dir).resolve()
    target_root = Path(dst_dir).resolve()

    if direction == "pull":
        source_root, target_root = target_root, source_root

    print(f"[*] Direction: {source_root}  ==>  {target_root}")
    print(f"[*] Scanning metadata...")

    src_meta = scan_metadata(source_root)
    dst_meta = scan_metadata(target_root)

    src_keys = set(src_meta.keys())
    dst_keys = set(dst_meta.keys())

    to_copy_missing = sorted(src_keys - dst_keys)
    orphans_in_dst = sorted(dst_keys - src_keys)
    common_files = src_keys & dst_keys

    # Check for size mismatches
    size_mismatches = []
    same_size_candidates = []

    for f in common_files:
        if src_meta[f] != dst_meta[f]:
            size_mismatches.append(f)
        else:
            same_size_candidates.append(f)

    # Hash same-size files to detect silent content modifications
    print(f"[*] Verifying checksums on {len(same_size_candidates)} matching files...")
    src_hashes = hash_candidates_parallel(source_root, same_size_candidates)
    dst_hashes = hash_candidates_parallel(target_root, same_size_candidates, max_workers=4)

    hash_mismatches = [
        f for f in same_size_candidates
        if src_hashes.get(f) != dst_hashes.get(f)
    ]

    to_update = sorted(size_mismatches + hash_mismatches)

    # ----------------- EXECUTION PLAN REPORT ----------------- #
    print("\n" + "=" * 60)
    print("CHANGES DETECTED:")
    print(f"  Missing on Target (To Create) : {len(to_copy_missing)}")
    print(f"  Modified on Source (To Update): {len(to_update)}")
    print(f"  Extra on Target (Orphans)     : {len(orphans_in_dst)}")
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
    print_cli_command(Path(LOCAL_PATH), Path(CIFS_MOUNT), mirror=False)

    # Step 2: Compare & Sync via Python
    sync_directories(
        src_dir=LOCAL_PATH,
        dst_dir=CIFS_MOUNT,
        direction="push",          # "push" sends Local -> CIFS
        sync=False,                # Set to True to apply changes
        dry_run=True,              # Set to False to disable preview safety
        delete_orphan_dst=False    # Set to True to delete remote files not on local
    )