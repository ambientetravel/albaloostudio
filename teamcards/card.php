<?php
/*
 * Public card page — what the QR opens. /u/<slug> (rewrite) or card.php?u=<slug>.
 *
 * Shows the person, one-tap call / WhatsApp / email / save-contact, and the
 * "share your details back" form. A submitted form becomes a contact owned by
 * the card's person and brand. Honeypot hits are stored flagged as spam, not
 * dropped, so an admin can review them; the visitor sees the same thank-you.
 */

declare(strict_types=1);
require __DIR__ . '/lib.php';

$slug = (string)($_GET['u'] ?? '');
$c = $slug !== '' ? card_by_slug($slug) : null;
if (!$c || !$c['active']) {
    http_response_code(404);
    echo '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Card not found</title><p style="font:16px system-ui;padding:2em">This card is not available.</p>';
    exit;
}

$B = base_url();
$sent = false; $err = '';

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    start_session();
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

if (!$sent && ($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') db()->prepare('UPDATE cards SET views = views + 1 WHERE id = ?')->execute([$c['id']]);

function notify_owner(array $c): void {
    $from = (string)cfg('mail_from', '');
    if ($from === '') return;
    $q = db()->prepare('SELECT email, notify FROM users WHERE id = ?'); $q->execute([$c['user_id']]); $u = $q->fetch();
    if (!$u || !$u['notify']) return;
    $lines = ["New contact via your {$c['brand_name']} card", '', 'Name: ' . post('name'), 'Email: ' . post('email'), 'Phone: ' . post('phone'),
              'Company: ' . post('company'), 'Title: ' . post('job_title'), 'Message: ' . post('note', 2000), '', base_url() . '/index.php?p=leads'];
    $subject = '=?UTF-8?B?' . base64_encode('New contact: ' . post('name')) . '?=';
    @mail($u['email'], $subject, implode("\n", $lines), "From: TeamCards <$from>\r\nContent-Type: text/plain; charset=UTF-8\r\n" . (post('email') ? 'Reply-To: ' . post('email') . "\r\n" : ''));
}

$wa = preg_replace('/\D+/', '', $c['whatsapp']);
$ig = ltrim($c['instagram'], '@');
$initials = implode('', array_map(fn($w) => mb_substr($w, 0, 1), array_slice(preg_split('/\s+/', $c['full_name']) ?: [], 0, 2)));
start_session();
?><!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= h($c['full_name']) ?> · <?= h($c['brand_name']) ?></title>
<meta name="robots" content="noindex">
<meta property="og:title" content="<?= h($c['full_name'] . ' · ' . $c['brand_name']) ?>">
<meta property="og:description" content="<?= h($c['title']) ?>">
<?php if ($c['photo']): ?><meta property="og:image" content="<?= h(photo_url($c['photo'])) ?>"><?php endif ?>
<meta name="theme-color" content="<?= h($c['color']) ?>">
<link rel="stylesheet" href="<?= h($B) ?>/assets/app.css?v=<?= TC_VERSION ?>">
</head>
<body class="public" style="--brand:<?= h($c['color']) ?>;--accent:<?= h($c['accent']) ?>">
<div class="pcard">
  <header>
    <?php if ($c['logo']): ?><img class="brandlogo" src="<?= h(photo_url($c['logo'])) ?>" alt="<?= h($c['brand_name']) ?>"><?php else: ?><span class="brandname"><?= h($c['brand_name']) ?></span><?php endif ?>
    <?php if ($c['photo']): ?><img class="face" src="<?= h(photo_url($c['photo'])) ?>" alt=""><?php else: ?><span class="face init"><?= h($initials) ?></span><?php endif ?>
    <h1><?= h($c['full_name']) ?></h1>
    <?php if ($c['title']): ?><p class="role"><?= h($c['title']) ?></p><?php endif ?>
    <?php if ($c['tagline']): ?><p class="tag"><?= h($c['tagline']) ?></p><?php endif ?>
  </header>

  <a class="save" href="<?= h($B) ?>/vcf.php?u=<?= h(rawurlencode($c['slug'])) ?>">Save contact</a>

  <nav class="links">
    <?php if ($c['phone']): ?><a href="tel:<?= h($c['phone']) ?>"><span>Call</span><?= h($c['phone']) ?></a><?php endif ?>
    <?php if ($wa): ?><a href="https://wa.me/<?= h($wa) ?>"><span>WhatsApp</span>+<?= h($wa) ?></a><?php endif ?>
    <?php if ($c['email']): ?><a href="mailto:<?= h($c['email']) ?>"><span>Email</span><?= h($c['email']) ?></a><?php endif ?>
    <?php if ($c['website']): ?><a href="<?= h($c['website']) ?>" rel="noopener"><span>Website</span><?= h(preg_replace('~^https?://(www\.)?~', '', rtrim($c['website'], '/'))) ?></a><?php elseif ($c['brand_domain']): ?><a href="https://<?= h($c['brand_domain']) ?>" rel="noopener"><span>Website</span><?= h($c['brand_domain']) ?></a><?php endif ?>
    <?php if ($c['linkedin']): ?><a href="<?= h($c['linkedin']) ?>" rel="noopener"><span>LinkedIn</span>Profile</a><?php endif ?>
    <?php if ($ig): ?><a href="https://instagram.com/<?= h(rawurlencode($ig)) ?>" rel="noopener"><span>Instagram</span>@<?= h($ig) ?></a><?php endif ?>
    <?php if ($c['address']): ?><a href="https://maps.google.com/?q=<?= h(rawurlencode($c['address'])) ?>" rel="noopener"><span>Office</span><?= h($c['address']) ?></a><?php endif ?>
  </nav>

  <?php if ($c['bio']): ?><p class="bio"><?= nl2br(h($c['bio'])) ?></p><?php endif ?>

  <section class="exchange" id="share">
  <?php if ($sent): ?>
    <h2>Thank you, <?= h(explode(' ', post('name'))[0]) ?>!</h2>
    <p><?= h(explode(' ', $c['full_name'])[0]) ?> has your details and will be in touch.</p>
    <a class="save" href="<?= h($B) ?>/vcf.php?u=<?= h(rawurlencode($c['slug'])) ?>">Save <?= h(explode(' ', $c['full_name'])[0]) ?>’s contact</a>
  <?php else: ?>
    <h2>Share your details with <?= h(explode(' ', $c['full_name'])[0]) ?></h2>
    <?php if ($err): ?><p class="err"><?= h($err) ?></p><?php endif ?>
    <form method="post" action="#share">
      <input type="hidden" name="csrf" value="<?= h(csrf()) ?>">
      <input name="name" placeholder="Your name *" autocomplete="name" required value="<?= h(post('name')) ?>">
      <input name="email" type="email" placeholder="Email" autocomplete="email" value="<?= h(post('email')) ?>">
      <input name="phone" type="tel" placeholder="Phone / WhatsApp" autocomplete="tel" value="<?= h(post('phone')) ?>">
      <input name="company" placeholder="Company" autocomplete="organization" value="<?= h(post('company')) ?>">
      <input name="job_title" placeholder="Job title" autocomplete="organization-title" value="<?= h(post('job_title')) ?>">
      <textarea name="note" rows="2" placeholder="What are you interested in?"><?= h(post('note', 2000)) ?></textarea>
      <input class="hp" name="company_url" tabindex="-1" autocomplete="off" aria-hidden="true">
      <label class="check"><input type="checkbox" name="consent" value="1"> I agree to be contacted by <?= h($c['brand_name']) ?> about my enquiry.</label>
      <button>Send my details</button>
    </form>
  <?php endif ?>
  </section>
</div>
</body></html>
