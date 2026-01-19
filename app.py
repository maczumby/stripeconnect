import os
import re
import secrets
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse, RedirectResponse
import stripe
from mautrix.client import Client
from mautrix.types import TextMessageEventContent, MessageType
from mautrix.errors import MatrixError

# Load environment variables
load_dotenv()

# ============================================
# CONFIGURATION
# ============================================

class Config:
    def __init__(self):
        self.matrix = {
            "server_url": os.getenv("MATRIX_SERVER_URL"),
            "bot_username": os.getenv("MATRIX_BOT_USERNAME"),
            "bot_password": os.getenv("MATRIX_BOT_PASSWORD"),
            "space_id": os.getenv("MATRIX_SPACE_ID"),
        }
        self.stripe = {
            "secret_key": os.getenv("STRIPE_SECRET_KEY"),
            "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET"),
            "connect_webhook_secret": os.getenv("STRIPE_CONNECT_WEBHOOK_SECRET"),
        }
        self.admin = {
            "username": os.getenv("ADMIN_USERNAME"),
            "password": os.getenv("ADMIN_PASSWORD"),
        }
        self.port = int(os.getenv("PORT", "3001"))
        # Base URL for your app (needed for redirect URLs)
        self.base_url = os.getenv("BASE_URL", f"http://localhost:{self.port}")

config = Config()

# Initialize Stripe
stripe.api_key = config.stripe["secret_key"]

# Initialize FastAPI
app = FastAPI(title="Matrix LaunchPass - Stripe Connect", version="1.0.0")

# Matrix client (initialized on startup)
matrix_client: Optional[Client] = None

