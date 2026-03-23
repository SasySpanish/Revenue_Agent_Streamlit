# ticker_resolver.py
# Tool che converte una descrizione testuale in ticker validi su yfinance.
# Strategia ibrida: la LLM suggerisce i ticker, yfinance li valida.

import yfinance as yf
from langchain_core.tools import tool

# wheelhouse
# ---------------------------------------------------------------------------
# KNOWLEDGE BASE — ticker noti per settore
# Usata come fallback/suggerimento per la LLM
# ---------------------------------------------------------------------------

KNOWN_TICKERS = {
    # Automotive europeo
    "volkswagen": "VOW3.DE", "vw": "VOW3.DE",
    "stellantis": "STLAM.MI", "fiat": "STLAM.MI",
    "mercedes": "MBG.DE", "mercedes-benz": "MBG.DE",
    "bmw": "BMW.DE",
    "renault": "RNO.PA",
    "porsche": "P911.DE",
    "volvo cars": "VOLCAR-B.ST",
    "traton": "TKA.DE",
    "iveco": "IVG.MI",
    "ferrari": "RACE.MI",
    # Banche europee
    "unicredit": "UCG.MI",
    "intesa": "ISP.MI", "intesa sanpaolo": "ISP.MI",
    "bnp": "BNP.PA", "bnp paribas": "BNP.PA",
    "santander": "SAN.MC",
    "deutsche bank": "DBK.DE",
    "hsbc": "HSBA.L",
    "barclays": "BARC.L",
    "societe generale": "GLE.PA",
    "ing": "INGA.AS",
    # Tech US
    "apple": "AAPL", "microsoft": "MSFT",
    "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "meta": "META",
    "nvidia": "NVDA", "tesla": "TSLA",
    # Energia
    "eni": "ENI.MI", "shell": "SHEL.L",
    "bp": "BP.L", "totalenergies": "TTE.PA",
    "exxon": "XOM", "chevron": "CVX",
    
    # Semiconduttori
    "intel": "INTC", "amd": "AMD",
    "tsmc": "TSM", "qualcomm": "QCOM", "broadcom": "AVGO",
    "asml": "ASML.AS", "stmicroelectronics": "STM.MI", "st": "STM.MI",
    "infineon": "IFX.DE", "applied materials": "AMAT",
    "kla": "KLAC", "lam research": "LRCX",

    # Farmaceutico / Healthcare
    "johnson & johnson": "JNJ",
    "pfizer": "PFE", "roche": "ROG.SW", "novartis": "NOVN.SW",
    "astrazeneca": "AZN.L", "sanofi": "SAN.PA",
    "merck": "MRK", "abbvie": "ABBV", "eli lilly": "LLY",
    "novo nordisk": "NOVO-B.CO", "biontech": "BNTX",

    # Telecomunicazioni
    "at&t": "T", "verizon": "VZ", "t-mobile": "TMUS",
    "deutsche telekom": "DTE.DE", "vodafone": "VOD.L",
    "telecom italia": "TIT.MI", "tim": "TIT.MI",
    "orange": "ORA.PA", "telefonica": "TEF.MC",
    "swisscom": "SCMN.SW", "proximus": "PROX.BR",

    # Aerospace & Defense
    "boeing": "BA", "airbus": "AIR.PA", "lockheed": "LMT",
    "lockheed martin": "LMT", "raytheon": "RTX",
    "northrop": "NOC", "northrop grumman": "NOC",
    "general dynamics": "GD", "bae systems": "BA.L",
    "leonardo": "LDO.MI", "safran": "SAF.PA",
    "rolls royce": "RR.L", "thales": "HO.PA",

    # Food & Beverage
    "nestle": "NESN.SW", "unilever": "UNA.AS",
    "danone": "BN.PA", "ab inbev": "ABI.BR",
    "diageo": "DGE.L", "pepsi": "PEP",
    "coca-cola": "KO",
    "mondelez": "MDLZ", "kraft heinz": "KHC",
    "campari": "CPR.MI",
    

    # Lusso & Fashion
    "lvmh": "MC.PA", "hermes": "RMS.PA",
    "kering": "KER.PA", "richemont": "CFR.SW",
    "burberry": "BRBY.L", "moncler": "MONC.MI",
    "brunello cucinelli": "BC.MI",
    "tod's": "TOD.MI",
    "hugo boss": "BOSS.DE", "salvatore ferragamo": "SFER.MI",

    # Asset Management / Fintech
    "blackrock": "BLK", "blackstone": "BX",
    "goldman sachs": "GS", "morgan stanley": "MS",
    "jpmorgan": "JPM", "jp morgan": "JPM",
    "visa": "V", "mastercard": "MA",
    "paypal": "PYPL", "square": "SQ", "block": "SQ",
    "fineco": "FBK.MI", "finecobank": "FBK.MI",
    "azimut": "AZM.MI",

    # Italia FTSE MIB aggiuntivi
    "enel": "ENEL.MI", "eni": "ENI.MI",
    "mediobanca": "MB.MI",
    "generali": "G.MI",
    "prysmian": "PRY.MI", "amplifon": "AMP.MI",
    "recordati": "REC.MI", "diasorin": "DIA.MI",
    "reply": "REY.MI", "cerved": "CERV.MI",
    
    
}

