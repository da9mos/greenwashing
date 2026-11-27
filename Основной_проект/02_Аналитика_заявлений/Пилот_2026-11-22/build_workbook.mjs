import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const [dataPath, libraries, previewDir] = process.argv.slice(2);
const resolveArtifact = createRequire(path.join(path.resolve(libraries), 'resolver.cjs'));
const { Workbook, SpreadsheetFile, FileBlob } = await import(
  pathToFileURL(resolveArtifact.resolve('@oai/artifact-tool')).href
);
const data = JSON.parse(await fs.readFile(dataPath, 'utf8'));
const book = Workbook.create();

function addSheet(name, tableName, rows, widths, height) {
  const sheet = book.worksheets.add(name);
  const lastCol = String.fromCharCode(64 + widths.length);
  const address = `A1:${lastCol}${rows.length}`;
  const grid = sheet.getRange(address);
  grid.values = rows;
  grid.format.wrapText = true;
  grid.format.verticalAlignment = 'center';
  const table = sheet.tables.add(address, true, tableName);
  table.style = 'TableStyleMedium2';
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  for (const [index, width] of widths.entries()) {
    const col = String.fromCharCode(65 + index);
    sheet.getRange(`${col}:${col}`).format.columnWidthPx = width;
  }
  sheet.getRange(`A1:${lastCol}1`).format.rowHeightPx = 38;
  sheet.getRange(`A2:${lastCol}${rows.length}`).format.rowHeightPx = height;
  sheet.getRange(`A1:${lastCol}${rows.length}`).format.font.size = 11;
  return address;
}

const layouts = [
  { name: 'Заявления', table: 'Claims', rows: data.claims, widths: [55, 112, 57, 59, 119, 130, 421, 267], height: 90 },
  { name: 'Сверка', table: 'Review', rows: data.review, widths: [55, 111, 57, 112, 403, 226, 285], height: 104 },
  { name: 'Ручная проверка', table: 'HumanReview', rows: data.human_review, widths: [55, 455, 540], height: 94 },
];
const addresses = layouts.map(({ name, table, rows, widths, height }) => addSheet(name, table, rows, widths, height));
const filename = fileURLToPath(new URL('ESG_пилот.xlsx', import.meta.url));
await (await SpreadsheetFile.exportXlsx(book)).save(filename);
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(filename));
for (const [index, { name, rows }] of layouts.entries()) {
  const sheet = reopened.worksheets.getItem(name);
  assert.deepEqual(sheet.getRange(addresses[index]).values, rows);
  if (previewDir) {
    const preview = await reopened.render({ sheetName: name, range: addresses[index], format: 'png' });
    await fs.writeFile(path.join(previewDir, `${name}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
}
