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

  gsap.set(front, { rotationX: 18, transformOrigin: '50% 100%' });
  gsap.set(back, { z: -200, rotationX: 18, transformOrigin: '50% 100%' });

  function build() {
    if (tl) {
      tl.scrollTrigger && tl.scrollTrigger.kill(true);
      tl.kill();
      tl = null;
    }

    gsap.set(front, { clearProps: 'transform' });
    gsap.set(back, { clearProps: 'transform' });
    gsap.set(lead, { clearProps: 'transform' });
    gsap.set(stampIn, { clearProps: 'transform' });
    gsap.set(ties, { clearProps: 'transform' });
    gsap.set(front, { rotationX: 18, transformOrigin: '50% 100%' });
    gsap.set(back, { z: -200, rotationX: 18, transformOrigin: '50% 100%' });

    var vh = hero.clientHeight;
    var H = front.offsetHeight;
    var restTop = rise.offsetTop;
    var targetTop = Math.round((vh - H) / 2);
    var ty = targetTop - restTop;
    var ly = -(lead.offsetTop + lead.offsetHeight + 48);

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

    tl.to(front, { rotationX: 0, y: ty, duration: 0.7 }, 0);
    tl.to(back, { y: ty * 0.4, duration: 1 }, 0);
    tl.to(lead, { y: ly, duration: 0.5 }, 0);
    ties.forEach(function (bar, i) {
      var s = 0.3 + i * 0.11;
      tl.to(bar, { scaleY: 0, duration: 0.05 }, s);
      tl.to(bar, { scaleY: 1, duration: 0.05 }, s + 0.05);
    });
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
