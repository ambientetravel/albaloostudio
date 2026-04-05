// ===== Hero Canvas — Flowing particle field =====
(function() {
  const canvas = document.getElementById('heroCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w, h, particles, mouseX = 0, mouseY = 0;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }

  function createParticles() {
    particles = [];
    const count = Math.floor((w * h) / 8000);
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 2 + 0.5,
        opacity: Math.random() * 0.4 + 0.1,
        hue: Math.random() > 0.5 ? 32 : 270, // gold or purple
      });
    }
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);

    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      for (let j = i + 1; j < particles.length; j++) {
        const q = particles[j];
        const dx = p.x - q.x;
        const dy = p.y - q.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.strokeStyle = `hsla(${p.hue}, 60%, 60%, ${(1 - dist / 120) * 0.06})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
          ctx.stroke();
        }
      }
    }

    // Draw & update particles
    particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;

      // Wrap around
      if (p.x < 0) p.x = w;
      if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h;
      if (p.y > h) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${p.hue}, 60%, 65%, ${p.opacity})`;
      ctx.fill();
    });

    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', () => { resize(); createParticles(); });
  resize();
  createParticles();
  draw();

  // Waveform animation
  const wavePath1 = document.getElementById('wavePath1');
  const wavePath2 = document.getElementById('wavePath2');
  let waveFrame = 0;

  function animateWave() {
    waveFrame += 0.02;
    let d1 = 'M0 60';
    let d2 = 'M0 60';
    for (let x = 0; x <= 1200; x += 10) {
      const y1 = 60 + Math.sin(x * 0.008 + waveFrame) * 25 + Math.sin(x * 0.015 + waveFrame * 1.5) * 15;
      const y2 = 60 + Math.cos(x * 0.006 + waveFrame * 0.8) * 20 + Math.sin(x * 0.012 + waveFrame * 2) * 10;
      d1 += ` L${x} ${y1}`;
      d2 += ` L${x} ${y2}`;
    }
    if (wavePath1) wavePath1.setAttribute('d', d1);
    if (wavePath2) wavePath2.setAttribute('d', d2);
    requestAnimationFrame(animateWave);
  }
  animateWave();
})();

// ===== Showcase card interaction =====
document.querySelectorAll('.showcase-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.showcase-card').forEach(c => c.classList.remove('active'));
    card.classList.add('active');
    const artist = card.dataset.artist;
    const section = document.getElementById(artist);
    if (section) section.scrollIntoView({ behavior: 'smooth' });
  });
});

// ===== Navbar scroll effect =====
const navbar = document.getElementById('navbar');

window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 50);
});

// ===== Mobile nav toggle =====
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');

navToggle.addEventListener('click', () => {
  navLinks.classList.toggle('open');
  const spans = navToggle.querySelectorAll('span');
  if (navLinks.classList.contains('open')) {
    spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
    spans[1].style.opacity = '0';
    spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
  } else {
    spans[0].style.transform = '';
    spans[1].style.opacity = '';
    spans[2].style.transform = '';
  }
});

navLinks.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    navLinks.classList.remove('open');
    const spans = navToggle.querySelectorAll('span');
    spans[0].style.transform = '';
    spans[1].style.opacity = '';
    spans[2].style.transform = '';
  });
});

// ===== Smooth scroll =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  });
});

// ===== Artist pill click navigation =====
document.querySelectorAll('.artist-pill').forEach(pill => {
  pill.addEventListener('click', () => {
    const artist = pill.dataset.artist;
    const section = document.getElementById(artist);
    if (section) section.scrollIntoView({ behavior: 'smooth' });
  });
});

// ===== Scroll reveal =====
const revealElements = document.querySelectorAll(
  '.section-header, .about-grid, .wwd-card, .artist-grid, .podcast-featured, .episode-card, .release-card, .contact-grid, .footer-grid, .artist-etymology, .sound-signature, .mythology-map, .artist-album-preview, .bpm-range'
);

revealElements.forEach(el => el.classList.add('reveal'));

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  },
  { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
);

revealElements.forEach(el => observer.observe(el));

// ===== Contact form =====
const contactForm = document.getElementById('contactForm');

contactForm.addEventListener('submit', (e) => {
  const btn = contactForm.querySelector('button[type="submit"]');
  btn.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
      <polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
    Sending...
  `;
  btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
  // Form will submit via FormSubmit.co — no preventDefault
});

// ===== Active nav on scroll =====
const sections = document.querySelectorAll('section[id]');

window.addEventListener('scroll', () => {
  const scrollY = window.scrollY + 100;
  sections.forEach(section => {
    const top = section.offsetTop;
    const height = section.offsetHeight;
    const id = section.getAttribute('id');
    const link = document.querySelector(`.nav-links a[href="#${id}"]`);
    if (link) {
      if (scrollY >= top && scrollY < top + height) {
        link.style.color = 'var(--text-bright)';
      } else {
        link.style.color = '';
      }
    }
  });
});
