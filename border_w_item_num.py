#!/usr/bin/env python3
import inkex
from inkex import PathElement, TextElement
from math import isfinite


def parse_inch(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return 0.0
    return float(s.replace(",", "."))


def rounded_rect_path(x, y, w, h, r):
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


class RoundedBorderItemNumber(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--thickness_in", default="0.060")
        pars.add_argument("--radius_in", default="0.000")
        pars.add_argument("--item_text", default="30XXXX")
        pars.add_argument("--text_height_in", default="0.100")
        pars.add_argument("--keep_master", type=inkex.Boolean, default=True)

    def effect(self):
        t_in = parse_inch(self.options.thickness_in)
        r_in = parse_inch(self.options.radius_in)
        text_height_in = parse_inch(self.options.text_height_in)
        item_text = (self.options.item_text or "").upper()

        if not isfinite(t_in) or t_in <= 0:
            raise inkex.AbortExtension("Border thickness must be positive.")
        if not isfinite(r_in) or r_in < 0:
            raise inkex.AbortExtension("Radius must be >= 0.")
        if not isfinite(text_height_in) or text_height_in <= 0:
            raise inkex.AbortExtension("Text height must be positive.")

        t = self.svg.unittouu(f"{t_in}in")
        r_override = self.svg.unittouu(f"{r_in}in") if r_in > 0 else 0.0
        text_height = self.svg.unittouu(f"{text_height_in}in")

        rects = [el for el in self.svg.selection.values() if el.tag.endswith("rect")]
        if not rects:
            raise inkex.AbortExtension("Select a live rectangle.")

        for rect in rects:
            x = float(rect.get("x", 0))
            y = float(rect.get("y", 0))
            w = float(rect.get("width", 0))
            h = float(rect.get("height", 0))

            rx = float(rect.get("rx", 0) or 0)
            ry = float(rect.get("ry", 0) or 0)

            r = r_override if r_override > 0 else max(rx, ry)
            rect.set("rx", str(r))
            rect.set("ry", str(r))

            if w <= 2*t or h <= 2*t:
                raise inkex.AbortExtension("Rectangle too small for thickness.")
            if r < t:
                raise inkex.AbortExtension("Radius must be >= thickness.")

            # --- Border geometry ---
            xi = x + t
            yi = y + t
            wi = w - 2*t
            hi = h - 2*t
            ri = r - t

            d_outer = rounded_rect_path(x, y, w, h, r)
            d_inner = rounded_rect_path(xi, yi, wi, hi, ri)

            border = PathElement()
            border.path = inkex.Path(f"{d_outer} {d_inner}")
            border.style = rect.style.copy()
            border.style["fill"] = rect.style.get("fill", "#000000") or "#000000"
            border.style["stroke"] = "none"
            border.set("fill-rule", "evenodd")
            border.set("inkscape:label", "MAIN_BORDER_GEOM")

            # --- Item number placement ---
            margin = 0.1 * t  # scales with border thickness

            x_text = x + w - (r - t) - margin
            y_text = y + h - (r - t) - margin

            text = TextElement()
            text.text = item_text
            text.set("x", str(x_text))
            text.set("y", str(y_text))
            text.style = {
                "font-size": str(text_height),
                "font-family": "Arial",
                "fill": "#000000",
                "text-anchor": "end",
                "dominant-baseline": "alphabetic"
            }
            text.set("inkscape:label", "ITEM_NUMBER")

            parent = rect.getparent()
            parent.add(border)
            parent.add(text)

            rect.delete()


if __name__ == "__main__":
    RoundedBorderItemNumber().run()
