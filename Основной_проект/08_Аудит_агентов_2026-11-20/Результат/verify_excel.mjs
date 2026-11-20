import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const filename = new URL('./Excel/Газпром_пример_полного_цикла_8_тезисов.xlsx', import.meta.url).pathname;
const data = JSON.parse(await fs.readFile(new URL('./company.json', import.meta.url), 'utf8'));
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(decodeURIComponent(filename)));
if (book.worksheets.items.length !== 1) throw new Error('Expected one user-facing sheet');
const sheet = book.worksheets.getItemAt(0);
const expected = [data.headers, ...data.sheets[0].rows];
if (JSON.stringify(sheet.getRange('A3:F11').values) !== JSON.stringify(expected)) throw new Error('Value readback differs');
if (!data.sheets[0].rows.every(row => row[4].startsWith('Исследовано:') && row[5].includes('https://'))) {
  throw new Error('Every example needs a completed research outcome and actual source links');
}
const preview = await book.render({ sheetName: sheet.name, range: 'A1:F5', scale: 1.4, format: 'png' });
await fs.writeFile(new URL('./Excel/Проверка_вида.png', import.meta.url), new Uint8Array(await preview.arrayBuffer()));
console.log(JSON.stringify({ sheets: 1, rows: 8, columns: 6, valuesVerified: true, researchedRows: 8, preview: true }));
