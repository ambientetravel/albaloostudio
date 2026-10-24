<?php
/* CSV export of the contacts list, same filters as the Contacts page. Members get their own only. */

declare(strict_types=1);
require __DIR__ . '/lib.php';

$u = require_login();
[$sql, $args] = lead_query($u);
$q = db()->prepare($sql . ' ORDER BY l.id DESC'); $q->execute($args);

header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="contacts-' . gmdate('Y-m-d') . '.csv"');
header('Cache-Control: no-store');
$out = fopen('php://output', 'w');
fwrite($out, "\xEF\xBB\xBF"); // Excel reads UTF-8 (Persian names) only with a BOM
$cols = ['created_at', 'name', 'email', 'phone', 'company', 'job_title', 'brand', 'owner', 'card_name', 'event', 'status', 'source', 'consent', 'note'];
fputcsv($out, $cols, ',', '"', '');
// Leading = + - @ would run as a formula in Excel; prefix with an apostrophe.
$safe = fn($v) => preg_match('/^[=+\-@\t\r]/', (string)$v) && !preg_match('/^\+[\d\s().-]+$/', (string)$v) ? "'" . $v : (string)$v;
foreach ($q as $r) fputcsv($out, array_map(fn($k) => $safe($r[$k] ?? ''), $cols), ',', '"', '');
