(function () {
  var root = document.documentElement;
  root.classList.remove("no-js");

  var inst = document.querySelector(".instrument");
  var sw = document.getElementById("alter");
  var live = document.getElementById("live");
  var srBalance = document.querySelector("[data-sr-balance]");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setRefused(refused) {
    inst.setAttribute("data-state", refused ? "refused" : "released");
    sw.setAttribute("aria-checked", refused ? "true" : "false");
    srBalance.textContent = refused ? "436.47" : "436.46";
    live.textContent = refused
      ? "Refused. BALANCE_MISMATCH: running balance breaks at TXN 4."
      : "Released. Running balance ties on every row.";
  }
  sw.addEventListener("click", function () {
    setRefused(inst.getAttribute("data-state") !== "refused");
  });

  var theme = document.getElementById("theme");
  theme.addEventListener("click", function () {
    if (root.getAttribute("data-theme") === "light") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", "light");
  });

  function enter() {
    root.classList.remove("js-enter");
    if (reduce || !window.gsap) return;
    if (window.CustomEase) gsap.registerPlugin(CustomEase);
    var ob = window.CustomEase ? CustomEase.create("ob", "M0,0 C0.16,1,0.3,1,1,1") : "power3.out";

    var tl = gsap.timeline({ defaults: { ease: ob } });
    tl.from(".copy > *", { opacity: 0, y: 14, duration: 1.1, stagger: 0.09 }, 0.1)
      .from(".instrument", {
        y: 46, rotateX: 9, opacity: 0, duration: 1.5,
        transformPerspective: 1600, transformOrigin: "50% 100%"
      }, 0.2)
      .from(".rail li", { opacity: 0, duration: 0.6, stagger: 0.08 }, 0.75)
      .from(".row", { opacity: 0, duration: 0.6, stagger: 0.12 }, 0.85)
      .from(".row .bar", { scaleY: 0, transformOrigin: "50% 0%", duration: 0.7, stagger: 0.12 }, 0.85)
      .from(".foot", { opacity: 0, duration: 0.8 }, 1.5)
      .from(".verdict", { scale: 1.32, rotation: -6, opacity: 0, duration: 0.7, ease: "power4.out" }, 1.6);
  }

  if (window.gsap) enter();
  else root.classList.remove("js-enter");

  if (!reduce && window.matchMedia && window.matchMedia("(pointer: fine)").matches) {
    var hero = document.querySelector(".hero");
    var tilt = document.querySelector(".tilt");
    hero.addEventListener("pointermove", function (e) {
      var r = hero.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5;
      var y = (e.clientY - r.top) / r.height - 0.5;
      tilt.style.setProperty("--ry", (x * 2.2).toFixed(2) + "deg");
      tilt.style.setProperty("--rx", (-y * 2.2).toFixed(2) + "deg");
    });
    hero.addEventListener("pointerleave", function () {
      tilt.style.setProperty("--rx", "0deg");
      tilt.style.setProperty("--ry", "0deg");
    });
  }
})();
