"""Financial account type classification.

Defines account types across four categories: investment, banking, credit, and
other. Used to classify accounts from financial providers and determine
appropriate handling for each type.

Categories:
    Investment: Brokerage, IRA, 401k, HSA - accounts that hold securities
    Banking: Checking, savings, CD - traditional deposit accounts
    Credit: Credit cards, lines of credit - revolving credit accounts
    Other: Loans, mortgages, uncategorized

Reference:
    - docs/architecture/account-domain-model.md

Usage:
    from src.domain.enums import AccountType

    if account_type in AccountType.investment_types():
        # Handle investment account
"""

from enum import Enum


class AccountType(str, Enum):
    """Financial account type classification.

    Inherits from str for easy serialization and database storage.
    Values are lowercase for consistency across the system.

    Categories:
        Investment: Securities, trading, retirement accounts
        Banking: Checking, savings, money market accounts
        Credit: Credit cards, lines of credit
        Other: Loans, mortgages, specialized accounts

    Example:
        >>> account_type = AccountType.BROKERAGE
        >>> account_type.value
        'brokerage'
        >>> account_type in AccountType.investment_types()
        True
    """

    # -------------------------------------------------------------------------
    # Investment Accounts
    # -------------------------------------------------------------------------

    BROKERAGE = "brokerage"
    """General brokerage/trading account.

    Standard taxable investment account for buying and selling securities.
    No special tax treatment.
    """

    IRA = "ira"
    """Traditional Individual Retirement Account.

    Tax-deferred retirement account. Contributions may be tax-deductible,
    withdrawals taxed as ordinary income.
    """

    ROTH_IRA = "roth_ira"
    """Roth Individual Retirement Account.

    After-tax contributions, tax-free qualified withdrawals.
    Subject to income limits and contribution limits.
    """

    RETIREMENT_401K = "401k"
    """Employer-sponsored 401(k) retirement account.

    Tax-deferred contributions from payroll. May include employer match.
    Early withdrawal penalties apply before age 59½.
    """

    RETIREMENT_403B = "403b"
    """403(b) retirement account for nonprofits.

    Similar to 401(k) but for employees of public schools,
    tax-exempt organizations, and certain ministers.
    """

    HSA = "hsa"
    """Health Savings Account.

    Triple tax-advantaged account for qualified medical expenses.
    Requires enrollment in high-deductible health plan.
    Can be invested and used for retirement after age 65.
    """

    # -------------------------------------------------------------------------
    # Banking Accounts
    # -------------------------------------------------------------------------

    CHECKING = "checking"
    """Checking/current account.

    Transactional account for everyday banking.
    Typically offers unlimited deposits and withdrawals.
    """

    SAVINGS = "savings"
    """Savings account.

    Deposit account for saving money with interest.
    May have withdrawal limits under Regulation D.
    """

    MONEY_MARKET = "money_market"
    """Money market account.

    Higher interest savings account with check-writing capabilities.
    Often requires higher minimum balance.
    """

    CD = "cd"
    """Certificate of Deposit.

    Time deposit with fixed term and fixed interest rate.
    Early withdrawal penalties typically apply.
    """

    # -------------------------------------------------------------------------
    # Credit Accounts
    # -------------------------------------------------------------------------

    CREDIT_CARD = "credit_card"
    """Credit card account.

    Revolving credit with monthly billing cycle.
    Has credit limit and may incur interest on balances.
    """

    LINE_OF_CREDIT = "line_of_credit"
    """Line of credit account.

    Revolving credit facility with draw period.
    Interest charged only on amount borrowed.
    """

    # -------------------------------------------------------------------------
    # Other Accounts
    # -------------------------------------------------------------------------

    LOAN = "loan"
    """Loan account.

    Installment loan with fixed repayment schedule.
    Examples: personal loan, auto loan, student loan.
    """

    MORTGAGE = "mortgage"
    """Mortgage account.

    Real estate loan secured by property.
    Long-term installment loan (15-30 years typical).
    """

    OTHER = "other"
    """Uncategorized account type.

    Fallback for account types not fitting other categories.
    Used when provider returns unknown account type.
    """

    # -------------------------------------------------------------------------
    # Class Methods - Category Queries
    # -------------------------------------------------------------------------

    @classmethod
    def values(cls) -> list[str]:
        """Get all account type values as strings.

        Returns:
            List of account type string values.

        Example:
            >>> AccountType.values()
            ['brokerage', 'ira', 'roth_ira', ...]
        """
        return [account_type.value for account_type in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid account type.

        Args:
            value: String to check.

        Returns:
            True if value is a valid account type.

        Example:
            >>> AccountType.is_valid("brokerage")
            True
            >>> AccountType.is_valid("invalid")
            False
        """
        return value in cls.values()

    @classmethod
    def investment_types(cls) -> list["AccountType"]:
        """Get account types that hold securities.

        Investment accounts can hold stocks, bonds, mutual funds,
        ETFs, and other securities. These accounts may have
        special tax treatment.

        Returns:
            List of investment account types.

        Example:
            >>> AccountType.BROKERAGE in AccountType.investment_types()
            True
        """
        return [
            cls.BROKERAGE,
            cls.IRA,
            cls.ROTH_IRA,
            cls.RETIREMENT_401K,
            cls.RETIREMENT_403B,
            cls.HSA,
        ]

    @classmethod
    def bank_types(cls) -> list["AccountType"]:
        """Get traditional banking account types.

        Bank accounts are deposit accounts held at financial
        institutions. They are FDIC insured up to limits.

        Returns:
            List of banking account types.

        Example:
            >>> AccountType.CHECKING in AccountType.bank_types()
            True
        """
        return [cls.CHECKING, cls.SAVINGS, cls.MONEY_MARKET, cls.CD]

    @classmethod
    def retirement_types(cls) -> list["AccountType"]:
        """Get retirement/tax-advantaged account types.

        These accounts have special tax treatment and are
        designed for long-term retirement savings.

        Returns:
            List of retirement account types.

        Example:
            >>> AccountType.IRA in AccountType.retirement_types()
            True
        """
        return [
            cls.IRA,
            cls.ROTH_IRA,
            cls.RETIREMENT_401K,
            cls.RETIREMENT_403B,
            cls.HSA,
        ]

    @classmethod
    def credit_types(cls) -> list["AccountType"]:
        """Get credit and loan account types.

        Credit accounts represent money owed. Balance is typically
        shown as negative or as amount owed.

        Returns:
            List of credit account types.

        Example:
            >>> AccountType.CREDIT_CARD in AccountType.credit_types()
            True
        """
        return [cls.CREDIT_CARD, cls.LINE_OF_CREDIT, cls.LOAN, cls.MORTGAGE]

    # -------------------------------------------------------------------------
    # Instance Methods - Type Checks
    # -------------------------------------------------------------------------

    def is_investment(self) -> bool:
        """Check if this account type is an investment account.

        Returns:
            True if this is an investment account type.

        Example:
            >>> AccountType.BROKERAGE.is_investment()
            True
            >>> AccountType.CHECKING.is_investment()
            False
        """
        return self in self.investment_types()

    def is_bank(self) -> bool:
        """Check if this account type is a banking account.

        Returns:
            True if this is a banking account type.

        Example:
            >>> AccountType.CHECKING.is_bank()
            True
            >>> AccountType.BROKERAGE.is_bank()
            False
        """
        return self in self.bank_types()

    def is_retirement(self) -> bool:
        """Check if this account type is a retirement account.

        Returns:
            True if this is a retirement account type.

        Example:
            >>> AccountType.IRA.is_retirement()
            True
            >>> AccountType.BROKERAGE.is_retirement()
            False
        """
        return self in self.retirement_types()

    def is_credit(self) -> bool:
        """Check if this account type is a credit account.

        Returns:
            True if this is a credit account type.

        Example:
            >>> AccountType.CREDIT_CARD.is_credit()
            True
            >>> AccountType.CHECKING.is_credit()
            False
        """
        return self in self.credit_types()

    @property
    def category(self) -> str:
        """Get the category for this account type.

        Returns:
            Category string: "investment", "banking", "credit", or "other".

        Example:
            >>> AccountType.BROKERAGE.category
            'investment'
            >>> AccountType.CHECKING.category
            'banking'
        """
        if self.is_investment():
            return "investment"
        if self.is_bank():
            return "banking"
        if self.is_credit():
            return "credit"
        return "other"
