<?php
/*
 * Leads for the pipeline: GET, HMAC-signed exactly as orchestrator/config.py
 * signs every hop (X-Albaloo-Signature = "sha256=" + HMAC-SHA256(secret,
 * "{timestamp}." + body), X-Albaloo-Timestamp within 300 s).
 *
 *   python3 agent4_sales_closer_batch.py --leads-url https://cruise24.me/api/leads.php
 *
 * Returns {"leads":[...]} with the leads not handed out before, then moves the
 * cursor. Leads marked "suspect" (honeypot filled) are left out. ?all=1 returns
 * every lead, suspects included, and leaves the cursor alone (re-runs).
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

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
    header('Allow: GET');
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

if (($_GET['all'] ?? '') === '1') out(200, ['leads' => $leads, 'total' => count($leads)]);

// Honeypot hits stay in the file for a human to review; the pipeline only gets clean ones.
$clean = fn(array $rows) => array_values(array_filter($rows, fn($r) => empty($r['suspect'])));

$curFile = $dataDir . '/cursor.json.php';
$fh = fopen($curFile, 'c+');
if (!$fh || !flock($fh, LOCK_EX)) out(500, ['error' => 'storage']);
$raw = preg_replace('/^<\?php[^\n]*\n/', '', (string)stream_get_contents($fh));
$served = (int)((json_decode((string)$raw, true) ?: [])['served'] ?? 0);
$new = array_slice($leads, $served);
ftruncate($fh, 0); rewind($fh);
fwrite($fh, "<?php http_response_code(404); exit; ?>\n" . json_encode(['served' => count($leads), 'at' => gmdate('c')]));
flock($fh, LOCK_UN); fclose($fh);

out(200, ['leads' => $clean($new), 'total' => count($leads)]);
