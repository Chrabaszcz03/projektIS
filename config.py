from datetime import date

COINS = [
    ("bitcoin", "BTC"),
    ("ethereum", "ETH"),
]

DATE_FROM = date(2015, 8, 7)   # Ethereum genesis block
DATE_TO   = date(2022, 9, 23)  # last date in events.json

# Minimum number of articles per category per day to count as an "event day"
EVENT_THRESHOLD = 3

CATEGORY_MAP = {
    "BUSINESS":     "Gospodarka",
    "MONEY":        "Gospodarka",
    "ECONOMY":      "Gospodarka",
    "TECH":         "Technologia",
    "SCIENCE":      "Technologia",
    "POLITICS":     "Geopolityka",
    "WORLD NEWS":   "Geopolityka",
    "THE WORLDPOST":"Geopolityka",
    "WORLDPOST":    "Geopolityka",
    "ENTERTAINMENT":"Popkultura",
    "COMEDY":       "Popkultura",
    "ARTS":         "Popkultura",
    "MEDIA":        "Popkultura",
    "CULTURE & ARTS":"Popkultura",
    "CRIME":        "Regulacje/Prawo",
    "LAW & CRIME":  "Regulacje/Prawo",
}

ANALYSIS_CATEGORIES = [
    "Gospodarka",
    "Technologia",
    "Geopolityka",
    "Popkultura",
    "Regulacje/Prawo",
    "Inne",
]

CATEGORY_COLORS = {
    "Gospodarka":       "#2196F3",
    "Technologia":      "#4CAF50",
    "Geopolityka":      "#F44336",
    "Popkultura":       "#FF9800",
    "Regulacje/Prawo":  "#9C27B0",
    "Inne":             "#9E9E9E",
}
