"""A package for splitting NSW topographic maps across smaller pages"""

import importlib.resources
import json
import urllib.request

import pymupdf

URL_PREFIX = (
    "https://portal.spatial.nsw.gov.au/download/NSWTopographicMaps/"
    "DTDB_GeoReferenced_Raster_CollarOn_161070"
)
MM_PER_PT = 25.4 / 72
COVER_WIDTH_PT = 326

_names_scales_file = (
    importlib.resources.files("nsw_topo_split") / "nsw_topo_map_names_scales.json"
)
map_names_scales: dict[str, dict[str, str]] = json.load(
    _names_scales_file.open("r", encoding="utf-8")
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


def posterize(  # pylint: disable=too-many-locals,too-many-arguments
    docsrc: pymupdf.Document,
    n_pages: tuple[int, int],
    page_size: tuple[float, float],
    *,
    overlap: float | tuple[float, float] = 0.0,
    clip: dict[str, float] | None = None,
    no_white_space: bool = True,
) -> pymupdf.Document:
    """
    Posterize a PDF.

    Args:
        docsrc: Document to posterize (the first page will be used).
        n_pages: Number of poster pages along the (horizontal, vertical) axes.
        page_size: (width, height) of the output pages, in points.
        overlap: (horizontal, vertical) overlap between output pages, in points.
            If only one value is given, the overlaps are assumed to be equal.
        clip: Mapping from "left", "right", "top", "bottom" to the respective
            amounts, in points, to clip from `docsrc` before posterizing. Default
            is 0 on all sides.
        no_white_space: If True, increase overlaps to eliminate any white space
            on the output pages.

    Returns:
        Document containing the poster pages in column-major order.
    """

    if isinstance(overlap, float):
        overlap = (overlap,) * 2
    if clip is None:
        clip = {}
    for side in ["left", "right", "top", "bottom"]:
        clip.setdefault(side, 0.0)

    # Express the clip rectangle relative to the source page
    pagesrc = docsrc[0]
    clip_rect = pagesrc.bound() + (
        clip["left"],
        clip["top"],
        -clip["right"],
        -clip["bottom"],
    )

    # Express the layout origin relative to the source page
    layout_size = (
        n_pages[0] * page_size[0] - (n_pages[0] - 1) * overlap[0],
        n_pages[1] * page_size[1] - (n_pages[1] - 1) * overlap[1],
    )
    if no_white_space:
        if layout_size[0] > clip_rect.width and n_pages[0] > 1:
            layout_size = (clip_rect.width, layout_size[1])
            overlap = (
                (n_pages[0] * page_size[0] - layout_size[0]) / (n_pages[0] - 1),
                overlap[1],
            )
        if layout_size[1] > clip_rect.height and n_pages[1] > 1:
            layout_size = (layout_size[0], clip_rect.height)
            overlap = (
                overlap[0],
                (n_pages[1] * page_size[1] - layout_size[1]) / (n_pages[1] - 1),
            )
    pad = (
        (layout_size[0] - clip_rect.width) / 2,
        (layout_size[1] - clip_rect.height) / 2,
    )
    layout_origin = (clip["left"] - pad[0], clip["top"] - pad[1])

    docout = pymupdf.Document()
    for j in range(n_pages[0]):
        for i in range(n_pages[1]):
            # Express the poster page origin relative to the source page
            page_origin = (
                layout_origin[0] + j * (page_size[0] - overlap[0]),
                layout_origin[1] + i * (page_size[1] - overlap[1]),
            )
            # Express the clip rectangle relative to the poster page
            clip_rect_rel_page = clip_rect - (
                page_origin[0],
                page_origin[1],
                page_origin[0],
                page_origin[1],
            )
            pageout: pymupdf.Page = docout.new_page(
                width=page_size[0], height=page_size[1]
            )
            pageout.show_pdf_page(clip_rect_rel_page, docsrc, clip=clip_rect)

    return docout


def make_cover(docsrc: pymupdf.Document) -> pymupdf.Document:
    """
    Put the map title page and legend side-by-side.

    Args:
        docsrc: The original map.

    Returns:
        New document containing a single page with the map title page and legend
        side-by-side.
    """

    pagesrc = docsrc[0]
    docout = pymupdf.Document()
    pageout: pymupdf.Page = docout.new_page(
        width=2 * COVER_WIDTH_PT, height=pagesrc.bound().height
    )
    # Title page (bottom right corner of map sheet)
    pageout.show_pdf_page(
        pymupdf.Rect(0, 0, COVER_WIDTH_PT, pageout.bound().height),
        docsrc,
        clip=pymupdf.Rect(
            pagesrc.bound().width - COVER_WIDTH_PT,
            pagesrc.bound().height / 2,
            pagesrc.bound().bottom_right,
        ),
    )
    # Legend (top right corner of map sheet)
    pageout.show_pdf_page(
        pymupdf.Rect(COVER_WIDTH_PT, 0, 2 * COVER_WIDTH_PT, pageout.bound().height),
        docsrc,
        clip=pymupdf.Rect(
            pagesrc.bound().width - COVER_WIDTH_PT,
            0,
            pagesrc.bound().width,
            pagesrc.bound().height / 2,
        ),
    )
    return docout
