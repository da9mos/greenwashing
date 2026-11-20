"""Prepare PDF-derived inputs in isolated single-threaded processes only."""
import json
from pathlib import Path
import run_models as rm
from probe_geometry import source_details
from compare_results import decimal_span_reference


def prepare_report(row):
    index = rm.page_inputs(row)
    rid = row['report_id']
    folder = rm.BASE / '_проверка/геометрия' / rid
    folder.mkdir(parents=True, exist_ok=True)
    with rm.fitz.open(rm.BASE / index['source']) as doc:
        for item in index['pages']:
            n = item['pdf_page']
            output = folder / f'page_{n:04d}_metadata.json'
            if output.exists():
                old = json.loads(output.read_text())
                if old.get('source_sha256') != index['source_sha256']:
                    raise ValueError('Geometry cache source changed')
                if all((rm.BASE / name).is_file() and rm.sha(rm.BASE / name) == digest
                       for name, digest in zip(old['images'], old['image_sha256'])):
                    continue
            geometry, images = source_details(rid, n)
            flags = rm.fitz.TEXTFLAGS_DICT & ~rm.fitz.TEXT_PRESERVE_IMAGES
            reference = decimal_span_reference(doc[n - 1].get_text('dict', flags=flags))
            rm.put_json(output, {'source_sha256': index['source_sha256'], 'geometry': geometry,
                                'images': [str(p.relative_to(rm.BASE)) for p in images],
                                'image_sha256': [rm.sha(p) for p in images], 'decimal_reference': reference})
    return index
