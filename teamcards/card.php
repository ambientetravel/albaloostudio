<?php
/*
 * Public card page — what the QR opens. /u/<slug> (rewrite) or card.php?u=<slug>.
 *
 * Renders the card in its design (template), its link blocks in order, the
 * "Exchange contacts" sheet (optionally opening by itself on load) and a Share
 * sheet with the QR. A submitted form becomes a contact owned by the card's
 * person and brand. Honeypot hits are stored flagged as spam, not dropped, so
 * an admin can review them; the visitor sees the same thank-you.
 */

declare(strict_types=1);
require __DIR__ . '/lib.php';

$slug = (string)($_GET['u'] ?? '');
$c = $slug !== '' ? card_by_slug($slug) : null;
if (!$c || !$c['active'] || $c['brand_status'] !== 'active') {
    http_response_code(404);
    echo '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Card not found</title><p style="font:16px system-ui;padding:2em">This card is not available.</p>';
    exit;
}

$B = base_url();
$url = card_url($c['slug']);
$sent = false; $err = '';
start_session();

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    if (!hash_equals($_SESSION['csrf'] ?? '', (string)($_POST['csrf'] ?? ''))) $err = 'The form expired — please try again.';
    elseif (post('name') === '') $err = 'Please enter your name.';
    elseif (post('email') === '' && post('phone') === '') $err = 'Please leave an email or a phone number.';
    elseif (post('email') !== '' && !filter_var(post('email'), FILTER_VALIDATE_EMAIL)) $err = 'That email address looks wrong.';
    else {
        $q = db()->prepare("SELECT COUNT(*) FROM leads WHERE ip_hash = ? AND created_at >= datetime('now','-1 hour')");
        $q->execute([ip_hash()]);
        if ((int)$q->fetchColumn() >= 8) $err = 'Too many submissions from this network — please try again later.';
        else {
            $suspect = post('company_url') !== '' ? 1 : 0;   // honeypot field, hidden from people
            insert_lead(['card_id' => $c['id'], 'user_id' => $c['user_id'], 'brand_id' => $c['brand_id'], 'source' => 'qr',
                         'consent' => isset($_POST['consent']) ? 1 : 0, 'suspect' => $suspect, 'event' => '']);
            if (!$suspect) notify_owner($c);
            $sent = true;
        }
    }
}

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') db()->prepare('UPDATE cards SET views = views + 1 WHERE id = ?')->execute([$c['id']]);

function notify_owner(array $c): void {
    $q = db()->prepare('SELECT email, notify FROM users WHERE id = ?'); $q->execute([$c['user_id']]); $u = $q->fetch();
    if (!$u || !$u['notify']) return;
    $lines = ["New contact via your {$c['brand_name']} card", '', 'Name: ' . post('name'), 'Email: ' . post('email'), 'Phone: ' . post('phone'),
              'Company: ' . post('company'), 'Title: ' . post('job_title'), 'Message: ' . post('note', 2000), '', base_url() . '/index.php?p=leads'];
    send_mail($u['email'], 'New contact: ' . post('name'), implode("\n", $lines), post('email'));
}