# Settori predefiniti pronti all'uso
SECTOR_PRESETS = {
    "automotive europeo": {
        "VOW3.DE":     {"name": "Volkswagen Group",  "country": "DE", "segment": "mass-market"},
        "STLAM.MI":    {"name": "Stellantis",         "country": "IT", "segment": "mass-market"},
        "MBG.DE":      {"name": "Mercedes-Benz",      "country": "DE", "segment": "premium"},
        "BMW.DE":      {"name": "BMW Group",           "country": "DE", "segment": "premium"},
        "RNO.PA":      {"name": "Renault Group",       "country": "FR", "segment": "mass-market"},
        "P911.DE":     {"name": "Porsche AG",          "country": "DE", "segment": "premium"},
        "VOLCAR-B.ST": {"name": "Volvo Cars",          "country": "SE", "segment": "premium"},
        "TKA.DE":      {"name": "TRATON Group",        "country": "DE", "segment": "commercial"},
        "IVG.MI":      {"name": "Iveco Group",         "country": "IT", "segment": "commercial"},
    },
    "banche europee": {
        "UCG.MI":  {"name": "UniCredit",        "country": "IT", "segment": "banking"},
        "ISP.MI":  {"name": "Intesa Sanpaolo",  "country": "IT", "segment": "banking"},
        "BNP.PA":  {"name": "BNP Paribas",      "country": "FR", "segment": "banking"},
        "SAN.MC":  {"name": "Santander",         "country": "ES", "segment": "banking"},
        "DBK.DE":  {"name": "Deutsche Bank",    "country": "DE", "segment": "banking"},
        "HSBA.L":  {"name": "HSBC",             "country": "GB", "segment": "banking"},
        "BARC.L":  {"name": "Barclays",         "country": "GB", "segment": "banking"},
        "GLE.PA":  {"name": "Societe Generale", "country": "FR", "segment": "banking"},
        "INGA.AS": {"name": "ING Group",        "country": "NL", "segment": "banking"},
    },
    "big tech us": {
        "AAPL":  {"name": "Apple",     "country": "US", "segment": "tech"},
        "MSFT":  {"name": "Microsoft", "country": "US", "segment": "tech"},
        "GOOGL": {"name": "Alphabet",  "country": "US", "segment": "tech"},
        "AMZN":  {"name": "Amazon",   "country": "US", "segment": "tech"},
        "META":  {"name": "Meta",     "country": "US", "segment": "tech"},
        "NVDA":  {"name": "Nvidia",   "country": "US", "segment": "tech"},
    },
    
    "semiconduttori": {
        "NVDA":    {"name": "Nvidia",             "country": "US", "segment": "semiconductors"},
        "TSM":     {"name": "TSMC",               "country": "TW", "segment": "semiconductors"},
        "ASML.AS": {"name": "ASML",               "country": "NL", "segment": "semiconductors"},
        "INTC":    {"name": "Intel",              "country": "US", "segment": "semiconductors"},
        "AMD":     {"name": "AMD",                "country": "US", "segment": "semiconductors"},
        "AVGO":    {"name": "Broadcom",           "country": "US", "segment": "semiconductors"},
        "QCOM":    {"name": "Qualcomm",           "country": "US", "segment": "semiconductors"},
        "STM.MI":  {"name": "STMicroelectronics", "country": "IT", "segment": "semiconductors"},
        "IFX.DE":  {"name": "Infineon",           "country": "DE", "segment": "semiconductors"},
        "AMAT":    {"name": "Applied Materials",  "country": "US", "segment": "semiconductors"},
        "KLAC":    {"name": "KLA Corporation",    "country": "US", "segment": "semiconductors"},
        "LRCX":    {"name": "Lam Research",       "country": "US", "segment": "semiconductors"},
    },
    "pharma": {
        "LLY":       {"name": "Eli Lilly",      "country": "US", "segment": "pharma"},
        "NOVO-B.CO": {"name": "Novo Nordisk",   "country": "DK", "segment": "pharma"},
        "ABBV":      {"name": "AbbVie",         "country": "US", "segment": "pharma"},
        "JNJ":       {"name": "J&J",            "country": "US", "segment": "pharma"},
        "ROG.SW":    {"name": "Roche",          "country": "CH", "segment": "pharma"},
        "NOVN.SW":   {"name": "Novartis",       "country": "CH", "segment": "pharma"},
        "AZN.L":     {"name": "AstraZeneca",    "country": "GB", "segment": "pharma"},
        "SAN.PA":    {"name": "Sanofi",         "country": "FR", "segment": "pharma"},
        "PFE":       {"name": "Pfizer",         "country": "US", "segment": "pharma"},
        "MRK":       {"name": "Merck",          "country": "US", "segment": "pharma"},
        "BNTX":      {"name": "BioNTech",       "country": "DE", "segment": "pharma"},
    },
    "telecomunicazioni": {
        "T":       {"name": "AT&T",              "country": "US", "segment": "telco"},
        "VZ":      {"name": "Verizon",           "country": "US", "segment": "telco"},
        "TMUS":    {"name": "T-Mobile",          "country": "US", "segment": "telco"},
        "DTE.DE":  {"name": "Deutsche Telekom",  "country": "DE", "segment": "telco"},
        "VOD.L":   {"name": "Vodafone",          "country": "GB", "segment": "telco"},
        "ORA.PA":  {"name": "Orange",            "country": "FR", "segment": "telco"},
        "TEF.MC":  {"name": "Telefonica",        "country": "ES", "segment": "telco"},
        "TIT.MI":  {"name": "Telecom Italia",    "country": "IT", "segment": "telco"},
        "SCMN.SW": {"name": "Swisscom",          "country": "CH", "segment": "telco"},
    },
    "aerospace defense": {
        "BA":    {"name": "Boeing",           "country": "US", "segment": "aerospace"},
        "AIR.PA":{"name": "Airbus",           "country": "FR", "segment": "aerospace"},
        "LMT":   {"name": "Lockheed Martin",  "country": "US", "segment": "aerospace"},
        "RTX":   {"name": "Raytheon",         "country": "US", "segment": "aerospace"},
        "NOC":   {"name": "Northrop Grumman", "country": "US", "segment": "aerospace"},
        "GD":    {"name": "General Dynamics", "country": "US", "segment": "aerospace"},
        "BA.L":  {"name": "BAE Systems",      "country": "GB", "segment": "aerospace"},
        "LDO.MI":{"name": "Leonardo",         "country": "IT", "segment": "aerospace"},
        "SAF.PA":{"name": "Safran",           "country": "FR", "segment": "aerospace"},
        "HO.PA": {"name": "Thales",           "country": "FR", "segment": "aerospace"},
        "RR.L":  {"name": "Rolls-Royce",      "country": "GB", "segment": "aerospace"},
    },
    "food beverage": {
        "NESN.SW": {"name": "Nestlé",       "country": "CH", "segment": "food"},
        "UNA.AS":  {"name": "Unilever",     "country": "NL", "segment": "food"},
        "BN.PA":   {"name": "Danone",       "country": "FR", "segment": "food"},
        "ABI.BR":  {"name": "AB InBev",     "country": "BE", "segment": "food"},
        "DGE.L":   {"name": "Diageo",       "country": "GB", "segment": "food"},
        "PEP":     {"name": "PepsiCo",      "country": "US", "segment": "food"},
        "KO":      {"name": "Coca-Cola",    "country": "US", "segment": "food"},
        "MDLZ":    {"name": "Mondelez",     "country": "US", "segment": "food"},
        "KHC":     {"name": "Kraft Heinz",  "country": "US", "segment": "food"},
        "CPR.MI":  {"name": "Campari",      "country": "IT", "segment": "food"},
    },
    "lusso": {
        "MC.PA":   {"name": "LVMH",               "country": "FR", "segment": "luxury"},
        "RMS.PA":  {"name": "Hermès",             "country": "FR", "segment": "luxury"},
        "KER.PA":  {"name": "Kering",             "country": "FR", "segment": "luxury"},
        "CFR.SW":  {"name": "Richemont",          "country": "CH", "segment": "luxury"},
        "RACE.MI": {"name": "Ferrari",            "country": "IT", "segment": "luxury"},
        "MONC.MI": {"name": "Moncler",            "country": "IT", "segment": "luxury"},
        "BC.MI":   {"name": "Brunello Cucinelli", "country": "IT", "segment": "luxury"},
        "BRBY.L":  {"name": "Burberry",           "country": "GB", "segment": "luxury"},
        "BOSS.DE": {"name": "Hugo Boss",          "country": "DE", "segment": "luxury"},
        "TOD.MI":  {"name": "Tod's",              "country": "IT", "segment": "luxury"},
        "SFER.MI": {"name": "Salvatore Ferragamo","country": "IT", "segment": "luxury"},
    },
    "asset management": {
        "BLK":  {"name": "BlackRock",     "country": "US", "segment": "asset_mgmt"},
        "BX":   {"name": "Blackstone",   "country": "US", "segment": "asset_mgmt"},
        "GS":   {"name": "Goldman Sachs","country": "US", "segment": "asset_mgmt"},
        "MS":   {"name": "Morgan Stanley","country": "US", "segment": "asset_mgmt"},
        "V":    {"name": "Visa",         "country": "US", "segment": "fintech"},
        "MA":   {"name": "Mastercard",   "country": "US", "segment": "fintech"},
        "PYPL": {"name": "PayPal",       "country": "US", "segment": "fintech"},
        "SQ":   {"name": "Block",        "country": "US", "segment": "fintech"},
        "FBK.MI":{"name": "FinecoBank",  "country": "IT", "segment": "fintech"},
        "AZM.MI":{"name": "Azimut",      "country": "IT", "segment": "asset_mgmt"},
    },
    "ftse mib": {
        "ENEL.MI": {"name": "Enel",              "country": "IT", "segment": "utilities"},
        "ENI.MI":  {"name": "Eni",               "country": "IT", "segment": "energy"},
        "UCG.MI":  {"name": "UniCredit",         "country": "IT", "segment": "banking"},
        "ISP.MI":  {"name": "Intesa Sanpaolo",   "country": "IT", "segment": "banking"},
        "RACE.MI": {"name": "Ferrari",           "country": "IT", "segment": "luxury"},
        "G.MI":    {"name": "Generali",          "country": "IT", "segment": "insurance"},
        "MONC.MI": {"name": "Moncler",           "country": "IT", "segment": "luxury"},
        "MB.MI":   {"name": "Mediobanca",        "country": "IT", "segment": "banking"},
        "PRY.MI":  {"name": "Prysmian",          "country": "IT", "segment": "industrial"},
        "CPR.MI":  {"name": "Campari",           "country": "IT", "segment": "food"},
        "AMP.MI":  {"name": "Amplifon",          "country": "IT", "segment": "healthcare"},
        "REC.MI":  {"name": "Recordati",         "country": "IT", "segment": "pharma"},
    },
}


