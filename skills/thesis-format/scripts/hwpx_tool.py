#!/usr/bin/env python3
"""바로논문 양식 도구: 받은 견본 hwpx의 서식을 그대로 읽고, 그 서식으로 원고를 조판하고, 맞게 됐는지 대조한다.

하위 명령
  profile  견본.hwpx -o profile.json [--md 요약.md]   견본의 쪽·글꼴·문단·스타일 값을 그대로 추출 + 역할 추천
  build    --template 견본.hwpx --map map.json --md 원고.md -o 결과.hwpx
  verify   --template 견본.hwpx --map map.json --out 결과.hwpx [--md 원고.md] [-o 보고서.md]
  render   결과.hwpx --out-dir 폴더   (Windows + 한글 + 보안모듈 필요: PDF와 쪽 PNG)
  convert  양식.hwp -o 양식.hwpx       (Windows + 한글: hwp를 hwpx로)

표준 라이브러리만 사용(render의 PNG 변환만 PyMuPDF 사용). 단위: HWPUNIT 1pt=100, 1mm≈283.465.
"""
import argparse
import copy
import html
import json
import os
import re
import shutil
import struct
import sys
import zipfile

HU_PER_MM = 7200 / 25.4  # 283.4646

ROLES = {
    "title": "논문 제목",
    "chapter": "장 제목 (# , 예: Ⅰ. 서론)",
    "section": "절 제목 (## , 예: 1. 연구의 필요성)",
    "subsection": "항 제목 (### , 예: 가. ...)",
    "subsubsection": "목 제목 (#### , 예: 1) ...)",
    "body": "본문 문단",
    "list": "목록 항목 (- 또는 1.)",
    "quote": "인용·예시 (> )",
    "table_caption": "표 제목 (<표 Ⅱ-1> ...)",
    "figure_caption": "그림 제목 ([그림 Ⅱ-1] ...)",
    "table_cell": "표 안 글자",
    "table_para": "표를 담는 문단(보통 가운데 정렬)",
    "figure_para": "그림을 담는 문단(보통 가운데 정렬)",
    "reference": "참고문헌 항목",
    "note": "표·그림 아래 주석/출처",
}


def mm(hu):
    return round(int(hu) / HU_PER_MM, 1)


def pt(hu):
    return round(int(hu) / 100, 1)


# ---------------------------------------------------------------- 패키지 읽기
class Hwpx:
    def __init__(self, path):
        self.path = path
        with zipfile.ZipFile(path) as z:
            self.infos = z.infolist()
            self.files = {i.filename: z.read(i.filename) for i in self.infos}
        self.header = self.files["Contents/header.xml"].decode("utf-8")
        self.sections = sorted([n for n in self.files if re.match(r"Contents/section\d+\.xml$", n)],
                               key=lambda n: int(re.findall(r"\d+", n)[-1]))

    def section(self, i=0):
        return self.files[self.sections[i]].decode("utf-8")

    def save(self, out):
        tmp = out + ".tmp"
        with zipfile.ZipFile(tmp, "w") as z:
            names = list(self.files)
            if "mimetype" in names:  # mimetype은 맨 앞, 무압축
                z.writestr(zipfile.ZipInfo("mimetype"), self.files["mimetype"], compress_type=zipfile.ZIP_STORED)
            for n in names:
                if n == "mimetype":
                    continue
                z.writestr(n, self.files[n], compress_type=zipfile.ZIP_DEFLATED)
        os.replace(tmp, out)


def attr(tag, name, default=""):
    m = re.search(r'\b' + name + r'="([^"]*)"', tag)
    return m.group(1) if m else default


# ---------------------------------------------------------------- 헤더 해석
def parse_header(h):
    fonts = {}
    for ff in re.finditer(r'<hh:fontface lang="(\w+)"[^>]*>(.*?)</hh:fontface>', h, re.S):
        fonts[ff.group(1)] = {attr(f, "id"): attr(f, "face") for f in re.findall(r"<hh:font [^>]*>", ff.group(2))}
    chars = {}
    for m in re.finditer(r'(<hh:charPr id="(\d+)"[^>]*>)(.*?)</hh:charPr>', h, re.S):
        open_tag, cid, body = m.group(1), m.group(2), m.group(3)
        fr = re.search(r"<hh:fontRef [^>]*>", body)
        ratio = re.search(r"<hh:ratio [^>]*>", body)
        spacing = re.search(r"<hh:spacing [^>]*>", body)
        ul = re.search(r"<hh:underline [^>]*>", body)
        chars[cid] = {
            "size_pt": pt(attr(open_tag, "height", "1000")),
            "font_hangul": fonts.get("HANGUL", {}).get(attr(fr.group(0), "hangul"), "") if fr else "",
            "font_latin": fonts.get("LATIN", {}).get(attr(fr.group(0), "latin"), "") if fr else "",
            "bold": "<hh:bold" in body,
            "italic": "<hh:italic" in body,
            "underline": attr(ul.group(0), "type", "NONE") if ul else "NONE",
            "color": attr(open_tag, "textColor", "#000000"),
            "ratio_pct": int(attr(ratio.group(0), "hangul", "100")) if ratio else 100,
            "spacing_pct": int(attr(spacing.group(0), "hangul", "0")) if spacing else 0,
        }
    paras = {}
    for m in re.finditer(r'(<hh:paraPr id="(\d+)"[^>]*>)(.*?)</hh:paraPr>', h, re.S):
        pid, body = m.group(2), m.group(3)
        # 새 한글은 hp:case(HwpUnitChar) 값을 쓴다. 없으면 바로 적힌 값.
        case = re.search(r"<hp:case[^>]*>(.*?)</hp:case>", body, re.S)
        src = case.group(1) if case else body
        def mv(tag):
            x = re.search(r"<hc:" + tag + r' value="(-?\d+)"', src)
            return pt(x.group(1)) if x else 0.0
        ls = re.search(r"<hh:lineSpacing [^>]*>", src)
        al = re.search(r"<hh:align [^>]*>", body)
        bs = re.search(r"<hh:breakSetting [^>]*>", body)
        hd = re.search(r"<hh:heading [^>]*>", body)
        paras[pid] = {
            "align": attr(al.group(0), "horizontal") if al else "",
            "line_spacing_type": attr(ls.group(0), "type") if ls else "",
            "line_spacing": int(attr(ls.group(0), "value", "0")) if ls else 0,
            "indent_pt": mv("intent"), "left_pt": mv("left"), "right_pt": mv("right"),
            "space_before_pt": mv("prev"), "space_after_pt": mv("next"),
            "page_break_before": attr(bs.group(0), "pageBreakBefore") == "1" if bs else False,
            "keep_with_next": attr(bs.group(0), "keepWithNext") == "1" if bs else False,
            "heading": attr(hd.group(0), "type", "NONE") if hd else "NONE",
        }
    styles = {}
    for s in re.findall(r"<hh:style [^>]*>", h):
        styles[attr(s, "id")] = {"name": attr(s, "name"), "eng": attr(s, "engName"), "type": attr(s, "type"),
                                 "paraPr": attr(s, "paraPrIDRef"), "charPr": attr(s, "charPrIDRef")}
    borders = {}
    for m in re.finditer(r'<hh:borderFill id="(\d+)"[^>]*>(.*?)</hh:borderFill>', h, re.S):
        sides = {side: attr(re.search(r"<hh:" + side + r"Border [^>]*>", m.group(2)).group(0), "type")
                 for side in ("left", "right", "top", "bottom") if re.search(r"<hh:" + side + r"Border ", m.group(2))}
        borders[m.group(1)] = sides
    return {"fonts": fonts, "charPr": chars, "paraPr": paras, "styles": styles, "borderFill": borders}


