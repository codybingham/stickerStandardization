#!/usr/bin/env python3
import inkex
from inkex import PathElement
from math import isfinite


def parse_inch(v) -> float:
    """Accepts string or float, supports comma decimals, preserves precision."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return 0.0
    s = s.replace(",", ".")
    return float(s)


def rounded_rect_path(x, y, w, h, r):
    """SVG path for a rounded rectangle (clockwise)."""
    r = max(0.0, min(r, w / 2.0, h / 2.0))

    if r <= 1e-9:
        return f"M {x},{y} H {x+w} V {y+h} H {x} Z"

    x0, y0 = x, y
    x1, y1 = x + w, y + h

    d = []
    d.append(f"M {x0+r},{y0}")
    d.append(f"H {x1-r}")
    d.append(f"A {r},{r} 0 0 1 {x1},{y0+r}")
    d.append(f"V {y1-r}")
    d.append(f"A {r},{r} 0 0 1 {x1-r},{y1}")
    d.append(f"H {x0+r}")
    d.append(f"A {r},{r} 0 0 1 {x0},{y1-r}")
    d.append(f"V {y0+r}")
    d.append(f"A {r},{r} 0 0 1 {x0+r},{y0}")
    d.append("Z")

    return " ".join(d)


class RoundedDoubleBorderMaker(inkex.EffectExtension):
    def add_arguments(self, pars):
        # IMPORTANT: no type= here — we parse manually to keep thousandths+
        pars.add_argument("--thickness_in", default="0.060")
        pars.add_argument("--radius_in", default="0.000")
        pars.add_argument("--cut_stroke_in", default="0.005")
        pars.add_argument("--keep_master", type=inkex.Boolean, default=True)
        pars.add_argument("--remove_rect", type=inkex.Boolean, default=False)

    def effect(self):
        t_in = parse_inch(self.options.thickness_in)
        r_in = parse_inch(self.options.radius_in)
        cut_stroke_in = parse_inch(self.options.cut_stroke_in)

        if not isfinite(t_in) or t_in <= 0:
            raise inkex.AbortExtension("Main border thickness must be a positive number (inches).")

        if not isfinite(r_in) or r_in < 0:
            raise inkex.AbortExtension("Outside radius must be >= 0 (inches).")

        if not isfinite(cut_stroke_in) or cut_stroke_in <= 0:
            raise inkex.AbortExtension("Cut line stroke width must be a positive number (inches).")

        # Convert inches → document user units (px)
        t = self.svg.unittouu(f"{t_in}in")
        r_override = self.svg.unittouu(f"{r_in}in") if r_in > 0 else 0.0
        cut_sw = self.svg.unittouu(f"{cut_stroke_in}in")

        rects = [el for el in self.svg.selection.values() if el.tag.endswith("rect")]
        if not rects:
            raise inkex.AbortExtension("Select at least one live rectangle and run again.")

        for rect in rects:
            x = float(rect.get("x", 0))
            y = float(rect.get("y", 0))
            w = float(rect.get("width", 0))
            h = float(rect.get("height", 0))

            rx = float(rect.get("rx", 0) or 0)
            ry = float(rect.get("ry", 0) or 0)

            # Determine outside radius (cut line radius)
            if r_override > 0:
                r = r_override
            else:
                r = max(rx, ry)

            # Enforce Rx = Ry on the master rectangle
            rect.set("rx", str(r))
            rect.set("ry", str(r))

            # Need room for ring between inset t and 2t => inner loop dims (w-4t, h-4t) must remain positive
            if w <= 4 * t or h <= 4 * t:
                raise inkex.AbortExtension(
                    "Rectangle is too small for this thickness.\n"
                    "Need width and height > 4 × thickness."
                )

            # Radii constraints:
            # Cut line radius = r
            # Ring outer radius = r - t
            # Ring inner radius = r - 2t  => require r >= 2t
            if r < 2 * t:
                raise inkex.AbortExtension(
                    "Thickness is too large for the corner radius.\n"
                    "Need outside radius >= 2 × thickness (so inner radius stays >= 0)."
                )

            # Common stroke styling for cut lines
            stroke_color = rect.style.get("stroke", "#000000") or "#000000"

            # --- CUT LINE (same dimensions as original rectangle) ---
            d_cut = rounded_rect_path(x, y, w, h, r)
            cut = PathElement()
            cut.path = inkex.Path(d_cut)
            cut.style = rect.style.copy()
            cut.style["fill"] = "none"
            cut.style["stroke"] = stroke_color
            cut.style["stroke-width"] = str(cut_sw)
            cut.style["stroke-linejoin"] = "round"
            cut.style["stroke-linecap"] = "round"
            cut.set("inkscape:label", "CUT_LINE")

            # --- INNER CUT LINE (inset by t) : this rounds the “inner gap” corner you pointed out ---
            xg = x + t
            yg = y + t
            wg = w - 2 * t
            hg = h - 2 * t
            rg = r - t

            d_gap = rounded_rect_path(xg, yg, wg, hg, rg)
            gap_cut = PathElement()
            gap_cut.path = inkex.Path(d_gap)
            gap_cut.style = rect.style.copy()
            gap_cut.style["fill"] = "none"
            gap_cut.style["stroke"] = stroke_color
            gap_cut.style["stroke-width"] = str(cut_sw)
            gap_cut.style["stroke-linejoin"] = "round"
            gap_cut.style["stroke-linecap"] = "round"
            gap_cut.set("inkscape:label", "CUT_LINE_INNER")

            # --- MAIN BORDER GEOMETRY (ring inset by t from cut line, thickness t) ---
            # Outer loop at inset t
            x1 = x + t
            y1 = y + t
            w1 = w - 2 * t
            h1 = h - 2 * t
            r1 = r - t

            # Inner loop at inset 2t
            x2 = x + 2 * t
            y2 = y + 2 * t
            w2 = w - 4 * t
            h2 = h - 4 * t
            r2 = r - 2 * t

            d_outer = rounded_rect_path(x1, y1, w1, h1, r1)
            d_inner = rounded_rect_path(x2, y2, w2, h2, r2)
            d_ring = f"{d_outer} {d_inner}"

            ring = PathElement()
            ring.path = inkex.Path(d_ring)
            ring.style = rect.style.copy()
            ring.style["fill"] = rect.style.get("fill", "#000000") or "#000000"
            ring.style["stroke"] = "none"
            ring.set("fill-rule", "evenodd")
            ring.set("inkscape:label", "MAIN_BORDER_GEOM")

            # Insert next to original (order: cut line, inner cut line, ring)
            parent = rect.getparent()
            parent.add(cut)
            parent.add(gap_cut)
            parent.add(ring)

            # Master handling
            if self.options.keep_master and not self.options.remove_rect:
                rect.set("inkscape:label", "OUTSIDE_MASTER")
                rect.set("sodipodi:insensitive", "true")  # lock in UI
            if self.options.remove_rect:
                rect.delete()


if __name__ == "__main__":
    RoundedDoubleBorderMaker().run()
