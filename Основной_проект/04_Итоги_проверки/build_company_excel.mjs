import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [input, output] = process.argv.slice(2);
const data = JSON.parse(await fs.readFile(input, 'utf8'));
const workbook = Workbook.create();
const widths = [57, 510, 153, 100, 185, 433];
const endBySheet = new Map();

for (const [index, report] of data.sheets.entries()) {
  const sheet = workbook.worksheets.add(report.title);
  const end = 3 + report.rows.length;
  sheet.showGridLines = false;
  sheet.getRange('A1:F1').merge();
  sheet.getRange('A1').values = [[`${data.company} · ${report.id}`]];
  sheet.getRange('A2:F2').merge();
  sheet.getRange('A2').values = [[data.draft ? 'Промежуточная выгрузка' : 'Результаты проверки заявлений']];
  sheet.getRange(`A3:F${end}`).values = [data.headers, ...report.rows];
  if (report.rows.length) {
    const table = sheet.tables.add(`A3:F${end}`, true, `Claims${index + 1}`);
    table.style = 'TableStyleLight1';
    table.showBandedRows = false;
    table.showFilterButton = true;
    const body = sheet.getRange(`A4:F${end}`);
    body.format.font = { name: 'Arial', size: 10, color: '#222222' };
    body.format.wrapText = true;
    body.format.verticalAlignment = 'top';
    report.rows.forEach((row, n) => {
      const lines = Math.max(...row.map((value, i) => String(value).split('\n')
        .reduce((count, line) => count + Math.max(1, Math.ceil(line.length * 7 / (widths[i] - 14))), 0)));
      sheet.getRange(`A${n + 4}:F${n + 4}`).format.rowHeightPx = Math.min(440, Math.max(28, 14 * lines + 12));
    });
  }
  for (const range of ['A1:F1', 'A3:F3']) {
    sheet.getRange(range).format = {
      fill: '#173754', font: { name: 'Arial', size: 11, bold: true, color: '#FFFFFF' },
      rowHeightPx: 34, verticalAlignment: 'center',
    };
  }
  widths.forEach((width, i) => { sheet.getCell(2, i).format.columnWidthPx = width; });
  sheet.freezePanes.freezeRows(3);
  endBySheet.set(report.id, end);
}

const folder = path.resolve(output);
await fs.mkdir(folder, { recursive: false });
const filename = path.join(folder, `Оценка_заявлений_${data.company}${data.draft ? '_черновик' : ''}.xlsx`);
await (await SpreadsheetFile.exportXlsx(workbook)).save(filename);
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(filename));
if (reopened.worksheets.items.length !== data.sheets.length) throw new Error('Missing XLSX tabs');
await fs.mkdir(path.join(folder, 'CSV'));
const escapeCell = value => '"' + String(value).replaceAll('"', '""') + '"';
for (const [index, report] of data.sheets.entries()) {
  const sheet = reopened.worksheets.getItemAt(index);
  const expected = [data.headers, ...report.rows];
  const actual = sheet.getRange(`A3:F${endBySheet.get(report.id)}`).values;
  if (sheet.name !== report.title || JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`XLSX readback differs for ${report.id}`);
  }
  const csv = expected.map(row => row.map(escapeCell).join(';')).join('\n');
  await fs.writeFile(path.join(folder, 'CSV', `${report.id}.csv`), '\uFEFF' + csv + '\n');
}
console.log(JSON.stringify({ filename, sheets: data.sheets.length, rows: data.sheets.reduce((n, sheet) => n + sheet.rows.length, 0) }));
