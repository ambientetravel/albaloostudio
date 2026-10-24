<?php
/*
 * Copy to config.php on the server and fill in. config.php is never committed
 * and never in a deploy bundle.
 */
return [
    // Public address of this install, no trailing slash. Card QR codes point here,
    // so pick it once and keep it — changing it later breaks printed QR codes.
    'base_url' => 'https://cards.boutimar.com',

    // /u/<slug> card links need mod_rewrite (DirectAdmin has it). false → card.php?u=<slug>.
    'pretty_urls' => true,

    // One-time key to create the first admin at /index.php?p=setup. 12+ random characters.
    'setup_key' => '',

    // Salt for hashing visitor IPs (rate limiting). Any random string.
    'ip_salt' => '',

    // Email the card owner when someone leaves details. An address on this domain
    // (e.g. cards@boutimar.com). Empty = no emails, contacts are still stored.
    'mail_from' => '',

    // Where the SQLite database lives. Outside public_html is better when allowed:
    // 'data_dir' => '/home/USER/teamcards-data',

    // Apple Wallet — see WALLET.md. Paths are server paths, keep them outside public_html.
    'apple_wallet' => [
        'pass_type_id' => '',          // pass.com.boutimar.card
        'team_id'      => '',          // 10-character Apple Team ID
        'p12'          => '',          // /home/USER/wallet-keys/pass.p12
        'p12_password' => '',
        // or, if the .p12 will not open (OpenSSL 3 + old export), PEM files instead:
        'cert_pem'     => '',
        'key_pem'      => '',
        'key_password' => '',
        'wwdr_pem'     => '',          // /home/USER/wallet-keys/AppleWWDRCAG4.pem
    ],

    // Google Wallet — see WALLET.md.
    'google_wallet' => [
        'issuer_id'            => '',  // numeric issuer id from pay.google.com/business/console
        'service_account_json' => '',  // /home/USER/wallet-keys/google-wallet-sa.json
    ],
];
