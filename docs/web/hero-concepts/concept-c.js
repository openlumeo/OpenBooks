/* Concept C, "The Equation". Progressive enhancement only: the static page is the
   fully resolved equation. With JS off, or with reduced motion, nothing below runs
   (except the theme toggle, which is optional). */
(function () {
  var root = document.documentElement;

  /* ---------- Theme toggle (optional, remembered per viewer) ---------- */
  var toggle = document.querySelector('.c-toggle');
  function paintToggle() {
    var light = root.getAttribute('data-theme') === 'light';
    toggle.setAttribute('aria-pressed', light ? 'true' : 'false');
    toggle.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
  }
  function setTheme(light) {
    if (light) root.setAttribute('data-theme', 'light');
    else root.removeAttribute('data-theme');
    try { localStorage.setItem('ob-theme', light ? 'light' : 'dark'); } catch (e) {}
    paintToggle();
  }
  paintToggle();
  toggle.addEventListener('click', function () {
    setTheme(root.getAttribute('data-theme') !== 'light');
  });

  /* ---------- Entrance ---------- */
  var reduced = false;
  try { reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
  var hasGsap = typeof window.gsap !== 'undefined';

  function reveal() { root.classList.remove('pre'); }

  if (!hasGsap || reduced) {
    reveal();
    return;
  }
  // Failsafe: never leave the page hidden if the timeline fails to build.
  var failsafe = setTimeout(reveal, 2500);

  var gsap = window.gsap;
  var K = 0.8; // global time scale: the whole entrance runs in about 5 seconds
  function t(x) { return x * K; }

  var nav = document.querySelector('.c-nav');
  var h1 = document.querySelector('.c-h1');
  var copy = document.querySelector('.c-copy');
  var eq = document.querySelector('.c-eq');
  var rule = document.querySelector('.eq-rule');
  var legend = document.querySelector('.legend');
  var stamp = document.querySelector('.stamp');
  var ops = Array.prototype.slice.call(document.querySelectorAll('.op'));

  var terms = {
    open:    { el: document.querySelector('.t-open'),  src: 'Statement · opening' },
    credits: { el: document.querySelector('.t-cr'),    src: 'Rows 1–8 · CR' },
    debits:  { el: document.querySelector('.t-dr'),    src: 'Rows 1–8 · DR' },
    closing: { el: document.querySelector('.t-close'), src: 'Statement · closing' }
  };

  // Build the chips and hide figures in their reserved slots (layout does not move).
  var chips = {};
  Object.keys(terms).forEach(function (k) {
    var term = terms[k].el;
    var fig = term.querySelector('.fig');
    var chip = document.createElement('span');
    chip.className = 'src';
    chip.setAttribute('aria-hidden', 'true');
    chip.textContent = terms[k].src;
    term.insertBefore(chip, fig);
    chips[k] = chip;
    gsap.set(fig, { visibility: 'hidden' });
  });
  gsap.set(stamp, { opacity: 0, rotation: 2, scale: 1.35 });
  gsap.set(rule, { scaleX: 0 });
  gsap.set(legend, { opacity: 0 });
  gsap.set(ops, { opacity: 0 });

  // Digit roll: each digit spins through random digits, then locks left to right.
  function digitCount(s) {
    var n = 0;
    for (var i = 0; i < s.length; i++) if (/\d/.test(s.charAt(i))) n++;
    return n;
  }
  function roll(fig, at, dur) {
    var final = fig.getAttribute('data-final');
    var n = digitCount(final);
    var st = { p: 0 };
    tl.to(st, {
      p: 1,
      duration: dur,
      ease: 'none',
      onUpdate: function () {
        var now = Math.floor(performance.now() / 42);
        var out = '';
        var r = 0;
        for (var i = 0; i < final.length; i++) {
          var ch = final.charAt(i);
          if (/\d/.test(ch)) {
            var lock = (r + 1) / n;
            if (st.p >= lock) out += ch;
            else out += String((now + i * 7 + r * 3) % 10);
            r++;
          } else {
            out += ch;
          }
        }
        fig.textContent = out;
      }
    }, at);
  }

  var tl = gsap.timeline({ paused: true, onComplete: function () { clearTimeout(failsafe); } });

  tl.fromTo(nav, { opacity: 0, y: -8 }, { opacity: 1, y: 0, duration: t(0.6), ease: 'power2.out' }, 0);
  tl.fromTo(h1, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: t(0.9), ease: 'expo.out' }, t(0.1));

  // One term: chip appears, gives way to the figure, which rolls its digits.
  function term(k, at) {
    var chip = chips[k];
    var fig = terms[k].el.querySelector('.fig');
    tl.fromTo(chip, { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: t(0.22), ease: 'power2.out' }, at);
    tl.to(chip, { opacity: 0, duration: t(0.16), ease: 'power1.in' }, at + t(0.5));
    tl.set(fig, { visibility: 'visible' }, at + t(0.62));
    roll(fig, at + t(0.62), t(0.6));
  }

  term('open', t(0.5));
  tl.fromTo(ops[0], { opacity: 0 }, { opacity: 1, duration: t(0.2) }, t(1.7));
  term('credits', t(1.8));
  tl.fromTo(ops[1], { opacity: 0 }, { opacity: 1, duration: t(0.2) }, t(3.0));
  term('debits', t(3.1));
  tl.fromTo(ops[2], { opacity: 0 }, { opacity: 1, duration: t(0.2) }, t(4.2));
  // The equals line draws itself, then the closing figure resolves last.
  tl.fromTo(rule, { scaleX: 0 }, { scaleX: 1, duration: t(0.7), ease: 'expo.out' }, t(4.3));
  term('closing', t(4.75));
  tl.fromTo(stamp, { opacity: 0, scale: 1.35 }, { opacity: 1, scale: 1, duration: t(0.42), ease: 'back.out(1.8)' }, t(6.1));
  tl.fromTo(legend, { opacity: 0 }, { opacity: 1, duration: t(0.5), ease: 'power1.out' }, t(4.6));
  tl.fromTo(copy, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: t(0.7), ease: 'power2.out' }, t(6.2));

  reveal();
  tl.play(0);

  // Frozen frames for review: add #t=2.4 to the URL to pause the entrance at that second.
  var m = /#t=([\d.]+)/.exec(window.location.hash);
  if (m) {
    tl.pause().seek(parseFloat(m[1]), false); // seek with callbacks so the digit roll renders
    clearTimeout(failsafe);
  }
})();
