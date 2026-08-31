# The Music Club — Product Requirements Document

## Original Problem Statement
> build it's backend, database, server. add two admin accounts, google id autherisation login and password, forget password through otp in the registered mail.

Landing page reference: The Music Club | Express Yourself — a campus music collective run by Chanakya & Siddharth (Jam Room #2). Features: Jam Sessions, Skill Workshops, Live Showcases. Semester roadmap: Meetup (Wk1), Jams (Wk3), Open Mic (Wk6), Concert (Wk10).

## User Choices (v1)
- Auth: **Custom JWT email + password** (no Google OAuth; user opted for password-only)
- Email provider for OTP: **Resend** (API key configured, sender `onboarding@resend.dev`)
- Access model: **Admin-gated** — only admins can log in; no public self-registration
- MVP scope for admin panel: Members + Events + Sessions + Gallery + Profile

## User Personas
- **Chanakya** (Co-Director) — creative direction, event coordination
- **Siddharth** (Co-Director) — community & gear operations

## Architecture
- **Frontend**: React 19 + React Router 7 + Tailwind + shadcn/ui + sonner (toasts). Font: Syne (display) + Plus Jakarta Sans (body) + JetBrains Mono. Dark theme with electric amber/crimson/violet palette.
- **Backend**: FastAPI + Motor (MongoDB async). JWT (PyJWT) with 12h access + 7d refresh httpOnly cookies. bcrypt password hashing.
- **DB**: MongoDB (`music_club_db`) with collections: `users`, `password_reset_otps`, `login_attempts`, `events`, `sessions`, `gallery`. Unique indexes on `users.email`, `users.id`, and `password_reset_otps.email`.
- **Email**: Resend for OTP delivery with branded HTML template. Falls back to log-only dev mode if `RESEND_API_KEY` empty.

## Implemented (2026-02, iteration 1)
- Landing page mirroring the artifact: hero, philosophy grid, features, live events/sessions feed, roadmap timeline, leadership, contact.
- Auth: `/api/auth/login`, `/logout`, `/me`, `/refresh`, `/forgot-password`, `/verify-otp`, `/reset-password`, `/change-password`
- Brute-force protection: 5 failed logins per email → 15-minute lockout (429)
- OTP: 6-digit numeric, bcrypt-hashed in DB, 10-minute expiry, single-use, max 6 verify attempts
- Two admins seeded on startup: `mchanakya64@gmail.com`, `siddharthsharma2649@gmail.com` (both `Admin@123`)
- Admin dashboard (`/admin/*`) with sidebar: Overview stats, Members CRUD, Events CRUD, Sessions CRUD, Gallery CRUD, Profile + change password
- Public read APIs: `/api/public/events`, `/api/public/sessions`, `/api/public/gallery`
- Admin-only members guard: cannot delete admin accounts
- 3-step Forgot Password UI (Email → OTP → New Password) using shadcn `InputOTP`
- Seed data for events, sessions, and gallery on first boot

## Backlog / Deferred
### P1
- Public gallery masonry page with tag filters + lightbox
- Members table: search, filter by role/status/instrument, bulk actions
- Event RSVP tracking + capacity display on public site
- Email verification flow for members created by admin
- Password strength meter on reset/change forms

### P2
- Google OAuth (re-offer once user is ready)
- File uploads for gallery images (currently URL-only) via Object Storage
- Email templates for event announcements + reminders (Resend broadcasts)
- Audit log for admin actions
- Dark/light theme toggle
- Refresh-token rotation