$blocks = array_values(array_filter(card_blocks($c), fn($b) => !empty($b['show'])));
$exchange = current(array_filter($blocks, fn($b) => $b['type'] === 'exchange')) ?: null;
$first = explode(' ', $c['full_name'])[0];
$initials = implode('', array_map(fn($w) => mb_substr($w, 0, 1), array_slice(preg_split('/\s+/', $c['full_name']) ?: [], 0, 2)));
$sheetOpen = $sent || $err !== '' || ($exchange && !empty($exchange['auto_open']) && empty($_GET['noform']));
$host = preg_replace('~^https?://(www\.)?~', '', rtrim($c['co_website'], '/'));
?><!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= h($c['full_name']) ?> · <?= h($c['co_name']) ?></title>
<meta name="robots" content="noindex">
<meta property="og:title" content="<?= h($c['full_name'] . ' · ' . $c['co_name']) ?>">
<meta property="og:description" content="<?= h($c['title']) ?>">
<?php if ($c['photo']): ?><meta property="og:image" content="<?= h(photo_url($c['photo'])) ?>"><?php endif ?>
<meta name="theme-color" content="<?= h($c['color']) ?>">
<link rel="stylesheet" href="<?= h($B) ?>/assets/app.css?v=<?= TC_VERSION ?>">
</head>
<body class="public t-<?= h($c['tpl']) ?>" style="--brand:<?= h($c['color']) ?>;--accent:<?= h($c['accent']) ?>">
<div class="pcard">
  <button class="sharebtn" type="button" data-open="share">Share</button>
  <header<?php if ($c['tpl'] === 'photo' && $c['photo']): ?> style="background-image:linear-gradient(180deg,#0000 35%,#000b),url('<?= h(photo_url($c['photo'])) ?>')"<?php endif ?>>
    <?php if ($c['logo']): ?><img class="brandlogo" src="<?= h(photo_url($c['logo'])) ?>" alt="<?= h($c['brand_name']) ?>"><?php else: ?><span class="brandname"><?= h($c['brand_name']) ?></span><?php endif ?>
    <?php if ($c['tpl'] !== 'photo' || !$c['photo']): ?>
      <?php if ($c['photo']): ?><img class="face" src="<?= h(photo_url($c['photo'])) ?>" alt=""><?php else: ?><span class="face init"><?= h($initials) ?></span><?php endif ?>
    <?php endif ?>
    <h1><?= h($c['full_name']) ?></h1>
    <?php if ($c['title']): ?><p class="role"><?= h($c['title']) ?></p><?php endif ?>
    <?php if ($c['tagline']): ?><p class="tag"><?= h($c['tagline']) ?></p><?php endif ?>
  </header>

  <?php if ($c['tpl'] === 'minimal'): ?>
  <div class="contactline">
    <?php if ($c['phone']): ?><a href="tel:<?= h(preg_replace('/[^\d+]/', '', $c['phone'])) ?>"><?= h($c['phone']) ?></a><?php endif ?>
    <?php if ($c['email']): ?><a href="mailto:<?= h($c['email']) ?>"><?= h($c['email']) ?></a><?php endif ?>
  </div>
  <?php endif ?>

  <nav class="blocks">
  <?php foreach ($blocks as $b):
      if ($b['type'] === 'exchange'): ?>
        <button type="button" class="blk primary" data-open="xsheet"><?= h($b['label']) ?></button>
      <?php elseif ($b['type'] === 'text'): ?>
        <div class="blk-text s-<?= h($b['style']) ?>"><?= nl2br(h($b['value'])) ?></div>
      <?php elseif ($b['type'] === 'socials'):
        $links = array_filter(array_map(fn($net, $val) => ($href = social_url($net, (string)$val)) ? [$net, $href] : null, array_keys($b['socials']), $b['socials']));
        if ($links): ?>
        <div class="socials"><?php foreach ($links as [$net, $href]): ?><a href="<?= h($href) ?>" rel="noopener" target="_blank"><?= h(SOCIALS[$net][0]) ?></a><?php endforeach ?></div>
        <?php endif ?>
      <?php else: $href = block_href($b, $c); if ($href): ?>
        <a class="blk<?= $b['type'] === 'save' ? ' accent' : '' ?>" href="<?= h($href) ?>"<?= in_array($b['type'], ['link', 'book', 'pay', 'navigate', 'whatsapp'], true) ? ' rel="noopener" target="_blank"' : '' ?>><?= h($b['label']) ?></a>
      <?php endif; endif;
  endforeach ?>
  </nav>

  <?php if ($c['bio']): ?><p class="bio"><?= nl2br(h($c['bio'])) ?></p><?php endif ?>

  <footer class="company">
    <div><b><?= h($c['co_name']) ?></b>
      <?php if ($c['co_website']): ?><a href="<?= h($c['co_website']) ?>" rel="noopener"><?= h($host) ?></a><?php endif ?>
      <?php if ($c['co_address']): ?><span><?= h($c['co_address']) ?></span><?php endif ?>
      <?php if ($c['co_phone'] && $c['co_phone'] !== $c['phone']): ?><a href="tel:<?= h(preg_replace('/[^\d+]/', '', $c['co_phone'])) ?>"><?= h($c['co_phone']) ?></a><?php endif ?>
    </div>
    <?php if ($c['logo']): ?><img src="<?= h(photo_url($c['logo'])) ?>" alt=""><?php endif ?>
  </footer>
