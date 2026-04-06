# Business Table Reference — Univest Backend

Authoritative guide for choosing the correct table and understanding column semantics.
Use this before writing any query touching financial, subscription, or user data.

---

## Subscriptions

- For ANY query about subscription revenue, mandate payments, plan pricing, or user subscriptions, use `user_current_subscription` as the primary table.
- Only use `commodity_user_subscription` when the user explicitly asks about commodity (F&O, MCX) product subscriptions.
- Only use `basket_user_subscription` when the user explicitly asks about basket/index portfolio subscriptions.
- All three tables (`user_current_subscription`, `commodity_user_subscription`, `basket_user_subscription`) share the same column structure (amount, mandate_id, plan_id, user_id). The **table name** is the key distinguishing factor — choose based on domain context.
- `subscription_plan_master` contains plan definitions for general PRO plans. `brokerage_subscription_plan_master` contains plans for trading/brokerage-specific plans.

## Monetary Values

- `amount` in `user_current_subscription`, `commodity_user_subscription`, and `basket_user_subscription` is stored as BIGINT and may be in paise (1/100 of a rupee). Verify units against sample data before reporting revenue figures.
- `amount` in `user_transaction_history` is DECIMAL(10,2). Verify whether the value represents rupees or paise before aggregating.
- `amount` in `user_fund_transaction_history` is stored as DOUBLE. Verify units before use.
- `amount` in `user_fund_payout_history` is NUMERIC — treat as rupees unless sample data says otherwise.
- When in doubt, always run a `SELECT MAX(amount), MIN(amount), AVG(amount)` sanity check before reporting a revenue figure.

## Transactions & Fund Flows

- For general payment transactions (deposits into the app wallet, subscription payments, UPI/bank flows): use `user_transaction_history`.
- For fund movements specifically within a user's brokerage/demat account (broker fund add/withdraw): use `user_fund_transaction_history`.
- For brokerage account payout/withdrawal records (money transferred out via Rupeeseed): use `user_fund_payout_history`.
- `payment_type` column: `CR` = credit (money coming in), `DR` = debit (money going out). Both tables use this convention.
- Do NOT mix `user_transaction_history` and `user_fund_transaction_history` in aggregate revenue queries — they represent different flows.

## KYC

- For general/initial KYC document records (PAN, Aadhaar, bank doc): use `user_kyc` (also `user_kycs`).
- For broker-specific KYC (exchange registration, DDPI, F&O enablement): use `user_broker_kyc`.
- For KRA Central KYC Registry records: use `kra_based_kyc`.
- For risk-assessment-based KYC: use `ra_user_kyc`.
- For PAN card standalone verification data: use `user_pan_card_details`.
- For failed PAN verification attempts (Decentro flow): use `pan_verification_failure_log`.

## Orders & Positions

- For current open/executed equity trading orders: use `user_demat_orders`.
- Do NOT use the older `orders` table for active trading data — it is a legacy table and may be stale.
- For a user's current holdings/positions in the broker account: use `user_positions`.
- For cash and margin balance in a trading account: use `user_demat_balance`.
- `user_demat_orders.gtt_order = true` indicates a GTT (Good-Till-Triggered) conditional order — filter these out for regular order analytics unless the query is specifically about GTT.

## Market & Company Data

- For company/stock lookup (name, symbol, ISIN, sector): use `company_master` with `fin_code` as the primary key.
- For sector/industry classification: join `company_master` → `industry_master` on `ind_code`.
- For current stock prices (last traded price, OHLC): use `stock_prices`.
- For historical OHLC at specific intervals: use the appropriate aggregated table — `stock_prices_per_day`, `per_week`, `per_month`, `per_quarter`, `per_year`, `per_half_year`.
- `fin_code` is the universal stock identifier across the platform. Never mix `fin_code` with `scrip_code` — they are different identifiers.

## Support Tickets

- For general app support tickets (non-trading issues): use `support_tickets`.
- For trading/brokerage-specific support tickets: use `broker_support_tickets`.
- `support_tickets.commodity_query` and `customer_call_requests.commodity_query` are boolean flags — use them to filter commodity-related support volume separately.
- Do NOT join `support_chat_history` with `broker_support_chat_history` — they back different ticket systems.

## User Segments & Identity

- `users` is the single source of truth for user identity. All user-facing queries should start here.
- For device/app version tracking: use `user_devices`.
- For bank account details (for payouts): use `user_bank_details`.
- For deleted/offboarded accounts: use `deleted_users` — never delete rows from `users` directly.
- `blacklisted_users` stores platform-banned users. Always LEFT JOIN or exclude these when computing active user metrics.

## Baskets / Portfolio Products

- `uni_baskets` contains product definitions (name, CAGR, methodology, composition).
- `uni_baskets_composition` contains the stock-level holdings for each basket (fin_code, qty, value).
- For user subscription to a basket product: use `basket_user_subscription`, not `uni_baskets`.

## Trade Cards (Social Trading)

- `trade_cards` stores expert recommendations (BUY/SELL/TRACK/HOLD).
- `status` values: `WAITING` (not yet triggered), `HIT` (target hit), `CLOSED` (manually closed), `MISSED` (expired without hitting).
- `trade_cards.created_at` and `expires_at` are stored as LONG (milliseconds since epoch) — convert before display.
- `parent_id` links a modified trade card to its original — filter `parent_id IS NULL` to get original cards only.

## Scheduled Jobs

- `shedlock` is a distributed lock table for Spring ShedLock — do NOT query or modify it for business metrics.

## Notifications

- `nudges` is the older nudge system. `new_nudge` is the current implementation — prefer `new_nudge` for active notification analytics.
- `whatsapp_campaigns` tracks campaign-level metadata; `whatsapp_message_details` tracks individual message delivery status.

## IPO

- For IPO product definitions: use `ipo_master`.
- For lot size and pricing: use `ipo_lot_details`.
- For financial data at IPO time: use `ipo_financial_details`.
- All IPO tables are read-only reference data — do not write to them from application flows.

## Lending (Faircent)

- `faircent_leads` stores user leads for the lending product.
- `faircent_investment_details` stores individual investments. `withdrawal_requested` boolean indicates a pending withdrawal.
- `faircent_plans` defines the plan options. `user_faircent_plans` stores user selections.
- Use `faircent_payment_history` (not `user_transaction_history`) for Faircent-specific payment records.

## Timestamps & Timezones

- All timestamps are in **Asia/Kolkata (IST)** unless otherwise noted.
- Most tables use `TIMESTAMP` (without timezone). A few use `BIGINT` milliseconds (notably `trade_cards`).
- When filtering by date, always apply IST timezone conversion to avoid off-by-one-day errors in midnight-boundary queries.
