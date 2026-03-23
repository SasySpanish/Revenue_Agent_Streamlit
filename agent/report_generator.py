# report_generator.py  
# Genera report discorsivi con llama-3.3-70b via Groq.
# Report più ricchi, strutturati e dettagliati rispetto alla versione Ollama.

import json
import os
import base64
from pathlib import Path
from langchain_core.tools import tool
from config_llm import get_report_llm


# ---------------------------------------------------------------------------
# PROMPT DI SISTEMA
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior equity research analyst with 20 years of 
experience covering European and US equities. You write institutional-quality 
financial reports that are clear, data-driven, and actionable.

Your reports always follow this structure's points:
1. **Executive Summary** — 3-5 sentences covering the key takeaway
2. **Sector Overview** — brief context on the sector and macro environment
3. **Company Analysis** — for each company: strengths, weaknesses, standout metrics
4. **Comparative Analysis** — who leads and who lags, and why
5. **Risk Flags** — companies below critical thresholds with explanation
6. **Conclusion** — investment narrative and key watch items

Rules:
- Be specific: cite actual numbers from the data
- Be direct: avoid filler phrases and generic statements
- Flag anomalies: negative margins, extreme leverage, outlier multiples
- Write in flowing prose, not bullet points
- Length: 600-900 words per point
- Language: English"""


# ---------------------------------------------------------------------------
# PROMPT BUILDER
# ---------------------------------------------------------------------------

def _build_prompt(summary: dict, group_stats: dict, companies: list) -> str:
    company_names = [
        c.get("name", c) if isinstance(c, dict) else c
        for c in companies
    ]

    lines = [
        f"Write a full equity research report for the following "
        f"{len(summary)} companies: {', '.join(company_names)}.\n",
        "## Financial Data (latest available fiscal year)\n",
    ]

    for company, indicators in summary.items():
        lines.append(f"### {company}")
        for k, v in indicators.items():
            val = f"{v:.2f}" if isinstance(v, float) and v is not None else "N/A"
            lines.append(f"- {k}: {val}")
        lines.append("")

    if group_stats:
        lines.append("## Group Statistics\n")
        if "median" in group_stats:
            lines.append("**Group Medians:**")
            for k, v in group_stats["median"].items():
                lines.append(
                    f"- {k}: {v:.2f}" if isinstance(v, float) else f"- {k}: {v}"
                )
        if "best" in group_stats:
            lines.append("\n**Best performer per indicator:**")
            for k, v in group_stats["best"].items():
                lines.append(f"- {k}: {v}")
        if "worst" in group_stats:
            lines.append("\n**Needs attention per indicator:**")
            for k, v in group_stats["worst"].items():
                lines.append(f"- {k}: {v}")

    lines.append(
        "\n## Critical Thresholds to check\n"
        "Flag any company below these sector benchmarks:\n"
        "- EBIT Margin < 5%\n"
        "- ROE < 10%\n"
        "- ROI/ROCE < 8%\n"
        "- Net Margin < 3%\n"
        "- Debt/Equity > 2x\n"
        "- Current Ratio < 1x\n"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GENERAZIONE TESTO
# ---------------------------------------------------------------------------

def generate_report_text(summary: dict, group_stats: dict,
                          companies: list) -> str:
    print("[report_generator] Generando report con llama-3.3-70b...")
    llm    = get_report_llm()
    prompt = _build_prompt(summary, group_stats, companies)

    response = llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("human",  prompt),
    ])

    text = response.content.strip()
    print(f"[report_generator] Report generato ({len(text)} caratteri)")
    return text


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _encode_image(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _collect_charts(output_dir: str) -> list[dict]:
    charts_dir = os.path.join(output_dir, "charts")
    if not os.path.exists(charts_dir):
        return []
    charts = []
    for f in sorted(Path(charts_dir).glob("*.png")):
        b64 = _encode_image(str(f))
        if b64:
            label = f.stem.replace("_", " ").replace("bar ", "").title()
            charts.append({"label": label, "data": b64})
    return charts


def _render_report_html(text: str) -> str:
    """Converte il testo markdown-like in HTML."""
    html = ""
    in_ul = False
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if in_ul:
                html += "</ul>\n"
                in_ul = False
            continue
        if line.startswith("## "):
            html += f"<h2>{line[3:]}</h2>\n"
        elif line.startswith("### "):
            html += f"<h3>{line[4:]}</h3>\n"
        elif line.startswith("**") and line.endswith("**"):
            html += f"<p><strong>{line[2:-2]}</strong></p>\n"
        elif line.startswith("- "):
            if not in_ul:
                html += "<ul>\n"
                in_ul = True
            html += f"<li>{line[2:]}</li>\n"
        else:
            if in_ul:
                html += "</ul>\n"
                in_ul = False
            # Gestisce **bold** inline
            import re
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            html += f"<p>{line}</p>\n"
    if in_ul:
        html += "</ul>\n"
    return html


# ---------------------------------------------------------------------------
# EXPORT HTML
# ---------------------------------------------------------------------------

def generate_html_report(report_text: str, output_dir: str,
                          companies: list, summary: dict) -> str:
    charts = _collect_charts(output_dir)
    company_names = [
        c.get("name", c) if isinstance(c, dict) else c
        for c in companies
    ]

    # Tabella indicatori
    if summary:
        indicators   = list(next(iter(summary.values())).keys())
        table_headers = "".join(f"<th>{i}</th>" for i in indicators)
        table_rows   = ""
        for company, vals in summary.items():
            def _fmt(v):
                if v is None:
                    return "N/A"
                try:
                    return f"{float(v):.2f}"
                except Exception:
                    return str(v)
            cells = "".join(f"<td>{_fmt(vals.get(ind))}</td>" for ind in indicators)
            table_rows += f"<tr><td><b>{company}</b></td>{cells}</tr>\n"
        table_html = f"""
        <div style="overflow-x:auto">
        <table>
          <thead><tr><th>Company</th>{table_headers}</tr></thead>
          <tbody>{table_rows}</tbody>
        </table>
        </div>"""
    else:
        table_html = "<p>No data available.</p>"

    # Grafici
    charts_html = ""
    for chart in charts:
        charts_html += f"""
        <div class="chart-card">
          <h3>{chart['label']}</h3>
          <img src="data:image/png;base64,{chart['data']}" alt="{chart['label']}">
        </div>"""

    report_html  = _render_report_html(report_text)
    dashboard_path = os.path.join(output_dir, "trend_dashboard.html")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Financial Analysis Report — {' · '.join(company_names)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f0f4f8; color: #1a1a2e; line-height: 1.75;
  }}
  header {{
    background: linear-gradient(135deg, #03045e, #0077b6);
    color: white; padding: 36px 48px;
  }}
  header h1  {{ font-size: 1.9rem; font-weight: 700; }}
  header p   {{ opacity: 0.8; margin-top: 6px; font-size: 0.95rem; }}
  header small {{ opacity: 0.6; font-size: 0.8rem; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px; }}
  .card {{
    background: white; border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    padding: 32px; margin-bottom: 28px;
  }}
  h2 {{
    font-size: 1.2rem; color: #03045e;
    border-bottom: 2px solid #0077b6;
    padding-bottom: 8px; margin: 24px 0 14px;
  }}
  h3  {{ font-size: 1rem; color: #0077b6; margin: 18px 0 8px; }}
  p   {{ margin-bottom: 12px; }}
  ul  {{ margin: 8px 0 12px 22px; }}
  li  {{ margin-bottom: 5px; }}
  table {{
    width: 100%; border-collapse: collapse;
    font-size: 0.8rem; margin-top: 12px;
  }}
  th {{
    background: #03045e; color: white;
    padding: 9px 11px; text-align: left; white-space: nowrap;
  }}
  td  {{ padding: 8px 11px; border-bottom: 1px solid #e8eef5; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8fbff; }}
  .dashboard-btn {{
    display: inline-block; background: #0077b6; color: white;
    padding: 11px 22px; border-radius: 6px; text-decoration: none;
    font-weight: 600; margin-bottom: 28px; font-size: 0.95rem;
  }}
  .dashboard-btn:hover {{ background: #023e8a; }}
  .charts-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
    gap: 20px;
  }}
  .chart-card {{
    background: white; border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07); padding: 18px;
  }}
  .chart-card h3 {{ font-size: 0.88rem; margin-bottom: 10px; color: #03045e; }}
  .chart-card img {{ width: 100%; height: auto; border-radius: 6px; }}
  .badge {{
    display: inline-block; background: #e8f4fd; color: #0077b6;
    padding: 3px 10px; border-radius: 20px;
    font-size: 0.78rem; font-weight: 600; margin-right: 6px;
  }}
  footer {{
    text-align: center; font-size: 0.78rem;
    color: #888; padding: 24px;
  }}
</style>
</head>
<body>

<header>
  <h1>📊 Financial Analysis Report</h1>
  <p>{' &nbsp;·&nbsp; '.join(company_names)}</p>
  <small>Generated by sasyspanish · groq's llama-3.3-70b-versatile · 
  Data: Yahoo Finance</small>
</header>

<div class="container">

  {'<a class="dashboard-btn" href="trend_dashboard.html" target="_blank">📈 Open Interactive Dashboard</a>' if os.path.exists(dashboard_path) else ''}

  <div class="card">
    <h2>Analyst Commentary</h2>
    {report_html}
  </div>

  <div class="card">
    <h2>Key Indicators — Latest Fiscal Year</h2>
    {table_html}
  </div>

  <h2 style="margin:0 0 16px;padding:0;border:none;color:#03045e">Charts</h2>
  <div class="charts-grid">
    {charts_html}
  </div>

</div>

<footer>
  Data source: Yahoo Finance via yfinance &nbsp;·&nbsp;
  For educational / personal use only &nbsp;·&nbsp;
  wheelhouse-agent-groq
</footer>

</body>
</html>"""

    html_path = os.path.join(output_dir, "report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[report_generator] ✅ HTML salvato: {html_path}")
    return html_path