</div>

<?php if ($exchange): ?>
<dialog class="sheet" id="xsheet" data-autoopen="<?= $sheetOpen ? '1' : '0' ?>">
  <button class="x" type="button" data-close aria-label="Close">×</button>
  <?php if ($sent): ?>
    <h2>Thank you, <?= h(explode(' ', post('name'))[0]) ?>!</h2>
    <p><?= h($first) ?> has your details and will be in touch.</p>
    <a class="blk accent" href="<?= h($B) ?>/vcf.php?u=<?= h(rawurlencode($c['slug'])) ?>">Save <?= h($first) ?>’s contact</a>
  <?php else: ?>
    <h2>Let’s connect!</h2>
    <p class="muted">Share your contact information with <?= h($first) ?></p>
    <?php if ($err): ?><p class="err"><?= h($err) ?></p><?php endif ?>
    <form method="post" action="<?= h($url) ?>">
      <input type="hidden" name="csrf" value="<?= h(csrf()) ?>">
      <input name="name" placeholder="Your name *" autocomplete="name" required value="<?= h(post('name')) ?>">
      <input name="email" type="email" placeholder="Email" autocomplete="email" value="<?= h(post('email')) ?>">
      <div class="or">or</div>
      <input name="phone" type="tel" placeholder="Phone / WhatsApp" autocomplete="tel" value="<?= h(post('phone')) ?>">
      <details<?= post('company') || post('note') ? ' open' : '' ?>><summary>+ Add more information</summary>
        <input name="company" placeholder="Company" autocomplete="organization" value="<?= h(post('company')) ?>">
        <input name="job_title" placeholder="Job title" autocomplete="organization-title" value="<?= h(post('job_title')) ?>">
        <textarea name="note" rows="2" placeholder="What are you interested in?"><?= h(post('note', 2000)) ?></textarea>
      </details>
      <input class="hp" name="company_url" tabindex="-1" autocomplete="off" aria-hidden="true">
      <label class="check"><input type="checkbox" name="consent" value="1"> I agree to be contacted by <?= h($c['co_name']) ?> about my enquiry.</label>
      <button>Connect</button>
    </form>
  <?php endif ?>
</dialog>
<?php endif ?>

<dialog class="sheet" id="share">
  <button class="x" type="button" data-close aria-label="Close">×</button>
  <h2>Scan to connect with <?= h($first) ?></h2>
  <div class="qr" data-qr="<?= h($url) ?>"></div>
  <?php $msg = rawurlencode($c['full_name'] . ' · ' . $c['co_name'] . ' — ' . $url); ?>
  <div class="sharelinks">
    <button type="button" data-copy="<?= h($url) ?>">Copy link</button>
    <a href="https://wa.me/?text=<?= $msg ?>" target="_blank" rel="noopener">WhatsApp</a>
    <a href="sms:?&body=<?= $msg ?>">Text</a>
    <a href="mailto:?subject=<?= rawurlencode($c['full_name']) ?>&body=<?= $msg ?>">Email</a>
    <a href="https://t.me/share/url?url=<?= rawurlencode($url) ?>" target="_blank" rel="noopener">Telegram</a>
    <a href="https://www.linkedin.com/sharing/share-offsite/?url=<?= rawurlencode($url) ?>" target="_blank" rel="noopener">LinkedIn</a>
  </div>
</dialog>
<script src="<?= h($B) ?>/assets/qrcode.js"></script>
<script src="<?= h($B) ?>/assets/app.js?v=<?= TC_VERSION ?>"></script>
</body></html>
