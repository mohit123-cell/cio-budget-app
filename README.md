# CIO Budget App

This is a Django + PostgreSQL + Heroku + Amazon S3 ready project for the CIO budgeting application.

## What the project does right now
- Google login only (no plain Django login required)
- Four roles: Member, Officer, Treasurer, User Administrator
- Membership moderation with **pending / active / banned** statuses
- Profile page with Google picture fallback and S3-backed uploaded profile image
- Budget categories and purchase request workflow
- Direct messages between active users
- Announcement board with replies for in-app communication
- S3-backed document upload and retrieval
- User Administrator page that can only manage non-admin roles
- Account deletion page for users
- GitHub Actions CI using PostgreSQL
- Heroku-ready configuration with Postgres and WhiteNoise for static files

## Role summary
- **Member**: can view approved budget info, announcements, docs, and messages
- **Officer**: can submit purchase requests, upload docs, and post announcements
- **Treasurer**: can do everything officers can, plus create categories, review requests, and manage membership approval/ban status
- **User Administrator**: can only manage user roles and cannot use the normal app

## First login bootstrap
- The **first Google user** created in a fresh database becomes an **active Treasurer** automatically.
- Every later Google user is created as **Member + Pending Approval**.
- A Treasurer can then activate or ban them from the Membership page.
- A User Administrator must still be created through Django admin or the database.

## Local setup
1. Create a virtual environment and activate it.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in the values.
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Create a superuser (optional but recommended):
   ```bash
   python manage.py createsuperuser
   ```
6. Start the server:
   ```bash
   python manage.py runserver
   ```
7. Open `http://localhost:8000`.

## Fix for the Google sign-in button not showing
This project uses the **Google popup callback flow**, not `data-login_uri`, so you should not get the `Unsecured login_uri provided` error.

In Google Cloud Console, your OAuth client should include:
- `http://localhost:8000` in **Authorized JavaScript origins**
- your Heroku app URL in **Authorized JavaScript origins** later

## Amazon S3 setup
Set these environment variables in Heroku (and optionally locally):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`
- `AWS_S3_CUSTOM_DOMAIN` (optional)

If these are present, uploaded profile images, receipts, announcement attachments, and documents go to S3.
If they are missing, local development falls back to the local `media/` folder.



Deploy normally. The `Procfile` runs migrations on release.

## Create a User Administrator
1. Log in to `/admin/` with a Django superuser.
2. Open **Profiles**.
3. Change the target user's role to **User Administrator**.
4. Do **not** create that role through the normal app. The app blocks it.


## Fix for `createsuperuser` IntegrityError
If you previously hit an error mentioning `accounts_profile.profile_picture_url`, pull this updated project and run:

```bash
python manage.py migrate
```

That new migration removes the leftover legacy column that was causing profile creation to fail for superusers and first-time users.


## Important update
If dashboard or messages crash after login, run `python manage.py migrate`. Version includes migration `0007_create_messaging_models.py` to create the missing messaging tables.


## Duplicate Google-login test accounts
If you created more than one local Django user with the same email while testing, Google login now safely reuses the primary matching account instead of crashing. Run `python manage.py migrate` to apply the `google_sub` field used for stable Google account linking.
