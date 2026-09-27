"""
Token repository.

Encapsulates all database queries related to the Token model.
Services call these methods — they never build queries directly.
"""

from sqlalchemy.orm import Session

from app.models.token import Token
from app.repositories.base import BaseRepository
from app.schemas.token import TokenBase


class TokenRepository(BaseRepository[Token]):
    """Data access layer for Token records."""

    def __init__(self, db: Session):
        super().__init__(Token, db)

    def get_by_pair_address(self, pair_address: str) -> Token | None:
        """Find a token by its unique pair address."""
        return (
            self._db.query(Token)
            .filter(Token.pair_address == pair_address)
            .first()
        )

    def get_by_chain(self, chain: str, skip: int = 0, limit: int = 100) -> list[Token]:
        """Fetch tokens filtered by chain."""
        return (
            self._db.query(Token)
            .filter(Token.chain == chain)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def upsert(self, token_data: TokenBase) -> Token:
        """
        Insert or update a token based on pair_address.

        If a token with the same pair_address exists, update its mutable fields
        (price, market cap, FDV, liquidity, socials). The pair_address, token_address,
        and chain are immutable identity fields.

        If no token exists, create a new record.

        Args:
            token_data: TokenBase schema with the latest data from the scanner.

        Returns:
            The persisted Token ORM object (with id populated).
        """
        existing = self.get_by_pair_address(token_data.pair_address)

        if existing is not None:
            # Update mutable fields
            existing.name = token_data.name
            existing.symbol = token_data.symbol
            existing.price = token_data.price
            existing.market_cap = token_data.market_cap
            existing.fdv = token_data.fdv
            existing.liquidity = token_data.liquidity
            existing.pair_created_at = token_data.pair_created_at
            existing.website = token_data.website
            existing.twitter = token_data.twitter
            existing.telegram = token_data.telegram

            self._db.commit()
            self._db.refresh(existing)
            return existing
        else:
            # Create new token
            new_token = Token(
                pair_address=token_data.pair_address,
                token_address=token_data.token_address,
                name=token_data.name,
                symbol=token_data.symbol,
                chain=token_data.chain,
                price=token_data.price,
                market_cap=token_data.market_cap,
                fdv=token_data.fdv,
                liquidity=token_data.liquidity,
                pair_created_at=token_data.pair_created_at,
                website=token_data.website,
                twitter=token_data.twitter,
                telegram=token_data.telegram,
            )
            return self.create(new_token)
