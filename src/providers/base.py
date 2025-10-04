"""Base provider module with specialized transaction handling for different provider types.

This module provides the foundation for all financial service provider integrations
in Dashtam. It handles the complexity of different transaction types across banking,
brokerage, credit card, crypto, and aggregator providers.

The design uses:
1. A base Transaction class with common fields
2. Specialized transaction classes for each provider type
3. A transaction factory pattern to create the right type
4. Provider-specific transaction parsing

This approach ensures that banking transactions (deposits, withdrawals, transfers)
are handled differently from brokerage transactions (trades, dividends, options),
while maintaining a consistent interface for the Dashtam application.

Key Features:
- Type-safe transaction handling per provider category
- Preserves all provider-specific data while standardizing common fields
- Extensible design for adding new providers and transaction types
- Unified interface for querying across all financial institutions
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Type
from datetime import datetime
from enum import Enum
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================================
# ENUMS
# ============================================================================


class ProviderType(str, Enum):
    """Types of financial service providers."""

    BROKERAGE = "brokerage"
    BANKING = "banking"
    AGGREGATOR = "aggregator"
    CRYPTO = "crypto"
    CREDIT_CARD = "credit_card"


class TransactionType(str, Enum):
    """Base transaction types common across providers."""

    DEBIT = "debit"
    CREDIT = "credit"
    TRANSFER = "transfer"
    FEE = "fee"
    INTEREST = "interest"
    OTHER = "other"


class BrokerageTransactionType(str, Enum):
    """Brokerage-specific transaction types."""

    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    CAPITAL_GAIN = "capital_gain"
    OPTION_EXERCISE = "option_exercise"
    OPTION_ASSIGNMENT = "option_assignment"
    MARGIN_INTEREST = "margin_interest"
    COMMISSION = "commission"
    SEC_FEE = "sec_fee"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class CryptoTransactionType(str, Enum):
    """Crypto-specific transaction types."""

    BUY = "buy"
    SELL = "sell"
    EXCHANGE = "exchange"
    MINING_REWARD = "mining_reward"
    STAKING_REWARD = "staking_reward"
    GAS_FEE = "gas_fee"
    WALLET_TRANSFER = "wallet_transfer"
    AIRDROP = "airdrop"


class OrderType(str, Enum):
    """Order types for brokerage transactions."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


# ============================================================================
# BASE TRANSACTION MODEL
# ============================================================================


class BaseTransaction(BaseModel):
    """Base transaction model with common fields across all providers.

    This is the foundation that all specialized transactions inherit from.
    It contains the minimum fields that every transaction must have.
    """

    id: str = Field(..., description="Unique transaction ID from provider")
    account_id: str = Field(..., description="Associated account ID")
    date: datetime = Field(..., description="Transaction date")
    description: str = Field(..., description="Human-readable description")
    amount: Decimal = Field(
        ..., description="Transaction amount (use Decimal for precision)"
    )
    currency: str = Field(default="USD", description="Currency code")
    status: str = Field(default="completed", description="Transaction status")
    pending: bool = Field(default=False, description="Is transaction pending")

    # Common categorization
    transaction_type: TransactionType = Field(default=TransactionType.OTHER)
    category: Optional[str] = Field(
        None, description="Provider or user-defined category"
    )
    subcategory: Optional[str] = Field(None, description="More specific categorization")

    # Metadata for provider-specific data
    raw_data: Dict[str, Any] = Field(
        default_factory=dict, description="Original provider data"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional processed data"
    )

    model_config = ConfigDict(
        # Pydantic v2 handles Decimal and datetime serialization automatically
        # Decimal is serialized as string by default to preserve precision
        # datetime is serialized as ISO format by default
    )

    @field_validator("amount", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: Any) -> Decimal:
        """Ensure amount is always a Decimal for precision."""
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


# ============================================================================
# SPECIALIZED TRANSACTION MODELS
# ============================================================================


class BankingTransaction(BaseTransaction):
    """Transaction model for traditional banking providers.

    Extends base transaction with banking-specific fields.
    """

    # Banking-specific fields
    balance_after: Optional[Decimal] = Field(
        None, description="Account balance after transaction"
    )
    check_number: Optional[str] = Field(None, description="Check number if applicable")
    reference_number: Optional[str] = Field(None, description="Bank reference number")

    # Transfer details
    is_transfer: bool = Field(default=False)
    linked_account_id: Optional[str] = Field(
        None, description="For transfers between accounts"
    )

    # Location info for physical transactions
    merchant_name: Optional[str] = Field(None, description="Merchant or ATM name")
    merchant_location: Optional[str] = Field(None, description="Transaction location")

    # Transaction method
    method: Optional[str] = Field(None, description="ACH, wire, ATM, check, etc.")


