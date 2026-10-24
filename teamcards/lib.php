<?php
/*
 * TeamCards — shared core: config, SQLite, auth, CSRF, layout.
 *
 * Self-hosted replacement for a HeyDrop-style digital business card +
 * lead capture tool. One install serves every brand (Boutimar, Ambiente
 * Travel, Cruise24 …); each card belongs to one person and one brand, and
 * every contact captured through a card is attributed to both.
 */

declare(strict_types=1);

const TC_VERSION = '1.1.0';

$CFG = is_file(__DIR__ . '/config.php') ? (require __DIR__ . '/config.php') : [];

function cfg(string $key, mixed $default = null): mixed {
    global $CFG;
    return $CFG[$key] ?? $default;
}

function base_url(): string {
    $b = (string)cfg('base_url', '');
    if ($b !== '') return rtrim($b, '/');
    $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
    $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    return $scheme . '://' . ($_SERVER['HTTP_HOST'] ?? 'localhost') . $dir;
}

function card_url(string $slug): string {
    return base_url() . (cfg('pretty_urls', true) ? '/u/' : '/card.php?u=') . rawurlencode($slug);
}

function data_dir(): string {
    $d = rtrim((string)cfg('data_dir', __DIR__ . '/data'), '/');
    if (!is_dir($d)) mkdir($d, 0750, true);
    return $d;
}

function db(): PDO {
    static $pdo = null;
    if ($pdo) return $pdo;
    $pdo = new PDO('sqlite:' . data_dir() . '/teamcards.sqlite');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;');
    migrate($pdo);
    return $pdo;
}

function migrate(PDO $pdo): void {
    $pdo->exec(<<<SQL
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        name TEXT NOT NULL, password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member', notify INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE TABLE IF NOT EXISTS brands (
        id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
        domain TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT '#0f3d5e',
        accent TEXT NOT NULL DEFAULT '#e8b04a', logo TEXT NOT NULL DEFAULT '',
        tagline TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        brand_id INTEGER NOT NULL REFERENCES brands(id), slug TEXT NOT NULL UNIQUE,
        full_name TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '', whatsapp TEXT NOT NULL DEFAULT '',
        website TEXT NOT NULL DEFAULT '', linkedin TEXT NOT NULL DEFAULT '',
        instagram TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
        bio TEXT NOT NULL DEFAULT '', photo TEXT NOT NULL DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1, views INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY, card_id INTEGER REFERENCES cards(id) ON DELETE SET NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        brand_id INTEGER REFERENCES brands(id) ON DELETE SET NULL,
        name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
        company TEXT NOT NULL DEFAULT '', job_title TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '', event TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT 'qr', status TEXT NOT NULL DEFAULT 'new',
        consent INTEGER NOT NULL DEFAULT 0, suspect INTEGER NOT NULL DEFAULT 0,
        ip_hash TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE INDEX IF NOT EXISTS leads_user ON leads(user_id, created_at);
    CREATE INDEX IF NOT EXISTS leads_brand ON leads(brand_id, created_at);
    CREATE INDEX IF NOT EXISTS leads_ip ON leads(ip_hash, created_at);
    SQL);
    // v1.1 columns. Card company/design fields left '' inherit the brand's.
    add_cols($pdo, 'cards', ['company_name' => "TEXT NOT NULL DEFAULT ''", 'company_website' => "TEXT NOT NULL DEFAULT ''",
        'company_address' => "TEXT NOT NULL DEFAULT ''", 'company_phone' => "TEXT NOT NULL DEFAULT ''", 'company_email' => "TEXT NOT NULL DEFAULT ''",
        'template' => "TEXT NOT NULL DEFAULT ''", 'wallet_style' => "TEXT NOT NULL DEFAULT ''", 'blocks' => "TEXT NOT NULL DEFAULT ''",
        'auto_open' => 'INTEGER NOT NULL DEFAULT 0', 'updated_at' => "TEXT NOT NULL DEFAULT ''"]);
    add_cols($pdo, 'brands', ['company_name' => "TEXT NOT NULL DEFAULT ''", 'company_address' => "TEXT NOT NULL DEFAULT ''",
        'company_phone' => "TEXT NOT NULL DEFAULT ''", 'company_email' => "TEXT NOT NULL DEFAULT ''",
        'template' => "TEXT NOT NULL DEFAULT 'classic'", 'wallet_style' => "TEXT NOT NULL DEFAULT 'brand'"]);
    add_cols($pdo, 'users', ['status' => "TEXT NOT NULL DEFAULT 'active'", 'invite_token' => "TEXT NOT NULL DEFAULT ''",
        'invite_expires' => "TEXT NOT NULL DEFAULT ''", 'phone' => "TEXT NOT NULL DEFAULT ''"]);
    if ((int)$pdo->query('SELECT COUNT(*) FROM brands')->fetchColumn() === 0) {
        // Names and domains only. Colours are placeholders — edit under Brands.
        $seed = $pdo->prepare('INSERT INTO brands (slug, name, domain, color, accent) VALUES (?,?,?,?,?)');
        foreach ([
            ['boutimar', 'Boutimar', 'boutimar.com', '#0b3954', '#e0a458'],
            ['ambiente', 'Ambiente Travel', 'ambientetravel.com', '#1d3a2f', '#c9a227'],
            ['cruise24', 'Cruise24', 'cruise24.me', '#0a2a4a', '#3fa7d6'],
        ] as $b) $seed->execute($b);
    }
}

