"""Offline review-evidence gate. Passing is not semantic certification of a PDF."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

COMPONENTS = ('text', 'numbers', 'tables', 'footnotes', 'graphics', 'reading_order', 'links', 'display')
STATUSES = {'checked', 'not_applicable', 'pending', 'blocked'}
REQUIRED_KINDS = {'source_image', 'output_render', 'comparison'}
KINDS = REQUIRED_KINDS | {'source_crop'}
MARKER = re.compile(r'<!--\s*pdf_page:\s*(\d+)\s*-->')
HEX = re.compile(r'[0-9a-f]{64}')

class GateError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

def fail(code, message):
    raise GateError(code, message)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def obj(value, label):
    if not isinstance(value, dict):
        fail('SCHEMA', label + ' must be an object')
    return value

def entries(value, label):
    if not isinstance(value, list):
        fail('SCHEMA', label + ' must be a list')
    return value

def description(value, label):
    if not isinstance(value, str) or len(value.strip()) < 20:
        fail('EMPTY_EVIDENCE', label + ' needs a concrete observation (at least 20 characters)')
    return value

def file_ref(root, value, label, suffixes):
    value = obj(value, label)
    relative = value.get('path')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        fail('UNSAFE_PATH', label + ' must use a relative path within --root')
    raw = root / relative
    path = raw.resolve()
    if not path.is_relative_to(root) or raw.is_symlink():
        fail('UNSAFE_PATH', label + ' escapes root or is a symlink')
    if path.suffix.lower() not in suffixes or not path.is_file():
        fail('MISSING_FILE', label + ' is missing or has an unsupported type: ' + relative)
    expected = value.get('sha256')
    if not isinstance(expected, str) or not HEX.fullmatch(expected) or sha(path) != expected:
        fail('SHA_MISMATCH', label + ' does not identify the current saved file')
    if path.stat().st_size == 0:
        fail('EMPTY_EVIDENCE', label + ' is empty')
    return path

def validate_review(manifest_path, root=None):
    """Validate identities/coverage only; never mutate manifests or source artifacts."""
    manifest_path = Path(manifest_path).resolve()
    root = Path(root).resolve() if root else manifest_path.parent
    manifest_bytes = manifest_path.read_bytes()
    data = obj(json.loads(manifest_bytes), 'manifest')
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        fail('SCHEMA', 'schema_version must be 1')
    if set(data) - {'schema_version', 'source', 'output', 'artifacts', 'review'}:
        fail('SCHEMA', 'Unexpected root fields: do not mix conversion and review registries')
    source_meta = obj(data.get('source'), 'source')
    output_meta = obj(data.get('output'), 'output')
    source = file_ref(root, source_meta, 'source', {'.pdf'})
    output = file_ref(root, output_meta, 'output', {'.md'})
    identities = {source: source_meta['sha256'], output: output_meta['sha256']}
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    try:
        import pymupdf as fitz
        with fitz.open(source) as doc:
            if not doc.is_pdf or doc.needs_pass:
                fail('PDF_UNREADABLE', 'Source must be a readable PDF')
            total = len(doc)
            bounds = [list(page.rect) for page in doc]
    except ImportError as exc:
        fail('PDF_READER_UNAVAILABLE', 'Install/use the existing local PyMuPDF environment: ' + str(exc))
    except GateError:
        raise
    except Exception as exc:
        fail('PDF_UNREADABLE', type(exc).__name__ + ': ' + str(exc))
    if type(source_meta.get('pages')) is not int or source_meta['pages'] != total or total < 1:
        fail('SOURCE_PAGE_COUNT', 'Declared page count differs from the actual PDF')
    md = output.read_text()
    markers = list(MARKER.finditer(md))
    if [int(m[1]) for m in markers] != list(range(1, total + 1)):
        fail('OUTPUT_PAGE_COVERAGE', 'Saved MD must contain every physical page exactly once and in order')
    if re.findall(r'id=[\"\'](pdf-page-\d+)[\"\']', md) != [f'pdf-page-{n}' for n in range(1, total + 1)]:
        fail('OUTPUT_PAGE_ANCHORS', 'Saved MD must contain one ordered physical-page anchor per page')
    parts = {i + 1: md[m.start(): markers[i+1].start() if i+1 < len(markers) else len(md)] for i,m in enumerate(markers)}
    review = obj(data.get('review'), 'review')
    declared = review.get('status')
    if declared not in {'partial', 'checked'}:
        fail('SCHEMA', 'review.status must be partial or checked; conversion metadata is not review evidence')
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        fail('SCHEMA', 'review.reviewer must identify the reviewing actor/session')
    if review.get('method') not in {'full_source_comparison', 'sample', 'automated'}:
        fail('SCHEMA', 'Unknown review.method')
    try:
        stamp = dt.datetime.fromisoformat(review['reviewed_at'])
        if stamp.tzinfo is None:
            raise ValueError('timezone missing')
    except (KeyError, TypeError, ValueError):
        fail('SCHEMA', 'review.reviewed_at must be an ISO timestamp with timezone')
    global_issues = entries(review.get('issues'), 'review.issues')
    artifacts = {}
    comparisons = {}
    for item in entries(data.get('artifacts'), 'artifacts'):
        item = obj(item, 'artifact')
        key = item.get('id')
        if not isinstance(key, str) or not key.strip() or key in artifacts:
            fail('SCHEMA', 'Artifact IDs must be nonempty and unique')
        number = item.get('pdf_page')
        if type(number) is not int or not 1 <= number <= total:
            fail('SCHEMA', 'Artifact must identify a physical PDF page')
        kind = item.get('kind')
        if kind not in KINDS:
            fail('SCHEMA', 'Unknown artifact kind')
        path = file_ref(root, item, 'artifact ' + key, {'.json'} if kind == 'comparison' else {'.png', '.jpg', '.jpeg', '.webp'})
        identities[path] = item['sha256']
        if path in {source, output}:
            fail('EMPTY_EVIDENCE', 'An input/output is not independent review evidence')
        if kind == 'comparison':
            content = obj(json.loads(path.read_text()), 'comparison')
            if (type(content.get('schema_version')) is not int or content['schema_version'] != 1
                    or type(content.get('pdf_page')) is not int or content['pdf_page'] != number
                    or content.get('source_sha256') != source_meta['sha256']
                    or content.get('output_sha256') != output_meta['sha256']):
                fail('EVIDENCE_IDENTITY', 'Comparison must bind the exact PDF, saved MD and physical page')
            obj(content.get('components'), 'comparison.components')
            comparisons[key] = content
        else:
            try:
                with fitz.open(path) as image:
                    if image.is_pdf or len(image) != 1:
                        fail('INVALID_IMAGE', 'Review evidence must be an actual single image')
                    image_pixels = fitz.Pixmap(str(path))
                if kind in {'source_image', 'source_crop'}:
                    scale = item.get('render_scale')
                    if type(scale) not in (int, float) or not .25 <= scale <= 4:
                        fail('SOURCE_IMAGE_IDENTITY', 'Source image needs its real render_scale between 0.25 and 4')
                    rectangle = bounds[number-1]
                    if (rectangle[2]-rectangle[0]) * (rectangle[3]-rectangle[1]) * scale * scale > 40_000_000:
                        fail('SOURCE_IMAGE_IDENTITY', 'Source evidence render is too large; provide a bounded full-page render')
                    clip = None
                    if kind == 'source_crop':
                        box = item.get('clip')
                        if (not isinstance(box, list) or len(box) != 4
                                or not all(type(v) in (int, float) for v in box)
                                or not (rectangle[0] <= box[0] < box[2] <= rectangle[2]
                                        and rectangle[1] <= box[1] < box[3] <= rectangle[3])):
                            fail('SOURCE_IMAGE_IDENTITY', 'Source crop must identify its true in-page clip rectangle')
                        clip = fitz.Rect(box)
                    with fitz.open(source) as pdf:
                        expected_pixels = pdf[number-1].get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
                    if (image_pixels.width, image_pixels.height, image_pixels.digest) != (expected_pixels.width, expected_pixels.height, expected_pixels.digest):
                        fail('SOURCE_IMAGE_IDENTITY', 'Source image pixels do not match the stated physical PDF page/render_scale')
                elif item.get('output_sha256') != output_meta['sha256']:
                    fail('EVIDENCE_IDENTITY', 'Output render must bind the current saved Markdown hash')
            except GateError:
                raise
            except Exception:
                fail('INVALID_IMAGE', 'Image artifact cannot be decoded: ' + key)
        artifacts[key] = item
    missing = []
    page_records = entries(review.get('pages'), 'review.pages')
    nums = []
    for page in page_records:
        page = obj(page, 'review page')
        number = page.get('pdf_page')
        if type(number) is not int or number in nums or not 1 <= number <= total:
            fail('REVIEW_PAGE_COVERAGE', 'Review pages must be unique physical page numbers')
        nums.append(number)
        page_issues = entries(page.get('issues'), 'page.issues')
        if page_issues:
            missing.append(f'page {number}: open issues')
        components = obj(page.get('components'), 'page.components')
        if set(components) - set(COMPONENTS):
            fail('SCHEMA', 'Unknown content component; do not put conversion metadata here')
        for name in COMPONENTS:
            component = components.get(name)
            if component is None:
                missing.append(f'page {number}: missing {name}')
                continue
            component = obj(component, name)
            status = component.get('status')
            if status not in STATUSES:
                fail('SCHEMA', 'Unknown component review status')
            if status in {'pending', 'blocked'}:
                description(component.get('reason'), name + '.reason')
                missing.append(f'page {number}: {name} {status}')
            if status == 'not_applicable':
                description(component.get('reason'), name + '.reason')
                if name in {'reading_order', 'display'}:
                    fail('COMPONENT_COVERAGE', name + ' cannot be omitted even for a blank source page')
            refs = entries(component.get('evidence'), name + '.evidence')
            if any(not isinstance(key, str) for key in refs):
                fail('SCHEMA', 'Evidence references must be artifact ID strings')
            if len(refs) != len(set(refs)):
                fail('SCHEMA', 'Duplicate evidence references')
            kinds = set()
            compared = False
            for key in refs:
                if not isinstance(key, str) or key not in artifacts:
                    fail('MISSING_EVIDENCE', 'Unknown evidence reference')
                artifact = artifacts[key]
                if artifact['pdf_page'] != number:
                    fail('EVIDENCE_PAGE', 'Cover/mosaic evidence cannot attest a different page')
                kinds.add(artifact['kind'])
                if artifact['kind'] != 'comparison':
                    continue
                finding = obj(comparisons[key]['components'].get(name), 'comparison component ' + name)
                if finding.get('status') != status:
                    fail('EVIDENCE_STATUS', 'Manifest and comparison disagree about component status')
                description(finding.get('finding'), 'comparison finding')
                locator = obj(finding.get('source_locator'), 'source_locator')
                box = locator.get('bbox')
                if type(locator.get('pdf_page')) is not int or locator['pdf_page'] != number or not isinstance(box, list) or len(box) != 4:
                    fail('EVIDENCE_LOCATOR', 'Comparison must locate the reviewed source region')
                if not all(type(v) in (int, float) for v in box):
                    fail('EVIDENCE_LOCATOR', 'Source bbox must contain numbers')
                x0,y0,x1,y1 = bounds[number-1]
                if not (x0 <= box[0] < box[2] <= x1 and y0 <= box[1] < box[3] <= y1):
                    fail('EVIDENCE_LOCATOR', 'Source bbox is outside the physical page')
                locator = obj(finding.get('output_locator'), 'output_locator')
                excerpt = locator.get('excerpt')
                if (locator.get('anchor') != f'pdf-page-{number}' or not isinstance(excerpt, str)
                        or len(excerpt.strip()) < 4 or excerpt not in parts[number]):
                    fail('EVIDENCE_LOCATOR', 'Comparison must locate actual content in the saved MD page')
                compared = True
            if status in {'checked', 'not_applicable'} and (not REQUIRED_KINDS.issubset(kinds) or not compared):
                missing.append(f'page {number}: {name} lacks source image, output render or comparison')
    for number in range(1, total + 1):
        if number not in nums:
            missing.append(f'page {number}: no review record')
    if global_issues:
        missing.append('document: open issues')
    if review['method'] != 'full_source_comparison':
        missing.append('document: review is not a full source comparison')
    if nums != sorted(nums):
        fail('REVIEW_PAGE_COVERAGE', 'Review pages must be ordered')
    if declared == 'checked' and missing:
        fail('CHECKED_WITH_GAPS', '; '.join(missing))
    if sha(manifest_path) != manifest_digest or any(sha(path) != expected for path, expected in identities.items()):
        fail('FILES_CHANGED_DURING_REVIEW', 'Manifest, source, output or evidence changed while the gate was reading it')
    return {'gate': 'pass' if declared == 'checked' else 'partial', 'declared_review_status': declared,
            'eligible_for_checked': declared == 'checked' and not missing, 'physical_pages': total,
            'review_page_records': len(nums), 'missing': missing,
            'source_sha256': source_meta['sha256'], 'output_sha256': output_meta['sha256'],
            'semantic_truth_verified_by_gate': False,
            'scope': 'File identity, evidence structure and declared component coverage only. Evidence observations still require real source review.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--require-checked', action='store_true')
    args = parser.parse_args()
    try:
        result = validate_review(args.manifest, args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if args.require_checked and not result['eligible_for_checked'] else 0
    except (GateError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({'gate': 'reject', 'code': getattr(exc, 'code', 'INVALID_MANIFEST'),
                          'message': str(exc), 'semantic_truth_verified_by_gate': False}, ensure_ascii=False, indent=2))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
