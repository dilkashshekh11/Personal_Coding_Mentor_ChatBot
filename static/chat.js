// Assistant page: modes, language and the live conversation
(function () {
  var root = document.getElementById("assistant");
  if (!root) return;
  var box = document.getElementById("messages"), form = document.getElementById("chatForm");
  var input = document.getElementById("input"), sendBtn = document.getElementById("sendBtn");
  var lang = document.getElementById("lang");
  var chatId = root.dataset.chatId, mode = root.dataset.mode, busy = false;
  var modeButtons = root.querySelectorAll(".chip");

  lang.value = root.dataset.lang;

  box.querySelectorAll(".bubble[data-md]").forEach(function (b) {
    b.innerHTML = renderMd(b.textContent);
  });
  box.scrollTop = box.scrollHeight;

  function pickMode(key) {
    mode = key;
    modeButtons.forEach(function (b) {
      var on = b.dataset.mode === key;
      b.classList.toggle("on", on);
      if (on) input.placeholder = b.dataset.hint;
    });
  }
  modeButtons.forEach(function (b) {
    b.addEventListener("click", function () { pickMode(b.dataset.mode); input.focus(); });
  });
  pickMode(mode);

  function addMessage(role) {
    var wrap = document.createElement("div");
    wrap.className = "msg " + role;
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    wrap.appendChild(bubble);
    box.appendChild(wrap);
    box.scrollTop = box.scrollHeight;
    return bubble;
  }

  async function send() {
    var text = input.value.trim();
    if (!text || busy) return;
    busy = true; sendBtn.disabled = true; input.value = "";
    var emptyNote = document.getElementById("emptyChat");
    if (emptyNote) emptyNote.remove();

    addMessage("user").textContent = text;
    var bubble = addMessage("assistant");
    bubble.textContent = "Thinking"; bubble.classList.add("thinking");
    var answer = "";

    function show() {
      var i = answer.indexOf("[[FAILED]]");
      var body = i < 0 ? answer : answer.slice(0, i);
      var html = renderMd(body);
      if (i >= 0) html += '<p class="error-text">' + escapeHtml(answer.slice(i + 10)) + "</p>";
      if (html) bubble.classList.remove("thinking");
      bubble.innerHTML = html || "Thinking";
      box.scrollTop = box.scrollHeight;
    }

    try {
      var r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, chat_id: chatId || null, mode: mode, language: lang.value })
      });
      var id = r.headers.get("X-Chat-Id");
      if (id && id !== chatId) {
        chatId = id;
        window.history.replaceState(null, "", "/assistant/" + id);
      }
      var reader = r.body.getReader(), dec = new TextDecoder();
      while (true) {
        var s = await reader.read();
        if (s.done) break;
        answer += dec.decode(s.value, { stream: true });
        show();
      }
    } catch (e) {
      answer += "\n[[FAILED]]Could not reach the app. Is it still running?";
    }
    show();
    busy = false; sendBtn.disabled = false; input.focus();
  }

  form.addEventListener("submit", function (e) { e.preventDefault(); send(); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
})();
