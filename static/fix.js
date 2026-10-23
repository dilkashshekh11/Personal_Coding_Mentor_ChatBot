// Fix My Code page: upload or paste code, then show the answer as it arrives
(function () {
  var code = document.getElementById("code");
  if (!code) return;
  var file = document.getElementById("file"), fileName = document.getElementById("fileName");
  var checkBtn = document.getElementById("checkBtn"), clearBtn = document.getElementById("clearBtn");
  var status = document.getElementById("status");
  var empty = document.getElementById("empty"), answer = document.getElementById("answer");
  var outError = document.getElementById("outError"), outFix = document.getElementById("outFix");
  var outCode = document.getElementById("outCode");
  var source = "paste", name = "";

  file.addEventListener("change", function () {
    var f = file.files[0];
    if (!f) return;
    if (f.size > 200000) { setStatus("That file is too big.", true); return; }
    var reader = new FileReader();
    reader.onload = function () {
      code.value = reader.result;
      source = "upload"; name = f.name;
      fileName.textContent = "File: " + f.name;
      setStatus("");
    };
    reader.readAsText(f);
    file.value = "";
  });

  clearBtn.addEventListener("click", function () {
    code.value = ""; source = "paste"; name = ""; fileName.textContent = "";
    answer.hidden = true; empty.hidden = false; setStatus("");
  });

  function setStatus(text, bad) {
    status.textContent = text;
    status.className = "status" + (bad ? " bad" : "");
  }

  function parse(text) {
    var p = { error: "", fix: "", code: "" };
    var parts = text.split(/\[\[(ERROR|FIX|CODE)\]\]/);
    if (parts.length === 1) { p.error = text; return p; }
    for (var i = 1; i < parts.length - 1; i += 2) p[parts[i].toLowerCase()] = parts[i + 1].trim();
    p.code = p.code.replace(/^```[a-zA-Z]*\n?/, "").replace(/\n?```\s*$/, "");
    return p;
  }

  function show(text) {
    var p = parse(text);
    outError.textContent = p.error;
    outFix.textContent = p.fix;
    outCode.textContent = p.code;
  }

  checkBtn.addEventListener("click", async function () {
    if (!code.value.trim()) { setStatus("Paste or upload your code first.", true); return; }
    checkBtn.disabled = true;
    setStatus("Checking...");
    empty.hidden = true; answer.hidden = false;
    show("");
    var text = "";
    try {
      var r = await fetch("/api/fix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.value, source: source, filename: name })
      });
      var reader = r.body.getReader(), dec = new TextDecoder();
      while (true) {
        var s = await reader.read();
        if (s.done) break;
        text += dec.decode(s.value, { stream: true });
        if (text.indexOf("[[FAILED]]") < 0) show(text);
      }
    } catch (e) {
      text += "\n[[FAILED]]Could not reach the app. Is it still running?";
    }
    var i = text.indexOf("[[FAILED]]");
    if (i >= 0) {
      setStatus(text.slice(i + 10), true);
      if (!text.slice(0, i).trim()) { answer.hidden = true; empty.hidden = false; }
    } else {
      show(text);
      setStatus("Done.");
    }
    checkBtn.disabled = false;
  });

  document.getElementById("copyBtn").addEventListener("click", function () {
    copyText(outCode.textContent, this);
  });
  document.getElementById("saveBtn").addEventListener("click", function () {
    var blob = new Blob([outCode.textContent], { type: "text/plain" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name ? "fixed_" + name.replace(/\.txt$/, ".py") : "fixed_code.py";
    a.click();
    URL.revokeObjectURL(a.href);
  });
})();
