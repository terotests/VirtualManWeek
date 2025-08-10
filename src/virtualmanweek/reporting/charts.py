from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict, Tuple

from ..db import models
from ..config import appdata_root

# HTML chart export (Chart.js via CDN) and rich tables

def compute_scale_unit(max_seconds: int) -> Tuple[float, str]:
    if max_seconds >= 3600:
        return 3600.0, "Hours"
    if max_seconds >= 600:
        return 60.0, "Minutes"
    return 1.0, "Seconds"


def _fmt_time_short(sec: int) -> str:
    """Format seconds into a readable time string.
    
    Examples:
    - 45 -> "45s"
    - 125 -> "2min 5s"
    - 3665 -> "1h 1min"
    """
    if sec < 60:
        return f"{sec}s"
    elif sec < 3600:
        minutes = sec // 60
        seconds = sec % 60
        if seconds == 0:
            return f"{minutes}min"
        return f"{minutes}min {seconds}s"
    else:
        hours = sec // 3600
        remaining = sec % 3600
        minutes = remaining // 60
        if minutes == 0:
            return f"{hours}h"
        return f"{hours}h {minutes}min"


def _fmt_dt(ts: int) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts)


def render_mode_distribution_html(html_path: Path) -> None:
    """Generate an HTML file with mode distribution using only Chart.js CDN and plain HTML.

    - Reads data via models.mode_distribution() and time_entries for detail sections
    - Chooses sensible unit scaling (s/min/h)
    - Writes to html_path
    """
    data = models.mode_distribution()
    if not data:
        # Write a minimal HTML stating no data so caller can still open it
        html_path.write_text("<html><body><p>No data yet.</p></body></html>", encoding="utf-8")
        return
    max_val = max(int(r['total_active']) for r in data)
    divisor, unit = compute_scale_unit(max_val)

    labels: List[str] = [r['mode'] for r in data]
    raw_values: List[int] = [int(r['total_active']) for r in data]
    if unit == 'Hours':
        values = [round(v / divisor, 2) for v in raw_values]
    elif unit == 'Minutes':
        values = [round(v / divisor, 1) for v in raw_values]
    else:
        values = [int(v / divisor) for v in raw_values]

    per_mode_tables: List[str] = []
    daily_tables: List[str] = []

    import html as _html
    with models.connect() as conn:
        cur = conn.cursor()
        # Per-mode details
        for mode in labels:
            cur.execute(
                "SELECT date, start_ts, end_ts, active_seconds, idle_seconds, manual_seconds, description FROM time_entries WHERE mode_label=? ORDER BY active_seconds DESC, start_ts DESC LIMIT 200",
                (mode,),
            )
            rows = cur.fetchall()
            if not rows:
                continue
            row_html_parts: List[str] = []
            for r in rows:
                desc = r["description"] or ""
                desc = _html.escape(desc).replace('\n', '<br/>')
                dt_str = _fmt_dt(r['start_ts'])
                active_fmt = _fmt_time_short(r['active_seconds'])
                idle_fmt = _fmt_time_short(r['idle_seconds']) if r['idle_seconds'] else ''
                manual_fmt = _fmt_time_short(r['manual_seconds'] if 'manual_seconds' in r.keys() and r['manual_seconds'] else 0) if ('manual_seconds' in r.keys() and r['manual_seconds']) else ''
                total_fmt = _fmt_time_short(r['active_seconds'] + (r['idle_seconds'] or 0) + (r['manual_seconds'] if 'manual_seconds' in r.keys() and r['manual_seconds'] else 0))
                row_html_parts.append(
                    f"<tr><td>{dt_str}</td><td class='num'>{active_fmt}</td><td class='num'>{idle_fmt}</td><td class='num'>{manual_fmt}</td><td class='num'>{total_fmt}</td><td class='desc'>{desc}</td></tr>"
                )
            table_html = (
                f"<h4>{_html.escape(mode)}</h4>"
                "<table class='mode'><thead><tr><th>Date/Start Time</th><th>Active</th><th>Idle</th><th>Manual</th><th>Total</th><th>Description</th></tr></thead><tbody>"
                + "".join(row_html_parts)
                + "</tbody></table>"
            )
            per_mode_tables.append(table_html)
        # Daily timeline
        cur.execute(
            "SELECT date, start_ts, active_seconds, idle_seconds, manual_seconds, mode_label, description FROM time_entries ORDER BY date ASC, start_ts ASC LIMIT 2000"
        )
        daily_rows = cur.fetchall()
        if daily_rows:
            from collections import defaultdict
            grouped: Dict[str, list] = defaultdict(list)
            for r in daily_rows:
                grouped[r['date']].append(r)
            for d in sorted(grouped.keys()):
                entries = grouped[d]
                try:
                    weekday = datetime.strptime(d, '%Y-%m-%d').strftime('%A')
                except Exception:
                    weekday = d
                row_parts: List[str] = []
                for r in entries:
                    t_str = datetime.fromtimestamp(r['start_ts']).strftime('%H:%M:%S') if r['start_ts'] else ''
                    desc = (r['description'] or '').replace('\n', ' ')
                    desc = _html.escape(desc)
                    active_fmt = _fmt_time_short(r['active_seconds'])
                    idle_fmt = _fmt_time_short(r['idle_seconds']) if r['idle_seconds'] else ''
                    manual_fmt = _fmt_time_short(r['manual_seconds'] if 'manual_seconds' in r.keys() and r['manual_seconds'] else 0) if ('manual_seconds' in r.keys() and r['manual_seconds']) else ''
                    total_fmt = _fmt_time_short(r['active_seconds'] + (r['idle_seconds'] or 0) + (r['manual_seconds'] if 'manual_seconds' in r.keys() and r['manual_seconds'] else 0))
                    row_parts.append(
                        f"<tr><td>{t_str}</td><td>{_html.escape(r['mode_label'])}</td><td class='num'>{active_fmt}</td><td class='num'>{idle_fmt}</td><td class='num'>{manual_fmt}</td><td class='num'>{total_fmt}</td><td class='desc'>{desc}</td></tr>"
                    )
                daily_tables.append(
                    f"<h4>{weekday} {d}</h4><table class='mode'><thead><tr><th>Start</th><th>Mode</th><th>Active</th><th>Idle</th><th>Manual</th><th>Total</th><th>Description</th></tr></thead><tbody>{''.join(row_parts)}</tbody></table>"
                )

    detail_section = "\n".join(per_mode_tables) if per_mode_tables else "<p><em>No detailed entries.</em></p>"
    daily_section = "\n".join(daily_tables) if daily_tables else "<p><em>No daily entries.</em></p>"

    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Mode Distribution</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f9f9fb;color:#222}}
