"""A script for splitting NSW topographic maps across smaller pages."""

import argparse
import pathlib

import pypdf

from nsw_topo_split import (
    download_map,
    make_cover_pages,
    make_map_pages,
    map_names_scales,
    mm_to_pt,
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
            "output directory (default: working directory). "
            "Files are output in a subdirectory corresponding to the "
            "publication year and map name, e.g., 2022/katoomba."
        ),
    )
    parser.add_argument(
        "-s", "--size", default="A3", help="page size (e.g., A4; default A3)"
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
        default=[20.0, 20.0],
        help=(
            "horizontal and vertical overlap between pages in mm " "(default: [20, 20])"
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
    args = parser.parse_args()

    full_name = map_names_scales[args.name]["full_name"]
    page_size = getattr(pypdf.PaperSize, args.size)
    if not args.portrait:
        page_size = (page_size[1], page_size[0])
    if args.n_pages is None:
        if (args.size, args.mode) == ("A4", "cover"):
            args.n_pages = [1, 2]
        elif (args.size, args.mode) == ("A4", "map"):
            args.n_pages = [4, 3]
        elif (args.size, args.mode) == ("A3", "cover"):
            args.n_pages = [1, 1]
        elif (args.size, args.mode) == ("A3", "map"):
            args.n_pages = [3, 2]
        else:
            raise RuntimeError(
                "-n/--n-pages must be specified for paper sizes other than A4 and A3"
            )

    out_dir = args.out / args.year / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    master_file = (out_dir / full_name).with_suffix(".pdf")
    if args.force_download or not master_file.exists():
        download_map(args.name, args.year, master_file)

    reader = pypdf.PdfReader(master_file)
    if args.mode == "cover":
        make_pages = make_cover_pages
        out_file = (out_dir / (full_name + "_cover_" + args.size)).with_suffix(".pdf")
    else:
        make_pages = make_map_pages
        out_file = (out_dir / (full_name + "_split_" + args.size)).with_suffix(".pdf")

    writer = pypdf.PdfWriter()
    pages = make_pages(
        reader.pages[0],
        page_size,
        args.n_pages,
        (mm_to_pt(args.overlap[0]), mm_to_pt(args.overlap[1])),
        not args.allow_white_space,
    )
    for page in pages:
        writer.add_page(page)
    writer.compress_identical_objects()
    with open(out_file, "wb") as f:
        writer.write(f)
    reader.close()


main()
