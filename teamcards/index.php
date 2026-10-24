<?php
/*
 * TeamCards dashboard. One router, ?p=<page>. Every POST is CSRF-checked;
 * every page but login/setup/invite requires a session. Workspace pages are
 * scoped to ws_id(): members see their own cards and contacts, admins their
 * whole workspace, and the owner runs the platform from p=owner.
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
                ->execute([post('email'), post('name') ?: 'Owner', password_hash((string)$_POST['password'], PASSWORD_DEFAULT), 'owner']);
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)db()->lastInsertId();
            flash('Owner account created. Create your first workspace (sub-brand) below.');
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
       . '<label>Password<input name="password" type="password" minlength="10" required></label><button>Create owner account</button></form>'
       . '<p class="muted small">This is the platform owner: you create the sub-brands and their admins.</p></div>';
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
    [$where, $args] = is_admin() ? ['l.brand_id = ?', [ws_id()]] : ['l.brand_id = ? AND l.user_id = ?', [ws_id(), $u['id']]];
    $stat = function (string $sql) use ($args) { $q = db()->prepare($sql); $q->execute($args); return (int)$q->fetchColumn(); };
    $total = $stat("SELECT COUNT(*) FROM leads l WHERE $where AND l.suspect = 0");
    $week  = $stat("SELECT COUNT(*) FROM leads l WHERE $where AND l.suspect = 0 AND l.created_at >= '" . utc('-7 days') . "'");
    $cards = $stat("SELECT COUNT(*) FROM cards l WHERE $where");
    $views = $stat("SELECT COALESCE(SUM(views),0) FROM cards l WHERE $where");
    [$used, $max] = ws_seats(ws_id());
    page_head('Dashboard');
    echo '<h1>' . h(ws()['name']) . '</h1><div class="stats">'
       . "<div><b>$total</b>contacts</div><div><b>$week</b>last 7 days</div><div><b>$cards</b>cards" . (is_admin() && $max ? " <span class=\"muted\">of $max</span>" : '') . "</div><div><b>$views</b>card views</div></div>";
    if (is_admin()) {
        $q = db()->prepare("SELECT u.name, COUNT(l.id) n FROM users u LEFT JOIN leads l ON l.user_id = u.id AND l.suspect = 0 AND l.brand_id = u.brand_id
            WHERE u.brand_id = ? GROUP BY u.id, u.name ORDER BY n DESC LIMIT 12");
        $q->execute([ws_id()]);
        echo '<h2>By team member</h2><div class="stats small">';
        foreach ($q as $r) echo '<div><b>' . (int)$r['n'] . '</b>' . h($r['name']) . '</div>';
        echo '</div>';
    }
    echo '<h2>Latest contacts</h2>';
    $q = db()->prepare("SELECT l.*, b.name brand, u.name owner FROM leads l LEFT JOIN brands b ON b.id = l.brand_id LEFT JOIN users u ON u.id = l.user_id
        WHERE $where AND l.suspect = 0 ORDER BY l.id DESC LIMIT 10");
    $q->execute($args);
    leads_table($q->fetchAll());
    echo '<p><a class="btn" href="index.php?p=leads">All contacts</a> <a class="btn ghost" href="index.php?p=scan">Quick add a contact</a></p>';
    page_foot(); break;

/* ── cards ───────────────────────────────────────────────────────────── */
case 'cards':
    $u = require_login();
    $sql = 'SELECT c.*, ' . CARD_BRAND_COLS . ', u.name owner,
        (SELECT COUNT(*) FROM leads l WHERE l.card_id = c.id AND l.suspect = 0) leads
        FROM cards c JOIN brands b ON b.id = c.brand_id JOIN users u ON u.id = c.user_id';
    $args = [ws_id()];
    $w = ['c.brand_id = ?'];
    if (!is_admin()) { $w[] = 'c.user_id = ?'; $args[] = $u['id']; }
    if (($_GET['q'] ?? '') !== '') { $w[] = '(c.full_name LIKE ? OR c.email LIKE ? OR c.title LIKE ?)'; array_push($args, ...array_fill(0, 3, '%' . $_GET['q'] . '%')); }
    $q = db()->prepare($sql . ' WHERE ' . implode(' AND ', $w) . ' ORDER BY c.full_name'); $q->execute($args);
    [$used, $max] = ws_seats(ws_id());
    page_head('Cards');
    echo '<div class="row"><h1>Cards' . (is_admin() && $max ? ' <span class="muted">' . $used . ' of ' . $max . '</span>' : '') . '</h1><div><a class="btn" href="index.php?p=card">+ New card</a>' . (is_admin() ? ' <a class="btn ghost" href="index.php?p=bulk">Bulk create</a>' : '') . '</div></div>';
    echo '<form class="filters" method="get"><input type="hidden" name="p" value="cards"><input name="q" placeholder="Search by name, email or title…" value="' . h((string)($_GET['q'] ?? '')) . '"><button>Search</button></form><div class="grid">';
    foreach ($q as $c) {
        $c = card_effective($c);
        $url = card_url($c['slug']);
        echo '<article class="tile" style="--brand:' . h($c['color']) . ';--accent:' . h($c['accent']) . '">'
           . '<div class="tile-top"><span class="pill">' . h($c['brand_name']) . '</span>' . ($c['active'] ? '' : ' <span class="pill off">off</span>') . '</div>'
           . '<h3>' . h($c['full_name']) . '</h3><p>' . h($c['title']) . '</p>'
           . '<div class="qr" data-qr="' . h($url) . '" data-name="' . h($c['slug']) . '"></div>'
           . '<p class="muted">' . (int)$c['views'] . ' views · ' . (int)$c['leads'] . ' contacts' . (is_admin() ? ' · ' . h($c['owner']) : '') . '<br><span class="small">' . h(explode(' — ', TEMPLATES[$c['tpl']])[0]) . ' design</span></p>'
           . '<div class="actions"><a href="' . h($url) . '" target="_blank">Open</a><a href="index.php?p=card&id=' . (int)$c['id'] . '">Edit</a>'
           . '<a href="#" data-copy="' . h($url) . '">Copy link</a><a href="#" data-dl-png>QR PNG</a><a href="#" data-dl-svg>QR SVG</a><a href="index.php?p=print&id=' . (int)$c['id'] . '" target="_blank">Print</a>'
           . '<a href="wallet.php?id=' . (int)$c['id'] . '&t=apple">Apple Wallet</a><a href="wallet.php?id=' . (int)$c['id'] . '&t=google">Google Wallet</a></div></article>';
    }
    echo '</div>';
    page_foot(); break;

