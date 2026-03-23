# app.py  
# Interfaccia Streamlit per wheelhouse-agent-groq.
# Lancia con: streamlit run app.py

import sys
import os
import json
import time
import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Legge la API key sia da .env (locale) sia da st.secrets (Streamlit Cloud) (POST)
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    from dotenv import load_dotenv
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(BASE_DIR, ".env"))

# Calcola il path assoluto relativo alla posizione di app.py
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
WHEELHOUSE_PATH = os.path.join(BASE_DIR, "core")
GROQ_AGENT_PATH = os.path.join(BASE_DIR, "agent")

for p in [WHEELHOUSE_PATH, GROQ_AGENT_PATH]:
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(os.path.join(BASE_DIR, ".env"))
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")

# Import agente (lazy — solo quando serve)
from ticker_resolver  import ticker_resolver_tool, validate_custom_tickers_tool
from tool_analysis    import run_analysis_tool
from report_generator import generate_report_tool


# ---------------------------------------------------------------------------
# CONFIGURAZIONE PAGINA
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Revenue Agent — Financial Analysis · Made by sasyspanish",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# STILE CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
  .main-header {
    background: linear-gradient(135deg, #03045e, #0077b6);
    color: white; padding: 28px 32px; border-radius: 10px;
    margin-bottom: 24px;
  }
  .main-header h1 { font-size: 1.9rem; margin: 0; }
  .main-header p  { opacity: 0.8; margin: 6px 0 0; font-size: 0.95rem; }
  .metric-card {
    background: white; border-radius: 8px;
    padding: 16px; border-left: 4px solid #0077b6;
    box-shadow: 0 2px 6px rgba(0,0,0,0.07);
  }
  .history-item {
    background: white; border-radius: 8px;
    padding: 14px 16px; margin-bottom: 10px;
    border-left: 3px solid #0077b6;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    cursor: pointer;
  }
  .history-item:hover { border-left-color: #023e8a; }
  .status-ok   { color: #1a7a4a; font-weight: 600; }
  .status-warn { color: #c0392b; font-weight: 600; }
  .badge {
    display: inline-block; background: #e8f4fd; color: #0077b6;
    padding: 2px 10px; border-radius: 20px;
    font-size: 0.8rem; font-weight: 600; margin: 2px;
  }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []   # lista di analisi completate

if "current_result" not in st.session_state:
    st.session_state.current_result = None

if "running" not in st.session_state:
    st.session_state.running = False


# ---------------------------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------------------------

def run_pipeline(user_input: str, progress_bar, status_text) -> dict | None:
    """
    Esegue il pipeline deterministico con aggiornamenti UI in tempo reale.
    Ritorna il dizionario con i path dei file generati, o None in caso di errore.
    """

    # Step 1 — Ticker resolver
    status_text.markdown("🔍 **Step 1/3** — Resolving tickers...")
    progress_bar.progress(10)

    resolver_result = ticker_resolver_tool.invoke({"query": user_input})
    data = json.loads(resolver_result)

    if not data.get("tickers"):
        resolver_result = validate_custom_tickers_tool.invoke(
            {"ticker_list": user_input}
        )
        data = json.loads(resolver_result)

    tickers = data.get("tickers") or data.get("valid", [])
    names   = data.get("names", {})

    if not tickers:
        st.error(
            f"❌ No tickers found for **'{user_input}'**. "
            "Try explicit symbols like `BMW.DE, AAPL, UCG.MI` "
            "or sector keywords like `european banks`, `big tech us`."
        )
        return None

    status_text.markdown(
        f"✅ **Step 1/3** — Tickers resolved: "
        + " ".join([f"`{t}`" for t in tickers])
    )
    progress_bar.progress(25)

    # Step 2 — Analisi finanziaria
    status_text.markdown(
        f"📊 **Step 2/3** — Running financial analysis "
        f"for {len(tickers)} companies..."
    )
    progress_bar.progress(35)

    analysis_result = run_analysis_tool.invoke(
        {"resolver_output": resolver_result}
    )
    analysis_data = json.loads(analysis_result)

    if analysis_data.get("status") != "success":
        st.error(f"❌ Analysis failed: {analysis_data.get('error')}")
        return None

    progress_bar.progress(70)
    output_dir = analysis_data.get("output_dir")
    status_text.markdown(
        f"✅ **Step 2/3** — Analysis complete. "
        f"Output: `{output_dir}`"
    )

    # Step 3 — Report
    status_text.markdown(
        "✍️ **Step 3/3** — Generating report with "
        "llama-3.3-70b... (this may take 20-40 seconds)"
    )
    progress_bar.progress(75)

    report_result = generate_report_tool.invoke(
        {"analysis_output": analysis_result}
    )
    report_data = json.loads(report_result)

    if report_data.get("status") != "success":
        st.error(f"❌ Report generation failed: {report_data.get('error')}")
        return None

    progress_bar.progress(100)
    status_text.markdown("✅ **Done!** Report generated successfully.")

    files = report_data.get("files", {})

    return {
        "prompt":     user_input,
        "tickers":    tickers,
        "names":      names,
        "output_dir": output_dir,
        "files":      files,
        "timestamp":  datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary":    analysis_data.get("summary", {}),
        "report_text": report_data.get("report_text", ""),
    }


# ---------------------------------------------------------------------------
# SIDEBAR — storico analisi
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 📂 Analysis History")

    if not st.session_state.history:
        st.caption("No analyses yet. Run your first prompt!")
    else:
        for i, item in enumerate(reversed(st.session_state.history)):
            idx = len(st.session_state.history) - 1 - i
            label = ", ".join(item["tickers"][:3])
            if len(item["tickers"]) > 3:
                label += f" +{len(item['tickers'])-3}"
            if st.button(
                f"🕐 {item['timestamp']}\n{label}",
                key=f"history_{idx}",
                use_container_width=True,
            ):
                st.session_state.current_result = item

    st.divider()
    st.markdown("### ⚙️ Settings")
    st.caption(f"**Model:** llama-3.3-70b-versatile")
    st.caption(f"**Provider:** Groq")
    st.caption(f"**Data:** Yahoo Finance via yfinance")
    st.caption(f"**Creator:** sasyspanish")
    st.divider()
    st.markdown("### 💡 Example prompts")
    examples = [
        # Automotive
        "Automotive europeo",
        "BMW.DE, MBG.DE, STLAM.MI",
        # Banche
        "European banks",
        "Banche europee",
        # Tech
        "Big tech us",
        "Apple, Microsoft, Nvidia",
        # Semiconduttori
        "Semiconductors",
        "ASML.AS, NVDA, TSM",
        # Pharma
        "Pharma",
        "Healthcare",
        # Telecom
        "Telecomunicazioni",
        "Telecom",
        # Aerospace
        "Aerospace defense",
        "Difesa",
        # Food & Beverage
        "Food beverage",
        "NESN.SW, DGE.L, KO",
        # Lusso
        "Lusso",
        "Luxury fashion",
        "MC.PA, RMS.PA, RACE.MI",
        # Fintech
        "Fintech",
        "Asset management",
        # Italia
        "FTSE MIB",
        "Italia",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state["prefill"] = ex


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
  <h1>📊 Revenue Agent — Financial Analysis </h1>
  <p>Powered by llama-3.3-70b via Groq · Data from Yahoo Finance · Made by sasyspanish</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# INPUT
# ---------------------------------------------------------------------------

prefill = st.session_state.pop("prefill", "")

col1, col2 = st.columns([5, 1])
with col1:
    user_input = st.text_input(
        "Describe the companies or sector to analyse:",
        value=prefill,
        placeholder="e.g. European banks · Apple, Microsoft · BMW.DE, MBG.DE",
        label_visibility="collapsed",
    )
with col2:
    run_btn = st.button(
        "▶ Run", type="primary",
        use_container_width=True,
        disabled=st.session_state.running,
    )

st.caption(
    "**Sector keywords:** `automotive europeo` · `banche europee` · `big tech us`  "
    "| **Direct tickers:** `BMW.DE, AAPL, UCG.MI`"
)


# ---------------------------------------------------------------------------
# ESECUZIONE PIPELINE
# ---------------------------------------------------------------------------

if run_btn and user_input.strip():
    st.session_state.running = True
    st.divider()

    progress_bar = st.progress(0)
    status_text  = st.empty()

    with st.spinner(""):
        result = run_pipeline(
            user_input.strip(), progress_bar, status_text
        )

    st.session_state.running = False

    if result:
        st.session_state.history.append(result)
        st.session_state.current_result = result
        st.rerun()


# ---------------------------------------------------------------------------
# RISULTATI
# ---------------------------------------------------------------------------

result = st.session_state.current_result

if result:
    st.divider()

    # Header risultato
    st.markdown(f"### 📋 Analysis: {', '.join(result['tickers'])}")
    st.caption(f"🕐 {result['timestamp']} · Output: `{result['output_dir']}`")

    # Metriche rapide
    summary = result.get("summary", {})
    if summary:
        companies = list(summary.keys())
        n = min(len(companies), 4)
        cols = st.columns(n)
        for i, company in enumerate(companies[:n]):
            with cols[i]:
                ebit = summary[company].get("EBIT Margin (%)")
                roe  = summary[company].get("ROE (%)")
                st.metric(
                    label=company,
                    value=f"EBIT {ebit:.1f}%" if ebit else "N/A",
                    delta=f"ROE {roe:.1f}%" if roe else None,
                )

    st.divider()

    # Tab per i contenuti
    tab1, tab2, tab3 = st.tabs([
        "📄 Report Preview",
        "📈 Interactive Dashboard",
        "⬇️ Downloads",
    ])

    # --- Tab 1: Report HTML inline ---
    with tab1:
        html_path = result["files"].get("html")
        if html_path and os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=900, scrolling=True)
        else:
            st.warning("Report HTML not found.")

    # --- Tab 2: Dashboard Plotly ---
    with tab2:
        dashboard_path = result["files"].get("dashboard")
        if dashboard_path and os.path.exists(dashboard_path):
            with open(dashboard_path, "r", encoding="utf-8") as f:
                dash_content = f.read()
            st.components.v1.html(dash_content, height=800, scrolling=True)
        else:
            st.warning("Dashboard not found.")

    # --- Tab 3: Download ---
    with tab3:
        st.markdown("#### Download files")

        col1, col2 = st.columns(2)

        with col1:
            html_path = result["files"].get("html")
            if html_path and os.path.exists(html_path):
                with open(html_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Report (HTML)",
                        data=f,
                        file_name=f"report_{'_'.join(result['tickers'][:3])}.html",
                        mime="text/html",
                        use_container_width=True,
                    )

        with col2:
            pdf_path = result["files"].get("pdf")
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Report (PDF)",
                        data=f,
                        file_name=f"report_{'_'.join(result['tickers'][:3])}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

        st.divider()
        st.markdown("#### Output folder")
        st.code(result["output_dir"])
        st.caption(
            "The output folder contains all PNG charts, the Excel file, "
            "the PDF summary and the interactive HTML dashboard."
        )
