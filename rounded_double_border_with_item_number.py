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

    d = [
        f"M {x0+r},{y0}",
        f"H {x1-r}",
        f"A {r},{r} 0 0 1 {x1},{y0+r}",
        f"V {y1-r}",
        f"A {r},{r} 0 0 1 {x1-r},{y1}",
        f"H {x0+r}",
        f"A {r},{r} 0 0 1 {x0},{y1-r}",
        f"V {y0+r}",
        f"A {r},{r} 0 0 1 {x0+r},{y0}",
        "Z",
    ]
    return " ".join(d)


class RoundedDoubleBorderItem(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--thickness_in", default="0.060")
        pars.add_argument("--radius_in", default="0.000")
        pars.add_argument("--cut_stroke_in", default="0.005")
        pars.add_argument("--item_text", default="30XXXX")
        pars.add_argument("--text_height_in", default="0.100")

    def effect(self):
        t_in = parse_inch(self.options.thickness_in)
        r_in = parse_inch(self.options.radius_in)
        cut_sw_in = parse_inch(self.options.cut_stroke_in)
        text_height_in = parse_inch(self.options.text_height_in)
        item_text = self.options.item_text

        if not isfinite(t_in) or t_in <= 0:
            raise inkex.AbortExtension("Thickness must be positive.")
        if not isfinite(r_in) or r_in < 0:
            raise inkex.AbortExtension("Radius must be >= 0.")
        if not isfinite(cut_sw_in) or cut_sw_in <= 0:
            raise inkex.AbortExtension("Cut stroke must be positive.")

        t = self.svg.unittouu(f"{t_in}in")
        r_override = self.svg.unittouu(f"{r_in}in") if r_in > 0 else 0.0
        cut_sw = self.svg.unittouu(f"{cut_sw_in}in")
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

            if w <= 4*t or h <= 4*t:
                raise inkex.AbortExtension("Rectangle too small for thickness.")
            if r < 2*t:
                raise inkex.AbortExtension("Radius must be >= 2 × thickness.")

            parent = rect.getparent()
            stroke_color = rect.style.get("stroke", "#000000") or "#000000"

            # --- Outer cut line ---
            cut_outer = PathElement()
            cut_outer.path = inkex.Path(rounded_rect_path(x, y, w, h, r))
            cut_outer.style = {
                "fill": "none",
                "stroke": stroke_color,
                "stroke-width": str(cut_sw),
                "stroke-linejoin": "round",
            }
            cut_outer.set("inkscape:label", "CUT_LINE")

            # --- Inner cut line ---
            cut_inner = PathElement()
            cut_inner.path = inkex.Path(
                rounded_rect_path(x+t, y+t, w-2*t, h-2*t, r-t)
            )
            cut_inner.style = cut_outer.style.copy()
            cut_inner.set("inkscape:label", "CUT_LINE_INNER")

            # --- Main border ring ---
            ring = PathElement()
            ring.path = inkex.Path(
                f"{rounded_rect_path(x+t, y+t, w-2*t, h-2*t, r-t)} "
                f"{rounded_rect_path(x+2*t, y+2*t, w-4*t, h-4*t, r-2*t)}"
            )
            ring.style = {"fill": "#000000", "stroke": "none"}
            ring.set("fill-rule", "evenodd")
            ring.set("inkscape:label", "MAIN_BORDER_GEOM")

            # --- Item number ---
            margin = 0.2 * t
            x_text = x + w - (r - t) - margin
            y_text = y + h - (r - t) - margin

            text = TextElement()
            text.text = item_text
            text.set("x", str(x_text))
            text.set("y", str(y_text))
            text.style = {
                "font-family": "Arial",
                "font-size": str(text_height),
                "fill": "#000000",
                "text-anchor": "end",
                "dominant-baseline": "alphabetic",
            }
            text.set("inkscape:label", "ITEM_NUMBER")

            parent.add(cut_outer)
            parent.add(cut_inner)
            parent.add(ring)
            parent.add(text)

            # Always consume the original rectangle
            rect.delete()


if __name__ == "__main__":
    RoundedDoubleBorderItem().run()