case 'slugcheck':
    require_login();
    header('Content-Type: application/json');
    $want = slugify((string)($_GET['s'] ?? ''));
    $q = db()->prepare('SELECT id FROM cards WHERE slug = ? AND id != ?'); $q->execute([$want, (int)($_GET['id'] ?? 0)]);
    echo json_encode(['slug' => $want, 'free' => !$q->fetch(), 'url' => card_url($want)]);
    exit;

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
        foreach (['full_name' => 120, 'title' => 120, 'email' => 160, 'phone' => 40, 'whatsapp' => 40, 'website' => 200, 'bio' => 600,
                  'company_name' => 120, 'company_website' => 200, 'company_address' => 240, 'company_phone' => 40, 'company_email' => 160] as $k => $max) $f[$k] = post($k, $max);
        foreach (['website', 'company_website'] as $k) if ($f[$k] !== '' && !preg_match('~^https?://~i', $f[$k])) $f[$k] = 'https://' . $f[$k];
        $f['template'] = isset(TEMPLATES[$_POST['template'] ?? '']) ? $_POST['template'] : '';
        $f['wallet_style'] = isset(WALLET_STYLES[$_POST['wallet_style'] ?? '']) ? $_POST['wallet_style'] : '';
        $blocks = clean_blocks((string)($_POST['blocks'] ?? ''));
        $f['blocks'] = $blocks ? json_encode($blocks, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) : '';
        $brandId = ws_id();
        $owner = is_admin() ? (int)($_POST['user_id'] ?? $u['id']) : (int)($c['user_id'] ?? $u['id']);
        if (!in_array($owner, array_map('intval', array_column(ws_users(), 'id')), true) && $owner !== (int)$u['id']) $owner = (int)$u['id'];
        [$used, $max] = ws_seats($brandId);
        $wantSlug = post('slug', 48);
        if ($f['full_name'] === '') $err = 'Name is required.';
        elseif (!$c && $max && $used >= $max) $err = "This workspace has used all $max cards. Ask the platform owner for more.";
        elseif ($f['email'] !== '' && !filter_var($f['email'], FILTER_VALIDATE_EMAIL)) $err = 'Email looks wrong.';
        elseif ($wantSlug !== '' && unique_slug($wantSlug, (int)($c['id'] ?? 0)) !== slugify($wantSlug)) $err = 'The link name “' . slugify($wantSlug) . '” is taken — pick another.';
        if (!$err) {
            try { $photo = save_upload('photo'); } catch (RuntimeException $e) { $err = $e->getMessage(); $photo = null; }
        }
        if (!$err) {
            $slug = $wantSlug !== '' ? slugify($wantSlug) : ($c['slug'] ?? unique_slug($f['full_name'] . '-' . ws()['name']));
            $cols = $f + ['brand_id' => $brandId, 'user_id' => $owner, 'slug' => $slug, 'active' => isset($_POST['active']) ? 1 : 0, 'updated_at' => gmdate('Y-m-d H:i:s')];
            if ($photo !== null) $cols['photo'] = $photo;
            if (isset($_POST['remove_photo'])) $cols['photo'] = '';
            if ($c) {
                $set = implode(', ', array_map(fn($k) => "$k = :$k", array_keys($cols)));
                db()->prepare("UPDATE cards SET $set WHERE id = :id")->execute($cols + ['id' => $c['id']]);
            } else {
                db()->prepare('INSERT INTO cards (' . implode(',', array_keys($cols)) . ') VALUES (:' . implode(',:', array_keys($cols)) . ')')->execute($cols);
            }
            if ($slug !== ($c['slug'] ?? $slug)) flash('Card saved. Its link changed to ' . card_url($slug) . ' — QR codes printed with the old link no longer work.');
            else flash('Card saved: ' . card_url($slug));
            redirect('index.php?p=cards');
        }
        $c = array_merge($c ?? [], $_POST, ['blocks' => $f['blocks'] ?? '']);
    }
    $c ??= ['full_name' => $u['name'], 'email' => $u['email'], 'phone' => $u['phone'], 'active' => 1, 'user_id' => $u['id'], 'brand_id' => ws_id()];
    $v = fn(string $k) => h((string)($c[$k] ?? ''));
    $brandRow = !empty($c['brand_id']) ? brand((int)$c['brand_id']) : null;
    page_head($id ? 'Edit card' : 'New card');
    echo '<h1>' . ($id ? 'Edit card · ' . $v('full_name') : 'New card') . '</h1>' . ($err ? '<p class="err">' . h($err) . '</p>' : '');
    echo '<nav class="tabs"><a href="#personal">Personal</a><a href="#company">Company</a><a href="#links">Links</a><a href="#design">Design</a><a href="#url">Card URL</a></nav>';
    echo '<form method="post" enctype="multipart/form-data" class="form" id="cardform">' . csrf_field();

    echo '<section id="personal"><h2>Personal details</h2><div class="cols">';
    if (is_admin()) {
        echo '<label>Card holder<select name="user_id">';
        $people = ws_users();
        if (!in_array((int)$u['id'], array_map('intval', array_column($people, 'id')), true)) $people[] = ['id' => $u['id'], 'name' => $u['name'] . ' (owner)'];
        foreach ($people as $m) echo '<option value="' . $m['id'] . '"' . ((int)($c['user_id'] ?? 0) === (int)$m['id'] ? ' selected' : '') . '>' . h($m['name']) . '</option>';
        echo '</select></label>';
    }
    foreach (['full_name' => 'Full name *', 'title' => 'Job title', 'email' => 'Email', 'phone' => 'Phone (+country code)', 'whatsapp' => 'WhatsApp (+country code)', 'website' => 'Personal website'] as $k => $label)
        echo '<label>' . h($label) . '<input name="' . $k . '" value="' . $v($k) . '"' . ($k === 'full_name' ? ' required' : '') . '></label>';
    echo '</div><label>Short bio<textarea name="bio" rows="2">' . $v('bio') . '</textarea></label>';
    echo '<label>Photo (JPG/PNG/WebP, square works best)<input type="file" name="photo" accept="image/jpeg,image/png,image/webp"></label>';
    if (!empty($c['photo']) && is_string($c['photo'])) echo '<p><img class="avatar" src="' . h(photo_url($c['photo'])) . '" alt=""> <label class="check"><input type="checkbox" name="remove_photo"> remove photo</label></p>';
    echo '<label class="check"><input type="checkbox" name="active"' . (!empty($c['active']) ? ' checked' : '') . '> Card is live</label></section>';

    echo '<section id="company"><h2>Company details</h2><p class="muted">Leave a field empty to use the brand default' . ($brandRow ? ' (' . h($brandRow['name']) . ')' : '') . '. Defaults are set by an admin under Branding.</p><div class="cols">';
    foreach (['company_name' => ['Company name', 'company_name'], 'company_website' => ['Company website', 'domain'], 'company_address' => ['Address', 'company_address'],
              'company_phone' => ['Office phone', 'company_phone'], 'company_email' => ['Office email', 'company_email']] as $k => [$label, $bk])
        echo '<label>' . $label . '<input name="' . $k . '" value="' . $v($k) . '" placeholder="' . h($brandRow ? ($bk === 'domain' && $brandRow['domain'] ? 'https://' . $brandRow['domain'] : (string)$brandRow[$bk]) : '') . '"></label>';
    echo '</div></section>';

    $blocks = card_blocks($c + ['phone' => '', 'whatsapp' => '', 'email' => '', 'linkedin' => '', 'instagram' => '']);
    echo '<section id="links"><h2>Links</h2><p class="muted">The buttons on your card, top to bottom. Drag or use ↑ ↓ to reorder; untick “Show” to hide one.</p>'
       . '<input type="hidden" name="blocks" id="blocks-json"><div id="blocks" data-blocks="' . h(json_encode($blocks, JSON_UNESCAPED_UNICODE)) . '" data-types="' . h(json_encode(BLOCK_TYPES)) . '" data-socials="' . h(json_encode(array_map(fn($s) => $s[0], SOCIALS))) . '"></div>'
       . '<div class="addblock"><select id="addtype">';
    foreach (BLOCK_TYPES as $t => $bt) if (!in_array($t, ['exchange', 'save'], true)) echo '<option value="' . $t . '">' . h($bt[0]) . '</option>';
    echo '</select> <button type="button" class="ghost btn" id="addblock">+ Add</button></div></section>';

    echo '<section id="design"><h2>Card design</h2><div class="tpls"><label class="tpl"><input type="radio" name="template" value=""' . (($c['template'] ?? '') === '' ? ' checked' : '') . '><span class="tplbox tpl-default">Brand default</span></label>';
    foreach (TEMPLATES as $t => $label) echo '<label class="tpl"><input type="radio" name="template" value="' . $t . '"' . (($c['template'] ?? '') === $t ? ' checked' : '') . '><span class="tplbox tpl-' . $t . '"><i></i><b></b><em></em><em></em></span><small>' . h($label) . '</small></label>';
    echo '</div><h3>Wallet pass colour</h3><div class="tpls"><label class="tpl"><input type="radio" name="wallet_style" value=""' . (($c['wallet_style'] ?? '') === '' ? ' checked' : '') . '><span class="wbox">Brand default</span></label>';
    foreach (WALLET_STYLES as $w => $label) echo '<label class="tpl"><input type="radio" name="wallet_style" value="' . $w . '"' . (($c['wallet_style'] ?? '') === $w ? ' checked' : '') . '><span class="wbox w-' . $w . '">' . h($label) . '</span></label>';
    echo '</div></section>';

    echo '<section id="url"><h2>Card URL</h2><label>Link name<span class="slugrow"><span class="muted">' . h(base_url()) . (cfg('pretty_urls', true) ? '/u/' : '/card.php?u=') . '</span><input name="slug" id="slug" value="' . $v('slug') . '" placeholder="auto from name" data-id="' . (int)($c['id'] ?? 0) . '"></span></label>'
       . '<button type="button" class="ghost btn" id="slugcheck">Check availability</button> <span id="slugmsg" class="muted"></span>'
       . '<p class="muted">Changing the link breaks QR codes already printed with the old one.</p></section>';
    echo '<div class="savebar"><button>Save card</button> <a href="index.php?p=cards">Cancel</a></div></form>';
    if ($id) echo '<form method="post" onsubmit="return confirm(\'Delete this card? Contacts captured by it are kept.\')">' . csrf_field() . '<button name="delete" value="1" class="danger">Delete card</button></form>';
    page_foot(); break;

