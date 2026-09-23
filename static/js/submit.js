(function () {
  var form = document.getElementById("subForm");

  if (form && form.dataset.code) {
    try {
      localStorage.setItem("dh_last", JSON.stringify({
        code: form.dataset.code,
        name: form.dataset.room || "",
        at: Date.now()
      }));
    } catch (e) {}
  }

  function syncMode() {
    var checked = document.querySelector('input[name="presentation_type"]:checked');
    var v = (checked || {}).value || "link";
    var fileWrap = document.getElementById("presFileWrap");
    var linkWrap = document.getElementById("presLinkWrap");

    if (fileWrap) fileWrap.hidden = v !== "file";
    if (linkWrap) linkWrap.hidden = v !== "link";
  }

  document.querySelectorAll('input[name="presentation_type"]').forEach(function (radio) {
    radio.addEventListener("change", syncMode);
  });
  syncMode();

  if (!form) return;

  var code = form.dataset.code;
  var status = document.getElementById("saveStatus");

  function say(text) {
    if (status) status.textContent = text;
  }

  var timer = null;
  var dirty = false;

  function save() {
    if (!dirty) return;
    dirty = false;
    say("saving…");

    var fd = new FormData(form);
    fd.set("autosave", "1");

    var checked = document.querySelector('input[name="presentation_type"]:checked');
    if (checked) fd.set("presentation_type", checked.value);

    var linkInput = document.querySelector('input[name="presentation_link"]');
    if (linkInput) fd.set("presentation_link", linkInput.value);

    fetch("/submit/" + code + "/save", {
      method: "POST",
      body: fd,
      headers: { "X-Requested-With": "fetch" }
    })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        say(j.ok
          ? (j.saved.join(" + ") + " saved · " + new Date().toLocaleTimeString())
          : ("save broke: " + (j.error || "??")));
      })
      .catch(function () {
        say("offline — retrying");
        dirty = true;
      });
  }

  function markDirty() {
    dirty = true;
    say("editing…");
    clearTimeout(timer);
    timer = setTimeout(save, 2500);
  }

  form.addEventListener("input", markDirty);

  document.addEventListener("change", function (e) {
    if (e.target && e.target.name === "presentation_link") markDirty();
  });

  setInterval(save, 20000);

  var file = document.getElementById("shotFile");
  var prev = document.getElementById("shotPrev");

  if (file) file.addEventListener("change", function () {
    if (!file.files.length) return;
    say("uploading…");

    var fd = new FormData();
    fd.append("shot", file.files[0]);

    fetch("/submit/" + code + "/shot", { method: "POST", body: fd })
      .then(function (r) {
        return r.json().then(function (j) { return { status: r.status, body: j }; });
      })
      .then(function (o) {
        if (o.body.ok) {
          say("shot saved");
          if (prev) {
            prev.src = o.body.url;
            prev.hidden = false;
          }
        } else {
          say("upload broke: " + (o.body.error || o.status));
        }
      });
  });

  var deckFile = document.getElementById("presFile");
  var deckStatus = document.getElementById("presStatus");

  if (deckFile) deckFile.addEventListener("change", function () {
    if (!deckFile.files.length) return;
    if (deckStatus) deckStatus.textContent = "uploading deck…";

    var fd = new FormData();
    fd.append("file", deckFile.files[0]);

    fetch("/submit/" + code + "/presentation/file", { method: "POST", body: fd })
      .then(function (r) {
        return r.json().then(function (j) { return { status: r.status, body: j }; });
      })
      .then(function (o) {
        if (o.body.ok) {
          location.reload();
        } else if (deckStatus) {
          deckStatus.textContent = "upload broke: " + (o.body.error || o.status);
        }
      });
  });

  var warm = document.getElementById("ghWarm");

  if (warm && code) {
    fetch("/submit/" + code + "/github/warm", { method: "POST" })
      .then(function () { warm.hidden = true; })
      .catch(function () { warm.hidden = true; });
  }

  var dl = document.getElementById("deadlineCount");
  var iso = dl && dl.dataset.iso;

  if (dl && iso) {
    var target = new Date(iso).getTime();

    (function tick() {
      var ms = target - Date.now();

      if (ms <= 0) {
        dl.textContent = "fields locked — read-only";
        return;
      }

      dl.textContent = Math.floor(ms / 3.6e6) + "h "
        + Math.floor(ms % 3.6e6 / 6e4) + "m "
        + Math.floor(ms % 6e4 / 1e3) + "s left";
      setTimeout(tick, 1000);
    })();
  }
})();
