# credentials/

This folder holds Google API credential files. **Never commit these to git.**

## Only one credential file needed

### `oauth_credentials.json`
One OAuth 2.0 credential covers **Google Sheets + Drive + Gmail** — all as your account (`jacques@creativrealty.com`).

**How to get it:**
1. Go to https://console.cloud.google.com/
2. Create a project (or use an existing one)
3. Enable these three APIs:
   - **Google Sheets API**
   - **Google Drive API**
   - **Gmail API**
4. Go to **APIs & Services → Credentials**
5. Click **Create Credentials → OAuth 2.0 Client ID**
6. Application type: **Desktop app**
7. Download the JSON → save as `credentials/oauth_credentials.json`

**First run:**
A browser window will open asking you to sign in as `jacques@creativrealty.com` and grant permissions. After that, the token is saved automatically as `credentials/google_token.json` — no login needed again unless the token expires.

## Shared Drive access

The system will automatically look for your **"MJ Realty"** shared Google Drive. As long as `jacques@creativrealty.com` is a member of that shared drive, the coaching folder and sheets will be created inside it and will be visible to Martin too.

If the shared drive isn't found, sheets fall back to My Drive.