case 'bulk':
    // Many cards at once: one row per person. New emails become invited users.
    $u = require_admin();
    $report = [];
    if ($isPost) {
        $brandId = ws_id();
        $rows = [];
        foreach ((array)($_POST['rows'] ?? []) as $r) $rows[] = array_map(fn($x) => clean((string)$x, 160), (array)$r);
        if (!empty($_FILES['csv']['tmp_name'])) {
            $fh = fopen($_FILES['csv']['tmp_name'], 'r');
            $head = array_map(fn($x) => strtolower(trim(preg_replace('/^\xEF\xBB\xBF/', '', (string)$x))), fgetcsv($fh, null, ',', '"', '') ?: []);
            $col = function (array $names) use ($head): ?int { foreach ($names as $n) if (($i = array_search($n, $head, true)) !== false) return $i; return null; };
            $ix = ['name' => $col(['name', 'full name']), 'email' => $col(['email', 'email (login)']), 'mobile' => $col(['mobile', 'phone']), 'title' => $col(['title', 'job title']), 'admin' => $col(['admin', 'role'])];
            while (($r = fgetcsv($fh, null, ',', '"', '')) !== false) {
                $g = fn($k) => $ix[$k] === null ? '' : clean((string)($r[$ix[$k]] ?? ''), 160);
                $rows[] = ['name' => $g('name'), 'email' => $g('email'), 'mobile' => $g('mobile'), 'title' => $g('title'), 'admin' => in_array(strtolower($g('admin')), ['1', 'yes', 'true', 'admin'], true) ? '1' : ''];
            }
        }
        $sendMail = isset($_POST['send_invites']);
        foreach ($rows as $r) {
            $name = $r['name'] ?? ''; $email = strtolower($r['email'] ?? '');
            if ($name === '' && $email === '') continue;
            if ($name === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) { $report[] = [$name ?: $email, 'skipped — needs a name and a valid email', '']; continue; }
            $q = db()->prepare('SELECT * FROM users WHERE email = ?'); $q->execute([$email]); $usr = $q->fetch();
            if ($usr && (int)$usr['brand_id'] !== $brandId) { $report[] = [$name, 'skipped — this email belongs to another workspace', '']; continue; }
            [$used, $max] = ws_seats($brandId);
            if ($max && $used >= $max) { $report[] = [$name, "skipped — card limit ($max) reached", '']; continue; }
            $link = '';
            if (!$usr) {
                db()->prepare("INSERT INTO users (email, name, phone, password_hash, role, status, brand_id) VALUES (?,?,?,?,?, 'invited', ?)")
                    ->execute([$email, $name, $r['mobile'] ?? '', password_hash(bin2hex(random_bytes(16)), PASSWORD_DEFAULT), !empty($r['admin']) ? 'admin' : 'member', $brandId]);
                $q->execute([$email]); $usr = $q->fetch();
                $link = issue_invite((int)$usr['id']);
            }
            $has = db()->prepare('SELECT slug FROM cards WHERE user_id = ? AND brand_id = ?'); $has->execute([$usr['id'], $brandId]);
            if ($slug = $has->fetchColumn()) { $report[] = [$name, 'already has a card here', card_url($slug)]; continue; }
            $slug = unique_slug($name . '-' . ws()['name']);
            db()->prepare('INSERT INTO cards (user_id, brand_id, slug, full_name, title, email, phone, updated_at) VALUES (?,?,?,?,?,?,?,?)')
                ->execute([$usr['id'], $brandId, $slug, $name, $r['title'] ?? '', $email, $r['mobile'] ?? '', gmdate('Y-m-d H:i:s')]);
            $mailed = $link && $sendMail ? send_invite($usr, $link) : false;
            $report[] = [$name, 'card created' . ($link ? ($mailed ? ' · invite emailed' : ' · invite link below') : ' · existing user'), $link ?: card_url($slug)];
        }
    }
    page_head('Bulk create');
    echo '<h1>Bulk create cards</h1>';
    if ($report) {
        echo '<div class="flash">Done — ' . count($report) . ' rows. Invite links are valid 7 days; send them privately if they were not emailed.</div><table class="tbl"><tr><th>Name</th><th>Result</th><th>Link</th></tr>';
        foreach ($report as [$n, $res, $l]) echo '<tr><td>' . h($n) . '</td><td>' . h($res) . '</td><td>' . ($l ? '<a href="#" data-copy="' . h($l) . '">Copy</a> <span class="muted small">' . h($l) . '</span>' : '') . '</td></tr>';
        echo '</table>';
    }
    echo '<form method="post" enctype="multipart/form-data" class="form">' . csrf_field() . '<p class="muted">Cards are created in <b>' . h(ws()['name']) . '</b>. New emails become invited team members of this workspace.</p><table class="tbl rows" id="bulkrows"><tr><th>Full name</th><th>Email (login)</th><th>Mobile</th><th>Title</th><th>Admin</th></tr>';
    for ($i = 0; $i < 3; $i++) echo '<tr><td><input name="rows[' . $i . '][name]"></td><td><input type="email" name="rows[' . $i . '][email]"></td><td><input name="rows[' . $i . '][mobile]"></td><td><input name="rows[' . $i . '][title]"></td><td><input type="checkbox" name="rows[' . $i . '][admin]" value="1"></td></tr>';
    echo '</table><p><button type="button" class="ghost btn" id="addrow">+ Add another</button></p>'
       . '<label>…or a CSV file (columns: name, email, mobile, title, admin)<input type="file" name="csv" accept=".csv,text/csv"></label>'
       . '<label class="check"><input type="checkbox" name="send_invites"' . (cfg('mail_from') ? ' checked' : ' disabled') . '> Email each new person their invite' . (cfg('mail_from') ? '' : ' (set mail_from in config.php to enable)') . '</label>'
       . '<p><button>Create cards</button></p></form>';
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
    // Quick add: someone met in person. Photograph their business card or badge and the AI scanner fills the form.
    $u = require_login();
    $myCards = db()->prepare('SELECT c.id, c.full_name, b.name brand FROM cards c JOIN brands b ON b.id = c.brand_id WHERE c.user_id = ? AND c.brand_id = ? ORDER BY c.full_name');
    $myCards->execute([$u['id'], ws_id()]); $myCards = $myCards->fetchAll();
    $err = ''; $pre = []; $source = (string)($_POST['source'] ?? 'manual');
    if ($isPost && isset($_POST['do_scan'])) {
        try {
            $f = $_FILES['cardphoto'] ?? null;
            if (!$f || $f['error'] !== UPLOAD_ERR_OK) throw new RuntimeException('Take or choose a photo first.');
            [$path, $mime] = shrink_image($f['tmp_name']);
            $pre = ai_scan_card($path, $mime);
            @unlink($path);
            $pre['note'] = trim(implode("\n", array_filter([$pre['website'] ?? '', $pre['address'] ?? ''])));
            $source = 'scan';
            if (!array_filter($pre)) $err = 'Nothing readable on that photo — try again closer, or type the details.';
        } catch (RuntimeException $e) { $err = $e->getMessage(); }
        $pre += ['event' => post('event', 120), 'card_id' => (int)($_POST['card_id'] ?? 0)];
    } elseif ($isPost) {
        $cardId = (int)($_POST['card_id'] ?? 0);
        $card = $cardId ? card_by_id($cardId) : null;
        if ($card && !can_edit_card($card)) $card = null;
        $brandId = ws_id();
        if (post('name') === '') $err = 'Name is required.';
        elseif (post('email') !== '' && !filter_var(post('email'), FILTER_VALIDATE_EMAIL)) $err = 'Email looks wrong.';
        else {
            insert_lead(['card_id' => $card['id'] ?? null, 'user_id' => $u['id'], 'brand_id' => $brandId,
                         'source' => $source === 'scan' ? 'scan' : 'manual', 'consent' => isset($_POST['consent']) ? 1 : 0]);
            $_SESSION['last_event'] = post('event', 120);
            $_SESSION['last_card'] = $cardId;
            flash('Saved ' . post('name') . '.'); redirect('index.php?p=scan');
        }
        $pre = $_POST;
    }
    $pv = fn(string $k) => h((string)($pre[$k] ?? ''));
    $selCard = (int)($pre['card_id'] ?? ($_SESSION['last_card'] ?? 0));
    page_head('Quick add');
    echo '<h1>Quick add a contact</h1>' . ($err ? '<p class="err">' . h($err) . '</p>' : '');
    echo '<form method="post" enctype="multipart/form-data" class="form">' . csrf_field() . '<input type="hidden" name="source" value="' . h($source) . '">';
    echo '<div class="scanbox"><b>Scan a business card or badge</b><span class="muted">' . (cfg('anthropic_api_key') ? 'Photo is read by AI, then you check the fields and save. The photo is not kept.' : 'AI scanner is off — add anthropic_api_key in config.php.') . '</span>'
       . '<input type="file" name="cardphoto" accept="image/*" capture="environment"' . (cfg('anthropic_api_key') ? '' : ' disabled') . '><button name="do_scan" value="1" class="ghost btn" formnovalidate' . (cfg('anthropic_api_key') ? '' : ' disabled') . '>Read card</button></div>';
    if ($source === 'scan' && !$err) echo '<p class="flash">Read by the AI scanner — check every field before saving.</p>';
    echo '<div class="cols"><label>Captured on card<select name="card_id"><option value="">— none —</option>';
    foreach ($myCards as $mc) echo '<option value="' . $mc['id'] . '"' . ($selCard === (int)$mc['id'] ? ' selected' : '') . '>' . h($mc['brand'] . ' · ' . $mc['full_name']) . '</option>';
    echo '</select></label>';
    foreach (['name' => 'Name *', 'email' => 'Email', 'phone' => 'Phone', 'company' => 'Company', 'job_title' => 'Job title'] as $k => $l)
        echo '<label>' . $l . '<input name="' . $k . '" value="' . $pv($k) . '"' . ($k === 'name' ? ' required' : '') . ($k === 'email' ? ' type="email"' : '') . '></label>';
    echo '<label>Event / place<input name="event" list="events" value="' . h((string)($pre['event'] ?? ($_SESSION['last_event'] ?? ''))) . '"></label>' . events_datalist()
       . '</div><label>Note<textarea name="note" rows="3">' . $pv('note') . '</textarea></label>'
       . '<label class="check"><input type="checkbox" name="consent"> They agreed to be contacted</label><p><button>Save contact</button></p></form>';
    page_foot(); break;

