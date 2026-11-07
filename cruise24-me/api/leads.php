<?php
/*
 * Leads for the pipeline: GET, HMAC-signed exactly as orchestrator/config.py
 * signs every hop (X-Albaloo-Signature = "sha256=" + HMAC-SHA256(secret,
 * "{timestamp}." + body), X-Albaloo-Timestamp within 300 s).
 *
 *   python3 agent4_sales_closer_batch.py --leads-url https://cruise24.me/api/leads.php
 *
 * GET returns {"leads":[...], "seqs":[...], "next":N}: the leads not yet acknowledged
 * (suspects, i.e. honeypot filled, left out), each with its position in the file.
 *
 *   - A caller that sends "X-Albaloo-Ack: 1" (the Closer) keeps the cursor where it
 *     is. It POSTs {"ack": N}, signed over that body, once the leads are safely in the
 *     Ops app; only then does the cursor move. A run that dies in between loses nothing:
 *     the same leads are served again.
 *   - A caller without the header gets the old behaviour: the cursor moves on the GET.
 *
 * ?all=1 returns every lead, suspects included, and leaves the cursor alone (re-runs).
 *
 * No secret configured → 503. Customer messages are never served unsigned.
 */

declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

function out(int $code, array $body): never {
    http_response_code($code);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

$method = $_SERVER['REQUEST_METHOD'] ?? '';
if ($method !== 'GET' && $method !== 'POST') {
    header('Allow: GET, POST');
    out(405, ['error' => 'method']);
}

$cfg = is_file(__DIR__ . '/config.php') ? (require __DIR__ . '/config.php') : [];
$secret = (string)($cfg['signing_secret'] ?? '');
if (strlen($secret) < 16) out(503, ['error' => 'not configured']);

$sig = (string)($_SERVER['HTTP_X_ALBALOO_SIGNATURE'] ?? '');
$ts  = (string)($_SERVER['HTTP_X_ALBALOO_TIMESTAMP'] ?? '');
if ($sig === '' || !ctype_digit($ts)) out(401, ['error' => 'unsigned']);
if (abs(time() - (int)$ts) > 300) out(401, ['error' => 'stale']);
$body = (string)file_get_contents('php://input');
$expected = 'sha256=' . hash_hmac('sha256', $ts . '.' . $body, $secret);
if (!hash_equals($expected, $sig)) out(401, ['error' => 'signature']);

$dataDir = rtrim($cfg['data_dir'] ?? (__DIR__ . '/data'), '/');
$file = $dataDir . '/leads.ndjson.php';
$leads = [];
if (is_file($file)) {
    foreach (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        if (str_starts_with($line, '<?php')) continue;
        $row = json_decode($line, true);
        if (is_array($row)) $leads[] = $row;
    }
}

$curFile = $dataDir . '/cursor.json.php';
$readCursor = function ($fh): int {
    rewind($fh);
    $raw = preg_replace('/^<\?php[^\n]*\n/', '', (string)stream_get_contents($fh));
    return (int)((json_decode((string)$raw, true) ?: [])['served'] ?? 0);
};
$writeCursor = function ($fh, int $served): void {
    ftruncate($fh, 0); rewind($fh);
    fwrite($fh, "<?php http_response_code(404); exit; ?>\n" . json_encode(['served' => $served, 'at' => gmdate('c')]));
};

if ($method === 'POST') {
    // Acknowledge: the signature above covered this body, so N cannot be altered in transit.
    $ack = json_decode($body, true);
    if (!is_array($ack) || !isset($ack['ack']) || !is_int($ack['ack']) || $ack['ack'] < 0) out(400, ['error' => 'ack']);
    $fh = fopen($curFile, 'c+');
    if (!$fh || !flock($fh, LOCK_EX)) out(500, ['error' => 'storage']);
    $served = max($readCursor($fh), min($ack['ack'], count($leads)));   // forward only, never past the file
    $writeCursor($fh, $served);
    flock($fh, LOCK_UN); fclose($fh);
    out(200, ['served' => $served, 'total' => count($leads)]);
}

if (($_GET['all'] ?? '') === '1') out(200, ['leads' => $leads, 'total' => count($leads)]);

// Honeypot hits stay in the file for a human to review; the pipeline only gets clean ones.

$deferred = ($_SERVER['HTTP_X_ALBALOO_ACK'] ?? '') === '1';
$fh = fopen($curFile, 'c+');
if (!$fh || !flock($fh, LOCK_EX)) out(500, ['error' => 'storage']);
$served = $readCursor($fh);
$new = array_slice($leads, $served, null, true);          // keys are file positions (0-based)
if (!$deferred) $writeCursor($fh, count($leads));          // old behaviour: forget on the GET
flock($fh, LOCK_UN); fclose($fh);

$clean = array_filter($new, fn($r) => empty($r['suspect']));
$resp = ['leads' => array_values($clean), 'total' => count($leads)];
if ($deferred) {
    $resp['seqs'] = array_map(fn($k) => $k + 1, array_keys($clean));   // 1-based: the number to ack to include it
    $resp['next'] = count($leads);
}
out(200, $resp);
