(function () {
  var box = document.getElementById("lastUsed");
  if (!box) return;

  var saved = null;
  try {
    saved = JSON.parse(localStorage.getItem("dh_last") || "null");
  } catch (e) {}

  if (!saved || !saved.code) return;

  function ago(timestamp) {
    var seconds = Math.floor((Date.now() - timestamp) / 1000);

    if (seconds < 60) return "just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
    return Math.floor(seconds / 86400) + "d ago";
  }

  document.getElementById("lastX").addEventListener("click", function () {
    try { localStorage.removeItem("dh_last"); } catch (e) {}
    box.hidden = true;
  });

  fetch("/check/" + encodeURIComponent(saved.code))
    .then(function (r) { return r.json(); })
    .then(function (j) {
      var text = document.getElementById("lastText");

      if (!j.ok) {
        text.textContent = "last code no longer active.";
      } else {
        var link = document.createElement("a");
        link.href = "/submit/" + encodeURIComponent(saved.code);
        link.textContent = j.name || saved.code;

        text.textContent = "last used: ";
        text.appendChild(link);
        text.appendChild(document.createTextNode(" · used " + ago(saved.at || Date.now())));
      }

      box.hidden = false;
    })
    .catch(function () {});
})();
