#!/usr/bin/env python3
"""
Script to compare active configuration files (in $HOME or custom target directory)
with the dotfiles stored in this repository and generate a diff report.
"""

import os
import sys
import argparse
import difflib
import json
from pathlib import Path

# Files/directories in repo to ignore by default
DEFAULT_IGNORES = {
    ".git",
    ".gitignore",
    "README.md",
    "install.sh",
    "check_diffs.py",
    "check_diffs.sh",
}

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def supports_color(force_color=False, no_color=False):
    if no_color:
        return False
    if force_color:
        return True
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def colorize(text, color, use_color=True):
    if not use_color:
        return text
    return f"{color}{text}{Colors.ENDC}"

def scan_repo_files(repo_dir, ignores):
    repo_files = []
    repo_path = Path(repo_dir).resolve()

    for root, dirs, files in os.walk(repo_path):
        # Filter ignored directories in-place
        dirs[:] = [
            d for d in dirs
            if d not in ignores and not os.path.relpath(os.path.join(root, d), repo_path).startswith('.git')
        ]
        
        for file in files:
            full_path = Path(root) / file
            rel_path = full_path.relative_to(repo_path)
            rel_str = str(rel_path)
            
            # Check ignores for top-level or relative path
            if rel_str in ignores or rel_path.parts[0] in ignores:
                continue
                
            repo_files.append(rel_path)

    return sorted(repo_files)

def compare_file(repo_file_path, target_file_path, rel_path_str):
    if not target_file_path.exists():
        return {
            "status": "MISSING_IN_TARGET",
            "rel_path": rel_path_str,
            "repo_file": str(repo_file_path),
            "target_file": str(target_file_path),
            "diff": []
        }

    try:
        with open(repo_file_path, 'r', encoding='utf-8', errors='replace') as rf:
            repo_lines = [line.rstrip('\r\n') for line in rf]
        with open(target_file_path, 'r', encoding='utf-8', errors='replace') as tf:
            target_lines = [line.rstrip('\r\n') for line in tf]
    except Exception as e:
        return {
            "status": "ERROR",
            "rel_path": rel_path_str,
            "repo_file": str(repo_file_path),
            "target_file": str(target_file_path),
            "error": str(e),
            "diff": []
        }

    diff_lines = list(difflib.unified_diff(
        target_lines,
        repo_lines,
        fromfile=f"active (~/{rel_path_str})",
        tofile=f"repo ({rel_path_str})",
        lineterm=""
    ))

    if not diff_lines:
        return {
            "status": "MATCH",
            "rel_path": rel_path_str,
            "repo_file": str(repo_file_path),
            "target_file": str(target_file_path),
            "diff": []
        }
    else:
        return {
            "status": "DIFFERENT",
            "rel_path": rel_path_str,
            "repo_file": str(repo_file_path),
            "target_file": str(target_file_path),
            "diff": diff_lines,
            "diff_count": len(diff_lines)
        }

def format_diff_line(line, use_color=True):
    if not use_color:
        return line
    if line.startswith('---') or line.startswith('+++'):
        return colorize(line, Colors.BOLD, use_color)
    elif line.startswith('@@'):
        return colorize(line, Colors.OKCYAN, use_color)
    elif line.startswith('+'):
        return colorize(line, Colors.OKGREEN, use_color)
    elif line.startswith('-'):
        return colorize(line, Colors.FAIL, use_color)
    return line

