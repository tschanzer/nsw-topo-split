"""A package for splitting NSW topographic maps across smaller pages"""

import json
import logging
import math
import pathlib
import re
import urllib.parse
import urllib.request
import warnings
from typing import Any, Callable, cast
from urllib.error import HTTPError

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
NOMINAL_COVER_WIDTH_PT = 326
MARGIN_MM = {
    "2022": 0.0,
    "2017": 5.0,
    "2016": 5.0,
    "2015": 5.0,
    "2014": 5.0,
    "2011": 5.0,
}

COLLAR_REGEX = re.compile(
    r"-?[0-9]+[º°]\s*[0-9]+'"  # match lat/lon coordinates
    r"|m[NESW]"  # match grid coordinates
    r"|000m"  # match grid coordinates
    r"|\(MGA(?:\s[0-9]+)?\)"  # match the "(MGA XX)" that accompanies grid coordinates
)
_Block = tuple[float, float, float, float, str, int, int]

logger = logging.getLogger(__name__)


def _get_map_url(name: str, year: str) -> str:
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
    return cast(str, data["features"][0]["attributes"][url_key])


def _download(url: str, outfile: str | pathlib.Path) -> None:
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


def download_map(
    name: str, year: str, *, base_dir: pathlib.Path, force_download: bool = False
) -> pathlib.Path:
    """
    Download a map if required.

    Args:
        name: Name of the map (case-insensitive), e.g., 'katoomba' or
            'mount wilson'.
        year: Publication year of the map, e.g., '2017'.
        base_dir: The base directory in which the map will be saved.
        force_download: Download the map even if it already exists in base_dir
            (default False).

    Returns:
        The path to the downloaded (or existing) map file.
    """

    url = _get_map_url(name, year)
    filename = url.split("/")[-1]
    out_dir: pathlib.Path = base_dir / year / filename.removesuffix(".pdf")
    out_dir.mkdir(parents=True, exist_ok=True)
    master_file = out_dir / filename
    if force_download or not master_file.exists():
        try:
            _download(url, master_file)
        except HTTPError as e:
            raise RuntimeError(
                f"The {year} edition does not seem to be available for "
                f"{name}. Please try another edition."
            ) from e
    else:
        logger.info("using existing map at %s", master_file)
    return master_file


def mm_to_pt(x_mm: float) -> float:
    """Convert millimetres to points."""
    return x_mm / MM_PER_PT


def pt_to_mm(x_pt: float) -> float:
    """Convert points to millimetres."""
    return x_pt * MM_PER_PT


def _choose_n_pages_1d(from_size: float, to_size: float, overlap: float) -> int:
    return math.ceil((from_size - overlap) / (to_size - overlap))


def _choose_n_pages(
    from_size: tuple[float, float],
    to_size: tuple[float, float],
    overlap: tuple[float, float],
) -> tuple[int, int]:
    """
    Determine the number of poster pages needed to cover a source page.

    Args:
        from_size:
    """

    return cast(
        tuple[int, int], tuple(map(_choose_n_pages_1d, from_size, to_size, overlap))
    )


def _calc_layout_size(page_size: float, n_pages: int, overlap: float) -> float:
    return n_pages * page_size - (n_pages - 1) * overlap


def _calc_layout_params_1d(  # pylint: disable=too-many-arguments
    *,
    page_size: float,
    n_pages: int,
    min_overlap: float,
    cropbox: tuple[float, float],
    allow_whitespace: bool,
    artbox: tuple[float, float],
) -> tuple[float, float]:
    max_layout_size = _calc_layout_size(page_size, n_pages, min_overlap)
    cropbox_size = cropbox[1] - cropbox[0]
    if max_layout_size > cropbox_size:
        if not allow_whitespace and n_pages > 1:
            origin = cropbox[0]
            # Increase overlap so the layout size equals the cropbox size
            overlap = (n_pages * page_size - cropbox_size) / (n_pages - 1)
        else:
            # Center the layout on the cropbox
            origin = (cropbox[0] + cropbox[1]) / 2 - max_layout_size / 2
            overlap = min_overlap
    else:
        # Center the layout on the artbox
        origin = (artbox[0] + artbox[1]) / 2 - max_layout_size / 2
        # Make sure the layout is still inside the cropbox
        if origin < cropbox[0]:
            origin = cropbox[0]
        elif origin + max_layout_size > cropbox[1]:
            origin = cropbox[1] - max_layout_size
        overlap = min_overlap
    return origin, overlap