# ---------------------------------------------------------------- 문단 나누기
P_TOKEN = re.compile(r"<hp:p\b[^>]*?(/?)>|</hp:p>")


def top_paragraphs(sec):
    """섹션의 최상위 문단 (시작, 끝) 위치 목록. 표 안 문단은 포함하지 않는다."""
    out, depth, start = [], 0, None
    for m in P_TOKEN.finditer(sec):
        tok = m.group(0)
        if tok.startswith("</"):
            depth -= 1
            if depth == 0 and start is not None:
                out.append((start, m.end()))
                start = None
        elif m.group(1) == "/":
            if depth == 0:
                out.append((m.start(), m.end()))
        else:
            if depth == 0:
                start = m.start()
            depth += 1
    return out


def para_text(p):
    p = re.sub(r"<hp:tbl\b.*?</hp:tbl>", "", p, flags=re.S)
    parts = re.findall(r"<hp:t>(.*?)</hp:t>|<hp:t/>", p, re.S)
    txt = "".join(re.sub(r"<[^>]+>", "", x) for x in parts)
    return html.unescape(txt).strip()


def para_char_ids(p):
    p2 = re.sub(r"<hp:tbl\b.*?</hp:tbl>", "", p, flags=re.S)
    ids = []
    for m in re.finditer(r'<hp:run charPrIDRef="(\d+)"[^>]*>(.*?)</hp:run>', p2, re.S):
        if "<hp:t>" in m.group(2):
            ids.append(m.group(1))
    return ids


# ---------------------------------------------------------------- profile
PATTERNS = [
    ("chapter", re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.．]\s*\S")),
    ("chapter", re.compile(r"^제\s*\d+\s*장")),
    ("section", re.compile(r"^\d+\s*[.．]\s*\S")),
    ("subsection", re.compile(r"^[가나다라마바사아자차카타파하]\s*[.．]\s*\S")),
    ("subsubsection", re.compile(r"^\d+\)\s*\S|^\(\d+\)\s*\S")),
    ("table_caption", re.compile(r"^<\s*표\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d]+[-–.]?\d*\s*>|^\[?\s*표\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d]+[-–]\d+")),
    ("figure_caption", re.compile(r"^[\[<]\s*그림\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d]+[-–.]?\d*\s*[\]>]|^그림\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d]+[-–]\d+")),
    ("reference", re.compile(r"\(\s*(19|20)\d{2}[a-z]?\s*\)\s*[.．]")),
]


def profile(path, sec_index=0):
    hw = Hwpx(path)
    hd = parse_header(hw.header)
    sec = hw.section(sec_index)
    pages = []
    for sp in re.finditer(r"<hp:pagePr [^>]*>\s*<hp:margin [^>]*>", sec):
        t = sp.group(0)
        pages.append({
            "paper_mm": [mm(attr(t, "width")), mm(attr(t, "height"))],
            "orientation": "가로" if attr(t, "landscape") == "NARROWLY" else "세로",
            "margin_mm": {k: mm(attr(t.split("<hp:margin")[1], k, "0")) for k in
                          ("top", "bottom", "left", "right", "header", "footer", "gutter")},
            "gutter_type": attr(t, "gutterType"),
        })
    page_num = [{"pos": attr(x, "pos"), "format": attr(x, "formatType"), "side": attr(x, "sideChar")}
                for x in re.findall(r"<hp:pageNum [^>]*>", sec)]
    combos = {}
    for (a, b) in top_paragraphs(sec):
        p = sec[a:b]
        tag = re.match(r"<hp:p [^>]*>", p).group(0)
        txt = para_text(p)
        if not txt:
            continue
        cids = para_char_ids(p)
        main_c = max(set(cids), key=cids.count) if cids else ""
        key = f'{attr(tag, "styleIDRef")}|{attr(tag, "paraPrIDRef")}|{main_c}'
        c = combos.setdefault(key, {"style": attr(tag, "styleIDRef"), "paraPr": attr(tag, "paraPrIDRef"),
                                    "charPr": main_c, "count": 0, "samples": [], "lengths": [], "guess": {}})
        c["count"] += 1
        c["lengths"].append(len(txt))
        if len(c["samples"]) < 4:
            c["samples"].append(txt[:70])
        for role, rx in PATTERNS:
            if rx.search(txt) and (role != "reference" or len(txt) > 30):
                c["guess"][role] = c["guess"].get(role, 0) + 1
                break
    combo_list = []
    for k, c in combos.items():
        L = c.pop("lengths")
        c["avg_len"] = round(sum(L) / len(L), 1)
        c["style_name"] = hd["styles"].get(c["style"], {}).get("name", "")
        c["para"] = hd["paraPr"].get(c["paraPr"], {})
        c["char"] = hd["charPr"].get(c["charPr"], {})
        combo_list.append(c)
    combo_list.sort(key=lambda c: -c["count"])
    tables = []
    for t in re.finditer(r"<hp:tbl [^>]*>", sec):
        tables.append({"rows": attr(t.group(0), "rowCnt"), "cols": attr(t.group(0), "colCnt"),
                       "borderFill": attr(t.group(0), "borderFillIDRef")})
    prof = {
        "source": os.path.basename(path), "section_index": sec_index, "sections": len(hw.sections),
        "pages": pages, "page_number": page_num,
        "has_header_ctrl": "<hp:header " in sec, "has_footer_ctrl": "<hp:footer " in sec,
        "styles": {sid: {**s, "para": hd["paraPr"].get(s["paraPr"], {}), "char": hd["charPr"].get(s["charPr"], {})}
                   for sid, s in hd["styles"].items()},
        "paragraph_formats": combo_list[:60],
        "tables": tables[:20], "table_count": len(tables),
        "picture_count": len(re.findall(r"<hp:pic ", sec)),
        "suggested_map": suggest_map(combo_list),
    }
    return prof


