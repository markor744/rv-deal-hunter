# RV Deal Hunter

Checks RV relocation deal sites twice a day and texts you when a good deal shows up on your
routes. It runs by itself on GitHub (free), not on your Mac.

## What it does

- **7am and 1pm Pacific:** checks the sites.
  - Deals scoring **70 or more** are texted right away.
  - Deals scoring **40 to 69** wait for the 6pm digest.
  - Anything lower is only logged.
- **6pm:** sends one digest text if anything is waiting.
- **Sundays at 6pm:** a "still running" text.
- **Feb 1 and Aug 15:** season reminders.
- **If a site fails 3 runs in a row:** a warning text.
- **Never** texts about the same deal twice, and **never more than 5 texts a day** in total.
- Each deal gets a phone-friendly **trip plan page** fitted to that deal's nights and distance cap.

## What a text looks like

> RV DEAL 82/100 Great: LA > Vancouver. Pick up Mar 3-8, 7 nights. All-in about $1,130-1,290
> (RV $80, flight there $160-320, fuel+camping $890). Watch: $2,330 bond. Details + book: (link)

**"All-in"** is the whole trip in Canadian dollars:
- the RV (nights plus booking fee);
- getting there or home: a flight from or to Vancouver, or a bus, train or ferry for Seattle,
  Bellingham or Victoria;
- fuel for the drive, minus any fuel refund;
- campgrounds.

It's an estimate. Flight prices are typical fares, not quotes; the deal page has a button for
today's real prices. You can change the fuel, campground and fare assumptions under `travel:`
and `costs:` in `config.yaml`.

The score uses the all-in cost too, so a "$1 a night" RV with a $2,000 fuel bill no longer ranks
as a great deal.

## Settings

On the deals page, tap the **gear** (top right):
- **How will you sleep?** Mostly free (the default), Mix, or Campgrounds every night.
- **People travelling:** 1 to 4. Flights and buses are per person; the default is 2.
- **Which route to show first:** Scenic (the default) or Fast.

Every price on every deal updates right away, and your phone remembers the choices. Texts and
scores use the same defaults in `config.yaml` (`camping_style`, `travellers`, `route_first`).

Deals on your routes that score under 40 are not texted. They're listed under **Skipped**, with
the reasons (for example "costs ~$300 a night all-in, rushed, winter roads").

## How the score works

Out of 100. Every part is a real number you can check on the deal page under "Why this score":

| Part | Points | What earns them |
|---|---|---|
| Value | 50 | All-in cost per night (RV, fee, flight or bus, fuel after refund, camping). $80 or less = full points, $300 or more = zero |
| Pace | 15 | Nights compared with the days the drive needs at about 5 hours a day. Rushed = 0, twice the time you need = full |
| Distance | 10 | Unlimited or at least 20% more than the route = full. Less than the route = 0 |
| Timing | 10 | Pick-up window open for at least a week = full. Closing in a day or two = very little |
| Season | 10 | Snow, mountain passes or blizzards on the route in those months cost points |
| Sleeps | 5 | Sleeps 2 or more |
| Priority city | +5 | Bonus when it starts in one of your priority cities (total capped at 100) |

**Unknowns earn little, never full marks.** For example, a missing booking fee is assumed to be $49,
and a missing distance cap earns 3 of 10. A closed pick-up window scores 0.

You can change any of this under `scoring:` in `config.yaml`.

## Free camping

Every night in a trip plan lists **sleep options**:
- the paid campground;
- the free options for that region:
  - US national forest and BLM land, usually up to 14 days in any 28;
  - BC recreation sites;
  - Ontario Crown land, free for Canadian residents for up to 21 days on one site;
  - store car parks that allow overnight stays (ask inside first);
- a **"Find free spots near..."** map search.

City stops and national parks (Banff, Lake Louise, Jasper) say honestly that free spots are rare or not
allowed there.

The **Money** tab has a switch: **Campgrounds** (pay every night), **Mix** (about half free) or
**Mostly free** (free, plus a paid site every 4th night for showers, water and a dump station). The
total updates as you switch. Texts and scores use `camping_style:` in `config.yaml` (default `free`).

## The deal pages

Every text links to a page made for your phone (light and dark mode).

- **At the top:** the verdict ("Great deal", "Worth a look" or "Weak deal"), then four lines:
  **When** to pick up, **Getting there** (or home), **The RV** price, and **All-in**.
- **Grab it in 3 steps:** 1 Book the RV, 2 See today's flight prices (Google Flights, already
  filled in), 3 Open the route map. Plus a "What to bring" list.
- **Why this score:** why it scored what it did, as a checklist (good, so-so, bad, unknown). Below it,
  the best route and things to know, such as border crossings.
- **Day by day:** switch between route options (for example Scenic coast vs Fast inland). Day by
  day: drive, km, hours, stops, an overnight campground with a map link, and directions. Road and
  season alerts for your dates are folded into one section.
