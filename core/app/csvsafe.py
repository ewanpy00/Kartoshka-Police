FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def cell(value: object) -> str:
    """Text for one CSV cell, with a leading quote when a spreadsheet would read it as a formula."""
    text = str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text
