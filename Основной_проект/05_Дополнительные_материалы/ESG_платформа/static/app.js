const $ = id => document.getElementById(id);
const labels = {queued:"В очереди",running:"Агент работает",partial:"Частичный результат",extracted:"Извлечение обработано",failed:"Прогон прерван"};
let reports = [], selected = "", checked = new Set(), claims = [], requestId = 0;
const report = () => reports.find(r => r.report_id === selected);
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (className) node.className = className;
  return node;
};
async function api(path, ids) {
  const response = await fetch(path, ids ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({ids})} : {});
  if (!response.ok) throw Error(`Запрос завершился с кодом ${response.status}`);
  return response.json();
}
function renderChoices() {
  const group = reports.filter(r => r.company === $("company").value);
  $("choices").replaceChildren(...group.map(r => {
    const item = el("div", null, "choice" + (r.report_id === selected ? " active" : ""));
    const box = el("input");
    box.type = "checkbox"; box.checked = checked.has(r.report_id);
    box.setAttribute("aria-label", `Поставить в очередь ${r.report_id}`);
    box.onchange = () => box.checked ? checked.add(r.report_id) : checked.delete(r.report_id);
    const open = el("button", `${r.year} · ${r.report_type}${r.job ? " · " + labels[r.job.status] : ""}`);
    open.onclick = () => selectReport(r.report_id);
    item.append(box, open);
    return item;
  }));
}
function renderDetail(showClaims=true) {
  const r = report();
  if (!r) return;
  $("reportId").textContent = r.report_id;
  $("reportTitle").textContent = `${r.company} · ${r.year}`;
  const found = claims.filter(c => c.searched).length;
  const consistent = r.audit?.hash && r.audit?.positions;
  const stage = (title, detail, ok) => {
    const div = el("div",null,"stage" + (ok ? " ok" : ""));
    div.append(el("b",title),el("span",detail)); return div;
  };
  $("steps").replaceChildren(
    stage("Markdown", consistent ? `${r.physical_pages} стр. · хеш и порядок сверены` : "Ожидает технической сверки",consistent),
    stage("Извлечение ESG",r.job ? `${labels[r.job.status]}${r.job.batches ? ` · ${r.job.processed}/${r.job.batches}` : ""}` : r.pilot_rows ? "Есть пилотная партия" : "Ожидает запуска",false),
    stage("Внешний поиск", found ? `${found} из ${claims.length} заявлений` : "Ожидает поиска",false)
  );
  $("md").href = "api/md/" + encodeURIComponent(selected);
  $("pdf").href = r.pdf_source_url;
  $("csv").href = "api/csv/" + encodeURIComponent(selected);
  $("csv").hidden = !claims.length;
  $("reviewReport").disabled = !claims.some(row => !row.searched && !["queued","running"].includes(row.review_status));
  $("scope").textContent = r.job?.reason || (claims.length ? `${claims.length} кандидатных заявлений. Полнота и числовые поля требуют сверки по PDF.` : "");
  if(showClaims) renderClaims();
}
function renderClaims() {
  const needle = $("filter").value.trim().toLowerCase();
  const filtered = claims.filter(r => `${r.statement} ${r.block} ${r.status} ${r.reason}`.toLowerCase().includes(needle));
  $("claims").replaceChildren(...(filtered.length ? filtered.slice(0,150).map(row => {
    const node = el("details",null,"claim");
    node.append(el("summary",row.statement),el("span",`${row.block} · ${row.type} · ${row.status}${row.page ? " · PDF " + row.page : ""}`,"meta"));
    const reason = el("p",row.reason || "Внешний поиск ещё не выполнен.","reason");
    node.append(reason);
    for (const url of row.links || []) {
      if (!/^https?:\/\//i.test(url)) continue;
      const link = el("a",new URL(url).hostname);
      link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer";
      const p = el("p",null,"reason"); p.append(link); node.append(p);
    }
    const button = el("button", ({queued:"Поиск в очереди",running:"Поиск выполняется",complete:"Поиск завершён"})[row.review_status] || "Найти внешние источники","secondary search-source");
    button.disabled = ["queued","running","complete"].includes(row.review_status);
    button.onclick = async () => {
      button.disabled = true;
      try {
        const result = await fetch("api/review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({report_id:selected,claim_id:row.id})});
        if (!result.ok) throw Error(`Запрос завершился с кодом ${result.status}`);
        row.review_status="queued"; button.textContent="Поиск в очереди";
        $("notice").textContent="Заявление добавлено в очередь внешнего поиска.";
      } catch(error) {button.disabled=false;$("notice").textContent=error.message;}
    };
    node.append(button);
    return node;
  }) : [el("p",needle ? "По запросу ничего не найдено." : "Заявления появятся после извлечения.", "empty")]));
  if (filtered.length > 150) $("claims").append(el("p",`Показаны 150 из ${filtered.length}. Полный список доступен в CSV.`,"hint"));
}
async function selectReport(rid) {
  selected = rid; claims = []; const id = ++requestId;
  renderChoices();renderDetail();
  try { const result = await api("api/claims/" + encodeURIComponent(rid)); if (requestId === id) { claims = result; renderDetail(); } }
  catch(error) { $("notice").textContent=error.message; }
}
async function refresh(first=false) {
  reports = await api("api/reports");
  const companies = [...new Set(reports.map(r=>r.company))].sort((a,b)=>a.localeCompare(b,"ru"));
  if(first) {
    $("company").replaceChildren(...companies.map(c=>el("option",c)));
    $("company").value = "Газпром";
    checked = new Set(["GAZP-2023-ЭО"]);
    if (reports.some(r=>r.report_id==="GAZP-2023-ЭО")) await selectReport("GAZP-2023-ЭО");
  }
  $("companies").textContent = companies.length;
  $("reports").textContent = reports.length;
  $("audited").textContent = reports.filter(r=>r.audit?.hash && r.audit?.positions).length;
  $("queued").textContent = reports.filter(r=>["queued","running"].includes(r.job?.status)).length;
  renderChoices();renderDetail(false);
}
async function action(button,path,ids,done) {
  if(!ids.length) { $("notice").textContent="Отметьте хотя бы один отчёт."; return; }
  button.disabled=true;
  try { await api(path,ids); await refresh(); $("notice").textContent=done; }
  catch(error) { $("notice").textContent=error.message; }
  finally { button.disabled=false; }
}
$("company").onchange=()=>selectReport(reports.find(r=>r.company===$("company").value).report_id);
$("filter").oninput=renderClaims;
$("reviewReport").onclick=async()=>{
  const button = $("reviewReport"); button.disabled = true;
  try {
    const response = await fetch("api/review-report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({report_id:selected})});
    if(!response.ok) throw Error(`Запрос завершился с кодом ${response.status}`);
    const result=await response.json();
    await selectReport(selected);
    $("notice").textContent=`Внешний поиск поставлен в очередь по отчёту. Кандидаты: ${result.queued}.`;
  } catch(error) {button.disabled=false;$("notice").textContent=error.message;}
};
$("run").onclick=()=>action($("run"),"api/queue",[...checked],"Задания добавлены в очередь.");
$("audit").onclick=()=>action($("audit"),"api/audit",[selected],"Хеш и порядок страниц сверены. Смотрите статус отчёта.");
$("auditAll").onclick=()=>action($("auditAll"),"api/audit",reports.map(r=>r.report_id),"Техническая сверка корпуса завершена.");
await refresh(true).catch(error=>{$("notice").textContent=error.message;});
setInterval(async()=>{try {const last=report()?.job?.status; await refresh(); if(selected && (last!==report()?.job?.status || claims.some(row=>["queued","running"].includes(row.review_status)))) {
 const result=await api("api/claims/"+encodeURIComponent(selected));
 if(result.some((row,i)=>row.review_status!==claims[i]?.review_status) || result.length!==claims.length){claims=result;renderDetail();}
}}catch{}},10000);
