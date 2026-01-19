# Railway Deployment Guide

Your code is on GitHub: https://github.com/maczumby/stripeconnect

## Deploy to Railway

### 1. Create New Project

1. Go to [Railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `maczumby/stripeconnect`
5. Railway will automatically detect Python and install dependencies

### 2. Add Environment Variables

Click on your project → "Variables" tab

**Copy all values from your local `.env` file and add them to Railway:**

- `MATRIX_SERVER_URL`
- `MATRIX_BOT_USERNAME`
- `MATRIX_BOT_PASSWORD`
- `MATRIX_SPACE_ID`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_CONNECT_WEBHOOK_SECRET` (get after setting up webhook)
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `GOOGLE_SHEETS_CREDENTIALS_JSON` (paste entire JSON)
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `BASE_URL` (update after getting Railway URL)

### 3. Deploy

Railway will automatically:
- Install dependencies from `requirements.txt`
- Use the `Procfile` to start your app
- Expose your app on a public URL

### 4. Get Your Railway URL

After deployment:
1. Click "Settings" → "Domains"
2. Copy your Railway URL
3. Update `BASE_URL` variable with this URL

### 5. Update Stripe Webhooks

1. Go to Stripe Dashboard → Webhooks
2. Add Connect webhook endpoint
3. URL: `https://your-railway-url.railway.app/webhook/stripe/connect`
4. Listen to "Events on Connected accounts"
5. Select events: account.updated, checkout.session.completed, customer.subscription.deleted
6. Copy webhook secret and add to Railway as `STRIPE_CONNECT_WEBHOOK_SECRET`

### 6. Test Deployment

Visit: `https://your-railway-url.railway.app/`

Check health: `https://your-railway-url.railway.app/health`

View logs in Railway to verify:
- Google Sheets connected
- Matrix bot logged in
- Server running

## Redeploy

Any push to GitHub main branch automatically redeploys:

```bash
git add .
git commit -m "Your changes"
git push origin main
```

## Production Checklist

- [ ] All environment variables set in Railway
- [ ] BASE_URL updated with Railway URL
- [ ] Stripe Connect webhook configured
- [ ] Webhook secret added to Railway
- [ ] Test endpoint responding
- [ ] Google Sheets connecting
- [ ] Strong admin password set
