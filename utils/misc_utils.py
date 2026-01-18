def get_currency_symbol(currency_code: str) -> str:
    """
    Returns the currency symbol for a given ISO 4217 currency code.
    Defaults to the code itself if no symbol is found.
    """
    symbols = {
        "NGN": "₦",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        # Add more currency symbols as needed
    }
    return symbols.get(currency_code.upper(), currency_code)
