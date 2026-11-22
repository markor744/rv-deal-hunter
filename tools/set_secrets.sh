#!/bin/zsh
# Stores each value as a GitHub Secret. gh asks for each value and hides what you paste.
# Run from the rv-deal-hunter folder:  zsh tools/set_secrets.sh
set -e
for name in TWILIO_ACCOUNT_SID TWILIO_API_KEY_SID TWILIO_API_KEY_SECRET TWILIO_FROM ALERT_TO; do
  echo "Paste the value for $name, then press Enter (nothing will show):"
  gh secret set "$name"
done
echo "Done. Secret names now on GitHub:"; gh secret list