- **Money:** the all-in breakdown, what you pay the company, the fuel refund, what is only held on your card (bond and deposit), and
  the price of extra nights and extra distance.
- **Fine print:** penalty terms, vehicle, booking method, a link to the original listing, and a
  list of what the company didn't list (never guessed).

The list of all deals (the plans link in the digest) starts with the **Best right now** deal, then tabs:
**Great** (70 or more), **Good** (40 to 69), **Closing** (pick-up ends within 2 weeks) and **All**.
Each deal shows its dates, nights, all-in cost and flight cost.

## Sites

| Site | Status |
|---|---|
| Imoova (USA + Canada) | On. Reads its two table pages, plus the deal page for new deals on your routes. |
| CanaDream relocation specials | On |
| CanaDream + El Monte RV, Canada to US | On. Both companies' pages are merged, so you never get a duplicate text. |
| Fraserway | On. Phone booking only (1-800-661-2441). If they post deals in a format it can't read, it tells you to call rather than guessing. |
| Cruise America / Cruise Canada | **Off.** Its terms of use forbid robots and data gathering. |

Each site's robots.txt is checked again on every run. If a site starts blocking, the tool stops
and reports it. It visits each site at most twice a day, with a pause between pages.

## Add or remove friends

Friends get the deal alerts, the 6pm digest and the season reminders. Only you get system texts
(site failures, Sunday check-ins, tests). Up to 5 friends.

**Ask them first.** Texting people who didn't agree breaks Canada's anti-spam rules and gets
numbers blocked by carriers. Each new friend automatically gets one welcome text, on the next run,
saying who it's from and that they can reply **STOP** anytime. Twilio handles STOP for you.

**Add or change friends from your phone or computer:**
1. On GitHub, open your **rv-deal-hunter** repo, then **Settings**, then **Secrets and variables**,
   then **Actions**.
2. Either:
   - first time: click **New repository secret** and name it `ALERT_FRIENDS`, or
   - after that: click the pencil next to **ALERT_FRIENDS**.
3. Type all your friends' numbers, separated by commas, for example
   `+16045551234, +17785555678`. Writing them like `604-555-1234` also works.
4. Click **Add secret** (or **Update secret**).

You won't be able to see the numbers again, even on GitHub. To change the list, type the whole
list again. To remove someone, save the list without their number. To remove everyone, delete the
secret.

**Or from Terminal** (it asks for the list and hides it): `gh secret set ALERT_FRIENDS`

**Choose what friends get:** in `config.yaml`, under `friends:`, edit `receive: [alerts, digest, season]`.
For example, `receive: [alerts]` sends them only the best deals, and `receive: []` pauses all friends.

**Check it worked:** run `status` (see "Run a check now"). It shows how many friends are set up
and any problems, such as "friend 2: not a valid number". It never shows the numbers.

**US friends:** your Vancouver Twilio number can text Canadian numbers without any registration.
To text **US** numbers, Twilio requires the number to be registered for US "A2P 10DLC" first, and
unregistered texts get extra carrier fees or are blocked. So US numbers are skipped until you
register (Twilio Console > Messaging > Regulatory Compliance) and set `us_friends: true` in `config.yaml`.

## Change your routes or the score thresholds

1. On GitHub, open your **rv-deal-hunter** repo and click **config.yaml**.
2. Click the **pencil** icon (top right of the file).
3. Edit what you want:
   - `end_in`, `start_in`: the cities that count as your routes.
   - `priority_origins`: starting cities that earn a bonus.
   - `text_now: 70`: the score that triggers an instant text.
   - `digest: 40`: the lowest score that goes in the digest.
   - `max_texts_per_day: 5`
4. Click **Commit changes**, then **Commit changes** again.

The next run uses the new settings. Keep the spacing exactly as it is; YAML is fussy about it.

## Pause texts

- **Quick pause:** in `config.yaml`, change `texts_enabled: true` to `texts_enabled: false`. It keeps
  checking and logging but sends nothing.
- **Stop everything:** open the **Actions** tab, click **RV Deal Hunter** on the left, then the **...**
  button (top right), then **Disable workflow**. Turn it back on the same way.

## Run a check now

1. Open the **Actions** tab and click **RV Deal Hunter** on the left.
2. Click **Run workflow**.
3. Pick what to run:
   - `check`: check the sites. It still counts toward the 2-a-day limit per site.
   - `test-sms`: send "RV Deal Hunter test message." (to you only)
   - `welcome`: send the welcome text to any friend who hasn't had one
   - `fixtures`: a practice run on saved pages. No websites, no texts.
   - `status`: a summary. Never shows secrets.
4. Click the green **Run workflow** button.

After about 30 seconds a run appears. Click it, then **run**, to see what happened.

## Rotate the Twilio key (do this if you think it leaked, or once a year)

