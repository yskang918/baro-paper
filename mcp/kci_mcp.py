#!/usr/bin/env python3
"""바로논문 학술 검색 MCP 서버 (표준 라이브러리만 사용).

도구
- kci_search      : KCI 논문 검색 (KCI Open API 키 필요)
- kci_article     : KCI 논문 상세 (KCI Open API 키 필요)
- openalex_search : OpenAlex 검색 (키 없이 사용, 국내 학술지 일부 포함)
- verify_reference: 참고문헌이 실제로 있는지 KCI·OpenAlex·Crossref에서 확인

KCI 키는 환경변수 KCI_API_KEY 또는 ~/.baro-paper/config.json 의 "kci_api_key" 에서 읽는다.
"""
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SERVER_NAME = "baro-scholar"
SERVER_VERSION = "0.4.0"
UA = "baro-paper/0.2 (academic research assistant)"
KCI_URL = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".baro-paper", "config.json")


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def kci_key():
    return os.environ.get("KCI_API_KEY") or load_config().get("kci_api_key") or ""


CACHE_DIR = os.path.join(os.path.expanduser("~"), ".baro-paper", "cache")
CACHE_DAYS = 7


class LimitError(Exception):
    pass


OPENALEX_LIMIT_MSG = ("OpenAlex 하루 무료 한도를 다 썼습니다. 키가 없으면 같은 인터넷(학교·집 공유기)을 쓰는 사람 모두가 "
                      "작은 한도를 나눠 쓰고, 한국 시간 오전 9시에 다시 채워집니다. https://openalex.org 에서 무료 계정을 만들고 "
                      "API 키를 받아 /baro-paper:setup 에서 등록하면 개인 한도로 씁니다. 그동안은 crossref_search 를 쓰세요.")


def http_get(url, params, timeout=25, headers=None, cache=True):
    import hashlib
    import time
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    full = url + ("?" + q if q else "")
    safe_key = re.sub(r"(api_key|key)=[^&]+", r"\1=*", full)  # 키는 캐시 이름에 넣지 않음
    cpath = os.path.join(CACHE_DIR, hashlib.sha1((safe_key + str(headers)).encode()).hexdigest() + ".bin")
    if cache and os.path.exists(cpath) and time.time() - os.path.getmtime(cpath) < CACHE_DAYS * 86400:
        with open(cpath, "rb") as f:
            return f.read()
    h = {"User-Agent": UA, **(headers or {})}
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers=h), timeout=timeout) as r:
                data = r.read()
            if cache:
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cpath, "wb") as f:
                    f.write(data)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                body = e.read()[:400].decode("utf-8", "ignore")
                wait = e.headers.get("Retry-After", "")
                if "openalex" in url and ("budget" in body.lower() or (wait.isdigit() and int(wait) > 60)):
                    raise LimitError(OPENALEX_LIMIT_MSG)
                time.sleep(min(int(wait) if wait.isdigit() else 2 ** attempt * 2, 20))
                continue
            if e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise
        except urllib.error.URLError as e:
            last = e
            time.sleep(2 ** attempt)
    raise last


def norm(s):
    return re.sub(r"[\W_]+", "", (s or "").lower())


def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------- KCI ----------------
def _text(el, path):
    x = el.find(path)
    return (x.text or "").strip() if x is not None and x.text else ""


def parse_kci(xml_bytes):
    root = ET.fromstring(xml_bytes)
    msg = root.find(".//result/resultMsg")
    total = root.find(".//outputData/result/total")
    records = []
    for rec in root.iter("record"):
        j = rec.find("journalInfo")
        a = rec.find("articleInfo")
        if a is None:
            continue
        titles = {t.get("lang", ""): (t.text or "").strip() for t in a.iter("article-title")}
        authors = [(_text(au, ".") or "").strip() for au in a.iter("author")]
        abstracts = {t.get("lang", ""): (t.text or "").strip() for t in a.iter("abstract")}
        records.append({
            "kci_id": a.get("article-id", ""),
            "title": titles.get("original") or next(iter(titles.values()), ""),
            "title_en": titles.get("english") or titles.get("foreign", ""),
            "authors": [x for x in authors if x],
            "journal": _text(j, "journal-name") if j is not None else "",
            "publisher": _text(j, "publisher-name") if j is not None else "",
            "year": _text(j, "pub-year") if j is not None else "",
            "volume": _text(j, "volume") if j is not None else "",
            "issue": _text(j, "issue") if j is not None else "",
            "pages": "-".join(x for x in (_text(a, "fpage"), _text(a, "lpage")) if x),
            "doi": _text(a, "doi"),
            "keywords": [(k.text or "").strip() for k in a.iter("keyword") if k.text],
            "abstract": (abstracts.get("original") or "")[:800],
            "citations_kci": (a.find("citation-count").get("kci") if a.find("citation-count") is not None else ""),
            "url": _text(a, "url"),
            "source": "KCI",
        })
    return {
        "message": (msg.text or "").strip() if msg is not None and msg.text else "",
        "total": (total.text or "").strip() if total is not None and total.text else str(len(records)),
        "records": records,
    }


