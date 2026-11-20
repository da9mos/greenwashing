#!/usr/bin/env python3
"""Local source/evidence gate for ESG assessments; no model or network calls."""
import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

TYPES = {"обязательство", "результат", "декларация"}
VERDICTS = {"подтверждено", "декларативно", "противоречит фактам", "недостаточно данных"}
FIELDS = ["claim_id", "company", "report_id", "pdf_page", "printed_page", "quote", "claim_type", "esg_block", "verdict", "reason", "limitation", "source_url", "assessment_method"]


def source_pages(report):
    text = report.read_text(encoding="utf-8")
    return {int(m[1]): m[2] for m in re.finditer(r"<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)", text, re.S)}


def validate(data, report):
    errors = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    if data.get("schema_version") != "1.0":
        errors.append("unsupported schema_version")
    if data.get("source_sha256") != hashlib.sha256(report.read_bytes()).hexdigest():
        errors.append("source_sha256 mismatch")
    if not isinstance(data.get("report_id"), str) or not data["report_id"]:
        errors.append("report_id required")
    if not isinstance(data.get("company"), str) or not data["company"]:
        errors.append("company required")
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        return errors + ["nonempty claims array required"]
    pages = source_pages(report)
    seen = set()
    for i, claim in enumerate(claims):
        prefix = f"claim[{i}]"
        if not isinstance(claim, dict):
            errors.append(prefix + ": object required")
            continue
        def fail(message):
            errors.append(prefix + ": " + message)
        for key in FIELDS:
            if key not in claim or claim[key] in (None, ""):
                fail(key + " required")
        cid = claim.get("claim_id")
        if not isinstance(cid, str) or cid in seen:
            fail("claim_id must be a unique string")
        if isinstance(cid, str):
            seen.add(cid)
        if claim.get("company") != data.get("company") or claim.get("report_id") != data.get("report_id"):
            fail("company/report_id mismatch")
        page = claim.get("pdf_page")
        if type(page) is not int or page not in pages:
            fail("invalid physical PDF page")
        else:
            quote = claim.get("quote")
            if not isinstance(quote, str) or not quote.strip() or quote not in pages[page]:
                fail("verbatim quote absent from specified page")
        if claim.get("claim_type") not in TYPES:
            fail("invalid claim_type")
        if claim.get("verdict") not in VERDICTS:
            fail("invalid verdict")
        if claim.get("esg_block") not in {"E", "S", "G"}:
            fail("invalid esg_block")
        for key in ("reason", "limitation", "assessment_method", "source_url"):
            if not isinstance(claim.get(key), str) or not claim.get(key, "").strip():
                fail(key + " must be a nonempty string")
        if not str(claim.get("source_url", "")).startswith("https://"):
            fail("source_url must use https")
        if claim.get("verdict") == "декларативно" and claim.get("claim_type") != "декларация":
            fail("declarative verdict requires declaration type; missing evidence is not declaration")
        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list):
            fail("evidence must be an array")
            evidence = []
        decisive = claim.get("verdict") in {"подтверждено", "противоречит фактам"}
        if decisive:
            required_relation = "supports" if claim["verdict"] == "подтверждено" else "contradicts"
            qualifying = []
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                matches = all(item.get(k) == claim.get(k) and claim.get(k) for k in ("entity_scope", "metric", "period", "boundary", "assessment_target"))
                provenance = all(isinstance(item.get(k), str) and item[k].strip() for k in ("source_url", "publication_date", "event_period", "quote", "locator"))
                try:
                    date.fromisoformat(str(item.get("publication_date", "")))
                    dated = True
                except ValueError:
                    dated = False
                separate_source = str(item.get("source_url", "")).split("#")[0] != str(claim.get("source_url", "")).split("#")[0]
                if matches and provenance and dated and separate_source and item.get("independent") is True and item.get("relation") == required_relation and item.get("reviewed") is True and str(item.get("source_url", "")).startswith("https://"):
                    qualifying.append(item)
            if not qualifying:
                fail("decisive verdict needs reviewed independent evidence matching entity, metric, period, boundary and assessment target")
            relations = {item.get("relation") for item in evidence if isinstance(item, dict) and item.get("reviewed") is True}
            if {"supports", "contradicts"} <= relations and not claim.get("conflict_resolution"):
                fail("conflicting evidence needs explicit conflict_resolution")
    return errors


def prepare(report, output):
    pages = source_pages(report)
    if not pages:
        raise ValueError("report has no physical page markers")
    instruction = (Path(__file__).parent / "CLAIM_ASSESSMENT_AGENT.md").read_text(encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    (output / "prompt.md").write_text(instruction + "\n\n# Входной отчёт\n\n" + report.read_text(encoding="utf-8"), encoding="utf-8")
    (output / "input_manifest.json").write_text(json.dumps({"source_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "physical_pages": len(pages), "source": report.name, "status": "prepared_not_assessed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "prepared_not_assessed", "pages": len(pages), "output": str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Create a local LLM work packet; does not execute a model")
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    for name in ("validate", "export"):
        p = sub.add_parser(name)
        p.add_argument("--report", type=Path, required=True)
        p.add_argument("--assessment", type=Path, required=True)
        if name == "export":
            p.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.report, args.output)
        else:
            data = json.loads(args.assessment.read_text(encoding="utf-8"))
            errors = validate(data, args.report)
            result = {"status": "invalid" if errors else "valid", "claims": len(data.get("claims", [])) if isinstance(data, dict) else 0, "errors": errors, "check_scope": "source integrity and evidence contract; not independent semantic truth verification"}
            if not errors and args.command == "export":
                args.csv.parent.mkdir(parents=True, exist_ok=True)
                with args.csv.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter=";", extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(data["claims"])
                result["csv"] = str(args.csv)
            if errors:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
