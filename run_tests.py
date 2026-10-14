"""Run pytest and write test_report.json."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

subprocess.run([sys.executable, "-m", "pytest", "-q", "--junitxml=.junit.xml"], check=False)
root = ET.parse(".junit.xml").getroot()
suite = root if root.tag == "testsuite" else root.find("testsuite")
errors, failed = [], 0
for case in suite.iter("testcase"):
    for bad in list(case.findall("failure")) + list(case.findall("error")):
        failed += 1
        errors.append({"file": case.get("file") or case.get("classname", ""),
                       "line": int(case.get("line") or 0),
                       "message": (bad.get("message") or "")[:500]})
total = int(suite.get("tests")) - int(suite.get("skipped", 0))
report = {"status": "PASS" if failed == 0 else "FAIL", "passed": total - failed, "failed": failed, "errors": errors}
with open("test_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False))