# ---------------------------------------------------------------------------
# EXPORT PDF
# ---------------------------------------------------------------------------

def generate_pdf_report(report_text: str, output_dir: str,
                        companies: list) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    company_names = [
        c.get("name", c) if isinstance(c, dict) else c
        for c in companies
    ]
    pdf_path = os.path.join(output_dir, "report.pdf")

    with PdfPages(pdf_path) as pdf:
        # Pagina titolo
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        ax.text(0.5, 0.72, "Financial Analysis Report",
                ha="center", va="center", fontsize=28,
                fontweight="bold", color="#03045e",
                transform=ax.transAxes)
        ax.text(0.5, 0.60, " · ".join(company_names),
                ha="center", va="center", fontsize=13,
                color="#0077b6", transform=ax.transAxes)
        ax.text(0.5, 0.46,
                "Model: llama-3.3-70b-versatile via Groq\n"
                "Data: Yahoo Finance via yfinance\n"
                "Generated by sasyspanish",
                ha="center", va="center", fontsize=10,
                color="#888", transform=ax.transAxes)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Pagine testo
        chars_per_page = 3200
        lines          = report_text.split("\n")
        current        = []
        current_len    = 0
        pages          = []

        for line in lines:
            current.append(line)
            current_len += len(line)
            if current_len >= chars_per_page:
                pages.append("\n".join(current))
                current     = []
                current_len = 0
        if current:
            pages.append("\n".join(current))

        for page_text in pages:
            fig, ax = plt.subplots(figsize=(11, 8.5))
            ax.axis("off")
            ax.text(0.05, 0.95, page_text,
                    ha="left", va="top", fontsize=8.5,
                    family="monospace", transform=ax.transAxes,
                    wrap=True)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    print(f"[report_generator] ✅ PDF salvato: {pdf_path}")
    return pdf_path


