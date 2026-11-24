BrandMatch = tuple[str, str]


def tokens(brand: dict) -> set[str]:
    names = [brand["id"], *brand.get("names", [])]
    return {
        name.lower().replace(" ", "")
        for name in names
        if name.isascii()
    }


def is_official(domain: str, official_domains: list[str]) -> bool:
    return any(
        domain == official or domain.endswith("." + official)
        for official in official_domains
    )


def match_domains(domains: list[str], brands: list[dict]) -> list[BrandMatch]:
    matches = []
    for raw in domains:
        domain = raw.lower().removeprefix("*.")
        for brand in brands:
            if is_official(domain, brand.get("official_domains", [])):
                continue
            if any(token in domain for token in tokens(brand)):
                matches.append((brand["id"], domain))
    return matches