case 'import':
    // HeyDrop (or any) CSV export → contacts. Header names are matched loosely.
    $u = require_admin();
    $report = '';
    if ($isPost && !empty($_FILES['csv']['tmp_name'])) {
        $brandId = ws_id(); $owner = (int)($_POST['user_id'] ?? $u['id']);
        if (!in_array($owner, array_map('intval', array_column(ws_users(), 'id')), true)) $owner = (int)$u['id'];
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
        $exists = db()->prepare("SELECT 1 FROM leads WHERE brand_id = ? AND email != '' AND LOWER(email) = LOWER(?)");
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
        $report = "Imported $ok · skipped $skip empty rows · $dupe already present (same email in this workspace). Columns recognised: " . implode(', ', array_keys($map));
    }
    page_head('Import');
    echo '<h1>Import contacts (CSV)</h1>' . ($report ? '<div class="flash">' . h($report) . '</div>' : '')
       . '<p class="muted">Export your contacts from HeyDrop (or any CRM) as CSV and load them here. Recognised headers: name / first name / last name, email, phone, company, title, note, event/tag, date.</p>'
       . '<form method="post" enctype="multipart/form-data" class="form">' . csrf_field() . '<div class="cols"><label>Assign to<select name="user_id">';
    foreach (ws_users() as $m) echo '<option value="' . $m['id'] . '">' . h($m['name']) . '</option>';
    echo '</select></label></div><label>CSV file<input type="file" name="csv" accept=".csv,text/csv" required></label><p><button>Import</button></p></form>';
    page_foot(); break;

