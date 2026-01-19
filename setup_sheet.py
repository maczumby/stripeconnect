#!/usr/bin/env python3
"""
Setup script to initialize Google Sheets for Stripe Connect
This creates the "Creators" worksheet with proper headers
"""

import json
import gspread
from google.oauth2.service_account import Credentials

# Configuration
CREDENTIALS_PATH = "/Users/mzvibe/Downloads/filamentskunkworks-e1f9089d9996.json"
SPREADSHEET_ID = "1K1fKlwZcpQYQ_-S3UzA9LHgVan01DwTqO15qf_RgZok"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def setup_creators_sheet():
    """Initialize the Creators worksheet with proper headers"""

    print("🔧 Setting up Google Sheets for Stripe Connect...")
    print()

    # Load credentials
    print(f"📁 Loading credentials from: {CREDENTIALS_PATH}")
    with open(CREDENTIALS_PATH, 'r') as f:
        creds_dict = json.load(f)

    print(f"✅ Service Account: {creds_dict['client_email']}")
    print()

    # Authorize
    print("🔑 Authorizing with Google...")
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)
    print("✅ Authorized successfully")
    print()

    # Open spreadsheet
    print(f"📊 Opening spreadsheet: {SPREADSHEET_ID}")
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    print(f"✅ Opened: {spreadsheet.title}")
    print()

    # Check if "Creators" worksheet already exists
    try:
        worksheet = spreadsheet.worksheet("Creators")
        print("⚠️  'Creators' worksheet already exists")

        # Ask if user wants to overwrite
        response = input("   Do you want to clear it and reset headers? (y/n): ")
        if response.lower() != 'y':
            print("   Skipping...")
            return

        # Clear existing data
        print("   Clearing existing data...")
        worksheet.clear()

    except gspread.WorksheetNotFound:
        # Create new worksheet
        print("📝 Creating 'Creators' worksheet...")
        worksheet = spreadsheet.add_worksheet(title="Creators", rows=100, cols=10)
        print("✅ Worksheet created")

    print()

    # Add headers
    print("📋 Adding column headers...")
    headers = [
        "creator_id",
        "stripe_account_id",
        "email",
        "name",
        "onboarding_complete",
        "charges_enabled",
        "loops",
        "created_at",
        "updated_at"
    ]

    worksheet.append_row(headers)
    print("✅ Headers added:")
    for i, header in enumerate(headers, 1):
        print(f"   Column {i}: {header}")

    print()

    # Format the header row
    print("🎨 Formatting header row...")
    worksheet.format('A1:I1', {
        "backgroundColor": {
            "red": 0.2,
            "green": 0.6,
            "blue": 0.86
        },
        "textFormat": {
            "bold": True,
            "foregroundColor": {
                "red": 1.0,
                "green": 1.0,
                "blue": 1.0
            }
        },
        "horizontalAlignment": "CENTER"
    })
    print("✅ Header formatted")
    print()

    # Freeze header row
    print("❄️  Freezing header row...")
    worksheet.freeze(rows=1)
    print("✅ Header row frozen")
    print()

    # Add a test row (optional)
    add_test = input("Do you want to add a test creator row? (y/n): ")
    if add_test.lower() == 'y':
        from datetime import datetime
        test_row = [
            "test_creator_1",
            "acct_test_123",
            "test@example.com",
            "Test Creator",
            "FALSE",
            "FALSE",
            "",
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ]
        worksheet.append_row(test_row)
        print("✅ Test row added")
        print()

    print("=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. View your sheet: https://docs.google.com/spreadsheets/d/" + SPREADSHEET_ID)
    print("2. Add these to your .env file:")
    print()
    print("   GOOGLE_SHEETS_CREDENTIALS_JSON='" + json.dumps(creds_dict) + "'")
    print()
    print(f"   GOOGLE_SHEETS_SPREADSHEET_ID={SPREADSHEET_ID}")
    print()
    print("3. Start your server: python app.py")
    print()

if __name__ == "__main__":
    try:
        setup_creators_sheet()
    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        print()
        print("Troubleshooting:")
        print("- Make sure the sheet is shared with: stripe-connect@filamentskunkworks.iam.gserviceaccount.com")
        print("- Verify the spreadsheet ID is correct")
        print("- Check that the credentials file exists")