function add_cols(PDO $pdo, string $table, array $cols): void {
    $have = array_column($pdo->query("PRAGMA table_info($table)")->fetchAll(PDO::FETCH_ASSOC), 'name');
    foreach ($cols as $name => $ddl) if (!in_array($name, $have, true)) $pdo->exec("ALTER TABLE $table ADD COLUMN $name $ddl");
}

/* ── helpers ─────────────────────────────────────────────────────────── */

function h(?string $s): string { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }

function clean(string $s, int $max = 200): string {
    $s = trim(preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', $s) ?? '');
    return mb_substr($s, 0, $max);
}

function post(string $k, int $max = 200): string { return clean((string)($_POST[$k] ?? ''), $max); }

function slugify(string $s): string {
    $s = strtolower(trim(preg_replace('/[^A-Za-z0-9]+/', '-', iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $s) ?: $s) ?? '', '-'));
    return $s !== '' ? substr($s, 0, 48) : 'card-' . bin2hex(random_bytes(3));
}

function unique_slug(string $base, int $exceptId = 0): string {
    $slug = slugify($base); $try = $slug; $n = 2;
    $q = db()->prepare('SELECT id FROM cards WHERE slug = ? AND id != ?');
    while (true) { $q->execute([$try, $exceptId]); if (!$q->fetch()) return $try; $try = $slug . '-' . $n++; }
}

function ip_hash(): string {
    return hash('sha256', (string)cfg('ip_salt', 'teamcards') . '|' . ($_SERVER['REMOTE_ADDR'] ?? ''));
}

function redirect(string $to): never { header('Location: ' . $to); exit; }

function flash(?string $msg = null): ?string {
    if ($msg !== null) { $_SESSION['flash'] = $msg; return null; }
    $m = $_SESSION['flash'] ?? null; unset($_SESSION['flash']); return $m;
}

/* ── session, auth, csrf ─────────────────────────────────────────────── */

function start_session(): void {
    if (session_status() === PHP_SESSION_ACTIVE) return;
    session_name('tc_sess');
    session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'httponly' => true, 'samesite' => 'Lax',
        'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off']);
    session_start();
}

function me(): ?array {
    start_session();
    if (empty($_SESSION['uid'])) return null;
    static $u = false;
    if ($u === false) {
        $q = db()->prepare('SELECT * FROM users WHERE id = ?'); $q->execute([$_SESSION['uid']]);
        $u = $q->fetch() ?: null;
    }
    return $u;
}

function is_admin(): bool { return (me()['role'] ?? '') === 'admin'; }

function require_login(): array {
    $u = me();
    if (!$u) redirect('index.php?p=login');
    return $u;
}

function require_admin(): array {
    $u = require_login();
    if ($u['role'] !== 'admin') { http_response_code(403); exit('Admins only.'); }
    return $u;
}

function csrf(): string {
    start_session();
    return $_SESSION['csrf'] ??= bin2hex(random_bytes(16));
}

function csrf_field(): string { return '<input type="hidden" name="csrf" value="' . h(csrf()) . '">'; }

function check_csrf(): void {
    start_session();
    if (!hash_equals($_SESSION['csrf'] ?? '', (string)($_POST['csrf'] ?? ''))) { http_response_code(400); exit('Form expired — go back and reload.'); }
}

