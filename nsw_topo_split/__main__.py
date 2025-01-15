"""A script for splitting NSW topographic maps into A3 pages."""

import argparse
import pathlib

import pypdf

from nsw_topo_split import make_cover_page, make_map_pages


def main():
    """Split a NSW topographic map into A3 pages."""

    parser = argparse.ArgumentParser(
        description='Split a NSW topographic map into A3 pages')
    parser.add_argument(
        'file', type=pathlib.Path, help='Map file (PDF)')
    parser.add_argument(
        '-o',
        '--out',
        type=pathlib.Path,
        help='Output directory (default: file.parent)',
    )
    args = parser.parse_args()
    if args.out is not None:
        if not args.out.is_dir():
            raise ValueError('out must be a directory')
        out_dir = args.out
    else:
        out_dir = args.file.parent


    reader = pypdf.PdfReader(args.file)
    writer = pypdf.PdfWriter()
    writer.add_page(make_cover_page(reader.pages[0]))
    out = (out_dir/(args.file.stem + '_cover')).with_suffix(args.file.suffix)
    with open(out, 'wb') as f:
        writer.write(f)

    writer = pypdf.PdfWriter()
    for page in make_map_pages(reader.pages[0]):
        writer.add_page(page)
    out = (out_dir/(args.file.stem + '_split')).with_suffix(args.file.suffix)
    with open(out, 'wb') as f:
        writer.write(f)

    reader.close()


main()
