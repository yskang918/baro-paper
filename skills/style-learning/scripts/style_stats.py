#!/usr/bin/env python3
"""문체 수치 분석: 문장 길이, 끝맺음, 연결어, 자주 쓰는 표현, 인용 방식, 대화 기록의 고침 지시.

python style_stats.py 파일... -o 결과.json
지원: .hwpx .md .txt .jsonl(Claude Code 대화) / .docx .pdf .pptx 는 markitdown이 있으면 읽음
"""
import argparse
import collections
import html
import json
import os
import re
import sys
import zipfile

ENDINGS = ["하였다", "했다", "한다", "하다", "이다", "였다", "있다", "없다", "된다", "되었다", "것이다", "보인다",
           "나타났다", "확인하였다", "확인했다", "할 수 있다", "볼 수 있다", "판단된다", "생각된다", "필요하다", "함", "음", "임"]
CONNECTIVES = ["그러나", "하지만", "따라서", "그러므로", "즉", "또한", "한편", "특히", "이처럼", "이와 같이", "그리고",
               "반면", "더불어", "나아가", "다시 말해", "결국", "이에", "그런데", "아울러", "먼저", "다음으로", "마지막으로"]
SELF = ["연구자", "본 연구", "이 연구", "필자", "우리는", "나는"]
WATCH = ["되어진", "에 있어서", "를 통해", "을 통해", "라고 할 수 있다", "중요한 역할", "다양한", "매우", "획기적"]
CORR = re.compile(r"(말고|대신|바꿔|고쳐|빼|지워|하지 ?마|쓰지 ?마|어색|이상해|틀렸|아니라|로 해|로 써|처럼 써|금지|싫어)")


def read_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".hwpx":
        out = []
        with zipfile.ZipFile(path) as z:
            for n in sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml", n)):
                s = z.read(n).decode("utf-8")
                for p in re.findall(r"<hp:p\b.*?</hp:p>", s, re.S):
                    t = "".join(re.findall(r"<hp:t>(.*?)</hp:t>", p, re.S))
                    t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
                    if t:
                        out.append(t)
        return "\n".join(out), []
    if ext in (".md", ".txt"):
        return open(path, encoding="utf-8", errors="replace").read(), []
    if ext == ".jsonl":
        return read_chat(path)
    try:
        from markitdown import MarkItDown
        return MarkItDown().convert(path).text_content, []
    except Exception as e:
        raise SystemExit(f"{path}: 읽지 못함({e}). hwp는 hwpx로 바꿔서 넣으세요.")


def read_chat(path):
    """Claude Code 대화 기록: 사용자 메시지에서 고침 지시만 뽑는다. 문체 근거(본문)로는 쓰지 않는다."""
    corrections = []
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "user":
            continue
        msg = d.get("message", {})
        content = msg.get("content")
        texts = [content] if isinstance(content, str) else [c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text"]
        for t in texts:
            t = t.strip()
            if not t or t.startswith("<") or len(t) > 600:
                continue
            if CORR.search(t):
                corrections.append({"when": d.get("timestamp", ""), "text": t[:300]})
    return "", corrections


def sentences(text):
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[다음임함요])[.?!]\s+|(?<=[.?!])\s+(?=[가-힣A-Z])", text)
    return [p.strip() for p in parts if len(p.strip()) >= 8 and re.search(r"[가-힣]", p)]


def analyze(texts):
    sents = [s for t in texts for s in sentences(t)]
    lens = sorted(len(s) for s in sents)
    end_c = collections.Counter()
    for s in sents:
        s2 = s.rstrip(".?! )\"'")
        for e in sorted(ENDINGS, key=len, reverse=True):
            if s2.endswith(e):
                end_c[e] += 1
                break
        else:
            end_c["기타"] += 1
    body = "\n".join(texts)
    first = collections.Counter()
    for s in sents:
        for c in CONNECTIVES:
            if s.startswith(c):
                first[c] += 1
    conn = {c: body.count(c) for c in CONNECTIVES if body.count(c)}
    words = re.findall(r"[가-힣A-Za-z]+", body)
    grams = collections.Counter(" ".join(words[i:i + n]) for n in (2, 3) for i in range(len(words) - n + 1))
    cite_paren = len(re.findall(r"\([^()]{1,60}?,\s*(19|20)\d{2}[a-z]?(,\s*p+\.\s*\d+)?\)", body))
    cite_narr = len(re.findall(r"[가-힣A-Za-z]+(?: 외| et al\.)?\((19|20)\d{2}\)", body))
    n = len(sents) or 1
    return {
        "sentences": len(sents),
        "sentence_length": {"mean": round(sum(lens) / n, 1) if lens else 0,
                            "median": lens[len(lens) // 2] if lens else 0,
                            "p90": lens[int(len(lens) * 0.9)] if lens else 0},
        "endings_pct": {k: round(v * 100 / n, 1) for k, v in end_c.most_common(12)},
        "sentence_initial_connectives": dict(first.most_common(10)),
        "connective_counts": dict(sorted(conn.items(), key=lambda x: -x[1])[:15]),
        "self_reference": {w: body.count(w) for w in SELF if body.count(w)},
        "watch_expressions": {w: body.count(w) for w in WATCH if body.count(w)},
        "citations": {"parenthetical": cite_paren, "narrative": cite_narr},
        "english_in_parens": len(re.findall(r"\([A-Za-z][A-Za-z \-]{2,40}\)", body)),
        "frequent_phrases": [g for g, c in grams.most_common(60) if c >= 3][:30],
        "example_sentences": [s for s in sents if 30 <= len(s) <= 120][:12],
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", required=True)
    a = ap.parse_args()
    texts, corrections, used = [], [], []
    for f in a.files:
        t, c = read_text(f)
        if t.strip():
            texts.append(t)
        corrections += c
        used.append({"file": os.path.basename(f), "chars": len(t), "corrections": len(c)})
    res = {"files": used, **analyze(texts), "corrections": corrections[:200]}
    json.dump(res, open(a.o, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"out": a.o, "sentences": res["sentences"], "corrections": len(corrections),
                      "top_endings": list(res["endings_pct"].items())[:5]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