# HTTP Basic Auth security
security = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials for protected endpoints"""
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        config.admin["username"].encode("utf8") if config.admin["username"] else b""
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        config.admin["password"].encode("utf8") if config.admin["password"] else b""
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ============================================
# GOOGLE SHEETS STORAGE FUNCTIONS
# ============================================

import json
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets configuration
GOOGLE_SHEETS_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Initialize Google Sheets client
sheets_client = None
creators_worksheet = None

def init_google_sheets():
    """Initialize Google Sheets connection"""
    global sheets_client, creators_worksheet

    try:
        # Load service account credentials
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

        if not creds_json or not spreadsheet_id:
            print("⚠️  Google Sheets credentials not configured. Using fallback storage.")
            return False

        # Parse credentials from environment variable
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=GOOGLE_SHEETS_SCOPES)

        # Authorize and open spreadsheet
        sheets_client = gspread.authorize(creds)
        spreadsheet = sheets_client.open_by_key(spreadsheet_id)

        # Get or create the "Creators" worksheet
        try:
            creators_worksheet = spreadsheet.worksheet("Creators")
        except gspread.WorksheetNotFound:
            # Create worksheet with headers
            creators_worksheet = spreadsheet.add_worksheet(title="Creators", rows=100, cols=10)
            creators_worksheet.append_row([
                "creator_id",
                "stripe_account_id",
                "email",
                "name",
                "onboarding_complete",
                "charges_enabled",
                "loops",
                "created_at",
                "updated_at"
            ])

        print("✅ Google Sheets connected successfully")
        return True

    except Exception as e:
        print(f"❌ Failed to initialize Google Sheets: {e}")
        return False

def add_creator(creator_id: str, stripe_account_id: str, email: str, name: str = None):
    """Add a new creator account to Google Sheets"""
    try:
        from datetime import datetime
        timestamp = datetime.utcnow().isoformat()

        # Add row to sheet
        creators_worksheet.append_row([
            creator_id,
            stripe_account_id,
            email,
            name or "",
            "FALSE",  # onboarding_complete
            "FALSE",  # charges_enabled
            "",       # loops (empty for now)
            timestamp,
            timestamp
        ])

        print(f"✅ Added creator to Google Sheets: {creator_id} → {stripe_account_id}")

    except Exception as e:
        print(f"❌ Error adding creator to Google Sheets: {e}")
        raise

def update_creator(creator_id: str, updates: Dict[str, Any]):
    """Update creator account information in Google Sheets"""
    try:
        from datetime import datetime

        # Find the row with this creator_id
        cell = creators_worksheet.find(creator_id)
        if not cell:
            print(f"⚠️  Creator {creator_id} not found in sheet")
            return False

        row_num = cell.row

        # Get current row data
        row_data = creators_worksheet.row_values(row_num)

        # Update fields (column indices based on our header)
        # Headers: creator_id, stripe_account_id, email, name, onboarding_complete, charges_enabled, loops, created_at, updated_at
        if "onboarding_complete" in updates:
            creators_worksheet.update_cell(row_num, 5, "TRUE" if updates["onboarding_complete"] else "FALSE")

        if "charges_enabled" in updates:
            creators_worksheet.update_cell(row_num, 6, "TRUE" if updates["charges_enabled"] else "FALSE")

        if "loops" in updates:
            loops_str = ",".join(updates["loops"]) if isinstance(updates["loops"], list) else str(updates["loops"])
            creators_worksheet.update_cell(row_num, 7, loops_str)

        # Update timestamp
        creators_worksheet.update_cell(row_num, 9, datetime.utcnow().isoformat())

        print(f"✅ Updated creator in Google Sheets: {creator_id}")
        return True

    except Exception as e:
        print(f"❌ Error updating creator in Google Sheets: {e}")
        return False

def get_creator(creator_id: str) -> Optional[Dict[str, Any]]:
    """Get creator account by ID from Google Sheets"""
    try:
        # Find the row with this creator_id
        cell = creators_worksheet.find(creator_id)
        if not cell:
            return None

        row_num = cell.row
        row_data = creators_worksheet.row_values(row_num)

        # Parse row data into dict
        # Headers: creator_id, stripe_account_id, email, name, onboarding_complete, charges_enabled, loops, created_at, updated_at
        loops_str = row_data[6] if len(row_data) > 6 else ""
        loops = [l.strip() for l in loops_str.split(",") if l.strip()] if loops_str else []

        return {
            "stripe_account_id": row_data[1],
            "email": row_data[2],
            "name": row_data[3] if len(row_data) > 3 else None,
            "onboarding_complete": row_data[4].upper() == "TRUE" if len(row_data) > 4 else False,
            "charges_enabled": row_data[5].upper() == "TRUE" if len(row_data) > 5 else False,
            "loops": loops,
        }

    except Exception as e:
        print(f"❌ Error getting creator from Google Sheets: {e}")
        return None

def get_creator_by_account(stripe_account_id: str) -> Optional[tuple[str, Dict[str, Any]]]:
    """Get creator by their Stripe account ID from Google Sheets"""
    try:
        # Find the cell with this stripe_account_id (column 2)
        cell = creators_worksheet.find(stripe_account_id, in_column=2)
        if not cell:
            return None

        row_num = cell.row
        row_data = creators_worksheet.row_values(row_num)

        # Parse row data
        creator_id = row_data[0]
        loops_str = row_data[6] if len(row_data) > 6 else ""
        loops = [l.strip() for l in loops_str.split(",") if l.strip()] if loops_str else []

        creator_info = {
            "stripe_account_id": row_data[1],
            "email": row_data[2],
            "name": row_data[3] if len(row_data) > 3 else None,
            "onboarding_complete": row_data[4].upper() == "TRUE" if len(row_data) > 4 else False,
            "charges_enabled": row_data[5].upper() == "TRUE" if len(row_data) > 5 else False,
            "loops": loops,
        }

        return (creator_id, creator_info)

    except Exception as e:
        print(f"❌ Error getting creator by account from Google Sheets: {e}")
        return None

def load_creators() -> Dict[str, Any]:
    """Load all creators from Google Sheets"""
    try:
        all_records = creators_worksheet.get_all_records()

        creators_dict = {}
        for record in all_records:
            creator_id = record.get("creator_id")
            if creator_id:
                loops_str = record.get("loops", "")
                loops = [l.strip() for l in loops_str.split(",") if l.strip()] if loops_str else []

                creators_dict[creator_id] = {
                    "stripe_account_id": record.get("stripe_account_id"),
                    "email": record.get("email"),
                    "name": record.get("name"),
                    "onboarding_complete": str(record.get("onboarding_complete", "")).upper() == "TRUE",
                    "charges_enabled": str(record.get("charges_enabled", "")).upper() == "TRUE",
                    "loops": loops,
                }

        return {"creators": creators_dict}

    except Exception as e:
        print(f"❌ Error loading creators from Google Sheets: {e}")
        return {"creators": {}}

# ============================================
# MATRIX FUNCTIONS
# ============================================

async def login_to_matrix():
    """Login to Matrix and initialize client"""
    global matrix_client

    print(f"\n🔐 Logging into Matrix as {config.matrix['bot_username']}...")

    try:
        # Create client
        matrix_client = Client(base_url=config.matrix["server_url"])

        # Login with password
        response = await matrix_client.login(
            identifier=config.matrix["bot_username"],
            login_type="m.login.password",
            password=config.matrix["bot_password"]
        )

        print(f"✅ Successfully logged in as {response.user_id}")
        print(f"   Device ID: {response.device_id or 'N/A'}")

        return {"success": True, "user_id": response.user_id}

    except Exception as err:
        print(f"❌ Matrix login exception: {str(err)}")
        raise err


async def invite_to_matrix(email: str) -> Dict[str, Any]:
    """Invite a user to the Matrix Space by email using standard Matrix client API"""
    print(f"\n📨 Inviting {email} to Space via email...")

    try:
        id_server = "sydent.filament.dm"
        space_id = config.matrix["space_id"]

        # Step 1: Get OpenID token for identity server authentication
        print(f"   Getting OpenID token...")
        from urllib.parse import quote
        user_id_str = str(matrix_client.mxid)
        encoded_user_id = quote(user_id_str, safe='')

        openid_response = await matrix_client.api.request(
            method="POST",
            path=f"/_matrix/client/v3/user/{encoded_user_id}/openid/request_token",
            content={}
        )

        openid_token = openid_response.get("access_token")
        if not openid_token:
            raise Exception("Failed to get OpenID token")

        print(f"   ✓ Got OpenID token")

        # Step 2: Register with sydent to get identity server access token
        print(f"   Registering with sydent...")
        import aiohttp
        async with aiohttp.ClientSession() as session:
            register_url = f"https://{id_server}/_matrix/identity/v2/account/register"
            register_data = {
                "access_token": openid_token,
                "expires_in": openid_response.get("expires_in", 3600),
                "matrix_server_name": openid_response.get("matrix_server_name", "api.filament.dm"),
                "token_type": openid_response.get("token_type", "Bearer")
            }

            async with session.post(register_url, json=register_data) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Failed to register with identity server: {resp.status} - {error_text}")

                sydent_response = await resp.json()
                sydent_token = sydent_response.get("token")

                if not sydent_token:
                    raise Exception("No token returned from identity server")

        print(f"   ✓ Registered with sydent")

        # Step 3: Call Synapse's standard room invite endpoint
        print(f"   Calling Synapse's room invite API...")

        invite_data = {
            "id_server": id_server,
            "id_access_token": sydent_token,
            "medium": "email",
            "address": email
        }

        await matrix_client.api.request(
            method="POST",
            path=f"/_matrix/client/v3/rooms/{space_id}/invite",
            content=invite_data
        )

        print(f"✅ Successfully sent email invite to {email}")
        return {"success": True}

    except MatrixError as err:
        # Check for "already in room" error
        if err.errcode == "M_FORBIDDEN" and "already" in str(err).lower():
            print(f"ℹ️  {email} is already in the Space")
            return {"success": True, "already_member": True}

        print(f"❌ Matrix invite failed: {err.errcode} - {err.message}")
        return {
            "success": False,
            "error": {"errcode": err.errcode, "error": err.message}
        }

    except Exception as err:
        print(f"❌ Matrix invite exception: {str(err)}")
        return {"success": False, "error": str(err)}


# ============================================
# HELPER FUNCTIONS
# ============================================

def is_valid_email(email: Optional[str]) -> bool:
    """Validate email format"""
    if not email:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


# ============================================
# STRIPE CONNECT ENDPOINTS
# ============================================

@app.post("/connect/onboard")
async def creator_onboarding(request: Request, username: str = Depends(verify_admin)):
    """
    NEW THING 1: Creator Onboarding Endpoint

    Create a Stripe Connect Express account for a creator and get onboarding URL.

    POST body:
    {
        "creator_id": "creator_123",
        "email": "creator@example.com",
        "name": "Creator Name"
    }

    Returns:
    {
        "success": true,
        "onboarding_url": "https://connect.stripe.com/setup/...",
        "account_id": "acct_xyz",
        "creator_id": "creator_123"
    }
    """
    try:
        data = await request.json()
        creator_id = data.get("creator_id")
        email = data.get("email")
        name = data.get("name")

        if not creator_id or not email:
            raise HTTPException(status_code=400, detail="creator_id and email are required")

        if not is_valid_email(email):
            raise HTTPException(status_code=400, detail="Invalid email format")

        # Check if creator already exists
        existing = get_creator(creator_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Creator {creator_id} already exists with account {existing['stripe_account_id']}"
            )

        print(f"\n🎨 Creating Stripe Connect account for {creator_id}...")

        # Step 1: Create Express account
        account = stripe.Account.create(
            type="express",
            email=email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            business_type="individual",
            metadata={
                "creator_id": creator_id,
            }
        )

        print(f"✅ Created Express account: {account.id}")

        # Step 2: Create AccountLink for onboarding
        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{config.base_url}/connect/refresh?account_id={account.id}",
            return_url=f"{config.base_url}/connect/return?account_id={account.id}",
            type="account_onboarding",
        )

        print(f"✅ Generated onboarding URL")

        # Step 3: Save to our database
        add_creator(creator_id, account.id, email, name)

        return {
            "success": True,
            "onboarding_url": account_link.url,
            "account_id": account.id,
            "creator_id": creator_id,
            "expires_at": account_link.expires_at
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating creator account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connect/return")
async def onboarding_return(account_id: str):
    """
    NEW THING 2: Return URL Endpoint

    Stripe redirects creators here after they complete (or exit) onboarding.
    Check their account status and show appropriate message.
    """
    try:
        print(f"\n🔙 Creator returned from onboarding: {account_id}")

        # Look up the creator
        creator_data = get_creator_by_account(account_id)
        if not creator_data:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Creator account not found"}
            )

        creator_id, creator_info = creator_data

        # Retrieve account status from Stripe
        account = stripe.Account.retrieve(account_id)

        charges_enabled = account.charges_enabled
        details_submitted = account.details_submitted

        print(f"   Charges enabled: {charges_enabled}")
        print(f"   Details submitted: {details_submitted}")

        # Update our database
        update_creator(creator_id, {
            "onboarding_complete": details_submitted,
            "charges_enabled": charges_enabled,
        })

        if charges_enabled:
            print(f"✅ Creator {creator_id} is ready to accept payments!")
            return {
                "success": True,
                "status": "complete",
                "message": "Onboarding complete! You can now accept payments.",
                "creator_id": creator_id,
                "account_id": account_id,
                "charges_enabled": True
            }
        else:
            print(f"⚠️  Creator {creator_id} hasn't finished onboarding")
            # Generate a new onboarding link
            account_link = stripe.AccountLink.create(
                account=account_id,
                refresh_url=f"{config.base_url}/connect/refresh?account_id={account_id}",
                return_url=f"{config.base_url}/connect/return?account_id={account_id}",
                type="account_onboarding",
            )

            return {
                "success": False,
                "status": "incomplete",
                "message": "Please complete your onboarding to start accepting payments.",
                "creator_id": creator_id,
                "account_id": account_id,
                "charges_enabled": False,
                "retry_url": account_link.url
            }

    except Exception as e:
        print(f"❌ Error processing return: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connect/refresh")
async def onboarding_refresh(account_id: str):
    """
    NEW THING 3: Refresh URL Endpoint

    If the onboarding link expires, Stripe sends creators here.
    Generate a new AccountLink and redirect them back to Stripe.
    """
    try:
        print(f"\n🔄 Refreshing onboarding link for: {account_id}")

        # Generate new AccountLink
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{config.base_url}/connect/refresh?account_id={account_id}",
            return_url=f"{config.base_url}/connect/return?account_id={account_id}",
            type="account_onboarding",
        )

        print(f"✅ Generated new onboarding URL")

        # Redirect them to the new onboarding URL
        return RedirectResponse(url=account_link.url)

    except Exception as e:
        print(f"❌ Error refreshing link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/stripe/connect")
async def stripe_connect_webhook(request: Request):
    """
    NEW THING 4: Connect Webhook Endpoint

    Handle events from CREATOR accounts (not your platform account).
    This webhook receives events about:
    - account.updated (when creator finishes onboarding)
    - checkout.session.completed (when subscriber pays a creator)
    - customer.subscription.deleted (when subscriber cancels)
    """
    # Get raw body for signature verification
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Verify webhook signature
    try:
        event = stripe.Webhook.construct_event(
            payload=body,
            sig_header=sig_header,
            secret=config.stripe["connect_webhook_secret"]
        )
    except ValueError as e:
        print(f"❌ Invalid payload: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
    except stripe.error.SignatureVerificationError as e:
        print(f"❌ Invalid signature: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")

    print(f"\n{'=' * 50}")
    print(f"📥 Connect Event: {event['type']}")
    print(f"{'=' * 50}")

    # Get the connected account ID
    connected_account_id = event.get("account")
    if connected_account_id:
        print(f"   Connected Account: {connected_account_id}")

    # Handle account.updated
    if event["type"] == "account.updated":
        account = event["data"]["object"]
        account_id = account["id"]

        print(f"\n📋 Account Updated: {account_id}")
        print(f"   Charges enabled: {account.get('charges_enabled')}")
        print(f"   Details submitted: {account.get('details_submitted')}")

        # Update our database
        creator_data = get_creator_by_account(account_id)
        if creator_data:
            creator_id, _ = creator_data
            update_creator(creator_id, {
                "onboarding_complete": account.get("details_submitted", False),
                "charges_enabled": account.get("charges_enabled", False),
            })
            print(f"✅ Updated creator {creator_id} status")

    # Handle checkout.session.completed
    elif event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        connected_account = event.get("account")

        customer_id = session.get('customer')
        print(f"\n📋 Checkout Session (Creator Account):")
        print(f"   Customer ID: {customer_id}")
        print(f"   Creator Account: {connected_account}")
        print(f"   Session Email: {session.get('customer_email')}")

        # Get customer email
        customer_email = session.get('customer_email')

        if not customer_email and customer_id:
            print(f"   Fetching email from customer object...")
            try:
                # IMPORTANT: Retrieve from the connected account
                customer = stripe.Customer.retrieve(
                    customer_id,
                    stripe_account=connected_account
                )
                customer_email = customer.email
                print(f"   ✓ Found email: {customer_email}")
            except Exception as e:
                print(f"   ❌ Failed to fetch customer: {e}")

        if not customer_email:
            print(f"\n❌ No customer email found!")
            return {"received": True, "error": "No customer email found"}

        print(f"\n🔍 Customer Email: {customer_email}")

        # Validate email
        if not is_valid_email(customer_email):
            print(f"\n❌ Invalid email format: {customer_email}")
            return {"received": True, "error": "Invalid email format"}

        # Send Matrix invite
        result = await invite_to_matrix(customer_email)

        if result["success"]:
            print(f"\n🎉 SUCCESS! Email invite sent to {customer_email}!")
            print(f"   They will receive an email to join the Matrix space.")
        else:
            print(f"\n⚠️  Invite failed, but webhook processed.")

    # Handle customer.subscription.deleted
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        connected_account = event.get("account")

        customer_id = subscription.get('customer')
        print(f"\n📋 Subscription Cancelled (Creator Account):")
        print(f"   Customer ID: {customer_id}")
        print(f"   Creator Account: {connected_account}")
        print(f"   Subscription ID: {subscription.get('id')}")

        # TODO: Implement kick from Matrix space
        # For now, just log it
        print(f"\n⚠️  TODO: Implement Matrix kick for customer {customer_id}")

    # Always return 200 to Stripe
    return {"received": True}


@app.post("/connect/create-checkout")
async def create_checkout_for_creator(request: Request):
    """
    MODIFIED EXISTING: Create checkout session for a creator's product

    This is how you create a payment that goes to a creator's account
    with your platform taking an application fee.

    POST body:
    {
        "creator_id": "creator_123",
        "price_id": "price_xyz",
        "application_fee_percent": 10,
        "success_url": "https://...",
        "cancel_url": "https://..."
    }
    """
    try:
        data = await request.json()
        creator_id = data.get("creator_id")
        price_id = data.get("price_id")
        application_fee_percent = data.get("application_fee_percent", 10)
        success_url = data.get("success_url")
        cancel_url = data.get("cancel_url")

        if not creator_id or not price_id:
            raise HTTPException(status_code=400, detail="creator_id and price_id are required")

        # Get creator's Stripe account
        creator = get_creator(creator_id)
        if not creator:
            raise HTTPException(status_code=404, detail=f"Creator {creator_id} not found")

        if not creator.get("charges_enabled"):
            raise HTTPException(
                status_code=400,
                detail=f"Creator {creator_id} hasn't completed onboarding yet"
            )

        stripe_account_id = creator["stripe_account_id"]

        print(f"\n💳 Creating checkout for creator {creator_id} ({stripe_account_id})...")

        # Create checkout session on the creator's account with platform fee
        session = stripe.checkout.Session.create(
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=success_url or f"{config.base_url}/success",
            cancel_url=cancel_url or f"{config.base_url}/cancel",
            # KEY PARAMETERS FOR STRIPE CONNECT:
            stripe_account=stripe_account_id,  # Creator's account
            subscription_data={
                "application_fee_percent": application_fee_percent,  # Your cut
            },
        )

        print(f"✅ Created checkout session: {session.id}")
        print(f"   URL: {session.url}")
        print(f"   Application fee: {application_fee_percent}%")

        return {
            "success": True,
            "session_id": session.id,
            "url": session.url,
            "creator_id": creator_id,
            "stripe_account": stripe_account_id,
            "application_fee_percent": application_fee_percent
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating checkout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CREATOR MANAGEMENT ENDPOINTS
# ============================================

@app.get("/creators")
async def list_creators(username: str = Depends(verify_admin)):
    """List all creators and their onboarding status"""
    try:
        data = load_creators()
        creators_list = []

        for creator_id, info in data["creators"].items():
            # Get latest account status from Stripe
            try:
                account = stripe.Account.retrieve(info["stripe_account_id"])
                creators_list.append({
                    "creator_id": creator_id,
                    "stripe_account_id": info["stripe_account_id"],
                    "email": info["email"],
                    "name": info.get("name"),
                    "onboarding_complete": account.details_submitted,
                    "charges_enabled": account.charges_enabled,
                    "payouts_enabled": account.payouts_enabled,
                    "loops": info.get("loops", []),
                })
            except Exception as e:
                print(f"⚠️  Failed to fetch account {info['stripe_account_id']}: {e}")
                creators_list.append({
                    "creator_id": creator_id,
                    "stripe_account_id": info["stripe_account_id"],
                    "email": info["email"],
                    "name": info.get("name"),
                    "error": str(e),
                    "loops": info.get("loops", []),
                })

        return {
            "count": len(creators_list),
            "creators": creators_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/creators/{creator_id}")
async def get_creator_status(creator_id: str, username: str = Depends(verify_admin)):
    """Get detailed status for a specific creator"""
    try:
        creator = get_creator(creator_id)
        if not creator:
            raise HTTPException(status_code=404, detail=f"Creator {creator_id} not found")

        # Get latest account info from Stripe
        account = stripe.Account.retrieve(creator["stripe_account_id"])

        return {
            "creator_id": creator_id,
            "stripe_account_id": creator["stripe_account_id"],
            "email": creator["email"],
            "name": creator.get("name"),
            "onboarding_complete": account.details_submitted,
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
            "requirements": {
                "currently_due": account.requirements.currently_due if account.requirements else [],
                "eventually_due": account.requirements.eventually_due if account.requirements else [],
                "past_due": account.requirements.past_due if account.requirements else [],
            },
            "loops": creator.get("loops", []),
        }

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/creators/{creator_id}/generate-login-link")
async def generate_creator_login_link(creator_id: str, username: str = Depends(verify_admin)):
    """
    Generate a login link for a creator to access their Express Dashboard.
    This is where creators can see their earnings, payouts, etc.
    """
    try:
        creator = get_creator(creator_id)
        if not creator:
            raise HTTPException(status_code=404, detail=f"Creator {creator_id} not found")

        # Generate login link
        login_link = stripe.Account.create_login_link(creator["stripe_account_id"])

        return {
            "success": True,
            "url": login_link.url,
            "created": login_link.created
        }

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# HEALTH CHECK & INFO
# ============================================

@app.get("/")
async def root():
    """API information"""
    return {
        "name": "Matrix LaunchPass - Stripe Connect",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "connect_onboard": "POST /connect/onboard",
            "connect_return": "GET /connect/return",
            "connect_refresh": "GET /connect/refresh",
            "connect_webhook": "POST /webhook/stripe/connect",
            "create_checkout": "POST /connect/create-checkout",
            "list_creators": "GET /creators",
            "get_creator": "GET /creators/{creator_id}",
            "creator_login_link": "POST /creators/{creator_id}/generate-login-link",
            "health": "GET /health",
        },
    }


@app.get("/health")
async def health():
    """Health check"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