NO_KEY = ("KCI API 키가 없습니다. KCI 검색은 키가 있어야 합니다. "
          "키 없이 openalex_search 를 쓰거나, /baro-paper:setup 에서 키를 등록하세요 "
          "(발급: https://open.kci.go.kr → OPEN API 키신청).")


def kci_search(args):
    key = kci_key()
    if not key:
        return {"error": NO_KEY}
    p = {
        "key": key, "apiCode": "articleSearch",
        "title": args.get("title", ""), "author": args.get("author"), "keyword": args.get("keyword"),
        "journal": args.get("journal"), "abstract": args.get("abstract"),
        "dateFrom": args.get("date_from"), "dateTo": args.get("date_to"),
        "page": args.get("page", 1), "displayCount": min(int(args.get("count", 20)), 100),
        "sortNm": args.get("sort"),
    }
    if not p["title"]:
        return {"error": "KCI 검색은 title(제목 검색어)이 꼭 있어야 합니다."}
    return parse_kci(http_get(KCI_URL, p))


def kci_article(args):
    key = kci_key()
    if not key:
        return {"error": NO_KEY}
    return parse_kci(http_get(KCI_URL, {"key": key, "apiCode": "articleDetail", "id": args["kci_id"]}))


# ---------------- OpenAlex ----------------
def _inv_abstract(inv):
    if not inv:
        return ""
    pos = {}
    for w, idx in inv.items():
        for i in idx:
            pos[i] = w
    return " ".join(pos[i] for i in sorted(pos))[:800]


def openalex_search(args):
    filters = []
    if args.get("from_year"):
        filters.append(f"from_publication_date:{int(args['from_year'])}-01-01")
    if args.get("to_year"):
        filters.append(f"to_publication_date:{int(args['to_year'])}-12-31")
    if args.get("type"):
        filters.append(f"type:{args['type']}")
    p = {"search": args["query"], "per-page": min(int(args.get("count", 20)), 50),
         "filter": ",".join(filters) or None, "sort": args.get("sort")}
    d = _oa(p)
    out = []
    for w in d.get("results", []):
        src = ((w.get("primary_location") or {}).get("source") or {})
        out.append({
            "openalex_id": w.get("id", ""),
            "title": w.get("display_name", ""),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", [])][:8],
            "year": w.get("publication_year"),
            "journal": src.get("display_name", ""),
            "doi": w.get("doi", ""),
            "cited_by": w.get("cited_by_count", 0),
            "language": w.get("language", ""),
            "type": w.get("type", ""),
            "abstract": _inv_abstract(w.get("abstract_inverted_index")),
            "source": "OpenAlex",
        })
    return {"total": d.get("meta", {}).get("count", len(out)), "records": out}


# ---------------- 트렌드 ----------------
def _oa_filter(query, precise=True, country=None, extra=None):
    f = [f'title_and_abstract.search:{query}' if precise else None]
    if country:
        f.append(f"authorships.countries:{country.upper()}")
    f += extra or []
    return ",".join(x for x in f if x)


def _oa(params):
    c = load_config()
    key = os.environ.get("OPENALEX_API_KEY") or c.get("openalex_api_key")
    if key:
        params["api_key"] = key
    if c.get("contact_email"):
        params["mailto"] = c["contact_email"]
    return json.loads(http_get("https://api.openalex.org/works", params))


def openalex_trend(args):
    """연도별 논문 수. 정확한 구문은 query를 큰따옴표로 감싼다."""
    q = args["query"]
    fy = int(args.get("from_year", 2015))
    ty = args.get("to_year")
    extra = [f"from_publication_date:{fy}-01-01"] + ([f"to_publication_date:{int(ty)}-12-31"] if ty else [])
    res = {}
    for label, country in (("전체", None), ("한국 저자", "KR")) if args.get("compare_korea", True) else (("전체", None),):
        p = {"filter": _oa_filter(q, args.get("precise", True), country, extra), "group_by": "publication_year"}
        if not args.get("precise", True):
            p["search"] = q
        d = _oa(p)
        res[label] = {g["key"]: g["count"] for g in sorted(d.get("group_by", []), key=lambda g: g["key"]) if g["key"].isdigit()}
    import datetime
    this_year = str(datetime.date.today().year)
    return {"query": q, "counts_by_year": res,
            "note": f"{this_year}년은 아직 진행 중이라 적게 또는 미리 등록된 논문 때문에 많게 나올 수 있다. OpenAlex 색인 기준이며 국내 학술지는 일부만 들어 있다."}


