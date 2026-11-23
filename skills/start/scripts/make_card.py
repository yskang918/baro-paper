#!/usr/bin/env python3
"""판단 카드 만들기: card.json → 판단카드.html (한 화면에서 읽고 결정하는 요약 + 펼쳐 보는 자료)

python make_card.py card.json -o 판단카드.html [--open]

card.json 형식은 skills/start/card_schema.md 참고. 표준 라이브러리만 사용.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import webbrowser

CSS = """
:root{--ink:#1d2430;--sub:#5b6574;--line:#e3e7ee;--bg:#ffffff;--panel:#f6f8fb;--amber:#d98a00;--amber-soft:#fff4dc;
--go:#1f7a4d;--go-soft:#e3f4ea;--fix:#b26a00;--fix-soft:#fff1d6;--stop:#b3261e;--stop-soft:#fbe5e3}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 Pretendard,"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:36px 24px 80px}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;border-bottom:2px solid var(--ink);padding-bottom:10px}
.brand{font-weight:800;letter-spacing:-.01em}.brand b{color:var(--amber)}
.meta{color:var(--sub);font-size:14px}
h1{font-size:26px;line-height:1.35;margin:22px 0 6px;letter-spacing:-.02em}
.oneline{color:var(--sub);margin:0 0 22px}
.verdict{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:center;border-radius:10px;padding:20px 22px;margin-bottom:22px}
.verdict .tag{font-size:28px;font-weight:800;letter-spacing:-.02em;white-space:nowrap}
.verdict .why{font-size:17px}
.verdict .score{color:var(--sub);font-size:14px;margin-top:4px}
.v-go{background:var(--go-soft)}.v-go .tag{color:var(--go)}
.v-fix{background:var(--fix-soft)}.v-fix .tag{color:var(--fix)}
.v-stop{background:var(--stop-soft)}.v-stop .tag{color:var(--stop)}
h2{font-size:18px;margin:30px 0 10px;letter-spacing:-.01em;display:flex;align-items:center;gap:8px}
h2:before{content:"";width:6px;height:18px;background:var(--amber);border-radius:2px}
.rq{border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:8px 0;display:grid;grid-template-columns:96px 1fr auto;gap:12px;align-items:start}
.rq .id{font-weight:800}.rq .type{color:var(--sub);font-size:13px}
.rq .ok{font-size:13px;font-weight:700;padding:2px 8px;border-radius:4px;white-space:nowrap}
.ok-yes{background:var(--go-soft);color:var(--go)}.ok-cond{background:var(--fix-soft);color:var(--fix)}.ok-no{background:var(--stop-soft);color:var(--stop)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.box{background:var(--panel);border-radius:8px;padding:14px 16px}
.box h3{margin:0 0 8px;font-size:15px}
ul.clean{margin:0;padding-left:18px}ul.clean li{margin:6px 0}
.ev{color:var(--sub);font-size:14px;display:block}
.risk{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid var(--line);border-radius:8px;margin:8px 0;overflow:hidden}
.risk div{padding:11px 14px}.risk .r{border-right:1px solid var(--line)}
.risk .f{background:var(--panel)}.risk small{display:block;color:var(--sub);font-size:12px;font-weight:700;margin-bottom:2px}
.cost{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.cost div{border:1px solid var(--line);border-radius:8px;padding:10px 12px}.cost small{color:var(--sub);display:block;font-size:13px}
.scores{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:6px 18px}
.bar{display:grid;grid-template-columns:110px 1fr 28px;gap:8px;align-items:center;font-size:14px}
.bar i{display:block;height:8px;background:var(--line);border-radius:4px;position:relative}
.bar i b{position:absolute;left:0;top:0;bottom:0;background:var(--amber);border-radius:4px}
.decide{border:2px solid var(--ink);border-radius:10px;padding:18px 20px;margin-top:30px}
.decide .opts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}
.decide .opts div{border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:14px}
.decide .opts strong{display:block;font-size:16px}
.note{color:var(--sub);font-size:14px}
details{border:1px solid var(--line);border-radius:8px;margin:8px 0;background:#fff}
summary{cursor:pointer;padding:11px 14px;font-weight:700}
details .md{padding:0 16px 14px;font-size:14px;overflow-x:auto}
.md table{border-collapse:collapse;margin:8px 0;font-size:13px}.md th,.md td{border:1px solid var(--line);padding:5px 8px;vertical-align:top}
.md th{background:var(--panel)}.md h1{font-size:18px}.md h2{font-size:16px}.md h2:before{display:none}.md h3{font-size:15px}
.md blockquote{margin:8px 0;padding:6px 12px;border-left:3px solid var(--line);color:var(--sub)}
img.chart{max-width:100%;border:1px solid var(--line);border-radius:8px}
@media (max-width:720px){.grid2,.risk,.decide .opts{grid-template-columns:1fr}.risk .r{border-right:0;border-bottom:1px solid var(--line)}.rq{grid-template-columns:1fr}}
@media print{details{break-inside:avoid}details:not([open]){display:none}}
"""


def esc(s):
    return html.escape(str(s or ""))


def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank">\1</a>', s)
    return s


def md_to_html(text):
    """간단한 Markdown → HTML (제목·표·목록·인용·문단). 자료 펼쳐 보기용."""
    out, lines, i = [], text.replace("\r\n", "\n").split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>")
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\s*\|?\s*:?-{2,}", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = "<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
            out.append(t + "</table>")
            continue
        if re.match(r"^([-*]|\d+\.)\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        if s.startswith(">"):
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip().lstrip("> "))
                i += 1
            out.append("<blockquote>" + "<br>".join(inline(x) for x in q) + "</blockquote>")
            continue
        if s.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>" + esc("\n".join(code)) + "</pre>")
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|\||[-*]\s|\d+\.\s|>|```)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def verdict_class(v):
    if "보류" in v:
        return "v-stop"
    if "진행" in v and "조건" not in v:
        return "v-go"
    return "v-fix"


def ok_class(a):
    a = str(a)
    if a.startswith("예"):
        return "ok-yes"
    if a.startswith("아니"):
        return "ok-no"
    return "ok-cond"


def build(card, base_dir):
    c = card
    P = [f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>바로논문 카드 · {esc(c.get("title"))}</title><style>{CSS}</style></head><body><div class="wrap">']
    idea = c.get("kind") == "idea"
    P.append(f'<div class="top"><div class="brand"><b>바로</b>논문 {"아이디어 카드" if idea else "판단 카드"}</div><div class="meta">{esc(c.get("date"))} · {esc(c.get("mode", "빠른 판단"))}</div></div>')
    P.append(f'<h1>{esc(c.get("title"))}</h1><p class="oneline">{inline(c.get("one_line"))}</p>')
    v = c.get("verdict", "")
    if v:
        P.append(f'<div class="verdict {verdict_class(v)}"><div class="tag">{esc(v)}</div><div><div class="why">{inline(c.get("verdict_reason"))}</div>'
             f'<div class="score">{esc(c.get("score", ""))}</div></div></div>')
    if c.get("rqs"):
        P.append("<h2>연구 질문</h2>")
        for r in c["rqs"]:
            P.append(f'<div class="rq"><div><div class="id">{esc(r.get("id"))}</div><div class="type">{esc(r.get("type"))}</div></div>'
                     f'<div>{inline(r.get("text"))}</div><div class="ok {ok_class(r.get("answerable"))}">답할 수 있나: {esc(r.get("answerable"))}</div></div>')
    if c.get("candidates"):
        P.append("<h2>아이디어 후보</h2>")
        for cd in c["candidates"]:
            sc = " · ".join(f"{k} {v}" for k, v in (cd.get("scores") or {}).items())
            P.append(f'<div class="rq"><div><div class="id">{esc(cd.get("rank"))}순위</div><div class="type">{esc(sc)}</div></div>'
                     f'<div><strong>{inline(cd.get("title"))}</strong><br>{inline(cd.get("question"))}'
                     f'<span class="ev">채우는 빈틈: {inline(cd.get("gap"))}</span><span class="ev">방법: {inline(cd.get("method"))}</span>'
                     f'<span class="ev">걸림돌: {inline(cd.get("risk"))}</span></div>'
                     f'<div class="ok {ok_class(cd.get("feasible", "조건부"))}">실행: {esc(cd.get("feasible", ""))}</div></div>')
    if c.get("why") or c.get("todo_before"):
        P.append('<div class="grid2">')
        P.append('<div class="box"><h3>왜 해 볼 만한가</h3><ul class="clean">' + "".join(
        f'<li>{inline(w.get("point"))}<span class="ev">{inline(w.get("evidence"))}</span></li>' for w in c.get("why", [])) + "</ul></div>")
        P.append(f'<div class="box"><h3>{"고르기 전에 볼 것" if idea else "결정 전에 할 일"}</h3><ul class="clean">' + "".join(
            f"<li>{inline(t)}</li>" for t in c.get("todo_before", [])) + "</ul></div></div>")
    if c.get("risks"):
        P.append("<h2>가장 큰 걸림돌</h2>")
        for r in c["risks"]:
            P.append(f'<div class="risk"><div class="r"><small>걸림돌</small>{inline(r.get("risk"))}</div>'
                     f'<div class="f"><small>이렇게 하면 풀림</small>{inline(r.get("fix"))}</div></div>')
    if c.get("cost"):
        P.append('<h2>하면 드는 것</h2><div class="cost">' + "".join(
            f'<div><small>{esc(x.get("label"))}</small>{inline(x.get("value"))}</div>' for x in c["cost"]) + "</div>")
    for ch in c.get("charts", []):
        p = ch.get("path", "")
        P.append(f'<h2>{esc(ch.get("title", "그래프"))}</h2><img class="chart" src="{esc(p)}" alt="{esc(ch.get("title", ""))}">')
    if c.get("scores"):
        P.append('<h2>기준별 점수</h2><div class="scores">' + "".join(
            f'<div class="bar"><span>{esc(s.get("name"))}</span><i><b style="width:{int(float(s.get("score", 0)) * 20)}%"></b></i><span>{esc(s.get("score"))}</span></div>'
            for s in c["scores"]) + "</div>")
    if c.get("unverified"):
        P.append('<h2>확인하지 못한 것</h2><ul class="clean">' + "".join(f"<li>{inline(u)}</li>" for u in c["unverified"]) + "</ul>")
    if idea:
        P.append('<div class="decide"><strong>Claude Code 대화창에서 후보를 골라 주세요.</strong>'
                 '<div class="opts"><div><strong>후보 고르기</strong>1~2개를 골라 연구 판단으로 넘어감</div><div><strong>섞거나 고치기</strong>후보를 합치거나 바꿔서</div>'
                 '<div><strong>다시 찾기</strong>다른 키워드로 한 번 더</div></div></div>')
    else:
        P.append('<div class="decide"><strong>결정은 Claude Code 대화창에서 골라 주세요.</strong>'
                 '<div class="opts"><div><strong>진행</strong>계획서 쓰기로 넘어감</div><div><strong>고쳐서 다시</strong>고칠 점을 반영해 다시 판단</div>'
                 '<div><strong>보류</strong>여기서 멈추고 기록만 남김</div></div></div>')
    if c.get("files"):
        P.append('<h2>자세한 자료 (눌러서 펼치기)</h2>')
        for f in c["files"]:
            fp = os.path.join(base_dir, f["path"])
            body = md_to_html(open(fp, encoding="utf-8").read()) if os.path.exists(fp) else f'<p class="note">파일 없음: {esc(f["path"])}</p>'
            P.append(f'<details><summary>{esc(f.get("label"))}</summary><div class="md">{body}</div></details>')
    P.append('<p class="note" style="margin-top:28px">이 카드는 바로논문(baro-paper)이 만들었습니다. 숫자와 인용은 문헌 목록에서 확인된 것만 씁니다.</p></div></body></html>')
    return "\n".join(P)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("card")
    ap.add_argument("-o", required=True)
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    card = json.load(open(a.card, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(a.o))
    open(a.o, "w", encoding="utf-8").write(build(card, base))
    if a.open:
        p = os.path.abspath(a.o)
        try:
            if os.name == "nt":
                os.startfile(p)
            elif sys.platform == "darwin":
                subprocess.run(["open", p])
            else:
                webbrowser.open("file://" + p)
        except Exception:
            webbrowser.open("file://" + p)
    print(json.dumps({"card": os.path.abspath(a.o)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
