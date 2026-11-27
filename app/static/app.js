"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const els = {
    tabText: $("tab-text"), tabUrl: $("tab-url"),
    panelText: $("panel-text"), panelUrl: $("panel-url"),
    form: $("form"), text: $("text"), url: $("url"), counter: $("counter"), clear: $("clear"),
    style: $("style"), keyPoints: $("key-points"), submit: $("submit"),
    empty: $("empty"), error: $("error"), loading: $("loading"), output: $("output"),
    title: $("out-title"), source: $("out-source"), summary: $("out-summary"),
    pointsWrap: $("out-points-wrap"), points: $("out-points"),
    stOrig: $("st-orig"), stSum: $("st-sum"), stRatio: $("st-ratio"), stTime: $("st-time"),
    engine: $("out-engine"), badge: $("engine-badge"), copy: $("copy"), download: $("download"),
  };

  let mode = "text";
  let lastResult = null;

  // ---- Tabs -------------------------------------------------------------
  function setMode(next) {
    mode = next;
    const isText = mode === "text";
    els.tabText.classList.toggle("active", isText);
    els.tabUrl.classList.toggle("active", !isText);
    els.tabText.setAttribute("aria-selected", String(isText));
    els.tabUrl.setAttribute("aria-selected", String(!isText));
    els.panelText.hidden = !isText;
    els.panelUrl.hidden = isText;
    (isText ? els.text : els.url).focus();
  }
  els.tabText.addEventListener("click", () => setMode("text"));
  els.tabUrl.addEventListener("click", () => setMode("url"));

  // ---- Word counter -----------------------------------------------------
  const countWords = (s) => (s.match(/[\p{L}\p{N}'’-]+/gu) || []).length;
  function updateCounter() {
    const n = countWords(els.text.value);
    const mins = Math.max(n / 238, 0).toFixed(1);
    els.counter.textContent = `${n.toLocaleString()} words · ~${mins} min read`;
  }
  els.text.addEventListener("input", updateCounter);
  els.clear.addEventListener("click", () => { els.text.value = ""; updateCounter(); els.text.focus(); });

  // ---- State helpers ----------------------------------------------------
  function show(state) {
    els.empty.hidden = state !== "empty";
    els.loading.hidden = state !== "loading";
    els.output.hidden = state !== "output";
    if (state !== "error") els.error.hidden = true;
  }
  function showError(msg) {
    show(lastResult ? "output" : "empty");
    els.error.textContent = msg;
    els.error.hidden = false;
  }
  function setBusy(busy) {
    els.submit.disabled = busy;
    els.submit.classList.toggle("loading", busy);
    els.submit.querySelector(".btn-label").textContent = busy ? "Summarizing…" : "Summarize";
  }

  // ---- Rendering ---------------------------------------------------------
  function renderSummary(container, text) {
    container.replaceChildren();
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    const isBullet = (l) => /^([-*•]|\d+[.)])\s+/.test(l);
    let list = null;
    for (const line of lines) {
      if (isBullet(line)) {
        if (!list) { list = document.createElement("ul"); container.appendChild(list); }
        const li = document.createElement("li");
        li.textContent = line.replace(/^([-*•]|\d+[.)])\s+/, "");
        list.appendChild(li);
      } else {
        list = null;
        const p = document.createElement("p");
        p.textContent = line;
        container.appendChild(p);
      }
    }
  }

  function render(data) {
    lastResult = data;
    els.title.textContent = data.title || "Summary";
    if (data.source_url) {
      els.source.href = data.source_url;
      els.source.textContent = data.source_title || data.source_url;
      els.source.hidden = false;
    } else {
      els.source.hidden = true;
    }
    renderSummary(els.summary, data.summary);

    els.points.replaceChildren(...(data.key_points || []).map((p) => {
      const li = document.createElement("li");
      li.textContent = p;
      return li;
    }));
    els.pointsWrap.hidden = !(data.key_points && data.key_points.length);

    const s = data.stats;
    els.stOrig.textContent = `${s.original_words.toLocaleString()} words`;
    els.stSum.textContent = `${s.summary_words.toLocaleString()} words`;
    els.stRatio.textContent = `${Math.max(0, Math.round((1 - s.compression_ratio) * 100))}%`;
    const saved = Math.max(s.reading_time_minutes - s.summary_words / 238, 0);
    els.stTime.textContent = saved < 1 ? "<1 min" : `~${Math.round(saved)} min`;

    els.engine.textContent = data.engine === "claude"
      ? `Summarized by Claude (${data.model}).`
      : "Summarized offline with the extractive engine (sentences taken from the article). Add an Anthropic API key for AI summaries.";
    show("output");
  }

  function toMarkdown(d) {
    let md = `# ${d.title}\n\n`;
    if (d.source_url) md += `Source: ${d.source_url}\n\n`;
    md += `${d.summary}\n`;
    if (d.key_points && d.key_points.length) {
      md += `\n## Key points\n\n${d.key_points.map((p) => `- ${p}`).join("\n")}\n`;
    }
    return md;
  }

  // ---- Actions ----------------------------------------------------------
  els.copy.addEventListener("click", async () => {
    if (!lastResult) return;
    try {
      await navigator.clipboard.writeText(toMarkdown(lastResult));
      els.copy.textContent = "Copied!";
    } catch {
      els.copy.textContent = "Copy failed";
    }
    setTimeout(() => { els.copy.textContent = "Copy"; }, 1500);
  });

  els.download.addEventListener("click", () => {
    if (!lastResult) return;
    const blob = new Blob([toMarkdown(lastResult)], { type: "text/markdown" });
    const a = document.createElement("a");
    const slug = (lastResult.title || "summary").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
    a.href = URL.createObjectURL(blob);
    a.download = `${slug || "summary"}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  function errorMessage(body, status) {
    if (body && typeof body.detail === "string") return body.detail;
    if (body && Array.isArray(body.detail) && body.detail.length) {
      return body.detail.map((d) => (d.msg || "").replace(/^Value error, /, "")).join(" ");
    }
    return `Something went wrong (HTTP ${status}). Please try again.`;
  }

  async function submit(e) {
    if (e) e.preventDefault();
    const payload = {
      length: els.form.querySelector('input[name="length"]:checked').value,
      style: els.style.value,
      include_key_points: els.keyPoints.checked,
    };
    if (mode === "text") {
      const text = els.text.value.trim();
      if (!text) { showError("Paste an article to summarize."); els.text.focus(); return; }
      payload.text = text;
    } else {
      const url = els.url.value.trim();
      if (!/^https?:\/\/\S+\.\S+/i.test(url)) { showError("Enter a valid http(s) URL."); els.url.focus(); return; }
      payload.url = url;
    }

    setBusy(true);
    show("loading");
    try {
      const res = await fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(errorMessage(body, res.status));
      render(body);
    } catch (err) {
      showError(err instanceof TypeError ? "Can't reach the server. Is it running?" : err.message);
    } finally {
      setBusy(false);
    }
  }

  els.form.addEventListener("submit", submit);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") submit(e);
  });

  // ---- Engine badge -------------------------------------------------------
  fetch("/api/health").then((r) => r.json()).then((h) => {
    els.badge.hidden = false;
    if (h.engine === "claude") {
      els.badge.textContent = `AI: ${h.model}`;
    } else {
      els.badge.textContent = "Offline mode";
      els.badge.classList.add("offline");
      els.badge.title = "No ANTHROPIC_API_KEY configured: using the extractive summarizer.";
    }
  }).catch(() => {});

  updateCounter();
})();