def openalex_topics(args):
    """최근 기간과 이전 기간의 주제 비중을 비교해 뜨는 주제를 찾는다."""
    q = args["query"]
    rf = int(args.get("recent_from", 2024))
    pf, pt = int(args.get("past_from", rf - 5)), int(args.get("past_to", rf - 2))
    def grp(extra):
        p = {"filter": _oa_filter(q, args.get("precise", True), args.get("country"), extra), "group_by": args.get("by", "topics.id")}
        if not args.get("precise", True):
            p["search"] = q
        return _oa(p).get("group_by", [])
    new = grp([f"from_publication_date:{rf}-01-01"])
    old = {g["key"]: g["count"] for g in grp([f"from_publication_date:{pf}-01-01", f"to_publication_date:{pt}-12-31"])}
    tn, to = sum(g["count"] for g in new) or 1, sum(old.values()) or 1
    rows = []
    for g in new:
        o = old.get(g["key"], 0)
        rows.append({"topic": g.get("key_display_name", g["key"]), "recent": g["count"], "past": o,
                     "growth_ratio": round((g["count"] / tn) / ((o + 1) / to), 2)})
    min_n = int(args.get("min_recent", 5))
    rising = sorted([r for r in rows if r["recent"] >= min_n], key=lambda r: -r["growth_ratio"])[: int(args.get("top", 15))]
    biggest = sorted(rows, key=lambda r: -r["recent"])[:10]
    return {"query": q, "recent": f"{rf}~", "past": f"{pf}~{pt}", "rising": rising, "largest_recent": biggest,
            "note": "growth_ratio = 최근 비중 / 이전 비중. 1보다 크면 비중이 커진 주제. 주제 분류는 OpenAlex 자동 분류다."}


def kci_trend(args):
    key = kci_key()
    if not key:
        return {"error": NO_KEY}
    fy, ty = int(args.get("from_year", 2015)), int(args.get("to_year", 2026))
    if ty - fy > 15:
        return {"error": "한 번에 16년까지만 셉니다."}
    out = {}
    for y in range(fy, ty + 1):
        r = parse_kci(http_get(KCI_URL, {"key": key, "apiCode": "articleSearch", "title": args["title"],
                                         "keyword": args.get("keyword"), "dateFrom": f"{y}01", "dateTo": f"{y}12", "displayCount": 1}))
        out[str(y)] = int(r["total"]) if str(r["total"]).isdigit() else r["total"]
    return {"title_query": args["title"], "counts_by_year": out, "note": "KCI 제목 검색 기준 연도별 논문 수"}


# ---------------- Crossref ----------------
def crossref_search(title, year=None, rows=5):
    p = {"query.bibliographic": title, "rows": rows}
    if year:
        p["filter"] = f"from-pub-date:{int(year)-1},until-pub-date:{int(year)+1}"
    d = json.loads(http_get("https://api.crossref.org/works", p))
    out = []
    for it in d.get("message", {}).get("items", []):
        y = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        out.append({"title": (it.get("title") or [""])[0], "year": y, "doi": it.get("DOI", ""),
                    "journal": (it.get("container-title") or [""])[0],
                    "authors": [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in it.get("author", [])][:6],
                    "source": "Crossref"})
    return out


def crossref_tool(args):
    recs = crossref_search(args["query"], args.get("year"), min(int(args.get("count", 10)), 30))
    return {"total": len(recs), "records": recs,
            "note": "Crossref 검색(키 불필요). OpenAlex 한도에 걸렸을 때 대신 쓴다. 국내 DOI 일부는 Crossref에 없다."}


def doi_lookup(doi):
    """doi.org를 거쳐 등록 기관(Crossref·KISTI 등) 상관없이 서지를 받는다."""
    d = doi.strip()
    for pre in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if d.lower().startswith(pre):
            d = d[len(pre):]
    m = json.loads(http_get("https://doi.org/" + urllib.parse.quote(d, safe="/"), {},
                            headers={"Accept": "application/vnd.citationstyles.csl+json"}))
    y = ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    ct = m.get("container-title", "")
    return {"doi": d, "title": m.get("title", ""), "year": y,
            "journal": ct if isinstance(ct, str) else (ct or [""])[0],
            "publisher": m.get("publisher", ""),
            "authors": [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in m.get("author", [])][:6],
            "source": "doi.org"}