/* ── team & brands (admin) ───────────────────────────────────────────── */
case 'team':
    $u = require_admin();
    if ($isPost) {
        $target = (int)($_POST['uid'] ?? 0);
        $q = db()->prepare('SELECT * FROM users WHERE id = ? AND brand_id = ?'); $q->execute([$target, ws_id()]); $t = $q->fetch();
        $act = (string)($_POST['act'] ?? 'add');
        if ($act !== 'add' && !$t) { flash('No such user.'); redirect('index.php?p=team'); }
        if ($act !== 'add' && (int)$t['id'] === (int)$u['id'] && in_array($act, ['remove', 'cancel', 'role'], true)) { flash('You cannot change or remove yourself.'); redirect('index.php?p=team'); }
        switch ($act) {
            case 'remove': case 'cancel':
                db()->prepare('DELETE FROM users WHERE id = ?')->execute([$t['id']]);
                flash($act === 'cancel' ? 'Invitation cancelled.' : 'Removed. Their cards are deleted; their contacts are kept, unassigned.'); break;
            case 'role':
                db()->prepare('UPDATE users SET role = ? WHERE id = ?')->execute([$t['role'] === 'admin' ? 'member' : 'admin', $t['id']]);
                flash($t['name'] . ' is now ' . ($t['role'] === 'admin' ? 'a member' : 'an admin') . '.'); break;
            case 'invite':  // (re)send invitation, or a password-reset link for an active user
                $link = issue_invite((int)$t['id']);
                $mailed = isset($_POST['email']) && send_invite($t, $link);
                flash(($mailed ? 'Emailed to ' . $t['email'] . '. ' : '') . 'Link for ' . $t['name'] . ' (valid 7 days): ' . $link); break;
            default:
                $email = strtolower(post('email', 160));
                if (post('name') === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) { flash('Name and a valid email are needed.'); break; }
                try {
                    db()->prepare("INSERT INTO users (email, name, phone, password_hash, role, status, brand_id) VALUES (?,?,?,?,?, 'invited', ?)")
                        ->execute([$email, post('name'), post('phone', 40), password_hash(bin2hex(random_bytes(16)), PASSWORD_DEFAULT), ($_POST['role'] ?? '') === 'admin' ? 'admin' : 'member', ws_id()]);
                } catch (PDOException) { flash('That email already has an account (in this or another workspace).'); break; }
                $nu = ['id' => (int)db()->lastInsertId(), 'name' => post('name'), 'email' => $email];
                $link = issue_invite($nu['id']);
                $mailed = isset($_POST['send']) && send_invite($nu, $link);
                flash('Invited ' . $nu['name'] . '. ' . ($mailed ? 'Invite emailed. ' : '') . 'Invite link (valid 7 days): ' . $link . ' — now create their card under Cards.');
        }
        redirect('index.php?p=team');
    }
    page_head('Team');
    $mailOn = (bool)cfg('mail_from');
    echo '<div class="row"><h1>Team · ' . h(ws()['name']) . '</h1><a class="btn ghost" href="index.php?p=bulk">Bulk create cards</a></div><div class="scroll"><table class="tbl"><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Cards</th><th>Contacts</th><th>Created</th><th></th></tr>';
    $tq = db()->prepare('SELECT u.*, (SELECT COUNT(*) FROM cards c WHERE c.user_id = u.id) cards, (SELECT COUNT(*) FROM leads l WHERE l.user_id = u.id AND l.suspect = 0) leads FROM users u WHERE u.brand_id = ? ORDER BY u.status DESC, u.name');
    $tq->execute([ws_id()]);
    foreach ($tq as $m) {
        $btn = fn(string $act, string $label, string $extra = '') => '<form method="post" class="inline">' . csrf_field() . '<input type="hidden" name="uid" value="' . $m['id'] . '"><input type="hidden" name="act" value="' . $act . '">' . $extra . '<button class="link' . (in_array($act, ['remove', 'cancel'], true) ? ' danger" onclick="return confirm(\'Sure?\')' : '') . '">' . $label . '</button></form>';
        $self = (int)$m['id'] === (int)$u['id'];
        echo '<tr><td>' . h($m['name']) . '</td><td>' . h($m['email']) . '</td><td><span class="dot ' . h($m['role']) . '"></span>' . h(ucfirst($m['role'])) . '</td>'
           . '<td><span class="st st-' . h($m['status']) . '">' . h(ucfirst($m['status'])) . '</span></td><td>' . $m['cards'] . '</td><td>' . $m['leads'] . '</td><td class="nowrap">' . h(substr($m['created_at'], 0, 10)) . '</td><td class="acts">';
        if ($m['status'] === 'invited') echo $btn('invite', 'Get invite link') . ($mailOn ? $btn('invite', 'Resend email', '<input type="hidden" name="email" value="1">') : '') . (!$self ? $btn('cancel', 'Cancel invite') : '');
        else echo $btn('invite', 'Password reset link');
        if (!$self) echo $btn('role', $m['role'] === 'admin' ? 'Make member' : 'Make admin') . ($m['status'] !== 'invited' ? $btn('remove', 'Remove') : '');
        echo '</td></tr>';
    }
    echo '</table></div><h2>Invite a team member</h2><form method="post" class="form">' . csrf_field() . '<input type="hidden" name="act" value="add"><div class="cols">'
       . '<label>Name<input name="name" required></label><label>Email (login)<input name="email" type="email" required></label><label>Mobile<input name="phone"></label>'
       . '<label>Role<select name="role"><option value="member">Member — own cards & contacts</option><option value="admin">Admin — everything</option></select></label></div>'
       . '<label class="check"><input type="checkbox" name="send"' . ($mailOn ? ' checked' : ' disabled') . '> Email them the invite' . ($mailOn ? '' : ' (set mail_from in config.php)') . '</label>'
       . '<p><button>Invite</button></p></form>';
    page_foot(); break;

