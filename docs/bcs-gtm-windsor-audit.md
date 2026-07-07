# BCS GTM Container Audit - Windsor.ai Reverse Engineering

Container: `GTM-KQQ7TNP` (www.brightoncollege.edu.sg)
Account: `6000232799` (Cognita - Brighton College Singapore)

---

## Windsor.ai Attribution System

Windsor.ai is a multi-touch attribution SaaS platform. Their 3 tags + 4 triggers form a self-contained cross-channel attribution pipeline that uses GA as the data transport layer.

### How It Works (Data Flow)

```
1. Every page load
   └─> Tag 126: Delayed pageview script
       └─> Pushes custom event "delayedPageview" to dataLayer (after page fully loads)
           └─> Tag 128: Captures email from form fields, SHA-256 hashes it
               └─> Stores hashed email as "transactionId" in dataLayer

2. Any form submit click or form submission
   └─> Tag 131: UA event sent to GA with:
       - Hashed email as transaction ID (cross-platform join key)
       - Nationality (from Gravity Forms dataLayer)
       - Year Level (from Gravity Forms dataLayer)
       - Original Page URL (landing page/referrer context)

3. Windsor.ai platform (external)
   └─> Pulls GA data via API
   └─> Matches hashed emails with ad platform data (Google, Meta, Yahoo, Bing)
   └─> Produces multi-touch attribution reports
```

### Windsor Tags (verified code)

#### Tag 126: `[windsor.ai] - cHTML delayed pageview`
- **Type:** Custom HTML | **Fires on:** All Pages

```html
<script>
window.setTimeout(function() {
  window.dataLayer.push({
    event: 'delayedPageview'
  });
}, 1500);
</script>
```

Waits 1.5 seconds for Gravity Forms to render, then fires the `delayedPageview` event that triggers tag 128.

#### Tag 128: `[windsor.ai] - Save hashed email as transactionid`
- **Type:** Custom HTML | **Fires on:** Event `delayedPageview`

```html
<script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/sjcl/1.0.8/sjcl.min.js"></script>
<script type="application/javascript">
  var emails = document.querySelectorAll('input[name="email"],input[type="email"]');
  if (emails.length) {
    var i;
    for (i = 0; i < emails.length; i++) {
      if (emails[i].value != '') {
        var email = emails[i].value;
        window.dataLayer = window.dataLayer || [];
        dataLayer.push({
          'transactionId': sjcl.codec.hex.fromBits(sjcl.hash.sha256.hash(email)),
          'transactionTotal': 1
        });
      }
    }
  }
</script>
```

Loads SJCL crypto library. Scans all email input fields on the page. If any has a value, SHA-256 hashes it and pushes as `transactionId` with `transactionTotal: 1`. The hashed email is the deterministic cross-platform join key. `transactionTotal: 1` exploits UA's e-commerce transaction API so Windsor can pull conversions via GA's e-commerce reporting endpoint.

#### Tag 131: `[windsor.ai] - save to GA`
- **Type:** Universal Analytics | **Fires on:** Form submit clicks + form submissions (triggers 129, 130, 187)
- Sends hashed email (as transaction ID) + Nationality + Year Level + Original Page URL to GA. Windsor pulls this via GA API.

#### Tag 125: `Facebook - Lead Pixel - TY Pages`
- **Type:** Custom HTML | **Fires on:** Taster Day TY, Book a Tour TY, Enquire Now TY, Open House TY

```html
<script>
  fbq('track', 'Lead');
</script>
```

Fires Meta's standard `Lead` event on all thank-you pages to feed conversion optimization in Meta Ads.

### Windsor Triggers

| Trigger ID | Name | Type | Condition |
|------------|------|------|-----------|
| 127 | `[windsor.ai] - event delayed_pageview` | Custom Event | Event = `delayedPageview` |
| 129 | `[windsor.ai] - FORM SUBMIT CLICK` | Click | Form ID contains "submit" |
| 130 | `[windsor.ai] - FORM SUBMIT CLICK 3` | Click | Form Classes contains "btn-primary" |
| 187 | `[windsor.ai] - form submissions` | Form Submission | All forms (no filter) |

### Windsor Variables (Lead Enrichment)

| Variable ID | Name | Type | Purpose |
|-------------|------|------|---------|
| 75 | `Nationality` | DataLayer Variable | Parent nationality from Gravity Forms - tells Windsor which nationalities each ad channel attracts |
| 63 | `Year Level` | DataLayer Variable | Target year level - tells Windsor which school stages each channel drives interest for |
| 64 | `Original Page URL` | DataLayer Variable | Landing page context for attribution path |

