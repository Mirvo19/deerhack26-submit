(function () {
  document.addEventListener("click", function (e) {
    var copyBtn = e.target.closest("[data-copy]");

    if (copyBtn) {
      (function (el) {
        function back(text) {
          el.textContent = text;
          setTimeout(function () { el.textContent = "copy"; }, 1200);
        }

        if (navigator.clipboard) {
          navigator.clipboard.writeText(el.dataset.copy)
            .then(function () { back("copied!"); })
            .catch(function () { back(el.dataset.copy); });
        } else {
          back(el.dataset.copy);
        }
      })(copyBtn);
    }

    var refreshBtn = e.target.closest("[data-refresh]");

    if (refreshBtn) {
      refreshBtn.disabled = true;
      refreshBtn.textContent = "refreshing…";

      var fd = new FormData();
      fd.append("force", "1");

      fetch("/staff/projects/" + refreshBtn.dataset.refresh + "/refresh-github", { method: "POST", body: fd })
        .finally(function () { location.reload(); });
    }

    var printBtn = e.target.closest("[data-print]");

    if (printBtn) {
      window.print();
    }
  });

  var selectAll = document.getElementById("selAll");

  if (selectAll && !selectAll.dataset.wired) {
    selectAll.dataset.wired = "1";

    selectAll.addEventListener("change", function () {
      document.querySelectorAll(".slip-check").forEach(function (box) {
        box.checked = selectAll.checked;
        box.closest(".slip").classList.toggle("skip", !selectAll.checked);
      });
    });

    document.querySelectorAll(".slip-check").forEach(function (box) {
      box.addEventListener("change", function () {
        box.closest(".slip").classList.toggle("skip", !box.checked);
      });
    });
  }

  var warm = document.querySelector("[data-gh-warm]");

  if (warm) {
    fetch("/staff/projects/" + warm.dataset.ghWarm + "/refresh-github", { method: "POST" })
      .then(function () { warm.hidden = true; })
      .catch(function () { warm.hidden = true; });
  }
})();