def suggest_map(combos):
    """서식 조합마다 표본 글을 보고 역할을 추천한다. 확정은 사람이 한다."""
    m = {}
    scored = {}
    for c in combos:
        for role, n in c["guess"].items():
            if n / c["count"] >= 0.5:
                if role not in scored or n > scored[role][0]:
                    scored[role] = (n, c)
    for role, (n, c) in scored.items():
        m[role] = {"style": c["style"], "paraPr": c["paraPr"], "charPr": c["charPr"],
                   "why": f"표본 {c['count']}개 중 {n}개가 {ROLES[role]} 모양", "samples": c["samples"][:2]}
    body = [c for c in combos if c["avg_len"] > 60 and not c["guess"]]
    if body:
        c = max(body, key=lambda c: c["count"] * c["avg_len"])
        m["body"] = {"style": c["style"], "paraPr": c["paraPr"], "charPr": c["charPr"],
                     "why": f"긴 문단 {c['count']}개(평균 {c['avg_len']}자)", "samples": c["samples"][:2]}
    return m


def profile_md(p):
    L = [f"# 양식 분석: {p['source']}", ""]
    for i, pg in enumerate(p["pages"]):
        mg = pg["margin_mm"]
        L.append(f"- 쪽 {i+1}: 용지 {pg['paper_mm'][0]}×{pg['paper_mm'][1]}mm {pg['orientation']}, "
                 f"여백 위 {mg['top']} 아래 {mg['bottom']} 왼쪽 {mg['left']} 오른쪽 {mg['right']} "
                 f"머리말 {mg['header']} 꼬리말 {mg['footer']} 제본 {mg['gutter']}mm")
    for pn in p["page_number"]:
        L.append(f"- 쪽번호: 위치 {pn['pos']}, 형식 {pn['format']}, 옆 문자 '{pn['side']}'")
    L += ["", "## 스타일(견본에 이름이 붙은 문단 모양)", "",
          "| id | 이름 | 글꼴 | 크기 | 굵게 | 정렬 | 줄간격 | 들여쓰기 | 위/아래 간격 |", "|---|---|---|---|---|---|---|---|---|"]
    for sid, s in p["styles"].items():
        c, a = s["char"], s["para"]
        L.append(f"| {sid} | {s['name']} | {c.get('font_hangul','')} | {c.get('size_pt','')}pt | {'예' if c.get('bold') else ''} | "
                 f"{a.get('align','')} | {a.get('line_spacing','')}{'%' if a.get('line_spacing_type')=='PERCENT' else ''} | "
                 f"{a.get('indent_pt','')}pt | {a.get('space_before_pt','')}/{a.get('space_after_pt','')}pt |")
    L += ["", "## 실제로 쓰인 문단 서식 (많이 쓰인 순)", "",
          "| # | 스타일 | 문단 | 글자 | 개수 | 글꼴·크기 | 정렬·줄간격 | 표본 |", "|---|---|---|---|---|---|---|---|"]
    for i, c in enumerate(p["paragraph_formats"][:30]):
        ch, pa = c["char"], c["para"]
        L.append(f"| {i} | {c['style']} {c['style_name']} | {c['paraPr']} | {c['charPr']} | {c['count']} | "
                 f"{ch.get('font_hangul','')} {ch.get('size_pt','')}pt{' 굵게' if ch.get('bold') else ''} | "
                 f"{pa.get('align','')} {pa.get('line_spacing','')} | {' / '.join(s[:30] for s in c['samples'][:2])} |")
    L += ["", "## 역할 추천 (사람이 확인해서 map.json으로 확정)", ""]
    for role, v in p["suggested_map"].items():
        L.append(f"- {role} ({ROLES.get(role,'')}): 스타일 {v['style']} · 문단 {v['paraPr']} · 글자 {v['charPr']} — {v['why']} — 예: {v['samples'][0][:40] if v['samples'] else ''}")
    missing = [r for r in ROLES if r not in p["suggested_map"]]
    L += ["", "추천하지 못한 역할: " + ", ".join(missing), ""]
    L.append(f"표 {p['table_count']}개, 그림 {p['picture_count']}개, 섹션 {p['sections']}개(분석한 섹션 {p['section_index']}).")
    return "\n".join(L)


# ---------------------------------------------------------------- 원고(md) 읽기
def parse_md(text):
    blocks, para, lines = [], [], text.replace("\r\n", "\n").split("\n")
    def flush():
        if para:
            blocks.append(("body", " ".join(x.strip() for x in para)))
            para.clear()
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flush(); i += 1; continue
        if s in ("<!-- pagebreak -->", "\\newpage", "<!-- 쪽나눔 -->"):
            flush(); blocks.append(("pagebreak", "")); i += 1; continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            flush()
            blocks.append((["chapter", "section", "subsection", "subsubsection"][len(m.group(1)) - 1], m.group(2).strip()))
            i += 1; continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\s*\|?\s*:?-{2,}", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append(("table", rows)); continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)", s)
        if m:
            flush(); blocks.append(("image", {"caption": m.group(1), "path": m.group(2)})); i += 1; continue
        role = None
        for r, rx in PATTERNS[5:7]:
            if rx.search(s):
                role = r
        if role:
            flush(); blocks.append((role, s)); i += 1; continue
        if s.startswith(">"):
            flush(); blocks.append(("quote", s.lstrip("> ").strip())); i += 1; continue
        if re.match(r"^[-*•]\s+", s):
            flush(); blocks.append(("list", s)); i += 1; continue
        if s.startswith("[참고문헌]") or s.startswith("[ref]"):
            flush(); blocks.append(("reference", s.split("]", 1)[1].strip())); i += 1; continue
        if s.startswith("(주)") or s.startswith("주.") or s.startswith("출처:") or s.startswith("※"):
            flush(); blocks.append(("note", s)); i += 1; continue
        para.append(ln)
        i += 1
    flush()
    # '참고문헌' 장 아래 문단은 참고문헌 항목으로
    out, in_ref = [], False
    for kind, val in blocks:
        if kind in ("chapter", "section") and isinstance(val, str):
            in_ref = bool(re.search(r"참고\s*문헌|References", val))
        elif in_ref and kind == "body":
            kind = "reference"
        out.append((kind, val))
    return out


# ---------------------------------------------------------------- 조판
def esc(s):
    return html.escape(s, quote=False)