### What Windsor Was Using the Data For

1. **Cross-platform identity stitching** - Hashed email is the join key. Same parent fills in a form -> hashed email matches their GA sessions, Google Ads clicks, Meta ad impressions, Yahoo/Bing touchpoints. This produces a full journey view across all paid channels

2. **Multi-touch attribution modelling** - Windsor runs its own attribution model (data-driven or Markov) using the joined cross-platform data. This is exactly what our BQ+D365 Markov pipeline now does natively

3. **Lead quality segmentation by channel** - Nationality + Year Level enrichment means Windsor could answer "Which channels bring Japanese families looking at Year 7?" not just "Which channels bring leads." This is the insight layer we don't yet replicate in the attribution dashboard

4. **Form-level conversion tracking** - Three separate triggers (submit button click, primary button click, form submission event) provide redundancy - if one doesn't fire, another catches it. Belt and braces for form attribution

---

## Microsoft Ads (Bing UET) Mirror Tags

Windsor also had Microsoft/Bing UET tags (tag 189-210) mirroring most conversion events. These feed the same data to Bing's attribution via UET tag `136028549`. Most are now paused, but the base tag (189) and several form/click events remain active.

---

## Full Tag Inventory by Platform

### Google Ads Conversion Tags (type: awct) - 26 tags

**Micro-conversion page views** (high-intent page visits sent as Google Ads conversions):
| Tag | Page | Status |
|-----|------|--------|
| 23 | Pre-Prep Curriculum | Active |
| 36 | Prep Curriculum | Active |
| 37 | Admissions | Active |
| 38 | Contact Admissions | Active |
| 39 | Apply Today | Active |
| 40 | Learning at Brighton | Active |
| 41 | School Contacts | Active |
| 42 | Contact Us | Active |
| 43 | Application Process | Active |
| 44 | Assessment Criteria | Active |
| 45 | Admissions Forms | Active |
| 46 | Fee Schedule | Active |
| 112 | All Pages (new) | Active |

**Macro-conversions** (form submissions / thank-you pages):
| Tag | Conversion | Status |
|-----|-----------|--------|
| 16 | Generic TYP Event | Active |
| 53 | Enquire Now page view | Active |
| 71 | Book a Tour page view | Active |
| 123 | Open House page view | Active |
| 113 | Enquire Now TY (GDN) | Active |
| 116 | Book a Tour TY (GDN) | Active |
| 118 | Open House Confirm (GDN) | Active |
| 121 | Open House Submission (Shared MCC) | Active |

**FPD (First-Party Data) Tags** - newer layer:
| Tag | Conversion | Status |
|-----|-----------|--------|
| 243 | Open House Form Submission | Active |
| 257 | Book A Tour Form Submission | Active |
| 258 | Make An Enquiry Form Submission | Active |
| 259 | PCP Form Submission | Active |
| 260 | Open House Step 1 Next | Active |
| 261 | Book A Tour Step 1 Next | Active |
| 262 | Make An Enquiry Step 1 Next | Active |
| 263 | PCP Step 1 Next | Active |
| 273 | WhatsApp Click | Active |

### Facebook/Meta Pixel Tags (type: cvt_5RM3Q) - 11 tags

| Tag | Event | Status |
|-----|-------|--------|
| 21 | All Pages (old pixel) | Active |
| 101 | All Pages (new pixel, TAG FB) | Active |
| 52 | Enquire Now page view (old) | Active |
| 102 | Enquire Now page view (new) | Active |
| 62 | Thank You page view (old) | Active |
| 103 | Generic Thank You (new) | Active |
| 69 | Book a Tour page view (old) | Active |
| 104 | Book a Tour page view (new) | Active |
| 107 | Open House page view | Active |
| 105 | Book a Tour TY | Paused |
| 106 | Open House Confirm | Paused |
| 125 | Lead Pixel - TY Pages (custom HTML) | Active - fires on Enquire TY, Book Tour TY, Open House TY, Taster Day TY |

### GA4 Tags (type: gaawe/googtag) - 17 tags

