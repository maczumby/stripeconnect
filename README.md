# Stripe Connect Multi-Creator Platform

A complete implementation of Stripe Connect that allows multiple creators to have their own Stripe accounts while you automatically collect application fees on every payment.

## What This Does

Instead of one Stripe account (yours), each creator gets their own Stripe account. You take a percentage of every payment automatically.

### The Flow

1. **Creator Onboarding** → Creator signs up, you create their Stripe Express account
2. **Stripe Handles KYC** → Stripe's hosted form collects their info (identity, bank, etc.)
3. **Creator Accepts Payments** → Customers pay the creator directly
4. **You Get Your Cut** → Application fees are automatically deducted
5. **Matrix Invites** → Customers are automatically invited to your Matrix space

## Architecture

```
Customer Payment → Creator's Stripe Account (90%) → You get 10% fee automatically
                ↓
           Webhook fires
                ↓
    Customer invited to Matrix Space
```

## What You Build vs What Stripe Builds

### You Build (This Code)
- ✅ Creator onboarding endpoint (`POST /connect/onboard`)
- ✅ Return URL handler (creator finishes onboarding)
- ✅ Refresh URL handler (onboarding link expires)
- ✅ Connect webhook endpoint (events on creator accounts)
- ✅ Checkout session creation with application fees
- ✅ Creator management (list, status, login links)
- ✅ Google Sheets integration for creator data

### Stripe Builds (Hosted by Stripe)
- ✅ Onboarding form (collects business info, identity, bank)
- ✅ Identity verification
- ✅ Bank account collection
- ✅ Creator Express Dashboard (earnings, payouts, etc.)
- ✅ Payout handling

## Setup

### Prerequisites

1. **Stripe Account** with Connect enabled
2. **Matrix Bot** with space admin permissions
3. **Google Cloud Project** with Sheets API enabled

### 1. Stripe Dashboard Setup

Go through these steps in your Stripe Dashboard:

#### Enable Connect
1. Go to **Settings → Connect**
2. Complete your platform profile:
   - Business name
   - Support email
   - Branding (logo, colors)