case 'invite':
    // Public: an invited person (or a reset) sets their password from the emailed / copied link.
    $tok = (string)($_GET['t'] ?? '');
    $q = db()->prepare("SELECT * FROM users WHERE invite_token = ? AND invite_token != '' AND invite_expires > ?");
    $q->execute([hash('sha256', $tok), utc()]); $t = $q->fetch();
    $err = '';
    if ($t && $isPost) {
        $pw = (string)($_POST['password'] ?? '');
        if (strlen($pw) < 10) $err = 'Use at least 10 characters.';
        elseif ($pw !== (string)($_POST['password2'] ?? '')) $err = 'The two passwords differ.';
        else {
            db()->prepare("UPDATE users SET password_hash = ?, status = 'active', invite_token = '', invite_expires = '' WHERE id = ?")->execute([password_hash($pw, PASSWORD_DEFAULT), $t['id']]);
            session_regenerate_id(true); $_SESSION['uid'] = (int)$t['id'];
            flash('Welcome, ' . $t['name'] . '. Your cards are below.'); redirect('index.php?p=cards');
        }
    }
    page_head('Set your password', 'auth');
    echo '<div class="authbox"><h1>TeamCards</h1>';
    if (!$t) echo '<p class="err">This link has expired or was already used. Ask your admin for a new one.</p><p><a href="index.php?p=login">Sign in</a></p>';
    else echo '<p>Hi ' . h($t['name']) . ' — choose a password for <b>' . h($t['email']) . '</b>.</p>' . ($err ? '<p class="err">' . h($err) . '</p>' : '')
        . '<form method="post">' . csrf_field() . '<label>Password<input type="password" name="password" minlength="10" autocomplete="new-password" required></label>'
        . '<label>Again<input type="password" name="password2" minlength="10" autocomplete="new-password" required></label><button>Save and sign in</button></form>';
    echo '</div>';
    page_foot(); break;

case 'brands':
    // Branding of the current workspace: colours, logo, company details, default design.
    require_admin();
    $b = ws();
    if ($isPost) {
        $hex = fn($k, $d) => preg_match('/^#[0-9a-f]{6}$/i', post($k)) ? post($k) : $d;
        try { $logo = save_upload('logo'); } catch (RuntimeException $e) { flash($e->getMessage()); redirect('index.php?p=brands'); }
        $cols = ['domain' => strtolower(preg_replace('~^https?://|/.*$~i', '', post('domain', 120))), 'color' => $hex('color', '#0f3d5e'),
                 'accent' => $hex('accent', '#e8b04a'), 'tagline' => post('tagline', 160), 'company_name' => post('company_name', 120),
                 'company_address' => post('company_address', 240), 'company_phone' => post('company_phone', 40), 'company_email' => post('company_email', 160),
                 'template' => isset(TEMPLATES[$_POST['template'] ?? '']) ? $_POST['template'] : 'classic',
                 'wallet_style' => isset(WALLET_STYLES[$_POST['wallet_style'] ?? '']) ? $_POST['wallet_style'] : 'brand'];
        if (is_owner() && post('name', 80) !== '') $cols['name'] = post('name', 80);   // the workspace name is the owner's call
        if ($logo) $cols['logo'] = $logo;
        if (isset($_POST['remove_logo'])) $cols['logo'] = '';
        db()->prepare('UPDATE brands SET ' . implode(', ', array_map(fn($k) => "$k = :$k", array_keys($cols))) . ' WHERE id = :id')->execute($cols + ['id' => $b['id']]);
        if (($_POST['apply'] ?? '') === 'all') {
            // "Save for all cards": every card drops its own company details and design and follows the brand again.
            $n = db()->prepare("UPDATE cards SET company_name = '', company_website = '', company_address = '', company_phone = '', company_email = '', template = '', wallet_style = '' WHERE brand_id = ?");
            $n->execute([$b['id']]);
            flash('Branding saved and applied to all ' . $n->rowCount() . ' cards.');
        } else flash('Branding saved. New cards, and cards left on the defaults, follow it; cards with their own settings keep them.');
        redirect('index.php?p=brands');
    }
    page_head('Branding');
    echo '<h1>Branding · ' . h($b['name']) . '</h1><p class="muted">Defaults for every card in this workspace. A card can still override any of them.</p>'
       . '<form method="post" enctype="multipart/form-data" class="form">' . csrf_field() . '<div class="cols">'
       . (is_owner() ? '<label>Workspace name<input name="name" value="' . h($b['name']) . '" required></label>' : '')
       . '<label>Website domain<input name="domain" value="' . h($b['domain']) . '" placeholder="example.com"></label>'
       . '<label>Main colour<input type="color" name="color" value="' . h($b['color']) . '"></label><label>Accent<input type="color" name="accent" value="' . h($b['accent']) . '"></label>'
       . '<label>Tagline<input name="tagline" value="' . h($b['tagline']) . '"></label>'
       . '<label>Logo (PNG, transparent)' . ($b['logo'] ? ' <img class="logo-s" src="' . h(photo_url($b['logo'])) . '" alt=""> <span class="check small"><input type="checkbox" name="remove_logo"> remove</span>' : '') . '<input type="file" name="logo" accept="image/png,image/jpeg,image/webp"></label>'
       . '<label>Company name<input name="company_name" value="' . h($b['company_name']) . '" placeholder="' . h($b['name']) . '"></label><label>Address<input name="company_address" value="' . h($b['company_address']) . '"></label>'
       . '<label>Office phone<input name="company_phone" value="' . h($b['company_phone']) . '"></label><label>Office email<input name="company_email" value="' . h($b['company_email']) . '"></label>'
       . '<label>Default card design<select name="template">';
    foreach (TEMPLATES as $t => $l) echo '<option value="' . $t . '"' . ($b['template'] === $t ? ' selected' : '') . '>' . h($l) . '</option>';
    echo '</select></label><label>Default wallet colour<select name="wallet_style">';
    foreach (WALLET_STYLES as $w => $l) echo '<option value="' . $w . '"' . ($b['wallet_style'] === $w ? ' selected' : '') . '>' . h($l) . '</option>';
    echo '</select></label></div><p><button name="apply" value="defaults">Save for new cards</button>'
       . ' <button name="apply" value="all" class="ghost btn" onclick="return confirm(\'Every card in this workspace loses its own company details and design and follows the branding. Continue?\')">Save for all cards</button></p></form>';
    page_foot(); break;

/* ── platform owner ─────────────────────────────────────────────────── */
case 'switch':
    require_owner();
    if ($isPost) {
        $to = (int)($_POST['ws'] ?? 0);
        $_SESSION['ws'] = $to && brand($to) ? $to : 0;
    }
    redirect($_SESSION['ws'] ? 'index.php?p=home' : 'index.php?p=owner');

