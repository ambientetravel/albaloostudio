# Wallet passes — one-time setup

TeamCards builds and signs both passes itself. What it cannot do is create the
accounts: those belong to the company. Until they are filled in, the wallet
buttons show what is missing instead of failing.

Keep every key file **outside public_html**, e.g. `/home/USER/wallet-keys/`.

## Apple Wallet (.pkpass)

Needs an Apple Developer Program membership (USD 99/year — a spending decision, not set up here).

1. developer.apple.com → Certificates, IDs & Profiles → Identifiers → **+** → *Pass Type IDs*
   → `pass.com.boutimar.card`.
2. Create a certificate for that Pass Type ID (needs a CSR from Keychain Access on a Mac),
   download it, double-click, then in Keychain export cert + key as `pass.p12` with a password.
3. Download Apple's **WWDR G4** intermediate and convert it:
   `openssl x509 -inform der -in AppleWWDRCAG4.cer -out AppleWWDRCAG4.pem`
4. config.php → `apple_wallet`: `pass_type_id`, `team_id` (top-right of the developer portal),
   `p12`, `p12_password`, `wwdr_pem`.

If the server says it cannot read the .p12 (OpenSSL 3 rejects old RC2 exports), convert once:

    openssl pkcs12 -legacy -in pass.p12 -clcerts -nokeys -out pass-cert.pem
    openssl pkcs12 -legacy -in pass.p12 -nocerts -out pass-key.pem

and set `cert_pem`, `key_pem`, `key_password` instead of `p12`.

## Google Wallet

Free.

1. pay.google.com/business/console → Google Wallet API → create an issuer. Note the numeric **Issuer ID**.
2. console.cloud.google.com → enable **Google Wallet API** → IAM → Service accounts → create one → Keys →
   add JSON key → download.
3. Back in the Wallet console → Users → invite the service account's email as *Developer*.
4. config.php → `google_wallet`: `issuer_id`, `service_account_json` (path to the JSON).

Until Google approves the issuer for production, only accounts added as test users in the
Wallet console can save passes.

## What was verified

Both signing paths were run against test credentials: the Google JWT verifies against the
service-account public key, and the .pkpass manifest hashes match and its PKCS#7 signature
verifies against the signing chain. Neither has been opened on a real phone yet — that needs
the real Apple certificate and Google issuer.
