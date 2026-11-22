# RV Deal Hunter: year simulation

Simulated 2026-11-22 to 2027-11-21 (365 days), 2013 runs, 149 texts recorded (none sent). **33 of 33 checks passed.**

## Checks

| | Check | Detail |
|---|---|---|
| PASS | Never more than 5 texts a day | busiest day: 5 |
| PASS | No deal is texted twice | 94 deals alerted, repeats: [] |
| PASS | Every text is plain and 300 characters or less | 383 texts checked |
| PASS | Each site is checked at most twice a day | max per site per day: 2 |
| PASS | Each slot (7am, 1pm, 6pm) runs at most once a day | days with a repeat: 0 |
| PASS | Slots are rarely missed even when GitHub drops runs | missed: {'check_am': 5, 'check_pm': 2, 'digest': 4} (both runs of a slot dropped or delayed out) |
| PASS | A 'still running' text arrives every week | 53 check-ins for 53 weeks; weeks with none: [] |
| PASS | The spring season reminder arrives once, on or just after Feb 01 | sent: ['2027-02-02'] |
| PASS | The fall season reminder arrives once, on or just after Aug 15 | sent: ['2027-08-15'] |
| PASS | Daylight saving days still run the 7am and 1pm checks | DST days ['2027-03-14', '2027-11-07'], missed: [] |
| PASS | A burst of 9 great deals respects the cap and still reaches you | 5 texts that day; 9 of 9 reached you directly |
| PASS | The weekly check-in still comes the week of the burst | sent: ['2027-05-10'] |
| PASS | A 4-day site outage gives exactly one warning text | warnings: [('2027-06-30', 'failure canadream')] |
| PASS | A one-off site error gives no warning |  |
| PASS | A new friend gets exactly one welcome text | welcomes: 1 |
| PASS | Friends never get system texts, or texts from before they were added | friend got 144 texts |
| PASS | The digest never lists a deal whose pick-up has closed | stale entries: 0, e.g. [] |
| PASS | No great deal is lost (texted, or in a digest) | 99 great deals, lost: [] |
| PASS | Memory file stays small after a year | 266 KB |
| PASS | Old plan pages are cleaned up | 58 pages on disk, 45 deals still open |
| PASS | Deal log stays a reasonable size | 0.3 MB |
| PASS | Dates without a year are read right on every day of the year | 0 wrong, e.g. [] |
| PASS | Scores spread out instead of bunching around one number | 332 matching deals, spread (std dev) 25, 13% between 60 and 75, range 15-100 |
| PASS | Winter road warnings show in January and not in July |  |
| PASS | Trips cost more in summer and holidays than in January | {1: 1331, 3: 1461, 7: 1584, 12: 1441} |
| PASS | Your settings: no Sunday check-in texts | check-ins: 0 |
| PASS | Your settings: no season reminder texts | reminders: 0 |
| PASS | Your settings: multi-deal texts only carry great deals | 8 digests, non-great entries: 0 |
| PASS | Your settings: no great deal is lost | 99 great deals, lost: [] |
| PASS | Your settings: at most one deal text a day | busiest day: 1 deal texts |
| PASS | Your settings: no deal text on a day without a new great deal | 83 days with a deal text, 84 days with a new great deal |
| PASS | Your settings: no deal is texted twice | 75 single alerts |
| PASS | Your settings: every text is about a deal (or a broken site) | texts on 84 of 365 days; {'alert': 75, 'daily': 8, 'failure': 1} |

## Month by month (texts to you)

| Month | New matching deals | Alerts | Digests | Check-ins | Reminders | Warnings | Runs |
|---|---|---|---|---|---|---|---|
| Nov 2026 | 11 | 2 | 0 | 0 | 0 | 0 | 47 |
| Dec 2026 | 9 | 1 | 0 | 0 | 0 | 0 | 176 |
| Jan 2027 | 9 | 3 | 0 | 0 | 0 | 0 | 172 |
| Feb 2027 | 34 | 10 | 0 | 0 | 0 | 0 | 148 |
| Mar 2027 | 37 | 10 | 0 | 0 | 0 | 0 | 163 |
| Apr 2027 | 35 | 8 | 0 | 0 | 0 | 0 | 162 |
| May 2027 | 52 | 9 | 0 | 0 | 0 | 0 | 166 |
| Jun 2027 | 10 | 1 | 0 | 0 | 0 | 0 | 172 |
| Jul 2027 | 8 | 1 | 0 | 0 | 0 | 1 | 177 |
| Aug 2027 | 32 | 10 | 0 | 0 | 0 | 0 | 172 |
| Sep 2027 | 38 | 11 | 0 | 0 | 0 | 0 | 165 |
| Oct 2027 | 31 | 9 | 0 | 0 | 0 | 0 | 175 |
| Nov 2027 | 26 | 8 | 0 | 0 | 0 | 0 | 118 |

## Sample texts

- Nov 23 08:04: `RV DEAL 100/100 Great: Vancouver > Seattle. Pick up Dec 1-3, 12 nights. All-in about $830-930 (RV $640, bus/ferry home $40-90, fuel+camping $110). Watch: $2,330 bond. Details + book: https://markor744.github.io/rv-deal-hunter/p/SIM-imoova-2.html`
- Nov 26 07:36: `RV DEAL 100/100 Great: Vancouver > Seattle. Pick up Jan 10-12, 3 nights. All-in about $88-190 (RV $3, bus/ferry home $40-90, fuel+camping $5). Watch: $1,000 bond. Details + book: https://markor744.github.io/rv-deal-hunter/p/SIM-imoova-5.html`