3. Select **"Platform"** business model
4. Select **"Application fees"** monetization
5. Customize branding (shows on Stripe's hosted onboarding)

#### Set Up Webhooks
1. Go to **Developers → Webhooks → Add endpoint**
2. URL: `https://your-app.railway.app/webhook/stripe/connect`
3. Listen to: **"Events on Connected accounts"**
4. Select events:
   - `account.updated`
   - `checkout.session.completed`
   - `customer.subscription.deleted`
5. Copy the webhook secret (starts with `whsec_`)

### 2. Google Sheets Setup

Follow the detailed guide in [GOOGLE_SHEETS_SETUP.md](./GOOGLE_SHEETS_SETUP.md)

Quick summary:
1. Create Google Cloud project
2. Enable Sheets API and Drive API
3. Create service account and download JSON key
4. Create a Google Sheet for creators
5. Share the sheet with service account email

### 3. Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill in all the values:

```bash
# Matrix
MATRIX_SERVER_URL=https://api.filament.dm
MATRIX_BOT_USERNAME=@yourbot:filament.dm
MATRIX_BOT_PASSWORD=your_bot_password
MATRIX_SPACE_ID=!yourspaceid:filament.dm

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # Not used here but keep it
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_...  # From step 1 above

# Admin
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_JSON='{"type":"service_account",...}'
GOOGLE_SHEETS_SPREADSHEET_ID=1abc...xyz

# Server
PORT=3001
BASE_URL=http://localhost:3001  # Change for production
```

### 4. Install Dependencies

```bash
cd stripeconnect
pip install -r requirements.txt
```

### 5. Run the Server

```bash
python app.py
```

You should see:
```
✅ Google Sheets connected successfully
✅ Successfully logged in as @yourbot:filament.dm
🚀 Matrix LaunchPass - Stripe Connect v1.0
   Server running on: http://localhost:3001
```

## Testing the Full Flow

### Step 1: Onboard a Test Creator

```bash
curl -X POST http://localhost:3001/connect/onboard \
  -u admin:your_password \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "test_creator_1",
    "email": "creator@example.com",
    "name": "Test Creator"
  }'
```

Response:
```json
{
  "success": true,
  "onboarding_url": "https://connect.stripe.com/setup/...",
  "account_id": "acct_xyz",
  "creator_id": "test_creator_1"
}
```

### Step 2: Complete Onboarding

1. Open the `onboarding_url` in a browser
2. Fill out the Stripe form (use test data)
3. For test mode, use:
   - Phone: Any valid format
   - SSN: `000-00-0000` (test SSN)
   - Bank account: Use test routing/account numbers
4. Submit the form

Stripe will redirect to: `http://localhost:3001/connect/return?account_id=acct_xyz`

You'll see:
```json
{
  "success": true,
  "status": "complete",
  "message": "Onboarding complete! You can now accept payments.",
  "charges_enabled": true
}
```

### Step 3: Check Google Sheets

Open your Google Sheet. You should see a new row:

| creator_id | stripe_account_id | email | name | onboarding_complete | charges_enabled | loops | created_at | updated_at |
|------------|-------------------|-------|------|---------------------|-----------------|-------|------------|------------|
| test_creator_1 | acct_xyz | creator@example.com | Test Creator | TRUE | TRUE | | 2026-01-18... | 2026-01-18... |

### Step 4: Create a Test Product (in Stripe Dashboard)

Since the creator needs something to sell:

1. Go to Stripe Dashboard → Products
2. Create a new product
3. Add a recurring price (e.g., $10/month)
4. Copy the price ID (starts with `price_`)

Or use the Stripe API:
```bash
curl https://api.stripe.com/v1/products \
  -u sk_test_...: \
  -d name="Premium Membership" \
  -d description="Access to premium content"

curl https://api.stripe.com/v1/prices \
  -u sk_test_...: \
  -d product=prod_xyz \
  -d unit_amount=1000 \
  -d currency=usd \
  -d "recurring[interval]"=month
```

### Step 5: Create Checkout Session for Creator

```bash
curl -X POST http://localhost:3001/connect/create-checkout \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "test_creator_1",
    "price_id": "price_xyz",
    "application_fee_percent": 10,
    "success_url": "http://localhost:3001/success",
    "cancel_url": "http://localhost:3001/cancel"
  }'
```

Response:
```json
{
  "success": true,
  "session_id": "cs_test_...",
  "url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "creator_id": "test_creator_1",
  "application_fee_percent": 10
}
```

### Step 6: Complete Test Payment

1. Open the checkout `url` in a browser
2. Use Stripe test card: `4242 4242 4242 4242`
3. Use any future expiry date and CVC
4. Enter a test email: `subscriber@example.com`
5. Complete the payment

### Step 7: Verify Webhook Received

Check your server logs. You should see:
```
📥 Connect Event: checkout.session.completed
   Connected Account: acct_xyz
   Customer Email: subscriber@example.com
✅ Successfully sent email invite to subscriber@example.com
```

### Step 8: Check Matrix

The customer should receive an email invite to join your Matrix space!

### Step 9: Verify Application Fee

1. Go to Stripe Dashboard → Payments
2. Find the payment you just made
3. Click on it
4. You should see:
   - **Gross amount:** $10.00
   - **Application fee:** $1.00 (10%)
   - **Net to creator:** $9.00

The creator gets $9.00, you automatically keep $1.00.

## API Endpoints

### Creator Onboarding

```bash
POST /connect/onboard
Authorization: Basic admin:password
Content-Type: application/json

{
  "creator_id": "creator_123",
  "email": "creator@example.com",
  "name": "Creator Name"
}
```

Returns onboarding URL for creator to complete their setup.

### Create Checkout for Creator

```bash
POST /connect/create-checkout
Content-Type: application/json

{
  "creator_id": "creator_123",
  "price_id": "price_xyz",
  "application_fee_percent": 10,
  "success_url": "https://yoursite.com/success",
  "cancel_url": "https://yoursite.com/cancel"
}
```

Creates a Stripe Checkout session on the creator's account with your platform fee.

### List All Creators

```bash
GET /creators
Authorization: Basic admin:password
```

Returns all creators with their onboarding status.

### Get Creator Status

```bash
GET /creators/{creator_id}
Authorization: Basic admin:password
```

Returns detailed status for a specific creator.

### Generate Creator Login Link

```bash
POST /creators/{creator_id}/generate-login-link
Authorization: Basic admin:password
```

Generates a login link for the creator to access their Express Dashboard.

### Webhooks

```
POST /webhook/stripe/connect
```

Receives events from creator accounts (not your platform account).

## Data Schema (Google Sheets)

The "Creators" worksheet has these columns:

| Column | Type | Description |
|--------|------|-------------|
| creator_id | String | Your internal creator ID |
| stripe_account_id | String | Stripe Connect account ID (acct_xyz) |
| email | String | Creator's email |
| name | String | Creator's name |
| onboarding_complete | Boolean | TRUE if finished onboarding |
| charges_enabled | Boolean | TRUE if can accept payments |
| loops | String | Comma-separated Matrix room IDs |
| created_at | ISO DateTime | When creator was added |
| updated_at | ISO DateTime | Last update time |

## Managing Creators

### In Google Sheets

You can directly edit the sheet to:
- View all creators at a glance
- Manually update status
- Add Matrix room IDs to the "loops" column
- See who's completed onboarding

### Via API

Use the `/creators` endpoint to programmatically manage creators.

### Creator Dashboard Access

Creators can view their earnings and manage payouts in their Stripe Express Dashboard. Generate a login link for them:

```bash
curl -X POST http://localhost:3001/creators/test_creator_1/generate-login-link \
  -u admin:password
```

## Webhook Events Handled

### `account.updated`
Fires when creator updates their account or completes onboarding. Updates Google Sheets with latest status.

### `checkout.session.completed`
Fires when a customer completes payment. Invites customer to Matrix space via email.

### `customer.subscription.deleted`
Fires when a subscription is cancelled. (TODO: Implement Matrix kick)

## Build Order / Implementation Checklist

- [x] 1. Creator onboarding endpoint
- [x] 2. Return/refresh URL endpoints
- [x] 3. Connect webhook endpoint
- [x] 4. Modify checkout to use stripe_account
- [x] 5. Google Sheets storage system
- [x] 6. Creator management endpoints
- [x] 7. Setup documentation
- [ ] 8. Test full flow (your turn!)
- [ ] 9. Implement subscription cancellation (Matrix kick)
- [ ] 10. Deploy to production

## Production Deployment

### Update Environment Variables

1. Change `BASE_URL` to your production domain
2. Update webhook URL in Stripe Dashboard
3. Use production Stripe keys (starts with `sk_live_`)
4. Use strong admin password

### Security Checklist

- [ ] Never commit `.env` to Git
- [ ] Use production Stripe API keys
- [ ] Verify webhook signatures
- [ ] Use HTTPS for all webhooks
- [ ] Restrict admin endpoints with strong auth
- [ ] Service account JSON is secured
- [ ] Google Sheet is only shared with service account

## Troubleshooting

### Creator onboarding link expired
The creator will be redirected to the refresh URL, which generates a new link automatically.

### Webhook not received
1. Check Stripe Dashboard → Webhooks → View logs
2. Verify webhook secret in `.env`
3. Make sure you're listening to "Events on Connected accounts"

### Google Sheets not updating
1. Check service account has "Editor" access to the sheet
2. Verify credentials JSON is valid
3. Check server logs for errors

### Application fee not showing
1. Make sure you passed `application_fee_percent` in checkout creation
2. Verify you're using `stripe_account` parameter
3. Check Stripe Dashboard → Connect → Settings (must have Application Fees enabled)

## Next Steps

1. Complete the test flow above
2. Integrate checkout creation into your frontend
3. Add creator signup flow to your app
4. Implement subscription cancellation (kick from Matrix)
5. Add creator management UI
6. Deploy to production

## Need Help?

- [Stripe Connect Docs](https://stripe.com/docs/connect)
- [Stripe Connect Express Accounts](https://stripe.com/docs/connect/express-accounts)
- [Application Fees](https://stripe.com/docs/connect/direct-charges#collecting-fees)
- [Connect Webhooks](https://stripe.com/docs/connect/webhooks)

## Differences from Your Original Integration

Your original code (`/app.py`):
- Single Stripe account (yours)
- Direct payment to you
- Simple webhook handling

This new code (`/stripeconnect/app.py`):
- Multiple creator accounts
- Payments go to creators (you get a fee)
- Connect-specific webhook handling
- Creator onboarding flow
- Google Sheets for easy management

Both can run side-by-side on different ports!
