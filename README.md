# nsw-topo-split

[![CI](https://img.shields.io/github/actions/workflow/status/tschanzer/nsw-topo-split/ci.yaml?label=CI&logo=github&style=flat-square)](https://github.com/tschanzer/nsw-topo-split/actions/workflows/ci.yaml)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-blue?style=flat-square)](https://github.com/pylint-dev/pylint)
[![type checking: mypy](https://img.shields.io/badge/type%20checking-mypy-blue?style=flat-square)](https://mypy-lang.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-blue?logo=pre-commit&style=flat-square)](https://github.com/pre-commit/pre-commit)

`nsw-topo-split` is a simple Python package that provides a command-line
interface for downloading and evenly splitting NSW Spatial Services topographic
maps across smaller pages. This is useful if you can't get an official hard copy
(e.g., for a new edition), or if you don't have access to a large-format printer
to print the digital maps provided on the [NSW Spatial Collaboration
Portal](https://portal.spatial.nsw.gov.au/portal/apps/webappviewer/index.html?id=06e3c2e0de1e4efda863854048c613c6).

## Quick example
```
python -m nsw_topo_split cover katoomba 2022
python -m nsw_topo_split map katoomba 2022
```
![example](example/example.png)

Maps shown above are © *State of New South Wales (Spatial Services, a business
unit of the Department of Customer Service NSW)*,  reproduced under the terms of
the Creative Commons Attribution 4.0 license.

## Usage
```
usage: python -m nsw_topo_split [-h] [-o OUT] [-s SIZE] [-p]
                                [-n N_PAGES N_PAGES]
                                [-l OVERLAP OVERLAP] [-w] [-f]
                                {map,cover} name year

split a NSW topographic map across smaller pages

positional arguments:
  {map,cover}           'map' to make the map pages, 'cover' to make the cover
                        pages
  name                  lowercase map name with spaces replaced by underscores,
                        e.g., mount_wilson
  year                  year of publication

options:
  -h, --help            show this help message and exit
  -o, --out OUT         output directory (default: working directory). Files are
                        output in a subdirectory corresponding to the
                        publication year and map name, e.g., 2022/katoomba.
  -s, --size SIZE       page size (e.g., A4; default A3)
  -p, --portrait        use portrait layout rather than landscape
  -n, --n-pages N_PAGES N_PAGES
                        horizontal and vertical number of pages (default: [4, 3]
                        for A4, [3, 2] otherwise)
  -l, --overlap OVERLAP OVERLAP
                        horizontal and vertical overlap between pages in mm
                        (default: [20, 20])
  -w, --allow-white-space
                        do not expand overlaps to eliminate white space
  -f, --force-download  download the original map, even if it already exists in
                        the output directory
```

For example, the [quick example](#quick-example) above will produce three PDFs
in `./2022/katoomba`:
- `8930-1S+KATOOMBA.pdf`: The original map downloaded from Spatial Services
- `8930-1S+KATOOMBA_cover_A3.pdf`: A landscape A3 page with the map cover page
    and legend side-by-side
- `8930-1S+KATOOMBA_split_A3.pdf`: The map, split across six landscape A3 pages
  with 20mm overlaps.

When printing double-sided, make sure to choose "flip on long edge".

## Development installation
Clone the repository and navigate to its root directory. Then, in a clean
virtual environment, run
```bash
pip install -r requirements/dev.txt  # for reproducibility
pre-commit install
pip install -e .
```
