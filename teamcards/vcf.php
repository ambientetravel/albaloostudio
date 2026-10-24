<?php
/* vCard 3.0 download for a card — "Save contact" on iOS and Android. */

declare(strict_types=1);
require __DIR__ . '/lib.php';

$c = card_by_slug((string)($_GET['u'] ?? ''));
if (!$c || !$c['active']) { http_response_code(404); exit('Not found'); }

$esc = fn(string $s) => str_replace(["\\", "\n", ',', ';'], ["\\\\", '\n', '\,', '\;'], $s);
$parts = preg_split('/\s+/', trim($c['full_name'])) ?: [];
$last = count($parts) > 1 ? array_pop($parts) : '';
$lines = ['BEGIN:VCARD', 'VERSION:3.0', 'N:' . $esc($last) . ';' . $esc(implode(' ', $parts)) . ';;;', 'FN:' . $esc($c['full_name']), 'ORG:' . $esc($c['co_name'])];
if ($c['title'])    $lines[] = 'TITLE:' . $esc($c['title']);
if ($c['phone'])    $lines[] = 'TEL;TYPE=CELL,VOICE:' . $esc($c['phone']);
if ($c['whatsapp'] && $c['whatsapp'] !== $c['phone']) $lines[] = 'TEL;TYPE=WHATSAPP:' . $esc($c['whatsapp']);
if ($c['email'])    $lines[] = 'EMAIL;TYPE=INTERNET,WORK:' . $esc($c['email']);
if ($c['co_phone'] && $c['co_phone'] !== $c['phone']) $lines[] = 'TEL;TYPE=WORK,VOICE:' . $esc($c['co_phone']);
if ($c['co_email'] && $c['co_email'] !== $c['email']) $lines[] = 'EMAIL;TYPE=INTERNET:' . $esc($c['co_email']);
$site = $c['website'] ?: $c['co_website'];
if ($site)          $lines[] = 'URL:' . $esc($site);
foreach (card_blocks($c) as $b) {
    if ($b['type'] !== 'socials' || empty($b['show'])) continue;
    foreach ($b['socials'] as $net => $val) if ($u = social_url($net, $val)) $lines[] = 'X-SOCIALPROFILE;TYPE=' . $net . ':' . $esc($u);
}
if ($c['co_address']) $lines[] = 'ADR;TYPE=WORK:;;' . $esc($c['co_address']) . ';;;;';
$lines[] = 'NOTE:' . $esc(card_url($c['slug']));
$photo = $c['photo'] ? __DIR__ . '/uploads/' . basename($c['photo']) : '';
if ($photo && is_file($photo) && filesize($photo) < 600000) {
    $type = str_ends_with($photo, '.png') ? 'PNG' : 'JPEG';
    if (!str_ends_with($photo, '.webp')) $lines[] = "PHOTO;ENCODING=b;TYPE=$type:" . base64_encode((string)file_get_contents($photo));
}
$lines[] = 'END:VCARD';

// RFC 6350 line folding at 75 octets.
$out = '';
foreach ($lines as $l) { while (strlen($l) > 75) { $out .= substr($l, 0, 75) . "\r\n "; $l = substr($l, 75); } $out .= $l . "\r\n"; }

header('Content-Type: text/vcard; charset=utf-8');
header('Content-Disposition: attachment; filename="' . preg_replace('/[^a-z0-9-]/', '', $c['slug']) . '.vcf"');
header('Cache-Control: no-cache');
echo $out;