h2{{margin-top:0}}
#meta{{font-size:12px;color:#555;margin-bottom:12px}}
canvas{{border:1px solid #ddd;background:#fff}}
section.details h3, section.daily h3{{margin-top:40px;border-bottom:2px solid #0A4F9C;padding-bottom:4px}}
table.mode{{border-collapse:collapse;margin:12px 0 28px 0;width:100%;background:#fff;font-size:13px}}
table.mode th,table.mode td{{border:1px solid #ddd;padding:4px 6px;vertical-align:top}}
table.mode th{{background:#0A4F9C;color:#fff;text-align:left}}
.num{{text-align:right;white-space:nowrap}}
.desc{{max-width:640px;}}
h4{{margin:28px 0 6px 0;color:#0A4F9C}}
</style>
<script src='https://cdn.jsdelivr.net/npm/chart.js'></script></head><body>
<h2>Mode Distribution (Active {unit})</h2>
<div id='meta'>Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &middot; Max raw seconds: {max_val}</div>
<canvas id='c' width='1000' height='500'></canvas>
<script>
const labels = {labels};
const dataVals = {values};
const unit = '{unit}';
new Chart(document.getElementById('c').getContext('2d'), {{
  type: 'bar',
  data: {{ labels: labels, datasets: [{{ label: 'Active ' + unit, data: dataVals, backgroundColor: '#0A4F9C'}}] }},
  options: {{ indexAxis: 'x', responsive: false, plugins: {{ legend: {{ position: 'bottom' }}, tooltip: {{ callbacks: {{ label: (ctx)=> ctx.parsed.y + ' ' + unit }} }} }}, scales: {{ y: {{ beginAtZero: true, title: {{ display:true, text: unit }} }} }} }}
}});
</script>
<section class='daily'>
<h3>Daily Timeline</h3>
{daily_section}
</section>
<section class='details'>
<h3>Detailed Entries (Per Mode)</h3>
{detail_section}
</section>
</body></html>"""
    html_path.write_text(html, encoding='utf-8')


def export_mode_distribution_html_to(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    render_mode_distribution_html(path)


def default_export_path() -> Path:
    return Path(appdata_root()) / "mode_distribution.html"
