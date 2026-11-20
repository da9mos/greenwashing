"""Do not invoke the native PDF library from controller network threads."""
import sys
import run_models as rm

if __name__ == '__main__':
    rows = [r for r in rm.ROWS if r['report_id'] == sys.argv[1]]
    if len(rows) != 1:
        raise SystemExit('Unknown report ID')
    result = rm.page_inputs(rows[0])
    print(result['report_id'], len(result['pages']))
