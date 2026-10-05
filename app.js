const $ = s => document.querySelector(s);
const ymd = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const now0 = new Date();
const state = { view: "cal", month: { y: now0.getFullYear(), m: now0.getMonth() }, sel: ymd(now0), pref: "", genre: "", range: "all", area: "", q: "" };
let data = { sessions: [] };
const GENRES = { jazz: ["Jazz", "#e0a526"], blues: ["Blues", "#4a8fe0"], rock: ["Rock", "#e0533d"], funk: ["Funk/Soul", "#9b59d0"],
  pop: ["Pop", "#e05c9a"], classic: ["クラシック", "#2faa6b"], all: ["ジャンル問わず", "#8a8178"] };
const gname = g => (GENRES[g] || [g])[0];
const gcol = g => (GENRES[g] || [0, "#8a8178"])[1];
const gstyle = gs => `--g:${gcol(gs[0])};--g2:${gcol(gs[1] || gs[0])}`;
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
  c.className = "card"; c.style.cssText = gstyle(s.genre);
  const map = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(s.venue.replace(/^\(サンプル\)/,"") + " " + (s.address || s.pref + " " + s.area));
  const tags = s.genre.map(g => `<span class="tag">${esc(gname(g))}</span>`).join("") + (s.level ? `<span class="tag">${esc(s.level)}</span>` : "");
  c.innerHTML = `<div class="t">${s.time_note ? esc(s.time_note) : s.start + (s.end ? "–" + s.end : "")}</div>
    <div class="v">${esc(s.venue)}</div>
    <div class="m">${esc(s.pref)} ${esc(s.area)} ・ ${esc(s.fee)}</div>
    <div class="m">${esc(s.instruments)}</div>
    <div>${tags}</div>
    ${s.note ? `<div class="m">📝 ${esc(s.note)}</div>` : ""}
    ${s.warn ? '<div class="warn">⚠ 会場サイトに休業/中止の記載があります。事前に確認を</div>' : ""}
    ${s.sample ? '<div class="sample">サンプルデータ</div>' : ""}
    ${s.src ? `<div class="sample">情報元: ${esc(s.src)}</div>` : ""}
    <div class="links">${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">公式</a>` : ""}<a href="${map}" target="_blank" rel="noopener">地図</a></div>`;
  return c;
}

const emptyMsg = () => '<div class="empty">該当するセッションがありません' + (state.pref === "埼玉" || state.pref === "千葉" ? "<br><small>この地域は公式確認済みの会場をまだ登録できていません</small>" : "") + "</div>";
function buildGenreChips() {
  const present = Object.keys(GENRES).filter(g => data.sessions.some(s => s.genre.includes(g)));
  $("#genre").innerHTML = '<button data-v="" class="on">すべて</button>' + present.map(g => `<button data-v="${g}">${esc(gname(g))}</button>`).join("");
}
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

const HOLIDAYS = {
  "2026-01-01":"元日","2026-01-12":"成人の日","2026-02-11":"建国記念の日","2026-02-23":"天皇誕生日","2026-03-20":"春分の日",
  "2026-04-29":"昭和の日","2026-05-03":"憲法記念日","2026-05-04":"みどりの日","2026-05-05":"こどもの日","2026-05-06":"振替休日",
  "2026-07-20":"海の日","2026-08-11":"山の日","2026-09-21":"敬老の日","2026-09-22":"国民の休日","2026-09-23":"秋分の日",
  "2026-10-12":"スポーツの日","2026-11-03":"文化の日","2026-11-23":"勤労感謝の日",
  "2027-01-01":"元日","2027-01-11":"成人の日","2027-02-11":"建国記念の日","2027-02-23":"天皇誕生日","2027-03-21":"春分の日",
  "2027-03-22":"振替休日","2027-04-29":"昭和の日","2027-05-03":"憲法記念日","2027-05-04":"みどりの日","2027-05-05":"こどもの日",
  "2027-07-19":"海の日","2027-08-11":"山の日","2027-09-20":"敬老の日","2027-09-23":"秋分の日","2027-10-11":"スポーツの日",
  "2027-11-03":"文化の日","2027-11-23":"勤労感謝の日"
};

function renderCalendar() {
  const el = $("#cal"), today = ymd(new Date());
  const by = {};
  for (const s of filtered(false)) (by[s.date] ||= []).push(s);
  const { y, m } = state.month, first = new Date(y, m, 1), last = new Date(y, m + 1, 0);
  const dates = data.sessions.map(s => s.date), minD = dates[0] || today, maxD = dates[dates.length - 1] || today;
  const prevOk = ymd(new Date(y, m, 0)) >= minD, nextOk = ymd(new Date(y, m + 1, 1)) <= maxD;
  const mname = first.toLocaleString("en", { month: "long" });
  let h = `<div class="mhead"><button id="prev" ${prevOk ? "" : "disabled"} aria-label="前の月">‹</button>
    <div class="mtitle"><span class="mbig">${m + 1}</span><span class="msub"><b>${mname}</b> ${y}<br>${y}年${m + 1}月</span></div>
    <button id="next" ${nextOk ? "" : "disabled"} aria-label="次の月">›</button></div><div class="grid">`;
  h += [...WD].map((w, i) => `<div class="dow${i === 0 ? " sun" : i === 6 ? " sat" : ""}">${w}</div>`).join("");
  const start = new Date(y, m, 1 - first.getDay()), end = new Date(y, m, last.getDate() + (6 - last.getDay()));
  for (let dt = new Date(start); dt <= end; dt.setDate(dt.getDate() + 1)) {
    const iso = ymd(dt), list = by[iso] || [], wd = dt.getDay(), hol = HOLIDAYS[iso];
    const cls = ["cell", dt.getMonth() !== m && "adj", iso === today && "today", iso === state.sel && "sel", iso < today && "past", !list.length && "none",
      (wd === 0 || hol) ? "sun" : wd === 6 && "sat"].filter(Boolean).join(" ");
    const dots = list.slice(0, 6).map(s => `<i class="dot" style="${gstyle(s.genre)}"></i>`).join("");
    const pills = list.slice(0, 4).map(s => `<span class="pill" style="${gstyle(s.genre)}">${esc(s.start || "午後")} ${esc(s.venue)}</span>`).join("") + (list.length > 4 ? `<span class="more">+${list.length - 4}</span>` : "");
    h += `<button class="${cls}" data-d="${iso}"><span class="n">${dt.getDate()}</span>${hol ? `<span class="hol">${hol}</span>` : ""}<span class="dots">${dots}</span><span class="pills">${pills}</span>${list.length ? `<span class="cnt">${list.length}件</span>` : ""}</button>`;
  }
  const present = [...new Set(data.sessions.flatMap(s => s.genre))];
  el.innerHTML = h + '</div><div class="legend">' + present.map(g => `<i class="dot" style="--g:${gcol(g)};--g2:${gcol(g)}"></i>${esc(gname(g))}`).join(" ") + "</div>";
  $("#prev").onclick = () => { state.month = { y: m ? y : y - 1, m: m ? m - 1 : 11 }; state.sel = ""; render(); };
  $("#next").onclick = () => { state.month = { y: m < 11 ? y : y + 1, m: (m + 1) % 12 }; state.sel = ""; render(); };
  el.querySelectorAll(".cell[data-d]").forEach(b => b.onclick = () => {
    const [yy, mm] = b.dataset.d.split("-").map(Number);
    state.sel = b.dataset.d; state.month = { y: yy, m: mm - 1 }; render();
    $("#day").scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  const day = $("#day"); day.textContent = "";
  if (state.sel) {
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
  buildGenreChips();
  render();
}).catch(() => { $("#cal").hidden = false; $("#cal").innerHTML = '<div class="empty">データを読み込めませんでした</div>'; });

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