class BrokerageTransaction(BaseTransaction):
    """Transaction model for investment brokerage providers.

    Handles stock trades, options, dividends, and other investment transactions.
    """

    # Security information
    symbol: Optional[str] = Field(None, description="Stock/ETF/Option symbol")
    cusip: Optional[str] = Field(None, description="CUSIP identifier")
    security_type: Optional[str] = Field(
        None, description="stock, etf, option, mutual_fund, bond"
    )

    # Trade details
    brokerage_type: Optional[BrokerageTransactionType] = Field(None)
    quantity: Optional[Decimal] = Field(None, description="Number of shares/contracts")
    price_per_unit: Optional[Decimal] = Field(
        None, description="Price per share/contract"
    )

    # Order information
    order_type: Optional[OrderType] = Field(None)
    order_id: Optional[str] = Field(None, description="Broker's order ID")
    trade_date: Optional[datetime] = Field(None, description="Trade execution date")
    settlement_date: Optional[datetime] = Field(None, description="Settlement date")

    # Fees and commissions
    commission: Optional[Decimal] = Field(None, description="Trading commission")
    fees: Optional[Decimal] = Field(None, description="Other fees (SEC, TAF, etc.)")

    # For options
    option_type: Optional[str] = Field(None, description="call or put")
    strike_price: Optional[Decimal] = Field(None, description="Option strike price")
    expiration_date: Optional[datetime] = Field(None, description="Option expiration")

    # For dividends/distributions
    distribution_type: Optional[str] = Field(
        None, description="dividend, capital_gain, return_of_capital"
    )
    tax_withheld: Optional[Decimal] = Field(None, description="Tax withholding amount")


class CreditCardTransaction(BaseTransaction):
    """Transaction model for credit card providers.

    Handles purchases, payments, cash advances, and rewards.
    """

    # Merchant information
    merchant_name: str = Field(..., description="Merchant name")
    merchant_category: Optional[str] = Field(
        None, description="MCC - Merchant Category Code"
    )
    merchant_location: Optional[str] = Field(
        None, description="Merchant city/state/country"
    )

    # Credit card specific
    is_credit: bool = Field(default=False, description="True for payments/credits")
    is_cash_advance: bool = Field(default=False)
    is_foreign_transaction: bool = Field(default=False)

    # Rewards
    rewards_earned: Optional[Dict[str, Decimal]] = Field(
        None, description="Points/cashback earned {type: amount}"
    )
    rewards_redeemed: Optional[Dict[str, Decimal]] = Field(None)

    # Additional fees
    foreign_transaction_fee: Optional[Decimal] = Field(None)
    cash_advance_fee: Optional[Decimal] = Field(None)

    # Dispute/return status
    is_disputed: bool = Field(default=False)
    is_return: bool = Field(default=False)
    original_transaction_id: Optional[str] = Field(
        None, description="For returns/disputes"
    )


class CryptoTransaction(BaseTransaction):
    """Transaction model for cryptocurrency providers.

    Handles crypto trades, transfers, staking, and DeFi transactions.
    """

    # Crypto details
    crypto_type: CryptoTransactionType = Field(...)
    coin_symbol: str = Field(..., description="BTC, ETH, etc.")
    coin_name: Optional[str] = Field(None, description="Bitcoin, Ethereum, etc.")

    # Trade information
    quantity: Decimal = Field(..., description="Amount of cryptocurrency")
    price_per_coin: Optional[Decimal] = Field(
        None, description="Price in fiat currency"
    )

    # For exchanges/swaps
    to_coin_symbol: Optional[str] = Field(
        None, description="For crypto-to-crypto exchanges"
    )
    to_quantity: Optional[Decimal] = Field(None)
    exchange_rate: Optional[Decimal] = Field(None)

    # Network/blockchain details
    blockchain: Optional[str] = Field(
        None, description="Bitcoin, Ethereum, Solana, etc."
    )
    transaction_hash: Optional[str] = Field(
        None, description="Blockchain transaction hash"
    )
    block_number: Optional[int] = Field(None)

    # Fees
    network_fee: Optional[Decimal] = Field(None, description="Gas/network fees")
    platform_fee: Optional[Decimal] = Field(None, description="Exchange fees")

    # Wallet information
    from_address: Optional[str] = Field(None, description="Sending wallet address")
    to_address: Optional[str] = Field(None, description="Receiving wallet address")

    # DeFi/Staking
    protocol: Optional[str] = Field(None, description="DeFi protocol name")
    apy: Optional[Decimal] = Field(
        None, description="Annual percentage yield for staking"
    )


