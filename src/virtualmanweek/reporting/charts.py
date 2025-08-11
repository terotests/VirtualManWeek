from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict, Tuple, Optional

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


def _generate_weekly_project_table(cur, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> str:
    """Generate a table showing project time distribution by weekday."""
    import html as _html
    from collections import defaultdict
    
    # Query for project data with dates
    query = """
        SELECT date, start_ts, active_seconds, idle_seconds, manual_seconds, 
               project_id, p.code, p.name
        FROM time_entries te
        LEFT JOIN projects p ON te.project_id = p.id
    """
    
    params = []
    if start_date or end_date:
        conditions = []
        if start_date:
            conditions.append("start_ts >= ?")
            params.append(int(start_date.timestamp()))
        if end_date:
            conditions.append("start_ts <= ?")
            params.append(int(end_date.timestamp()))
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY date ASC"
    cur.execute(query, params)
    rows = cur.fetchall()
    
    if not rows:
        return "<p><em>No project data available.</em></p>"
    
    # Group data by project and weekday
    # Structure: {project_name: {date_key: total_seconds}}
    project_data = defaultdict(lambda: defaultdict(int))
    all_dates = set()
    all_projects = set()
    
    for r in rows:
        try:
            date_obj = datetime.strptime(r['date'], '%Y-%m-%d')
            weekday = date_obj.strftime('%A')  # Monday, Tuesday, etc.
            day_number = date_obj.strftime('%d.%m')  # 10.08
            date_key = f"{weekday}\n{day_number}"
            
            # Get project name
            if r['project_id'] and r['code']:
                if r['name']:
                    project_name = f"{r['code']} - {r['name']}"
                else:
                    project_name = r['code']
            elif r['project_id']:
                project_name = f"Project {r['project_id']}"
            else:
                project_name = "(No Project)"
            
            # Sum total time (active + idle + manual)
            total_time = (r['active_seconds'] or 0) + (r['idle_seconds'] or 0) + (r['manual_seconds'] or 0)
            
            project_data[project_name][date_key] += total_time
            all_dates.add(date_key)
            all_projects.add(project_name)
            
        except Exception:
            continue  # Skip invalid dates
    
    if not all_projects:
        return "<p><em>No project data with valid dates.</em></p>"
    
    # Sort dates by actual date (not string)
    def date_sort_key(date_key):
        try:
            # Extract day and month from format "Monday\n10.08"
            parts = date_key.split('\n')
            if len(parts) == 2:
                day_month = parts[1]  # "10.08"
                day, month = day_month.split('.')
                # Use current year for sorting, this might span year boundary but should be OK for weekly view
                year = datetime.now().year
                return datetime(year, int(month), int(day))
        except:
            pass
        return datetime.min
    
    sorted_dates = sorted(all_dates, key=date_sort_key)
    sorted_projects = sorted(all_projects)
    
    # Generate HTML table
    header_cells = ['<th class="project-col">Project</th>']
    for date_key in sorted_dates:
        header_cells.append(f'<th class="weekday-col">{_html.escape(date_key)}</th>')
    
    table_rows = ['<tr>' + ''.join(header_cells) + '</tr>']
    
    for project in sorted_projects:
        row_cells = [f'<td class="project-name">{_html.escape(project)}</td>']
        for date_key in sorted_dates:
            total_seconds = project_data[project][date_key]
            if total_seconds > 0:
                time_str = _fmt_time_short(total_seconds)
                row_cells.append(f'<td class="num">{time_str}</td>')
            else:
                row_cells.append('<td class="num">-</td>')
        table_rows.append('<tr>' + ''.join(row_cells) + '</tr>')
    
    table_html = f"""
    <h3>Weekly Project Distribution</h3>
    <table class="weekly-project">
        <thead>{''.join(table_rows[:1])}</thead>
        <tbody>{''.join(table_rows[1:])}</tbody>
    </table>
    """
    
    return table_html


def render_mode_distribution_html(html_path: Path, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> None:
    """Generate an HTML file with mode distribution using only Chart.js CDN and plain HTML.

    - Reads data via models.mode_distribution() and time_entries for detail sections
    - Chooses sensible unit scaling (s/min/h)
    - Writes to html_path
    - If start_date/end_date provided, filters data to that range
    """
    # Get mode distribution data
    mode_data = models.mode_distribution(start_date, end_date)
    project_data = models.project_distribution(start_date, end_date)
    
    if not mode_data and not project_data:
        # Write a minimal HTML stating no data so caller can still open it
        date_info = ""
        if start_date and end_date:
            date_info = f" for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        html_path.write_text(f"<html><body><p>No data yet{date_info}.</p></body></html>", encoding="utf-8")
        return
    
    # Calculate max value and unit scaling from both datasets
    max_val = 0
    total_time_seconds = 0
    if mode_data:
        max_val = max(max_val, max(int(r['total_active']) for r in mode_data))
        total_time_seconds += sum(int(r['total_active']) for r in mode_data)
    if project_data:
        max_val = max(max_val, max(int(r['total_active']) for r in project_data))
        # Don't double-count project data since it's the same time entries as modes
        # total_time_seconds is already counted from mode_data
    
    divisor, unit = compute_scale_unit(max_val)

    # Prepare mode data
    mode_labels: List[str] = [r['mode'] for r in mode_data] if mode_data else []
    mode_raw_values: List[int] = [int(r['total_active']) for r in mode_data] if mode_data else []
    if unit == 'Hours':
        mode_values = [round(v / divisor, 2) for v in mode_raw_values]
    elif unit == 'Minutes':
        mode_values = [round(v / divisor, 1) for v in mode_raw_values]
    else:
        mode_values = [int(v / divisor) for v in mode_raw_values]

    # Prepare project data
    project_labels: List[str] = [r['project_name'] for r in project_data] if project_data else []
    project_raw_values: List[int] = [int(r['total_active']) for r in project_data] if project_data else []
    if unit == 'Hours':
        project_values = [round(v / divisor, 2) for v in project_raw_values]
    elif unit == 'Minutes':
        project_values = [round(v / divisor, 1) for v in project_raw_values]
    else:
        project_values = [int(v / divisor) for v in project_raw_values]

    per_mode_tables: List[str] = []
    daily_tables: List[str] = []

    import html as _html
    with models.connect() as conn:
        cur = conn.cursor()
        # Per-mode details
        for mode in mode_labels:
            # Build query with date filtering
            base_query = "SELECT date, start_ts, end_ts, active_seconds, idle_seconds, manual_seconds, description FROM time_entries WHERE mode_label=?"
            params = [mode]
            
            if start_date:
                base_query += " AND start_ts >= ?"
                params.append(int(start_date.timestamp()))
            if end_date:
                base_query += " AND start_ts <= ?"
                params.append(int(end_date.timestamp()))
            
            base_query += " ORDER BY active_seconds DESC, start_ts DESC LIMIT 200"
            cur.execute(base_query, params)
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
        daily_query = "SELECT date, start_ts, active_seconds, idle_seconds, manual_seconds, mode_label, description FROM time_entries"
        daily_params = []
        
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append("start_ts >= ?")
                daily_params.append(int(start_date.timestamp()))
            if end_date:
                conditions.append("start_ts <= ?")
                daily_params.append(int(end_date.timestamp()))
            daily_query += " WHERE " + " AND ".join(conditions)
        
        daily_query += " ORDER BY date ASC, start_ts ASC LIMIT 2000"
        cur.execute(daily_query, daily_params)
        daily_rows = cur.fetchall()
        
        # Generate weekly project distribution table
        weekly_project_table = _generate_weekly_project_table(cur, start_date, end_date)
        
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
    
    # Include weekly project table
    weekly_project_section = weekly_project_table

    # Generate title with date range info
    title_suffix = ""
    if start_date and end_date:
        if start_date.date() == end_date.date():
            title_suffix = f" - {start_date.strftime('%Y-%m-%d')}"
        else:
            title_suffix = f" - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    elif start_date:
        title_suffix = f" - from {start_date.strftime('%Y-%m-%d')}"
    elif end_date:
        title_suffix = f" - until {end_date.strftime('%Y-%m-%d')}"

    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Time Distribution{title_suffix}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f9f9fb;color:#222}}
h2{{margin-top:0}}
h3{{margin-top:40px;border-bottom:2px solid #0A4F9C;padding-bottom:4px}}
#meta{{font-size:12px;color:#555;margin-bottom:12px}}
canvas{{border:1px solid #ddd;background:#fff;margin-bottom:30px}}
section.details h3, section.daily h3{{margin-top:40px;border-bottom:2px solid #0A4F9C;padding-bottom:4px}}
table.mode{{border-collapse:collapse;margin:12px 0 28px 0;width:100%;background:#fff;font-size:13px}}
table.mode th,table.mode td{{border:1px solid #ddd;padding:4px 6px;vertical-align:top}}
table.mode th{{background:#0A4F9C;color:#fff;text-align:left}}
table.weekly-project{{border-collapse:collapse;margin:12px 0 28px 0;width:100%;background:#fff;font-size:13px}}
table.weekly-project th,table.weekly-project td{{border:1px solid #ddd;padding:6px 8px;vertical-align:top;text-align:center}}
table.weekly-project th{{background:#0A4F9C;color:#fff;font-weight:bold}}
table.weekly-project th.project-col{{text-align:left;min-width:150px}}
table.weekly-project th.weekday-col{{min-width:80px;white-space:pre-line}}
table.weekly-project td.project-name{{text-align:left;font-weight:500;background:#f8f9fa}}
.num{{text-align:right;white-space:nowrap}}
.desc{{max-width:640px;}}
h4{{margin:28px 0 6px 0;color:#0A4F9C}}
.chart-section{{margin-bottom:40px}}
</style>
<script src='https://cdn.jsdelivr.net/npm/chart.js'></script></head><body>
<h2>Time Distribution{title_suffix}</h2>
<div id='meta'>Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &middot; Total time: {_fmt_time_short(total_time_seconds)}</div>

<div class='chart-section'>
<h3>Mode Distribution (Active {unit})</h3>
<canvas id='modeChart' width='1000' height='400'></canvas>
</div>

<div class='chart-section'>
<h3>Project Distribution (Active {unit})</h3>
<canvas id='projectChart' width='1000' height='400'></canvas>
</div>

<script>
// Mode distribution chart
const modeLabels = {mode_labels};
const modeDataVals = {mode_values};
const projectLabels = {project_labels};
const projectDataVals = {project_values};
const unit = '{unit}';

if (modeLabels.length > 0) {{
    new Chart(document.getElementById('modeChart').getContext('2d'), {{
        type: 'bar',
        data: {{ labels: modeLabels, datasets: [{{ label: 'Active ' + unit, data: modeDataVals, backgroundColor: '#0A4F9C'}}] }},
        options: {{ indexAxis: 'x', responsive: false, plugins: {{ legend: {{ position: 'bottom' }}, tooltip: {{ callbacks: {{ label: (ctx)=> ctx.parsed.y + ' ' + unit }} }} }}, scales: {{ y: {{ beginAtZero: true, title: {{ display:true, text: unit }} }} }} }}
    }});
}} else {{
    document.getElementById('modeChart').style.display = 'none';
    document.querySelector('h3').innerHTML = 'Mode Distribution (Active {unit}) - No data';
}}

if (projectLabels.length > 0) {{
    new Chart(document.getElementById('projectChart').getContext('2d'), {{
        type: 'bar',
        data: {{ labels: projectLabels, datasets: [{{ label: 'Active ' + unit, data: projectDataVals, backgroundColor: '#2E8B57'}}] }},
        options: {{ indexAxis: 'x', responsive: false, plugins: {{ legend: {{ position: 'bottom' }}, tooltip: {{ callbacks: {{ label: (ctx)=> ctx.parsed.y + ' ' + unit }} }} }}, scales: {{ y: {{ beginAtZero: true, title: {{ display:true, text: unit }} }} }} }}
    }});
}} else {{
    document.getElementById('projectChart').style.display = 'none';
    document.querySelectorAll('h3')[1].innerHTML = 'Project Distribution (Active {unit}) - No data';
}}
</script>
{weekly_project_section}
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


def export_mode_distribution_html_to(path: Path, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    render_mode_distribution_html(path, start_date, end_date)


def default_export_path() -> Path:
    return Path(appdata_root()) / "mode_distribution.html"
