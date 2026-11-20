import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [input, output, previewPath] = process.argv.slice(2);
const { rows } = JSON.parse(await fs.readFile(input, 'utf8'));
const workbook = Workbook.create();
const types = {
  'результат': 'Утверждение о результате',
  'обязательство': 'Обязательство',
  'декларация': 'Общая декларация',
};
const visibleRows = rows.filter(row => !/^\s*\|.*\|\s*$/m.test(row.statement));
const primary = visibleRows.map(row => [
  row.number,
  row.statement.replace(/^\s*#{1,6} +/gm, '').replace(/\*\*/g, '').replace(/\u00ad/g, ''),
  types[row.type], row.block, row.verdict, row.reason,
]);

function addSheet(name, tableName, heading, note, headers, values, widths) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const last = String.fromCharCode(64 + headers.length);
  const end = values.length + 3;
  sheet.getRange(`A1:${last}1`).merge();
  sheet.getRange('A1').values = [[heading]];
  sheet.getRange(`A1:${last}1`).format = {
    fill: '#173754', font: { name: 'Arial', size: 16, bold: true, color: '#FFFFFF' },
    rowHeightPx: 37, verticalAlignment: 'center',
  };
  sheet.getRange(`A2:${last}2`).merge();
  sheet.getRange('A2').values = [[note]];
  sheet.getRange(`A2:${last}2`).format = {
    font: { name: 'Arial', size: 11, color: '#333333' },
    wrapText: true, rowHeightPx: 38, verticalAlignment: 'center',
  };
  sheet.getRange(`A3:${last}${end}`).values = [headers, ...values];
  const table = sheet.tables.add(`A3:${last}${end}`, true, tableName);
  table.style = 'TableStyleLight1';
  table.showBandedRows = false;
  table.showFilterButton = true;
  const content = sheet.getRange(`A4:${last}${end}`);
  content.format.font = { name: 'Arial', size: 10, color: '#222222' };
  content.format.wrapText = true;
  content.format.verticalAlignment = 'top';
  sheet.getRange(`A3:${last}3`).format = {
    fill: '#173754', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' },
    rowHeightPx: 36, verticalAlignment: 'center',
  };
  widths.forEach((width, index) => {
    sheet.getCell(2, index).format.columnWidthPx = width;
  });
  values.forEach((record, index) => {
    const lines = Math.max(...record.map((value, col) => String(value).split('\n')
      .reduce((sum, line) => sum + Math.max(1, Math.ceil(line.length * 7 / (widths[col] - 14))), 0)));
    sheet.getRange(`A${index + 4}:${last}${index + 4}`).format.rowHeightPx =
      Math.min(440, Math.max(37, 14 * lines + 12));
  });
  sheet.freezePanes.freezeRows(3);
  return [last, end];
}

const main = addSheet('Заявления', 'Claims', 'Газпром · экологический отчёт за 2023 год',
  'Пилот. Часть заявлений и источников ещё проверяется.',
  ['№', 'Заявление', 'Тип заявления', 'E / S / G', 'Проверка', 'Почему и на основании чего'],
  primary, [50, 520, 145, 103, 168, 400]);

await (await SpreadsheetFile.exportXlsx(workbook)).save(output);
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
const [last, end] = main;
const actual = reopened.worksheets.getItemAt(0).getRange(`A4:${last}${end}`).values;
if (reopened.worksheets.items.length !== 1 || JSON.stringify(actual) !== JSON.stringify(primary)) {
  throw new Error('XLSX readback differs from the statements register');
}
const preview = await workbook.render({ sheetName: 'Заявления', range: 'A1:F10', scale: 1, format: 'png' });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
console.log(JSON.stringify({ output, rows: primary.length, omittedTableBlocks: rows.length - primary.length }));
