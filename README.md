# nsw-topo-split

`nsw-topo-split` is a simple Python package that provides a command-line
interface for downloading and evenly splitting NSW Spatial Services topographic
maps into A3 pages with 20mm overlaps. This is useful if you can't get an
official hard copy (e.g., for a new edition), or if you don't have access to a
large-format printer to print the GeoPDFs provided on the [NSW Spatial
Collaboration
Portal](https://portal.spatial.nsw.gov.au/portal/apps/webappviewer/index.html?id=06e3c2e0de1e4efda863854048c613c6).

## Quick example
```
python -m nsw_topo_split katoomba 2022
```
![example](example.png)

Maps shown above are © *State of New South Wales (Spatial Services, a business
unit of the Department of Customer Service NSW)*,  reproduced under the terms of
the Creative Commons Attribution 4.0 license.

## Dependencies
- `pypdf`

## Installation
1. Clone the repository
2. Navigate to the repository directory and install using `pip install .`

## Usage
```
usage: python -m nsw_topo_split [-h] [-o OUT] name year

Split a NSW topographic map into A3 pages

positional arguments:
  name           Lowercase map name, e.g. kanangra
  year           Year of publication

options:
  -h, --help     show this help message and exit
  -o, --out OUT  Output directory (default: current working directory)
```

For example, `python -m nsw_topo_split katoomba 2022` will produce three PDFs in
the current working directory:
- `8930-1S+KATOOMBA.pdf`: The original map downloaded from Spatial Services
- `8930-1S+KATOOMBA_cover.pdf`: A portrait A3 page with the map cover page
    and legend side-by-side
- `8930-1S+KATOOMBA_split.pdf`: The map, split across six landscape A3 pages
  with 20mm overlaps.

When printing double-sided, make sure to choose "flip on long edge".
