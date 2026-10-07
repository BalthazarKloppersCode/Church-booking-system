# WhatsApp setup (Meta Cloud API)

The app sends booking messages through Meta's WhatsApp Cloud API from a
dedicated church number. Everything below is done in Meta's dashboards by the
church — the app only needs three values at the end.

WhatsApp only lets a business start a conversation with a pre-approved
**message template**, so the app sends the four templates listed in step 4.
The wording lives in `backend/app/whatsapp.py`; a test fails if this page and
that file ever disagree.

## 1. The number

Use a number that is **not already registered on WhatsApp or WhatsApp
Business** (a spare SIM or a landline that can receive a call works). Once it is
on the Cloud API it can't be used in the normal WhatsApp app at the same time.
You need to be able to receive an SMS or voice call on it once, to verify it.

## 2. Meta business account and app

1. Go to <https://business.facebook.com> and create a business portfolio
   (for example "Joshua Generation Pinehurst"). Use a church email address.
2. Go to <https://developers.facebook.com> → **My Apps** → **Create app** →
   use case **Other** → app type **Business** → attach it to that portfolio.
3. On the app dashboard, **Add product → WhatsApp → Set up**.

## 3. Register the number

In the app: **WhatsApp → API Setup → Add phone number**. Enter the church's
display name, category and the number, then verify it with the code.

Write down two values shown on the API Setup page:

- **Phone number ID** → this is `WHATSAPP_PHONE_NUMBER_ID`
- **WhatsApp Business Account ID** (needed again in step 5)

Meta reviews the display name; messaging works while it is pending but the
name shown to people may be the number until it's approved.

## 4. Create the message templates

Open **WhatsApp Manager → Message templates → Create template** and create
each of the four below. For all of them: category **Utility**, language
**English** (this must match `WHATSAPP_TEMPLATE_LANGUAGE`, default `en`), and
use the name and body **exactly** as shown. Meta asks for sample values for the
`{{numbers}}` — use the ones in the tables.

Approval usually takes minutes, occasionally a day. A rejected template can
be edited and resubmitted.

### `booking_confirmed`

```
Hi {{1}}, your booking for {{2}} is confirmed.

Room: {{3}}
Date: {{4}}
Time: {{5}}
Reference: {{6}}

Your full confirmation and venue conditions are saved under My bookings at {{7}}. Please keep this message for your records.
```

| Variable | Sample |
| --- | --- |
| {{1}} | Jane |
| {{2}} | Wedding |
| {{3}} | Main Hall |
| {{4}} | Saturday, 14 November 2026 |
| {{5}} | 14:00–18:00 |
| {{6}} | JGP-1A2B3C4D |
| {{7}} | https://your-site.vercel.app/my-bookings |

### `booking_pending`

```
Hi {{1}}, we've received your request to book {{2}} on {{3}} at {{4}}.

It needs approval from the office. We'll message you as soon as it has been reviewed.
```

| Variable | Sample |
| --- | --- |
| {{1}} | Jane |
| {{2}} | Main Hall |
| {{3}} | Saturday, 14 November 2026 |
| {{4}} | 14:00 |

### `booking_not_approved`

```
Hi {{1}}, unfortunately your request to book {{2}} on {{3}} was not approved.

Note from the office: {{4}}

Please contact the office if you'd like to discuss alternatives.
```

| Variable | Sample |
| --- | --- |
| {{1}} | Jane |
| {{2}} | Main Hall |
| {{3}} | Saturday, 14 November 2026 |
| {{4}} | The hall is already in use that day. |

### `admin_new_request`

```
New booking request from {{1}} ({{2}}): {{3}} on {{4}} at {{5}} for {{6}} people. Reason: {{7}}.

Please review it in the admin portal.
```

| Variable | Sample |
| --- | --- |
| {{1}} | Jane Smith |
| {{2}} | Durbanville |
| {{3}} | Main Hall |
| {{4}} | Sat 14 Nov |
| {{5}} | 14:00 |
| {{6}} | 120 |
| {{7}} | Wedding |

## 5. A token that doesn't expire

The token on the API Setup page lasts 24 hours — fine for a first test, no good
for the live site. Make a permanent one:

1. <https://business.facebook.com/settings> → **Users → System users → Add**.
   Name it "Booking system", role **Admin**.
2. **Add assets** → Apps → your app → **Full control**. Add assets again →
   WhatsApp accounts → your account → **Full control**.
3. **Generate token** → pick your app → expiry **Never** → tick
   `whatsapp_business_messaging` and `whatsapp_business_management` → copy it.

Treat it like a password. Don't paste it into chat, email or the code.

## 6. Give the app the values

Set these in `backend/.env` for local testing **and** in Render →
Environment (then redeploy):

| Setting | Value |
| --- | --- |
| `WHATSAPP_PHONE_NUMBER_ID` | the Phone number ID from step 3 |
| `WHATSAPP_ACCESS_TOKEN` | the permanent token from step 5 |
| `WHATSAPP_TEMPLATE_LANGUAGE` | only if you chose something other than `en` |
| `ADMIN_NOTIFY_WHATSAPP` | office number(s) to alert about new requests, comma-separated |
| `WHATSAPP_DEFAULT_COUNTRY_CODE` | only if not South Africa (default `27`) |

Phone numbers typed the local way (`082 123 4567`) are converted to
international form automatically.

After the deploy, the Render log should show
`[whatsapp] configured: phone number id …`. Then make a test booking with your
own number: you should see `[whatsapp sent] to=…` in the log and the message on
your phone. A problem shows as `[whatsapp error] … code …: reason` — the code
is Meta's, e.g. `132001` template name/language mismatch, `190` expired token,
`131030` number not allowed yet (see below).

## Good to know

- **Until the account is verified/live**, Meta only lets you message numbers
  you've added under *API Setup → To* (up to 5 test recipients). Real bookers
  get messages once the app is switched to **Live** and the business is
  verified (Business settings → Security centre → Business verification).
- **Cost.** Meta charges per template message sent outside a 24-hour
  conversation window; utility messages are cheap but not free, and the old
  "1,000 free conversations a month" allowance no longer exists. Add a payment
  method in WhatsApp Manager and check Meta's current price list for your
  country before going live.
- **Opt-in.** WhatsApp's rules require people to have agreed to be messaged.
  The booking form asks for a phone number to contact them, so say so near
  that field ("we'll send updates on WhatsApp").
- **Room Guide PDFs** aren't sent yet. WhatsApp can send a PDF as a document
  message once it's hosted at a public link; that's a separate step.
