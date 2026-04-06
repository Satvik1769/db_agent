## Subscription and Revenue Tables
- For ANY query about subscription revenue, mandate payments, plan pricing, or user subscriptions, use `user_current_subscription` as the primary table.
- Only use `commodity_user_subscription` when the user explicitly asks about commodity (F&O, MCX) product subscriptions.
- Both tables have nearly identical columns (amount, mandate_id, plan_id, user_id). The table name is the key distinguishing factor — choose based on domain context.

## Monetary Values
- `amount` columns in subscription tables may be stored in paise (1/100 of a rupee). Verify units against sample data before reporting revenue figures.
