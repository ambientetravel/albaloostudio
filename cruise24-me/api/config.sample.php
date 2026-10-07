<?php
/*
 * Copy to config.php on the server (same folder) and fill in.
 * config.php is never committed and never in a deploy bundle.
 */
return [
    // Shared with the pipeline: orchestrator's WEBHOOK_SIGNING_SECRET.
    // leads.php answers 503 until this is set (at least 16 characters).
    'signing_secret' => '',

    // Optional: send a copy of each request to our own inbox. Leave empty to
    // only store it. Never a customer address.
    'notify_to'   => '',
    'notify_from' => '',   // an address on the site's own domain, e.g. forms@cruise24.me

    // Salt for the hashed rate-limit key. Any random string.
    'ip_salt' => '',

    // Where leads are stored. Default: api/data (blocked from the web twice over).
    // A folder outside public_html is better when the host allows it.
    // 'data_dir' => '/home/USER/cruise24-data',
];
