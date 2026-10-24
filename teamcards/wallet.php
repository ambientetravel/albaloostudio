<?php
/*
 * Wallet passes for a card: the person's own business card in Apple Wallet /
 * Google Wallet, QR on the front, so it can be shown at a stand without
 * unlocking anything but the wallet.
 *
 *   wallet.php?id=<card>&t=apple   → signed .pkpass (needs an Apple Pass Type ID certificate)
 *   wallet.php?id=<card>&t=google  → redirect to "Save to Google Wallet" (needs a Google Wallet issuer + service account)
 *
 * Neither works without credentials only you can create; until they are in
 * config.php this page says exactly which are missing instead of failing.
 */

declare(strict_types=1);
require __DIR__ . '/lib.php';

final class WalletNotConfigured extends RuntimeException {}

require_login();
$c = card_by_id((int)($_GET['id'] ?? 0));
if (!$c || !can_edit_card($c)) { http_response_code(404); exit('Not found'); }
$type = ($_GET['t'] ?? '') === 'google' ? 'google' : 'apple';
$url = card_url($c['slug']);

try {
    $type === 'apple' ? apple_pass($c, $url) : google_pass($c, $url);
} catch (WalletNotConfigured $e) {
    page_head('Wallet');
    echo '<h1>' . ($type === 'apple' ? 'Apple' : 'Google') . ' Wallet is not set up yet</h1><p>' . h($e->getMessage()) . '</p>'
       . '<p>See <b>WALLET.md</b> in the TeamCards folder for the one-time setup. Until then, the printed QR and the “Save contact” button on the card do the same job.</p>'
       . '<p><a class="btn" href="index.php?p=cards">Back to cards</a></p>';
    page_foot();
} catch (Throwable $e) {
    http_response_code(500);
    page_head('Wallet error');
    echo '<h1>Could not build the pass</h1><p class="err">' . h($e->getMessage()) . '</p>';
    page_foot();
}

/** [background, foreground, label] hex for the card's wallet style. */
function wallet_colors(array $c): array {
    return match ($c['wstyle']) {
        'dark'  => ['#2b2f33', '#ffffff', $c['accent']],
        'white' => ['#ffffff', '#14202b', $c['color']],
        default => [$c['color'], '#ffffff', $c['accent']],
    };
}

function rgb(string $hex): string {
    [$r, $g, $b] = sscanf($hex, '#%02x%02x%02x') ?: [0, 0, 0];
    return "rgb($r, $g, $b)";
}

/** Brand-coloured square with the brand initial — Apple requires an icon even with a logo. */
function brand_png(array $c, int $w, int $h, bool $initialOnly = true): string {
    $im = imagecreatetruecolor($w, $h);
    [$r, $g, $b] = sscanf(wallet_colors($c)[0], '#%02x%02x%02x') ?: [15, 61, 94];
    imagefill($im, 0, 0, imagecolorallocate($im, $r, $g, $b));
    $logo = $c['logo'] ? __DIR__ . '/uploads/' . basename($c['logo']) : '';
    if ($logo && is_file($logo) && ($src = @imagecreatefromstring((string)file_get_contents($logo)))) {
        $sw = imagesx($src); $sh = imagesy($src); $s = min($w / $sw, $h / $sh);
        $dw = (int)($sw * $s); $dh = (int)($sh * $s);
        imagecopyresampled($im, $src, (int)(($w - $dw) / 2), (int)(($h - $dh) / 2), 0, 0, $dw, $dh, $sw, $sh);
    } else {
        $txt = $initialOnly ? mb_strtoupper(mb_substr($c['brand_name'], 0, 1)) : $c['brand_name'];
        [$fr, $fg, $fb] = sscanf(wallet_colors($c)[1], '#%02x%02x%02x');
        $white = imagecolorallocate($im, $fr, $fg, $fb); $f = 5;
        imagestring($im, $f, (int)(($w - imagefontwidth($f) * strlen($txt)) / 2), (int)(($h - imagefontheight($f)) / 2), $txt, $white);
    }
    ob_start(); imagepng($im); return (string)ob_get_clean();
}

