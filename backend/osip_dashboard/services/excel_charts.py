"""Shared openpyxl chart construction: sizing, margins, label placement.

Extracted from holdings_export.py so the multi-source domain exports
(Asset Management, Brokerage, Clients, Corporate Finance) can reuse the same
chart-quality work instead of duplicating it: fixed label font sizes (some
renderers otherwise auto-scale label text to the chart's physical size),
explicit non-overlapping title/legend/plot-area regions, and per-slice
label placement (push outside with a leader line, then nudge apart along
the rim) for slices too small to carry an inside label without colliding
with a neighbour - all confirmed against real Excel, not just a renderer
quirk, during this app's holdings-export work.
"""

from __future__ import annotations

from decimal import Decimal
import math
from typing import Any

from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.axis import ChartLines
from openpyxl.chart.label import DataLabel, DataLabelList, _DataLabelBase
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.text import RichText
from openpyxl.descriptors import Typed
from openpyxl.drawing.line import LineProperties
from openpyxl.drawing.text import CharacterProperties, Paragraph, ParagraphProperties


def label_font(size_points: int) -> RichText:
    """A fixed data-label font size, in points.

    Without an explicit size, some chart renderers auto-scale data-label
    text to the chart's physical dimensions, which can inflate label text
    well past what a couple of percent digits need and make adjacent
    small-slice labels collide even once correctly placed.
    """
    properties = CharacterProperties(sz=size_points * 100)
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=properties))])


class PositionedDataLabel(DataLabel):
    """A per-point data label that also carries a manual position delta.

    openpyxl's own ``DataLabel`` has no ``layout`` field, even though the
    underlying OOXML ``CT_DLbl`` schema supports one - Excel uses it to
    remember a label a user dragged. Re-declaring the inherited descriptors
    (rather than just adding ``layout``) is required: openpyxl decides which
    child elements need ``desc.to_tree()`` wrapping from ``__nested__``,
    which is computed per-class from its own ``__dict__`` at class-creation
    time, not from inherited attributes.
    """

    idx = DataLabel.idx
    numFmt = _DataLabelBase.numFmt
    spPr = _DataLabelBase.spPr
    txPr = _DataLabelBase.txPr
    dLblPos = _DataLabelBase.dLblPos
    showLegendKey = _DataLabelBase.showLegendKey
    showVal = _DataLabelBase.showVal
    showCatName = _DataLabelBase.showCatName
    showSerName = _DataLabelBase.showSerName
    showPercent = _DataLabelBase.showPercent
    showBubbleSize = _DataLabelBase.showBubbleSize
    showLeaderLines = _DataLabelBase.showLeaderLines
    separator = _DataLabelBase.separator
    layout = Typed(expected_type=Layout, allow_none=True)
    __elements__ = ("idx", "layout") + tuple(tag for tag in DataLabel.__elements__ if tag != "idx")

    def __init__(self, idx: int = 0, layout: Layout | None = None, **kw: Any):
        self.layout = layout
        super().__init__(idx=idx, **kw)


def slice_midpoint_angle(values: list[Any], index: int, total: Decimal) -> float:
    """Clockwise angle, in radians from 12 o'clock, of slice ``index``'s midpoint.

    Pie slices are drawn in row order starting at 12 o'clock, so this only
    needs each slice's share and how much precedes it in the same order.
    """
    preceding = sum((value for value in values[:index] if isinstance(value, Decimal)), Decimal("0"))
    this_value = values[index] if isinstance(values[index], Decimal) else Decimal("0")
    midpoint_fraction = (preceding + this_value / 2) / total
    return float(midpoint_fraction) * 2 * math.pi


def radial_offset_layout(angle: float, radial: float, tangential: float) -> Layout:
    """A manual position delta for one outside data label, in chart fractions.

    ``radial`` pushes the label further from the pie's centre along its own
    slice direction; ``tangential`` shifts it sideways along the pie's rim -
    the lever that actually separates two labels whose default outEnd
    position landed in the same spot. Chart y grows downward, so the radial
    unit vector is (sin, -cos) for a clockwise-from-12-o'clock angle.
    """
    radial_x, radial_y = math.sin(angle), -math.cos(angle)
    tangential_x, tangential_y = math.cos(angle), math.sin(angle)
    return Layout(manualLayout=ManualLayout(
        x=radial * radial_x + tangential * tangential_x,
        y=radial * radial_y + tangential * tangential_y,
    ))


