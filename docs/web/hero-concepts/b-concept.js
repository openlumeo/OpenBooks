/* Concept B, "The Monolith". Theme toggle, plus one scroll-scrubbed timeline (GSAP ScrollTrigger).
   With no JS, or with reduced motion, the static CSS is the finished composition. */
(function () {
  var root = document.documentElement;
  var KEY = 'b-theme';
  var toggle = document.querySelector('.theme-toggle');

  function isLight() { return root.getAttribute('data-theme') === 'light'; }

  function syncToggle() {
    var light = isLight();
    toggle.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
    toggle.setAttribute('aria-pressed', String(light));
  }

  toggle.addEventListener('click', function () {
    var next = isLight() ? 'dark' : 'light';
    if (next === 'light') root.setAttribute('data-theme', 'light');
    else root.removeAttribute('data-theme');
    try { localStorage.setItem(KEY, next); } catch (e) {}
    syncToggle();
  });
  syncToggle();

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !window.gsap || !window.ScrollTrigger) return;

  gsap.registerPlugin(ScrollTrigger);

  var hero = document.querySelector('.hero');
  var rise = document.querySelector('.rise');
  var front = document.querySelector('.plane-front');
  var back = document.querySelector('.plane-back');
  var lead = document.querySelector('.lead');
  var stampIn = document.querySelector('.stamp-in');
  var ties = Array.prototype.slice.call(document.querySelectorAll('.lrow .tie'));
  var tl = null;

  // Rest pose must equal the CSS rest pose.
  gsap.set(front, { rotationX: 18, transformOrigin: '50% 100%' });
  gsap.set(back, { z: -200, rotationX: 18, transformOrigin: '50% 100%' });

  function build() {
    if (tl) {
      tl.scrollTrigger && tl.scrollTrigger.kill(true);
      tl.kill();
      tl = null;
    }

    // Reset to the rest pose before measuring, so a rebuild never starts from a scrubbed state.
    gsap.set(front, { clearProps: 'transform' });
    gsap.set(back, { clearProps: 'transform' });
    gsap.set(lead, { clearProps: 'transform' });
    gsap.set(stampIn, { clearProps: 'transform' });
    gsap.set(ties, { clearProps: 'transform' });
    gsap.set(front, { rotationX: 18, transformOrigin: '50% 100%' });
    gsap.set(back, { z: -200, rotationX: 18, transformOrigin: '50% 100%' });

    var vh = hero.clientHeight;
    var H = front.offsetHeight;
    var restTop = rise.offsetTop;                    // layout position, ignores the entrance transform
    var targetTop = Math.round((vh - H) / 2);        // monument centred when flat
    var ty = targetTop - restTop;                    // negative: rises to centre
    var ly = -(lead.offsetTop + lead.offsetHeight + 48); // lead leaves the top of the viewport

    // All tweens default to ease none: this is a straight scrub.
    tl = gsap.timeline({
      defaults: { ease: 'none' },
      scrollTrigger: {
        trigger: hero,
        start: 'top top',
        end: '+=120%',
        pin: true,
        scrub: true,
        invalidateOnRefresh: true
      }
    });

    // 1. Monument tilts flat and rises to centre.
    tl.to(front, { rotationX: 0, y: ty, duration: 0.7 }, 0);
    // 2. Back plane of ledger lines moves slower: shallow parallax.
    tl.to(back, { y: ty * 0.4, duration: 1 }, 0);
    // 3. Headline, lede and CTAs clear the way.
    tl.to(lead, { y: ly, duration: 0.5 }, 0);
    // 4. Ties verify one by one: each bar retracts and re-draws in turn; the end state is all tied.
    ties.forEach(function (bar, i) {
      var s = 0.3 + i * 0.11;
      tl.to(bar, { scaleY: 0, duration: 0.05 }, s);
      tl.to(bar, { scaleY: 1, duration: 0.05 }, s + 0.05);
    });
    // 5. End of hero scroll: the RELEASED stamp lands (a single press).
    tl.to(stampIn, { scale: 0.94, duration: 0.04 }, 0.9);
    tl.to(stampIn, { scale: 1, duration: 0.06 }, 0.94);

    ScrollTrigger.refresh();
  }

  var resizeTimer = null;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(build, 150);
  });

  build();
  window.addEventListener('load', build);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(build);
})();
