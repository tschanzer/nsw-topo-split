"""A package for splitting NSW topographic maps across smaller pages"""

import copy
import importlib.resources
import json
import urllib.request
from typing import Iterator

import pypdf

URL_PREFIX = (
    "https://portal.spatial.nsw.gov.au/download/NSWTopographicMaps/"
    "DTDB_GeoReferenced_Raster_CollarOn_161070"
)
MM_PER_PT = 25.4 / 72
COVER_WIDTH_PT = 326

map_names_scales: dict[str, dict[str, str]] = json.load(
    importlib.resources.open_text("nsw_topo_split", "nsw_topo_map_names_scales.json")
)


def download_map(name: str, year: str, out: str) -> None:
    """
    Download a NSW topo map.

    Args:
        name: The lowercase name of the map, e.g. 'kanangra'.
        year: The publication year, e.g. '2017' or '2022'.
        out: Path for saving the downloaded file.
    """

    full_name = map_names_scales[name]["full_name"]
    scale = map_names_scales[name]["scale"]
    url = "/".join([URL_PREFIX, year, scale, full_name]) + ".pdf"
    with urllib.request.urlopen(url) as stream:
        with open(out, "wb") as f:
            f.write(stream.read())


def mm_to_pt(x_mm: float) -> float:
    """Convert millimetres to points."""
    return x_mm / MM_PER_PT


def crop_hide_translate(
    page: pypdf.PageObject,
    *,
    left: float = 0.0,
    right: float = 0.0,
    bottom: float = 0.0,
    top: float = 0.0,
) -> pypdf.PageObject:
    """
    Crop a page, white out the cropped content and translate to (0,0).

    Args:
        page: Page to be cropped.
        left, right, bottom, top: Amount to remove from each side, in
            points (default 0).

    Returns:
        A new page, with the content cropped by the specified amounts,
        and translated so the bottom left corner of the visible content
        at (0,0).
    """

    page = copy.deepcopy(page)
    page.mediabox.left += left
    page.mediabox.right -= right
    page.mediabox.bottom += bottom
    page.mediabox.top -= top

    # Put the bottom left corner of the content at (0,0)
    transformation = pypdf.Transformation().translate(
        tx=-page.mediabox.left, ty=-page.mediabox.bottom
    )
    page.add_transformation(transformation, expand=True)

    # Merge onto a new blank page to white out cropped content
    new_page = pypdf.PageObject.create_blank_page(
        width=page.mediabox.width, height=page.mediabox.height
    )
    new_page.merge_page(page)
    return new_page


def make_cover(original: pypdf.PageObject) -> pypdf.PageObject:
    """
    Put the map title page and legend side-by-side.

    Args:
        original: The original map page.

    Returns:
        A new page with the map title page and legend side-by-side.
    """

    # Grab the title page (bottom right corner of the original map)
    cover = crop_hide_translate(
        original,
        left=original.mediabox.width - COVER_WIDTH_PT,
        top=original.mediabox.height / 2,
    )

    # Grab the legend (top right corner of the original map)
    legend = crop_hide_translate(
        original,
        left=original.mediabox.width - COVER_WIDTH_PT,
        bottom=original.mediabox.height / 2,
    )
    # Move it to the right so it can sit beside the title page
    transformation = pypdf.Transformation().translate(tx=COVER_WIDTH_PT)
    legend.add_transformation(transformation, expand=True)

    cover.merge_page(legend, expand=True)
    return cover


def split_page(
    page: pypdf.PageObject,
    page_size: tuple[float, float],
    n_pages: tuple[int, int],
    overlap: tuple[float, float],
    no_white_space: bool,
) -> Iterator[pypdf.PageObject]:
    """
    Split a page across several smaller pages.

    Args:
        page: The page to be split.
        page_size: (width, height) of the output pages in points.
        n_pages: Number of pages (nx, ny) in each direction.
        overlaps: (overlap_x, overlap_y) between pages in points.
        no_white_space: If True, increase overlaps to eliminate any
            white space on the output pages.

    Yields:
        Output pages in column-major order.
    """

    # Work out the total dimensions of the multi-page layout (accounting
    # for overlaps)
    layout_dims = (
        n_pages[0] * page_size[0] - (n_pages[0] - 1) * overlap[0],
        n_pages[1] * page_size[1] - (n_pages[1] - 1) * overlap[1],
    )
    # If the layout would be larger than the map in either direction,
    # increase the corresponding overlap so this is no longer the case
    if no_white_space:
        if layout_dims[0] > page.mediabox.width and n_pages[0] > 1:
            layout_dims = (page.mediabox.width, layout_dims[1])
            overlap = (
                (n_pages[0] * page_size[0] - layout_dims[0]) / (n_pages[0] - 1),
                overlap[1],
            )
        if layout_dims[1] > page.mediabox.height and n_pages[1] > 1:
            layout_dims = (layout_dims[0], page.mediabox.height)
            overlap = (
                overlap[0],
                (n_pages[1] * page_size[1] - layout_dims[1]) / (n_pages[1] - 1),
            )

    # Work out where to put the bottom left corner of the bottom left
    # page so that the layout is centred on the map
    layout_origin = (
        (page.mediabox.width - layout_dims[0]) / 2,
        (page.mediabox.height - layout_dims[1]) / 2,
    )

    # Produce the output pages in column-major order
    for j in range(n_pages[0]):
        page.mediabox.left = layout_origin[0] + j * (page_size[0] - overlap[0])
        page.mediabox.right = page.mediabox.left + page_size[0]
        for i in range(n_pages[1] - 1, -1, -1):
            page.mediabox.bottom = layout_origin[1] + i * (page_size[1] - overlap[1])
            page.mediabox.top = page.mediabox.bottom + page_size[1]
            yield page


def make_cover_pages(
    original: pypdf.PageObject,
    page_size: tuple[float, float],
    n_pages: tuple[int, int],
    overlap: tuple[float, float],
    no_white_space: bool,
) -> Iterator[pypdf.PageObject]:
    """
    Make a multi-page cover.

    Args:
        original: The original map page.
        page_size: (width, height) of the output pages in points.
        n_pages: Number of pages (nx, ny) in each direction.
        overlaps: (overlap_x, overlap_y) between pages in points.
        no_white_space: If True, increase overlaps to eliminate any
            white space on the output pages.

    Yields:
        Output pages in column-major order.
    """

    cover = make_cover(original)
    yield from split_page(cover, page_size, n_pages, overlap, no_white_space)


def make_map_pages(
    original: pypdf.PageObject,
    page_size: tuple[float, float],
    n_pages: tuple[int, int],
    overlap: tuple[float, float],
    no_white_space: bool,
) -> Iterator[pypdf.PageObject]:
    """
    Make a multi-page cover.

    Args:
        original: The original map page.
        page_size: (width, height) of the output pages in points.
        n_pages: Number of pages (nx, ny) in each direction.
        overlaps: (overlap_x, overlap_y) between pages in points.
        no_white_space: If True, increase overlaps to eliminate any
            white space on the output pages.

    Yields:
        Output pages in column-major order.
    """

    map_ = crop_hide_translate(original, right=COVER_WIDTH_PT)
    yield from split_page(map_, page_size, n_pages, overlap, no_white_space)
