import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const here=new URL('./',import.meta.url);
const data=JSON.parse(await fs.readFile(new URL('company.json',here),'utf8'));
const filename=new URL('../04_Итоги_проверки/Газпром/Годовая_книга/Газпром.xlsx',here);
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(decodeURIComponent(filename.pathname)));
const names=book.worksheets.items.map(s=>s.name);
if(JSON.stringify(names)!==JSON.stringify(['2023','2024','2025']))throw new Error('Expected three annual tabs');
await fs.mkdir(new URL('Проверка_вида/',here),{recursive:true});
let count=0;
for(const [i,year] of data.sheets.entries()){
 const s=book.worksheets.getItemAt(i),expected=[data.headers,...year.rows];
 const actual=s.getRange(`A1:F${expected.length}`).values;
 if(JSON.stringify(actual)!==JSON.stringify(expected))throw new Error(`Value readback differs in ${year.title}`);
 for(const row of year.rows){
  if(/Исследовано:|направления поиска|сохранены в журнале|Проверка проектных агентов/i.test(row.join('\n')))throw new Error('Process boilerplate found');
  if(row.length!==6||row.some(c=>c===null||c===''))throw new Error('Missing user-facing content');
 }
 const image=await book.render({sheetName:s.name,range:`A1:F${Math.min(expected.length,3)}`,scale:1.2,format:'png'});
 await fs.writeFile(new URL(`Проверка_вида/${s.name}.png`,here),new Uint8Array(await image.arrayBuffer()));
 count+=year.rows.length;
}
const report={sheets:names,rows:data.sheets.map(s=>s.rows.length),total:count,valuesVerified:true,fullCorpusComplete:false};
await fs.writeFile(new URL('Проверка_вида/readback.json',here),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
