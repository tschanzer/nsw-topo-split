"""A script for splitting NSW topographic maps across smaller pages."""

import argparse
import logging
import pathlib
import sys
import time
from typing import cast

import pymupdf

from nsw_topo_split import (
    choose_margin,
    download_map,
    make_split_cover,
    make_split_map,
    mm_to_pt,
    rasterize,
)

DEFAULTS = {
    "dpi": 300,
    "size": "A3",
    "overlap": [20.0, 20.0],
}

logger = logging.getLogger(__name__)


def main() -> None:  # pylint: disable=too-many-statements
    """Split a NSW topographic map across smaller pages."""
    start_time = time.time()

    parser = argparse.ArgumentParser(
        description="split a NSW topographic map across smaller pages"
    )
    parser.add_argument(
        "mode",
        choices=["map", "cover"],
        help="'map' to make the map pages, 'cover' to make the cover pages",
    )
    parser.add_argument(
        "name",
        type=str.lower,
        help=(
            "map name (case-insensitive), e.g., katoomba; "
            "remember to quote names with spaces"
        ),
    )
    parser.add_argument("year", help="year of publication")
    parser.add_argument(
        "-o",
        "--out",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help=(
            "output directory (default: working directory); "
            "files are output in a subdirectory corresponding to the "
            "publication year and map name, e.g., 2022/8930-1S+KATOOMBA"
        ),
    )
    parser.add_argument(
        "-f",
        "--force-download",
        action="store_true",
        help=(
            "download the original map, even if it already exists "
            "in the output directory"
        ),
    )
    parser.add_argument(
        "-d",
        "--dpi",
        type=int,
        nargs="?",
        const=DEFAULTS["dpi"],
        help=(
            "rasterize the output to the specified resolution (default: "
            f"{DEFAULTS['dpi']:d} DPI); "
            "if this option is not given, then the output will not be rasterized. "
            "WARNING: this may make gridlines hard to see on some map editions. "
            "It will also increase processing time, and file size for mode=map."
        ),
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress log messages"
    )
    format_options = parser.add_argument_group("page format options")
    format_options.add_argument(
        "-s",
        "--size",
        default=DEFAULTS["size"],
        type=str.lower,
        choices=list(pymupdf.paper_sizes().keys()),
        metavar="SIZE",
        help=(
            "page size (case-insensitive; default A3); options are  'A0' through "
            "'A10', 'B0' through 'B10', 'C0' through 'C10', 'Card-4x6', 'Card-5x7', "
            "'Commercial', 'Executive', 'Invoice', 'Ledger', 'Legal', 'Legal-13', "
            "'Letter', 'Monarch' and 'Tabloid-Extra'"
        ),
    )
    format_options.add_argument(
        "-p",
        "--portrait",
        action="store_true",
        help="use portrait layout rather than landscape",
    )
    format_options.add_argument(
        "-n",
        "--n-pages",
        type=int,
        nargs=2,
        metavar=("NX", "NY"),
        help=(
            "horizontal and vertical number of pages "
            "(determined automatically by default)"
        ),
    )
    format_options.add_argument(
        "-l",
        "--overlap",
        type=float,
        nargs=2,
        metavar=("LX", "LY"),
        default=DEFAULTS["overlap"],
        help=(
            "horizontal and vertical overlap between pages in mm "
            f"(default: {DEFAULTS['overlap']})"
        ),
    )
    format_options.add_argument(
        "-w",
        "--allow-whitespace",
        action="store_true",
        help="do not expand overlaps to eliminate white space",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s :: %(message)s",
        level=(logging.WARNING if args.quiet else logging.INFO),
        stream=sys.stdout,
    )
    logging.captureWarnings(True)

    # Get page size in points
    page_size = pymupdf.paper_sizes()[args.size]
    if not args.portrait:
        page_size = (page_size[1], page_size[0])

    # Prepare directories and download map if needed
    master_file = download_map(
        args.name, args.year, base_dir=args.out, force_download=args.force_download
    )

    docsrc = pymupdf.Document(master_file)
    overlap_pt = cast(tuple[float, float], tuple(map(mm_to_pt, args.overlap)))
    margin = choose_margin(args.year)
    if args.mode == "cover":
        logger.info("producing cover page")
        docout = make_split_cover(
            docsrc[0],
            page_size=page_size,
            n_pages=args.n_pages,
            min_overlap=overlap_pt,
            allow_whitespace=args.allow_whitespace,
            margin=margin,
        )
        out_file = master_file.with_stem(master_file.stem + "_cover_" + args.size)
    else:
        logger.info("producing split map")
        docout = make_split_map(
            docsrc[0],
            page_size=page_size,
            n_pages=args.n_pages,
            min_overlap=overlap_pt,
            allow_whitespace=args.allow_whitespace,
            margin=margin,
        )
        out_file = master_file.with_stem(master_file.stem + "_split_" + args.size)

    if args.dpi is not None:
        docout = rasterize(docout, args.dpi)
    logger.info("writing result to %s", out_file)
    docout.ez_save(out_file)
    docsrc.close()
    logger.info("finished in %.2f s", time.time() - start_time)


main()