def _warn_n_pages(axis: str, amount_cut: float) -> None:
    warnings.warn(
        f"The chosen n_pages may be too small along the {axis} axis; {amount_cut:.1f} "
        "mm of content at the edges may not be visible on any of the poster pages. "
        "Inspect the output and increase n_pages if needed."
    )


def _calc_layout_params(  # pylint: disable=too-many-arguments
    *,
    page_size: tuple[float, float],
    n_pages: tuple[int, int],
    min_overlap: tuple[float, float],
    cropbox: pymupdf.Rect,
    allow_whitespace: bool,
    artbox: pymupdf.Rect,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Calculate the origin and overlaps for a poster layout.

    Args:
        page_size: (width, height) of the output pages, in points.
        n_pages: Number of poster pages along the (horizontal, vertical) axes.
        min_overlap: (horizontal, vertical) overlap between output pages, in
            points. If allow_whitespace is False, then the overlap may be
            increased to eliminate white space.
        cropbox: The rectangle to which the source page will be cropped.
        allow_whitespace: If True, do not increase overlaps to eliminate white
            space on the output pages.
        artbox: The function will try to position the poster pages (and choose
            n_pages if n_pages is None ) to ensure that everything inside this
            box is visible on the output pages. This may not be possible if the
            user specifies too few n_pages; in this case, a warning will be
            issued.

    Returns:
        A tuple ((origin_x, origin_y), (overlap_x, overlap_y)), in points.
    """

    origin_x, overlap_x = _calc_layout_params_1d(
        page_size=page_size[0],
        n_pages=n_pages[0],
        min_overlap=min_overlap[0],
        cropbox=(cropbox.x0, cropbox.x1),
        allow_whitespace=allow_whitespace,
        artbox=(artbox.x0, artbox.x1),
    )
    width = _calc_layout_size(page_size[0], n_pages[0], overlap_x)
    if width < artbox.x1 - artbox.x0:
        amount_cut = pt_to_mm((artbox.x1 - artbox.x0) - width)
        _warn_n_pages("x", amount_cut)

    origin_y, overlap_y = _calc_layout_params_1d(
        page_size=page_size[1],
        n_pages=n_pages[1],
        min_overlap=min_overlap[1],
        cropbox=(cropbox.y0, cropbox.y1),
        allow_whitespace=allow_whitespace,
        artbox=(artbox.y0, artbox.y1),
    )
    height = _calc_layout_size(page_size[1], n_pages[1], overlap_y)
    if height < artbox.y1 - artbox.y0:
        amount_cut = pt_to_mm((artbox.y1 - artbox.y0) - height)
        _warn_n_pages("y", amount_cut)

    return (origin_x, origin_y), (overlap_x, overlap_y)


def _make_poster(  # pylint: disable=too-many-locals,too-many-arguments
    pagesrc: pymupdf.Page,
    *,
    page_size: tuple[float, float],
    n_pages: tuple[int, int] | None = None,
    min_overlap: tuple[float, float] = (0.0, 0.0),
    cropbox: pymupdf.Rect | None = None,
    allow_whitespace: bool = False,
    artbox: pymupdf.Rect | None = None,
) -> pymupdf.Document:
    """
    Split a PDF page across several smaller pages.

    Args:
        pagesrc: The page to be split.
        page_size: (width, height) of the output pages, in points.
        n_pages: Number of poster pages along the (horizontal, vertical) axes
            (optional, determined automatically by default).
        min_overlap: (horizontal, vertical) overlap between output pages, in
            points (default 0). If allow_whitespace is False, then the overlap
            may be increased to eliminate white space.
        crop: Clip `pagesrc` to this rectangle before splitting (default: no
            clip).
        allow_whitespace: If True, do not increase overlaps to eliminate white
            space on the output pages.
        artbox: The function will try to position the poster pages (and choose
            n_pages if n_pages is None ) to ensure that everything inside this
            box is visible on the output pages. This may not be possible if the
            user specifies too few n_pages; in this case, a warning will be
            issued.

    Returns:
        Document containing the poster pages in column-major order.
    """

    if cropbox is None:
        cropbox = pagesrc.bound()
    if artbox is None:
        artbox = cropbox

    # Calculate the layout parameters
    if n_pages is None:
        n_pages = _choose_n_pages((artbox.width, artbox.height), page_size, min_overlap)
        logger.info("chosen page layout: %s", n_pages)
    layout_origin, overlap = _calc_layout_params(
        page_size=page_size,
        n_pages=n_pages,
        min_overlap=min_overlap,
        cropbox=cropbox,
        allow_whitespace=allow_whitespace,
        artbox=artbox,
    )
    if overlap[0] != min_overlap[0]:
        logger.info(
            "increasing horizontal overlap from %.2f to %.2f mm",
            pt_to_mm(min_overlap[0]),
            pt_to_mm(overlap[0]),
        )
    if overlap[1] != min_overlap[1]:
        logger.info(
            "increasing vertical overlap from %.2f to %.2f mm",
            pt_to_mm(min_overlap[1]),
            pt_to_mm(overlap[1]),
        )

    docout = pymupdf.Document()
    for j in range(n_pages[0]):
        for i in range(n_pages[1]):
            # Express the poster page origin relative to the source page
            page_origin = (
                layout_origin[0] + j * (page_size[0] - overlap[0]),
                layout_origin[1] + i * (page_size[1] - overlap[1]),
            )
            # Express the clip rectangle relative to the poster page
            clip_rect_rel_page = cropbox - page_origin * 2
            pageout = docout.new_page(width=page_size[0], height=page_size[1])
            pageout.show_pdf_page(
                clip_rect_rel_page, pagesrc.parent, pno=pagesrc.number, clip=cropbox
            )
    return docout


def _guess_cover_width(page_width: float) -> float:
    return page_width / round(page_width / NOMINAL_COVER_WIDTH_PT)


def _make_cover(pagesrc: pymupdf.Page, *, margin: float = 0.0) -> pymupdf.Document:
    """
    Put the map title page and legend side-by-side.

    Args:
        pagesrc: The original map.
        margin: Size of margin to trim from the source page, in points (default 0).

    Returns:
        New document containing a single page with the map title page and legend
        side-by-side.
    """

    docout = pymupdf.Document()
    cropbox = pagesrc.bound() + (margin, margin, -margin, -margin)
    cover_width = _guess_cover_width(cropbox.width)
    pageout = docout.new_page(width=2 * cover_width, height=cropbox.height / 2)
    # Put the title page (bottom right corner of map sheet) on the left
    pageout.show_pdf_page(
        pymupdf.Rect(0, 0, cover_width, cropbox.height / 2),
        pagesrc.parent,
        pno=pagesrc.number,
        clip=pymupdf.Rect(
            cropbox.x1 - cover_width,
            (cropbox.y0 + cropbox.y1) / 2,
            cropbox.bottom_right,
        ),
    )
    # Put the legend (top right corner of map sheet) on the right
    pageout.show_pdf_page(
        pymupdf.Rect(cover_width, 0, 2 * cover_width, cropbox.height / 2),
        pagesrc.parent,
        pno=pagesrc.number,
        clip=pymupdf.Rect(
            cropbox.x1 - cover_width,
            cropbox.y0,
            cropbox.x1,
            (cropbox.y0 + cropbox.y1) / 2,
        ),
    )
    return docout


def _is_map_text(block: _Block) -> bool:
    # b[6] == 0 means the block is text (not an image)
    # b[4] is the text in the block
    return block[6] == 0 and bool(COLLAR_REGEX.search(block[4]))


def _is_cover_text(block: _Block) -> bool:
    # b[6] == 0 means the block is text (not an image)
    return block[6] == 0


def _trivial_filter(_: _Block) -> bool:
    return True


def _get_bbox(
    page: pymupdf.Page,
    *,
    clip: pymupdf.Rect = None,
    filter_func: Callable[[_Block], bool] = _trivial_filter,
) -> pymupdf.Rect:
    """
    Return the smallest rectangle that encloses a page's blocks.

    Args:
        page: The page to be searched.
        clip: Consider only blocks that are inside this rectangle (useful for
            excluding the cover page and legend; optional).
        filter_func: Consider only blocks for which filter_func(block) is True
            (optional).
    """

    blocks = page.get_text("blocks", clip=clip)
    xcoords = []
    ycoords = []
    for b in filter(filter_func, blocks):
        xcoords.append(b[0])
        ycoords.append(b[1])
        xcoords.append(b[2])
        ycoords.append(b[3])
    return pymupdf.Rect([min(xcoords), min(ycoords), max(xcoords), max(ycoords)])


def _log_box_dims(box: pymupdf.Rect, text: str) -> None:
    logger.info("%s: (%.2f, %.2f) mm", text, pt_to_mm(box.width), pt_to_mm(box.height))


def make_split_map(  # pylint: disable=too-many-arguments
    pagesrc: pymupdf.Page,
    *,
    page_size: tuple[float, float],
    n_pages: tuple[int, int] | None = None,
    min_overlap: tuple[float, float] = (0.0, 0.0),
    allow_whitespace: bool = False,
    margin: float = 0.0,
) -> pymupdf.Document:
    """
    Split a map across several smaller pages.

    Args:
        pagesrc: The page to be split.
        page_size: (width, height) of the output pages, in points.
        n_pages: Number of poster pages along the (horizontal, vertical) axes
            (optional, determined automatically by default).
        min_overlap: (horizontal, vertical) overlap between output pages, in
            points (default 0). If allow_whitespace is False, then the overlap
            may be increased to eliminate white space.
        allow_whitespace: If True, do not increase overlaps to eliminate white
            space on the output pages.
        margin: Size of margin to trim from the source page, in points (default 0).

    Returns:
        Document containing the map pages in column-major order.
    """

    _log_box_dims(pagesrc.bound(), "original map dimensions")
    cropbox = pagesrc.bound() + (margin, margin, -margin, -margin)
    cropbox += (0.0, 0.0, -_guess_cover_width(cropbox.width), 0.0)
    _log_box_dims(cropbox, "cropped map dimensions")
    artbox = _get_bbox(pagesrc, clip=cropbox, filter_func=_is_map_text)
    _log_box_dims(artbox, "inferred artbox dimensions")
    return _make_poster(
        pagesrc,
        page_size=page_size,
        n_pages=n_pages,
        min_overlap=min_overlap,
        cropbox=cropbox,
        allow_whitespace=allow_whitespace,
        artbox=artbox,
    )


def make_split_cover(  # pylint: disable=too-many-arguments
    pagesrc: pymupdf.Page,
    *,
    page_size: tuple[float, float],
    n_pages: tuple[int, int] | None = None,
    min_overlap: tuple[float, float] = (0.0, 0.0),
    allow_whitespace: bool = False,
    margin: float = 0.0,
) -> pymupdf.Document:
    """
    Make the cover page and split it across several smaller pages.

    Args:
        pagesrc: The page to be split.
        page_size: (width, height) of the output pages, in points.
        n_pages: Number of poster pages along the (horizontal, vertical) axes
            (optional, determined automatically by default).
        min_overlap: (horizontal, vertical) overlap between output pages, in
            points (default 0). If allow_whitespace is False, then the overlap
            may be increased to eliminate white space.
        allow_whitespace: If True, do not increase overlaps to eliminate white
            space on the output pages.
        margin: Size of margin to trim from the source page, in points (default 0).

    Returns:
        Document containing the cover pages in column-major order.
    """

    _log_box_dims(pagesrc.bound(), "original map dimensions")
    cover = _make_cover(pagesrc, margin=margin)
    _log_box_dims(cover[0].bound(), "cover page dimensions")
    artbox = _get_bbox(cover[0], filter_func=_is_cover_text)
    _log_box_dims(artbox, "inferred artbox dimensions")
    return _make_poster(
        cover[0],
        page_size=page_size,
        n_pages=n_pages,
        min_overlap=min_overlap,
        allow_whitespace=allow_whitespace,
        artbox=artbox,
    )


def choose_margin(year: str) -> float:
    """
    Look up the margin size for a given edition.

    Args:
        year: The publication year.

    Returns:
        The margin size in points for that edition, defaulting to 0 for unknown
        editions.
    """

    if year in MARGIN_MM:
        margin = mm_to_pt(MARGIN_MM[year])
    else:
        logger.warning("Margin size is not known for year %s; defaulting to 0 pt", year)
        margin = 0.0
    return margin


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
        pix = pagesrc.get_pixmap(dpi=dpi)
        pngbytes = pix.tobytes("png")
        pngdoc = pymupdf.Document("png", pngbytes)
        pdfbytes = pngdoc.convert_to_pdf()
        pdfdoc = pymupdf.Document("pdf", pdfbytes)
        pageout = docout.new_page(
            width=pagesrc.bound().width, height=pagesrc.bound().height
        )
        pageout.show_pdf_page(pageout.bound(), pdfdoc)
    return docout