def verify_reference(args):
    title = args["title"]
    year = args.get("year")
    author = args.get("author", "")
    cands, notes = [], []
    if args.get("doi"):
        try:
            rec = doi_lookup(args["doi"])
            ok_year = not year or not rec["year"] or abs(int(rec["year"]) - int(year)) <= 1
            sim = similarity(title, rec["title"])
            ko_vs_en = bool(re.search(r"[가-힣]", title)) and not re.search(r"[가-힣]", rec["title"] or "")
            if ok_year and sim >= 0.6:
                verdict = "확인됨(DOI)"
            elif ok_year and ko_vs_en and rec["title"]:
                verdict = "확인됨(DOI·연도 일치, 등록 제목은 영문 — 같은 논문인지 제목 뜻을 한 번 대조)"
            elif ok_year:
                verdict = "DOI 있음·연도 일치 — 등록 제목이 다른 언어이거나 다름(사람이 제목 대조)"
            else:
                verdict = "DOI 있음 — 연도가 다름(사람이 확인 필요)"
            return {"verdict": verdict, "best_score": round(sim, 3), "best_match": rec, "others": [],
                    "notes": ["doi.org 등록 서지와 대조. 국내 학술지는 영문 제목으로 등록된 경우가 많다."]}
        except urllib.error.HTTPError as e:
            notes.append(f"DOI 조회 실패(HTTP {e.code}): DOI가 틀렸거나 등록되지 않음")
        except Exception as e:
            notes.append(f"DOI 조회 실패: {e}")
    if kci_key():
        try:
            cands += kci_search({"title": title, "count": 10}).get("records", [])
        except Exception as e:
            notes.append(f"KCI 확인 실패: {e}")
    else:
        notes.append("KCI 키 없음: KCI는 확인하지 않음")
    try:
        cands += openalex_search({"query": title, "count": 10}).get("records", [])
    except LimitError:
        notes.append("OpenAlex 한도 초과: 이번에는 Crossref·DOI로만 확인함(OpenAlex API 키를 등록하면 해결)")
    except Exception as e:
        notes.append(f"OpenAlex 확인 실패: {e}")
    try:
        cands += crossref_search(title, year)
    except Exception as e:
        notes.append(f"Crossref 확인 실패: {e}")
    scored = []
    for c in cands:
        s = similarity(title, c.get("title", "")) or similarity(title, c.get("title_en", ""))
        if year and c.get("year") and str(c["year"]).isdigit() and abs(int(c["year"]) - int(year)) > 1:
            s -= 0.2
        if author and c.get("authors") and not any(norm(author)[:2] in norm(a) for a in c["authors"]):
            s -= 0.1
        scored.append((round(s, 3), c))
    scored.sort(key=lambda x: -x[0])
    best = scored[0] if scored else (0, None)
    if best[0] >= 0.9:
        verdict = "확인됨"
    elif best[0] >= 0.7:
        verdict = "비슷한 논문 있음(사람이 확인 필요)"
    else:
        verdict = "찾지 못함(인용 전 원문 확인 필요)"
        if re.search(r"[가-힣]", title):
            notes.append("국문 제목은 해외 DB에 영문 제목으로만 있는 경우가 많다. DOI를 넣어 다시 확인하거나 KCI 키를 등록하라.")
    return {"verdict": verdict, "best_score": best[0], "best_match": best[1],
            "others": [dict(score=s, **{k: c.get(k) for k in ("title", "year", "journal", "doi", "source")}) for s, c in scored[1:4]],
            "notes": notes}