class Builder:
    def __init__(self, tpl, mapping, sec_index=0):
        self.hw = Hwpx(tpl)
        self.map = mapping
        self.hd = parse_header(self.hw.header)
        self.sec_index = sec_index
        self.sec = self.hw.section(sec_index)
        self.warn = []
        self.warned = set()
        self.next_id = 1000000
        self.bold_cache = {}
        self.pic_count = 0
        sp = re.search(r"<hp:pagePr [^>]*>\s*<hp:margin [^>]*>", self.sec).group(0)
        mg = sp.split("<hp:margin")[1]
        w = int(attr(sp, "width")) if attr(sp, "landscape") != "NARROWLY" else int(attr(sp, "height"))
        self.text_width = w - int(attr(mg, "left")) - int(attr(mg, "right")) - int(attr(mg, "gutter", "0"))

    FALLBACK = {"subsubsection": "subsection", "subsection": "section", "section": "chapter",
                "title": "chapter", "table_caption": "body", "figure_caption": "table_caption",
                "list": "body", "quote": "body", "reference": "body", "note": "body",
                "table_para": "figure_para", "figure_para": "body", "table_cell": "body"}

    def role(self, r, fallback=None):
        chain, x = [r], r
        while x in self.FALLBACK and x not in self.map:
            x = self.FALLBACK[x]
            chain.append(x)
        if fallback and x not in self.map:
            x = fallback
        v = self.map.get(x) or {}
        if not v:
            raise SystemExit(f"map.json에 '{r}' 역할(대신 쓸 '{x}' 포함)이 없습니다.")
        if x != r and r not in self.warned:
            self.warned.add(r)
            self.warn.append(f"'{r}' 역할이 map에 없어 '{x}' 서식으로 넣음")
        if "style_name" in v and "style" not in v:
            sid = next((k for k, s in self.hd["styles"].items() if s["name"] == v["style_name"]), None)
            if sid is None:
                raise SystemExit(f"견본에 '{v['style_name']}' 스타일이 없습니다.")
            st = self.hd["styles"][sid]
            v = {"style": sid, "paraPr": v.get("paraPr", st["paraPr"]), "charPr": v.get("charPr", st["charPr"]), **v}
        if "style" in v and ("paraPr" not in v or "charPr" not in v):
            st = self.hd["styles"][str(v["style"])]
            v = {"paraPr": st["paraPr"], "charPr": st["charPr"], **v}
        return {"style": str(v.get("style", "0")), "paraPr": str(v["paraPr"]), "charPr": str(v["charPr"])}

    def nid(self):
        self.next_id += 1
        return str(self.next_id)

    # 굵게: 같은 글자 모양에 굵게만 더한 글자 모양을 찾거나 만든다
    def bold_of(self, cid):
        if cid in self.bold_cache:
            return self.bold_cache[cid]
        base = self.hd["charPr"][cid]
        if base["bold"]:
            self.bold_cache[cid] = cid
            return cid
        for k, c in self.hd["charPr"].items():
            if c["bold"] and all(c[x] == base[x] for x in ("size_pt", "font_hangul", "font_latin", "italic", "color", "ratio_pct", "spacing_pct")):
                self.bold_cache[cid] = k
                return k
        m = re.search(r'<hh:charPr id="' + cid + r'".*?</hh:charPr>', self.hw.header, re.S).group(0)
        new_id = str(max(int(k) for k in self.hd["charPr"]) + 1)
        new = re.sub(r'id="\d+"', f'id="{new_id}"', m, count=1)
        new = re.sub(r"(<hh:offset [^>]*/>)", r"\1<hh:bold/>", new, count=1)
        self.hw.header = re.sub(r"(</hh:charProperties>)", new + r"\1", self.hw.header, count=1)
        self.hw.header = re.sub(r'(<hh:charProperties itemCnt=")(\d+)', lambda x: x.group(1) + str(int(x.group(2)) + 1), self.hw.header, count=1)
        self.hd["charPr"][new_id] = {**base, "bold": True}
        self.bold_cache[cid] = new_id
        return new_id

    def runs(self, text, cid):
        out = []
        for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
            if not part:
                continue
            c = self.bold_of(cid) if i % 2 else cid
            out.append(f'<hp:run charPrIDRef="{c}"><hp:t>{esc(part)}</hp:t></hp:run>')
        return "".join(out) or f'<hp:run charPrIDRef="{cid}"/>'

    def para(self, role, text, page_break=False):
        r = self.role(role)
        return (f'<hp:p id="{self.nid()}" paraPrIDRef="{r["paraPr"]}" styleIDRef="{r["style"]}" '
                f'pageBreak="{1 if page_break else 0}" columnBreak="0" merged="0">{self.runs(text, r["charPr"])}</hp:p>')

    def solid_border(self):
        for k, b in self.hd["borderFill"].items():
            if b and all(v == "SOLID" for v in b.values()) and len(b) == 4:
                return k
        new_id = str(max(int(k) for k in self.hd["borderFill"]) + 1)
        bf = (f'<hh:borderFill id="{new_id}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
              '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
              + "".join(f'<hh:{s}Border type="SOLID" width="0.12 mm" color="#000000"/>' for s in ("left", "right", "top", "bottom"))
              + '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/></hh:borderFill>')
        self.hw.header = re.sub(r"(</hh:borderFills>)", bf + r"\1", self.hw.header, count=1)
        self.hw.header = re.sub(r'(<hh:borderFills itemCnt=")(\d+)', lambda x: x.group(1) + str(int(x.group(2)) + 1), self.hw.header, count=1)
        self.hd["borderFill"][new_id] = {s: "SOLID" for s in ("left", "right", "top", "bottom")}
        return new_id

    def table(self, rows):
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        proto = re.search(r"<hp:tbl [^>]*>", self.sec)
        bf_tbl = attr(proto.group(0), "borderFillIDRef") if proto else self.solid_border()
        tc = re.search(r'<hp:tc [^>]*borderFillIDRef="(\d+)"', self.sec[proto.start():]) if proto else None
        bf_cell = tc.group(1) if tc else self.solid_border()
        cell = self.role("table_cell", "body")
        head_c = self.bold_of(cell["charPr"])
        width = self.text_width
        cw = [width // ncol] * ncol
        cw[-1] += width - sum(cw)
        ch = 1600
        trs = []
        for ri, r in enumerate(rows):
            tcs = []
            for ci, txt in enumerate(r):
                c = head_c if ri == 0 else cell["charPr"]
                tcs.append(
                    f'<hp:tc name="" header="{1 if ri == 0 else 0}" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{bf_cell}">'
                    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" '
                    'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                    f'<hp:p id="{self.nid()}" paraPrIDRef="{cell["paraPr"]}" styleIDRef="{cell["style"]}" pageBreak="0" columnBreak="0" merged="0">'
                    f'{self.runs(txt, c)}</hp:p></hp:subList>'
                    f'<hp:cellAddr colAddr="{ci}" rowAddr="{ri}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
                    f'<hp:cellSz width="{cw[ci]}" height="{ch}"/><hp:cellMargin left="141" right="141" top="141" bottom="141"/></hp:tc>')
            trs.append("<hp:tr>" + "".join(tcs) + "</hp:tr>")
        tbl = (f'<hp:tbl id="{self.nid()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
               f'lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" rowCnt="{len(rows)}" colCnt="{ncol}" '
               f'cellSpacing="0" borderFillIDRef="{bf_tbl}" noAdjust="0">'
               f'<hp:sz width="{width}" widthRelTo="ABSOLUTE" height="{ch * len(rows)}" heightRelTo="ABSOLUTE" protect="0"/>'
               '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
               'vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
               '<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:inMargin left="141" right="141" top="141" bottom="141"/>'
               + "".join(trs) + "</hp:tbl>")
        r = self.role("table_para", "body")
        return (f'<hp:p id="{self.nid()}" paraPrIDRef="{r["paraPr"]}" styleIDRef="{r["style"]}" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="{r["charPr"]}">{tbl}<hp:t/></hp:run></hp:p>')

    def image(self, path, base_dir):
        p = path if os.path.isabs(path) else os.path.join(base_dir, path)
        if not os.path.exists(p):
            self.warn.append(f"그림 파일 없음: {path}")
            return self.para("body", f"[그림 파일 없음: {path}]")
        data = open(p, "rb").read()
        wpx, hpx = image_size(data)
        ext = os.path.splitext(p)[1].lower().lstrip(".") or "png"
        ext = "jpg" if ext == "jpeg" else ext
        n = 1
        while f"BinData/baro{n}.{ext}" in self.hw.files:
            n += 1
        item = f"baro{n}"
        self.hw.files[f"BinData/{item}.{ext}"] = data
        hpf = self.hw.files["Contents/content.hpf"].decode("utf-8")
        hpf = hpf.replace("</opf:manifest>", f'<opf:item id="{item}" href="BinData/{item}.{ext}" media-type="image/{ext}" isEmbeded="1"/></opf:manifest>')
        self.hw.files["Contents/content.hpf"] = hpf.encode("utf-8")
        dw, dh = wpx * 75, hpx * 75  # 96dpi 기준 1px = 75 HWPUNIT
        maxw = int(self.text_width * 0.9)
        w = min(dw, maxw)
        h = int(dh * w / dw) if dw else dh
        pic = (f'<hp:pic id="{self.nid()}" zOrder="{self.pic_count}" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
               f'lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{self.nid()}" reverse="0">'
               f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="{w}" height="{h}"/>'
               '<hp:flip horizontal="0" vertical="0"/>'
               f'<hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
               '<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               '<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
               f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
               f'<hp:imgClip left="0" right="{dw}" top="0" bottom="{dh}"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:imgDim dimwidth="{dw}" dimheight="{dh}"/>'
               f'<hc:img binaryItemIDRef="{item}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/><hp:effects/>'
               f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
               '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="1" holdAnchorAndSO="0" '
               'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
               '<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:pic>')
        self.pic_count += 1
        r = self.role("figure_para", "body")
        return (f'<hp:p id="{self.nid()}" paraPrIDRef="{r["paraPr"]}" styleIDRef="{r["style"]}" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="{r["charPr"]}">{pic}<hp:t/></hp:run></hp:p>')

    def build(self, md_path, out):
        blocks = parse_md(open(md_path, encoding="utf-8").read())
        base = os.path.dirname(os.path.abspath(md_path))
        chap_break = self.map.get("_options", {}).get("chapter_page_break", True)
        cap_below = self.map.get("_options", {}).get("figure_caption_below", True)
        body, first_chapter, pending_break = [], True, False
        i = 0
        while i < len(blocks):
            kind, val = blocks[i]
            if kind == "pagebreak":
                pending_break = True
            elif kind == "chapter":
                body.append(self.para("chapter", val, page_break=(pending_break or (chap_break and not first_chapter))))
                first_chapter, pending_break = False, False
            elif kind == "table":
                body.append(self.table(val))
            elif kind == "image":
                if val["caption"] and not cap_below:
                    body.append(self.para("figure_caption", val["caption"]))
                body.append(self.image(val["path"], base))
                if val["caption"] and cap_below:
                    body.append(self.para("figure_caption", val["caption"]))
            else:
                body.append(self.para(kind if kind in ROLES else "body", val, page_break=pending_break))
                pending_break = False
            i += 1
        sec = self.sec
        tps = top_paragraphs(sec)
        first = sec[tps[0][0]:tps[0][1]]
        # 첫 문단: 쪽 설정(secPr)과 컨트롤(쪽번호·단 설정)만 남기고 글·도형은 지운다
        keep_runs = []
        for m in re.finditer(r"<hp:run [^>]*?(?:/>|>.*?</hp:run>)", first, re.S):
            r = m.group(0)
            if "<hp:secPr" in r or ("<hp:ctrl>" in r and not re.search(r"<hp:(rect|pic|tbl|line|ellipse|container)\b", r)):
                r = re.sub(r"<hp:t>.*?</hp:t>", "", r, flags=re.S)
                keep_runs.append(r)
        ftag = re.match(r"<hp:p [^>]*>", first).group(0)
        dropped = len(re.findall(r"<hp:(header|footer) ", sec[tps[0][1]:]))
        if dropped:
            self.warn.append(f"견본 본문 중간의 머리말/꼬리말 컨트롤 {dropped}개는 옮기지 않음(필요하면 한글에서 직접 지정)")
        new_first = ftag + "".join(keep_runs) + "</hp:p>"
        new_sec = sec[:tps[0][0]] + new_first + "".join(body) + sec[tps[-1][1]:]
        self.hw.files[self.hw.sections[self.sec_index]] = new_sec.encode("utf-8")
        self.hw.files["Contents/header.xml"] = self.hw.header.encode("utf-8")
        # 다른 섹션은 견본 글이 남지 않도록 목록에서 뺀다
        others = [n for k, n in enumerate(self.hw.sections) if k != self.sec_index]
        if others:
            hpf = self.hw.files["Contents/content.hpf"].decode("utf-8")
            for n in others:
                sid = os.path.splitext(os.path.basename(n))[0]
                hpf = re.sub(r'<opf:item id="' + sid + r'"[^>]*/>', "", hpf)
                hpf = re.sub(r'<opf:itemref idref="' + sid + r'"[^>]*/>', "", hpf)
                del self.hw.files[n]
            self.hw.files["Contents/content.hpf"] = hpf.encode("utf-8")
            self.warn.append(f"견본의 다른 섹션 {len(others)}개(표지 등)는 넣지 않음")
        if "Preview/PrvText.txt" in self.hw.files:
            txt = "\n".join(v for k, v in blocks if isinstance(v, str))[:1000]
            self.hw.files["Preview/PrvText.txt"] = txt.encode("utf-16-le") if self.hw.files["Preview/PrvText.txt"][:2] in (b"\xff\xfe",) else txt.encode("utf-8")
        self.hw.save(out)
        return {"out": out, "blocks": len(blocks), "warnings": self.warn}


def image_size(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b):
            if b[i] != 0xFF:
                i += 1; continue
            mk = b[i + 1]
            if mk in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return 800, 600


# ---------------------------------------------------------------- 글 지침 → 양식 파일
def _bump(h, tag, n=1):
    return re.sub(r'(<hh:' + tag + r' itemCnt=")(\d+)', lambda x: x.group(1) + str(int(x.group(2)) + n), h, count=1)


def _ensure_font(h, face):
    """모든 언어 글꼴 목록에 face가 있으면 그 id를, 없으면 추가하고 id를 돌려준다(언어별 dict)."""
    ids = {}

    def fix(m):
        head, lang, body = m.group(1), m.group(2), m.group(3)
        found = re.search(r'<hh:font id="(\d+)" face="' + re.escape(html.escape(face)) + r'"', body)
        if found:
            ids[lang] = found.group(1)
            return m.group(0)
        n = len(re.findall(r"<hh:font ", body))
        ids[lang] = str(n)
        new = f'<hh:font id="{n}" face="{html.escape(face)}" type="TTF" isEmbedded="0"/>'
        head = re.sub(r'fontCnt="\d+"', f'fontCnt="{n + 1}"', head)
        return head + body + new + "</hh:fontface>"

    h = re.sub(r'(<hh:fontface lang="(\w+)"[^>]*>)(.*?)</hh:fontface>', fix, h, flags=re.S)
    return h, ids


def from_spec(spec, base, out_hwpx, out_map):
    """spec(JSON): {"page": {"paper_mm":[210,297], "margin_mm": {...}}, "roles": {"body": {"font":"신명조","size_pt":11,
    "bold":false,"align":"JUSTIFY","line_spacing":160,"indent_pt":11 또는 "indent_chars":1,"space_before_pt":0,"space_after_pt":0,
    "page_break_before":false}, ...}, "_options": {...}}"""
    hw = Hwpx(base)
    h = hw.header
    hd = parse_header(h)
    c0 = re.search(r'<hh:charPr id="0".*?</hh:charPr>', h, re.S).group(0)
    p0 = re.search(r'<hh:paraPr id="0".*?</hh:paraPr>', h, re.S).group(0)
    next_c = max(int(k) for k in hd["charPr"]) + 1
    next_p = max(int(k) for k in hd["paraPr"]) + 1
    next_s = max(int(k) for k in hd["styles"]) + 1
    mapping = {"_options": spec.get("_options", {})}
    align_map = {"양쪽": "JUSTIFY", "왼쪽": "LEFT", "가운데": "CENTER", "오른쪽": "RIGHT", "배분": "DISTRIBUTE"}
    new_c, new_p, new_s = [], [], []
    for role, r in spec.get("roles", {}).items():
        size = float(r.get("size_pt", 10))
        h, fid = _ensure_font(h, r.get("font", "함초롬바탕"))
        if r.get("font_latin"):
            h, fl = _ensure_font(h, r["font_latin"])
        else:
            fl = fid
        c = re.sub(r'id="\d+"', f'id="{next_c}"', c0, count=1)
        c = re.sub(r'height="\d+"', f'height="{int(round(size * 100))}"', c, count=1)
        c = re.sub(r"<hh:fontRef [^>]*/>", '<hh:fontRef hangul="{}" latin="{}" hanja="{}" japanese="{}" other="{}" symbol="{}" user="{}"/>'.format(
            fid.get("HANGUL", "0"), fl.get("LATIN", "0"), fid.get("HANJA", "0"), fid.get("JAPANESE", "0"),
            fid.get("OTHER", "0"), fid.get("SYMBOL", "0"), fid.get("USER", "0")), c, count=1)
        c = c.replace("<hh:bold/>", "").replace("<hh:italic/>", "")
        if r.get("bold"):
            c = re.sub(r"(<hh:offset [^>]*/>)", r"\1<hh:bold/>", c, count=1)
        if r.get("italic"):
            c = re.sub(r"(<hh:offset [^>]*/>)", r"\1<hh:italic/>", c, count=1)
        if "spacing_pct" in r:
            c = re.sub(r"<hh:spacing [^>]*/>", '<hh:spacing hangul="{0}" latin="{0}" hanja="{0}" japanese="{0}" other="{0}" symbol="{0}" user="{0}"/>'.format(int(r["spacing_pct"])), c, count=1)
        if "ratio_pct" in r:
            c = re.sub(r"<hh:ratio [^>]*/>", '<hh:ratio hangul="{0}" latin="{0}" hanja="{0}" japanese="{0}" other="{0}" symbol="{0}" user="{0}"/>'.format(int(r["ratio_pct"])), c, count=1)
        new_c.append(c)
        indent = r.get("indent_pt", float(r.get("indent_chars", 0)) * size)
        vals = {"intent": indent, "left": r.get("left_pt", 0), "right": r.get("right_pt", 0),
                "prev": r.get("space_before_pt", 0), "next": r.get("space_after_pt", 0)}
        p = re.sub(r'id="\d+"', f'id="{next_p}"', p0, count=1)
        al = align_map.get(r.get("align", "JUSTIFY"), r.get("align", "JUSTIFY"))
        p = re.sub(r'(<hh:align horizontal=")\w+', r"\g<1>" + al, p, count=1)
        def set_margins(block, mult):
            for k, v in vals.items():
                block = re.sub(r'(<hc:' + k + r' value=")-?\d+', lambda m: m.group(1) + str(int(round(float(v) * 100 * mult))), block)
            block = re.sub(r'<hh:lineSpacing [^>]*/>', f'<hh:lineSpacing type="{r.get("line_spacing_type", "PERCENT")}" value="{int(r.get("line_spacing", 160))}" unit="HWPUNIT"/>', block)
            return block
        if "<hp:case" in p:
            p = re.sub(r"(<hp:case[^>]*>)(.*?)(</hp:case>)", lambda m: m.group(1) + set_margins(m.group(2), 1) + m.group(3), p, flags=re.S)
            p = re.sub(r"(<hp:default>)(.*?)(</hp:default>)", lambda m: m.group(1) + set_margins(m.group(2), 2) + m.group(3), p, flags=re.S)
        else:
            p = set_margins(p, 1)
        p = re.sub(r'pageBreakBefore="\d"', f'pageBreakBefore="{1 if r.get("page_break_before") else 0}"', p)
        p = re.sub(r'keepWithNext="\d"', f'keepWithNext="{1 if r.get("keep_with_next", role in ("chapter", "section", "subsection", "subsubsection", "table_caption")) else 0}"', p)
        new_p.append(p)
        name = r.get("style_name", f"바로_{role}")
        new_s.append(f'<hh:style id="{next_s}" type="PARA" name="{html.escape(name)}" engName="baro_{role}" '
                     f'paraPrIDRef="{next_p}" charPrIDRef="{next_c}" nextStyleIDRef="{next_s}" langID="1042" lockForm="0"/>')
        mapping[role] = {"style": str(next_s), "paraPr": str(next_p), "charPr": str(next_c),
                         "why": "글 지침에서 만든 서식", "source": r.get("source", "")}
        next_c += 1; next_p += 1; next_s += 1
    h = h.replace("</hh:charProperties>", "".join(new_c) + "</hh:charProperties>")
    h = h.replace("</hh:paraProperties>", "".join(new_p) + "</hh:paraProperties>")
    h = h.replace("</hh:styles>", "".join(new_s) + "</hh:styles>")
    h = _bump(h, "charProperties", len(new_c)); h = _bump(h, "paraProperties", len(new_p)); h = _bump(h, "styles", len(new_s))
    hw.header = h
    hw.files["Contents/header.xml"] = h.encode("utf-8")
    pg = spec.get("page", {})
    if pg:
        sec = hw.section(0)
        def fix_page(m):
            t = m.group(0)
            if "paper_mm" in pg:
                w, hh = pg["paper_mm"]
                t = re.sub(r'(<hp:pagePr [^>]*?)width="\d+"', lambda x: x.group(1) + f'width="{int(round(w * HU_PER_MM))}"', t, count=1)
                t = re.sub(r'(<hp:pagePr [^>]*?)height="\d+"', lambda x: x.group(1) + f'height="{int(round(hh * HU_PER_MM))}"', t, count=1)
            for k, v in pg.get("margin_mm", {}).items():
                t = re.sub(r'(<hp:margin [^>]*?)\b' + k + r'="\d+"', lambda x: x.group(1) + f'{k}="{int(round(v * HU_PER_MM))}"', t, count=1)
            return t
        sec = re.sub(r"<hp:pagePr [^>]*>\s*<hp:margin [^>]*>", fix_page, sec, count=1)
        hw.files[hw.sections[0]] = sec.encode("utf-8")
    hw.save(out_hwpx)
    json.dump(mapping, open(out_map, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"template": out_hwpx, "map": out_map, "roles": [k for k in mapping if not k.startswith("_")]}


# ---------------------------------------------------------------- 대조
def verify(template, mapping, out, md=None, spec=None):
    t, o = Hwpx(template), Hwpx(out)
    th, oh = parse_header(t.header), parse_header(o.header)
    issues, ok = [], []
    pt_ = profile(template)["pages"][0]
    po = profile(out)["pages"][0]
    if pt_ == po:
        ok.append(f"쪽 설정 일치: 용지 {po['paper_mm']}mm, 여백 {po['margin_mm']}")
    else:
        issues.append(f"쪽 설정 다름: 견본 {pt_} / 결과 {po}")
    pn_t = re.findall(r"<hp:pageNum [^>]*>", t.section(0))[:1]
    pn_o = re.findall(r"<hp:pageNum [^>]*>", o.section(0))[:1]
    (ok if pn_t == pn_o else issues).append(f"쪽번호 {'일치' if pn_t == pn_o else '다름'}: {pn_o[0] if pn_o else '없음'}")
    b = Builder(template, mapping)
    roles = {}
    for r in list(mapping):
        if r.startswith("_"):
            continue
        try:
            roles[r] = b.role(r)
        except SystemExit as e:
            issues.append(str(e))
    # 역할마다 결과의 서식 값이 견본 정의와 같은지
    for r, v in roles.items():
        for kind, key in (("paraPr", v["paraPr"]), ("charPr", v["charPr"])):
            a, c = th[kind].get(key), oh[kind].get(key)
            if a is None:
                issues.append(f"{r}: 견본에 {kind} {key}가 없음")
            elif a != c:
                issues.append(f"{r}: {kind} {key} 값이 견본과 다름 {a} → {c}")
        st = th["styles"].get(v["style"], {})
        ok.append(f"{r}: 스타일 '{st.get('name','')}' · 글꼴 {th['charPr'][v['charPr']]['font_hangul']} "
                  f"{th['charPr'][v['charPr']]['size_pt']}pt · {th['paraPr'][v['paraPr']]['align']} "
                  f"줄간격 {th['paraPr'][v['paraPr']]['line_spacing']}")
    # 결과 문단이 모두 map의 서식만 쓰는지
    allowed = {(v["paraPr"], v["style"]) for v in roles.values()}
    sec = o.section(0)
    tps = top_paragraphs(sec)
    stray = 0
    for a, bb in tps[1:]:
        tag = re.match(r"<hp:p [^>]*>", sec[a:bb]).group(0)
        if (attr(tag, "paraPrIDRef"), attr(tag, "styleIDRef")) not in allowed:
            stray += 1
    (issues if stray else ok).append(f"map에 없는 서식을 쓴 문단 {stray}개 (전체 {len(tps) - 1}개)")
    # 표·그림 번호 이어짐
    texts = [para_text(sec[a:bb]) for a, bb in tps]
    for label, rx in (("표", r"^<\s*표\s*([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d]+)[-–](\d+)"), ("그림", r"^[\[<]\s*그림\s*([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d]+)[-–](\d+)")):
        seq = {}
        for x in texts:
            m = re.match(rx, x)
            if m:
                seq.setdefault(m.group(1), []).append(int(m.group(2)))
        for ch, nums in seq.items():
            if nums != list(range(1, len(nums) + 1)):
                issues.append(f"{label} 번호가 {ch}장에서 이어지지 않음: {nums}")
        if seq:
            ok.append(f"{label} 번호 확인: " + ", ".join(f"{k}장 {len(v)}개" for k, v in seq.items()))
    if spec:
        align_map = {"양쪽": "JUSTIFY", "왼쪽": "LEFT", "가운데": "CENTER", "오른쪽": "RIGHT", "배분": "DISTRIBUTE"}
        pg = spec.get("page", {})
        if "paper_mm" in pg and [round(x) for x in po["paper_mm"]] != [round(x) for x in pg["paper_mm"]]:
            issues.append(f"용지가 규칙표와 다름: 규칙 {pg['paper_mm']} / 결과 {po['paper_mm']}")
        for k, v in pg.get("margin_mm", {}).items():
            if abs(po["margin_mm"].get(k, -1) - v) > 0.2:
                issues.append(f"여백 {k}가 규칙표와 다름: 규칙 {v}mm / 결과 {po['margin_mm'].get(k)}mm")
        for r, s in spec.get("roles", {}).items():
            if r not in roles:
                issues.append(f"규칙표의 '{r}' 역할이 map에 없음")
                continue
            c, p = oh["charPr"][roles[r]["charPr"]], oh["paraPr"][roles[r]["paraPr"]]
            size = float(s.get("size_pt", c["size_pt"]))
            checks = [("글꼴", s.get("font"), c["font_hangul"]), ("크기", size, c["size_pt"]),
                      ("굵게", bool(s.get("bold", False)), c["bold"]),
                      ("정렬", align_map.get(s.get("align", p["align"]), s.get("align", p["align"])), p["align"]),
                      ("줄간격", int(s.get("line_spacing", p["line_spacing"])), p["line_spacing"]),
                      ("들여쓰기", round(float(s.get("indent_pt", float(s.get("indent_chars", 0)) * size)), 1), p["indent_pt"]),
                      ("위 간격", float(s.get("space_before_pt", 0)), p["space_before_pt"]),
                      ("아래 간격", float(s.get("space_after_pt", 0)), p["space_after_pt"])]
            bad = [f"{n} 규칙 {a} / 결과 {b}" for n, a, b in checks if a is not None and a != b]
            (issues.append(f"{r}: 규칙표와 다름 — " + "; ".join(bad)) if bad else ok.append(f"{r}: 규칙표 값과 일치({s.get('source', '')[:40]})"))
    if md:
        src = parse_md(open(md, encoding="utf-8").read())
        want = sum(1 for k, v in src if k not in ("table", "image", "pagebreak") and v)
        got = sum(1 for x in texts[1:] if x)
        (ok if got >= want else issues).append(f"원고 문단 {want}개 / 결과 글 문단 {got}개")
        missing = [v for k, v in src if isinstance(v, str) and v and re.sub(r"\*\*", "", v)[:25] not in "\n".join(texts)]
        (issues if missing else ok).append(f"원고 글이 빠진 문단 {len(missing)}개" + (f": {missing[:3]}" if missing else ""))
    return {"ok": ok, "issues": issues}


def verify_md(res):
    L = ["# 양식 대조 결과", "", f"맞춘 항목 {len(res['ok'])}개 · 문제 {len(res['issues'])}개", "", "## 문제", ""]
    L += [f"- {x}" for x in res["issues"]] or ["- 없음"]
    L += ["", "## 맞춘 항목", ""] + [f"- {x}" for x in res["ok"]]
    L += ["", "이 대조는 파일 안의 값을 비교한 것입니다. 쪽 넘김·표 모양은 render로 그린 쪽 그림을 견본과 나란히 보고 확인해야 합니다."]
    return "\n".join(L)


# ---------------------------------------------------------------- 한글 프로그램 이용
def hancom():
    if os.name != "nt":
        raise SystemExit("한글 프로그램 자동화는 Windows에서만 됩니다. 결과 파일을 한글로 직접 열어 확인하세요.")
    try:
        import win32com.client  # noqa
    except ImportError:
        raise SystemExit("pywin32가 필요합니다: python -m pip install pywin32")
    import winreg
    import win32com.client
    hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
    registered = False
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\HNC\HwpAutomation\Modules")
        i = 0
        while True:
            try:
                name, _, _ = winreg.EnumValue(k, i)
            except OSError:
                break
            if hwp.RegisterModule("FilePathCheckDLL", name):
                registered = True
                break
            i += 1
    except OSError:
        pass
    if not registered:
        hwp.Quit()
        raise SystemExit("한글 보안 모듈이 등록되지 않았습니다. /baro-nonmun:setup 의 '한글 보안 모듈' 단계를 먼저 하세요.")
    try:
        hwp.XHwpWindows.Item(0).Visible = False
    except Exception:
        pass
    return hwp


def render(src, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    pdf = os.path.join(os.path.abspath(out_dir), os.path.splitext(os.path.basename(src))[0] + ".pdf")
    hwp = hancom()
    try:
        if not hwp.Open(os.path.abspath(src), "HWPX", "forceopen:true"):
            raise SystemExit("한글에서 파일을 열지 못했습니다(파일이 깨졌을 수 있음).")
        pages = hwp.PageCount
        if not hwp.SaveAs(pdf, "PDF", ""):
            raise SystemExit("PDF 저장 실패")
    finally:
        try:
            hwp.Clear(1)
            hwp.Quit()
        except Exception:
            pass
    pngs = []
    try:
        import fitz
        d = fitz.open(pdf)
        for i, pg in enumerate(d):
            f = os.path.join(out_dir, f"page_{i + 1:03d}.png")
            pg.get_pixmap(dpi=80).save(f)
            pngs.append(f)
    except ImportError:
        pngs = ["(PyMuPDF가 없어 쪽 그림은 만들지 않음: python -m pip install pymupdf)"]
    return {"pdf": pdf, "pages": pages, "pngs": pngs}


def convert(src, out):
    hwp = hancom()
    try:
        if not hwp.Open(os.path.abspath(src), "", "forceopen:true"):
            raise SystemExit("한글에서 파일을 열지 못했습니다.")
        if not hwp.SaveAs(os.path.abspath(out), "HWPX", ""):
            raise SystemExit("hwpx 저장 실패")
    finally:
        try:
            hwp.Clear(1)
            hwp.Quit()
        except Exception:
            pass
    return {"out": out}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("profile"); a.add_argument("src"); a.add_argument("-o", required=True); a.add_argument("--md"); a.add_argument("--map-out"); a.add_argument("--section", type=int, default=0)
    a = sp.add_parser("build"); a.add_argument("--template", required=True); a.add_argument("--map", required=True); a.add_argument("--md", required=True); a.add_argument("-o", required=True); a.add_argument("--section", type=int, default=0)
    a = sp.add_parser("verify"); a.add_argument("--template", required=True); a.add_argument("--map", required=True); a.add_argument("--out", required=True); a.add_argument("--md"); a.add_argument("-o"); a.add_argument("--spec")
    a = sp.add_parser("spec"); a.add_argument("--spec", required=True); a.add_argument("--base", required=True); a.add_argument("-o", required=True); a.add_argument("--map-out", required=True)
    a = sp.add_parser("render"); a.add_argument("src"); a.add_argument("--out-dir", required=True)
    a = sp.add_parser("convert"); a.add_argument("src"); a.add_argument("-o", required=True)
    x = ap.parse_args()
    if x.cmd == "profile":
        p = profile(x.src, x.section)
        json.dump(p, open(x.o, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if x.md:
            open(x.md, "w", encoding="utf-8").write(profile_md(p))
        if x.map_out:
            draft = {"_options": {"chapter_page_break": True, "figure_caption_below": True},
                     "_note": "추천 초안입니다. 표본을 보고 사람이 확인한 뒤 확정하세요."}
            draft.update({k: {kk: vv for kk, vv in v.items() if kk in ("style", "paraPr", "charPr", "why")} for k, v in p["suggested_map"].items()})
            json.dump(draft, open(x.map_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(json.dumps({"profile": x.o, "summary": x.md, "suggested_roles": list(p["suggested_map"])}, ensure_ascii=False))
    elif x.cmd == "build":
        mp = json.load(open(x.map, encoding="utf-8"))
        print(json.dumps(Builder(x.template, mp, x.section).build(x.md, x.o), ensure_ascii=False, indent=1))
    elif x.cmd == "verify":
        mp = json.load(open(x.map, encoding="utf-8"))
        res = verify(x.template, mp, x.out, x.md, json.load(open(x.spec, encoding="utf-8")) if x.spec else None)
        rep = verify_md(res)
        if x.o:
            open(x.o, "w", encoding="utf-8").write(rep)
        print(rep)
        sys.exit(1 if res["issues"] else 0)
    elif x.cmd == "spec":
        sp_ = json.load(open(x.spec, encoding="utf-8"))
        print(json.dumps(from_spec(sp_, x.base, x.o, x.map_out), ensure_ascii=False, indent=1))
    elif x.cmd == "render":
        print(json.dumps(render(x.src, x.out_dir), ensure_ascii=False, indent=1))
    elif x.cmd == "convert":
        print(json.dumps(convert(x.src, x.o), ensure_ascii=False))


if __name__ == "__main__":
    main()