function photo_png(array $c, int $size): ?string {
    $p = $c['photo'] ? __DIR__ . '/uploads/' . basename($c['photo']) : '';
    if (!$p || !is_file($p) || !($src = @imagecreatefromstring((string)file_get_contents($p)))) return null;
    $sw = imagesx($src); $sh = imagesy($src); $s = min($sw, $sh);
    $im = imagecreatetruecolor($size, $size);
    imagecopyresampled($im, $src, 0, 0, (int)(($sw - $s) / 2), (int)(($sh - $s) / 2), $size, $size, $s, $s);
    ob_start(); imagepng($im); return (string)ob_get_clean();
}

/* ── Apple Wallet (.pkpass) ──────────────────────────────────────────── */

function apple_pass(array $c, string $url): never {
    $a = cfg('apple_wallet', []);
    $missing = array_filter(['pass_type_id', 'team_id', 'wwdr_pem'], fn($k) => empty($a[$k]));
    if (empty($a['p12']) && (empty($a['cert_pem']) || empty($a['key_pem']))) $missing[] = 'p12 (or cert_pem + key_pem)';
    if ($missing) throw new WalletNotConfigured('config.php → apple_wallet is missing: ' . implode(', ', $missing) . '.');

    if (!empty($a['p12'])) {
        if (!openssl_pkcs12_read((string)file_get_contents($a['p12']), $p12, (string)($a['p12_password'] ?? '')))
            throw new RuntimeException('Cannot read the .p12 (wrong password, or an old RC2-encrypted export — see WALLET.md to convert it to PEM).');
        [$cert, $key] = [$p12['cert'], $p12['pkey']];
    } else {
        $cert = (string)file_get_contents($a['cert_pem']);
        $key = openssl_pkey_get_private((string)file_get_contents($a['key_pem']), (string)($a['key_password'] ?? ''));
        if (!$key) throw new RuntimeException('Cannot read key_pem.');
    }

    $field = fn($k, $label, $v) => ['key' => $k, 'label' => $label, 'value' => $v];
    $wc = wallet_colors($c);
    $pass = [
        'formatVersion' => 1, 'passTypeIdentifier' => $a['pass_type_id'], 'teamIdentifier' => $a['team_id'],
        'serialNumber' => 'card-' . $c['id'] . '-' . $c['slug'], 'organizationName' => $c['co_name'],
        'description' => $c['co_name'] . ' business card — ' . $c['full_name'], 'logoText' => $c['co_name'],
        'backgroundColor' => rgb($wc[0]), 'foregroundColor' => rgb($wc[1]), 'labelColor' => rgb($wc[2]),
        'sharingProhibited' => false,
        'generic' => [
            'primaryFields' => [$field('name', $c['title'] ?: 'Name', $c['full_name'])],
            'secondaryFields' => array_values(array_filter([$c['phone'] ? $field('phone', 'Phone', $c['phone']) : null, $c['email'] ? $field('email', 'Email', $c['email']) : null])),
            'auxiliaryFields' => $c['co_address'] ? [$field('address', 'Address', $c['co_address'])] : [],
            'backFields' => array_values(array_filter([
                $field('card', 'Card', $url),
                ($c['website'] ?: $c['co_website']) ? $field('web', 'Website', $c['website'] ?: $c['co_website']) : null,
                $c['co_phone'] ? $field('office', 'Office', $c['co_phone']) : null,
                $c['bio'] ? $field('bio', 'About', $c['bio']) : null,
            ])),
        ],
        'barcodes' => [['format' => 'PKBarcodeFormatQR', 'message' => $url, 'messageEncoding' => 'iso-8859-1', 'altText' => 'Scan to connect']],
    ];

    $files = ['pass.json' => json_encode($pass, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
              'icon.png' => brand_png($c, 29, 29), 'icon@2x.png' => brand_png($c, 58, 58), 'icon@3x.png' => brand_png($c, 87, 87),
              'logo.png' => brand_png($c, 160, 50, false), 'logo@2x.png' => brand_png($c, 320, 100, false)];
    if ($t = photo_png($c, 90)) { $files['thumbnail.png'] = $t; $files['thumbnail@2x.png'] = photo_png($c, 180); }

    $manifest = json_encode(array_map('sha1', $files), JSON_UNESCAPED_SLASHES);
    $tmp = sys_get_temp_dir() . '/tc-' . bin2hex(random_bytes(6));
    file_put_contents("$tmp.m", $manifest);
    $ok = openssl_pkcs7_sign("$tmp.m", "$tmp.s", $cert, $key, [], PKCS7_BINARY | PKCS7_DETACHED, $a['wwdr_pem']);
    $smime = (string)@file_get_contents("$tmp.s");
    @unlink("$tmp.m"); @unlink("$tmp.s");
    if (!$ok) throw new RuntimeException('Signing failed: ' . openssl_error_string());
    // S/MIME → raw DER: the base64 body of the smime.p7s part.
    if (!preg_match('/filename="?smime\.p7s"?\R\R(.+?)\R\R?-{2,}/s', $smime, $m)) throw new RuntimeException('Unexpected signature format.');
    $files['manifest.json'] = $manifest;
    $files['signature'] = base64_decode(preg_replace('/\s+/', '', $m[1]));

    $zipPath = "$tmp.zip"; $zip = new ZipArchive();
    $zip->open($zipPath, ZipArchive::CREATE);
    foreach ($files as $n => $data) $zip->addFromString($n, $data);
    $zip->close();
    header('Content-Type: application/vnd.apple.pkpass');
    header('Content-Disposition: attachment; filename="' . $c['slug'] . '.pkpass"');
    header('Content-Length: ' . filesize($zipPath));
    readfile($zipPath); @unlink($zipPath);
    exit;
}

/* ── Google Wallet (Save link with signed JWT) ───────────────────────── */

function b64url(string $s): string { return rtrim(strtr(base64_encode($s), '+/', '-_'), '='); }

function google_pass(array $c, string $url): never {
    $g = cfg('google_wallet', []);
    if (empty($g['issuer_id']) || empty($g['service_account_json']) || !is_file((string)$g['service_account_json']))
        throw new WalletNotConfigured('config.php → google_wallet needs issuer_id and service_account_json (path to the key file).');
    $sa = json_decode((string)file_get_contents($g['service_account_json']), true);
    if (empty($sa['client_email']) || empty($sa['private_key'])) throw new RuntimeException('service_account_json is not a service-account key file.');

    $iss = (string)$g['issuer_id'];
    $classId = "$iss.teamcards_" . preg_replace('/[^a-z0-9_]/', '_', strtolower((string)$c['brand_id']));
    $tl = fn(string $v) => ['defaultValue' => ['language' => 'en', 'value' => $v]];
    $object = [
        'id' => "$iss.card_" . $c['id'] . '_' . preg_replace('/[^A-Za-z0-9_.-]/', '_', $c['slug']),
        'classId' => $classId, 'state' => 'ACTIVE',
        'cardTitle' => $tl($c['co_name']), 'header' => $tl($c['full_name']), 'subheader' => $tl($c['title'] ?: 'Business card'),
        'hexBackgroundColor' => wallet_colors($c)[0],
        'barcode' => ['type' => 'QR_CODE', 'value' => $url, 'alternateText' => 'Scan to connect'],
        'textModulesData' => array_values(array_filter([
            $c['phone'] ? ['id' => 'phone', 'header' => 'Phone', 'body' => $c['phone']] : null,
            $c['email'] ? ['id' => 'email', 'header' => 'Email', 'body' => $c['email']] : null,
            $c['co_address'] ? ['id' => 'address', 'header' => 'Address', 'body' => $c['co_address']] : null,
        ])),
        'linksModuleData' => ['uris' => [['uri' => $url, 'description' => 'Digital card', 'id' => 'card']]],
    ];
    if ($c['logo']) $object['logo'] = ['sourceUri' => ['uri' => photo_url($c['logo'])]];
    if ($c['photo']) $object['heroImage'] = ['sourceUri' => ['uri' => photo_url($c['photo'])]];

    $claims = ['iss' => $sa['client_email'], 'aud' => 'google', 'typ' => 'savetowallet', 'iat' => time(),
               'origins' => [parse_url(base_url(), PHP_URL_SCHEME) . '://' . parse_url(base_url(), PHP_URL_HOST)],
               'payload' => ['genericClasses' => [['id' => $classId]], 'genericObjects' => [$object]]];
    $head = b64url(json_encode(['alg' => 'RS256', 'typ' => 'JWT']));
    $body = b64url(json_encode($claims, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));
    if (!openssl_sign("$head.$body", $sig, $sa['private_key'], OPENSSL_ALGO_SHA256)) throw new RuntimeException('JWT signing failed.');
    redirect('https://pay.google.com/gp/v/save/' . "$head.$body." . b64url($sig));
}
