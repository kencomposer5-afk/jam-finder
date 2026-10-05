const $ = s => document.querySelector(s);
const ymd = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const now0 = new Date();
const state = { view: "cal", month: { y: now0.getFullYear(), m: now0.getMonth() }, sel: ymd(now0), pref: "", genre: "", range: "all", area: "", q: "" };
let data = { sessions: [] };
const WD = "日月火水木金土";

function inRange(s) {
  const now = new Date(), today = ymd(now);
  if (s.date < today) return false;
  if (state.range === "today") return s.date === today;
  if (state.range === "week") { const e = new Date(now); e.setDate(e.getDate()+6); return s.date <= ymd(e); }
  if (state.range === "weekend") { const wd = new Date(s.date+"T00:00:00").getDay(); if (wd!==0&&wd!==5&&wd!==6) return false;
    const e = new Date(now); e.setDate(e.getDate()+7); return s.date <= ymd(e); }
  return true;
}

function filtered(useRange) {
  const q = state.q.toLowerCase();
  return data.sessions.filter(s => (!useRange || inRange(s))
    && (!state.genre || s.genre.includes(state.genre))
    && (!state.pref || s.pref === state.pref)
    && (!state.area || s.area === state.area)
    && (!q || (s.venue + s.instruments + s.area).toLowerCase().includes(q)));
}

function card(s) {
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
  return c;
}

const emptyMsg = () => '<div class="empty">該当するセッションがありません' + (state.pref === "埼玉" || state.pref === "千葉" ? "<br><small>この地域は公式確認済みの会場をまだ登録できていません</small>" : "") + "</div>";
const dayLabel = (iso, today) => { const d = new Date(iso+"T00:00:00"); return `${d.getMonth()+1}/${d.getDate()}(${WD[d.getDay()]})${iso === today ? " 今日" : ""}`; };

function renderList() {
  const rows = filtered(true), el = $("#list"), today = ymd(new Date());
  el.textContent = "";
  if (!rows.length) { el.innerHTML = emptyMsg(); return; }
  let last = "";
  for (const s of rows) {
    if (s.date !== last) {
      last = s.date;
      const h = document.createElement("h2");
      if (s.date === today) h.className = "today";
      h.textContent = dayLabel(s.date, today);
      el.append(h);
    }
    el.append(card(s));
  }
}

function renderCalendar() {
  const el = $("#cal"), today = ymd(new Date());
  const by = {};
  for (const s of filtered(false)) (by[s.date] ||= []).push(s);
  const { y, m } = state.month, first = new Date(y, m, 1), days = new Date(y, m + 1, 0).getDate();
  const dates = data.sessions.map(s => s.date), minD = dates[0] || today, maxD = dates[dates.length - 1] || today;
  const prevOk = ymd(new Date(y, m, 0)) >= minD, nextOk = ymd(new Date(y, m + 1, 1)) <= maxD;
  let h = `<div class="calhead"><button id="prev" ${prevOk ? "" : "disabled"} aria-label="前の月">‹</button><b>${y}年${m + 1}月</b><button id="next" ${nextOk ? "" : "disabled"} aria-label="次の月">›</button></div><div class="grid">`;
  h += [...WD].map((w, i) => `<div class="dow${i === 0 ? " sun" : i === 6 ? " sat" : ""}">${w}</div>`).join("");
  for (let i = 0; i < first.getDay(); i++) h += '<div class="cell blank"></div>';
  for (let d = 1; d <= days; d++) {
    const iso = ymd(new Date(y, m, d)), list = by[iso] || [], wd = new Date(y, m, d).getDay();
    const cls = ["cell", iso === today && "today", iso === state.sel && "sel", iso < today && "past", !list.length && "none", wd === 0 && "sun", wd === 6 && "sat"].filter(Boolean).join(" ");
    const dots = list.slice(0, 6).map(s => `<i class="dot ${s.genre.length > 1 ? "both" : s.genre[0]}"></i>`).join("");
    const pills = list.slice(0, 3).map(s => `<span class="pill ${s.genre.length > 1 ? "both" : s.genre[0]}">${esc(s.start)} ${esc(s.venue)}</span>`).join("") + (list.length > 3 ? `<span class="more">+${list.length - 3}</span>` : "");
    h += `<button class="${cls}" data-d="${iso}"><span class="n">${d}</span><span class="dots">${dots}</span><span class="pills">${pills}</span>${list.length ? `<span class="cnt">${list.length}</span>` : ""}</button>`;
  }
  el.innerHTML = h + '</div><div class="legend"><i class="dot jazz"></i>Jazz <i class="dot blues"></i>Blues <i class="dot both"></i>両方</div>';
  $("#prev").onclick = () => { state.month = { y: m ? y : y - 1, m: m ? m - 1 : 11 }; state.sel = ""; render(); };
  $("#next").onclick = () => { state.month = { y: m < 11 ? y : y + 1, m: (m + 1) % 12 }; state.sel = ""; render(); };
  el.querySelectorAll(".cell[data-d]").forEach(b => b.onclick = () => { state.sel = b.dataset.d; render(); $("#day").scrollIntoView({ behavior: "smooth", block: "nearest" }); });
  const day = $("#day"); day.textContent = "";
  if (state.sel && state.sel.startsWith(`${y}-${String(m + 1).padStart(2, "0")}`)) {
    const h2 = document.createElement("h2"); h2.textContent = dayLabel(state.sel, today); if (state.sel === today) h2.className = "today"; day.append(h2);
    const list = by[state.sel] || [];
    if (list.length) list.forEach(s => day.append(card(s))); else day.insertAdjacentHTML("beforeend", emptyMsg());
  } else day.innerHTML = '<div class="empty">日付をタップすると詳細が出ます</div>';
}

function render() {
  const cal = state.view === "cal";
  $("#cal").hidden = $("#day").hidden = !cal;
  $("#list").hidden = cal;
  $("#range").hidden = cal;
  cal ? renderCalendar() : renderList();
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
chips("#view", "view"); chips("#pref", "pref"); chips("#genre", "genre"); chips("#range", "range");
$("#area").onchange = e => { state.area = e.target.value; render(); };
$("#q").oninput = e => { state.q = e.target.value; render(); };

fetch("data/sessions.json", { cache: "no-cache" }).then(r => r.json()).then(j => {
  data = j;
  $("#updated").textContent = "最終更新 " + j.updated.replace("T", " ").slice(0, 16);
  [...new Set(j.sessions.map(s => s.area))].sort().forEach(a => $("#area").add(new Option(a, a)));
  render();
}).catch(() => { $("#cal").hidden = false; $("#cal").innerHTML = '<div class="empty">データを読み込めませんでした</div>'; });

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
