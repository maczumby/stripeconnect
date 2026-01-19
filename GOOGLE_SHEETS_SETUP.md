# Google Sheets Setup Guide

This guide will walk you through setting up Google Sheets as your creator database.

## Why Google Sheets?

For a proof of concept, Google Sheets is perfect because:
- You can manually manage creator data
- Easy to view and edit all creators at once
- No database setup required
- Free and accessible from anywhere

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click "Select a project" → "New Project"
3. Name it something like "Stripe Connect Platform"
4. Click "Create"

### 2. Enable Required APIs

1. In the search bar, type "Google Sheets API"
2. Click on it and click "Enable"
3. Go back and search for "Google Drive API"
4. Click on it and click "Enable"

### 3. Create a Service Account

1. Go to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
3. Name: `stripe-connect-bot`
4. Description: `Service account for Stripe Connect platform`
5. Click "Create and Continue"
6. Skip the optional steps (don't need to grant roles)
7. Click "Done"

### 4. Generate Service Account Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose "JSON" format
5. Click "Create"
6. A JSON file will download - **SAVE THIS SECURELY**

The JSON file looks like this:
```json
{
  "type": "service_account",
  "project_id": "your-project-123",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "stripe-connect-bot@your-project-123.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

### 5. Create Your Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new blank spreadsheet
3. Name it "Stripe Connect Creators"
4. Copy the Spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/1abc...xyz/edit
                                           ^^^^^^^^^^
                                        This is your ID
   ```

### 6. Share the Sheet with Your Service Account

**CRITICAL STEP:** Your service account needs access to the sheet!

1. In your Google Sheet, click "Share" (top right)
2. Paste the service account email from the JSON file
   - It looks like: `stripe-connect-bot@your-project-123.iam.gserviceaccount.com`
3. Give it "Editor" permissions
4. Uncheck "Notify people"
5. Click "Share"

### 7. Add Credentials to .env

In your `stripeconnect/.env` file, add:

```bash
# Copy the ENTIRE JSON file content as a single line
GOOGLE_SHEETS_CREDENTIALS_JSON='{"type":"service_account","project_id":"your-project-123",...}'

# Paste the Spreadsheet ID from step 5
GOOGLE_SHEETS_SPREADSHEET_ID=1abc...xyz
```

**Important:** The JSON must be:
- Wrapped in single quotes
- On a single line
- All escaped properly (the way it is in the file should work)

### 8. Test the Connection

Start your server:
```bash
cd stripeconnect
python app.py
```

You should see:
```
✅ Google Sheets connected successfully
```

The app will automatically create a "Creators" worksheet with these columns:
- creator_id
- stripe_account_id
- email
- name
- onboarding_complete
- charges_enabled
- loops
- created_at
- updated_at

## Managing Creators in Google Sheets

### View All Creators

Just open your Google Sheet and look at the "Creators" tab. You'll see all creator accounts in a nice table format.

### Manually Add a Creator

You can manually add rows to test:
1. Add a new row with a creator_id like "test_creator_1"
2. Add their stripe_account_id (you'll get this from the onboarding endpoint)
3. Add their email
4. Set onboarding_complete and charges_enabled to TRUE or FALSE

### Edit Creator Data

Just edit the cells directly in Google Sheets. The app reads the latest data on every request.

### Add Loop IDs

In the "loops" column, add comma-separated Matrix room IDs:
```
!room1:server.com,!room2:server.com
```

## Troubleshooting

### "Failed to initialize Google Sheets"

- Check that both APIs are enabled in Google Cloud Console
- Make sure the JSON credentials are valid
- Verify the service account email has access to the sheet

### "Creator not found"

- Check the spelling of creator_id in the sheet
- Make sure there are no extra spaces
- Verify the "Creators" worksheet exists

### "Permission denied"

- Make sure you shared the sheet with the service account email
- Give it "Editor" permissions, not just "Viewer"

## Security Notes

- **NEVER** commit your service account JSON to Git
- Add `.env` to your `.gitignore`
- The service account only has access to sheets you explicitly share with it
- You can revoke access anytime by unsharing the sheet

## Next Steps

Once Google Sheets is working:
1. Set up Stripe Connect in your dashboard
2. Configure webhooks
3. Test the full creator onboarding flow

See the main README for full setup instructions.
