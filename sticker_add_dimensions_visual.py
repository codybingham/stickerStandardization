#!/usr/bin/env python3
"""
Improved version of sticker_add_dimensions.py.

Key difference:
- Computes a stroke-aware "visual-ish" bounding box for each selected object,
  then dimensions that union instead of the pure geometric bbox.

Why this approach:
- In many real files, geometric bounds under-report size for stroked paths.
- Reading raw stroke-width alone is insufficient when transforms and
  vector-effect are involved.
- This script estimates global stroke expansion from each object's *effective*
  transform matrix, then expands its bbox accordingly.

Tradeoff:
- This is still an approximation (especially at extreme miter joins),
  but it is engineered to avoid undersizing in common sticker/label workflows.
"""

import math

import inkex
from inkex import Group, PathElement, TextElement


def parse_float(v, default=0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return default
    return float(s.replace(",", "."))


def parse_int(v, default=3) -> int:
    if v is None:
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def line_path(x1, y1, x2, y2) -> str:
    return f"M {x1},{y1} L {x2},{y2}"


def triangle_path(x, y, dx, dy, size):
    """
    Filled triangle arrowhead.
    Tip is exactly at (x,y). Direction (dx,dy) points FROM base TO tip.
    """
    mag = (dx * dx + dy * dy) ** 0.5
    if mag < 1e-9:
        mag = 1.0
    ux, uy = dx / mag, dy / mag
    px, py = -uy, ux

    tip_x, tip_y = x, y
    base_x = x - ux * size
    base_y = y - uy * size

    w = size * 0.45
    p1x = base_x + px * w
    p1y = base_y + py * w
    p2x = base_x - px * w
    p2y = base_y - py * w

    return f"M {tip_x},{tip_y} L {p1x},{p1y} L {p2x},{p2y} Z"


def _safe_style_value(el, key, default=""):
    try:
        return str(el.specified_style().get(key, default)).strip().lower()
    except Exception:
        return default


def _stroke_width_user_units(svg, el) -> float:
    """
    Return stroke width in user units *before transform*.
    Uses specified_style so cascaded CSS is respected.
    """
    raw = None
    try:
        raw = el.specified_style().get("stroke-width")
    except Exception:
        raw = None

    if raw is None:
        return 0.0

    try:
        sw = svg.unittouu(str(raw))
    except Exception:
        try:
            sw = float(str(raw))
        except Exception:
            sw = 0.0

    return max(0.0, float(sw))


def _non_scaling_stroke(el) -> bool:
    """True when vector-effect keeps stroke width constant in screen/user units."""
    ve = _safe_style_value(el, "vector-effect", "")
    return ve == "non-scaling-stroke"


def _effective_transform(el):
    """
    Best-effort composed transform to document coordinates.
    In Inkex this typically includes parent transforms.
    """
    try:
        return el.composed_transform()
    except Exception:
        return el.transform


def _xy_stroke_expansion(el, svg):
    """
    Estimate axis-aligned expansion added by stroke in document units.

    Heavy-lifting notes:
    - For normal scaling strokes, local stroke radius = stroke_width/2.
      We map the local unit circle through the element's linear transform.
      The maximum x/y excursions are:
          ex = r * sqrt(a^2 + c^2)
          ey = r * sqrt(b^2 + d^2)
      where matrix is [a c; b d].
    - For non-scaling-stroke, stroke width is already in document/user units,
      so expansion is roughly isotropic: ex = ey = r.

    Join/cap handling:
    - Miter joins can exceed half-stroke at sharp corners.
      We apply a conservative multiplier based on stroke-linejoin/miterlimit.
    """
    stroke = _safe_style_value(el, "stroke", "none")
    if stroke in ("", "none"):
        return 0.0, 0.0

    sw = _stroke_width_user_units(svg, el)
    if sw <= 0:
        return 0.0, 0.0

    r = 0.5 * sw

    if _non_scaling_stroke(el):
        ex = r
        ey = r
    else:
        t = _effective_transform(el)
        # 2x2 linear part
        a, b, c, d = float(t.a), float(t.b), float(t.c), float(t.d)
        ex = r * math.sqrt(a * a + c * c)
        ey = r * math.sqrt(b * b + d * d)

    # Conservative join/cap boost to avoid under-measurement on sharp miters.
    join = _safe_style_value(el, "stroke-linejoin", "miter")
    if join == "miter":
        raw_ml = _safe_style_value(el, "stroke-miterlimit", "4")
        try:
            miter_limit = max(1.0, float(raw_ml))
        except Exception:
            miter_limit = 4.0
        # Keep this bounded so one pathological style doesn't explode bbox.
        join_factor = min(miter_limit, 4.0)
    else:
        join_factor = 1.0

    return ex * join_factor, ey * join_factor


def visual_bbox_union(svg, elements):
    """
    Union geometric bboxes expanded by estimated rendered stroke extents.
    Returns (x0, y0, x1, y1).
    """
    x0 = y0 = x1 = y1 = None

    for el in elements:
        bb = el.bounding_box()
        if bb is None:
            continue

        ex, ey = _xy_stroke_expansion(el, svg)
        left = bb.left - ex
        top = bb.top - ey
        right = bb.right + ex
        bottom = bb.bottom + ey

        x0 = left if x0 is None else min(x0, left)
        y0 = top if y0 is None else min(y0, top)
        x1 = right if x1 is None else max(x1, right)
        y1 = bottom if y1 is None else max(y1, bottom)

    if None in (x0, y0, x1, y1):
        raise inkex.AbortExtension("Could not compute stroke-aware bounding box for selection.")

    return x0, y0, x1, y1


class StickerAddDimensionsVisual(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--offset_in", default="0.100")
        pars.add_argument("--text_height_in", default="0.120")
        pars.add_argument("--line_width_in", default="0.010")
        pars.add_argument("--arrow_size_in", default="0.060")
        pars.add_argument("--decimals", default="3")

    def effect(self):
        if not self.svg.selection:
            raise inkex.AbortExtension("Select an object (or group) to dimension.")

        offset_in = parse_float(self.options.offset_in, 0.1)
        text_height_in = parse_float(self.options.text_height_in, 0.12)
        line_width_in = parse_float(self.options.line_width_in, 0.01)
        arrow_size_in = parse_float(self.options.arrow_size_in, 0.06)
        decimals = parse_int(self.options.decimals, 3)

        if not (math.isfinite(offset_in) and offset_in > 0):
            raise inkex.AbortExtension("Offset must be > 0.")
        if not (math.isfinite(text_height_in) and text_height_in > 0):
            raise inkex.AbortExtension("Text height must be > 0.")
        if not (math.isfinite(line_width_in) and line_width_in > 0):
            raise inkex.AbortExtension("Line width must be > 0.")
        if not (math.isfinite(arrow_size_in) and arrow_size_in > 0):
            raise inkex.AbortExtension("Arrow size must be > 0.")

        # Convert inches -> document user units (px)
        offset = self.svg.unittouu(f"{offset_in}in")
        text_height = self.svg.unittouu(f"{text_height_in}in")
        line_w = self.svg.unittouu(f"{line_width_in}in")
        arrow_size = self.svg.unittouu(f"{arrow_size_in}in")

        # Stroke-aware bounds (new behavior)
        x0, y0, x1, y1 = visual_bbox_union(self.svg, self.svg.selection.values())

        width_px = x1 - x0
        height_px = y1 - y0

        width_in = self.svg.uutounit(width_px, "in")
        height_in = self.svg.uutounit(height_px, "in")

        fmt = f"{{:.{decimals}f}}"
        w_txt = fmt.format(width_in) + " in"
        h_txt = fmt.format(height_in) + " in"

        g = Group()
        g.set("inkscape:label", "DIMENSIONS_VISUAL")
        self.svg.get_current_layer().add(g)

        stroke = "#000000"
        dim_line_style = {
            "fill": "none",
            "stroke": stroke,
            "stroke-width": str(line_w),
            "stroke-linecap": "square",
            "stroke-linejoin": "miter",
        }
        arrow_style = {"fill": stroke, "stroke": "none"}
        text_style = {
            "font-family": "Arial",
            "font-size": str(text_height),
            "fill": stroke,
        }

        # Horizontal dimension (above) with same extension-line gap behavior.
        y_dim = y0 - offset

        ext1 = PathElement()
        ext1.path = inkex.Path(line_path(x0, y0, x0, y_dim))
        ext1.style = dim_line_style
        g.add(ext1)

        ext2 = PathElement()
        ext2.path = inkex.Path(line_path(x1, y0, x1, y_dim))
        ext2.style = dim_line_style
        g.add(ext2)

        dim_h = PathElement()
        dim_h.path = inkex.Path(line_path(x0, y_dim, x1, y_dim))
        dim_h.style = dim_line_style
        g.add(dim_h)

        ah1 = PathElement()
        ah1.path = inkex.Path(triangle_path(x0, y_dim, -1, 0, arrow_size))
        ah1.style = arrow_style
        g.add(ah1)

        ah2 = PathElement()
        ah2.path = inkex.Path(triangle_path(x1, y_dim, 1, 0, arrow_size))
        ah2.style = arrow_style
        g.add(ah2)

        th = TextElement()
        th.text = w_txt
        th.set("x", str((x0 + x1) / 2))
        th.set("y", str(y_dim - 0.25 * text_height))
        th.style = text_style | {"text-anchor": "middle"}
        th.set("inkscape:label", "DIM_WIDTH")
        g.add(th)

        # Vertical dimension (right) with same extension-line gap behavior.
        x_dim = x1 + offset

        ext3 = PathElement()
        ext3.path = inkex.Path(line_path(x1, y0, x_dim, y0))
        ext3.style = dim_line_style
        g.add(ext3)

        ext4 = PathElement()
        ext4.path = inkex.Path(line_path(x1, y1, x_dim, y1))
        ext4.style = dim_line_style
        g.add(ext4)

        dim_v = PathElement()
        dim_v.path = inkex.Path(line_path(x_dim, y0, x_dim, y1))
        dim_v.style = dim_line_style
        g.add(dim_v)

        av1 = PathElement()
        av1.path = inkex.Path(triangle_path(x_dim, y0, 0, -1, arrow_size))
        av1.style = arrow_style
        g.add(av1)

        av2 = PathElement()
        av2.path = inkex.Path(triangle_path(x_dim, y1, 0, 1, arrow_size))
        av2.style = arrow_style
        g.add(av2)

        y_mid = (y0 + y1) / 2
        text_offset = 0.35 * text_height
        x_txt_v = x_dim + text_offset
        y_txt_v = y_mid

        tv = TextElement()
        tv.text = h_txt
        tv.set("x", str(x_txt_v))
        tv.set("y", str(y_txt_v))
        tv.style = text_style | {
            "text-anchor": "middle",
            "dominant-baseline": "middle",
        }
        tv.set("inkscape:label", "DIM_HEIGHT")
        tv.set("transform", f"rotate(90 {x_txt_v} {y_txt_v})")
        g.add(tv)


if __name__ == "__main__":
    StickerAddDimensionsVisual().run()
