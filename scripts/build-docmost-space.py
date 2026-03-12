#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "docmost-space"
INLINE_LINK_PATTERN = re.compile(r"(?P<prefix>!?)\[(?P<label>[^\]]+)\]\((?P<target>[^)]+)\)")
BACK_LINK_PATTERN = re.compile(
    r"^\[← Back to README\]\((?:\.\./README\.md|Home\.md)\)\s*$",
    re.MULTILINE,
)
HTML_WRAPPER_LINES = {"<div align=\"center\">", "</div>"}
BADGE_LINE_PATTERN = re.compile(r"^\[!\[[^\]]+\]\([^)]+\)\]\([^)]+\)\s*$")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
DETAILS_OPEN_PATTERN = re.compile(r"^\s*<details>\s*$")
DETAILS_CLOSE_PATTERN = re.compile(r"^\s*</details>\s*$")
SUMMARY_PATTERN = re.compile(r"^\s*<summary>(.*?)</summary>\s*$")
CALLOUT_PATTERN = re.compile(r"^>\s*\[!([A-Z]+)\]\s*$", re.MULTILINE)


@dataclass(frozen=True)
class SourceDocument:
    source_path: Path
    output_path: Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def heading_title(path: Path) -> str:
    for line in read_text(path).splitlines():
        match = re.match(r"^#\s+(.*\S)\s*$", line)
        if match:
            return cleanup_title(match.group(1))
    return cleanup_title(path.stem.replace("-", " "))


def cleanup_title(title: str) -> str:
    title = title.strip()
    title = re.sub(r"[^\w\s&+-]", "", title, flags=re.UNICODE)
    title = re.sub(r"\s+", " ", title).strip()
    return title or "Untitled"


def bundle_documents() -> list[SourceDocument]:
    documents = [
        SourceDocument(
            source_path=REPO_ROOT / "README.md",
            output_path=Path("Home.md"),
        )
    ]

    for path in sorted((REPO_ROOT / "docs").glob("*.md")):
        if path.parent.name == "docmost-space":
            continue
        title = heading_title(path)
        documents.append(
            SourceDocument(
                source_path=path,
                output_path=Path(f"{title}.md"),
            )
        )

    return documents


def rewrite_target(
    target: str,
    *,
    source_path: Path,
    source_output_path: Path,
    output_map: dict[Path, Path],
) -> str:
    stripped = target.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("<"):
        return target
    if SCHEME_PATTERN.match(stripped):
        return target

    target_path_part, anchor = (stripped.split("#", 1) + [""])[:2]
    if not target_path_part:
        return target

    resolved_source_target = (source_path.parent / target_path_part).resolve()
    try:
        resolved_repo_target = resolved_source_target.relative_to(REPO_ROOT)
    except ValueError:
        return target

    repo_target_path = REPO_ROOT / resolved_repo_target
    output_target = output_map.get(repo_target_path)
    if output_target is None:
        return target

    rewritten = Path(
        Path(
            rebase_relative_path(
                source_output_path.parent,
                output_target,
            )
        )
    ).as_posix()
    if anchor:
        rewritten = f"{rewritten}#{anchor}"
    return rewritten


def rebase_relative_path(from_dir: Path, to_path: Path) -> str:
    from_parts = from_dir.parts
    to_parts = to_path.parts

    common = 0
    for left, right in zip(from_parts, to_parts):
        if left != right:
            break
        common += 1

    upward = [".."] * (len(from_parts) - common)
    downward = list(to_parts[common:])
    if not upward and not downward:
        return "."
    return "/".join(upward + downward)


def rewrite_links(
    text: str,
    *,
    source_path: Path,
    source_output_path: Path,
    output_map: dict[Path, Path],
) -> str:
    def replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        label = match.group("label")
        target = match.group("target")
        rewritten_target = rewrite_target(
            target,
            source_path=source_path,
            source_output_path=source_output_path,
            output_map=output_map,
        )
        return f"{prefix}[{label}]({rewritten_target})"

    return INLINE_LINK_PATTERN.sub(replace, text)


def normalize_docmost_markup(text: str) -> str:
    lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if DETAILS_OPEN_PATTERN.match(stripped) or DETAILS_CLOSE_PATTERN.match(stripped):
            continue

        summary_match = SUMMARY_PATTERN.match(stripped)
        if summary_match:
            summary = re.sub(r"<[^>]+>", "", summary_match.group(1)).strip()
            if summary:
                lines.append(f"### {summary}")
            continue

        lines.append(line)

    text = "\n".join(lines)
    return CALLOUT_PATTERN.sub(lambda match: f"> **{match.group(1).title()}:**", text)