SMALL_SLICE_THRESHOLD = Decimal("0.08")


def small_adjacent_slice_indices(values: list[Any], threshold: Decimal = SMALL_SLICE_THRESHOLD) -> set[int]:
    """Indices of pie slices too small, next to another small slice, to
    carry an inside label without the two overlapping.

    Pie slices are drawn in row order starting at 12 o'clock, so index i's
    visual neighbors are always i-1 and i+1 (wrapping around), regardless of
    how the rows were sorted upstream.
    """
    total = sum((value for value in values if isinstance(value, Decimal)), Decimal("0"))
    count = len(values)
    if count < 2 or total <= 0:
        return set()
    small = [isinstance(value, Decimal) and (value / total) < threshold for value in values]
    return {index for index in range(count) if small[index] and (small[index - 1] or small[(index + 1) % count])}


def cluster_nudges(indices: set[int], count: int) -> dict[int, float]:
    """Group flagged indices into contiguous runs and fan each run apart.

    A lone flagged slice gets no nudge (outEnd alone already gives it room).
    A run of ``n`` adjacent flagged slices gets symmetric tangential offsets
    (..., -1, 0, +1, ...) x a fixed step, so their labels spread out along
    the pie's rim instead of landing on the same default position.
    """
    if not indices:
        return {}
    ordered = sorted(indices)
    runs: list[list[int]] = [[ordered[0]]]
    for index in ordered[1:]:
        if index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    # A run touching both index 0 and count - 1 wraps around the same cluster.
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == count - 1:
        runs[0] = runs[-1] + runs[0]
        runs.pop()
    step = 0.045
    nudges: dict[int, float] = {}
    for run in runs:
        if len(run) < 2:
            continue
        offset = -(len(run) - 1) / 2
        for index in run:
            nudges[index] = offset * step
            offset += 1
    return nudges


OTHER_SLICE_THRESHOLD = Decimal("0.02")


def chart_series(
    rows: list[list[Any]], chart_column: int, threshold: Decimal = OTHER_SLICE_THRESHOLD, other_label: str = "Прочее",
) -> tuple[list[str], list[Decimal]]:
    """Category labels and chart values for the pie, grouping tiny slices.

    Any slice under ``threshold`` share is folded into one "Прочее" wedge,
    but only when there are at least two of them - a single small slice is
    left alone since there is nothing to group it with, and it usually has
    enough room next to its neighbours anyway.
    """
    labels = [str(row[0]) for row in rows]
    values = [row[chart_column - 1] if isinstance(row[chart_column - 1], Decimal) else Decimal("0") for row in rows]
    total = sum(values, Decimal("0"))
    if total <= 0:
        return labels, values
    small = [(value / total) < threshold for value in values]
    if sum(small) < 2:
        return labels, values
    kept_labels = [label for label, is_small in zip(labels, small) if not is_small]
    kept_values = [value for value, is_small in zip(values, small) if not is_small]
    merged_value = sum((value for value, is_small in zip(values, small) if is_small), Decimal("0"))
    return kept_labels + [other_label], kept_values + [merged_value]


