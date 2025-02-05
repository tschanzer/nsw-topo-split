"""A script for splitting NSW topographic maps across smaller pages."""

import argparse
import logging
import pathlib
import sys
import time

import pymupdf

from nsw_topo_split import (
    COVER_WIDTH_PT,
    download,
    get_map_url,
    make_cover,
    make_poster,
    mm_to_pt,
    rasterize,
)

logger = logging.getLogger(__name__)

N_PAGES_DEFAULTS = {
    ("a4", "cover"): [1, 2],
    ("a4", "map"): [4, 3],
    ("a3", "cover"): [1, 1],
    ("a3", "map"): [3, 2],
}


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
        const=300,
        help=(
            "rasterize the output to the specified resolution (default: 300 DPI); "
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
        default="A3",
        type=str.lower,
        choices=list(pymupdf.paper_sizes().keys()),
        metavar="SIZE",
        help=(
            "page size (case-insensitive); options are  'A0' through 'A10', "
            "'B0' through 'B10', 'C0' through 'C10', 'Card-4x6', 'Card-5x7', "
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
            "(default: [4, 3] for A4 map, [1, 2] for A4 cover, "
            "[3, 2] for A3 map, [1, 1] for A3 cover, otherwise undefined)"
        ),
    )
    format_options.add_argument(
        "-l",
        "--overlap",
        type=float,
        nargs=2,
        metavar=("LX", "LY"),
        default=[20.0, 20.0],
        help=(
            "horizontal and vertical overlap between pages in mm (default: [20, 20])"
        ),
    )
    format_options.add_argument(
        "-w",
        "--allow-white-space",
        action="store_true",
        help="do not expand overlaps to eliminate white space",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s :: %(message)s",
        level=(logging.WARNING if args.quiet else logging.INFO),
        stream=sys.stdout,
    )

    # Get page size in points
    page_size = pymupdf.paper_sizes()[args.size]
    if not args.portrait:
        page_size = (page_size[1], page_size[0])

    # Determine number of pages along each axis
    if args.n_pages is None:
        try:
            args.n_pages = N_PAGES_DEFAULTS[args.size, args.mode]
        except KeyError as e:
            raise RuntimeError(
                "-n/--n-pages must be specified for paper sizes other than A4 and A3"
            ) from e

    # Prepare directories and download map if needed
    url = get_map_url(args.name, args.year)
    filename = url.split("/")[-1]
    out_dir: pathlib.Path = args.out / args.year / filename.removesuffix(".pdf")
    out_dir.mkdir(parents=True, exist_ok=True)
    master_file = out_dir / filename
    if args.force_download or not master_file.exists():
        download(url, master_file)
    else:
        logger.info("using existing map at %s", master_file)

    docsrc = pymupdf.Document(master_file)
    overlap_mm = (mm_to_pt(args.overlap[0]), mm_to_pt(args.overlap[1]))
    if args.mode == "cover":
        logger.info("producing cover page")
        cover = make_cover(docsrc)
        docout = make_poster(
            cover,
            args.n_pages,
            page_size,
            overlap=overlap_mm,
            no_white_space=(not args.allow_white_space),
        )
        out_file = master_file.with_stem(master_file.stem + "_cover_" + args.size)
    else:
        logger.info("producing split map")
        docout = make_poster(
            docsrc,
            args.n_pages,
            page_size,
            overlap=overlap_mm,
            clip={"right": COVER_WIDTH_PT},
            no_white_space=(not args.allow_white_space),
        )
        out_file = master_file.with_stem(master_file.stem + "_split_" + args.size)

    if args.dpi is not None:
        docout = rasterize(docout, args.dpi)
    logger.info("writing result to %s", out_file)
    docout.ez_save(out_file)
    docsrc.close()
    logger.info("finished in %.2f s", time.time() - start_time)


main()
