"""
Square Terminal API integration for Nucleus.

Handles creating terminal checkout requests, querying checkout status, and
managing Point of Sale configuration. All functions here are for internal
service use only — they must never be called directly from Textual screens
except through the handlers in screens/dashboard.py.

Square Terminal flow:
  1. Staff fills the Manual Transaction form and clicks Process Transaction.
  2. process_terminal_checkout() sends a checkout request to the configured
     terminal device via the Square API.
  3. The terminal device displays the amount and accepts card / contactless payment.
  4. Staff can press Check Terminal Status later to pull the current state from Square
     and update the local SquareTransaction record.

When Square is not enabled the function falls back to recording a local-only
transaction so the staff always gets an audit record regardless of POS state.
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlmodel import Session, desc, select

from core.database import engine
from core.models import PosConfig, SquareTransaction, SquareTransactionStatus


# ---------------------------------------------------------------------------
# POS configuration helpers
# ---------------------------------------------------------------------------


def get_pos_config() -> PosConfig:
    """
    Returns the single PosConfig row, creating a default one (id=1) if it
    does not yet exist. Callers can treat the return value as always non-None.
    """
    with Session(engine) as session:
        config = session.get(PosConfig, 1)
        if not config:
            config = PosConfig(id=1)
            session.add(config)
            session.commit()
            session.refresh(config)
        return config


def pos_sandbox_token_is_configured() -> bool:
    """Returns True when a non-empty sandbox access token has been stored."""
    config = get_pos_config()
    return bool(config.square_access_token_sandbox)


def pos_production_token_is_configured() -> bool:
    """Returns True when a non-empty production access token has been stored."""
    config = get_pos_config()
    return bool(config.square_access_token_production)


def save_pos_config(
    enabled: bool,
    environment: str,
    location_id: str,
    device_id: str,
    currency: str,
) -> None:
    """
    Persists the non-sensitive POS configuration fields.
    Access tokens are saved separately via save_pos_access_token() so that
    toggling between sandbox and production never clears a stored credential.
    """
    with Session(engine) as session:
        config = session.get(PosConfig, 1)
        if not config:
            config = PosConfig(id=1)
        config.square_enabled = enabled
        config.square_environment = environment
        config.square_location_id = location_id.strip()
        config.square_device_id = device_id.strip()
        config.square_currency = currency.strip().upper() or "CAD"
        session.add(config)
        session.commit()


def save_pos_access_token(token: str, environment: str) -> None:
    """
    Stores the access token for the specified environment ("sandbox" or "production"),
    overwriting any previously saved value for that environment only.
    The raw token is never returned to the UI after this call.
    """
    with Session(engine) as session:
        config = session.get(PosConfig, 1)
        if not config:
            config = PosConfig(id=1)
        if environment == "production":
            config.square_access_token_production = token.strip()
        else:
            config.square_access_token_sandbox = token.strip()
        session.add(config)
        session.commit()


# ---------------------------------------------------------------------------
# Square SDK client factory
# ---------------------------------------------------------------------------


def _get_square_client():
    """
    Builds a configured Square SDK client (squareup v44+) using the stored
    access token for the currently active environment.
    Returns None if the squareup package is not installed or if no token has
    been configured for the active environment, rather than raising an exception.
    """
    try:
        from square import Square
        from square.client import SquareEnvironment
    except ImportError:
        return None

    config = get_pos_config()
    if config.square_environment == "production":
        token = config.square_access_token_production
        env = SquareEnvironment.PRODUCTION
    else:
        token = config.square_access_token_sandbox
        env = SquareEnvironment.SANDBOX

    if not token:
        return None

    return Square(token=token, environment=env)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_hackspace_name() -> str:
    """Returns the configured hackspace name for use in Square statement fields."""
    try:
        from core.services import get_setting

        return get_setting("hackspace_name", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Square Customer helpers
# ---------------------------------------------------------------------------


def _get_or_create_square_customer(
    client,
    customer_name: str,
    email: Optional[str],
    phone: Optional[str],
) -> Optional[str]:
    """
    Finds an existing Square Customer by email and returns their ID, or creates
    a new one if no match is found. Returns None when neither email nor name is
    available, or on API error — the checkout proceeds without a customer link.
    Attaching a customer ID to a checkout causes Square to record the full
    customer profile against the transaction in reports and the dashboard.
    """

    name_parts = customer_name.strip().split(" ", 1) if customer_name else []
    given_name = name_parts[0] if name_parts else ""
    family_name = name_parts[1] if len(name_parts) > 1 else ""

    # Search by email first to avoid creating duplicate customer records
    if email:
        try:
            from square.requests.customer_query import CustomerQueryParams
            from square.requests.customer_filter import CustomerFilterParams
            from square.requests.customer_text_filter import CustomerTextFilterParams

            search_result = client.customers.search(
                query=CustomerQueryParams(
                    filter=CustomerFilterParams(
                        email_address=CustomerTextFilterParams(exact=email)
                    )
                )
            )
            if search_result.customers:
                return search_result.customers[0].id
        except Exception:
            pass  # Fall through to create

    # Create a new customer record
    try:
        create_result = client.customers.create(
            given_name=given_name or None,
            family_name=family_name or None,
            email_address=email or None,
            phone_number=phone or None,
            creation_source="TERMINAL",
        )
        if create_result.customer:
            return create_result.customer.id
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Transaction record helpers
# ---------------------------------------------------------------------------


def _create_transaction_record(
    amount: float,
    customer_name: str,
    customer_email: Optional[str],
    customer_phone: Optional[str],
    description: Optional[str],
    user_account_number: Optional[int] = None,
    is_local: bool = True,
    square_checkout_id: Optional[str] = None,
    square_device_id: Optional[str] = None,
    square_location_id: Optional[str] = None,
    square_status: str = SquareTransactionStatus.LOCAL,
    square_raw_response: Optional[str] = None,
) -> SquareTransaction:
    """
    Inserts a SquareTransaction row and returns the refreshed object.
    This is an internal helper; callers should use process_terminal_checkout().
    """
    with Session(engine) as session:
        txn = SquareTransaction(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email or None,
            customer_phone=customer_phone or None,
            description=description or None,
            user_account_number=user_account_number,
            is_local=is_local,
            square_checkout_id=square_checkout_id,
            square_device_id=square_device_id,
            square_location_id=square_location_id,
            square_status=square_status,
            square_raw_response=square_raw_response,
        )
        session.add(txn)
        session.commit()
        session.refresh(txn)
        return txn


# ---------------------------------------------------------------------------
# Core POS operations
# ---------------------------------------------------------------------------


def process_terminal_checkout(
    amount: float,
    customer_name: str,
    customer_email: Optional[str],
    customer_phone: Optional[str],
    description: Optional[str],
    user_account_number: Optional[int] = None,
) -> Tuple[bool, str, Optional[SquareTransaction]]:
    """
    Sends a payment request to the configured Square Terminal device and records
    the result in the SquareTransaction table.

    Returns a (success, message, transaction) tuple.
    - success: True when the checkout was accepted by Square or recorded locally.
    - message: Human-readable result suitable for displaying as a TUI notification.
    - transaction: The saved SquareTransaction record, or None on hard failure.

    Falls back to a local-only record when Square Terminal is not enabled so
    staff always get an audit trail regardless of POS state.
    """
    config = get_pos_config()

    # Square not enabled — record locally and return immediately
    if not config.square_enabled:
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=True,
            square_status=SquareTransactionStatus.LOCAL,
        )
        return (
            True,
            "Transaction recorded locally (Square Terminal is not enabled).",
            txn,
        )

    client = _get_square_client()
    if not client:
        return (
            False,
            "Square client could not be initialised. Check that the access token is configured.",
            None,
        )

    # Square API amounts are in the smallest currency unit (cents)
    amount_cents = int(round(amount * 100))

    # Find or create a Square Customer record to link to the transaction.
    # This populates customer data in Square's dashboard and reports.
    square_customer_id = _get_or_create_square_customer(
        client, customer_name, customer_email, customer_phone
    )

    # Build a structured note that surfaces all transaction details in Square's
    # dashboard since that is the most visible free-text field on a transaction.
    note_parts = []
    if customer_name:
        note_parts.append(f"Customer: {customer_name}")
    if customer_email:
        note_parts.append(f"Email: {customer_email}")
    if customer_phone:
        note_parts.append(f"Phone: {customer_phone}")
    if description:
        note_parts.append(f"Description: {description}")
    note_text = " | ".join(note_parts)

    # statement_description_identifier appears on the cardholder's bank statement
    hackspace_name = _get_hackspace_name()
    statement_id = hackspace_name[:20] if hackspace_name else None

    try:
        from square.requests.terminal_checkout import TerminalCheckoutParams
        from square.requests.money import MoneyParams
        from square.requests.device_checkout_options import DeviceCheckoutOptionsParams

        checkout_params = TerminalCheckoutParams(
            amount_money=MoneyParams(
                amount=amount_cents,
                currency=config.square_currency or "CAD",
            ),
            reference_id=customer_name[:40] if customer_name else None,
            note=note_text or None,
            customer_id=square_customer_id,
            statement_description_identifier=statement_id,
            device_options=DeviceCheckoutOptionsParams(
                device_id=config.square_device_id,
                skip_receipt_screen=False,
            ),
        )
        result = client.terminal.checkouts.create(
            idempotency_key=str(uuid.uuid4()),
            checkout=checkout_params,
        )
    except Exception as exc:
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=False,
            square_status=SquareTransactionStatus.ERROR,
            square_raw_response=str(exc),
        )
        return False, f"Square API error: {exc}", txn

    if result.errors:
        error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=False,
            square_status=SquareTransactionStatus.FAILED,
            square_raw_response=json.dumps([e.__dict__ for e in result.errors]),
        )
        return False, f"Square returned errors: {error_msg}", txn

    checkout = result.checkout
    raw_status = (checkout.status or "pending").lower()
    txn = _create_transaction_record(
        amount=amount,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        description=description,
        user_account_number=user_account_number,
        is_local=False,
        square_checkout_id=checkout.id,
        square_device_id=config.square_device_id,
        square_location_id=config.square_location_id,
        square_status=raw_status,
        square_raw_response=json.dumps(
            checkout.model_dump() if hasattr(checkout, "model_dump") else str(checkout)
        ),
    )
    return (
        True,
        f"Checkout sent to terminal. Checkout ID: {checkout.id or 'unknown'}",
        txn,
    )


def record_cash_payment(
    amount: float,
    customer_name: str,
    customer_email: Optional[str],
    customer_phone: Optional[str],
    description: Optional[str],
    user_account_number: Optional[int] = None,
) -> Tuple[bool, str, Optional[SquareTransaction]]:
    """
    Records a cash payment in Square's Payments API so the transaction appears
    in Square Dashboard and reports alongside card payments. Bookkeeper only
    needs to reconcile one system.

    Returns a (success, message, transaction) tuple.
    - success: True when the cash payment was recorded in Square or locally.
    - message: Human-readable result for UI notification.
    - transaction: The saved SquareTransaction record, or None on hard failure.

    Falls back to local-only record when Square Terminal is not enabled or
    location_id is not configured (Payments API requires a location).
    """
    config = get_pos_config()

    # Square not enabled — record locally only
    if not config.square_enabled:
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=True,
            square_status=SquareTransactionStatus.CASH,
        )
        return (
            True,
            "Cash transaction recorded locally (Square Terminal is not enabled).",
            txn,
        )

    client = _get_square_client()
    if not client:
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=True,
            square_status=SquareTransactionStatus.CASH,
        )
        return (
            True,
            "Cash transaction recorded locally (access token not configured).",
            txn,
        )

    # Location ID is required for the Payments API
    if not config.square_location_id:
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=True,
            square_status=SquareTransactionStatus.CASH,
        )
        return (
            True,
            "Cash transaction recorded locally (location ID not configured).",
            txn,
        )

    amount_cents = int(round(amount * 100))

    # Find or create a Square Customer record
    square_customer_id = _get_or_create_square_customer(
        client, customer_name, customer_email, customer_phone
    )

    # Build structured note for Square Dashboard
    note_parts = []
    if customer_name:
        note_parts.append(f"Customer: {customer_name}")
    if customer_email:
        note_parts.append(f"Email: {customer_email}")
    if customer_phone:
        note_parts.append(f"Phone: {customer_phone}")
    if description:
        note_parts.append(f"Description: {description}")
    note_text = " | ".join(note_parts)

    # Statement descriptor for bank statement
    hackspace_name = _get_hackspace_name()
    statement_id = hackspace_name[:20] if hackspace_name else None

    try:
        from square.requests.money import MoneyParams

        result = client.payments.create(
            idempotency_key=str(uuid.uuid4()),
            source_id="CASH",
            amount_money=MoneyParams(
                amount=amount_cents,
                currency=config.square_currency or "CAD",
            ),
            location_id=config.square_location_id,
            customer_id=square_customer_id,
            # Passing the buyer's email causes Square to email them a receipt
            # automatically — the only receipt mechanism available for cash payments.
            buyer_email_address=customer_email or None,
            note=note_text or None,
            reference_id=customer_name[:40] if customer_name else None,
            statement_description_identifier=statement_id,
        )
    except Exception as exc:
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=True,
            square_status=SquareTransactionStatus.CASH,
            square_raw_response=str(exc),
        )
        return False, f"Square API error: {exc}", txn

    if result.errors:
        error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
        txn = _create_transaction_record(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            user_account_number=user_account_number,
            is_local=False,
            square_status=SquareTransactionStatus.FAILED,
            square_raw_response=json.dumps([e.__dict__ for e in result.errors]),
        )
        return False, f"Square returned errors: {error_msg}", txn

    payment = result.payment
    txn = _create_transaction_record(
        amount=amount,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        description=description,
        user_account_number=user_account_number,
        is_local=False,
        square_checkout_id=payment.id,
        square_device_id=config.square_device_id,
        square_location_id=config.square_location_id,
        square_status=SquareTransactionStatus.CASH_SQUARE,
        square_raw_response=json.dumps(
            payment.model_dump() if hasattr(payment, "model_dump") else str(payment)
        ),
    )
    return (
        True,
        f"Cash transaction recorded in Square. Payment ID: {payment.id or 'unknown'}",
        txn,
    )


def get_terminal_checkout_status(
    checkout_id: str,
) -> Tuple[bool, str, Optional[dict]]:
    """
    Queries Square for the current status of a terminal checkout.
    Returns (success, status_or_error_message, raw_response_dict).
    """
    client = _get_square_client()
    if not client:
        return False, "Square client not configured.", None

    try:
        result = client.terminal.checkouts.get(checkout_id)
    except Exception as exc:
        return False, f"Square API error: {exc}", None

    if result.errors:
        error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
        return False, error_msg, None

    checkout = result.checkout
    raw = checkout.model_dump() if hasattr(checkout, "model_dump") else {}
    return True, checkout.status or "unknown", raw


def update_transaction_status(txn_id: int) -> Tuple[bool, str]:
    """
    Fetches the latest checkout status from Square for the given local
    transaction ID and updates the square_status and square_raw_response fields.
    Returns (success, human_readable_message).
    """
    with Session(engine) as session:
        txn = session.get(SquareTransaction, txn_id)
        if not txn:
            return False, "Transaction not found."
        if not txn.square_checkout_id:
            return False, "This transaction has no Square checkout ID to look up."

        ok, status_or_error, raw = get_terminal_checkout_status(txn.square_checkout_id)
        if ok:
            txn.square_status = status_or_error.lower()
            if raw:
                txn.square_raw_response = json.dumps(raw)
            txn.updated_at = datetime.now()
            session.add(txn)
            session.commit()
            return True, f"Status updated: {status_or_error}"
        else:
            return False, status_or_error


def create_device_pairing_code() -> Tuple[bool, str, Optional[str]]:
    """
    Requests a new Terminal API device pairing code from Square.
    Returns (success, message_or_code, device_code_id).
    - On success: message_or_code is the short code to enter on the terminal,
      device_code_id is the ID to pass to check_device_pairing_status().
    - On failure: message_or_code is the error description, device_code_id is None.
    """
    client = _get_square_client()
    if not client:
        return (
            False,
            "Square client not configured. Save your access token first.",
            None,
        )

    config = get_pos_config()

    try:
        from square.requests.device_code import DeviceCodeParams

        result = client.devices.codes.create(
            idempotency_key=str(uuid.uuid4()),
            device_code=DeviceCodeParams(
                name="Nucleus POS Terminal",
                location_id=config.square_location_id or None,
                product_type="TERMINAL_API",
            ),
        )
    except Exception as exc:
        return False, f"Square API error: {exc}", None

    if result.errors:
        error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
        return False, error_msg, None

    code = result.device_code
    return True, code.code or "", code.id or ""


def check_device_pairing_status(device_code_id: str) -> Tuple[bool, str, Optional[str]]:
    """
    Checks whether the terminal has been paired using the given device code ID.
    Returns (paired, message, device_id).
    - paired=True and device_id set means the terminal completed pairing.
    - paired=False means still waiting, expired, or an error occurred.
    """
    client = _get_square_client()
    if not client:
        return False, "Square client not configured.", None

    try:
        result = client.devices.codes.get(device_code_id)
    except Exception as exc:
        return False, f"Square API error: {exc}", None

    if result.errors:
        error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
        return False, error_msg, None

    code = result.device_code
    status = (code.status or "").upper()

    if status == "PAIRED":
        return True, f"Terminal paired. Device ID: {code.device_id}", code.device_id
    elif status == "EXPIRED":
        return (
            False,
            "Pairing code expired. Click Pair Terminal to generate a new one.",
            None,
        )
    else:
        return (
            False,
            f"Not paired yet (status: {status}). Enter the code on the terminal then check again.",
            None,
        )


def refresh_pending_transactions() -> int:
    """
    Queries Square for the current status of every locally-pending or in-progress
    terminal checkout and updates the database records.

    This is called before loading the transactions table so that any checkouts
    Square auto-cancelled (typically after ~5 minutes of inactivity) are reflected
    immediately rather than waiting for manual staff intervention.

    Returns the number of transactions that were successfully refreshed.
    """
    pending_statuses = {
        SquareTransactionStatus.PENDING.value,
        SquareTransactionStatus.IN_PROGRESS.value,
    }

    with Session(engine) as session:
        stmt = select(SquareTransaction).where(
            SquareTransaction.square_checkout_id.is_not(None)
        )
        candidates = session.exec(stmt).all()
        pending = [t for t in candidates if t.square_status in pending_statuses]

    refreshed = 0
    for txn in pending:
        ok, _ = update_transaction_status(txn.id)
        if ok:
            refreshed += 1

    return refreshed


# ---------------------------------------------------------------------------
# Square Recurring Subscription helpers
# ---------------------------------------------------------------------------

# Statuses Square considers live and billable — member access should be granted.
_SUBSCRIPTION_ACTIVE_STATUSES = {"ACTIVE", "PENDING"}


def get_or_create_member_square_customer(
    acct_num: int,
) -> Tuple[bool, str, Optional[str]]:
    """
    Returns the Square Customer ID for the given member, creating a new
    Square Customer record if one has not been linked yet. Persists the ID
    back to the User row so future calls skip the API round-trip.

    Returns (success, message, customer_id).
    """
    from core.models import User

    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            return False, f"No member found with account number {acct_num}.", None

        # Reuse the stored ID rather than creating a duplicate customer record.
        if user.square_customer_id:
            return True, "Existing Square customer record found.", user.square_customer_id

        client = _get_square_client()
        if not client:
            return (
                False,
                "Square client could not be initialised. Check that the access token is configured.",
                None,
            )

        customer_name = f"{user.first_name} {user.last_name}"
        customer_id = _get_or_create_square_customer(
            client, customer_name, user.email, user.phone or None
        )
        if not customer_id:
            return False, "Could not create Square customer record. Check the API token.", None

        user.square_customer_id = customer_id
        session.add(user)
        session.commit()
        return True, "Square customer record created.", customer_id


def activate_square_subscription(
    acct_num: int,
    plan_variation_id: str,
    timezone: str = "America/Toronto",
) -> Tuple[bool, str]:
    """
    Enrols the member in a Square recurring subscription using invoice-based
    billing. Square emails the member a payment link for each billing cycle.
    Nucleus stores the subscription ID and status for daily polling.

    No card data is passed to or stored in Nucleus at any point.

    Returns (success, message).
    """
    from core.models import User

    if not plan_variation_id:
        return False, "No Plan Variation ID is configured. Set it in Settings > Subscriptions."

    ok, msg, customer_id = get_or_create_member_square_customer(acct_num)
    if not ok:
        return False, msg

    config = get_pos_config()
    if not config.square_location_id:
        return False, "No Location ID configured. Check Settings > Point of Sale."

    client = _get_square_client()
    if not client:
        return (
            False,
            "Square client could not be initialised. Check that the access token is configured.",
        )

    try:
        result = client.subscriptions.create(
            idempotency_key=str(uuid.uuid4()),
            location_id=config.square_location_id,
            plan_variation_id=plan_variation_id,
            customer_id=customer_id,
            # Omitting card_id causes Square to send invoice/payment request emails.
            start_date=datetime.now().date().isoformat(),
            timezone=timezone,
            source={"name": "Nucleus"},
        )
    except Exception as exc:
        return False, f"Square API error: {exc}"

    if result.errors:
        error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
        return False, f"Square returned errors: {error_msg}"

    sub = result.subscription
    with Session(engine) as session:
        user = session.get(User, acct_num)
        if user:
            user.square_subscription_id = sub.id
            user.square_subscription_status = sub.status or "PENDING"
            user.square_subscription_checked_at = datetime.now()
            session.add(user)
            session.commit()

    return (
        True,
        f"Subscription activated (ID: {sub.id}). Square will email the member a payment link.",
    )


def poll_member_subscription(acct_num: int) -> Tuple[bool, str]:
    """
    Fetches the current subscription status from Square for the given member
    and updates the local User record. Does not automatically change the
    member's role — status changes are surfaced to staff for review.

    Returns (success, message).
    """
    from core.models import User

    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            return False, f"No member found with account number {acct_num}."
        if not user.square_subscription_id:
            return False, "This member has no active Square subscription."

        client = _get_square_client()
        if not client:
            return False, "Square client could not be initialised."

        try:
            result = client.subscriptions.get(
                subscription_id=user.square_subscription_id
            )
        except Exception as exc:
            return False, f"Square API error: {exc}"

        if result.errors:
            error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
            return False, f"Square returned errors: {error_msg}"

        sub = result.subscription
        new_status = (sub.status or "UNKNOWN").upper()
        user.square_subscription_status = new_status
        user.square_subscription_checked_at = datetime.now()
        session.add(user)
        session.commit()

        is_active = new_status in _SUBSCRIPTION_ACTIVE_STATUSES
        action = "Access is active." if is_active else f"Access may need review (status: {new_status})."
        return True, f"Subscription status: {new_status}. {action}"


def cancel_square_subscription(acct_num: int) -> Tuple[bool, str]:
    """
    Cancels the Square subscription for the given member and clears the
    subscription ID from the local User record.

    Returns (success, message).
    """
    from core.models import User

    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            return False, f"No member found with account number {acct_num}."
        if not user.square_subscription_id:
            return False, "This member has no active Square subscription to cancel."

        subscription_id = user.square_subscription_id

        client = _get_square_client()
        if not client:
            return False, "Square client could not be initialised."

        try:
            result = client.subscriptions.cancel(subscription_id=subscription_id)
        except Exception as exc:
            return False, f"Square API error: {exc}"

        if result.errors:
            error_msg = "; ".join((e.detail or str(e)) for e in result.errors)
            return False, f"Square returned errors: {error_msg}"

        user.square_subscription_id = None
        user.square_subscription_status = "CANCELLED"
        user.square_subscription_checked_at = datetime.now()
        session.add(user)
        session.commit()

        return True, f"Subscription {subscription_id} cancelled."


def poll_all_active_subscriptions() -> Tuple[int, int]:
    """
    Polls Square for the current subscription status of every member that has
    a subscription ID on file. Intended to be run once daily by a script or
    scheduler. Returns (polled_count, error_count).
    """
    from core.models import User
    from sqlmodel import select as sql_select

    with Session(engine) as session:
        stmt = sql_select(User).where(User.square_subscription_id.is_not(None))
        members = session.exec(stmt).all()

    polled = 0
    errors = 0
    for member in members:
        ok, _ = poll_member_subscription(member.account_number)
        if ok:
            polled += 1
        else:
            errors += 1

    return polled, errors


def get_recent_transactions(limit: int = 50) -> List[SquareTransaction]:
    """Returns the most recent SquareTransaction records, newest first."""
    with Session(engine) as session:
        stmt = (
            select(SquareTransaction)
            .order_by(desc(SquareTransaction.created_at))
            .limit(limit)
        )
        return session.exec(stmt).all()
