"""A script for splitting NSW topographic maps into A3 pages."""

import argparse
import pathlib

import pypdf

from nsw_topo_split import (
    download_map,
    make_cover_page,
    make_map_pages,
    map_filename
)


def main():
    """Split a NSW topographic map into A3 pages."""

    parser = argparse.ArgumentParser(
        description='Split a NSW topographic map into A3 pages')
    parser.add_argument('name', help='Lowercase map name, e.g. kanangra')
    parser.add_argument('year', help='Year of publication')
    parser.add_argument(
        '-o',
        '--out',
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help='Output directory (default: current working directory)',
    )
    args = parser.parse_args()

    out = (args.out/map_filename(args.name)).with_suffix('.pdf')
    download_map(args.name, args.year, out)

    reader = pypdf.PdfReader(out)
    writer = pypdf.PdfWriter()
    writer.add_page(make_cover_page(reader.pages[0]))
    out = (args.out/(map_filename(args.name) + '_cover')).with_suffix('.pdf')
    with open(out, 'wb') as f:
        writer.write(f)

    writer = pypdf.PdfWriter()
    for page in make_map_pages(reader.pages[0]):
        writer.add_page(page)
    out = (args.out/(map_filename(args.name) + '_split')).with_suffix('.pdf')
    with open(out, 'wb') as f:
        writer.write(f)

    reader.close()


main()