/* ── data access ─────────────────────────────────────────────────────── */

function brands(): array { return db()->query('SELECT * FROM brands ORDER BY name')->fetchAll(); }

function brand(int $id): ?array {
    $q = db()->prepare('SELECT * FROM brands WHERE id = ?'); $q->execute([$id]); return $q->fetch() ?: null;
}

const CARD_BRAND_COLS = 'b.name AS brand_name, b.domain AS brand_domain, b.color, b.accent, b.logo, b.tagline,
    b.company_name AS brand_company_name, b.company_address AS brand_company_address, b.company_phone AS brand_company_phone,
    b.company_email AS brand_company_email, b.template AS brand_template, b.wallet_style AS brand_wallet_style';

function card_by_slug(string $slug): ?array {
    $q = db()->prepare("SELECT c.*, " . CARD_BRAND_COLS . "
        FROM cards c JOIN brands b ON b.id = c.brand_id WHERE c.slug = ?");
    $q->execute([$slug]); $c = $q->fetch(); return $c ? card_effective($c) : null;
}

function card_by_id(int $id): ?array {
    $q = db()->prepare("SELECT c.*, " . CARD_BRAND_COLS . "
        FROM cards c JOIN brands b ON b.id = c.brand_id WHERE c.id = ?");
    $q->execute([$id]); $c = $q->fetch(); return $c ? card_effective($c) : null;
}

/** A member may touch their own cards; an admin any. */
function can_edit_card(array $card): bool { $u = me(); return $u && ($u['role'] === 'admin' || (int)$card['user_id'] === (int)$u['id']); }

function photo_url(string $file): string { return $file === '' ? '' : base_url() . '/uploads/' . rawurlencode($file); }

/** Validate an uploaded image by content (not by name) and store it under a random name. */
function save_upload(string $field): ?string {
    if (empty($_FILES[$field]) || ($_FILES[$field]['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_NO_FILE) return null;
    $f = $_FILES[$field];
    if ($f['error'] !== UPLOAD_ERR_OK || $f['size'] > 4 * 1024 * 1024) throw new RuntimeException('Image must be under 4 MB.');
    $info = @getimagesize($f['tmp_name']);
    $ext = match ($info[2] ?? 0) { IMAGETYPE_JPEG => 'jpg', IMAGETYPE_PNG => 'png', IMAGETYPE_WEBP => 'webp', default => null };
    if (!$ext) throw new RuntimeException('Only JPG, PNG or WebP images.');
    $name = bin2hex(random_bytes(10)) . '.' . $ext;
    if (!move_uploaded_file($f['tmp_name'], __DIR__ . '/uploads/' . $name)) throw new RuntimeException('Upload failed.');
    return $name;
}

/** Re-encode an uploaded photo as JPEG, longest side ≤ 1600 px (keeps API uploads small). Returns [path, mime]. */
function shrink_image(string $tmp): array {
    $src = @imagecreatefromstring((string)file_get_contents($tmp));
    if (!$src) throw new RuntimeException('That file is not a readable image.');
    $w = imagesx($src); $h = imagesy($src); $s = min(1, 1600 / max($w, $h));
    $dst = imagecreatetruecolor(max(1, (int)($w * $s)), max(1, (int)($h * $s)));
    imagecopyresampled($dst, $src, 0, 0, 0, 0, imagesx($dst), imagesy($dst), $w, $h);
    $out = tempnam(sys_get_temp_dir(), 'tcscan');
    imagejpeg($dst, $out, 85);
    return [$out, 'image/jpeg'];
}

/* ── layout ──────────────────────────────────────────────────────────── */

function page_head(string $title, string $bodyClass = ''): void {
    $u = me();
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<meta name="robots" content="noindex,nofollow"><title>' . h($title) . ' · TeamCards</title>'
       . '<link rel="stylesheet" href="assets/app.css?v=' . TC_VERSION . '"></head><body class="' . h($bodyClass) . '">';
    if ($u) {
        $p = $_GET['p'] ?? 'home';
        $nav = ['home' => 'Dashboard', 'cards' => 'Cards', 'leads' => 'Contacts', 'scan' => 'Quick add'];
        if ($u['role'] === 'admin') $nav += ['team' => 'Team', 'brands' => 'Brands', 'settings' => 'Settings'];
        echo '<header class="top"><a class="logo" href="index.php">TeamCards</a><nav>';
        foreach ($nav as $k => $v) echo '<a href="index.php?p=' . $k . '"' . ($p === $k ? ' class="on"' : '') . '>' . h($v) . '</a>';
        echo '</nav><div class="who">' . h($u['name']) . ' · <a href="index.php?p=account">Account</a> · '
           . '<form method="post" action="index.php?p=logout" class="inline">' . csrf_field() . '<button class="link">Sign out</button></form></div></header>';
    }
    echo '<main class="wrap">';
    if ($m = flash()) echo '<div class="flash">' . h($m) . '</div>';
}

function page_foot(): void {
    echo '</main><script src="assets/qrcode.js"></script><script src="assets/app.js?v=' . TC_VERSION . '"></script></body></html>';
}

/* ── contacts ────────────────────────────────────────────────────────── */

const LEAD_STATUSES = ['new', 'contacted', 'qualified', 'won', 'lost'];

/** Shared with export.php: the filtered contact query for the current user. */
function lead_query(array $u): array {
    $w = ['1=1']; $a = [];
    if (!is_admin()) { $w[] = 'l.user_id = ?'; $a[] = $u['id']; }
    elseif (!empty($_GET['owner'])) { $w[] = 'l.user_id = ?'; $a[] = (int)$_GET['owner']; }
    if (!empty($_GET['brand'])) { $w[] = 'l.brand_id = ?'; $a[] = (int)$_GET['brand']; }
    if (!empty($_GET['status'])) { $w[] = 'l.status = ?'; $a[] = (string)$_GET['status']; }
    if (!empty($_GET['event'])) { $w[] = 'l.event = ?'; $a[] = (string)$_GET['event']; }
    if (!empty($_GET['from'])) { $w[] = 'l.created_at >= ?'; $a[] = (string)$_GET['from']; }
    if (!empty($_GET['to'])) { $w[] = 'l.created_at < date(?, \'+1 day\')'; $a[] = (string)$_GET['to']; }
    if (($_GET['q'] ?? '') !== '') { $w[] = '(l.name LIKE ? OR l.email LIKE ? OR l.company LIKE ? OR l.phone LIKE ? OR l.note LIKE ?)'; array_push($a, ...array_fill(0, 5, '%' . $_GET['q'] . '%')); }
    $w[] = empty($_GET['suspect']) ? 'l.suspect = 0' : 'l.suspect = 1';
    return ['SELECT l.*, b.name brand, u.name owner, c.full_name card_name FROM leads l LEFT JOIN brands b ON b.id = l.brand_id
        LEFT JOIN users u ON u.id = l.user_id LEFT JOIN cards c ON c.id = l.card_id WHERE ' . implode(' AND ', $w), $a];
}

/** Insert from $_POST fields plus the given overrides; returns the new id and fires the webhook. */
function insert_lead(array $over): int {
    $row = array_merge(['name' => post('name', 120), 'email' => post('email', 160), 'phone' => post('phone', 40), 'company' => post('company', 120),
            'job_title' => post('job_title', 120), 'note' => post('note', 2000), 'event' => post('event', 120), 'ip_hash' => ip_hash()], $over);
    db()->prepare('INSERT INTO leads (' . implode(',', array_keys($row)) . ') VALUES (:' . implode(',:', array_keys($row)) . ')')->execute($row);
    $id = (int)db()->lastInsertId();
    if (empty($row['suspect'])) fire_webhook($id);
    return $id;
}

const SOURCE_LABELS = ['qr' => 'Card form', 'manual' => 'Quick add', 'scan' => 'AI scanner', 'import' => 'Import'];

/* ── card design ─────────────────────────────────────────────────────── */

const TEMPLATES = [
    'classic' => 'Classic — brand band, round photo',
    'minimal' => 'Minimal — white card, company footer',
    'photo'   => 'Photo — full-width photo, name on top',
    'dark'    => 'Dark — gradient, glass buttons',
];
const WALLET_STYLES = ['brand' => 'Brand colour', 'dark' => 'Dark grey', 'white' => 'White'];

/** Company and design fields resolved against the brand: a blank card field inherits. */
function card_effective(array $c): array {
    foreach (['name', 'address', 'phone', 'email'] as $f) $c["co_$f"] = $c["company_$f"] !== '' ? $c["company_$f"] : (string)$c["brand_company_$f"];
    if ($c['co_name'] === '') $c['co_name'] = $c['brand_name'];
    $c['co_website'] = $c['company_website'] !== '' ? $c['company_website'] : ($c['brand_domain'] ? 'https://' . $c['brand_domain'] : '');
    $c['tpl'] = isset(TEMPLATES[$c['template']]) ? $c['template'] : (isset(TEMPLATES[$c['brand_template']]) ? $c['brand_template'] : 'classic');
    $c['wstyle'] = isset(WALLET_STYLES[$c['wallet_style']]) ? $c['wallet_style'] : (isset(WALLET_STYLES[$c['brand_wallet_style']]) ? $c['brand_wallet_style'] : 'brand');
    return $c;
}

/* ── link blocks ─────────────────────────────────────────────────────── */

// type => [label, value field label, default button text]. exchange/save are system blocks: hide, never delete.
const BLOCK_TYPES = [
    'exchange' => ['Exchange contacts', '', 'Exchange contacts'],
    'save'     => ['Save contact', '', 'Save contact'],
    'link'     => ['Link', 'URL', 'Visit our website'],
    'email'    => ['Email', 'Email address', 'Email me'],
    'call'     => ['Call', 'Phone number', 'Call me'],
    'sms'      => ['SMS', 'Phone number', 'Text me'],
    'whatsapp' => ['WhatsApp', 'WhatsApp number with country code', 'WhatsApp me'],
    'navigate' => ['Navigate', 'Address', 'Find our office'],
    'book'     => ['Book a meeting', 'Booking URL (Calendly, etc.)', 'Book a meeting'],
    'pay'      => ['Pay', 'Payment URL', 'Pay'],
    'text'     => ['Text', 'Text', ''],
    'socials'  => ['Social icons', '', ''],
];

// network => [label, how to turn the stored value into a URL]
const SOCIALS = [
    'linkedin' => ['LinkedIn', 'url'], 'instagram' => ['Instagram', 'https://instagram.com/%s'], 'facebook' => ['Facebook', 'url'],
    'x' => ['X', 'url'], 'youtube' => ['YouTube', 'url'], 'tiktok' => ['TikTok', 'https://tiktok.com/@%s'],
    'telegram' => ['Telegram', 'https://t.me/%s'], 'whatsapp' => ['WhatsApp', 'https://wa.me/%s'], 'wechat' => ['WeChat', 'url'],
    'snapchat' => ['Snapchat', 'url'], 'pinterest' => ['Pinterest', 'url'], 'threads' => ['Threads', 'https://threads.net/@%s'],
    'aparat' => ['Aparat', 'url'], 'tripadvisor' => ['Tripadvisor', 'url'], 'spotify' => ['Spotify', 'url'], 'reddit' => ['Reddit', 'url'],
];

function social_url(string $net, string $v): string {
    $v = trim($v);
    if ($v === '' || !isset(SOCIALS[$net])) return '';
    if (preg_match('~^https?://~i', $v)) return $v;
    $fmt = SOCIALS[$net][1];
    if ($fmt === 'url') return 'https://' . ltrim($v, '/');
    $handle = $net === 'whatsapp' ? preg_replace('/\D+/', '', $v) : ltrim($v, '@');
    return sprintf($fmt, rawurlencode($handle));
}

/** The card's blocks in order. A card never edited gets defaults built from its own fields. */
function card_blocks(array $c): array {
    $b = json_decode((string)($c['blocks'] ?? ''), true);
    if (is_array($b) && $b) return $b;
    $d = [['type' => 'exchange', 'label' => 'Exchange contacts', 'show' => true], ['type' => 'save', 'label' => 'Save contact', 'show' => true]];
    if ($c['phone'] ?? '') $d[] = ['type' => 'call', 'value' => $c['phone'], 'label' => 'Call me', 'show' => true];
    if ($c['whatsapp'] ?? '') $d[] = ['type' => 'whatsapp', 'value' => $c['whatsapp'], 'label' => 'WhatsApp me', 'show' => true];
    if ($c['email'] ?? '') $d[] = ['type' => 'email', 'value' => $c['email'], 'label' => 'Email me', 'show' => true];
    $soc = array_filter(['linkedin' => $c['linkedin'] ?? '', 'instagram' => $c['instagram'] ?? '']);
    $d[] = ['type' => 'socials', 'socials' => $soc, 'show' => true];
    return $d;
}

/** Validate blocks posted by the editor (JSON). Unknown types and empty values are dropped. */
function clean_blocks(string $json): array {
    $in = json_decode($json, true);
    if (!is_array($in)) return [];
    $out = []; $seen = [];
    foreach (array_slice($in, 0, 40) as $b) {
        $t = (string)($b['type'] ?? '');
        if (!isset(BLOCK_TYPES[$t])) continue;
        $blk = ['type' => $t, 'show' => !empty($b['show'])];
        if (in_array($t, ['exchange', 'save', 'socials'], true)) { if (isset($seen[$t])) continue; $seen[$t] = 1; }
        if ($t === 'socials') {
            $blk['socials'] = [];
            foreach (SOCIALS as $net => $_) if (($v = clean((string)($b['socials'][$net] ?? ''), 200)) !== '') $blk['socials'][$net] = $v;
        } elseif ($t === 'text') {
            $blk['value'] = clean((string)($b['value'] ?? ''), 1000);
            $blk['style'] = in_array($b['style'] ?? '', ['heading', 'subheading', 'body'], true) ? $b['style'] : 'body';
            if ($blk['value'] === '') continue;
        } else {
            $blk['label'] = clean((string)($b['label'] ?? ''), 60) ?: BLOCK_TYPES[$t][2];
            if (!in_array($t, ['exchange', 'save'], true)) {
                $v = clean((string)($b['value'] ?? ''), 300);
                if ($v === '') continue;
                if (in_array($t, ['link', 'book', 'pay'], true) && !preg_match('~^https?://~i', $v)) $v = 'https://' . $v;
                $blk['value'] = $v;
            }
            if ($t === 'exchange') $blk['auto_open'] = !empty($b['auto_open']);
        }
        $out[] = $blk;
    }
    foreach (['exchange', 'save'] as $sys) if (!isset($seen[$sys])) array_unshift($out, ['type' => $sys, 'label' => BLOCK_TYPES[$sys][2], 'show' => false]);
    return $out;
}

/** href for a block (null for text/socials/exchange, which render differently). */
function block_href(array $b, array $c): ?string {
    $v = (string)($b['value'] ?? '');
    return match ($b['type']) {
        'save' => base_url() . '/vcf.php?u=' . rawurlencode($c['slug']),
        'link', 'book', 'pay' => $v,
        'email' => 'mailto:' . $v,
        'call' => 'tel:' . preg_replace('/[^\d+]/', '', $v),
        'sms' => 'sms:' . preg_replace('/[^\d+]/', '', $v),
        'whatsapp' => 'https://wa.me/' . preg_replace('/\D+/', '', $v),
        'navigate' => 'https://maps.google.com/?q=' . rawurlencode($v),
        default => null,
    };
}

/* ── mail, invites, webhook ──────────────────────────────────────────── */

/** Plain-text mail from the configured address; false when mail is not configured. */
function send_mail(string $to, string $subject, string $body, string $replyTo = ''): bool {
    $from = (string)cfg('mail_from', '');
    if ($from === '' || !filter_var($to, FILTER_VALIDATE_EMAIL)) return false;
    $headers = "From: TeamCards <$from>\r\nContent-Type: text/plain; charset=UTF-8\r\n" . ($replyTo ? "Reply-To: $replyTo\r\n" : '');
    return @mail($to, '=?UTF-8?B?' . base64_encode($subject) . '?=', $body, $headers);
}

/** New 7-day invite token for a user; returns the link to set a password. */
function issue_invite(int $userId): string {
    $t = bin2hex(random_bytes(20));
    db()->prepare("UPDATE users SET invite_token = ?, invite_expires = datetime('now', '+7 days') WHERE id = ?")->execute([hash('sha256', $t), $userId]);
    return base_url() . '/index.php?p=invite&t=' . $t;
}

function send_invite(array $u, string $link): bool {
    return send_mail($u['email'], 'Your TeamCards business card', "Hi {$u['name']},\n\nYou have a digital business card on TeamCards.\n"
        . "Set your password here (link valid 7 days):\n$link\n\nAfter that, sign in at " . base_url() . "/ to see your card, QR code and the contacts you collect.\n");
}

/** POST the new contact to config webhook_url (Zapier/Make/HubSpot workflow), HMAC-signed like the rest of the pipeline. */
function fire_webhook(int $leadId): void {
    $url = (string)cfg('webhook_url', '');
    if ($url === '' || !preg_match('~^(https://|http://(127\.0\.0\.1|localhost)[:/])~', $url)) return;   // https only, except a local test listener
    $q = db()->prepare('SELECT l.id, l.name, l.email, l.phone, l.company, l.job_title, l.note, l.event, l.source, l.consent, l.created_at,
        b.name brand, b.domain brand_domain, u.name owner, u.email owner_email, c.slug card FROM leads l LEFT JOIN brands b ON b.id = l.brand_id
        LEFT JOIN users u ON u.id = l.user_id LEFT JOIN cards c ON c.id = l.card_id WHERE l.id = ?');
    $q->execute([$leadId]);
    if (!$row = $q->fetch()) return;
    $body = json_encode(['event' => 'contact.created', 'contact' => $row], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $ts = (string)time();
    $headers = ['Content-Type: application/json', "X-Albaloo-Timestamp: $ts",
        'X-Albaloo-Signature: sha256=' . hash_hmac('sha256', "$ts.$body", (string)cfg('webhook_secret', ''))];
    @file_get_contents($url, false, stream_context_create(['http' => ['method' => 'POST', 'header' => implode("\r\n", $headers),
        'content' => $body, 'timeout' => 4, 'ignore_errors' => true]]));
}

/* ── AI business-card scanner ────────────────────────────────────────── */

/**
 * Read a photographed business card or event badge with Claude and return contact fields.
 * Raw HTTP on purpose: the app ships as a dependency-free zip for shared hosting (no Composer).
 * The image is sent to the Anthropic API and not stored here.
 */
function ai_scan_card(string $path, string $mime): array {
    $key = (string)cfg('anthropic_api_key', '');
    if ($key === '') throw new RuntimeException('AI scanner is off: add anthropic_api_key to config.php.');
    $fields = ['name', 'email', 'phone', 'company', 'job_title', 'website', 'address'];
    $schema = ['type' => 'object', 'properties' => array_fill_keys($fields, ['type' => 'string']), 'required' => $fields, 'additionalProperties' => false];
    $req = [
        'model' => (string)cfg('scan_model', 'claude-opus-5-5'),
        'max_tokens' => 4000,
        'fallbacks' => 'default',
        'output_config' => ['effort' => 'low', 'format' => ['type' => 'json_schema', 'schema' => $schema]],
        'messages' => [['role' => 'user', 'content' => [
            ['type' => 'image', 'source' => ['type' => 'base64', 'media_type' => $mime, 'data' => base64_encode((string)file_get_contents($path))]],
            ['type' => 'text', 'text' => 'This is a photo of a business card or event badge. Extract the person\'s contact details. '
                . 'Copy text exactly as printed (keep Persian/Arabic script as is). Phone in international format if the country code is printed. '
                . 'Use an empty string for anything not on the card — never guess an email or phone.'],
        ]]],
    ];
    $ctx = stream_context_create(['http' => ['method' => 'POST', 'timeout' => 90, 'ignore_errors' => true,
        'header' => implode("\r\n", ['Content-Type: application/json', "x-api-key: $key", 'anthropic-version: 2026-10-21',
            'anthropic-beta: server-side-fallback-2026-07-01']),
        'content' => json_encode($req)]]);
    $raw = @file_get_contents(rtrim((string)cfg('anthropic_base_url', 'https://api.anthropic.com'), '/') . '/v1/messages', false, $ctx);
    $res = json_decode((string)$raw, true);
    if (!is_array($res)) throw new RuntimeException('Could not reach the AI scanner. Try again or type the details.');
    if (isset($res['error'])) throw new RuntimeException('AI scanner error: ' . ($res['error']['message'] ?? 'unknown'));
    if (($res['stop_reason'] ?? '') === 'refusal') throw new RuntimeException('The scanner declined this image. Type the details instead.');
    foreach ($res['content'] ?? [] as $blk) {
        if (($blk['type'] ?? '') === 'text' && is_array($data = json_decode($blk['text'], true))) {
            return array_map(fn($v) => clean((string)$v, 300), array_intersect_key($data, array_flip($fields)));
        }
    }
    throw new RuntimeException('The scanner returned nothing readable. Type the details instead.');
}
