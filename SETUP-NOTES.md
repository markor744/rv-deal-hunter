# Setup notes

Recorded during setup on 2026-11-22. No secrets, IDs or phone numbers are kept here.

## Sending number

- **Type:** local (10-digit long code). Not toll-free, not a short code.
- **Country:** Canada.
- **Registration:** none. It is not in a Twilio Messaging Service, and the account has no A2P 10DLC
  brand or campaign. Twilio has no registration process for Canadian local numbers.
- **Shared with Market Brain.** Both tools send from this number to the same mobile. Market Brain
  sends up to 3 texts a day and RV Deal Hunter up to 5.
- The account's other number is toll-free and verified for **PartyPitch** only. RV Deal Hunter
  does not use it, because its verification describes PartyPitch's texts, not deal alerts.

## Login

- RV Deal Hunter uses its own Standard API key, named "RV Deal Hunter" (US1 region), not the
  account's main Auth Token. Deleting this key does not affect Market Brain or PartyPitch.
- On this Mac the values live in the macOS Keychain, service `rv-deal-hunter`, accounts
  `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET`, `TWILIO_FROM`, `ALERT_TO`.

## Delivery

- **Test text:** "RV Deal Hunter test message." was **delivered** to the owner's mobile on
  2026-11-22 (1 segment, USD 0.0083).
- **Canadian phones:** Twilio's Canada guidelines say "Canadian mobile carriers enforce strict
  filtering on A2P messages" and recommend short codes or verified toll-free numbers for
  automated texts. From this number's last 100 texts (Oct 5 to Nov 21, 2026, all to Canadian
  phones), 64 were delivered and 36 were blocked by a carrier (error 30007). Expect some deal
  texts to be filtered, too.
- **If too many go missing:** a dedicated toll-free number, verified for RV Deal Hunter's own use,
  is the reliable fix. It costs a monthly fee and needs Twilio's verification first.
- **US numbers:** texts to US numbers from a +1 local number need an approved A2P 10DLC campaign,
  or they are blocked (error 30034). US friends stay skipped unless `us_friends: true` is set
  in `config.yaml`.
- Check each text in Twilio Console > Monitor > Logs > Messaging.

Sources: https://www.twilio.com/en-us/guidelines/ca/sms ,
https://www.twilio.com/docs/api/errors/30034 ,
https://www.twilio.com/docs/iam/api-keys/keys-in-console
