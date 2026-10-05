const $ = s => document.querySelector(s);
const state = { pref: "", genre: "", range: "all", area: "", q: "" };
let data = { sessions: [] };
const WD = "日月火水木金土";
const ymd = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;

function inRange(s) {
  const now = new Date(), today = ymd(now);
  if (s.date < today) return false;
  if (state.range === "today") return s.date === today;
  if (state.range === "week") { const e = new Date(now); e.setDate(e.getDate()+6); return s.date <= ymd(e); }
  if (state.range === "weekend") { const wd = new Date(s.date+"T00:00:00").getDay(); if (wd!==0&&wd!==5&&wd!==6) return false;
    const e = new Date(now); e.setDate(e.getDate()+7); return s.date <= ymd(e); }
  return true;
}

function render() {
  const q = state.q.toLowerCase();
  const rows = data.sessions.filter(s => inRange(s)
    && (!state.genre || s.genre.includes(state.genre))
    && (!state.pref || s.pref === state.pref)
    && (!state.area || s.area === state.area)
    && (!q || (s.venue + s.instruments + s.area).toLowerCase().includes(q)));
  const el = $("#list"); el.textContent = "";
  if (!rows.length) { el.innerHTML = '<div class="empty">該当するセッションがありません' + (state.pref === '埼玉' || state.pref === '千葉' ? '<br><small>この地域は公式確認済みの会場をまだ登録できていません</small>' : '') + '</div>'; return; }
  let last = "";
  for (const s of rows) {
    if (s.date !== last) {
      last = s.date; const d = new Date(s.date+"T00:00:00");
      const h = document.createElement("h2");
      if (s.date === ymd(new Date())) h.className = "today";
      h.textContent = `${d.getMonth()+1}/${d.getDate()}(${WD[d.getDay()]})${h.className ? " 今日" : ""}`;
      el.append(h);
    }
    const c = document.createElement("div");
    c.className = "card " + (s.genre.length > 1 ? "both" : s.genre[0]);
    const map = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(s.venue.replace(/^\(サンプル\)/,"") + " " + s.address);
    const tags = s.genre.map(g => `<span class="tag">${g}</span>`).join("") + (s.level ? `<span class="tag">${esc(s.level)}</span>` : "");
    c.innerHTML = `<div class="t">${s.start}${s.end ? "–" + s.end : ""}</div>
      <div class="v">${esc(s.venue)}</div>
      <div class="m">${esc(s.pref)} ${esc(s.area)} ・ ${esc(s.fee)}</div>
      <div class="m">${esc(s.instruments)}</div>
      <div>${tags}</div>
      ${s.note ? `<div class="m">📝 ${esc(s.note)}</div>` : ""}
      ${s.warn ? '<div class="warn">⚠ 会場サイトに休業/中止の記載があります。事前に確認を</div>' : ""}
      ${s.sample ? '<div class="sample">サンプルデータ</div>' : ""}
      <div class="links"><a href="${esc(s.url)}" target="_blank" rel="noopener">公式</a><a href="${map}" target="_blank" rel="noopener">地図</a></div>`;
    el.append(c);
  }
}
const esc = t => String(t ?? "").replace(/[&<>"]/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));

function chips(id, key) {
  $(id).addEventListener("click", e => {
    if (e.target.tagName !== "BUTTON") return;
    state[key] = e.target.dataset.v;
    $(id).querySelectorAll("button").forEach(b => b.classList.toggle("on", b === e.target));
    render();
  });
}
chips("#pref", "pref"); chips("#genre", "genre"); chips("#range", "range");
$("#area").onchange = e => { state.area = e.target.value; render(); };
$("#q").oninput = e => { state.q = e.target.value; render(); };

fetch("data/sessions.json", { cache: "no-cache" }).then(r => r.json()).then(j => {
  data = j;
  $("#updated").textContent = "最終更新 " + j.updated.replace("T", " ").slice(0, 16);
  [...new Set(j.sessions.map(s => s.area))].sort().forEach(a => $("#area").add(new Option(a, a)));
  render();
}).catch(() => { $("#list").innerHTML = '<div class="empty">データを読み込めませんでした</div>'; });

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
