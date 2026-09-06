// Render app icons from SVG and screenshot the built site through the real scroll timeline.
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const OUT = process.argv[2] || 'shots'; fs.mkdirSync(OUT, { recursive: true });
const srv = spawn('http-server', ['public', '-p', '8787', '-s', '-c-1']); await new Promise(r => setTimeout(r, 1200));
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium/chrome-linux/chrome' }).catch(() => chromium.launch());
try {
  // icons
  const ic = await browser.newPage({ viewport: { width: 512, height: 512 } });
  for (const [src, name] of [['icon.svg', 'icon-512.png'], ['icon-maskable.svg', 'icon-512-maskable.png']]) {
    await ic.setContent(`<body style="margin:0"><img src="data:image/svg+xml;utf8,${encodeURIComponent(fs.readFileSync('static/img/' + src, 'utf8'))}" width="512" height="512"></body>`);
    await ic.screenshot({ path: 'static/img/' + name, clip: { x: 0, y: 0, width: 512, height: 512 } });
  }
  await ic.setViewportSize({ width: 192, height: 192 });
  await ic.setContent(`<body style="margin:0"><img src="data:image/svg+xml;utf8,${encodeURIComponent(fs.readFileSync('static/img/icon.svg', 'utf8'))}" width="192" height="192"></body>`);
  await ic.screenshot({ path: 'static/img/icon-192.png' });
  for (const f of ['icon-512.png', 'icon-512-maskable.png', 'icon-192.png']) fs.copyFileSync('static/img/' + f, 'public/img/' + f);
  await ic.close();

  const errors = [];
  const shoot = async (vp, tag, url, stops) => {
    const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 1 });
    page.on('pageerror', e => errors.push(`${tag} ${url}: ${e.message}`));
    page.on('console', m => m.type() === 'error' && !/fonts.g|cdnjs|ERR_|net::/.test(m.text()) && errors.push(`${tag} ${url}: ${m.text()}`));
    await page.goto('http://127.0.0.1:8787' + url, { waitUntil: 'networkidle', timeout: 30000 }).catch(e => errors.push('goto ' + url + ' ' + e.message));
    await page.waitForTimeout(800);
    for (const [label, frac] of stops) {
      await page.evaluate(f => window.scrollTo(0, Math.round(innerHeight * f)), frac);
      await page.waitForTimeout(900);
      await page.screenshot({ path: `${OUT}/${tag}-${label}.png` });
    }
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    await page.close(); return h;
  };
  const stops = [['0-galataport', 0], ['1-push', 0.9], ['2-hull', 1.9], ['3-balcony', 2.6], ['4-door', 3.05], ['5-cabin', 4.4], ['6-below', 6.2], ['7-ports', 7.5], ['8-ships', 9.2]];
  const h = await shoot({ width: 1440, height: 900 }, 'desk', '/', stops);
  await shoot({ width: 390, height: 844 }, 'mob', '/', [['0', 0], ['5-cabin', 4.4], ['7', 7.2], ['9', 10]]);
  await shoot({ width: 1440, height: 900 }, 'port', '/ports/kusadasi/', [['top', 0], ['body', 0.9]]);
  await shoot({ width: 1440, height: 900 }, 'list', '/ports/', [['top', 0]]);
  await shoot({ width: 1440, height: 900 }, 'visa', '/visa/', [['top', 0]]);
  await shoot({ width: 1440, height: 900 }, 'offers', '/offers/', [['top', 0]]);
  await shoot({ width: 390, height: 844 }, 'mport', '/ports/istanbul-galataport/', [['top', 0], ['facts', 1.4]]);
  // full page of home below the hero for a layout sanity pass
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto('http://127.0.0.1:8787/', { waitUntil: 'networkidle' }); await p.evaluate(() => window.scrollTo(0, innerHeight * 5)); await p.waitForTimeout(600);
  await p.evaluate(() => { document.getElementById('hero').style.display = 'none'; document.querySelectorAll('.reveal').forEach(e => e.classList.add('is-in')); });
  await p.screenshot({ path: `${OUT}/desk-fullpage.png`, fullPage: true });
  await p.close();
  const manifest = await (await browser.newPage()).goto('http://127.0.0.1:8787/manifest.webmanifest');
  // PWA: register SW, save a port guide, go offline, reload it; an unsaved page must show the offline fallback.
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 800 } }); const pw = await ctx.newPage();
  await pw.goto('http://127.0.0.1:8787/ports/kusadasi/', { waitUntil: 'networkidle' }); await pw.waitForTimeout(1500);
  await pw.click('[data-save-offline]'); await pw.waitForTimeout(800);
  const saveTxt = await pw.textContent('[data-save-offline]');
  srv.kill(); await new Promise(r => setTimeout(r, 800)); // real offline: the origin is gone
  const r1 = await pw.goto('http://127.0.0.1:8787/ports/kusadasi/').catch(e => null); const t1 = r1 ? await pw.title() : 'FAILED';
  const r2 = await pw.goto('http://127.0.0.1:8787/gatherings/nowruz-1406/').catch(e => null); const t2 = r2 ? await pw.title() : 'FAILED';
  await pw.screenshot({ path: `${OUT}/offline-fallback.png` });
  console.log('PWA save:', saveTxt.trim(), '| offline saved page:', t1, '| offline unsaved page:', t2);
  await ctx.close();
  console.log('home scrollHeight', h, '· manifest', manifest.status(), '· errors', errors.length); errors.forEach(e => console.log('ERR', e));
} finally { await browser.close(); srv.kill(); }
