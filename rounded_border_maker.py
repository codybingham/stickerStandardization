#!/usr/bin/env python3
import inkex
from inkex import PathElement
from math import isfinite


def parse_inch(v) -> float:
    """
    Robust parser:
    - Accepts string or float (Inkscape may pass either)
    - Preserves thousandths+
    - Accepts comma or dot decimal separators
    """
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
    """
    SVG path for a rounded rectangle (clockwise).
    """
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


class RoundedBorderMaker(inkex.EffectExtension):
    def add_arguments(self, pars):
        # IMPORTANT: no type= here — let us parse manually
        pars.add_argument("--thickness_in", default="0.060")
        pars.add_argument("--radius_in", default="0.000")
        pars.add_argument("--keep_master", type=inkex.Boolean, default=True)
        pars.add_argument("--remove_rect", type=inkex.Boolean, default=False)

    def effect(self):
        t_in = parse_inch(self.options.thickness_in)
        r_in = parse_inch(self.options.radius_in)

        if not isfinite(t_in) or t_in <= 0:
            raise inkex.AbortExtension("Border thickness must be a positive number (inches).")

        if not isfinite(r_in) or r_in < 0:
            raise inkex.AbortExtension("Outside radius must be >= 0 (inches).")

        # Convert inches → document user units (px)
        t = self.svg.unittouu(f"{t_in}in")
        r_override = self.svg.unittouu(f"{r_in}in") if r_in > 0 else 0.0

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

            # Determine outside radius
            if r_override > 0:
                r = r_override
            else:
                r = max(rx, ry)

            # Enforce Rx = Ry on the master rectangle
            rect.set("rx", str(r))
            rect.set("ry", str(r))

            if w <= 2*t or h <= 2*t:
                raise inkex.AbortExtension(
                    "Border thickness is too large for the rectangle size."
                )

            if r < t:
                raise inkex.AbortExtension(
                    "Thickness is larger than the corner radius "
                    "(inner radius would go negative)."
                )

            xi = x + t
            yi = y + t
            wi = w - 2*t
            hi = h - 2*t
            ri = r - t

            d_outer = rounded_rect_path(x, y, w, h, r)
            d_inner = rounded_rect_path(xi, yi, wi, hi, ri)

            # Compound path with even-odd fill → true border geometry
            d = f"{d_outer} {d_inner}"

            border = PathElement()
            border.path = inkex.Path(d)
            border.style = rect.style.copy()
            border.style["fill"] = rect.style.get("fill", "#000000") or "#000000"
            border.style["stroke"] = "none"
            border.set("fill-rule", "evenodd")
            border.set("inkscape:label", "BORDER_GEOM")

            rect.getparent().add(border)

            if self.options.keep_master and not self.options.remove_rect:
                rect.set("inkscape:label", "OUTSIDE_MASTER")
                rect.set("sodipodi:insensitive", "true")  # lock in UI

            if self.options.remove_rect:
                rect.delete()


if __name__ == "__main__":
    RoundedBorderMaker().run()