case 'owner':
    $u = require_owner();
    if ($isPost) {
        $act = (string)($_POST['act'] ?? '');
        $id = (int)($_POST['id'] ?? 0);
        if ($act === 'create') {
            $name = post('name', 80);
            $email = strtolower(post('admin_email', 160));
            if ($name === '') { flash('Give the workspace a name.'); redirect('index.php?p=owner'); }
            if ($email !== '' && !filter_var($email, FILTER_VALIDATE_EMAIL)) { flash('The admin email looks wrong.'); redirect('index.php?p=owner'); }
            if ($email !== '') { $q = db()->prepare('SELECT 1 FROM users WHERE email = ?'); $q->execute([$email]); if ($q->fetch()) { flash("$email already has an account."); redirect('index.php?p=owner'); } }
            $hex = fn($k, $d) => preg_match('/^#[0-9a-f]{6}$/i', post($k)) ? post($k) : $d;
            db()->prepare("INSERT INTO brands (slug, name, domain, color, accent, max_cards, status, created_at) VALUES (?,?,?,?,?,?, 'active', ?)")
                ->execute([slugify($name) . '-' . bin2hex(random_bytes(2)), $name, strtolower(preg_replace('~^https?://|/.*$~i', '', post('domain', 120))),
                           $hex('color', '#0f3d5e'), $hex('accent', '#e8b04a'), max(0, (int)($_POST['max_cards'] ?? 0)), utc()]);
            $wsId = (int)db()->lastInsertId();
            $msg = "Workspace “{$name}” created.";
            if ($email !== '') {
                db()->prepare("INSERT INTO users (email, name, password_hash, role, status, brand_id) VALUES (?,?,?, 'admin', 'invited', ?)")
                    ->execute([$email, post('admin_name', 120) ?: $email, password_hash(bin2hex(random_bytes(16)), PASSWORD_DEFAULT), $wsId]);
                $adm = ['id' => (int)db()->lastInsertId(), 'name' => post('admin_name', 120) ?: $email, 'email' => $email];
                $link = issue_invite($adm['id']);
                $mailed = isset($_POST['send']) && send_invite($adm, $link);
                $msg .= ' Admin ' . $adm['name'] . ' invited' . ($mailed ? ' by email' : '') . '. Invite link (7 days): ' . $link;
            }
            flash($msg);
        } elseif ($b = brand($id)) {
            if ($act === 'status') {
                $new = $b['status'] === 'active' ? 'suspended' : 'active';
                db()->prepare('UPDATE brands SET status = ? WHERE id = ?')->execute([$new, $id]);
                flash($b['name'] . ($new === 'active' ? ' is active again.' : ' is suspended: its team cannot sign in and its public cards are offline.'));
            } elseif ($act === 'limit') {
                db()->prepare('UPDATE brands SET max_cards = ?, name = ? WHERE id = ?')->execute([max(0, (int)($_POST['max_cards'] ?? 0)), post('name', 80) ?: $b['name'], $id]);
                flash('Saved ' . (post('name', 80) ?: $b['name']) . '.');
            } elseif ($act === 'delete') {
                $n = db()->prepare('SELECT (SELECT COUNT(*) FROM cards WHERE brand_id = ?) + (SELECT COUNT(*) FROM leads WHERE brand_id = ?) + (SELECT COUNT(*) FROM users WHERE brand_id = ?)');
                $n->execute([$id, $id, $id]);
                if ((int)$n->fetchColumn() > 0) flash('Only an empty workspace can be deleted. Suspend it instead — nothing is lost.');
                else { db()->prepare('DELETE FROM brands WHERE id = ?')->execute([$id]); flash('Workspace deleted.'); }
            }
        }
        redirect('index.php?p=owner');
    }
    $since30 = utc('-30 days');
    $concat = is_mysql() ? "GROUP_CONCAT(u.name SEPARATOR ', ')" : "GROUP_CONCAT(u.name, ', ')";
    $rows = db()->query("SELECT b.*,
        (SELECT COUNT(*) FROM cards c WHERE c.brand_id = b.id) cards,
        (SELECT COUNT(*) FROM users u WHERE u.brand_id = b.id) people,
        (SELECT $concat FROM users u WHERE u.brand_id = b.id AND u.role = 'admin') admins,
        (SELECT COUNT(*) FROM leads l WHERE l.brand_id = b.id AND l.suspect = 0) leads,
        (SELECT COUNT(*) FROM leads l WHERE l.brand_id = b.id AND l.suspect = 0 AND l.created_at >= '$since30') leads30,
        (SELECT COALESCE(SUM(views),0) FROM cards c WHERE c.brand_id = b.id) views,
        (SELECT MAX(created_at) FROM leads l WHERE l.brand_id = b.id) last_lead
        FROM brands b ORDER BY b.status, b.name")->fetchAll();
    $tot = fn($k) => array_sum(array_column($rows, $k));
    page_head('Owner panel');
    echo '<h1>Owner panel</h1><p class="muted">Every sub-brand runs as its own workspace with its own admins, team, cards and contacts. They cannot see each other; you can enter any of them.</p>'
       . '<div class="stats"><div><b>' . count($rows) . '</b>workspaces</div><div><b>' . $tot('cards') . '</b>cards</div><div><b>' . $tot('people') . '</b>people</div><div><b>' . $tot('leads') . '</b>contacts</div><div><b>' . $tot('leads30') . '</b>contacts, last 30 days</div></div>'
       . '<h2>Workspaces</h2><div class="scroll"><table class="tbl"><tr><th>Workspace</th><th>Status</th><th>Admins</th><th>People</th><th>Cards / limit</th><th>Contacts</th><th>30 days</th><th>Views</th><th>Last contact</th><th></th></tr>';
    foreach ($rows as $r) {
        $form = fn(string $act, string $label, string $extra = '', string $cls = 'link') => '<form method="post" class="inline"' . ($label === 'Suspend' ? ' onsubmit="return confirm(\'Suspend ' . h(addslashes($r['name'])) . '? Its team is signed out and its public cards go offline until you activate it again. Nothing is deleted.\')"' : '') . '>' . csrf_field() . '<input type="hidden" name="act" value="' . $act . '"><input type="hidden" name="id" value="' . $r['id'] . '">' . $extra . '<button class="' . $cls . '">' . $label . '</button></form>';
        echo '<tr><td><span class="swatch" style="background:' . h($r['color']) . '"></span><b>' . h($r['name']) . '</b><br><span class="muted small">' . h($r['domain']) . '</span></td>'
           . '<td><span class="st st-' . ($r['status'] === 'active' ? 'active' : 'lost') . '">' . h($r['status']) . '</span></td>'
           . '<td>' . h($r['admins'] ?: '—') . '</td><td>' . $r['people'] . '</td><td>' . $r['cards'] . ' / ' . ($r['max_cards'] ?: '∞') . '</td>'
           . '<td>' . $r['leads'] . '</td><td>' . $r['leads30'] . '</td><td>' . $r['views'] . '</td><td class="nowrap">' . h(substr((string)$r['last_lead'], 0, 10) ?: '—') . '</td><td class="acts">'
           . '<form method="post" action="index.php?p=switch" class="inline">' . csrf_field() . '<input type="hidden" name="ws" value="' . $r['id'] . '"><button class="btn small">Enter</button></form> '
           . $form('status', $r['status'] === 'active' ? 'Suspend' : 'Activate')
           . '<details class="inline-edit"><summary>Edit</summary>' . $form('limit', 'Save', '<input name="name" value="' . h($r['name']) . '" aria-label="Name"> <input type="number" min="0" name="max_cards" value="' . (int)$r['max_cards'] . '" aria-label="Card limit" title="Card limit, 0 = unlimited"> ', 'btn small')
           . ($r['cards'] + $r['leads'] + $r['people'] == 0 ? $form('delete', 'Delete', '', 'link danger') : '') . '</details></td></tr>';
    }
    echo '</table></div><h2>Create a workspace</h2><form method="post" class="form">' . csrf_field() . '<input type="hidden" name="act" value="create"><div class="cols">'
       . '<label>Sub-brand name<input name="name" required placeholder="e.g. Cruise24"></label><label>Website domain<input name="domain" placeholder="cruise24.me"></label>'
       . '<label>Main colour<input type="color" name="color" value="#0f3d5e"></label><label>Accent<input type="color" name="accent" value="#e8b04a"></label>'
       . '<label>Card limit (0 = unlimited)<input type="number" min="0" name="max_cards" value="0"></label></div>'
       . '<h3>First admin (optional)</h3><div class="cols"><label>Name<input name="admin_name"></label><label>Email (login)<input type="email" name="admin_email"></label></div>'
       . '<label class="check"><input type="checkbox" name="send"' . (cfg('mail_from') ? ' checked' : ' disabled') . '> Email them the invite' . (cfg('mail_from') ? '' : ' (set mail_from in config.php — or copy the link shown after creating)') . '</label>'
       . '<p><button>Create workspace</button></p></form>';
    page_foot(); break;

case 'settings':
    // What is switched on, and what each missing piece needs. Values live in config.php only.
    require_owner();
    $a = cfg('apple_wallet', []); $g = cfg('google_wallet', []);
    $rows = [
        ['Card links', cfg('base_url') ? 'on' : 'off', cfg('base_url') ? h(base_url()) : 'base_url is not set — QR codes use the current host name. Set it before printing.'],
        ['Email (invites, new-contact alerts)', cfg('mail_from') ? 'on' : 'off', cfg('mail_from') ? 'From ' . h(cfg('mail_from')) : 'Set mail_from to an address on this domain.'],
        ['AI business-card scanner', cfg('anthropic_api_key') ? 'on' : 'off', cfg('anthropic_api_key') ? 'Model ' . h(cfg('scan_model', 'claude-opus-5-5')) : 'Set anthropic_api_key (console.anthropic.com → API keys).'],
        ['CRM webhook (Zapier / Make → HubSpot, etc.)', cfg('webhook_url') ? 'on' : 'off', cfg('webhook_url') ? 'Every new contact is POSTed to ' . h(parse_url((string)cfg('webhook_url'), PHP_URL_HOST)) . (cfg('webhook_secret') ? ', signed' : ' — <b>unsigned</b>: set webhook_secret') : 'Set webhook_url (https) and webhook_secret. Payload fields are listed in README.md.'],
        ['Apple Wallet', !empty($a['pass_type_id']) && !empty($a['wwdr_pem']) ? 'on' : 'off', 'See WALLET.md.'],
        ['Google Wallet', !empty($g['issuer_id']) && !empty($g['service_account_json']) ? 'on' : 'off', 'See WALLET.md.'],
    ];
    page_head('Settings');
    echo '<h1>Settings</h1><p class="muted">These are set in <code>config.php</code> on the server, not here, so secrets never pass through the browser.</p><table class="tbl"><tr><th>Feature</th><th>Status</th><th></th></tr>';
    foreach ($rows as [$f, $st, $note]) echo '<tr><td>' . h($f) . '</td><td><span class="st st-' . ($st === 'on' ? 'won' : 'lost') . '">' . $st . '</span></td><td>' . $note . '</td></tr>';
    echo '</table>';
    if (cfg('webhook_url')) {
        if ($isPost) { $last = (int)db()->query('SELECT MAX(id) FROM leads WHERE suspect = 0')->fetchColumn(); if ($last) { fire_webhook($last); flash('Sent the latest contact to the webhook.'); } else flash('No contacts yet to send.'); redirect('index.php?p=settings'); }
        echo '<form method="post" class="form">' . csrf_field() . '<p>Test the webhook by re-sending the most recent contact.</p><button>Send test</button></form>';
    }
    page_foot(); break;

case 'account':
    $u = me() ?? redirect('index.php?p=login');
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
    if (!$l || (int)$l['brand_id'] !== ws_id() || (!is_admin() && (int)$l['user_id'] !== (int)me()['id'])) { http_response_code(404); exit('Not found'); }
    return $l;
}

