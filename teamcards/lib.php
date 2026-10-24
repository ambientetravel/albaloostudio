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

const TC_VERSION = '1.0.0';

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

function card_by_slug(string $slug): ?array {
    $q = db()->prepare('SELECT c.*, b.name AS brand_name, b.domain AS brand_domain, b.color, b.accent, b.logo, b.tagline
        FROM cards c JOIN brands b ON b.id = c.brand_id WHERE c.slug = ?');
    $q->execute([$slug]); return $q->fetch() ?: null;
}

function card_by_id(int $id): ?array {
    $q = db()->prepare('SELECT c.*, b.name AS brand_name, b.domain AS brand_domain, b.color, b.accent, b.logo, b.tagline
        FROM cards c JOIN brands b ON b.id = c.brand_id WHERE c.id = ?');
    $q->execute([$id]); return $q->fetch() ?: null;
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

/* ── layout ──────────────────────────────────────────────────────────── */

function page_head(string $title, string $bodyClass = ''): void {
    $u = me();
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<meta name="robots" content="noindex,nofollow"><title>' . h($title) . ' · TeamCards</title>'
       . '<link rel="stylesheet" href="assets/app.css?v=' . TC_VERSION . '"></head><body class="' . h($bodyClass) . '">';
    if ($u) {
        $p = $_GET['p'] ?? 'home';
        $nav = ['home' => 'Dashboard', 'cards' => 'Cards', 'leads' => 'Contacts', 'scan' => 'Quick add'];
        if ($u['role'] === 'admin') $nav += ['team' => 'Team', 'brands' => 'Brands'];
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

/** Insert from $_POST fields plus the given overrides. Shared shape with card.php. */
function insert_lead(array $over): void {
    $row = ['name' => post('name', 120), 'email' => post('email', 160), 'phone' => post('phone', 40), 'company' => post('company', 120),
            'job_title' => post('job_title', 120), 'note' => post('note', 2000), 'event' => post('event', 120), 'ip_hash' => ip_hash()] + $over;
    $row = array_merge($row, $over);
    db()->prepare('INSERT INTO leads (' . implode(',', array_keys($row)) . ') VALUES (:' . implode(',:', array_keys($row)) . ')')->execute($row);
}
