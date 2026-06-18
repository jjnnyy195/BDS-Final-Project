"""
chart.py
========
Renders a multi-series line chart as a self-contained SVG string. No JS, no
chart library — keeps the deploy a single lightweight service and means the
chart renders even with scripts disabled.
"""

from typing import Dict, List

PALETTE = ["#f0b429", "#60a5fa", "#4ade80", "#f87171", "#c084fc", "#22d3ee"]


def line_chart(series: Dict[str, List[dict]], months: List[str],
               width: int = 1020, height: int = 300) -> str:
    pad_l, pad_r, pad_t, pad_b = 44, 16, 16, 30
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    if not months:
        return f'<svg viewBox="0 0 {width} {height}"></svg>'

    # Y axis is share 0..max (rounded up to a nice ceiling).
    max_share = 0.0
    for pts in series.values():
        for p in pts:
            max_share = max(max_share, p["share"])
    ceiling = max(0.1, (int(max_share * 10) + 1) / 10.0)

    def x(i):
        if len(months) == 1:
            return pad_l + plot_w / 2
        return pad_l + plot_w * i / (len(months) - 1)

    def y(share):
        return pad_t + plot_h * (1 - share / ceiling)

    parts = [f'<svg viewBox="0 0 {width} {height}" '
             f'xmlns="http://www.w3.org/2000/svg" '
             f'style="width:100%;height:auto;font-family:monospace">']

    # Horizontal gridlines + y labels.
    steps = 4
    for s in range(steps + 1):
        share = ceiling * s / steps
        yy = y(share)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{width-pad_r}" '
                     f'y2="{yy:.1f}" stroke="#1b242f" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-8}" y="{yy+3:.1f}" text-anchor="end" '
                     f'font-size="10" fill="#4d5a6e">{share*100:.0f}%</text>')

    # X labels (show every other month if crowded).
    every = 1 if len(months) <= 7 else 2
    for i, m in enumerate(months):
        if i % every == 0:
            parts.append(f'<text x="{x(i):.1f}" y="{height-10}" '
                         f'text-anchor="middle" font-size="10" fill="#4d5a6e">'
                         f'{m[2:]}</text>')

    # One polyline per series, indexed by the month axis.
    month_idx = {m: i for i, m in enumerate(months)}
    for k, (name, pts) in enumerate(series.items()):
        color = PALETTE[k % len(PALETTE)]
        coords = []
        for p in pts:
            if p["month"] in month_idx:
                coords.append((x(month_idx[p["month"]]), y(p["share"])))
        if not coords:
            continue
        d = " ".join(f'{px:.1f},{py:.1f}' for px, py in coords)
        parts.append(f'<polyline points="{d}" fill="none" stroke="{color}" '
                     f'stroke-width="2" stroke-linejoin="round"/>')
        for px, py in coords:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.5" '
                         f'fill="{color}"/>')

    parts.append('</svg>')
    return "".join(parts)
