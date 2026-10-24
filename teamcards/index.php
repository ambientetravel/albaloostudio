<?php
/*
 * TeamCards dashboard. One router, ?p=<page>. Every POST is CSRF-checked;
 * every page but login/setup requires a session. Members see their own
 * cards and contacts; admins see everything and manage team + brands.
 */

declare(strict_types=1);
require __DIR__ . '/lib.php';
start_session();

$p = (string)($_GET['p'] ?? 'home');
$isPost = ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST';
if ($isPost) check_csrf();

/* ── first run: create the admin, gated by config.php's setup_key ─────── */
$hasUsers = (int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn() > 0;
if (!$hasUsers && $p !== 'setup') redirect('index.php?p=setup');

switch ($p) {

case 'setup':
    if ($hasUsers) redirect('index.php?p=login');
    $key = (string)cfg('setup_key', '');
    $err = '';
    if ($isPost) {
        if (strlen($key) < 12 || !hash_equals($key, (string)($_POST['setup_key'] ?? ''))) $err = 'Setup key does not match config.php.';
        elseif (!filter_var(post('email'), FILTER_VALIDATE_EMAIL)) $err = 'Enter a valid email.';
        elseif (strlen((string)$_POST['password']) < 10) $err = 'Password needs at least 10 characters.';
        else {
            db()->prepare('INSERT INTO users (email, name, password_hash, role) VALUES (?,?,?,?)')
                ->execute([post('email'), post('name') ?: 'Admin', password_hash((string)$_POST['password'], PASSWORD_DEFAULT), 'admin']);
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)db()->lastInsertId();
            flash('Admin account created. Add your team under Team, then create cards.');
            redirect('index.php');
        }
    }
    page_head('Setup', 'auth');
    echo '<div class="authbox"><h1>Set up TeamCards</h1>';
    if (strlen($key) < 12) echo '<p class="err">config.php has no <code>setup_key</code> (12+ characters). Add one, then reload.</p>';
    if ($err) echo '<p class="err">' . h($err) . '</p>';
    echo '<form method="post">' . csrf_field()
       . '<label>Setup key (from config.php)<input name="setup_key" type="password" required></label>'
       . '<label>Your name<input name="name" required></label><label>Email<input name="email" type="email" required></label>'
       . '<label>Password<input name="password" type="password" minlength="10" required></label><button>Create admin</button></form></div>';
    page_foot(); break;

case 'login':
    $err = '';
    if ($isPost) {
        $q = db()->prepare('SELECT * FROM users WHERE email = ?'); $q->execute([post('email')]);
        $u = $q->fetch();
        if ($u && password_verify((string)($_POST['password'] ?? ''), $u['password_hash'])) {
            session_regenerate_id(true); $_SESSION['uid'] = (int)$u['id']; redirect('index.php');
        }
        usleep(400000); $err = 'Wrong email or password.';
    }
    page_head('Sign in', 'auth');
    echo '<div class="authbox"><h1>TeamCards</h1>' . ($err ? '<p class="err">' . h($err) . '</p>' : '')
       . '<form method="post">' . csrf_field() . '<label>Email<input name="email" type="email" autocomplete="username" required></label>'
       . '<label>Password<input name="password" type="password" autocomplete="current-password" required></label><button>Sign in</button></form></div>';
    page_foot(); break;

case 'logout':
    if ($isPost) { $_SESSION = []; session_destroy(); }
    redirect('index.php?p=login');

/* ── dashboard ───────────────────────────────────────────────────────── */
case 'home':
    $u = require_login();
    [$where, $args] = is_admin() ? ['1=1', []] : ['l.user_id = ?', [$u['id']]];
    $stat = fn(string $sql) => (function () use ($sql, $args) { $q = db()->prepare($sql); $q->execute($args); return (int)$q->fetchColumn(); })();
    $total = $stat("SELECT COUNT(*) FROM leads l WHERE $where AND l.suspect = 0");
    $week  = $stat("SELECT COUNT(*) FROM leads l WHERE $where AND l.suspect = 0 AND l.created_at >= datetime('now','-7 days')");
    $cards = $stat('SELECT COUNT(*) FROM cards l WHERE ' . (is_admin() ? '1=1' : 'l.user_id = ?'));
    $views = $stat('SELECT COALESCE(SUM(views),0) FROM cards l WHERE ' . (is_admin() ? '1=1' : 'l.user_id = ?'));
    page_head('Dashboard');
    echo '<h1>Hi ' . h(explode(' ', $u['name'])[0]) . '</h1><div class="stats">'
       . "<div><b>$total</b>contacts</div><div><b>$week</b>last 7 days</div><div><b>$cards</b>cards</div><div><b>$views</b>card views</div></div>";
    $q = db()->prepare("SELECT b.name, COUNT(l.id) n FROM brands b LEFT JOIN leads l ON l.brand_id = b.id AND l.suspect = 0 AND $where GROUP BY b.id ORDER BY n DESC");
    $q->execute($args);
    echo '<h2>By brand</h2><div class="stats small">';
    foreach ($q as $r) echo '<div><b>' . (int)$r['n'] . '</b>' . h($r['name']) . '</div>';
    echo '</div><h2>Latest contacts</h2>';
    $q = db()->prepare("SELECT l.*, b.name brand, u.name owner FROM leads l LEFT JOIN brands b ON b.id = l.brand_id LEFT JOIN users u ON u.id = l.user_id
        WHERE $where AND l.suspect = 0 ORDER BY l.id DESC LIMIT 10");
    $q->execute($args);
    leads_table($q->fetchAll());
    echo '<p><a class="btn" href="index.php?p=leads">All contacts</a> <a class="btn ghost" href="index.php?p=scan">Quick add a contact</a></p>';
    page_foot(); break;

/* ── cards ───────────────────────────────────────────────────────────── */
case 'cards':
    $u = require_login();
    $sql = 'SELECT c.*, b.name brand_name, b.color, b.accent, u.name owner,
        (SELECT COUNT(*) FROM leads l WHERE l.card_id = c.id AND l.suspect = 0) leads
        FROM cards c JOIN brands b ON b.id = c.brand_id JOIN users u ON u.id = c.user_id';
    $q = is_admin() ? db()->query($sql . ' ORDER BY u.name, b.name') : db()->prepare($sql . ' WHERE c.user_id = ? ORDER BY b.name');
    if (!is_admin()) $q->execute([$u['id']]);
    page_head('Cards');
    echo '<div class="row"><h1>Cards</h1><a class="btn" href="index.php?p=card">+ New card</a></div><div class="grid">';
    foreach ($q as $c) {
        $url = card_url($c['slug']);
        echo '<article class="tile" style="--brand:' . h($c['color']) . ';--accent:' . h($c['accent']) . '">'
           . '<div class="tile-top"><span class="pill">' . h($c['brand_name']) . '</span>' . ($c['active'] ? '' : '<span class="pill off">off</span>') . '</div>'
           . '<h3>' . h($c['full_name']) . '</h3><p>' . h($c['title']) . '</p>'
           . '<div class="qr" data-qr="' . h($url) . '" data-name="' . h($c['slug']) . '"></div>'
           . '<p class="muted">' . (int)$c['views'] . ' views · ' . (int)$c['leads'] . ' contacts' . (is_admin() ? ' · ' . h($c['owner']) : '') . '</p>'
           . '<div class="actions"><a href="' . h($url) . '" target="_blank">Open</a><a href="index.php?p=card&id=' . (int)$c['id'] . '">Edit</a>'
           . '<a href="#" data-dl-png>QR PNG</a><a href="#" data-dl-svg>QR SVG</a><a href="index.php?p=print&id=' . (int)$c['id'] . '" target="_blank">Print</a>'
           . '<a href="wallet.php?id=' . (int)$c['id'] . '&t=apple">Apple Wallet</a><a href="wallet.php?id=' . (int)$c['id'] . '&t=google">Google Wallet</a></div></article>';
    }
    echo '</div>';
    page_foot(); break;

case 'card':
    $u = require_login();
    $id = (int)($_GET['id'] ?? 0);
    $c = $id ? card_by_id($id) : null;
    if ($id && (!$c || !can_edit_card($c))) { http_response_code(404); exit('Not found'); }
    $err = '';
    if ($isPost && isset($_POST['delete']) && $c) {
        db()->prepare('DELETE FROM cards WHERE id = ?')->execute([$c['id']]);
        flash('Card deleted. Its contacts are kept.'); redirect('index.php?p=cards');
    }
    if ($isPost && !isset($_POST['delete'])) {
        $f = [];
        foreach (['full_name' => 120, 'title' => 120, 'email' => 160, 'phone' => 40, 'whatsapp' => 40, 'website' => 200,
                  'linkedin' => 200, 'instagram' => 120, 'address' => 240, 'bio' => 600] as $k => $max) $f[$k] = post($k, $max);
        $brandId = (int)($_POST['brand_id'] ?? 0);
        $owner = is_admin() ? (int)($_POST['user_id'] ?? $u['id']) : (int)($c['user_id'] ?? $u['id']);
        foreach (['website', 'linkedin'] as $k) if ($f[$k] !== '' && !preg_match('~^https?://~i', $f[$k])) $f[$k] = 'https://' . $f[$k];
        if ($f['full_name'] === '') $err = 'Name is required.';
        elseif (!brand($brandId)) $err = 'Pick a brand.';
        elseif ($f['email'] !== '' && !filter_var($f['email'], FILTER_VALIDATE_EMAIL)) $err = 'Email looks wrong.';
        if (!$err) {
            try { $photo = save_upload('photo'); } catch (RuntimeException $e) { $err = $e->getMessage(); $photo = null; }
        }
        if (!$err) {
            $slug = unique_slug(post('slug', 48) ?: ($f['full_name'] . '-' . brand($brandId)['slug']), (int)($c['id'] ?? 0));
            $cols = $f + ['brand_id' => $brandId, 'user_id' => $owner, 'slug' => $slug, 'active' => isset($_POST['active']) ? 1 : 0];
            if ($photo !== null) $cols['photo'] = $photo;
            if (isset($_POST['remove_photo'])) $cols['photo'] = '';
            if ($c) {
                $set = implode(', ', array_map(fn($k) => "$k = :$k", array_keys($cols)));
                db()->prepare("UPDATE cards SET $set WHERE id = :id")->execute($cols + ['id' => $c['id']]);
            } else {
                db()->prepare('INSERT INTO cards (' . implode(',', array_keys($cols)) . ') VALUES (:' . implode(',:', array_keys($cols)) . ')')->execute($cols);
            }
            flash('Card saved: ' . card_url($slug)); redirect('index.php?p=cards');
        }
        $c = array_merge($c ?? [], $_POST);
    }
    $c ??= ['full_name' => $u['name'], 'email' => $u['email'], 'active' => 1, 'user_id' => $u['id'], 'brand_id' => 0];
    page_head($id ? 'Edit card' : 'New card');
    echo '<h1>' . ($id ? 'Edit card' : 'New card') . '</h1>' . ($err ? '<p class="err">' . h($err) . '</p>' : '');
    echo '<form method="post" enctype="multipart/form-data" class="form">' . csrf_field() . '<div class="cols">';
    echo '<label>Brand<select name="brand_id" required><option value="">—</option>';
    foreach (brands() as $b) echo '<option value="' . $b['id'] . '"' . ((int)($c['brand_id'] ?? 0) === (int)$b['id'] ? ' selected' : '') . '>' . h($b['name']) . '</option>';
    echo '</select></label>';
    if (is_admin()) {
        echo '<label>Owner<select name="user_id">';
        foreach (db()->query('SELECT id, name FROM users ORDER BY name') as $m) echo '<option value="' . $m['id'] . '"' . ((int)($c['user_id'] ?? 0) === (int)$m['id'] ? ' selected' : '') . '>' . h($m['name']) . '</option>';
        echo '</select></label>';
    }
    $fields = ['full_name' => 'Full name *', 'title' => 'Job title', 'email' => 'Email', 'phone' => 'Phone (+country code)',
               'whatsapp' => 'WhatsApp number', 'website' => 'Website', 'linkedin' => 'LinkedIn URL', 'instagram' => 'Instagram handle',
               'address' => 'Office address', 'slug' => 'Link name (optional, e.g. ali-boutimar)'];
    foreach ($fields as $k => $label) echo '<label>' . h($label) . '<input name="' . $k . '" value="' . h((string)($c[$k] ?? '')) . '"' . ($k === 'full_name' ? ' required' : '') . '></label>';
    echo '</div><label>Short bio<textarea name="bio" rows="3">' . h((string)($c['bio'] ?? '')) . '</textarea></label>';
    echo '<label>Photo (JPG/PNG/WebP, square works best)<input type="file" name="photo" accept="image/jpeg,image/png,image/webp"></label>';
    if (!empty($c['photo']) && is_string($c['photo'])) echo '<p><img class="avatar" src="' . h(photo_url($c['photo'])) . '" alt=""> <label class="check"><input type="checkbox" name="remove_photo"> remove photo</label></p>';
    echo '<label class="check"><input type="checkbox" name="active"' . (!empty($c['active']) ? ' checked' : '') . '> Card is live</label>';
    echo '<p><button>Save card</button> <a href="index.php?p=cards">Cancel</a></p></form>';
    if ($id) echo '<form method="post" onsubmit="return confirm(\'Delete this card? Contacts captured by it are kept.\')">' . csrf_field() . '<button name="delete" value="1" class="danger">Delete card</button></form>';
    page_foot(); break;

case 'print':
    // A printable sheet: card front + big QR, for stands, badges and table tents.
    require_login();
    $c = card_by_id((int)($_GET['id'] ?? 0));
    if (!$c || !can_edit_card($c)) { http_response_code(404); exit('Not found'); }
    $url = card_url($c['slug']);
    echo '<!doctype html><html><head><meta charset="utf-8"><title>Print · ' . h($c['full_name']) . '</title><link rel="stylesheet" href="assets/app.css"></head>'
       . '<body class="print" style="--brand:' . h($c['color']) . ';--accent:' . h($c['accent']) . '">'
       . '<div class="sheet"><div class="bizcard"><div><b>' . h($c['full_name']) . '</b><span>' . h($c['title']) . '</span><span>' . h($c['brand_name']) . '</span>'
       . '<small>' . h($c['phone']) . '<br>' . h($c['email']) . '</small></div><div class="qr" data-qr="' . h($url) . '"></div></div>'
       . '<div class="tent"><h2>Scan to connect</h2><div class="qr big" data-qr="' . h($url) . '"></div><p>' . h($c['full_name']) . ' · ' . h($c['brand_name']) . '</p></div>'
       . '<p class="noprint"><button onclick="print()">Print</button></p></div><script src="assets/qrcode.js"></script><script src="assets/app.js"></script></body></html>';
    break;

/* ── contacts ────────────────────────────────────────────────────────── */
case 'leads':
    $u = require_login();
    if ($isPost && isset($_POST['lead_id'])) {
        $l = lead_for_edit((int)$_POST['lead_id']);
        if (isset($_POST['delete'])) db()->prepare('DELETE FROM leads WHERE id = ?')->execute([$l['id']]);
        else db()->prepare('UPDATE leads SET status = ?, note = ?, event = ? WHERE id = ?')
            ->execute([in_array($_POST['status'] ?? '', LEAD_STATUSES, true) ? $_POST['status'] : 'new', post('note', 2000), post('event', 120), $l['id']]);
        flash('Contact updated.'); redirect('index.php?' . http_build_query(array_diff_key($_GET, ['x' => 1])));
    }
    [$sql, $args] = lead_query($u);
    $rows = db()->prepare($sql . ' ORDER BY l.id DESC LIMIT 500'); $rows->execute($args); $rows = $rows->fetchAll();
    page_head('Contacts');
    echo '<div class="row"><h1>Contacts <span class="muted">(' . count($rows) . (count($rows) === 500 ? '+' : '') . ')</span></h1><div>'
       . '<a class="btn" href="index.php?p=scan">+ Add</a> <a class="btn ghost" href="export.php?' . h(http_build_query($_GET)) . '">Export CSV</a>'
       . (is_admin() ? ' <a class="btn ghost" href="index.php?p=import">Import CSV</a>' : '') . '</div></div>';
    lead_filters();
    leads_table($rows, true);
    page_foot(); break;

case 'scan':
    // Quick add: for a contact met in person who did not scan — or a paper card typed in.
    $u = require_login();
    $myCards = db()->prepare('SELECT c.id, c.full_name, b.name brand FROM cards c JOIN brands b ON b.id = c.brand_id WHERE c.user_id = ? ORDER BY b.name');
    $myCards->execute([$u['id']]); $myCards = $myCards->fetchAll();
    $err = '';
    if ($isPost) {
        $cardId = (int)($_POST['card_id'] ?? 0);
        $card = $cardId ? card_by_id($cardId) : null;
        if ($card && !can_edit_card($card)) $card = null;
        $brandId = $card ? (int)$card['brand_id'] : (int)($_POST['brand_id'] ?? 0);
        if (post('name') === '') $err = 'Name is required.';
        elseif (post('email') !== '' && !filter_var(post('email'), FILTER_VALIDATE_EMAIL)) $err = 'Email looks wrong.';
        elseif (!brand($brandId)) $err = 'Pick a card or a brand.';
        else {
            insert_lead(['card_id' => $card['id'] ?? null, 'user_id' => $u['id'], 'brand_id' => $brandId, 'source' => 'manual', 'consent' => isset($_POST['consent']) ? 1 : 0]);
            $_SESSION['last_event'] = post('event', 120);
            flash('Saved ' . post('name') . '.'); redirect('index.php?p=scan');
        }
    }
    page_head('Quick add');
    echo '<h1>Quick add a contact</h1><p class="muted">For someone you met who did not scan your QR. Scanning a paper card? Use your phone camera’s text copy and paste here.</p>'
       . ($err ? '<p class="err">' . h($err) . '</p>' : '') . '<form method="post" class="form">' . csrf_field() . '<div class="cols">';
    echo '<label>Captured on card<select name="card_id"><option value="">— none —</option>';
    foreach ($myCards as $mc) echo '<option value="' . $mc['id'] . '">' . h($mc['brand'] . ' · ' . $mc['full_name']) . '</option>';
    echo '</select></label><label>…or brand<select name="brand_id"><option value="">—</option>';
    foreach (brands() as $b) echo '<option value="' . $b['id'] . '">' . h($b['name']) . '</option>';
    echo '</select></label>';
    foreach (['name' => 'Name *', 'email' => 'Email', 'phone' => 'Phone', 'company' => 'Company', 'job_title' => 'Job title'] as $k => $l)
        echo '<label>' . $l . '<input name="' . $k . '"' . ($k === 'name' ? ' required' : '') . ($k === 'email' ? ' type="email"' : '') . '></label>';
    echo '<label>Event / place<input name="event" list="events" value="' . h($_SESSION['last_event'] ?? '') . '"></label>' . events_datalist()
       . '</div><label>Note<textarea name="note" rows="3"></textarea></label>'
       . '<label class="check"><input type="checkbox" name="consent"> They agreed to be contacted</label><p><button>Save contact</button></p></form>';
    page_foot(); break;

case 'import':
    // HeyDrop (or any) CSV export → contacts. Header names are matched loosely.
    $u = require_admin();
    $report = '';
    if ($isPost && !empty($_FILES['csv']['tmp_name'])) {
        $brandId = (int)($_POST['brand_id'] ?? 0); $owner = (int)($_POST['user_id'] ?? $u['id']);
        if (!brand($brandId)) { flash('Pick a brand.'); redirect('index.php?p=import'); }
        $fh = fopen($_FILES['csv']['tmp_name'], 'r');
        $head = array_map(fn($x) => strtolower(trim(preg_replace('/^\xEF\xBB\xBF/', '', (string)$x))), fgetcsv($fh, null, ',', '"', '') ?: []);
        $map = [];
        $aliases = ['name' => ['name', 'full name', 'fullname', 'contact name'], 'first' => ['first name', 'firstname', 'given name'],
            'last' => ['last name', 'lastname', 'surname', 'family name'], 'email' => ['email', 'e-mail', 'email address'],
            'phone' => ['phone', 'phone number', 'mobile', 'telephone'], 'company' => ['company', 'organization', 'organisation'],
            'job_title' => ['title', 'job title', 'position', 'role'], 'note' => ['note', 'notes', 'message', 'comment'],
            'event' => ['event', 'tag', 'tags', 'location'], 'created_at' => ['date', 'created', 'created at', 'scanned at', 'timestamp']];
        foreach ($aliases as $k => $names) foreach ($head as $i => $col) if (in_array($col, $names, true)) { $map[$k] = $i; break; }
        $ok = 0; $skip = 0; $dupe = 0;
        $exists = db()->prepare('SELECT 1 FROM leads WHERE brand_id = ? AND email != "" AND email = ? COLLATE NOCASE');
        while (($r = fgetcsv($fh, null, ',', '"', '')) !== false) {
            $g = fn($k) => isset($map[$k]) ? clean((string)($r[$map[$k]] ?? ''), $k === 'note' ? 2000 : 200) : '';
            $name = $g('name') ?: trim($g('first') . ' ' . $g('last'));
            if ($name === '' && $g('email') === '') { $skip++; continue; }
            if ($g('email') !== '') { $exists->execute([$brandId, $g('email')]); if ($exists->fetch()) { $dupe++; continue; } }
            $ts = strtotime($g('created_at')) ?: time();
            db()->prepare('INSERT INTO leads (user_id, brand_id, name, email, phone, company, job_title, note, event, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)')
                ->execute([$owner, $brandId, $name ?: $g('email'), $g('email'), $g('phone'), $g('company'), $g('job_title'), $g('note'), $g('event'), 'import', gmdate('Y-m-d H:i:s', $ts)]);
            $ok++;
        }
        $report = "Imported $ok · skipped $skip empty rows · $dupe already present (same email + brand). Columns recognised: " . implode(', ', array_keys($map));
    }
    page_head('Import');
    echo '<h1>Import contacts (CSV)</h1>' . ($report ? '<div class="flash">' . h($report) . '</div>' : '')
       . '<p class="muted">Export your contacts from HeyDrop (or any CRM) as CSV and load them here. Recognised headers: name / first name / last name, email, phone, company, title, note, event/tag, date.</p>'
       . '<form method="post" enctype="multipart/form-data" class="form">' . csrf_field() . '<div class="cols"><label>Brand<select name="brand_id" required>';
    foreach (brands() as $b) echo '<option value="' . $b['id'] . '">' . h($b['name']) . '</option>';
    echo '</select></label><label>Owner<select name="user_id">';
    foreach (db()->query('SELECT id, name FROM users ORDER BY name') as $m) echo '<option value="' . $m['id'] . '">' . h($m['name']) . '</option>';
    echo '</select></label></div><label>CSV file<input type="file" name="csv" accept=".csv,text/csv" required></label><p><button>Import</button></p></form>';
    page_foot(); break;

/* ── team & brands (admin) ───────────────────────────────────────────── */
case 'team':
    $u = require_admin();
    if ($isPost) {
        if (isset($_POST['delete'])) {
            if ((int)$_POST['delete'] === (int)$u['id']) flash('You cannot remove yourself.');
            else { db()->prepare('DELETE FROM users WHERE id = ?')->execute([(int)$_POST['delete']]); flash('Removed. Their cards are deleted; their contacts are kept, unassigned.'); }
        } elseif (isset($_POST['reset'])) {
            $pw = rtrim(strtr(base64_encode(random_bytes(9)), '+/', 'xy'), '=');
            db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')->execute([password_hash($pw, PASSWORD_DEFAULT), (int)$_POST['reset']]);
            flash("New temporary password: $pw — give it to them privately.");
        } else {
            $pw = rtrim(strtr(base64_encode(random_bytes(9)), '+/', 'xy'), '=');
            try {
                db()->prepare('INSERT INTO users (email, name, password_hash, role) VALUES (?,?,?,?)')
                    ->execute([post('email'), post('name'), password_hash($pw, PASSWORD_DEFAULT), ($_POST['role'] ?? '') === 'admin' ? 'admin' : 'member']);
                flash('Added ' . post('name') . ". Temporary password: $pw — they can change it under Account.");
            } catch (PDOException) { flash('That email already has an account.'); }
        }
        redirect('index.php?p=team');
    }
    page_head('Team');
    echo '<h1>Team</h1><table class="tbl"><tr><th>Name</th><th>Email</th><th>Role</th><th>Cards</th><th>Contacts</th><th></th></tr>';
    foreach (db()->query('SELECT u.*, (SELECT COUNT(*) FROM cards c WHERE c.user_id = u.id) cards, (SELECT COUNT(*) FROM leads l WHERE l.user_id = u.id AND l.suspect = 0) leads FROM users u ORDER BY name') as $m)
        echo '<tr><td>' . h($m['name']) . '</td><td>' . h($m['email']) . '</td><td>' . h($m['role']) . '</td><td>' . $m['cards'] . '</td><td>' . $m['leads'] . '</td><td class="nowrap">'
           . '<form method="post" class="inline">' . csrf_field() . '<button class="link" name="reset" value="' . $m['id'] . '">Reset password</button></form> '
           . '<form method="post" class="inline" onsubmit="return confirm(\'Remove ' . h(addslashes($m['name'])) . '?\')">' . csrf_field() . '<button class="link danger" name="delete" value="' . $m['id'] . '">Remove</button></form></td></tr>';
    echo '</table><h2>Add a team member</h2><form method="post" class="form">' . csrf_field() . '<div class="cols">'
       . '<label>Name<input name="name" required></label><label>Email<input name="email" type="email" required></label>'
       . '<label>Role<select name="role"><option value="member">Member — own cards & contacts</option><option value="admin">Admin — everything</option></select></label></div>'
       . '<p><button>Add</button></p></form>';
    page_foot(); break;

case 'brands':
    require_admin();
    if ($isPost) {
        $id = (int)($_POST['id'] ?? 0);
        $hex = fn($k, $d) => preg_match('/^#[0-9a-f]{6}$/i', post($k)) ? post($k) : $d;
        try { $logo = save_upload('logo'); } catch (RuntimeException $e) { flash($e->getMessage()); redirect('index.php?p=brands'); }
        $vals = [post('name', 80), strtolower(post('domain', 120)), $hex('color', '#0f3d5e'), $hex('accent', '#e8b04a'), post('tagline', 160)];
        if ($id) {
            db()->prepare('UPDATE brands SET name=?, domain=?, color=?, accent=?, tagline=?' . ($logo ? ', logo=?' : '') . ' WHERE id=?')
                ->execute(array_merge($vals, $logo ? [$logo] : [], [$id]));
        } elseif (post('name') !== '') {
            db()->prepare('INSERT INTO brands (name, domain, color, accent, tagline, logo, slug) VALUES (?,?,?,?,?,?,?)')
                ->execute(array_merge($vals, [$logo ?? '', slugify(post('name')) . '-' . bin2hex(random_bytes(2))]));
        }
        flash('Brand saved.'); redirect('index.php?p=brands');
    }
    page_head('Brands');
    echo '<h1>Brands</h1><p class="muted">Colours and logo drive each card page, the printed QR sheet and the wallet pass.</p>';
    foreach (array_merge(brands(), [['id' => 0, 'name' => '', 'domain' => '', 'color' => '#0f3d5e', 'accent' => '#e8b04a', 'tagline' => '', 'logo' => '']]) as $b) {
        echo '<form method="post" enctype="multipart/form-data" class="form brandrow">' . csrf_field() . '<input type="hidden" name="id" value="' . (int)$b['id'] . '">'
           . '<h3>' . ($b['id'] ? h($b['name']) : 'Add a brand') . '</h3><div class="cols">'
           . '<label>Name<input name="name" value="' . h($b['name']) . '" required></label><label>Website domain<input name="domain" value="' . h($b['domain']) . '"></label>'
           . '<label>Main colour<input type="color" name="color" value="' . h($b['color']) . '"></label><label>Accent<input type="color" name="accent" value="' . h($b['accent']) . '"></label>'
           . '<label>Tagline<input name="tagline" value="' . h($b['tagline']) . '"></label><label>Logo (PNG, transparent)' . ($b['logo'] ? ' <img class="logo-s" src="' . h(photo_url($b['logo'])) . '" alt="">' : '') . '<input type="file" name="logo" accept="image/png,image/jpeg,image/webp"></label>'
           . '</div><button>' . ($b['id'] ? 'Save' : 'Add brand') . '</button></form>';
    }
    page_foot(); break;

case 'account':
    $u = require_login();
    if ($isPost) {
        if (!password_verify((string)($_POST['current'] ?? ''), $u['password_hash'])) flash('Current password is wrong.');
        elseif (strlen((string)($_POST['new'] ?? '')) < 10) flash('New password needs 10+ characters.');
        else { db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')->execute([password_hash((string)$_POST['new'], PASSWORD_DEFAULT), $u['id']]); flash('Password changed.'); }
        db()->prepare('UPDATE users SET notify = ? WHERE id = ?')->execute([isset($_POST['notify']) ? 1 : 0, $u['id']]);
        redirect('index.php?p=account');
    }
    page_head('Account');
    echo '<h1>Account</h1><form method="post" class="form">' . csrf_field()
       . '<label>Current password<input type="password" name="current" required></label><label>New password<input type="password" name="new" minlength="10"></label>'
       . '<label class="check"><input type="checkbox" name="notify"' . ($u['notify'] ? ' checked' : '') . '> Email me when someone leaves their details on my card</label><p><button>Save</button></p></form>';
    page_foot(); break;

default:
    http_response_code(404); page_head('Not found'); echo '<h1>Not found</h1>'; page_foot();
}

/* ── page helpers ────────────────────────────────────────────────────── */

function lead_for_edit(int $id): array {
    $q = db()->prepare('SELECT * FROM leads WHERE id = ?'); $q->execute([$id]); $l = $q->fetch();
    if (!$l || (!is_admin() && (int)$l['user_id'] !== (int)me()['id'])) { http_response_code(404); exit('Not found'); }
    return $l;
}

function events_datalist(): string {
    $o = '<datalist id="events">';
    foreach (db()->query("SELECT DISTINCT event FROM leads WHERE event != '' ORDER BY id DESC LIMIT 50") as $e) $o .= '<option value="' . h($e['event']) . '">';
    return $o . '</datalist>';
}

function lead_filters(): void {
    $g = fn($k) => h((string)($_GET[$k] ?? ''));
    echo '<form class="filters" method="get"><input type="hidden" name="p" value="leads"><input name="q" placeholder="Search name, email, company…" value="' . $g('q') . '">';
    echo '<select name="brand"><option value="">All brands</option>';
    foreach (brands() as $b) echo '<option value="' . $b['id'] . '"' . (($_GET['brand'] ?? '') == $b['id'] ? ' selected' : '') . '>' . h($b['name']) . '</option>';
    echo '</select>';
    if (is_admin()) {
        echo '<select name="owner"><option value="">Everyone</option>';
        foreach (db()->query('SELECT id, name FROM users ORDER BY name') as $m) echo '<option value="' . $m['id'] . '"' . (($_GET['owner'] ?? '') == $m['id'] ? ' selected' : '') . '>' . h($m['name']) . '</option>';
        echo '</select>';
    }
    echo '<select name="status"><option value="">Any status</option>';
    foreach (LEAD_STATUSES as $s) echo '<option' . (($_GET['status'] ?? '') === $s ? ' selected' : '') . '>' . $s . '</option>';
    echo '</select><input name="event" list="events" placeholder="Event" value="' . $g('event') . '">' . events_datalist()
       . '<input type="date" name="from" value="' . $g('from') . '"><input type="date" name="to" value="' . $g('to') . '">'
       . '<label class="check"><input type="checkbox" name="suspect" value="1"' . (!empty($_GET['suspect']) ? ' checked' : '') . '> spam</label><button>Filter</button></form>';
}

function leads_table(array $rows, bool $editable = false): void {
    if (!$rows) { echo '<p class="muted">No contacts yet. Share your card QR and they will appear here.</p>'; return; }
    echo '<div class="scroll"><table class="tbl"><tr><th>When</th><th>Name</th><th>Email / phone</th><th>Company</th><th>Brand</th>' . (is_admin() ? '<th>Owner</th>' : '') . '<th>Event</th><th>Status</th>' . ($editable ? '<th></th>' : '') . '</tr>';
    foreach ($rows as $l) {
        echo '<tr><td class="nowrap">' . h(substr($l['created_at'], 0, 16)) . '<br><span class="muted">' . h($l['source']) . ($l['consent'] ? ' · ✓ consent' : '') . '</span></td>'
           . '<td><b>' . h($l['name']) . '</b>' . ($l['job_title'] ? '<br><span class="muted">' . h($l['job_title']) . '</span>' : '') . '</td>'
           . '<td>' . ($l['email'] ? '<a href="mailto:' . h($l['email']) . '">' . h($l['email']) . '</a>' : '') . ($l['phone'] ? '<br><a href="tel:' . h($l['phone']) . '">' . h($l['phone']) . '</a>' : '') . '</td>'
           . '<td>' . h($l['company']) . '</td><td>' . h($l['brand'] ?? '') . '</td>' . (is_admin() ? '<td>' . h($l['owner'] ?? '—') . '</td>' : '')
           . '<td>' . h($l['event']) . '</td><td><span class="st st-' . h($l['status']) . '">' . h($l['status']) . '</span></td>';
        if ($editable) {
            echo '<td><details><summary>Edit</summary><form method="post" class="mini">' . csrf_field() . '<input type="hidden" name="lead_id" value="' . (int)$l['id'] . '"><select name="status">';
            foreach (LEAD_STATUSES as $s) echo '<option' . ($l['status'] === $s ? ' selected' : '') . '>' . $s . '</option>';
            echo '</select><input name="event" list="events" value="' . h($l['event']) . '" placeholder="Event"><textarea name="note" rows="3" placeholder="Note">' . h($l['note']) . '</textarea>'
               . '<button>Save</button> <button name="delete" value="1" class="link danger" onclick="return confirm(\'Delete contact?\')">Delete</button></form></details></td>';
        }
        echo '</tr>';
    }
    echo '</table></div>';
}