function events_datalist(): string {
    $o = '<datalist id="events">';
    $q = db()->prepare("SELECT event FROM leads WHERE brand_id = ? AND event != '' GROUP BY event ORDER BY MAX(id) DESC LIMIT 50");
    $q->execute([ws_id()]);
    foreach ($q as $e) $o .= '<option value="' . h($e['event']) . '">';
    return $o . '</datalist>';
}

function lead_filters(): void {
    $g = fn($k) => h((string)($_GET[$k] ?? ''));
    echo '<form class="filters" method="get"><input type="hidden" name="p" value="leads"><input name="q" placeholder="Search name, email, company…" value="' . $g('q') . '">';
    if (is_admin()) {
        echo '<select name="owner"><option value="">Everyone</option>';
        foreach (ws_users() as $m) echo '<option value="' . $m['id'] . '"' . (($_GET['owner'] ?? '') == $m['id'] ? ' selected' : '') . '>' . h($m['name']) . '</option>';
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
    echo '<div class="scroll"><table class="tbl"><tr><th>When</th><th>Name</th><th>Email / phone</th><th>Company</th>' . (is_admin() ? '<th>Team member</th>' : '') . '<th>Event</th><th>Status</th>' . ($editable ? '<th></th>' : '') . '</tr>';
    foreach ($rows as $l) {
        echo '<tr><td class="nowrap">' . h(substr($l['created_at'], 0, 16)) . '<br><span class="muted">' . h(SOURCE_LABELS[$l['source']] ?? $l['source']) . ($l['consent'] ? ' · ✓ consent' : '') . '</span></td>'
           . '<td><b>' . h($l['name']) . '</b>' . ($l['job_title'] ? '<br><span class="muted">' . h($l['job_title']) . '</span>' : '') . '</td>'
           . '<td>' . ($l['email'] ? '<a href="mailto:' . h($l['email']) . '">' . h($l['email']) . '</a>' : '') . ($l['phone'] ? '<br><a href="tel:' . h($l['phone']) . '">' . h($l['phone']) . '</a>' : '') . '</td>'
           . '<td>' . h($l['company']) . '</td>' . (is_admin() ? '<td>' . h($l['owner'] ?? '—') . '</td>' : '')
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