class AggregatorTransaction(BaseTransaction):
    """Transaction model for aggregators like Plaid.

    Aggregators pull from multiple sources, so this model is flexible
    and includes fields to identify the source institution and type.
    """

    # Source information
    source_institution: str = Field(..., description="Original financial institution")
    source_institution_id: Optional[str] = Field(None)
    source_account_type: str = Field(
        ..., description="checking, savings, credit, investment"
    )

    # Aggregator-specific categorization
    plaid_category: Optional[List[str]] = Field(
        None, description="Plaid's category hierarchy"
    )
    personal_finance_category: Optional[str] = Field(
        None, description="Aggregator's PFM category"
    )

    # Enriched data
    merchant_name: Optional[str] = Field(None, description="Cleaned merchant name")
    merchant_logo: Optional[str] = Field(None, description="URL to merchant logo")
    is_recurring: bool = Field(
        default=False, description="Is this a recurring transaction"
    )

    # Location data
    location: Optional[Dict[str, Any]] = Field(
        None, description="Transaction location data"
    )

    # The actual transaction could be any type, so we store that info
    underlying_type: Optional[str] = Field(
        None, description="banking, brokerage, credit_card"
    )

    # Store the specialized transaction data if needed
    specialized_data: Optional[Dict[str, Any]] = Field(
        None, description="Data specific to underlying transaction type"
    )


# ============================================================================
# TRANSACTION FACTORY
# ============================================================================


class TransactionFactory:
    """Factory class to create appropriate transaction types based on provider type.

    This factory pattern allows us to create the right transaction model
    based on the provider type, making it easy to parse provider-specific
    data into our standardized models.
    """

    # Mapping of provider types to transaction classes
    TRANSACTION_CLASSES: Dict[ProviderType, Type[BaseTransaction]] = {
        ProviderType.BANKING: BankingTransaction,
        ProviderType.BROKERAGE: BrokerageTransaction,
        ProviderType.CREDIT_CARD: CreditCardTransaction,
        ProviderType.CRYPTO: CryptoTransaction,
        ProviderType.AGGREGATOR: AggregatorTransaction,
    }

    @classmethod
    def create_transaction(
        cls, provider_type: ProviderType, data: Dict[str, Any]
    ) -> BaseTransaction:
        """Create a transaction of the appropriate type.

        Args:
            provider_type: The type of provider.
            data: Transaction data from the provider.

        Returns:
            A transaction object of the appropriate specialized type.

        Example:
            >>> factory = TransactionFactory()
            >>> txn_data = {"id": "123", "amount": "100.50", ...}
            >>> transaction = factory.create_transaction(
            >>>     ProviderType.BROKERAGE,
            >>>     txn_data
            >>> )
            >>> isinstance(transaction, BrokerageTransaction)  # True
        """
        transaction_class = cls.TRANSACTION_CLASSES.get(provider_type, BaseTransaction)
        return transaction_class(**data)

    @classmethod
    def parse_provider_transaction(
        cls,
        provider_type: ProviderType,
        raw_transaction: Dict[str, Any],
        parser_func: Optional[callable] = None,
    ) -> BaseTransaction:
        """Parse raw provider data into appropriate transaction type.

        Args:
            provider_type: The type of provider.
            raw_transaction: Raw transaction data from provider API.
            parser_func: Optional custom parser function.

        Returns:
            Parsed transaction of the appropriate type.
        """
        if parser_func:
            parsed_data = parser_func(raw_transaction)
        else:
            # Default parsing - just pass through with raw_data
            parsed_data = {
                "raw_data": raw_transaction,
                **raw_transaction,  # Attempt to map fields directly
            }

        return cls.create_transaction(provider_type, parsed_data)


# ============================================================================
# BASE PROVIDER
# ============================================================================


