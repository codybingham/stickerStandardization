#!/usr/bin/env python3
import inkex
from inkex import PathElement, TextElement, Group
from math import isfinite

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
    mag = (dx*dx + dy*dy) ** 0.5
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


class StickerAddDimensions(inkex.EffectExtension):
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

        if not (isfinite(offset_in) and offset_in > 0):
            raise inkex.AbortExtension("Offset must be > 0.")
        if not (isfinite(text_height_in) and text_height_in > 0):
            raise inkex.AbortExtension("Text height must be > 0.")
        if not (isfinite(line_width_in) and line_width_in > 0):
            raise inkex.AbortExtension("Line width must be > 0.")
        if not (isfinite(arrow_size_in) and arrow_size_in > 0):
            raise inkex.AbortExtension("Arrow size must be > 0.")

        # Convert inches -> document user units (px)
        offset = self.svg.unittouu(f"{offset_in}in")
        text_height = self.svg.unittouu(f"{text_height_in}in")
        line_w = self.svg.unittouu(f"{line_width_in}in")
        arrow_size = self.svg.unittouu(f"{arrow_size_in}in")

        # Bounding box of entire selection (union)
        bbs = [el.bounding_box() for el in self.svg.selection.values()]
        if not bbs:
            raise inkex.AbortExtension("Could not compute bounding box for selection.")

        x0 = min(bb.left for bb in bbs)
        y0 = min(bb.top for bb in bbs)
        x1 = max(bb.right for bb in bbs)
        y1 = max(bb.bottom for bb in bbs)

        width_px = x1 - x0
        height_px = y1 - y0

        # Convert to inches for label text
        width_in = self.svg.uutounit(width_px, "in")
        height_in = self.svg.uutounit(height_px, "in")

        fmt = f"{{:.{decimals}f}}"
        w_txt = fmt.format(width_in) + " in"
        h_txt = fmt.format(height_in) + " in"

        # Create a group to hold dimension graphics
        g = Group()
        g.set("inkscape:label", "DIMENSIONS")
        self.svg.get_current_layer().add(g)

        # Common styles
        stroke = "#000000"
        dim_line_style = {
            "fill": "none",
            "stroke": stroke,
            "stroke-width": str(line_w),
            "stroke-linecap": "square",
            "stroke-linejoin": "miter",
        }
        arrow_style = {
            "fill": stroke,
            "stroke": "none",
        }
        text_style = {
            "font-family": "Arial",
            "font-size": str(text_height),
            "fill": stroke,
        }

        # -----------------------
        # Horizontal dimension (above)
        # -----------------------
        y_dim = y0 - offset
        # Extension lines up to dim line
        ext1 = PathElement()
        ext1.path = inkex.Path(line_path(x0, y0, x0, y_dim))
        ext1.style = dim_line_style
        g.add(ext1)

        ext2 = PathElement()
        ext2.path = inkex.Path(line_path(x1, y0, x1, y_dim))
        ext2.style = dim_line_style
        g.add(ext2)

        # Dimension line
        dim_h = PathElement()
        dim_h.path = inkex.Path(line_path(x0, y_dim, x1, y_dim))
        dim_h.style = dim_line_style
        g.add(dim_h)

        # Arrowheads (pointing inward)
        ah1 = PathElement()
        ah1.path = inkex.Path(triangle_path(x0, y_dim, -1, 0, arrow_size))
        ah1.style = arrow_style
        g.add(ah1)

        ah2 = PathElement()
        ah2.path = inkex.Path(triangle_path(x1, y_dim, 1, 0, arrow_size))
        ah2.style = arrow_style
        g.add(ah2)

        # Text centered
        th = TextElement()
        th.text = w_txt
        th.set("x", str((x0 + x1) / 2))
        th.set("y", str(y_dim - 0.25 * text_height))  # small lift above the line
        th.style = text_style | {"text-anchor": "middle"}
        th.set("inkscape:label", "DIM_WIDTH")
        g.add(th)

        # -----------------------
        # Vertical dimension (right)
        # -----------------------
        x_dim = x1 + offset
        # Extension lines to dim line
        ext3 = PathElement()
        ext3.path = inkex.Path(line_path(x1, y0, x_dim, y0))
        ext3.style = dim_line_style
        g.add(ext3)

        ext4 = PathElement()
        ext4.path = inkex.Path(line_path(x1, y1, x_dim, y1))
        ext4.style = dim_line_style
        g.add(ext4)

        # Dimension line
        dim_v = PathElement()
        dim_v.path = inkex.Path(line_path(x_dim, y0, x_dim, y1))
        dim_v.style = dim_line_style
        g.add(dim_v)

        # Arrowheads (pointing inward)
        av1 = PathElement()
        av1.path = inkex.Path(triangle_path(x_dim, y0, 0, -1, arrow_size))
        av1.style = arrow_style
        g.add(av1)

        av2 = PathElement()
        av2.path = inkex.Path(triangle_path(x_dim, y1, 0, 1, arrow_size))
        av2.style = arrow_style
        g.add(av2)

        # --- Vertical text next to the line (like width) ---
        y_mid = (y0 + y1) / 2
        text_offset = 0.35 * text_height  # distance from dimension line

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

        # rotate 180 from previous -90 => +90
        tv.set("transform", f"rotate(90 {x_txt_v} {y_txt_v})")
        g.add(tv)



if __name__ == "__main__":
    StickerAddDimensions().run()