| Tag | Event | Purpose |
|-----|-------|---------|
| 89 | Configuration (all pages) | GA4 config with `save clientid` teardown. Blocked on `/node/15/edit` |
| 234 | GA4 Tag (all pages) | Second GA4 config tag |
| 264 | All Asia Schools GA4 | Paused - was group-level tracking |
| 152 | Scroll Event | 50/75/90/100% scroll depth |
| 154 | Form Submit | Generic TY + Registration Complete pages |
| 166 | Admissions Enquiry Step 1 | Click Next button on enquiry form |
| 167 | Admissions Enquiry Step 2 | Submit button on enquiry form |
| 218 | fetch_user_data | Custom event `gtagApiGet` - retrieves GA4 client ID |
| 221 | All Link Clicks | Every outbound/internal link click |
| 223 | Video Events | YouTube video start/progress/complete/pause |
| 225 | FPD Call Clicks | tel: link clicks |
| 227 | FPD Email Clicks | mailto: link clicks |
| 229 | FPD Taster Day Form Submit | Taster Day TY page |
| 230 | FPD Book A Tour Button Click | Header CTA button |
| 231 | FPD Book A Tour Footer Button Click | Footer CTA button |
| 239 | FPD Open House Form Submission | Open House TY with #gf_6 hash |
| 250-256 | FPD per-form events | Open House, Book Tour, Enquiry, PCP - Step 1 + Submit |

### Yahoo Ads Tags (type: html) - 6 tags

All custom HTML pixel tags for Yahoo advertising:
- All Pages, Book a Tour, Book a Tour TY, Enquire Now, Submit Enquiry click, Enquire TY, PDF Download

### Other Tags

| Tag | Type | Purpose | Status |
|-----|------|---------|--------|
| 5 | UA Page View | Universal Analytics base tracking | Active (blocked on /node/15/edit) |
| 18 | Conversion Linker | Google Ads GCLID capture | Active |
| 86 | Organization Schema | Structured data | Paused |
| 88 | Admissions FAQ Schema | FAQ structured data on /admissions/faqs/ | Active |
| 213 | Fraud Blocker | Click fraud detection | Active |
| 215 | save clientid | Custom template - saves GA4 client_id (teardown of GA4 config) | Active |
| 219 | TruConversion | Heatmaps/session recordings | Active |
| 283 | Gravity Forms Listener | DOM Ready custom HTML - sets up GF event listeners | Active |

---

## Conversion Funnel Architecture

Windsor/the previous agency built a 3-tier conversion funnel:

### Tier 1: Micro-conversions (awareness signals)
- Page views on admissions-intent pages (12 specific URLs)
- Sent to Google Ads as conversion events for Smart Bidding signals
- Scroll depth, video views, link clicks (GA4)

### Tier 2: Intent signals (consideration)
- Enquire Now page view, Book a Tour page view, Open House page view
- Multi-step form tracking: Step 1 (Next button) and Step 2 (Submit)
- CTA button clicks (header + footer Book a Tour buttons)
- Call clicks, email clicks, WhatsApp clicks

### Tier 3: Macro-conversions (action)
- Thank-you page views (Enquire Now TY, Book a Tour TY, Open House TY, Registration Complete)
- Generic /thank-you/ catch-all
- Gravity Forms submission events
- Sent to Google Ads, Meta, Yahoo, Bing, and GA4

---

## Form Identification Method

The FPD tags use Gravity Forms page hash fragments to identify which form was submitted on the shared /thank-you/ page:

| Hash | Form | Gravity Form ID |
|------|------|----------------|
| `#gf_4` | Make An Enquiry | GF 4 |
| `#gf_5` | Book A Tour | GF 5 |
| `#gf_6` | Open House Registration | GF 6 |
| `#gf_22` | Preparatory Course Primary (PCP) | GF 22 |

Step 1 triggers match `Page Path` (the form page) + `Page Hash` (the GF hash).
Submit triggers match `Page Path` contains `thank-you` + `Page Hash`.

---

## What We've Replaced vs What's Lost

### Replaced by our BQ+D365 pipeline
- Cross-platform identity stitching (we use GA4 client_id + D365 CRM join instead of hashed email)
- Multi-touch attribution model (our Markov model vs Windsor's model)
- Channel-level conversion attribution

### Not yet replicated
- **Nationality + Year Level enrichment per lead** - Windsor captured these from Gravity Forms and attached them to each attributed conversion. Our pipeline attributes at the channel level but doesn't segment by demographic
- **Multi-step form funnel tracking** - Windsor tracked Step 1 (Next click) vs Step 2 (Submit). We only track completed submissions
- **Micro-conversion weighting** - The 12 admissions page-view conversions fed Smart Bidding. We track these in GA4 but don't use them in our attribution model

### Still active and serving a purpose
- Google Ads conversion tags (feeding Smart Bidding signals)
- Meta pixel events (feeding Meta's algorithm)
- GA4 event tracking (scroll, video, links, forms)
- Yahoo/Bing UET tracking
- Fraud Blocker
- Structured data injection (FAQ schema)
