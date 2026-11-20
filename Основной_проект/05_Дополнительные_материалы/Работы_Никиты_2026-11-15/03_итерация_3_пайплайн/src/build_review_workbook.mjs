import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const data=JSON.parse(await fs.readFile(new URL('../outputs/review_v3/workbook_input.json',import.meta.url),'utf8'));
const w=Workbook.create();
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
for(const t of data.sheets){
 const s=w.worksheets.add(t.name);s.showGridLines=false;
 const range=s.getRange(`A1:${col(t.headers.length-1)}${t.rows.length+1}`);
 range.values=[t.headers,...t.rows];
 range.format.font.name='Arial';range.format.font.size=10;
 range.format.rowHeight=30;range.format.columnWidth=19;range.format.verticalAlignment='top';
 for(let i=0;i<t.rows.length;i++){if(i%2===1)s.getRange(`A${i+2}:${col(t.headers.length-1)}${i+2}`).format.fill='#F3F6FA';}
 const h=s.getRange(`A1:${col(t.headers.length-1)}1`);h.format.fill='#243746';h.format.font.color='#FFFFFF';h.format.font.bold=true;h.format.wrapText=true;h.format.rowHeight=44;
 for(let j=0;j<t.headers.length;j++){
  const rr=s.getRange(`${col(j)}2:${col(j)}${Math.max(2,t.rows.length+1)}`);
  if(t.widths?.[j])rr.format.columnWidth=t.widths[j];
  rr.format.wrapText=true;
  const isNumeric=t.rows.some(r=>r[j]!==null)&&t.rows.every(r=>r[j]===null||typeof r[j]==='number'||/^-?[0-9]+([.,][0-9]+)?$/.test(String(r[j])));
  if(isNumeric)rr.format.horizontalAlignment='center';
 }
 if(t.name!=='Обзор'){s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(2);}
 if(t.name==='Обзор')s.getRange('B2:B11').format.horizontalAlignment='center';
 if(t.formulas)for(const [cell,formula]of Object.entries(t.formulas))s.getRange(cell).formulas=[[formula]];
 range.format.autofitRows();
}
w.recalculate();
await fs.mkdir(data.out,{recursive:true});
const x=await SpreadsheetFile.exportXlsx(w);await x.save(`${data.out}/Сбер_проверка_ESG.xlsx`);
for(const t of data.sheets){
 const b=await w.render({sheetName:t.name,range:`A1:${col(Math.min(t.headers.length-1,5))}${Math.min(t.rows.length+1,t.name==='Обзор'?11:7)}`,scale:1.3,format:'png'});
 await fs.writeFile(`${data.out}/preview_${t.name}.png`,new Uint8Array(await b.arrayBuffer()));
}
console.log((await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:30},maxChars:2000})).ndjson);
console.log(JSON.stringify({sheets:data.sheets.map(x=>[x.name,x.rows.length]),output:`${data.out}/Сбер_проверка_ESG.xlsx`}));
