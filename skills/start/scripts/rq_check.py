#!/usr/bin/env python3
"""RQ 일관성 검사: 02_RQ대응표.md의 RQ 문장이 다른 파일들에 글자 그대로 들어 있는지 본다.

python rq_check.py 02_RQ대응표.md 다른파일.md [다른파일.md ...]
- RQ 문장은 대응표의 '## RQn. 문장' 줄에서 읽는다.
- 다른 파일에서 'RQn'이 나오는데 문장이 다르면 '다름', 'RQn'이 아예 없으면 '없음'으로 알린다.
- 대응표에 없는 RQ 번호(예: RQ5)가 다른 파일에 나오면 알린다.
"""
import json
import re
import sys


def norm(s):
    return re.sub(r"[\s*_`'\"‘’“”]+", "", s)


def load_rqs(path):
    rqs = {}
    for ln in open(path, encoding="utf-8"):
        m = re.match(r"^#{2,4}\s*(RQ\d+)\.\s*(.+?)\s*$", ln.strip())
        if m:
            rqs[m.group(1)] = m.group(2).strip()
    return rqs


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    base, others = sys.argv[1], sys.argv[2:]
    rqs = load_rqs(base)
    if not rqs:
        print(json.dumps({"ok": False, "message": "대응표에서 '## RQ1. 문장' 형식의 줄을 찾지 못함"}, ensure_ascii=False))
        sys.exit(1)
    report, ok = [], True
    for f in others:
        try:
            text = open(f, encoding="utf-8").read()
        except FileNotFoundError:
            report.append({"file": f, "problem": "파일 없음"})
            ok = False
            continue
        nt = norm(text)
        for rid, sent in rqs.items():
            if norm(sent) in nt:
                continue
            if re.search(r"\b" + rid + r"\b", text):
                report.append({"file": f, "rq": rid, "problem": "문장이 대응표와 다름", "대응표": sent})
            else:
                report.append({"file": f, "rq": rid, "problem": "RQ가 나오지 않음(이 파일에 필요 없으면 무시)"})
            ok = False
        extra = sorted(set(re.findall(r"\bRQ\d+\b", text)) - set(rqs))
        if extra:
            report.append({"file": f, "problem": f"대응표에 없는 RQ 번호: {', '.join(extra)}"})
            ok = False
    print(json.dumps({"ok": ok, "rqs": rqs, "problems": report}, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
