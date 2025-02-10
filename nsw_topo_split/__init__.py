"""A package for splitting NSW topographic maps across smaller pages"""

import json
import logging
import pathlib
import re
import urllib.parse
import urllib.request

import pymupdf

ENDPOINT = (
    "https://portal.spatial.nsw.gov.au/server/rest/services/Hosted/TopoMapIndex/"
    "FeatureServer/0/query"
)
MAP_VIEWER_URL = (
    "https://portal.spatial.nsw.gov.au/portal/home/webmap/viewer.html"
    "?useExisting=1&layers=585654eb02d449cfbc46ed801303b9cf"
)
MM_PER_PT = 25.4 / 72
COVER_WIDTH_PT = 326

COLLAR_REGEX = re.compile(
    r"-?[0-9]+[º°]\s*[0-9]+'"  # match lat/lon coordinates
    r"|m[NESW]"  # match grid coordinates
    r"|000m"  # match grid coordinates
    r"|\(MGA(?:\s[0-9]+)?\)"  # match the "(MGA XX)" that accompanies grid coordinates
)

logger = logging.getLogger(__name__)


def get_map_url(name: str, year: str) -> str:
    """
    Query the ArcGIS API to get the URL of a NSW Spatial Services topo map.

    The map index dataset and API docs can be found at the following URL:
    https://portal.spatial.nsw.gov.au/server/rest/services/Hosted/TopoMapIndex/FeatureServer

    Args:
        name: Name of the map (case-insensitive), e.g., 'katoomba' or
            'mount wilson'.
        year: Publication year of the map, e.g., '2017'.

    Returns:
        The URL from which the map can be downloaded.
    """

    params = urllib.parse.urlencode(
        {
            "where": f"tilename = '{name.upper()}'",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    with urllib.request.urlopen(f"{ENDPOINT}?{params}") as response:
        data = json.load(response)

    # The map URLs are stored in a JSON object with undescriptive keys like
    # 'collaron_7", so we have to inspect the list of fields to work out which
    # one corresponds to the requested publication year.
    found_year = False
    for field in data["fields"]:
        if field["alias"] == f"CollarOn_{year}":
            url_key = field["name"]
            found_year = True
            break
    if not found_year:
        raise ValueError(
            f"Publication year '{year}' not found in database. "
            f"Please check the available years at {MAP_VIEWER_URL}."
        )

    if not data["features"]:
        # If the feature list is empty, there is no map with that name
        raise ValueError(
            f"Map '{name}' not found in database. "
            f"Please check the available maps at {MAP_VIEWER_URL}."
        )
    map_url: str = data["features"][0]["attributes"][url_key]
    return map_url


def download(url: str, outfile: str | pathlib.Path) -> None:
    """
    Download a file.

    Args:
        url: URL to download from.
        outfile: Path for saving the file.
    """

    logger.info("downloading from %s", url)
    with urllib.request.urlopen(url) as stream, open(outfile, "wb") as f:
        logger.info("writing downloaded file to %s", outfile)
        f.write(stream.read())


def mm_to_pt(x_mm: float) -> float:
    """Convert millimetres to points."""
    return x_mm / MM_PER_PT


def make_poster(  # pylint: disable=too-many-locals,too-many-arguments
    docsrc: pymupdf.Document,
    n_pages: tuple[int, int],
    page_size: tuple[float, float],
    *,
    overlap: float | tuple[float, float] = 0.0,
    clip: dict[str, float] | None = None,
    no_white_space: bool = True,
) -> pymupdf.Document:
    """
    Split a single-page PDF across several smaller pages.

    Args:
        docsrc: Document to split (only the first page will be used).
        n_pages: Number of poster pages along the (horizontal, vertical) axes.
        page_size: (width, height) of the output pages, in points.
        overlap: (horizontal, vertical) overlap between output pages, in points.
            If only one value is given, the overlaps are assumed to be equal.
        clip: Mapping from "left", "right", "top", "bottom" to the respective
            amounts, in points, to clip from `docsrc` before splitting. Default
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
            clip_rect_rel_page = clip_rect - page_origin * 2
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
    # Put the title page (bottom right corner of map sheet) on the left
    pageout.show_pdf_page(
        pymupdf.Rect(0, 0, COVER_WIDTH_PT, pageout.bound().height),
        docsrc,
        clip=pymupdf.Rect(
            pagesrc.bound().width - COVER_WIDTH_PT,
            pagesrc.bound().height / 2,
            pagesrc.bound().bottom_right,
        ),
    )
    # Put the legend (top right corner of map sheet) on the right
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


def rasterize(docsrc: pymupdf.Document, dpi: int) -> pymupdf.Document:
    """
    Rasterize a PDF by converting its pages to PNG.

    Args:
        docsrc: Document to be rasterized.
        dpi: Resolution.

    Returns:
        Rasterized document.
    """

    docout = pymupdf.Document()
    for i, pagesrc in enumerate(docsrc):
        logger.info("rasterizing page %d of %d", i + 1, len(docsrc))
        pix: pymupdf.Pixmap = pagesrc.get_pixmap(dpi=dpi)
        pngbytes = pix.tobytes("png")
        pngdoc = pymupdf.Document("png", pngbytes)
        pdfbytes = pngdoc.convert_to_pdf()
        pdfdoc = pymupdf.Document("pdf", pdfbytes)
        pageout: pymupdf.Page = docout.new_page(
            width=pagesrc.bound().width, height=pagesrc.bound().height
        )
        pageout.show_pdf_page(pageout.bound(), pdfdoc)
    return docout


def get_map_bbox(page: pymupdf.Page, clip: pymupdf.Rect = None) -> pymupdf.Rect:
    """
    Return a rectangle that encloses the map and all its coordinate labels.

    This is done in a rather hacky way by searching for text that matches the
    usual coordinate label format, and returning the rectangle that encloses all
    the matched text.

    Args:
        page: The page to be searched.
        clip: Require the result to be a subset of this rectangle (useful for
            excluding the cover page and legend; optional).
    """

    blocks = page.get_text("blocks", clip=clip)
    xcoords = []
    ycoords = []
    for b in blocks:
        # b[6] == 0 means the block is text (not an image)
        # b[4] is the text in the block
        if b[6] == 0 and COLLAR_REGEX.search(b[4]):
            xcoords.append(b[0])
            ycoords.append(b[1])
            xcoords.append(b[2])
            ycoords.append(b[3])
    return pymupdf.Rect([min(xcoords), min(ycoords), max(xcoords), max(ycoords)])
