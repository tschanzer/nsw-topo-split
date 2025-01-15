"""A package for splitting NSW topographic maps into A3 pages"""

import copy
import http.client
import importlib.resources
import json
import pathlib
import urllib.request
from typing import Iterator

import pypdf

URL_PREFIX = (
    'https://portal.spatial.nsw.gov.au/download/NSWTopographicMaps/'
    'DTDB_GeoReferenced_Raster_CollarOn_161070'
)

MM_PER_PT = 25.4/72
COVER_WIDTH_PT = 326
OVERLAP_MM = 20
N_PAGES_X = 3
N_PAGES_Y = 2
PAGE_HEIGHT_PT = pypdf.PaperSize.A3.width
PAGE_WIDTH_PT = pypdf.PaperSize.A3.height

name_dict = json.load(
        importlib.resources.open_text('nsw_topo_split', 'names_25k.json'))


def map_filename(name: str) -> str:
    """
    Convert a map name to its filename, e.g. 'katoomba' -> '8930-1S+KATOOMBA'.
    """

    return name_dict[name]


def download_map(name: str, year: str, out: str) -> None:
    """
    Downloads a 1:25k NSW topo map.

    Args:
        name: The lowercase name of the map, e.g. 'kanangra'.
        year: The publication year of the map, e.g. '2017' or '2022'.
        out: Path for saving the downloaded file.
    """

    url = URL_PREFIX + '/' + year + '/25k/' + map_filename(name) + '.pdf'
    with urllib.request.urlopen(url) as stream:
        with open(out, 'wb') as f:
            f.write(stream.read())


def _mm_to_pt(x_mm: float) -> float:
    return x_mm/MM_PER_PT


def make_cover_page(page: pypdf.PageObject) -> pypdf.PageObject:
    """
    Put the map cover page and legend side-by-side on a portrait page.
    """

    cover = copy.copy(page)
    cover.mediabox.left = cover.mediabox.right - COVER_WIDTH_PT
    cover.mediabox.top /= 2
    cover_page = pypdf.PageObject.create_blank_page(
        width=cover.mediabox.width, height=cover.mediabox.height)
    cover_page.merge_page(cover)
    cover_page.mediabox.left = (
        cover.mediabox.left + (cover.mediabox.width*2 - PAGE_HEIGHT_PT)/2)
    cover_page.mediabox.right = cover_page.mediabox.left + PAGE_HEIGHT_PT
    cover_page.mediabox.bottom = (
        cover.mediabox.bottom + (cover.mediabox.height - PAGE_WIDTH_PT)/2)
    cover_page.mediabox.top = cover_page.mediabox.bottom + PAGE_WIDTH_PT

    legend = copy.copy(page)
    legend_page = pypdf.PageObject.create_blank_page(
        width=legend.mediabox.width, height=legend.mediabox.height)
    legend.mediabox.left = legend.mediabox.right - COVER_WIDTH_PT
    legend.mediabox.bottom = legend.mediabox.top/2
    legend_page.merge_page(legend)
    transformation = pypdf.Transformation().translate(
        tx=legend.mediabox.width, ty=-legend.mediabox.height)
    legend_page.add_transformation(transformation, expand=True)

    cover_page.merge_page(legend_page)
    return cover_page


def make_map_pages(page: pypdf.PageObject) -> Iterator[pypdf.PageObject]:
    """
    Split the map across landscape pages.
    """

    map_ = copy.copy(page)
    page = pypdf.PageObject.create_blank_page(
        width=map_.mediabox.width, height=map_.mediabox.height)
    map_.mediabox.right -= COVER_WIDTH_PT
    page.merge_page(map_)

    overlap_pt = _mm_to_pt(OVERLAP_MM)
    layout_dims = (
        N_PAGES_X*PAGE_WIDTH_PT - (N_PAGES_X-1)*overlap_pt,
        N_PAGES_Y*PAGE_HEIGHT_PT - (N_PAGES_Y-1)*overlap_pt,
    )
    layout_origin = (
        map_.mediabox.left + (map_.mediabox.width - layout_dims[0])/2,
        map_.mediabox.bottom + (map_.mediabox.height - layout_dims[1])/2,
    )

    for j in range(N_PAGES_X):
        page.mediabox.left = (
            layout_origin[0] + j*(PAGE_WIDTH_PT - overlap_pt))
        page.mediabox.right = page.mediabox.left + PAGE_WIDTH_PT
        for i in range(N_PAGES_Y - 1, -1, -1):
            page.mediabox.bottom = (
                layout_origin[1] + i*(PAGE_HEIGHT_PT - overlap_pt))
            page.mediabox.top = page.mediabox.bottom + PAGE_HEIGHT_PT
            yield page