# ---------------------------------------------------------------------------
# TOOL PER L'AGENTE
# ---------------------------------------------------------------------------

@tool
def generate_report_tool(analysis_output: str) -> str:
    """
    Genera il report finale dell'analisi finanziaria.

    Input: stringa JSON prodotta da run_analysis_tool, contenente
           'summary', 'group_stats', 'companies' e 'output_dir'.

    Produce nella cartella di output:
    - report.html  → report completo con testo LLM + grafici embedded
    - report.pdf   → versione PDF del report discorsivo

    Restituisce i path dei file generati.
    """
    try:
        data = json.loads(analysis_output)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Input JSON non valido: {e}"})

    if data.get("status") != "success":
        return json.dumps({"error": "Analisi non riuscita.", "detail": data})

    summary     = data.get("summary", {})
    group_stats = data.get("group_stats", {})
    companies   = data.get("companies", [])
    output_dir  = data.get("output_dir", "output_agent")

    if not summary:
        return json.dumps({"error": "Nessun dato numerico per il report."})

    report_text = generate_report_text(summary, group_stats, companies)
    html_path   = generate_html_report(report_text, output_dir,
                                        companies, summary)
    pdf_path    = generate_pdf_report(report_text, output_dir, companies)

    return json.dumps({
        "status":      "success",
        "report_text": report_text[:600] + "...",
        "files": {
            "html":      html_path,
            "pdf":       pdf_path,
            "dashboard": os.path.join(output_dir, "trend_dashboard.html"),
        },
    }, ensure_ascii=False)