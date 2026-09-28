<?php
/*
 * Cruise24 request form → one line of NDJSON on our own server.
 *
 * The record uses the lead shape the pipeline already reads (channel, from_ref,
 * message, locale, landing_path, display_name, received_at), so leads.php can
 * hand it to agent 4 without a translation step.
 *
 * Answers JSON. The page shows "thank you" only when this returns ok:true;
 * a failure is shown as a failure, never swallowed.
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

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    out(405, ['ok' => false, 'error' => 'method']);
}

$cfg = is_file(__DIR__ . '/config.php') ? (require __DIR__ . '/config.php') : [];
$dataDir = rtrim($cfg['data_dir'] ?? (__DIR__ . '/data'), '/');

// Form posts arrive urlencoded; accept JSON too, for scripts and tests.
$in = $_POST;
if (!$in && str_starts_with((string)($_SERVER['CONTENT_TYPE'] ?? ''), 'application/json')) {
    $in = json_decode((string)file_get_contents('php://input', false, null, 0, 65536), true) ?: [];
}

function field(array $in, string $k, int $max): string {
    $v = is_string($in[$k] ?? null) ? $in[$k] : '';
    $v = trim(preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', $v) ?? '');
    return mb_substr($v, 0, $max);
}

// Honeypot: a field people never see. Bots fill it; pretend success so they move on.
if (field($in, 'website', 200) !== '') {
    out(200, ['ok' => true]);
}

$name  = field($in, 'name', 120);
$email = field($in, 'email', 200);
$pax   = field($in, 'pax', 8);
$where = field($in, 'where', 80);
$when  = field($in, 'when', 200);
$notes = field($in, 'notes', 4000);
$page  = field($in, 'page', 200);
$ref   = preg_replace('/[^A-Za-z0-9-]/', '', field($in, 'sailing', 64)) ?? '';

$errors = [];
if ($name === '') $errors[] = 'name';
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) $errors[] = 'email';
if ($errors) out(400, ['ok' => false, 'error' => 'invalid', 'fields' => $errors]);
if (!in_array($pax, ['1', '2', '3', '4', '5+', ''], true)) $pax = '';
if ($page !== '' && !preg_match('#^/[A-Za-z0-9/._\-]*$#', $page)) $page = '';

if (!is_dir($dataDir) && !@mkdir($dataDir, 0750, true)) {
    out(500, ['ok' => false, 'error' => 'storage']);
}

// Rate limit: 5 requests per address per 10 minutes. The address is stored
// hashed, never in clear.
$salt = (string)($cfg['ip_salt'] ?? 'cruise24');
$ipKey = substr(hash('sha256', $salt . ($_SERVER['REMOTE_ADDR'] ?? '')), 0, 16);
$rlFile = $dataDir . '/ratelimit.json.php';
$rl = @fopen($rlFile, 'c+');
if ($rl && flock($rl, LOCK_EX)) {
    $raw = stream_get_contents($rl);
    $raw = preg_replace('/^<\?php[^\n]*\n/', '', (string)$raw);
    $hits = json_decode((string)$raw, true) ?: [];
    $now = time();
    foreach ($hits as $k => $ts) {
        $hits[$k] = array_values(array_filter((array)$ts, fn($t) => $t > $now - 600));
        if (!$hits[$k]) unset($hits[$k]);
    }
    if (count($hits[$ipKey] ?? []) >= 5) {
        flock($rl, LOCK_UN); fclose($rl);
        out(429, ['ok' => false, 'error' => 'rate']);
    }
    $hits[$ipKey][] = $now;
    ftruncate($rl, 0); rewind($rl);
    fwrite($rl, "<?php http_response_code(404); exit; ?>\n" . json_encode($hits));
    flock($rl, LOCK_UN); fclose($rl);
}

$lines = [];
if ($ref !== '')   $lines[] = 'Sailing ref: ' . $ref;
if ($pax !== '')   $lines[] = 'Travellers: ' . $pax;
if ($where !== '') $lines[] = 'Where: ' . $where;
if ($when !== '')  $lines[] = 'When: ' . $when;
if ($notes !== '') $lines[] = $notes;

$lead = [
    'id'           => bin2hex(random_bytes(8)),
    'channel'      => 'site_form',
    'site'         => 'cruise24.me',
    'from_ref'     => $email,
    'display_name' => $name,
    'message'      => implode("\n", $lines),
    'locale'       => 'en',
    'landing_path' => $page,
    'travellers'   => $pax,
    'where'        => $where,
    'when'         => $when,
    'sailing_ref'  => $ref,
    'received_at'  => gmdate('Y-m-d\TH:i:s\Z'),
];

// The .php extension and the exit line mean the file cannot be read over the
// web even if the data folder's .htaccess is ignored.
$file = $dataDir . '/leads.ndjson.php';
$fh = @fopen($file, 'a');
if (!$fh || !flock($fh, LOCK_EX)) out(500, ['ok' => false, 'error' => 'storage']);
if (filesize($file) === 0) fwrite($fh, "<?php http_response_code(404); exit; ?>\n");
$ok = fwrite($fh, json_encode($lead, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");
fflush($fh); flock($fh, LOCK_UN); fclose($fh);
if ($ok === false) out(500, ['ok' => false, 'error' => 'storage']);

// Optional: a copy to our own inbox. Off unless config.php names one.
// Never to the customer; Reply-To lets the planner answer in one click.
$to = (string)($cfg['notify_to'] ?? '');
if ($to !== '' && filter_var($to, FILTER_VALIDATE_EMAIL)) {
    $from = (string)($cfg['notify_from'] ?? $to);
    $subject = '=?UTF-8?B?' . base64_encode('Cruise24 request: ' . $name . ($ref ? " ($ref)" : '')) . '?=';
    $body = "Name: $name\nEmail: $email\n" . implode("\n", $lines) . "\n\nPage: $page\nReceived: {$lead['received_at']}\nId: {$lead['id']}\n";
    $headers = "From: $from\r\nReply-To: $email\r\nContent-Type: text/plain; charset=utf-8";
    @mail($to, $subject, $body, $headers);
}

out(200, ['ok' => true, 'id' => $lead['id']]);