def generate_report(results, repo_dir, target_dir, summary_only=False, use_color=True):
    lines = []
    
    header_str = "Dotfiles Active Config Diff Report"
    sub_str = f"Repo Location:   {repo_dir}\nTarget Location: {target_dir}"
    
    lines.append(colorize("=" * 64, Colors.BOLD, use_color))
    lines.append(colorize(header_str.center(64), Colors.HEADER, use_color))
    lines.append(colorize("=" * 64, Colors.BOLD, use_color))
    lines.append(sub_str)
    lines.append("-" * 64)

    # Count statuses
    matches = [r for r in results if r["status"] == "MATCH"]
    different = [r for r in results if r["status"] == "DIFFERENT"]
    missing = [r for r in results if r["status"] == "MISSING_IN_TARGET"]
    errors = [r for r in results if r["status"] == "ERROR"]

    lines.append(colorize("SUMMARY:", Colors.BOLD, use_color))
    lines.append(f"  Total tracked configs checked : {len(results)}")
    lines.append(f"  {colorize('Identical / Matched', Colors.OKGREEN, use_color):<32} : {len(matches)}")
    lines.append(f"  {colorize('Modified / Different', Colors.WARNING, use_color):<32} : {len(different)}")
    lines.append(f"  {colorize('Missing in Active Config', Colors.FAIL, use_color):<32} : {len(missing)}")
    if errors:
        lines.append(f"  {colorize('Errors', Colors.FAIL, use_color):<32} : {len(errors)}")
    lines.append("-" * 64)

    lines.append(colorize("FILE STATUSES:", Colors.BOLD, use_color))
    for r in results:
        status = r["status"]
        path = r["rel_path"]
        if status == "MATCH":
            badge = colorize("[MATCH]", Colors.OKGREEN, use_color)
            lines.append(f"  {badge:<24} {path}")
        elif status == "DIFFERENT":
            badge = colorize("[DIFFERENT]", Colors.WARNING, use_color)
            lines.append(f"  {badge:<24} {path} ({r['diff_count']} diff lines)")
        elif status == "MISSING_IN_TARGET":
            badge = colorize("[MISSING IN TARGET]", Colors.FAIL, use_color)
            lines.append(f"  {badge:<24} {path}")
        elif status == "ERROR":
            badge = colorize("[ERROR]", Colors.FAIL, use_color)
            lines.append(f"  {badge:<24} {path}: {r.get('error')}")

    lines.append("-" * 64)

    if not summary_only and different:
        lines.append("")
        lines.append(colorize("DETAILED UNIFIED DIFFS:", Colors.BOLD, use_color))
        lines.append("=" * 64)

        for r in different:
            lines.append("")
            lines.append(colorize(f"--- Diff for: {r['rel_path']} ---", Colors.OKCYAN, use_color))
            for diff_line in r["diff"]:
                lines.append(format_diff_line(diff_line, use_color))

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Check active config vs repo dotfiles and report diffs.")
    parser.add_argument("-t", "--target", default=os.path.expanduser("~"), help="Target active config directory (default: $HOME)")
    parser.add_argument("-r", "--repo", default=os.path.dirname(os.path.abspath(__file__)), help="Repo directory (default: script location)")
    parser.add_argument("-s", "--summary-only", action="store_true", help="Print summary of file statuses only, without detailed inline diffs")
    parser.add_argument("-f", "--filter", help="Filter check to files matching this substring")
    parser.add_argument("-o", "--output", help="Save plain-text report to specified file")
    parser.add_argument("--json", action="store_true", help="Output report in JSON format")
    parser.add_argument("--color", action="store_true", help="Force colorized terminal output")
    parser.add_argument("--no-color", action="store_true", help="Disable colorized output")

    args = parser.parse_args()

    repo_dir = Path(args.repo).resolve()
    target_dir = Path(args.target).resolve()

    if not repo_dir.exists():
        print(f"Error: Repo directory '{repo_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not target_dir.exists():
        print(f"Error: Target directory '{target_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    use_color = supports_color(force_color=args.color, no_color=args.no_color)
    file_use_color = use_color if not (args.output or args.json) else False

    repo_files = scan_repo_files(repo_dir, DEFAULT_IGNORES)

    if args.filter:
        repo_files = [f for f in repo_files if args.filter in str(f)]

    results = []
    for rel_path in repo_files:
        repo_file_path = repo_dir / rel_path
        target_file_path = target_dir / rel_path
        res = compare_file(repo_file_path, target_file_path, str(rel_path))
        results.append(res)

    if args.json:
        report_json = {
            "repo_dir": str(repo_dir),
            "target_dir": str(target_dir),
            "summary": {
                "total": len(results),
                "matched": len([r for r in results if r["status"] == "MATCH"]),
                "different": len([r for r in results if r["status"] == "DIFFERENT"]),
                "missing_in_target": len([r for r in results if r["status"] == "MISSING_IN_TARGET"]),
                "error": len([r for r in results if r["status"] == "ERROR"])
            },
            "results": results
        }
        json_output = json.dumps(report_json, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as out_f:
                out_f.write(json_output)
            print(f"Report saved to {args.output}")
        else:
            print(json_output)
        return

    report_str = generate_report(results, str(repo_dir), str(target_dir), summary_only=args.summary_only, use_color=file_use_color)

    if args.output:
        plain_report = generate_report(results, str(repo_dir), str(target_dir), summary_only=args.summary_only, use_color=False)
        with open(args.output, "w", encoding="utf-8") as out_f:
            out_f.write(plain_report + "\n")
        print(f"Report saved to {args.output}")

    print(report_str)

if __name__ == "__main__":
    main()