def write_pie_chart(
    source_worksheet,
    *,
    label_col: int,
    value_col: int,
    first_row: int,
    last_row: int,
    values: list[Decimal],
    title: str,
    anchor: str,
    anchor_worksheet=None,
    visible_cells_only: bool = True,
) -> None:
    """Build a fully-configured, label-safe pie chart and anchor it.

    The caller has already written ``values`` (and their category labels) to
    ``source_worksheet`` at columns ``label_col``/``value_col``, rows
    ``first_row..last_row`` - this only builds the chart against that range.
    ``values`` is passed separately (rather than re-read from the sheet)
    because the label-placement math needs real ``Decimal`` values, not
    another round of cell parsing. Pass ``visible_cells_only=False`` when
    the source range is hidden - Excel's default "plot visible cells only"
    setting otherwise renders nothing at all.
    """
    anchor_worksheet = anchor_worksheet or source_worksheet
    chart = PieChart()
    chart.visible_cells_only = visible_cells_only
    data = Reference(source_worksheet, min_col=value_col, min_row=first_row, max_row=last_row)
    categories = Reference(source_worksheet, min_col=label_col, min_row=first_row, max_row=last_row)
    chart.add_data(data, titles_from_data=False)
    chart.set_categories(categories)
    chart.title = title
    count = len(values)
    outside_indices = small_adjacent_slice_indices(values)
    nudges = cluster_nudges(outside_indices, count)
    # Match the spacious native Excel layout used by the reference workbook:
    # large 15 x 7.5cm editable charts, with a bottom legend for a
    # two/three-slice view and a right legend for larger allocations. A
    # little extra height gives the pie itself more absolute room when it
    # has small adjacent slices to label outside its edge - the plot area
    # inscribes the pie to its shorter side, so height (not width) is what
    # actually grows the wheel here.
    chart.height = 9.0 if outside_indices else 7.5
    chart.width = 15
    bottom_legend = count <= 3
    chart.legend.position = "b" if bottom_legend else "r"
    # Title, plot, and legend get explicit non-overlapping regions rather
    # than relying on each renderer's own auto-layout: Excel reserves space
    # correctly on its own, but other Excel-compatible readers (LibreOffice,
    # web preview tools) were rendering the title touching the pie and, with
    # a right legend, long Russian category text colliding with the slices
    # instead of sitting in its own column.
    chart.title.overlay = False
    chart.title.layout = Layout(manualLayout=ManualLayout(
        xMode="edge", yMode="edge", x=0.02, y=0.02, w=0.96, h=0.12,
    ))
    chart.legend.overlay = False
    chart.legend.layout = Layout(manualLayout=ManualLayout(
        xMode="edge", yMode="edge",
        **({"x": 0.05, "y": 0.88, "w": 0.9, "h": 0.1} if bottom_legend
           else {"x": 0.66, "y": 0.16, "w": 0.32, "h": 0.8})
    ))
    # ChartBase._write() copies chart.layout onto plot_area.layout right
    # before serialization, discarding anything set directly on
    # plot_area.layout - the plot area's own position must be set here.
    chart.layout = Layout(manualLayout=ManualLayout(
        xMode="edge", yMode="edge",
        **({"x": 0.16, "y": 0.18, "w": 0.68, "h": 0.58} if bottom_legend
           else {"x": 0.08, "y": 0.18, "w": 0.5, "h": 0.66})
    ))
    # Match the reference workbook: show only percentages, with all
    # category/series labels explicitly disabled. Leaving these flags unset
    # makes some Excel-compatible readers infer "Series1" and the category
    # text, which was the source of the previous overlay bug.
    label_kwargs = dict(
        showLegendKey=False, showVal=False, showCatName=False, showSerName=False,
        showPercent=True, showBubbleSize=False, showLeaderLines=True,
    )
    # A fixed, modest size regardless of the chart's physical dimensions
    # (see label_font) - the outside overrides get an even smaller size
    # since those are exactly the crowded small-adjacent-slice labels.
    labels = DataLabelList(dLblPos="ctr" if count <= 2 else "inEnd", txPr=label_font(11), **label_kwargs)
    # A tiny slice sitting next to another tiny slice has nowhere to put an
    # inside label without the two overlapping (e.g. two adjacent 1-2%
    # wedges). Pull just those labels outside the pie with a leader line; a
    # run of several adjacent small slices additionally gets each label
    # nudged sideways along the pie's rim (see cluster_nudges) so they fan
    # out instead of landing on the same default outEnd spot - a plain
    # outEnd position alone still collided for slices only a few degrees
    # apart, confirmed against real Excel.
    total = sum((value for value in values if isinstance(value, Decimal)), Decimal("0"))
    overrides = []
    for index in sorted(outside_indices):
        tangential = nudges.get(index, 0.0)
        layout = None
        if tangential:
            angle = slice_midpoint_angle(values, index, total)
            layout = radial_offset_layout(angle, radial=0.03, tangential=tangential)
        overrides.append(PositionedDataLabel(idx=index, dLblPos="outEnd", txPr=label_font(9), layout=layout, **label_kwargs))
    if overrides:
        labels.dLbl = overrides
    chart.dataLabels = labels
    chart.varyColors = True
    anchor_worksheet.add_chart(chart, anchor)