# ---------------------------------------------------------------------------
# ALIAS DI SETTORE
# Mappa varianti linguistiche (EN/IT) ai preset canonici
# ---------------------------------------------------------------------------

SECTOR_ALIASES = {
    "semiconductor":    "semiconduttori",
    "semiconductors":   "semiconduttori",
    "chips":            "semiconduttori",
    "chip":             "semiconduttori",
    "semis":            "semiconduttori",
    "pharma":           "pharma",
    "farmaceutico":     "pharma",
    "healthcare":       "pharma",
    "salute":           "pharma",
    "telco":            "telecomunicazioni",
    "telecom":          "telecomunicazioni",
    "telecommunications": "telecomunicazioni",
    "defense":          "aerospace defense",
    "difesa":           "aerospace defense",
    "aerospace":        "aerospace defense",
    "food":             "food beverage",
    "cibo":             "food beverage",
    "beverage":         "food beverage",
    "luxury":           "lusso",
    "moda":             "lusso",
    "fashion":          "lusso",
    "fintech":          "asset management",
    "asset management": "asset management",
    "gestione":         "asset management",
    "italia":           "ftse mib",
    "italian":          "ftse mib",
    "italy":            "ftse mib",
    "mib":              "ftse mib",
}


# ---------------------------------------------------------------------------
# VALIDAZIONE TICKER
# ---------------------------------------------------------------------------

