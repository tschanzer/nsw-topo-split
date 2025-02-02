"""A script for splitting NSW topographic maps across smaller pages."""

import argparse
import pathlib

import pymupdf

from nsw_topo_split import (
    COVER_WIDTH_PT,
    download_map,
    make_cover,
    map_names_scales,
    mm_to_pt,
    posterize,
    rasterize,
)


def main() -> None:
    """Split a NSW topographic map across smaller pages."""

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
        help=(
            "lowercase map name with spaces replaced by underscores, "
            "e.g., mount_wilson"
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
            "publication year and map name, e.g., 2022/katoomba"
        ),
    )
    parser.add_argument(
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
    parser.add_argument(
        "-p",
        "--portrait",
        action="store_true",
        help="use portrait layout rather than landscape",
    )
    parser.add_argument(
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
    parser.add_argument(
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
    parser.add_argument(
        "-w",
        "--allow-white-space",
        action="store_true",
        help="do not expand overlaps to eliminate white space",
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
    args = parser.parse_args()

    # Get page size in points
    page_size = pymupdf.paper_sizes()[args.size]
    if not args.portrait:
        page_size = (page_size[1], page_size[0])

    # Determine number of pages along each axis
    if args.n_pages is None:
        if (args.size, args.mode) == ("a4", "cover"):
            args.n_pages = [1, 2]
        elif (args.size, args.mode) == ("a4", "map"):
            args.n_pages = [4, 3]
        elif (args.size, args.mode) == ("a3", "cover"):
            args.n_pages = [1, 1]
        elif (args.size, args.mode) == ("a3", "map"):
            args.n_pages = [3, 2]
        else:
            raise RuntimeError(
                "-n/--n-pages must be specified for paper sizes other than A4 and A3"
            )

    # Prepare directories and download map if needed
    out_dir = args.out / args.year / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    full_name = map_names_scales[args.name]["full_name"]
    master_file = (out_dir / full_name).with_suffix(".pdf")
    if args.force_download or not master_file.exists():
        download_map(args.name, args.year, master_file)

    docsrc = pymupdf.Document(master_file)
    overlap_mm = (mm_to_pt(args.overlap[0]), mm_to_pt(args.overlap[1]))
    if args.mode == "cover":
        cover = make_cover(docsrc)
        docout = posterize(
            cover,
            args.n_pages,
            page_size,
            overlap=overlap_mm,
            no_white_space=(not args.allow_white_space),
        )
        out_file = (out_dir / (full_name + "_cover_" + args.size)).with_suffix(".pdf")
    else:
        docout = posterize(
            docsrc,
            args.n_pages,
            page_size,
            overlap=overlap_mm,
            clip={"right": COVER_WIDTH_PT},
            no_white_space=(not args.allow_white_space),
        )
        out_file = (out_dir / (full_name + "_split_" + args.size)).with_suffix(".pdf")

    if args.dpi is not None:
        docout = rasterize(docout, args.dpi)
    docout.ez_save(out_file)
    docsrc.close()


main()