def write_bar_chart(
    source_worksheet,
    *,
    label_col: int,
    value_col_first: int,
    value_col_last: int,
    header_row: int,
    first_row: int,
    last_row: int,
    title: str,
    anchor: str,
    anchor_worksheet=None,
    y_axis_title: str | None = None,
    y_axis_number_format: str = "#,##0",
    horizontal: bool = False,
    row_separator_gridlines: bool = False,
    visible_cells_only: bool = True,
    log_scale: bool = False,
    min_value_padding: float | None = None,
) -> None:
    """Build a clustered bar/column chart for comparing magnitudes across
    categories (turnover by currency, assets by manager, and similar) -
    a pie chart is the wrong form here since these are compared magnitudes,
    not a whole-to-part share.

    Assumes a header row directly above ``first_row`` naming each series
    (``value_col_first..value_col_last``); used as the legend via
    ``titles_from_data``. A single value column is a plain (unclustered) bar.

    ``log_scale`` switches the value axis to base-10 log: a category that
    dominates the others by 2-3 orders of magnitude (e.g. KASE turnover vs.
    a small OTC venue) otherwise flattens every smaller bar to a sliver
    against the axis - confirmed against a real 40bn-vs-180k KZT turnover
    export. Only meaningful for strictly positive values; Excel simply omits
    a zero/negative bar on a log axis rather than erroring, which is
    acceptable here since counts and turnover are never negative.

    ``min_value_padding`` starts a linear axis just below the smallest
    plotted value instead of at zero, so bars that are all clustered in a
    narrow band (e.g. every row between 60% and 96% utilization) show their
    relative differences instead of reading as near-identical full-length
    bars. Ignored when ``log_scale`` is set (that already controls its own
    minimum). Never pushes the floor above zero - a chart of values that
    span or approach zero keeps the zero baseline.
    """
    anchor_worksheet = anchor_worksheet or source_worksheet
    chart = BarChart()
    chart.visible_cells_only = visible_cells_only
    chart.type = "bar" if horizontal else "col"
    chart.grouping = "clustered"
    # Slightly overlap series within a category so the blue/purple bars read as
    # one cluster; put the larger whitespace between category rows instead.
    chart.overlap = 25 if horizontal else 0
    chart.gapWidth = 250 if horizontal else 60
    chart.title = title
    chart.title.overlay = False
    # Horizontal ranking charts need substantially more canvas than the
    # compact column charts used elsewhere.  Their category labels sit on the
    # left and a bottom legend otherwise consumes most of the available plot
    # area (especially in Excel-compatible renderers).  Give these charts a
    # wide, tall frame and omit a redundant one-series legend so the bars use
    # the space the reader actually needs.
    if horizontal:
        chart.height = 14.0
        chart.width = 24
        if value_col_first == value_col_last:
            chart.legend = None
    else:
        chart.height = 9.0
        chart.width = 15
    chart.style = 10
    data = Reference(source_worksheet, min_col=value_col_first, max_col=value_col_last, min_row=header_row, max_row=last_row)
    categories = Reference(source_worksheet, min_col=label_col, min_row=first_row, max_row=last_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    # Give every bar a crisp, thin outline so adjacent statuses remain
    # distinguishable even when their fills are visually similar.
    for series in chart.series:
        series.graphicalProperties.line.solidFill = "000000"
        series.graphicalProperties.line.width = 8000
        series.graphicalProperties.line.prstDash = "solid"
    # BarChart keeps categories on the text x-axis and values on the numeric
    # y-axis even when the bars run horizontally.  Treating those axes as
    # swapped makes percentage/decimal formats land on the category axis and
    # leaves Excel to guess how to format the actual value ticks.
    value_axis = chart.y_axis
    category_axis = chart.x_axis
    if y_axis_title:
        value_axis.title = y_axis_title
    # Without an explicit format the axis falls back to each renderer's own
    # guess at "General" for numbers spanning billions, which showed up as
    # blank/unreadable tick labels rather than thousands-separated figures.
    value_axis.numFmt = y_axis_number_format
    value_axis.delete = False
    category_axis.delete = False
    if horizontal:
        # Keep the value-axis gridlines (vertical in a horizontal bar chart)
        # faint and readable.  Category-axis gridlines are optional: when
        # requested they separate rows, while leaving them off keeps clustered
        # bars in the same category visually grouped.
        value_axis.majorGridlines = ChartLines(
            spPr=GraphicalProperties(ln=LineProperties(solidFill="D9DEE7", w=5000))
        )
        if row_separator_gridlines:
            # Put faint horizontal separators on the category axis.  The
            # source table is now the visible summary table itself, so there
            # are no hidden helper categories involved.
            category_axis.majorGridlines = ChartLines(
                spPr=GraphicalProperties(ln=LineProperties(solidFill="D9DEE7", w=5000))
            )
            category_axis.majorTickMark = "none"
    if log_scale:
        # Do not force every logarithmic chart to start at 1.  That makes
        # unrelated distributions look identical.  Use the smallest positive
        # value actually included in the chart, rounded down to the lower
        # power-of-ten threshold: 202 -> 100, 2,020 -> 1,000, and 46 -> 10.
        # This keeps the first meaningful decade visible without placing the
        # baseline on an awkward value such as 202. Zero and negative values
        # cannot be represented on a log axis and are intentionally ignored.
        positive_values: list[float] = []
        for row_number in range(first_row, last_row + 1):
            for column in range(value_col_first, value_col_last + 1):
                value = source_worksheet.cell(row_number, column).value
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(numeric) and numeric > 0:
                    positive_values.append(numeric)
        value_axis.scaling.logBase = 10
        if positive_values:
            minimum = min(positive_values)
            value_axis.scaling.min = 10 ** math.floor(math.log10(minimum))
    elif min_value_padding is not None:
        all_values: list[float] = []
        for row_number in range(first_row, last_row + 1):
            for column in range(value_col_first, value_col_last + 1):
                value = source_worksheet.cell(row_number, column).value
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(numeric):
                    all_values.append(numeric)
        if all_values:
            value_axis.scaling.min = max(0.0, min(all_values) - min_value_padding)
    if chart.legend is not None:
        chart.legend.position = "b"
        chart.legend.overlay = False
    anchor_worksheet.add_chart(chart, anchor)


def write_line_chart(
    source_worksheet,
    *,
    label_col: int,
    value_col: int,
    header_row: int,
    first_row: int,
    last_row: int,
    title: str,
    anchor: str,
    anchor_worksheet=None,
    y_axis_title: str | None = None,
    line_color: str = "1F6FB2",
) -> None:
    """Build a single-series line chart for a value over time (e.g. unit
    value history) - a pie/bar chart is the wrong form for a time series."""
    anchor_worksheet = anchor_worksheet or source_worksheet
    chart = LineChart()
    chart.title = title
    chart.title.overlay = False
    chart.height = 9.0
    chart.width = 15
    # No chart.style number here: several of Excel's built-in line-chart
    # styles (style 12 among them) fade the stroke from a dark tone to a
    # pale tint across the series to imply progression - it reads as a
    # rendering glitch on a plain value-over-time line, not a deliberate
    # effect (confirmed against a real export). Setting the series color
    # explicitly below guarantees one solid color regardless of style.
    data = Reference(source_worksheet, min_col=value_col, min_row=header_row, max_row=last_row)
    categories = Reference(source_worksheet, min_col=label_col, min_row=first_row, max_row=last_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    if y_axis_title:
        chart.y_axis.title = y_axis_title
    # Without this, both axes render as bare lines with no tick labels at
    # all (confirmed against a real export) - the same fix write_bar_chart
    # already applies, just never carried over to the line chart builder.
    chart.y_axis.numFmt = "#,##0.00"
    chart.y_axis.delete = False
    chart.x_axis.delete = False
    chart.x_axis.numFmt = "dd.mm.yyyy"
    chart.legend = None
    for series in chart.series:
        series.smooth = False
        series.graphicalProperties.line.solidFill = line_color
        series.graphicalProperties.line.width = 20000
    anchor_worksheet.add_chart(chart, anchor)