def validate_ticker(symbol: str) -> dict | None:
    """
    Verifica che un ticker esista su yfinance e ritorna i suoi metadati.
    Ritorna None se il ticker non è valido.
    """
    try:
        info = yf.Ticker(symbol).info
        # yfinance ritorna un dict quasi vuoto per ticker inesistenti
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None and info.get("navPrice") is None:
            # Prova a controllare almeno il nome
            if not info.get("shortName") and not info.get("longName"):
                return None
        return {
            "name":    info.get("longName") or info.get("shortName", symbol),
            "country": info.get("country", "??"),
            "segment": info.get("industry", "unknown"),
        }
    except Exception:
        return None


def resolve_tickers(raw_list: list[str]) -> dict:
    """
    Data una lista di simboli grezzi (es. ["BMW.DE", "AAPL", "pippo"]),
    valida ciascuno su yfinance e ritorna solo quelli validi nel formato
    atteso da runner.run_full_analysis().
    """
    resolved = {}
    for symbol in raw_list:
        symbol = symbol.strip().upper()
        print(f"  Validando {symbol}...")
        meta = validate_ticker(symbol)
        if meta:
            resolved[symbol] = meta
            print(f"    ✅ {meta['name']}")
        else:
            print(f"    ❌ Ticker non valido: {symbol}")
    return resolved


