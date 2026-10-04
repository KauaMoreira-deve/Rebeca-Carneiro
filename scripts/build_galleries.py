"""Render every portfolio PDF page and build the gallery data file.

Usage:
    python -X utf8 scripts/build_galleries.py --inspect
    python -X utf8 scripts/build_galleries.py --render

PyMuPDF is expected either in the active Python environment or in
``tmp/pdf-tools`` (the local, disposable tool directory used by Codex).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
GALLERIES_DIR = ASSETS_DIR / "galleries"
LOCAL_TOOLS_DIR = ROOT / "tmp" / "pdf-tools"
COVER_PAGE_BY_SLUG = {
    # A primeira página repete a capa de EDITORIAIS; a página 7 diferencia o card.
    "water-lilies-monet": 7,
}

if LOCAL_TOOLS_DIR.exists():
    sys.path.insert(0, str(LOCAL_TOOLS_DIR))

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError as exc:  # pragma: no cover - depends on local tooling
        raise SystemExit(
            "PyMuPDF is required. Install it with: "
            "python -m pip install --target tmp/pdf-tools PyMuPDF"
        ) from exc


EXPORT_SUFFIX_RE = re.compile(r"[\s_-]*\d{8}_\d{6}_\d{4}$")
SPACE_RE = re.compile(r"\s+")


def clean_title(pdf_path: Path) -> str:
    """Remove the export timestamp and normalize accidental spacing."""

    title = EXPORT_SUFFIX_RE.sub("", pdf_path.stem)
    return SPACE_RE.sub(" ", title).strip(" _-")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "projeto"


def pdf_paths() -> list[Path]:
    return sorted(ASSETS_DIR.glob("*.pdf"), key=lambda item: item.name.casefold())


def inspect_pdfs() -> list[dict]:
    report: list[dict] = []

    for pdf_path in pdf_paths():
        with pymupdf.open(pdf_path) as document:
            page_sizes = []
            image_counts = []

            for page in document:
                page_sizes.append(
                    {
                        "width": round(page.rect.width, 1),
                        "height": round(page.rect.height, 1),
                    }
                )
                image_counts.append(len(page.get_images(full=True)))

            report.append(
                {
                    "file": pdf_path.name,
                    "title": clean_title(pdf_path),
                    "slug": slugify(clean_title(pdf_path)),
                    "pages": document.page_count,
                    "pageSizes": page_sizes,
                    "embeddedImagesPerPage": image_counts,
                }
            )

    return report


def render_page(
    page: pymupdf.Page,
    destination: Path,
    target_width: int,
    quality: int,
) -> None:
    scale = max(1.0, target_width / page.rect.width)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    destination.write_bytes(pixmap.tobytes("jpg", jpg_quality=quality))


def render_pdfs(target_width: int) -> list[dict]:
    GALLERIES_DIR.mkdir(parents=True, exist_ok=True)
    galleries: list[dict] = []
    sources = pdf_paths()

    for index, pdf_path in enumerate(sources, start=1):
        title = clean_title(pdf_path)
        slug = slugify(title)
        gallery_dir = GALLERIES_DIR / slug
        gallery_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir = gallery_dir / "miniaturas"
        thumbs_dir.mkdir(parents=True, exist_ok=True)

        with pymupdf.open(pdf_path) as document:
            images = []

            for page_number, page in enumerate(document, start=1):
                filename = f"pagina-{page_number:02d}.jpg"
                thumb_filename = f"pagina-{page_number:02d}.jpg"
                destination = gallery_dir / filename
                render_page(page, destination, target_width, quality=84)
                render_page(
                    page,
                    thumbs_dir / thumb_filename,
                    target_width=260,
                    quality=76,
                )
                images.append(
                    {
                        "src": f"assets/galleries/{slug}/{filename}",
                        "thumb": (
                            f"assets/galleries/{slug}/miniaturas/{thumb_filename}"
                        ),
                        "alt": f"{title} - página {page_number} de {document.page_count}",
                    }
                )

            cover_filename = "capa.jpg"
            cover_page_number = COVER_PAGE_BY_SLUG.get(slug, 1)
            render_page(
                document[cover_page_number - 1],
                gallery_dir / cover_filename,
                target_width=720,
                quality=80,
            )

            galleries.append(
                {
                    "id": slug,
                    "title": title,
                    "index": index,
                    "pageCount": document.page_count,
                    "cover": f"assets/galleries/{slug}/{cover_filename}",
                    "images": images,
                }
            )

        print(
            f"[{index:02d}/{len(sources):02d}] {title}: {len(images)} páginas",
            flush=True,
        )

    data = json.dumps(galleries, ensure_ascii=False, indent=2)
    manifest = (
        "// Gerado por scripts/build_galleries.py a partir dos PDFs em assets.\n"
        f"window.PORTFOLIO_GALLERIES = {data};\n"
    )
    (GALLERIES_DIR / "gallery-data.js").write_text(manifest, encoding="utf-8")
    return galleries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true", help="Print PDF metadata as JSON")
    mode.add_argument("--render", action="store_true", help="Render pages and write gallery data")
    parser.add_argument(
        "--width",
        type=int,
        default=1600,
        help="Rendered image width in pixels (default: 1600)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.inspect:
        print(json.dumps(inspect_pdfs(), ensure_ascii=False, indent=2))
        return

    galleries = render_pdfs(args.width)
    total_pages = sum(item["pageCount"] for item in galleries)
    print(f"Concluído: {len(galleries)} galerias e {total_pages} imagens.")


if __name__ == "__main__":
    main()