class BaseProvider(ABC):
    """Base provider with specialized transaction handling.

    This base provider class includes:
    1. Provider-type aware transaction handling
    2. Transaction factory integration
    3. Provider-specific parsing methods
    4. Common authentication and account management interface
    """

    def __init__(self):
        """Initialize the provider with type information."""
        self.provider_name: str = self.__class__.__name__.replace(
            "Provider", ""
        ).lower()
        self.provider_type: ProviderType = (
            ProviderType.BROKERAGE
        )  # Override in subclass
        self.transaction_factory = TransactionFactory()
        self.is_configured: bool = False

    @abstractmethod
    async def get_raw_transactions(
        self,
        user_id: UUID,
        account_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch raw transaction data from the provider API.

        This method should return the raw API response for transactions.
        The parsing will be handled separately.

        Args:
            user_id: The user ID.
            account_id: The account ID.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            List of raw transaction dictionaries from the provider.
        """
        pass

    @abstractmethod
    def parse_transaction(self, raw_transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a raw transaction into standardized format.

        This method should be implemented by each provider to map
        their specific transaction format to our standardized fields.

        Args:
            raw_transaction: Raw transaction from provider API.

        Returns:
            Dictionary with standardized transaction fields.

        Example implementation for Schwab:
            >>> def parse_transaction(self, raw_txn):
            >>>     return {
            >>>         "id": raw_txn["transactionId"],
            >>>         "symbol": raw_txn["symbol"],
            >>>         "quantity": raw_txn["quantity"],
            >>>         "price_per_unit": raw_txn["price"],
            >>>         "brokerage_type": BrokerageTransactionType.BUY,
            >>>         ...
            >>>     }
        """
        pass

    async def get_transactions(
        self,
        user_id: UUID,
        account_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[BaseTransaction]:
        """Get parsed transactions of the appropriate type.

        This method orchestrates fetching and parsing transactions,
        returning them as the appropriate specialized transaction type.

        Args:
            user_id: The user ID.
            account_id: The account ID.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            List of typed transaction objects.
        """
        # Fetch raw transactions
        raw_transactions = await self.get_raw_transactions(
            user_id, account_id, start_date, end_date
        )

        # Parse each transaction into the appropriate type
        parsed_transactions = []
        for raw_txn in raw_transactions:
            parsed_data = self.parse_transaction(raw_txn)
            transaction = self.transaction_factory.create_transaction(
                self.provider_type, parsed_data
            )
            parsed_transactions.append(transaction)

        return parsed_transactions

    def get_transaction_type(self) -> Type[BaseTransaction]:
        """Get the transaction class used by this provider.

        Returns:
            The transaction class for this provider type.
        """
        return TransactionFactory.TRANSACTION_CLASSES.get(
            self.provider_type, BaseTransaction
        )

    # ========================================================================
    # AUTHENTICATION METHODS
    # ========================================================================

    @abstractmethod
    async def authenticate(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with the provider and obtain access tokens.

        This method handles the provider-specific authentication flow,
        whether it's OAuth2, API key, or another method.

        Args:
            auth_data: Provider-specific authentication data.
                For OAuth2: {"code": "auth_code"}
                For API key: {"api_key": "key", "secret": "secret"}

        Returns:
            Authentication result containing tokens or session info.
            Typically: {"access_token": "...", "refresh_token": "..."}

        Raises:
            AuthenticationError: If authentication fails.
        """
        pass

    @abstractmethod
    async def refresh_authentication(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh expired authentication tokens.

        Uses a refresh token to obtain new access tokens without
        requiring the user to re-authenticate.

        IMPORTANT - Token Rotation Handling:
            This method MUST correctly handle token rotation by only including
            'refresh_token' in the response if the provider actually sends one.

            Token rotation occurs when a provider sends a NEW refresh token
            during the refresh operation, invalidating the old one. This is a
            security best practice used by many OAuth2 providers.

            Implementation Rules:
            1. If provider sends refresh_token → Include it in response
            2. If provider does NOT send refresh_token → Omit the key entirely
            3. NEVER default to the input refresh_token if not provided

            The TokenService will automatically detect and handle rotation by
            comparing the new refresh_token (if present) with the stored one.

        Args:
            refresh_token: The refresh token from initial authentication.

        Returns:
            Dictionary containing new authentication tokens:
            {
                "access_token": str,           # Required: New access token
                "refresh_token": str,          # Optional: Only if rotated by provider
                "expires_in": int,             # Optional: Token lifetime in seconds
                "token_type": str,             # Optional: Usually "Bearer"
                "id_token": str,               # Optional: JWT ID token (OIDC)
                "scope": str                   # Optional: Granted OAuth scopes
            }

            Examples:
                # Provider rotates refresh token (includes new one)
                {"access_token": "new_abc", "refresh_token": "new_xyz", "expires_in": 3600}

                # Provider does NOT rotate (omits refresh_token)
                {"access_token": "new_abc", "expires_in": 3600}

        Raises:
            AuthenticationError: If refresh fails.

        Example Implementation:
            ```python
            async def refresh_authentication(self, refresh_token: str) -> Dict[str, Any]:
                response = await self.http_client.post(
                    f"{self.base_url}/oauth/token",
                    data={"grant_type": "refresh_token", "refresh_token": refresh_token}
                )
                tokens = response.json()

                result = {
                    "access_token": tokens["access_token"],
                    "expires_in": tokens.get("expires_in", 3600),
                }

                # Only include refresh_token if provider sent it
                if "refresh_token" in tokens:
                    result["refresh_token"] = tokens["refresh_token"]

                return result
            ```
        """
        pass

    # ========================================================================
    # ACCOUNT METHODS
    # ========================================================================

    @abstractmethod
    async def get_accounts(
        self, provider_id: UUID, user_id: UUID, session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Fetch all accounts for the authenticated user.

        Retrieves a list of all financial accounts accessible through
        this provider for the given user.

        Args:
            provider_id: The provider instance ID.
            user_id: The Dashtam user ID to fetch accounts for.
            session: Database session for operations.

        Returns:
            List of account dictionaries. Each account should include:
            - id: Provider's account identifier
            - name: Account name or nickname
            - account_type: Type of account (checking, savings, investment, etc.)
            - balance: Current balance (optional)
            - currency: Account currency (default: USD)

        Raises:
            ProviderError: If the API call fails.
        """
        pass

    async def validate_connection(self, user_id: UUID) -> bool:
        """Validate that the provider connection is working.

        Tests the connection by attempting to fetch accounts.
        Can be overridden for more specific validation logic.

        Args:
            user_id: The user to validate connection for.

        Returns:
            True if connection is valid, False otherwise.
        """
        try:
            accounts = await self.get_accounts(user_id)
            return len(accounts) >= 0  # Connection works even if no accounts
        except Exception:
            return False

    # ========================================================================
    # PROVIDER INFO METHODS
    # ========================================================================

    async def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this provider.

        Returns metadata about the provider including its capabilities,
        requirements, and current status.

        Returns:
            Provider information dictionary.
        """
        return {
            "name": self.provider_name,
            "type": self.provider_type.value,
            "is_configured": self.is_configured,
            "supported_account_types": self.get_supported_account_types(),
            "supported_transaction_types": self.get_supported_transaction_types(),
            "requires_mfa": self.requires_mfa(),
        }

    def get_supported_account_types(self) -> List[str]:
        """Get list of account types this provider supports.

        Override in child classes to specify supported account types.

        Returns:
            List of supported account type strings.
        """
        if self.provider_type == ProviderType.BANKING:
            return ["checking", "savings", "money_market", "cd"]
        elif self.provider_type == ProviderType.BROKERAGE:
            return ["investment", "retirement", "401k", "ira", "brokerage"]
        elif self.provider_type == ProviderType.CREDIT_CARD:
            return ["credit_card"]
        elif self.provider_type == ProviderType.CRYPTO:
            return ["crypto_wallet", "crypto_exchange"]
        else:
            return ["checking", "savings", "investment", "credit_card"]

    def get_supported_transaction_types(self) -> List[str]:
        """Get list of transaction types this provider supports.

        Returns:
            List of supported transaction type strings based on provider type.
        """
        if self.provider_type == ProviderType.BROKERAGE:
            return [t.value for t in BrokerageTransactionType]
        elif self.provider_type == ProviderType.CRYPTO:
            return [t.value for t in CryptoTransactionType]
        else:
            return [t.value for t in TransactionType]

    def requires_mfa(self) -> bool:
        """Check if this provider requires multi-factor authentication.

        Override in child classes that require MFA.

        Returns:
            True if MFA is required, False otherwise.
        """
        return False