def resolve_from_text(text: str) -> dict:
    """
    Prova a risolvere ticker da testo libero usando la knowledge base.
    Controlla prima gli alias, poi i preset diretti, poi i nomi singoli.
    """
    text_lower = text.lower()

    # 1. Controlla alias (EN/IT) → preset canonico
    for alias, canonical in SECTOR_ALIASES.items():
        if alias in text_lower and canonical in SECTOR_PRESETS:
            print(f"  Preset trovato via alias '{alias}': '{canonical}'")
            return SECTOR_PRESETS[canonical]

    # 2. Controlla preset diretti (chiave esatta)
    for sector_key, preset in SECTOR_PRESETS.items():
        if sector_key in text_lower:
            print(f"  Preset trovato: '{sector_key}'")
            return preset

    # 3. Fallback — cerca nomi singoli nella knowledge base
    found = {}
    for name, symbol in KNOWN_TICKERS.items():
        if name in text_lower and symbol not in found:
            meta = validate_ticker(symbol)
            if meta:
                found[symbol] = meta

    return found 


# ---------------------------------------------------------------------------
# TOOL PER L'AGENTE
# ---------------------------------------------------------------------------

@tool
def ticker_resolver_tool(query: str) -> str:
    """
    Risolve una query testuale in una lista di ticker finanziari validi.

    Usa questo tool quando l'utente descrive aziende o settori in linguaggio
    naturale (es. 'i principali OEM europei', 'le banche italiane',
    'Apple e Microsoft').

    Restituisce una stringa JSON con i ticker validi trovati.
    """
    import json

    print(f"\n[ticker_resolver] Query: '{query}'")

    # 1. Prova match diretto con preset di settore
    result = resolve_from_text(query)
    if result:
        print(f"  Risolti {len(result)} ticker dalla knowledge base")
        # Ritorna solo i simboli come lista — il tool run_analysis
        # costruirà il dizionario completo chiamando validate_ticker
        return json.dumps({
            "tickers": list(result.keys()),
            "names":   {k: v["name"] for k, v in result.items()},
            "source":  "knowledge_base",
        })

    # 2. Se non trova nulla, ritorna istruzioni per la LLM
    return json.dumps({
        "tickers": [],
        "names":   {},
        "source":  "not_found",
        "message": (
            f"Nessun ticker trovato per '{query}'. "
            "Fornisci i simboli di borsa direttamente "
            "(es. 'BMW.DE', 'AAPL', 'UCG.MI')."
        ),
    })


@tool
def validate_custom_tickers_tool(ticker_list: str) -> str:
    """
    Valida una lista di ticker forniti direttamente dall'utente.

    Usa questo tool quando l'utente fornisce simboli di borsa espliciti
    (es. 'BMW.DE, AAPL, UCG.MI').

    Input: stringa con ticker separati da virgola.
    Restituisce: JSON con ticker validi e non validi.
    """
    import json

    raw = [t.strip() for t in ticker_list.split(",") if t.strip()]
    print(f"\n[validate_tickers] Validando: {raw}")

    resolved = resolve_tickers(raw)
    invalid  = [t.upper() for t in raw if t.upper() not in resolved]

    return json.dumps({
        "valid":   list(resolved.keys()),
        "names":   {k: v["name"] for k, v in resolved.items()},
        "invalid": invalid,
    })
