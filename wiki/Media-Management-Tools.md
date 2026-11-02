# Media Management & Synchronization Tools

This repository contains high-performance media management tools designed for large local drives and CIFS/SMB network storage shares.

---

## 1. Jellyfin File Compare & Sync (`jfFileCompare.py`)

Located at [`jfFileCompare.py`](https://github.com/nielsonm/dotfiles/blob/main/jfFileCompare.py). Synchronizes local downloads with Jellyfin CIFS/SMB media shares.

### Key Capabilities:
- **Fast Directory-Batched Metadata**: Replaces hundreds of slow remote `stat()` roundtrips across CIFS with single directory `scandir` batches.
- **Multiple Comparison Modes**:
  - `mtime_size`: Fast comparison using file size and modification timestamps.
  - `sample_hash`: 3-point sample hashing (head 1MB, middle 1MB, tail 1MB) for high-speed verification across network mounts.
  - `full_hash`: Full streaming SHA-256 calculation.
  - `size_only`: File size comparison.
- **Preview & Dry-Run Modes**: Generates preview reports and native OS commands (`rsync`, `robocopy`) before applying changes.

---

## 2. Media Duplicate Scanner (`find_media_duplicates.py`)

Located at [`find_media_duplicates.py`](https://github.com/nielsonm/dotfiles/blob/main/find_media_duplicates.py). Identifies exact duplicate files, cross-format duplicates, leftover files, and similar media titles.

### Safety Guarantee:
**Strictly Non-Destructive**: The script never deletes any files. It generates an inspectable shell script ([`cleanup_duplicates.sh`](https://github.com/nielsonm/dotfiles/blob/main/cleanup_duplicates.sh)) where all removal commands are commented out (`# rm -v -- '...'`) with preferred master files marked `[KEEP]`.

### Detection Categories:
1. **Category 1: Exact Byte-for-Byte Duplicates**:
   - Matches files sharing identical sizes using two-stage SHA-256 hashing (sample hash followed by full hash).
2. **Category 2: Cross-Format Duplicates**:
   - Detects the same content in different file containers:
     - eBooks: `.epub` vs `.azw3` vs `.mobi` vs `.pdf` (favoring `.epub`)
     - Video: `.mkv` vs `.mp4` vs `.avi` (favoring `.mkv`)
     - Audio: `.flac` vs `.m4a` vs `.mp3`
3. **Category 3: Incomplete & Mangled Files**:
   - Detects `.filepart` and `.part` download leftovers.
   - Identifies files with stripped extensions where a full companion exists.
4. **Category 4: Similar Filenames & Variants**:
   - Canonical token matching (e.g. `Author - Title` vs `Title - Author`).
   - Episode-aware filtering (`S01E01` never matches `S01E02`).
   - VobSub subtitle pairing (`.sub` and `.idx` companions are preserved).

### Usage:
```bash
# Scan default media library (/media/mike/Media)
python3 find_media_duplicates.py

# Scan custom target directory
python3 find_media_duplicates.py --path /media/mike/Media --output-script cleanup.sh --report-file report.txt

# Custom similarity threshold (default: 0.85)
python3 find_media_duplicates.py --similarity-threshold 0.90
```

### Generated Outputs:
- [`duplicates_report.txt`](https://github.com/nielsonm/dotfiles/blob/main/duplicates_report.txt): Complete human-readable breakdown.
- [`cleanup_duplicates.sh`](https://github.com/nielsonm/dotfiles/blob/main/cleanup_duplicates.sh): Safely commented-out shell commands.
