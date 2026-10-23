// shared helpers: menu, copy buttons and a small text-to-HTML converter

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inlineMd(s) {
  s = escapeHtml(s);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  return s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

// turns the assistant's text (headings, lists, code blocks) into HTML
function renderMd(text) {
  var out = [], lines = text.split("\n"), list = null, i = 0;
  function closeList() { if (list) { out.push("</" + list + ">"); list = null; } }
  function openList(tag) {
    if (list !== tag) { closeList(); out.push("<" + tag + ">"); list = tag; }
  }
  while (i < lines.length) {
    var line = lines[i], m;
    if (/^\s*```/.test(line)) {
      closeList();
      var code = [];
      i++;
      while (i < lines.length && !/^\s*```/.test(lines[i])) { code.push(lines[i]); i++; }
      i++;
      out.push('<div class="codebox"><button type="button" data-copy-next>Copy</button>' +
               "<pre><code>" + escapeHtml(code.join("\n")) + "</code></pre></div>");
      continue;
    }
    if ((m = line.match(/^#{1,4}\s+(.*)/))) {
      closeList(); out.push("<h4>" + inlineMd(m[1]) + "</h4>");
    } else if ((m = line.match(/^\s*[-*]\s+(.*)/))) {
      openList("ul"); out.push("<li>" + inlineMd(m[1]) + "</li>");
    } else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) {
      openList("ol"); out.push("<li>" + inlineMd(m[1]) + "</li>");
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList(); out.push("<p>" + inlineMd(line) + "</p>");
    }
    i++;
  }
  closeList();
  return out.join("");
}

function copyText(text, button) {
  function done() {
    var old = button.textContent;
    button.textContent = "Copied";
    setTimeout(function () { button.textContent = old; }, 1200);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, done);
  } else {
    var t = document.createElement("textarea");
    t.value = text; document.body.appendChild(t); t.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(t); done();
  }
}

document.addEventListener("click", function (e) {
  var next = e.target.closest("[data-copy-next]");
  if (next) {
    copyText(next.parentNode.querySelector("pre").textContent, next);
    return;
  }
  var target = e.target.closest("[data-copy]");
  if (target) {
    var el = document.querySelector(target.getAttribute("data-copy"));
    if (el) copyText(el.textContent, target);
  }
});

(function () {
  var menu = document.getElementById("menuBtn"), side = document.getElementById("sidebar");
  if (menu) menu.addEventListener("click", function () { side.classList.toggle("open"); });

})();