def normalize_markdown(
    document: SourceDocument,
    *,
    output_map: dict[Path, Path],
) -> str:
    text = read_text(document.source_path)
    text = rewrite_links(
        text,
        source_path=document.source_path,
        source_output_path=document.output_path,
        output_map=output_map,
    )

    lines = []
    for line in text.splitlines():
        if line.strip() in HTML_WRAPPER_LINES:
            continue
        if BADGE_LINE_PATTERN.match(line.strip()):
            continue
        lines.append(line)

    text = "\n".join(lines).strip() + "\n"
    text = BACK_LINK_PATTERN.sub("", text)
    text = normalize_docmost_markup(text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if document.source_path == REPO_ROOT / "README.md":
        preface = (
            "<!-- Generated by scripts/build-docmost-space.py. Edit README.md and docs/*.md instead. -->\n\n"
            "# Home\n\n"
            "This space mirrors the repository documentation in a Docmost-friendly layout.\n\n"
        )

        first_heading = next(iter(HEADING_PATTERN.finditer(text)), None)
        if first_heading:
            text = text[first_heading.end() :].lstrip()
        text = preface + text
    else:
        text = (
            "<!-- Generated by scripts/build-docmost-space.py. Edit the source page in docs/ instead. -->\n\n"
            + text
        )

    return text


def rendered_bundle() -> dict[Path, str]:
    documents = bundle_documents()
    output_map = {doc.source_path: doc.output_path for doc in documents}
    rendered: dict[Path, str] = {}
    manifest_lines = [
        "<!-- Generated by scripts/build-docmost-space.py. -->",
        "# Import Instructions",
        "",
        "Import this directory into Docmost as Markdown pages.",
        "",
        "Generated pages:",
        "",
    ]

    for document in documents:
        rendered[document.output_path] = normalize_markdown(document, output_map=output_map)
        manifest_lines.append(f"- `{document.output_path.as_posix()}`")

    rendered[Path("Import Instructions.md")] = "\n".join(manifest_lines).rstrip() + "\n"
    return rendered


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def existing_markdown_files(output_dir: Path) -> set[Path]:
    if not output_dir.exists():
        return set()
    return {
        path.relative_to(output_dir)
        for path in output_dir.rglob("*.md")
        if path.is_file()
    }


def write_bundle(output_dir: Path, expected: dict[Path, str]) -> None:
    current_files = existing_markdown_files(output_dir)
    expected_files = set(expected)

    for stale_path in sorted(current_files - expected_files, reverse=True):
        absolute = output_dir / stale_path
        absolute.unlink()
        cleanup_empty_parents(absolute.parent, output_dir)

    for relative_path, content in expected.items():
        write_text(output_dir / relative_path, content)


def cleanup_empty_parents(path: Path, stop_dir: Path) -> None:
    current = path
    while current != stop_dir and current.exists():
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def check_bundle(output_dir: Path, expected: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    actual_files = existing_markdown_files(output_dir)
    expected_files = set(expected)

    missing = sorted(expected_files - actual_files)
    extra = sorted(actual_files - expected_files)

    if missing:
        errors.append(
            "missing generated pages: " + ", ".join(path.as_posix() for path in missing)
        )
    if extra:
        errors.append(
            "unexpected files in bundle: " + ", ".join(path.as_posix() for path in extra)
        )

    for relative_path in sorted(expected_files & actual_files):
        current = read_text(output_dir / relative_path)
        if current != expected[relative_path]:
            errors.append(
                f"outdated generated page: {relative_path.as_posix()} "
                f"(expected {fingerprint(expected[relative_path])}, got {fingerprint(current)})"
            )

    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or verify the import-ready Docmost markdown bundle."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the generated bundle is missing or stale instead of writing it.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for generated files (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_dir = args.output_dir.resolve()
    expected = rendered_bundle()

    if args.check:
        errors = check_bundle(output_dir, expected)
        if errors:
            print("docmost bundle check failed:\n", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(f"docmost bundle is up to date: {output_dir}")
        return 0

    write_bundle(output_dir, expected)
    print(f"docmost bundle written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
