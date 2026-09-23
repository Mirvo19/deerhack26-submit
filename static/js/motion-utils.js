(function () {
  document.documentElement.classList.add("js");

  var cut = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var tiny = window.matchMedia("(max-width: 640px)").matches;
  var m = window.Motion;

  function show(scope) {
    (scope || document).querySelectorAll("[data-reveal]").forEach(function (el) {
      el.style.opacity = "1";
      el.style.transform = "none";
    });
  }

  function reveal(scope) {
    var els = (scope || document).querySelectorAll("[data-reveal]");

    if (cut || !("IntersectionObserver" in window) || !m) {
      show(scope);
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        m.animate(e.target, { opacity: [0, 1], y: tiny ? [0, 0] : [14, 0] }, { duration: .35, easing: "ease-out" })
          .finished.catch(function () {})
          .finally(function () { e.target.style.opacity = "1"; });
      });
    }, { threshold: .12 });

    els.forEach(function (el) { io.observe(el); });
  }

  function enter() {
    if (cut || !m) return;

    var items = document.querySelectorAll("[data-entrance]");
    if (!items.length) return;

    m.animate(items, { opacity: [0, 1], y: tiny ? [0, 0] : [18, 0] }, { duration: .4, easing: "ease-out", delay: m.stagger(.07) });
  }

  function lift(scope) {
    if (cut || !m) return;

    (scope || document).querySelectorAll("[data-lift]").forEach(function (el) {
      el.addEventListener("mouseenter", function () {
        m.animate(el, { y: -3 }, { duration: .16 });
      });
      el.addEventListener("mouseleave", function () {
        m.animate(el, { y: 0 }, { duration: .2 });
      });
    });
  }

  function wave(svg) {
    if (cut || !m || !svg) return;

    var paths = svg.querySelectorAll("path");
    if (!paths.length) return;

    m.animate(paths, { opacity: [1, .35, 1] }, { duration: 1.4, easing: "ease-in-out", delay: m.stagger(.08), repeat: Infinity });
  }

  window.dh = { reveal: reveal, enter: enter, lift: lift, wave: wave, show: show };

  var mb = document.getElementById("mnavBtn");
  var mp = document.getElementById("mnavPanel");

  if (mb && mp) {
    function mclose(refocus) {
      mb.setAttribute("aria-expanded", "false");
      document.removeEventListener("keydown", mesc);

      if (!cut && m) {
        m.animate(mp, { opacity: [0, 0], y: [0, -8] }, { duration: .15, easing: "ease-in" })
          .finished.then(function () { mp.hidden = true; })
          .catch(function () { mp.hidden = true; });
      } else {
        mp.hidden = true;
      }

      if (refocus) {
        try { mb.focus(); } catch (e) {}
      }
    }

    function mesc(e) {
      if (e.key === "Escape") {
        mclose(true);
      }
    }

    if (!mp.dataset.wired) {
      mp.dataset.wired = "1";
      mp.addEventListener("keydown", function (e) {
        if (e.key !== "Tab") return;

        var links = mp.querySelectorAll("a");
        if (!links.length) return;

        var first = links[0];
        var last = links[links.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      });
    }

    mb.addEventListener("click", function () {
      if (mp.hidden) {
        mp.hidden = false;
        mb.setAttribute("aria-expanded", "true");
        document.addEventListener("keydown", mesc);

        if (!cut && m) {
          m.animate(mp, { opacity: [0, 1], y: [-8, 0] }, { duration: .2, easing: "ease-out" });
        }

        var first = mp.querySelector("a");
        if (first) {
          try { first.focus({ preventScroll: true }); }
          catch (e) { try { first.focus(); } catch (x) {} }
        }
      } else {
        mclose(false);
      }
    });

    Array.prototype.forEach.call(mp.querySelectorAll("a"), function (a) {
      a.addEventListener("click", function () { mclose(false); });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    m = window.Motion || null;
    enter();
    reveal();
    lift();
    document.querySelectorAll("[data-motif-wave]").forEach(wave);
  });
})();
