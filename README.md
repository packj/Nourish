# Nourish 🍽️

> **Missionary Dinner Calendar for LDS Wards with Automatic Google Sheets Sync**

Nourish allows LDS ward members to easily sign up to feed their local full-time missionaries. Because church-managed missionary devices (running Mobile Device Management like Maas360 or Samsung Knox) often restrict access to general web browsers, **Nourish automatically synchronizes all dinner appointments directly into Google Sheets**, which missionaries can access natively on their phones.

---

## ✨ Features

- **Multiple Missionary Companionships:** Configure one or multiple calendars (e.g. *Ward Elders*, *Sister Missionaries*, *Senior Missionaries*), each with independent calendars, dietary notes, and contacts.
- **Mobile-First Ward Member Sign-Up:**
  - Fast, clean, no login required.
  - Interactive calendar grid + list view.
  - Double-booking prevention.
  - Add to Google / Apple / Outlook Calendar with 1-click `.ics` download.
  - Self-service cancellation with a simple PIN code.
- **Automatic Google Sheets Synchronization:**
  - **Google Apps Script Webhook (Recommended):** Zero-credential, 2-minute setup.
  - **Google Service Account:** Optional enterprise mode using Google Cloud credentials.
  - Full automated sync whenever a meal is booked or cancelled, plus manual one-click re-sync in Admin.
- **Admin Dashboard:**
  - Manage companionships, contact numbers, dietary restrictions, and default meal times.
  - Add manual bookings on behalf of ward members.
  - Blackout dates (e.g., District Conference, Exchanges, P-Day).
  - Built-in setup guide with copyable Apps Script code.
- **Production Ready:**
  - Configured for Gunicorn on port `8002`.
  - Ready-to-use `systemd` service unit and `nginx` reverse proxy configuration for AWS EC2.

---

## 🚀 Local Development & Testing

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default port is set to `8002` and default admin password is `nourish-admin`.

### 3. Run the Development Server
```bash
python run.py
```
Open [http://localhost:8002](http://localhost:8002) in your browser.

- **Public Calendars:** [http://localhost:8002/](http://localhost:8002/)
- **Admin Portal:** [http://localhost:8002/admin](http://localhost:8002/admin) (Default password: `nourish-admin`)

---

## 📊 Google Sheets Auto-Sync Setup

1. Create a Google Sheet (e.g. at [sheets.new](https://sheets.new)) and share it with the missionaries.
2. Go to **Extensions > Apps Script** in the sheet menu.
3. Paste the provided script from the Nourish Admin dashboard (`/admin/sheets-help`).
4. Click **Deploy > New deployment**, select type **Web app**, set access to **Anyone**, and click **Deploy**.
5. Copy the Web App URL and paste it into the missionary set's settings in Nourish!

---

## ☁️ Production Deployment on AWS EC2

### 1. Server Setup
On your Ubuntu/Debian EC2 instance:
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx git
git clone <your-repo-url> /home/ubuntu/Nourish
cd /home/ubuntu/Nourish
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with a secure ADMIN_PASSWORD and SECRET_KEY
```

### 2. Configure systemd Service
```bash
sudo cp deploy/nourish.service /etc/systemd/system/
sudo mkdir -p /var/log/nourish
sudo chown -R ubuntu:www-data /var/log/nourish
sudo systemctl daemon-reload
sudo systemctl enable --now nourish
sudo systemctl status nourish
```

### 3. Configure Nginx Reverse Proxy
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/nourish
sudo ln -s /etc/nginx/sites-available/nourish /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```
*(Optional: Use `certbot` to generate a free SSL certificate: `sudo certbot --nginx -d your-domain.com`)*
