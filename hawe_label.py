#!/usr/bin/env python3
import inkex
from inkex import PathElement, TextElement, Group
from math import floor, isfinite


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


def wrap_words(text: str, max_chars: int) -> list[str]:
    """Simple word wrap by character count."""
    text = " ".join((text or "").split())
    if not text:
        return [""]

    words = text.split(" ")
    lines = []
    cur = ""

    for w in words:
        if not cur:
            cur = w
            continue
        if len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w

    if cur:
        lines.append(cur)

    # If a single word exceeds max_chars, hard-break it
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


class StickerLabelGenerator(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--label_text", default="ENTER TEXT")
        pars.add_argument("--part_number", default="30XXXX")

        pars.add_argument("--width_in", default="1.5")
        pars.add_argument("--height_in", default="0.75")
        pars.add_argument("--radius_in", default="0.14")

        pars.add_argument("--border_thickness_in", default="0.03")
        pars.add_argument("--cut_gap_in", default="0.10")
        pars.add_argument("--pad_in", default="0.10")
        pars.add_argument("--main_font_in", default="0.22")
        pars.add_argument("--part_font_in", default="0.1")
        pars.add_argument("--line_spacing", default="1.10")
        pars.add_argument("--cut_line_width_in", default="0.01")

    def effect(self):
        label_text = (self.options.label_text or "").upper()
        part_number = (self.options.part_number or "").upper()

        width_in = parse_float(self.options.width_in, 1.5)
        height_in = parse_float(self.options.height_in, 0.75)
        radius_in = parse_float(self.options.radius_in, 0.14)

        border_thickness_in = parse_float(self.options.border_thickness_in, 0.03)
        cut_gap_in = parse_float(self.options.cut_gap_in, 0.10)
        pad_in = parse_float(self.options.pad_in, 0.10)
        main_font_in = parse_float(self.options.main_font_in, 0.22)
        part_font_in = parse_float(self.options.part_font_in, 0.12)
        line_spacing = parse_float(self.options.line_spacing, 1.10)
        cut_line_width_in = parse_float(self.options.cut_line_width_in, 0.01)

        for v, name in [
            (width_in, "width"),
            (height_in, "height"),
            (radius_in, "radius"),
            (border_thickness_in, "border thickness"),
            (cut_gap_in, "cut line gap"),
            (pad_in, "padding"),
            (main_font_in, "main font size"),
            (part_font_in, "part font size"),
            (line_spacing, "line spacing"),
            (cut_line_width_in, "cut line width"),
        ]:
            if not isfinite(v) or v <= 0:
                raise inkex.AbortExtension(f"{name} must be a positive number.")

        # Convert inches -> document user units (px)
        w = self.svg.unittouu(f"{width_in}in")
        h = self.svg.unittouu(f"{height_in}in")
        r = self.svg.unittouu(f"{radius_in}in")
        border_thickness = self.svg.unittouu(f"{border_thickness_in}in")
        cut_gap = self.svg.unittouu(f"{cut_gap_in}in")
        pad = self.svg.unittouu(f"{pad_in}in")
        main_fs = self.svg.unittouu(f"{main_font_in}in")
        part_fs = self.svg.unittouu(f"{part_font_in}in")
        cut_line_width = self.svg.unittouu(f"{cut_line_width_in}in")

        if w <= 2 * (cut_gap + border_thickness) or h <= 2 * (cut_gap + border_thickness):
            raise inkex.AbortExtension("Label is too small for cut gap + border thickness.")
        if r < (cut_gap + border_thickness):
            raise inkex.AbortExtension("Corner radius must be >= (cut gap + border thickness).")

        # Place near document origin (you can move after)
        x = 0.0
        y = 0.0

        # Group container
        g = Group()
        g.set("inkscape:label", "STICKER_LABEL")
        self.svg.get_current_layer().add(g)

        outer_bg = PathElement()
        outer_bg.path = inkex.Path(rounded_rect_path(x, y, w, h, r))
        outer_bg.style = {"fill": "#FFFFFF", "stroke": "none"}
        outer_bg.set("inkscape:label", "BACKGROUND_OUTER_FIELD")
        g.add(outer_bg)

        inner_fill = PathElement()
        inner_fill.path = inkex.Path(
            rounded_rect_path(x + cut_gap, y + cut_gap, w - 2 * cut_gap, h - 2 * cut_gap, r - cut_gap)
        )
        inner_fill.style = {"fill": "#000000", "stroke": "none"}
        inner_fill.set("inkscape:label", "BACKGROUND_INTERIOR")
        g.add(inner_fill)

        cut_line = PathElement()
        cut_line.path = inkex.Path(rounded_rect_path(x, y, w, h, r))
        cut_line.style = {
            "fill": "none",
            "stroke": "#000000",
            "stroke-width": str(cut_line_width),
            "stroke-linejoin": "round",
        }
        cut_line.set("inkscape:label", "CUT_LINE")
        g.add(cut_line)

        outer_in = cut_gap
        inner_in = cut_gap + border_thickness
        ring_outer = rounded_rect_path(x + outer_in, y + outer_in, w - 2 * outer_in, h - 2 * outer_in, r - outer_in)
        ring_inner = rounded_rect_path(x + inner_in, y + inner_in, w - 2 * inner_in, h - 2 * inner_in, r - inner_in)

        ring = PathElement()
        ring.path = inkex.Path(f"{ring_outer} {ring_inner}")
        ring.style = {"fill": "#000000", "stroke": "none"}
        ring.set("fill-rule", "evenodd")
        ring.set("inkscape:label", "MAIN_BORDER_GEOM")
        g.add(ring)

        # Main text wrapping
        # Approximate max characters per line based on available width and font size.
        # Average Arial glyph width ~0.55–0.60em; we use 0.58 * font size.
        avail_w = max(0.0, w - 2 * pad)
        avg_char_w = max(1e-6, 0.58 * main_fs)
        max_chars = max(4, int(floor(avail_w / avg_char_w)))

        lines = wrap_words(label_text, max_chars)

        # If too many lines to fit, gently reduce by merging/truncating
        # (keeps it deterministic and avoids text falling outside)
        max_lines = max(1, int(floor((h - 2 * pad) / (main_fs * line_spacing))))
        if len(lines) > max_lines:
            # compress: keep first (max_lines-1), put remainder on last
            kept = lines[: max_lines - 1]
            last = " ".join(lines[max_lines - 1 :])
            # hard-trim last line if absurdly long
            if len(last) > max_chars * 2:
                last = last[: max_chars * 2 - 1] + "…"
            lines = kept + [last]

        # Center block vertically in the label (but leave room for part number)
        # Reserve a little bottom-right area for part number.
        # Center main text block vertically on the label
        # Center main text block using line advance (fixes baseline bias)
        y_center = y + h / 2.0
        n = len(lines)
        advance = main_fs * line_spacing



        x_center = x + w / 2.0

        for i, line in enumerate(lines):
            yi = y_center + (i - (n - 1) / 2.0) * advance

            t = TextElement()
            t.text = line
            t.set("x", str(x_center))
            t.set("y", str(yi))
            t.style = {
                "font-family": "Arial",
                "font-weight": "bold",
                "font-size": str(main_fs),
                "fill": "#FFFFFF",
                "text-anchor": "middle",
                "dominant-baseline": "middle",
            }
            t.set("inkscape:label", f"MAIN_TEXT_{i+1}")
            g.add(t)


        # Part number (bottom-right)
        part = TextElement()
        part.text = part_number
        x_part = x + w - inner_in - pad
        y_part = y + h - inner_in - pad * 0.65
        part.set("x", str(x_part))
        part.set("y", str(y_part))
        part.style = {
            "font-family": "Arial",
            "font-weight": "normal",
            "font-size": str(part_fs),
            "fill": "#FFFFFF",
            "text-anchor": "end",
            "dominant-baseline": "alphabetic",
        }
        part.set("inkscape:label", "PART_NUMBER")
        g.add(part)


if __name__ == "__main__":
    StickerLabelGenerator().run()