1. In the Twilio Console (console.twilio.com), open **Account** (top right), then **API keys & tokens**.
2. Click **Create API key**, name it `RV Deal Hunter 2`, type **Standard**, then **Create**.
3. Copy the **SID** and the **Secret**. The secret is shown only once.
4. In Terminal, inside the rv-deal-hunter folder, run each line. Paste the value when asked; it stays hidden.
   ```
   gh secret set TWILIO_API_KEY_SID
   gh secret set TWILIO_API_KEY_SECRET
   ```
5. Run `test-sms` (see above) and check that the text arrives.
6. Back in Twilio, open the **old** key and click **Delete**.

Your other apps (Market Brain, PartyPitch) are not affected: this key belongs only to this tool.

## If the texts stop

1. **Actions tab:** is the latest run red? Click it and read the error near the bottom.
   - `Twilio error 20003`: the key is wrong or deleted. Rotate it (above).
   - `Twilio error 21610`: you replied STOP. Text **START** to the sending number.
   - `Twilio error 30007` or `30034`: a carrier blocked the text. See "Delivery" below.
   - `daily cap of 5 texts reached`: working as designed. The extra deals are in the next digest.
   - `FAILED (3 in a row)` for a site: the site changed its layout. Open Claude Code in this folder
     and say: "the <site> reader is failing, here is the log", then paste the log.
2. **No runs at all for days?** GitHub turns off schedules in public repos after 60 days with no
   activity. This tool commits a small file every run to stay active, but if it did switch off,
   the Actions tab shows a banner with a button to turn it back on.
3. **Twilio Console, Monitor > Logs > Messaging:** shows whether each text was delivered.
4. Run `status` (above) to see the last run, today's text count and any failing sites.

## Delivery

The tool sends from the Twilio number set up in Phase 1. Its type and registration status are
recorded in `SETUP-NOTES.md` once setup is done.

## Costs

- **GitHub:** free. Public repos have free Actions and free Pages.
- **Twilio:** at most 5 messages a day, each up to 2 segments, sent to you plus up to 5 friends.
  The worst case is 5 x 2 x 6 = 60 segments a day (about 1,800 a month). A normal month is far
  less, because most days have no great deal. Add the number's monthly fee, and check current
  rates in Twilio Console > Billing.

## Privacy

This repo is **public** (free GitHub Pages requires it). It holds code, deal facts and plan pages
only. Your number, your friends' numbers and all Twilio values live in **GitHub Secrets**, which
nobody can read, including you. Logs say "you" or "friend 2", never a number. To remember who
got a welcome text, the memory file keeps a scrambled fingerprint that can't be turned back into
a number. The plan pages contain no name, number or secret. The tests check this.

## Test a whole year in 10 seconds

The year simulator runs the real tool through 365 fake days, with no websites and no texts. It
throws in:
- delayed and dropped GitHub runs, manual runs, and daylight saving;
- New Year and leap days;
- a 4-day site outage, a one-off site error, and a burst of 9 great deals in one day;
- a friend added in spring, plus spring and fall deal seasons.

It then checks every promise: the 5-a-day cap, no repeats, weekly check-ins, reminders, failure
warnings, the digest, friends, seasonal prices and warnings, and file sizes.

- **On GitHub:** Actions, then Run workflow, then `simulate`.
- **In Terminal:** `.venv/bin/python -m rvdeals.simulate 2026-11-22 365`

The result is in `reports/year-simulation.md`: every check, plus a month-by-month table of what
you would have received.

What it found and fixed so far:
- deals dated "29 Feb" failed to read (leap years);
- old plan pages piled up forever (now removed 2 weeks after a deal closes);
- the Feb 1 and Aug 15 reminders were lost if GitHub skipped that evening (now they retry for 3 days);
- a Sunday check-in was lost if GitHub skipped it or the daily cap was full (now it comes the next evening);
- the digest could list deals that closed while waiting (now filtered out).

## For Claude Code (or a developer)

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                 # 60 tests on saved pages and two simulated years (tests/fixtures, from 2026-11-22)
.venv/bin/python -m rvdeals.main fixtures     # practice run; plan pages land in .practice/docs
DRY_RUN=1 .venv/bin/python -m rvdeals.main check   # real sites, prints texts instead of sending
```

- **Layout:**
  - `rvdeals/sources/`: one reader per site.
  - `scoring.py`: route rules and the 0-100 score.
  - `message.py`: texts, 300 characters or fewer.
  - `plans.py` and `itinerary_data.py`: the trip pages.
  - `state.py`: the tool's memory, in `state/state.json`.
  - `main.py`: slots, cap, digest, check-ins.
- **Settings:** secrets are read from environment variables only (see `rvdeals/sms.py`). Never print them.
- **When a site changes:** save a new snapshot into `tests/fixtures/`, update its reader until
  the tests pass, then push.
