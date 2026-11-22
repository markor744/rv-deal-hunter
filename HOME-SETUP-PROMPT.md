# Finish setup on your Mac

1. Download `rv-deal-hunter.zip`. Double-click it in Finder, then move the `rv-deal-hunter`
   folder into your `Projects` folder (create `Projects` in your home folder if you don't have one).
2. Open Terminal and paste:
   ```
   cd ~/Projects/rv-deal-hunter && claude
   ```
   You should see Claude Code start up in that folder.
3. Paste everything in the box below into Claude Code.

```
This folder is "RV Deal Hunter", already built and tested (read README.md first). It watches RV
relocation deal sites and texts me through Twilio. Finish the setup steps that need my Mac.
I'm not a developer: do the technical work yourself; for anything I must click, give exact steps
and tell me what I should see. Stop after each phase, show me what works, and wait for my OK.

HARD RULES
- Never print, log, commit, or paste any secret value: Twilio SIDs, tokens, API keys or secrets, and
  phone numbers. Refer to them by name only. Never cat or echo a .env file. Read values only into a
  subprocess's environment or pipe them straight into `security` or `gh secret set`.
- Do NOT modify the Market Brain or PartyPitch apps or any of their files. Read-only.
- Store secrets on this Mac only in the macOS Keychain (service name "rv-deal-hunter"), never in
  files in this folder.

PHASE 1: Twilio (read-only discovery, then a new key, then one test text)
1. Find the "Market Brain" project folder (check ~/Projects, ~/Developer, ~/Documents, ~/Desktop,
   ~/Code, and use `mdfind -name` if needed). Inside it, find the Twilio settings for its "RV Deals"
   part (.env, .env.local, config files, or Keychain). Tell me the file path and the variable NAMES
   only. If you also find PartyPitch's Twilio settings, list those names too, but use Market Brain's.
2. Load those values into the environment of ONE command only, without displaying them, and run
   `python3 tools/twilio_check.py` (read-only: number type, country, A2P 10DLC or toll-free
   verification status). Set up a venv first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   Then explain in plain English:
   - whether texting my Canadian mobile from that number is likely to be delivered, and
   - whether using it for this purpose could conflict with how it was registered (compare its
     registered use case and description with "personal deal alerts to the account owner").
   Check Twilio's current docs before you say anything about delivery rules. If the number is a
   poor fit, recommend the safest option (for example a Canadian local number) with its current
   monthly price, verified on Twilio's site.
3. Walk me through creating a NEW Twilio API Key just for this tool: Standard type, named
   "RV Deal Hunter". Confirm the current Console clicks first. Have me store its SID and Secret
   with these two commands, which ask for the value and hide it:
     security add-generic-password -U -s rv-deal-hunter -a TWILIO_API_KEY_SID -w
     security add-generic-password -U -s rv-deal-hunter -a TWILIO_API_KEY_SECRET -w
   Copy TWILIO_ACCOUNT_SID and TWILIO_FROM (or TWILIO_MESSAGING_SERVICE_SID) from Market Brain's
   settings into the Keychain the same way, by piping, never displaying.
4. Ask me to store my mobile number myself (format +1XXXXXXXXXX), without typing it into chat:
     security add-generic-password -U -s rv-deal-hunter -a ALERT_TO -w
5. Send ONE test text with the values read from Keychain into the command's environment:
     .venv/bin/python -m rvdeals.main test-sms
   It should arrive as "RV Deal Hunter test message." Write what you learned (number type, country,
   registration status, delivery notes; NO secrets or numbers) into SETUP-NOTES.md.
   Delete state/state.json afterwards so the real runs start fresh.

PHASE 2: Check it still works
Run `.venv/bin/python -m pytest -q` (expect 55 passed) and
`DRY_RUN=1 .venv/bin/python -m rvdeals.main check` from a temporary copy of this folder, so the
real state/ stays empty. Show me the would-be texts.

PHASE 3: GitHub (repo, secrets, Pages, schedule)
1. Make sure the gh CLI is installed and logged in (brew install gh; gh auth login). Show me what to click.
2. Create a PUBLIC repo named rv-deal-hunter. Public is required for free GitHub Pages and gives free
   Actions. Before the first push, confirm that `git status` shows no .env file and no secret.
3. Set the GitHub Secrets by piping from Keychain, so nothing is displayed. For each name in
   TWILIO_ACCOUNT_SID TWILIO_API_KEY_SID TWILIO_API_KEY_SECRET TWILIO_FROM ALERT_TO:
     security find-generic-password -s rv-deal-hunter -a NAME -w | gh secret set NAME
   (Use TWILIO_MESSAGING_SERVICE_SID instead of TWILIO_FROM if that's what Market Brain uses.)
   Then `gh secret list`, which shows names only.
   Friends (optional): ask me whether to add friends now. If yes, I'll run `gh secret set ALERT_FRIENDS`
   myself and type their numbers separated by commas (hidden). Remind me to ask them first. The
   sending number is a Vancouver local number, so Canadian friends work without registration; US
   numbers are skipped unless config.yaml has us_friends: true (needs A2P 10DLC registration).
4. Set plans_base_url in config.yaml to https://<my GitHub username>.github.io/rv-deal-hunter.
   Enable GitHub Pages from branch main, folder /docs (use gh api or tell me the clicks).
5. Check that the action versions in .github/workflows/rv-deal-hunter.yml (actions/checkout@v5,
   actions/setup-python@v6) are current, and that the schedule `timezone:` key is still supported.
   Then push.
6. Trigger runs: `gh workflow run rv-deal-hunter.yml -f command=test-sms`, then
   `-f command=check`. Watch them with `gh run watch` and show me the result.
   Note: the first real check may send up to 5 texts (the daily cap) for deals already listed today.
7. Open the Pages site on my phone and confirm the plan pages contain no name, number or secret.

FINISH
Summarize what's running, when, and what each text will look like. Point me to README.md for how to
change routes and thresholds, pause texts, run a check now, rotate the key, and what to do if texts stop.
```