# ============================================
# STARTUP & SHUTDOWN
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize Matrix client and Google Sheets on startup"""
    # Initialize Google Sheets
    sheets_initialized = init_google_sheets()
    if not sheets_initialized:
        print("\n⚠️  WARNING: Google Sheets not initialized. Creator data will not persist!")
        print("   Add GOOGLE_SHEETS_CREDENTIALS_JSON and GOOGLE_SHEETS_SPREADSHEET_ID to .env")

    # Initialize Matrix
    try:
        await login_to_matrix()
    except Exception as err:
        print(f"\n❌ Failed to login to Matrix. Cannot start server.")
        print(f"   Please check your MATRIX_BOT_USERNAME and MATRIX_BOT_PASSWORD in .env")
        raise err

    # Display startup banner
    print(f"""
╔════════════════════════════════════════════════════════╗
║                                                        ║
║   🚀 Matrix LaunchPass - Stripe Connect v1.0           ║
║      Multi-Creator Platform with Application Fees      ║
║                                                        ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║   Server running on: http://localhost:{config.port}            ║
║                                                        ║
║   Key Endpoints:                                       ║
║   • POST   /connect/onboard            - Creator signup║
║   • GET    /connect/return             - Onboard return║
║   • GET    /connect/refresh            - Onboard refresh║
║   • POST   /webhook/stripe/connect     - Connect hooks ║
║   • POST   /connect/create-checkout    - Create payment║
║   • GET    /creators                   - List creators ║
║   • GET    /health                     - Health check  ║
║                                                        ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║   Next steps for Stripe Dashboard:                    ║
║   1. Go to Settings → Connect                          ║
║   2. Complete platform profile                         ║
║   3. Select "Platform" business model                  ║
║   4. Select "Application fees" monetization            ║
║   5. Customize branding                                ║
║                                                        ║
║   Next steps for webhooks:                             ║
║   1. Go to Developers → Webhooks → Add endpoint        ║
║   2. URL: {config.base_url}/webhook/stripe/connect
║   3. Listen to: "Events on Connected accounts"         ║
║   4. Select events: account.updated,                   ║
║      checkout.session.completed,                       ║
║      customer.subscription.deleted                     ║
║   5. Copy webhook secret to .env as                    ║
║      STRIPE_CONNECT_WEBHOOK_SECRET                     ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
    """)

    # Validate config on startup
    print(f"\n📋 Configuration Check:")
    print(f"   Matrix Server: {'✅' if config.matrix['server_url'] else '❌ MISSING'}")
    print(f"   Matrix Bot: {'✅ Logged in' if matrix_client else '❌ MISSING'}")
    print(f"   Matrix Space ID: {'✅' if config.matrix['space_id'] else '❌ MISSING'}")
    print(f"   Admin Auth: {'✅' if config.admin['username'] and config.admin['password'] else '⚠️  INSECURE'}")
    print(f"   Connect Webhook Secret: {'✅' if config.stripe['connect_webhook_secret'] else '⚠️  MISSING - Set up webhooks!'}")
    print(f"   Base URL: {config.base_url}")
    print("")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup Matrix client on shutdown"""
    global matrix_client
    if matrix_client:
        print("\n🛑 Logging out of Matrix...")
        try:
            await matrix_client.logout()
            print("✅ Logged out successfully")
        except Exception as err:
            print(f"⚠️  Logout error (non-critical): {str(err)}")
        matrix_client = None


# ============================================
# MAIN (for direct execution)
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=config.port,
        reload=True
    )
