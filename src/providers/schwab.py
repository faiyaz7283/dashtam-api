"""Charles Schwab provider implementation for Dashtam.

This module implements the Schwab brokerage provider, handling OAuth authentication,
account fetching, and transaction retrieval with proper typing for brokerage operations.

The provider uses Schwab's Trader API to fetch investment accounts, positions, and
trading history, converting them to Dashtam's standardized brokerage transaction format.
"""

import os
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from src.providers.base import (
    BaseProvider,
    ProviderType,
    BrokerageTransactionType,
    TransactionType,
)
from src.providers.registry import register_provider

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@register_provider(
    key="schwab",
    name="Charles Schwab",
    provider_type=ProviderType.BROKERAGE,
    description="Full-service brokerage offering investment accounts, retirement planning, and trading services",
    icon_url="/static/icons/schwab.png",
    supported_features=[
        "oauth2",
        "accounts",
        "transactions",
        "positions",
        "trading",
        "market_data",
    ],
)
class SchwabProvider(BaseProvider):
    """Charles Schwab brokerage provider implementation.

    Handles OAuth2 authentication with Schwab's Trader API and provides
    access to investment accounts, positions, and trading transactions.

    Features:
    - OAuth2 authentication with PKCE support
    - Investment account data retrieval
    - Stock/ETF/Option transaction history
    - Dividend and capital gain tracking
    - Real-time position and balance updates
    """

    def __init__(self):
        """Initialize Schwab provider with configuration."""
        super().__init__()
        self.provider_type = ProviderType.BROKERAGE
        self.provider_name = "schwab"

        # Load Schwab API configuration
        self.api_key = os.getenv("SCHWAB_API_KEY")
        self.api_secret = os.getenv("SCHWAB_API_SECRET")
        self.redirect_uri = os.getenv(
            "SCHWAB_REDIRECT_URI", "https://127.0.0.1:8182/callback"
        )
        self.base_url = os.getenv("SCHWAB_API_BASE_URL", "https://api.schwabapi.com")

        # Check if provider is properly configured
        self.is_configured = bool(self.api_key and self.api_secret)

        if not self.is_configured:
            logger.warning(
                "Schwab provider not fully configured. Missing API credentials."
            )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate Basic Auth headers for OAuth requests.

        Returns:
            Dictionary with Authorization header for Basic Auth.
        """
        credentials = f"{self.api_key}:{self.api_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _get_api_headers(self, access_token: str) -> Dict[str, str]:
        """Generate headers for authenticated API requests.

        Args:
            access_token: OAuth access token.

        Returns:
            Dictionary with Authorization header for Bearer token.
        """
        return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    async def authenticate(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens.

        Args:
            auth_data: Must contain {"code": "authorization_code"}.

        Returns:
            Dictionary with access_token, refresh_token, expires_in, and token_type.

        Raises:
            Exception: If authentication fails or API returns error.
        """
        if "code" not in auth_data:
            raise ValueError("Authorization code required for Schwab authentication")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/oauth/token",
                headers=self._get_auth_headers(),
                data={
                    "grant_type": "authorization_code",
                    "code": auth_data["code"],
                    "redirect_uri": self.redirect_uri,
                },
            )

            if response.status_code != 200:
                raise Exception(f"Schwab authentication failed: {response.text}")

            tokens = response.json()
            logger.info("Successfully authenticated with Schwab")

            return {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "expires_in": tokens.get("expires_in", 1800),
                "token_type": tokens.get("token_type", "Bearer"),
                "scope": tokens.get("scope"),
            }

    async def refresh_authentication(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token from Schwab.

        Returns:
            Dictionary with new access_token and updated tokens.

        Raises:
            Exception: If refresh fails or token is invalid.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/oauth/token",
                headers=self._get_auth_headers(),
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )

            if response.status_code != 200:
                raise Exception(f"Token refresh failed: {response.text}")

            tokens = response.json()
            logger.info("Successfully refreshed Schwab tokens")

            return {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token", refresh_token),
                "expires_in": tokens.get("expires_in", 1800),
                "token_type": tokens.get("token_type", "Bearer"),
            }

    async def get_accounts(
        self, provider_id: UUID, user_id: UUID, session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Fetch all investment accounts for the user.

        Args:
            provider_id: The provider instance ID.
            user_id: Dashtam user ID to fetch accounts for.
            session: Database session for operations.

        Returns:
            List of account dictionaries with standardized fields.

        Raises:
            Exception: If API call fails or user has no valid tokens.
        """
        # Get user's access token from database
        access_token = await self._get_user_access_token(provider_id, user_id, session)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/trader/v1/accounts",
                headers=self._get_api_headers(access_token),
                params={"fields": "positions"},
            )

            if response.status_code != 200:
                raise Exception(f"Failed to fetch accounts: {response.text}")

            schwab_accounts = response.json()

            # Convert to standardized format
            accounts = []
            for schwab_account in schwab_accounts:
                account_data = schwab_account.get("securitiesAccount", {})

                # Calculate total value including positions
                total_value = Decimal(
                    str(
                        account_data.get("currentBalances", {}).get(
                            "liquidationValue", 0
                        )
                    )
                )

                accounts.append(
                    {
                        "id": account_data.get("accountNumber"),
                        "name": account_data.get("accountNickname")
                        or f"Schwab {account_data.get('type', 'Account')}",
                        "account_type": self._map_account_type(
                            account_data.get("type")
                        ),
                        "balance": float(total_value),
                        "currency": "USD",
                        "cash_balance": account_data.get("currentBalances", {}).get(
                            "cashBalance"
                        ),
                        "buying_power": account_data.get("currentBalances", {}).get(
                            "buyingPower"
                        ),
                        "positions_count": len(account_data.get("positions", [])),
                        "metadata": {
                            "is_margin": account_data.get("type") == "MARGIN",
                            "is_cash": account_data.get("type") == "CASH",
                            "day_trader": account_data.get("isDayTrader", False),
                            "round_trips": account_data.get("roundTrips", 0),
                        },
                    }
                )

            logger.info(f"Fetched {len(accounts)} accounts for user {user_id}")
            return accounts

    async def get_raw_transactions(
        self,
        provider_id: UUID,
        user_id: UUID,
        account_id: str,
        session: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch raw transaction data from Schwab API.

        Args:
            provider_id: The provider instance ID.
            user_id: Dashtam user ID.
            account_id: Schwab account number.
            session: Database session for operations.
            start_date: Beginning of date range (default: 30 days ago).
            end_date: End of date range (default: today).

        Returns:
            List of raw transaction dictionaries from Schwab API.

        Raises:
            Exception: If API call fails or authentication issues.
        """
        # Get user's access token
        access_token = await self._get_user_access_token(provider_id, user_id, session)

        # Default date range if not specified
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/trader/v1/accounts/{account_id}/transactions",
                headers=self._get_api_headers(access_token),
                params={
                    "startDate": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "endDate": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "types": "TRADE,DIVIDEND,INTEREST,JOURNAL,FEE",
                },
            )

            if response.status_code != 200:
                raise Exception(f"Failed to fetch transactions: {response.text}")

            transactions = response.json()
            logger.info(
                f"Fetched {len(transactions)} raw transactions for account {account_id}"
            )

            return transactions

    def parse_transaction(self, raw_transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Schwab transaction into standardized BrokerageTransaction format.

        Args:
            raw_transaction: Raw transaction data from Schwab API.

        Returns:
            Dictionary with fields matching BrokerageTransaction model.
        """
        # Extract common fields
        txn_id = str(raw_transaction.get("transactionId"))
        account_id = raw_transaction.get("accountNumber")
        txn_date = datetime.fromisoformat(
            raw_transaction.get("transactionDate").replace("Z", "+00:00")
        )
        description = raw_transaction.get("description", "")
        net_amount = Decimal(str(raw_transaction.get("netAmount", 0)))

        # Determine transaction type and parse accordingly
        txn_type = raw_transaction.get("type")

        parsed = {
            "id": txn_id,
            "account_id": account_id,
            "date": txn_date,
            "description": description,
            "amount": net_amount,
            "currency": "USD",
            "status": self._map_status(raw_transaction.get("status")),
            "pending": raw_transaction.get("status") != "VALID",
            "raw_data": raw_transaction,
            "metadata": {},
        }

        # Parse based on transaction type
        if txn_type == "TRADE":
            parsed.update(self._parse_trade_transaction(raw_transaction))
        elif txn_type == "DIVIDEND":
            parsed.update(self._parse_dividend_transaction(raw_transaction))
        elif txn_type == "INTEREST":
            parsed.update(self._parse_interest_transaction(raw_transaction))
        elif txn_type == "JOURNAL":
            parsed.update(self._parse_journal_transaction(raw_transaction))
        elif txn_type == "FEE":
            parsed.update(self._parse_fee_transaction(raw_transaction))
        else:
            # Default mapping for unknown types
            parsed["brokerage_type"] = BrokerageTransactionType.OTHER
            parsed["transaction_type"] = TransactionType.OTHER

        return parsed

    def _parse_trade_transaction(self, raw_txn: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a trade transaction (buy/sell of securities).

        Args:
            raw_txn: Raw trade transaction from Schwab.

        Returns:
            Dictionary with trade-specific fields.
        """
        trade_data = raw_txn.get("tradeDetails", {})

        # Determine if buy or sell
        is_buy = raw_txn.get("transactionSubType") in ["BY", "BUY"]

        return {
            "brokerage_type": BrokerageTransactionType.BUY
            if is_buy
            else BrokerageTransactionType.SELL,
            "transaction_type": TransactionType.DEBIT
            if is_buy
            else TransactionType.CREDIT,
            "symbol": trade_data.get("symbol"),
            "cusip": trade_data.get("cusip"),
            "security_type": self._map_security_type(trade_data.get("assetType")),
            "quantity": Decimal(str(abs(trade_data.get("quantity", 0)))),
            "price_per_unit": Decimal(str(trade_data.get("price", 0))),
            "commission": Decimal(str(raw_txn.get("commission", 0))),
            "fees": Decimal(str(raw_txn.get("fees", 0))),
            "order_id": trade_data.get("orderId"),
            "trade_date": datetime.fromisoformat(
                raw_txn.get("transactionDate").replace("Z", "+00:00")
            ),
            "settlement_date": datetime.fromisoformat(
                raw_txn.get("settlementDate").replace("Z", "+00:00")
            )
            if raw_txn.get("settlementDate")
            else None,
            "metadata": {
                "instruction": trade_data.get("instruction"),
                "position_effect": trade_data.get("positionEffect"),
                "exchange": trade_data.get("exchange"),
            },
        }

    def _parse_dividend_transaction(self, raw_txn: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a dividend transaction.

        Args:
            raw_txn: Raw dividend transaction from Schwab.

        Returns:
            Dictionary with dividend-specific fields.
        """
        return {
            "brokerage_type": BrokerageTransactionType.DIVIDEND,
            "transaction_type": TransactionType.CREDIT,
            "symbol": raw_txn.get("symbol"),
            "cusip": raw_txn.get("cusip"),
            "distribution_type": "dividend",
            "tax_withheld": Decimal(str(raw_txn.get("taxWithheld", 0))),
            "metadata": {
                "dividend_type": raw_txn.get("dividendType"),
                "payable_date": raw_txn.get("payableDate"),
                "record_date": raw_txn.get("recordDate"),
            },
        }

    def _parse_interest_transaction(self, raw_txn: Dict[str, Any]) -> Dict[str, Any]:
        """Parse an interest transaction.

        Args:
            raw_txn: Raw interest transaction from Schwab.

        Returns:
            Dictionary with interest-specific fields.
        """
        # Determine if it's margin interest (debit) or earned interest (credit)
        is_margin_interest = raw_txn.get("netAmount", 0) < 0

        return {
            "brokerage_type": (
                BrokerageTransactionType.MARGIN_INTEREST
                if is_margin_interest
                else BrokerageTransactionType.OTHER
            ),
            "transaction_type": TransactionType.DEBIT
            if is_margin_interest
            else TransactionType.CREDIT,
            "metadata": {"interest_type": "margin" if is_margin_interest else "earned"},
        }

    def _parse_journal_transaction(self, raw_txn: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a journal transaction (transfers, adjustments).

        Args:
            raw_txn: Raw journal transaction from Schwab.

        Returns:
            Dictionary with journal-specific fields.
        """
        is_transfer_in = raw_txn.get("netAmount", 0) > 0

        return {
            "brokerage_type": (
                BrokerageTransactionType.TRANSFER_IN
                if is_transfer_in
                else BrokerageTransactionType.TRANSFER_OUT
            ),
            "transaction_type": TransactionType.TRANSFER,
            "metadata": {
                "journal_type": raw_txn.get("journalType"),
                "contra_account": raw_txn.get("contraAccountNumber"),
            },
        }

    def _parse_fee_transaction(self, raw_txn: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a fee transaction.

        Args:
            raw_txn: Raw fee transaction from Schwab.

        Returns:
            Dictionary with fee-specific fields.
        """
        fee_type = raw_txn.get("feeType", "").upper()

        # Map to specific brokerage transaction type if possible
        if "SEC" in fee_type:
            brokerage_type = BrokerageTransactionType.SEC_FEE
        elif "COMMISSION" in fee_type:
            brokerage_type = BrokerageTransactionType.COMMISSION
        else:
            brokerage_type = BrokerageTransactionType.OTHER

        return {
            "brokerage_type": brokerage_type,
            "transaction_type": TransactionType.FEE,
            "metadata": {
                "fee_type": raw_txn.get("feeType"),
                "fee_description": raw_txn.get("feeDescription"),
            },
        }

    def _map_account_type(self, schwab_type: str) -> str:
        """Map Schwab account type to Dashtam account type.

        Args:
            schwab_type: Account type from Schwab API.

        Returns:
            Standardized account type string.
        """
        mapping = {
            "CASH": "brokerage",
            "MARGIN": "margin",
            "IRA": "ira",
            "ROTH_IRA": "roth_ira",
            "TRADITIONAL_IRA": "traditional_ira",
            "ROLLOVER_IRA": "rollover_ira",
            "SEP_IRA": "sep_ira",
            "401K": "401k",
        }
        return mapping.get(schwab_type, "investment")

    def _map_security_type(self, asset_type: str) -> str:
        """Map Schwab asset type to standardized security type.

        Args:
            asset_type: Asset type from Schwab API.

        Returns:
            Standardized security type string.
        """
        mapping = {
            "EQUITY": "stock",
            "ETF": "etf",
            "MUTUAL_FUND": "mutual_fund",
            "OPTION": "option",
            "FIXED_INCOME": "bond",
            "CASH_EQUIVALENT": "money_market",
        }
        return mapping.get(asset_type, "other")

    def _map_status(self, status: str) -> str:
        """Map Schwab transaction status to standardized status.

        Args:
            status: Status from Schwab API.

        Returns:
            Standardized status string.
        """
        if status == "VALID":
            return "completed"
        elif status == "PENDING":
            return "pending"
        elif status == "CANCELLED":
            return "cancelled"
        else:
            return "unknown"

    async def _get_user_access_token(
        self, provider_id: UUID, user_id: UUID, session: AsyncSession
    ) -> str:
        """Get user's access token from database.

        Uses the TokenService to retrieve a valid access token, handling
        automatic refresh if the token is expired or expiring soon.

        Args:
            provider_id: The provider instance ID.
            user_id: Dashtam user ID.
            session: Database session for operations.

        Returns:
            Valid access token for Schwab API.

        Raises:
            Exception: If no valid token found or token refresh fails.
        """
        from src.services.token_service import TokenService

        token_service = TokenService(session)
        access_token = await token_service.get_valid_access_token(
            provider_id=provider_id, user_id=user_id
        )
        return access_token

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL for Schwab.

        Args:
            state: Optional state parameter for OAuth security.

        Returns:
            Complete authorization URL to redirect user to.
        """
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "scope": "accounts read trading",
            "redirect_uri": self.redirect_uri,
        }

        if state:
            params["state"] = state

        from urllib.parse import urlencode

        query_string = urlencode(params)

        return f"{self.base_url}/v1/oauth/authorize?{query_string}"

    def requires_mfa(self) -> bool:
        """Schwab requires MFA for all OAuth flows.

        Returns:
            True, as Schwab always requires MFA.
        """
        return True