TOOLS = {
    "kci_search": (kci_search, "KCI(한국학술지인용색인) 논문 검색. 국내 학술지 논문을 찾을 때 먼저 쓴다. KCI API 키 필요.", {
        "type": "object", "required": ["title"],
        "properties": {
            "title": {"type": "string", "description": "제목 검색어(필수)"},
            "author": {"type": "string"}, "keyword": {"type": "string"}, "journal": {"type": "string"},
            "abstract": {"type": "string", "description": "초록 검색어"},
            "date_from": {"type": "string", "description": "발행연월 시작 YYYYMM"},
            "date_to": {"type": "string", "description": "발행연월 끝 YYYYMM"},
            "count": {"type": "integer", "description": "결과 수(최대 100)", "default": 20},
            "page": {"type": "integer", "default": 1},
            "sort": {"type": "string", "enum": ["title", "author", "pubiYr"], "description": "비우면 정확도순"}}}),
    "kci_article": (kci_article, "KCI 논문 한 편의 상세 정보(초록·키워드·피인용 등). KCI API 키 필요.", {
        "type": "object", "required": ["kci_id"],
        "properties": {"kci_id": {"type": "string", "description": "KCI 논문 제어번호 예: ART002358582"}}}),
    "openalex_search": (openalex_search, "OpenAlex 학술 검색(키 없으면 공용 하루 한도, 키 등록 권장). 해외 논문과 일부 국내 학술지. 한국어 검색어도 된다.", {
        "type": "object", "required": ["query"],
        "properties": {
            "query": {"type": "string"}, "from_year": {"type": "integer"}, "to_year": {"type": "integer"},
            "count": {"type": "integer", "default": 20, "description": "최대 50"},
            "type": {"type": "string", "description": "예: article, review, dissertation"},
            "sort": {"type": "string", "description": "예: cited_by_count:desc, publication_year:desc"}}}),
    "openalex_trend": (openalex_trend, "연도별 논문 수(전체·한국 저자). 분야·주제가 커지는지 볼 때. 정확한 구문은 큰따옴표: '\"cognitive offloading\"'.", {
        "type": "object", "required": ["query"],
        "properties": {"query": {"type": "string"}, "from_year": {"type": "integer", "default": 2015}, "to_year": {"type": "integer"},
                       "precise": {"type": "boolean", "default": True, "description": "제목·초록에서만 찾기(정확). false면 넓은 검색"},
                       "compare_korea": {"type": "boolean", "default": True}}}),
    "openalex_topics": (openalex_topics, "최근 기간과 이전 기간의 주제 비중을 비교해 '뜨는 주제'를 찾는다. 연구 트렌드 지도용.", {
        "type": "object", "required": ["query"],
        "properties": {"query": {"type": "string"}, "recent_from": {"type": "integer", "default": 2024},
                       "past_from": {"type": "integer"}, "past_to": {"type": "integer"},
                       "by": {"type": "string", "default": "topics.id", "description": "topics.id 또는 keywords.id"},
                       "country": {"type": "string", "description": "예: KR"}, "precise": {"type": "boolean", "default": True},
                       "top": {"type": "integer", "default": 15}, "min_recent": {"type": "integer", "default": 5}}}),
    "kci_trend": (kci_trend, "KCI 국내 논문의 연도별 수(제목 검색). KCI API 키 필요.", {
        "type": "object", "required": ["title"],
        "properties": {"title": {"type": "string"}, "keyword": {"type": "string"},
                       "from_year": {"type": "integer", "default": 2015}, "to_year": {"type": "integer", "default": 2026}}}),
    "crossref_search": (crossref_tool, "Crossref 검색(키 불필요). OpenAlex 한도에 걸렸을 때나 DOI를 찾을 때.", {
        "type": "object", "required": ["query"],
        "properties": {"query": {"type": "string"}, "year": {"type": "integer"}, "count": {"type": "integer", "default": 10}}}),
    "verify_reference": (verify_reference, "참고문헌이 실제로 있는지 확인. DOI가 있으면 꼭 넣는다(국문 논문도 doi.org로 확인됨). 없으면 KCI·OpenAlex·Crossref 제목 대조. 인용하기 전에 반드시 쓴다.", {
        "type": "object", "required": ["title"],
        "properties": {"title": {"type": "string"}, "year": {"type": "integer"},
                       "doi": {"type": "string", "description": "예: 10.18108/jeer.2025.28.6.58"},
                       "author": {"type": "string", "description": "제1저자 이름(선택)"}}}),
}


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        ver = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": ver, "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": [
            {"name": n, "description": d, "inputSchema": s} for n, (_, d, s) in TOOLS.items()]}}
    if method == "tools/call":
        p = msg.get("params") or {}
        name, args = p.get("name"), p.get("arguments") or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"없는 도구: {name}"}}
        try:
            res = TOOLS[name][0](args)
            is_err = isinstance(res, dict) and "error" in res
            text = json.dumps(res, ensure_ascii=False, indent=1)
        except LimitError as e:
            is_err, text = True, str(e)
        except Exception as e:
            is_err, text = True, f"{name} 실행 오류: {type(e).__name__}: {e}"
        return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": is_err}}
    if mid is None:  # 알림(notification)은 응답하지 않음
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"지원하지 않는 메서드: {method}"}}


def main():
    stdin = open(sys.stdin.fileno(), encoding="utf-8", errors="replace")
    stdout = open(sys.stdout.fileno(), "w", encoding="utf-8", newline="\n")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        out = handle(msg)
        if out is not None:
            stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    main()
