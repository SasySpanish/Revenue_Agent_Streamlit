# config_llm.py  
# Gestione centralizzata del modello LLM e della API key Groq.
# Importato da tutti gli altri moduli al posto di istanziare
# ChatGroq direttamente.

import os
from langchain_groq import ChatGroq

PRIMARY_MODEL  = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"
REPORT_MODEL   = "llama-3.3-70b-versatile"


def _get_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY non trovata nelle variabili d'ambiente. "
            "Controlla il file .env nella root del progetto."
        )
    return key


def get_llm(temperature: float = 0) -> ChatGroq:
    return ChatGroq(
        model=PRIMARY_MODEL,
        api_key=_get_api_key(),
        temperature=temperature,
        max_tokens=4096,
    )


def get_report_llm() -> ChatGroq:
    return ChatGroq(
        model=REPORT_MODEL,
        api_key=_get_api_key(),
        temperature=0.4,
        max_tokens=8192,
    )


def get_fallback_llm() -> ChatGroq:
    return ChatGroq(
        model=FALLBACK_MODEL,
        api_key=_get_api_key(),
        temperature=0,
        max_tokens=4096,
    )


def test_connection() -> bool:
    try:
        llm      = get_llm()
        response = llm.invoke("Reply with exactly: GROQ_OK")
        return "GROQ_OK" in response.content
    except Exception as e:
        print(f"  Errore connessione Groq: {e}")
        return False
# ---------------------------------------------------------------------------
# VERIFICA RAPIDA SE LANCIATO DIRETTAMENTE
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Testing Groq connection...")
    if test_connection():
        print("✅ Groq API key valida — modello risponde correttamente")
        print(f"   Modello principale : {PRIMARY_MODEL}")
        print(f"   Modello report     : {REPORT_MODEL}")
        print(f"   Modello fallback   : {FALLBACK_MODEL}")
    else:
        print("❌ Connessione fallita — controlla la API key nel file .env")