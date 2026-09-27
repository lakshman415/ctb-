"""
Chain identifier normalization.

Different providers name the same chain differently:

    canonical (ours + DexScreener)   GMGN
    solana                           sol
    ethereum                         eth
    bsc                              bsc
    base                             base
    robinhood                        robinhood

DexScreener rejects the short forms outright: `/tokens/v1/sol/{addr}` returns
zero pairs while `/tokens/v1/solana/{addr}` returns the pair. Leaking a GMGN
slug into stored data or a chart URL therefore produces "no pair found".

Everything inside the app uses the canonical form. Provider-specific slugs are
translated at the boundary, right where the provider is called.
"""

# GMGN (and other short-form) slugs -> canonical
_TO_CANONICAL = {
    "sol": "solana",
    "solana": "solana",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "bsc": "bsc",
    "bnb": "bsc",
    "binance": "bsc",
    "base": "base",
    "robinhood": "robinhood",
}

# canonical -> GMGN slug
_TO_GMGN = {
    "solana": "sol",
    "ethereum": "eth",
    "bsc": "bsc",
    "base": "base",
    "robinhood": "robinhood",
}


def to_canonical(chain: str | None) -> str:
    """
    Normalize any known chain alias to the canonical id used across the app.

    Unknown values pass through lowercased so a new chain still works without
    a code change — it just won't get an alias mapping.
    """
    if not chain:
        return ""
    key = chain.strip().lower()
    return _TO_CANONICAL.get(key, key)


def to_gmgn(chain: str | None) -> str:
    """Translate a canonical chain id into the slug GMGN expects."""
    canonical = to_canonical(chain)
    return _TO_GMGN.get(canonical, canonical)


def dexscreener_url(chain: str | None, address: str) -> str:
    """Build a DexScreener link using a canonical chain id."""
    return f"https://dexscreener.com/{to_canonical(chain)}/{address}"
