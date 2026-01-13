#!/usr/bin/env python3
import inkex
from inkex import PathElement, TextElement, Group
from math import floor, isfinite

FIXED_HEIGHT_IN = 1.0625


def parse_float(v, default=0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return default
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


def wrap_words_to_width(text: str, max_chars: int) -> list[str]:
    text = " ".join((text or "").split())
    if not text:
        return [""]

    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    # hard-break ultra-long words
    fixed = []
    for line in lines:
        if len(line) <= max_chars:
            fixed.append(line)
        else:
            s = line
            while len(s) > max_chars:
                fixed.append(s[:max_chars])
                s = s[max_chars:]
            if s:
                fixed.append(s)
    return fixed


class BucherStickerGenerator(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--background", default="white")

        pars.add_argument("--num_sections", type=int, default=4)
        pars.add_argument("--section_spacing_in", default="1.25")  # CELL WIDTH
        pars.add_argument("--end_margin_in", default="0.25")       # EDGE -> CELL EDGE
        pars.add_argument("--section_names", default="")

        pars.add_argument("--corner_radius_in", default="0.25")

        pars.add_argument("--border_thickness_in", default="0.03")
        pars.add_argument("--cut_gap_in", default="0.10")          # NEW
        pars.add_argument("--cut_line_width_in", default="0.01")

        pars.add_argument("--label_font_in", default="0.20")       # NEW
        pars.add_argument("--part_font_in", default="0.12")        # NEW

        pars.add_argument("--part_number", default="30XXXX")
        pars.add_argument("--part_location", default="right")
        pars.add_argument("--part_offset_in", default="0.08")      # NEW

        pars.add_argument("--dot_rows", type=int, default=2)
        pars.add_argument("--dot_cols", type=int, default=4)
        pars.add_argument("--dot_diam_in", default="0.06")
        pars.add_argument("--dot_pitch_x_in", default="0.15")
        pars.add_argument("--dot_pitch_y_in", default="0.15")
        pars.add_argument("--dot_stroke_in", default="0.012")

    def effect(self):
        bg_mode = (self.options.background or "white").lower()
        n = int(self.options.num_sections)

        spacing_in = parse_float(self.options.section_spacing_in, 1.25)
        end_margin_in = parse_float(self.options.end_margin_in, 0.25)

        radius_in = parse_float(self.options.corner_radius_in, 0.25)

        t_in = parse_float(self.options.border_thickness_in, 0.03)
        gap_in = parse_float(self.options.cut_gap_in, 0.10)
        cut_w_in = parse_float(self.options.cut_line_width_in, 0.01)

        label_fs_in = parse_float(self.options.label_font_in, 0.20)
        part_fs_in = parse_float(self.options.part_font_in, 0.12)

        part_number = (self.options.part_number or "30XXXX").upper()
        part_location = (self.options.part_location or "right").lower()
        part_offset_in = parse_float(self.options.part_offset_in, 0.08)

        dot_rows = int(self.options.dot_rows)
        dot_cols = int(self.options.dot_cols)
        dot_d_in = parse_float(self.options.dot_diam_in, 0.06)
        dot_px_in = parse_float(self.options.dot_pitch_x_in, 0.15)
        dot_py_in = parse_float(self.options.dot_pitch_y_in, 0.15)
        dot_sw_in = parse_float(self.options.dot_stroke_in, 0.012)

        if n <= 0:
            raise inkex.AbortExtension("Number of valve sections must be > 0.")

        for v, name in [
            (spacing_in, "Section spacing"),
            (end_margin_in, "End margin"),
            (radius_in, "Corner radius"),
            (t_in, "Border thickness"),
            (gap_in, "Cut line gap"),
            (cut_w_in, "Cut line width"),
            (label_fs_in, "Label font size"),
            (part_fs_in, "Part font size"),
            (part_offset_in, "Part offset"),
            (dot_d_in, "Dot diameter"),
            (dot_px_in, "Dot pitch X"),
            (dot_py_in, "Dot pitch Y"),
            (dot_sw_in, "Dot stroke width"),
        ]:
            if not isfinite(v) or v <= 0:
                raise inkex.AbortExtension(f"{name} must be a positive number.")

        if dot_rows <= 0 or dot_cols <= 0:
            raise inkex.AbortExtension("Dot grid rows/columns must be > 0.")

        # Fixed height
        h = self.svg.unittouu(f"{FIXED_HEIGHT_IN}in")

        # End margin is EDGE -> CELL EDGE, spacing is CELL WIDTH
        # Total length = 2*end_margin + N*spacing
        L_in = 2.0 * end_margin_in + n * spacing_in
        w = self.svg.unittouu(f"{L_in}in")

        spacing = self.svg.unittouu(f"{spacing_in}in")
        end_margin = self.svg.unittouu(f"{end_margin_in}in")
        r = self.svg.unittouu(f"{radius_in}in")

        t = self.svg.unittouu(f"{t_in}in")
        gap = self.svg.unittouu(f"{gap_in}in")
        cut_w = self.svg.unittouu(f"{cut_w_in}in")

        label_fs = self.svg.unittouu(f"{label_fs_in}in")
        part_fs = self.svg.unittouu(f"{part_fs_in}in")
        part_off = self.svg.unittouu(f"{part_offset_in}in")

        dot_d = self.svg.unittouu(f"{dot_d_in}in")
        dot_px = self.svg.unittouu(f"{dot_px_in}in")
        dot_py = self.svg.unittouu(f"{dot_py_in}in")
        dot_sw = self.svg.unittouu(f"{dot_sw_in}in")

        # Always black border + cut line per spec
        cut_color = "#000000"
        border_color = "#000000"

        # ✅ Make the outer "field" white always so the gap stays white even in black mode
        outer_field_fill = "#FFFFFF"
        if bg_mode == "black":
            interior_fill = "#000000"
            text_color = "#FFFFFF"
        else:
            interior_fill = "#FFFFFF"
            text_color = "#000000"

        # Parse section names
        raw = self.options.section_names or ""
        names = [(" ".join(s.strip().split())).upper() for s in raw.split(",") if s is not None]
        if len(names) < n:
            names += [""] * (n - len(names))
        if len(names) > n:
            names = names[:n]

        # Validate geometry for ring + gap
        # Border ring outer inset = gap, inner inset = gap + t
        # Need enough room and radius >= gap + t
        if w <= 2 * (gap + t) or h <= 2 * (gap + t):
            raise inkex.AbortExtension("Sticker too small for cut line gap + border thickness.")
        if r < (gap + t):
            raise inkex.AbortExtension("Corner radius must be >= (cut gap + border thickness).")

        x0, y0 = 0.0, 0.0

        g_all = Group()
        g_all.set("inkscape:label", "BUCHER_STICKER")
        self.svg.get_current_layer().add(g_all)

        # Outer field (white)
        outer_bg = PathElement()
        outer_bg.path = inkex.Path(rounded_rect_path(x0, y0, w, h, r))
        outer_bg.style = {"fill": outer_field_fill, "stroke": "none"}
        outer_bg.set("inkscape:label", "BACKGROUND_OUTER_FIELD")
        g_all.add(outer_bg)

        # Interior fill (white or black) - starts at the OUTER edge of the border ring
        outer_in = gap
        inner_in = gap + t

        if bg_mode == "black":
            inner_fill = PathElement()
            inner_fill.path = inkex.Path(
                rounded_rect_path(x0 + outer_in, y0 + outer_in, w - 2 * outer_in, h - 2 * outer_in, r - outer_in)
            )
            inner_fill.style = {"fill": interior_fill, "stroke": "none"}
            inner_fill.set("inkscape:label", "BACKGROUND_INTERIOR")
            g_all.add(inner_fill)
        # for white mode, the outer field is already white so no need for a second rect

        # Cut line (outer)
        cut = PathElement()
        cut.path = inkex.Path(rounded_rect_path(x0, y0, w, h, r))
        cut.style = {
            "fill": "none",
            "stroke": cut_color,
            "stroke-width": str(cut_w),
            "stroke-linejoin": "round",
        }
        cut.set("inkscape:label", "CUT_LINE")
        g_all.add(cut)

        # Border ring (black)
        d_outer = rounded_rect_path(x0 + outer_in, y0 + outer_in, w - 2 * outer_in, h - 2 * outer_in, r - outer_in)
        d_inner = rounded_rect_path(x0 + inner_in, y0 + inner_in, w - 2 * inner_in, h - 2 * inner_in, r - inner_in)

        ring = PathElement()
        ring.path = inkex.Path(f"{d_outer} {d_inner}")
        ring.style = {"fill": border_color, "stroke": "none"}
        ring.set("fill-rule", "evenodd")
        ring.set("inkscape:label", "MAIN_BORDER_GEOM")
        g_all.add(ring)

        # Text area (inside ring inner edge)
        inner_x = x0 + inner_in
        inner_y = y0 + inner_in
        inner_w = w - 2 * inner_in
        inner_h = h - 2 * inner_in

        # Wrapping logic uses fixed font size input (one size for all labels)
        line_spacing = 1.10
        avg_char_factor = 0.58

        cell_w = spacing
        cell_pad_x = 0.08 * spacing
        usable_cell_w = max(1.0, cell_w - 2 * cell_pad_x)

        top_pad = 0.10 * inner_h
        bot_pad = 0.12 * inner_h
        usable_h = max(1.0, inner_h - top_pad - bot_pad)

        def max_chars_for_fs(fs):
            return max(3, int(floor(usable_cell_w / max(1e-6, avg_char_factor * fs))))

        # Draw labels centered in each cell
        for i in range(n):
            cx = x0 + end_margin + (i + 0.5) * spacing
            nm = names[i] if i < len(names) else ""
            is_jack = ("JACK" in (nm or ""))

            max_chars = max_chars_for_fs(label_fs)
            lines = wrap_words_to_width(nm, max_chars)

            # If it doesn't fit vertically, we still draw (per your request: fixed font size),
            # but we keep the same placement logic.
            if is_jack:
                y_label_center = inner_y + top_pad + 0.35 * usable_h
                y_grid_center = inner_y + top_pad + 0.78 * usable_h
            else:
                y_label_center = inner_y + top_pad + 0.52 * usable_h
                y_grid_center = None

            nlines = len(lines)
            advance = label_fs * line_spacing

            for li, line in enumerate(lines):
                yi = y_label_center + (li - (nlines - 1) / 2.0) * advance
                ttxt = TextElement()
                ttxt.text = line
                ttxt.set("x", str(cx))
                ttxt.set("y", str(yi))
                ttxt.style = {
                    "font-family": "Arial",
                    "font-weight": "bold",
                    "font-size": str(label_fs),
                    "fill": text_color,
                    "text-anchor": "middle",
                    "dominant-baseline": "middle",
                }
                g_all.add(ttxt)

            # Jack dots
            if is_jack:
                grid_w = (dot_cols - 1) * dot_px + dot_d
                grid_h = (dot_rows - 1) * dot_py + dot_d
                gx0 = cx - grid_w / 2.0
                gy0 = y_grid_center - grid_h / 2.0

                # white bg: hollow dots; black bg: filled white dots
                if bg_mode == "black":
                    dot_fill = "#FFFFFF"
                    dot_stroke = "none"
                    dot_sw_use = "0"
                else:
                    dot_fill = "none"
                    dot_stroke = text_color
                    dot_sw_use = str(dot_sw)

                for rr in range(dot_rows):
                    for cc in range(dot_cols):
                        cx_dot = gx0 + cc * dot_px + dot_d / 2.0
                        cy_dot = gy0 + rr * dot_py + dot_d / 2.0
                        rad = dot_d / 2.0
                        d = (
                            f"M {cx_dot + rad},{cy_dot} "
                            f"A {rad},{rad} 0 1 0 {cx_dot - rad},{cy_dot} "
                            f"A {rad},{rad} 0 1 0 {cx_dot + rad},{cy_dot} Z"
                        )
                        circ = PathElement()
                        circ.path = inkex.Path(d)
                        circ.style = {"fill": dot_fill, "stroke": dot_stroke, "stroke-width": dot_sw_use}
                        g_all.add(circ)

        # Part number (Arial Regular) with configurable offset
        if part_location == "left":
            x_pn = inner_x + part_off
            anchor = "start"
        else:
            x_pn = inner_x + inner_w - part_off
            anchor = "end"

        # Bottom offset uses the same input (pull up from bottom edge)
        y_pn = inner_y + inner_h - part_off

        part = TextElement()
        part.text = part_number
        part.set("x", str(x_pn))
        part.set("y", str(y_pn))
        part.style = {
            "font-family": "Arial",
            "font-weight": "normal",
            "font-size": str(part_fs),
            "fill": text_color,
            "text-anchor": anchor,
            "dominant-baseline": "alphabetic",
        }
        part.set("inkscape:label", "PART_NUMBER")
        g_all.add(part)


if __name__ == "__main__":
    BucherStickerGenerator().run()
