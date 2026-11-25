#!/usr/bin/env python3
"""
공구모아 키워드·브랜드별 공구 페이지 생성기 (AEO/SEO용)

- 홈페이지와 같은 데이터(구글폼 연동 시트 프록시)를 받아서
  /gonggu/<브랜드>/index.html, /gonggu/index.html, /sitemap.xml, /llms.txt 를 만들어요.
- 브랜드 목록은 scripts/aeo_brands.json, 키워드 목록은 scripts/aeo_keywords.json 에서 고치면 돼요.
- GitHub Actions(.github/workflows/aeo.yml)가 매일 아침 자동 실행해요.

로컬 테스트: python3 scripts/build_aeo.py --items items.json
"""
import json, re, sys, os, html, datetime, urllib.request, urllib.parse, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://gonggumoa.com"
FORM_PROXY_URL = "https://script.google.com/macros/s/AKfycbwvqvbGVLOUBhIqITLa1SmzG_v-OB-tZRhJxFmO6VMV_ntVDuwRordm2OcHCtRSmRytMg/exec"
INPOCK_SHEET_ID = "1VjToHbaCFXtS0hYsdm7BYmxoRzwyyAwu_LYQYxxZLZk"
QNA_SHEET_ID = "1w6_NDPQQVI_n9d2q8gTA6V0StTCw8wfKcDox_G4LZmw"
GA_ID = "G-BBSL0JLGEH"
PAST_LIMIT = 8

KST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(KST).date()
WEEK = "월화수목금토일"


# ---------------- 데이터 받기 ----------------

def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "gonggumoa-aeo-builder"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def fetch_items():
    items, vip, offset = [], [], 0
    for _ in range(20):
        j = json.loads(get(f"{FORM_PROXY_URL}?offset={offset}&limit=3000", 120))
        if j.get("error"):
            raise SystemExit("프록시 오류: " + str(j["error"]))
        if offset == 0 and isinstance(j.get("vipList"), list):
            vip = j["vipList"]
        got = j.get("items") or []
        items += got
        if not j.get("hasMore") or not got:
            break
        offset += len(got)
    return items, vip


def gviz_rows(sheet_id, gid="0"):
    try:
        t = get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:json&gid={gid}")
        j = json.loads(re.search(r"setResponse\(([\s\S]*)\)", t).group(1))
        out = []
        for row in j["table"]["rows"]:
            out.append([("" if (c is None or c.get("v") is None) else str(c.get("v")).strip()) for c in (row.get("c") or [])])
        return out
    except Exception as e:
        print("시트 읽기 실패(건너뜀):", sheet_id, e)
        return []


def load_inpock():
    m = {}
    for r in gviz_rows(INPOCK_SHEET_ID):
        if len(r) >= 2 and r[0] and r[1]:
            m[r[0].replace("@", "").lower()] = r[1].replace("@", "")
    return m


def load_qna():
    m = {}
    for r in gviz_rows(QNA_SHEET_ID):
        if len(r) >= 2 and r[0] and r[1] and r[0] != "브랜드키":
            m[r[0]] = [re.sub(r"\s+", " ", x).strip() for x in r[1].splitlines() if x.strip()]
    return m


# ---------------- 날짜 ----------------

def pdate(s):
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(s or ""))
    return datetime.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def end_of(d):  # 홈페이지 getEndDate()와 같은 규칙
    e = pdate(d.get("end_date"))
    if e:
        return e
    o = pdate(d.get("date"))
    return o + datetime.timedelta(days=3) if o else None


def md(dt):
    return f"{dt.month}/{dt.day}({WEEK[dt.weekday()]})"


def kdate(dt):
    return f"{dt.year}년 {dt.month}월 {dt.day}일"


# ---------------- 정리 ----------------

def norm_items(raw):
    out, seen = [], set()
    for d in raw:
        name = re.sub(r"\s+", " ", str(d.get("name") or "")).strip()
        o = pdate(d.get("date"))
        if not name or not o:
            continue
        insta = str(d.get("insta") or "").strip().lstrip("@")
        key = (re.sub(r"\s", "", name).lower(), insta.lower(), o)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(name=name, inf=str(d.get("inf") or "").strip(), insta=insta,
                        open=o, end=end_of(d) or o, sub=str(d.get("sub") or "").strip()))
    return out


def matcher(words):
    pats = [re.compile(r"(^|[\s\[(/·,])" + re.escape(w), re.I) for w in words]
    return lambda name: any(p.search(name) for p in pats)


def slug_url(name):
    return f"/gonggu/{urllib.parse.quote(name)}/"


def link_for(d, vip, inpock):
    iid = d["insta"].lower()
    if iid in vip and inpock.get(iid):
        return "https://link.inpock.co.kr/" + inpock[iid], "구매 링크"
    if iid:
        return "https://www.instagram.com/" + d["insta"] + "/", "인스타"
    return SITE + "/", "공구모아"


# ---------------- HTML ----------------

E = html.escape

CSS = """
:root{--navy-dark:#1e2740;--bg:#f5f3ef;--surface:#fff;--ink:#1c1a17;--ink2:#5b5650;--border:#e8e3dc;--navy:#2d3a5a;--accent:#e8450a;--accent-light:#fdf0eb}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Pretendard",-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--ink);line-height:1.6;font-size:15px}
a{color:var(--navy)}
.wrap{max-width:720px;margin:0 auto;padding:20px 16px 48px}
header{background:var(--navy);height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 16px}
.logo{display:flex;align-items:center;gap:9px;text-decoration:none}
.logo-mark{width:34px;height:34px;border-radius:50%;background:var(--navy-dark);border:1.5px solid rgba(255,255,255,.35);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:9px;line-height:1.05;text-align:center}
.logo-text{font-weight:900;font-size:17px;color:#fff;letter-spacing:-.5px}
.hdr-link{font-size:12px;font-weight:700;color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.45);border-radius:20px;padding:5px 12px}
.hero{background:var(--navy-dark);padding:.55rem 16px;font-size:12px;color:rgba(255,255,255,.8)}
.crumb{font-size:12px;color:var(--ink2);margin-bottom:10px}
.crumb a{color:var(--ink2);text-decoration:none}
h1{font-size:24px;line-height:1.35;margin-bottom:12px;letter-spacing:-.02em}
h2{font-size:17px;margin:28px 0 10px}
.answer{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--navy);border-radius:10px;padding:14px 16px}
.answer b{color:var(--navy)}
.kw{margin-top:8px}
.asof{font-size:12px;color:var(--ink2);margin-top:6px}
.list{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.row{display:flex;gap:12px;padding:12px 14px;border-top:1px solid var(--border);align-items:flex-start}
.row:first-child{border-top:0}
.when{flex:0 0 96px;font-size:13px;font-weight:700;color:var(--navy)}
.when small{display:block;font-weight:600;color:var(--accent)}
.what{flex:1;min-width:0}
.what .n{font-weight:600}
.what .w{font-size:13px;color:var(--ink2)}
.go{flex:0 0 auto;font-size:12px;padding:5px 10px;border:1px solid var(--navy);border-radius:16px;text-decoration:none;white-space:nowrap}
.go.buy{background:var(--navy);color:#fff}
.past .when{color:var(--ink2)}
.empty{padding:14px;color:var(--ink2);font-size:14px}
.qa{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:8px}
.qa h3{font-size:15px;margin-bottom:4px}
.qa p{font-size:14px;color:var(--ink2)}
.cta{display:block;text-align:center;margin:28px 0 8px;padding:13px;border-radius:10px;background:var(--navy);color:#fff;text-decoration:none;font-weight:700}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chips a{font-size:13px;padding:5px 11px;border:1px solid var(--border);background:var(--surface);border-radius:16px;text-decoration:none;color:var(--ink)}
.chips a b{color:var(--accent);font-weight:700;margin-left:3px}
.memo{font-size:13px;color:var(--ink2);padding:10px 14px;border-top:1px solid var(--border)}
footer{margin-top:36px;font-size:12px;color:var(--ink2);text-align:center}
"""


def page(title, desc, path, body, ld):
    ga = f"""<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_ID}');</script>"""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="article">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:site_name" content="공구모아">
<meta property="article:modified_time" content="{TODAY.isoformat()}">
<link rel="icon" href="/favicon.ico">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">
{ga}
<style>{CSS}</style>
{"".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)}
</head>
<body>
<header><a class="logo" href="/"><div class="logo-mark">공구<br>모아</div><span class="logo-text">공구모아</span></a><a class="hdr-link" href="/gonggu/">키워드·브랜드별 공구 ↗</a></header>
<div class="hero">인스타 공구 일정, 매일 아침 모아서 알려드려요</div>
<div class="wrap">
{body}
<footer>공구모아 · (주)스테이프레시 · 인스타그램 @gong.gu.moa<br>공구 일정은 인플루언서 공지 기준이며 변경될 수 있어요.</footer>
</div></body></html>
"""


def row_html(d, vip, inpock, past=False):
    url, label = link_for(d, vip, inpock)
    who = f"{E(d['inf'])} (@{E(d['insta'])})" if d["inf"] else f"@{E(d['insta'])}"
    status = ""
    if not past:
        if d["open"] > TODAY:
            n = (d["open"] - TODAY).days
            status = f"<small>D-{n}</small>"
        else:
            status = "<small>진행 중</small>"
    cls = "go buy" if label == "구매 링크" else "go"
    return (f'<div class="row"><div class="when">{md(d["open"])}~<br>{md(d["end"])}{status}</div>'
            f'<div class="what"><div class="n">{E(d["name"])}</div><div class="w">{who}</div></div>'
            f'<a class="{cls}" href="{E(url)}" rel="nofollow noopener" target="_blank">{label} ↗</a></div>')


def who_txt(d):
    return f"{d['inf']}(@{d['insta']})" if d["inf"] else f"@{d['insta']}"


def brand_page(b, mine, vip, inpock, qna_lines, related, kwrel):
    name = b["name"]
    live = sorted([d for d in mine if d["end"] >= TODAY], key=lambda d: d["open"])
    past = sorted([d for d in mine if d["end"] < TODAY], key=lambda d: d["open"], reverse=True)[:PAST_LIMIT]
    ongoing = [d for d in live if d["open"] <= TODAY]
    upcoming = [d for d in live if d["open"] > TODAY]

    # 한 줄 답 (AI가 그대로 인용하기 좋게)
    if live:
        first = live[0]
        ans = (f"{kdate(TODAY)} 기준, <b>{E(name)} 공구는 진행 중 {len(ongoing)}건 · 오픈 예정 {len(upcoming)}건</b>이에요. "
               f"가장 가까운 공구는 <b>{md(first['open'])}~{md(first['end'])} {E(who_txt(first))}</b>의 {E(first['name'])} 공구예요.")
        plain = (f"{kdate(TODAY)} 기준 {name} 공구는 진행 중 {len(ongoing)}건, 오픈 예정 {len(upcoming)}건입니다. "
                 f"가장 가까운 공구는 {first['open'].month}/{first['open'].day}~{first['end'].month}/{first['end'].day} {who_txt(first)}의 {first['name']} 공구입니다.")
    elif past:
        p = past[0]
        ans = (f"{kdate(TODAY)} 기준, <b>{E(name)} 공구는 지금 잡힌 일정이 없어요.</b> "
               f"가장 최근 공구는 <b>{md(p['open'])}~{md(p['end'])} {E(who_txt(p))}</b>의 {E(p['name'])} 공구였어요.")
        plain = (f"{kdate(TODAY)} 기준 {name} 공구는 현재 잡힌 일정이 없습니다. "
                 f"가장 최근 공구는 {p['open'].month}/{p['open'].day}~{p['end'].month}/{p['end'].day} {who_txt(p)}의 {p['name']} 공구였습니다.")
    else:
        ans = f"{kdate(TODAY)} 기준, <b>{E(name)} 공구는 지금 잡힌 일정이 없어요.</b> 새 일정이 올라오면 이 페이지에 바로 반영돼요."
        plain = f"{kdate(TODAY)} 기준 {name} 공구는 현재 잡힌 일정이 없습니다. 새 일정은 공구모아에 매일 업데이트됩니다."

    path = slug_url(name)
    sec_live = "".join(row_html(d, vip, inpock) for d in live) or '<div class="empty">지금 진행 중이거나 예정된 공구가 없어요.</div>'
    sec_past = "".join(row_html(d, vip, inpock, past=True) for d in past)
    memo = ""
    if qna_lines and not past:
        memo = '<h2>공구모아 기록</h2><div class="list">' + "".join(f'<div class="memo">{E(x)}</div>' for x in qna_lines[:8]) + "</div>"
    rel = "".join(f'<a href="{slug_url(r)}">{E(r)} 공구{f"<b>{n}</b>" if n else ""}</a>' for r, n in related)
    kwchips = "".join(f'<a href="{slug_url(k)}">{E(t)} 공구{f"<b>{n}</b>" if n else ""}</a>' for k, t, n in kwrel)

    body = f"""<div class="crumb"><a href="/">공구모아</a> › <a href="/gonggu/">키워드·브랜드별 공구</a> › {E(name)}</div>
<h1>{E(name)} 공구 언제? 진행 중·오픈 예정 일정 총정리</h1>
<div class="answer">{ans}<div class="asof">업데이트 {kdate(TODAY)} · 매일 아침 갱신</div></div>
<h2>진행 중 · 오픈 예정 {E(name)} 공구</h2>
<div class="list">{sec_live}</div>
{f'<h2>최근 지난 {E(name)} 공구</h2><div class="list past">{sec_past}</div>' if sec_past else ''}
{memo}
{f'<h2>{E(name)} 관련 키워드</h2><div class="chips">{kwchips}</div>' if kwchips else ''}
<a class="cta" href="/">공구모아에서 전체 공구 일정 보기 →</a>
{f'<h2>함께 많이 찾는 공구</h2><div class="chips">{rel}</div>' if rel else ''}
"""
    ld = [
        {"@context": "https://schema.org", "@type": "WebPage", "name": f"{name} 공구 일정", "dateModified": TODAY.isoformat(),
         "description": plain, "url": SITE + slug_url(name)},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "공구모아", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "키워드·브랜드별 공구", "item": SITE + "/gonggu/"},
            {"@type": "ListItem", "position": 3, "name": f"{name} 공구", "item": SITE + path}]},
    ]
    title = f"{name} 공구 언제? {TODAY.month}월 공구 일정·진행 중 공구 | 공구모아"
    desc = plain[:150]
    return path, page(title, desc, path, body, ld), len(live)


def keyword_page(k, mine, vip, inpock, brands_in, kwrel):
    name, title = k["name"], k.get("title") or k["name"]
    live = sorted([d for d in mine if d["end"] >= TODAY], key=lambda d: d["open"])
    past = sorted([d for d in mine if d["end"] < TODAY], key=lambda d: d["open"], reverse=True)[:12]
    ongoing = [d for d in live if d["open"] <= TODAY]
    upcoming = [d for d in live if d["open"] > TODAY]
    top_live = list(dict.fromkeys(d["name"].split()[0] for d in live))[:5]
    if live:
        ans = (f"{kdate(TODAY)} 기준, <b>{E(title)} 공구는 진행 중 {len(ongoing)}건 · 오픈 예정 {len(upcoming)}건</b>이에요. "
               f"지금 열린 공구는 {E(', '.join(top_live))} 등이 있어요.")
        plain = (f"{kdate(TODAY)} 기준 {title} 공구는 진행 중 {len(ongoing)}건, 오픈 예정 {len(upcoming)}건입니다. "
                 f"지금 열린 공구는 {', '.join(top_live)} 등이 있습니다.")
    else:
        ans = f"{kdate(TODAY)} 기준, <b>{E(title)} 공구는 지금 잡힌 일정이 없어요.</b> 최근 공구를 참고해 주세요."
        plain = f"{kdate(TODAY)} 기준 {title} 공구는 현재 잡힌 일정이 없습니다."
    path = slug_url(name)
    sec_live = "".join(row_html(d, vip, inpock) for d in live[:40]) or '<div class="empty">지금 진행 중이거나 예정된 공구가 없어요.</div>'
    sec_past = "".join(row_html(d, vip, inpock, past=True) for d in past)
    bchips = "".join(f'<a href="{slug_url(b)}">{E(b)} 공구{f"<b>{n}</b>" if n else ""}</a>' for b, n in brands_in)
    kwchips = "".join(f'<a href="{slug_url(x)}">{E(t)} 공구{f"<b>{n}</b>" if n else ""}</a>' for x, t, n in kwrel)
    body = f"""<div class="crumb"><a href="/">공구모아</a> › <a href="/gonggu/">키워드·브랜드별 공구</a> › {E(title)}</div>
<h1>{E(title)} 공구 모음 — 지금 진행 중인 {E(name)} 공구 추천</h1>
<div class="answer">{ans}<div class="asof">업데이트 {kdate(TODAY)} · 매일 아침 갱신</div></div>
<h2>진행 중 · 오픈 예정 {E(name)} 공구</h2>
<div class="list">{sec_live}</div>
{f'<h2>최근 지난 {E(name)} 공구</h2><div class="list past">{sec_past}</div>' if sec_past else ''}
{f'<h2>{E(name)} 공구 브랜드</h2><div class="chips">{bchips}</div>' if bchips else ''}
<a class="cta" href="/">공구모아에서 전체 공구 일정 보기 →</a>
{f'<h2>함께 찾는 키워드</h2><div class="chips">{kwchips}</div>' if kwchips else ''}
"""
    ld = [
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{title} 공구 모음", "dateModified": TODAY.isoformat(),
         "description": plain, "url": SITE + path},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "공구모아", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "키워드·브랜드별 공구", "item": SITE + "/gonggu/"},
            {"@type": "ListItem", "position": 3, "name": f"{title} 공구", "item": SITE + path}]},
    ]
    return path, page(f"{title} 공구 추천 · {TODAY.month}월 진행 중인 {name} 공구 모음 | 공구모아", plain[:150], path, body, ld), len(live)


def index_page(stats, kstats):
    groups = collections.OrderedDict()
    for name, n, sub in sorted(stats, key=lambda x: (-x[1], x[0])):
        groups.setdefault(sub or "기타", []).append((name, n))
    total_live = sum(1 for s in stats if s[1])
    body = f"""<div class="crumb"><a href="/">공구모아</a> › 키워드·브랜드별 공구</div>
<h1>키워드·브랜드별 공구 일정 모음</h1>
<div class="answer">인스타 인플루언서 공동구매(공구) 일정을 키워드·브랜드별로 정리했어요. {kdate(TODAY)} 기준 <b>{len(stats)}개 브랜드</b> 중 <b>{total_live}개</b> 브랜드 공구가 진행 중이거나 오픈 예정이에요.<div class="asof">매일 아침 갱신</div></div>
<h2>키워드로 찾기</h2><div class="chips">""" + "".join(
        f'<a href="{slug_url(n)}">{E(t)}{f"<b>{c}</b>" if c else ""}</a>' for n, t, c in kstats) + """</div>
""" + "".join(
        f'<h2>브랜드 · {E(g)}</h2><div class="chips">' + "".join(
            f'<a href="{slug_url(n)}">{E(n)}{f"<b>{c}</b>" if c else ""}</a>' for n, c in lst) + "</div>"
        for g, lst in sorted(groups.items(), key=lambda x: -len(x[1])))
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "브랜드별 공구 일정 모음",
           "dateModified": TODAY.isoformat(), "url": SITE + "/gonggu/"}]
    return page("키워드·브랜드별 공구 일정 모음 — 영양제·칼마디·전집 공구 언제? | 공구모아",
                f"인스타 공구 일정을 브랜드별로 정리. {len(stats)}개 브랜드의 진행 중·오픈 예정 공구를 매일 업데이트해요.",
                "/gonggu/", body, ld)


# ---------------- 실행 ----------------

def main():
    args = sys.argv[1:]
    if "--items" in args:  # 로컬 테스트
        raw = json.load(open(args[args.index("--items") + 1]))
        vip = [d.get("insta", "").lower() for d in raw if str(d.get("hl", "")).upper() == "Y"]
    else:
        raw, vip = fetch_items()
    vip = set(str(v).lower().lstrip("@") for v in vip)
    items = norm_items(raw)
    inpock, qna = load_inpock(), load_qna()
    brands = json.load(open(os.path.join(ROOT, "scripts", "aeo_brands.json")))["brands"]
    print(f"공구 {len(items)}건, 브랜드 {len(brands)}개, PICK {len(vip)}명")

    per, subs = {}, {}
    for b in brands:
        m = matcher(b.get("match") or [b["name"]])
        per[b["name"]] = [d for d in items if m(d["name"])]
        c = collections.Counter(d["sub"] for d in per[b["name"]] if d["sub"])
        subs[b["name"]] = c.most_common(1)[0][0] if c else ""
    livecount = {n: sum(1 for d in v if d["end"] >= TODAY) for n, v in per.items()}

    # 키워드
    kws = json.load(open(os.path.join(ROOT, "scripts", "aeo_keywords.json")))["keywords"]
    kwitems = {}
    for k in kws:
        words = [w.lower() for w in k.get("match", [])]
        kwitems[k["name"]] = [d for d in items if (k.get("sub") and d["sub"] == k["sub"]) or any(w in d["name"].lower() for w in words)]
    kwlive = {n: sum(1 for d in v if d["end"] >= TODAY) for n, v in kwitems.items()}
    kwtitle = {k["name"]: (k.get("title") or k["name"]) for k in kws}
    def kw_of(lst, skip=None, limit=10):
        ids = set(map(id, lst))
        hit = [(n, sum(1 for d in v if id(d) in ids)) for n, v in kwitems.items() if n != skip]
        return [(n, kwtitle[n], kwlive[n]) for n, c in sorted(hit, key=lambda x: -x[1]) if c][:limit]

    stats, urls = [], []
    for b in brands:
        n = b["name"]
        related = [(r, livecount[r]) for r in sorted(per, key=lambda r: -livecount[r])
                   if r != n and subs[r] and subs[r] == subs[n]][:10]
        path, doc, live = brand_page(b, per[n], vip, inpock, qna.get(n), related, kw_of(per[n], limit=8))
        out = os.path.join(ROOT, "gonggu", n)
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, "index.html"), "w").write(doc)
        stats.append((n, live, subs[n]))
        urls.append(path)

    kstats = []
    for k in kws:
        n = k["name"]
        if not kwitems[n]:
            continue
        ids = set(map(id, kwitems[n]))
        bin_ = sorted(((b, livecount[b]) for b in per if any(id(d) in ids for d in per[b])), key=lambda x: -x[1])[:16]
        path, doc, live = keyword_page(k, kwitems[n], vip, inpock, bin_, kw_of(kwitems[n], skip=n, limit=10))
        out = os.path.join(ROOT, "gonggu", n)
        if os.path.exists(os.path.join(out, "index.html")) and n in per:
            continue   # 브랜드 이름과 겹치면 브랜드 페이지 우선
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, "index.html"), "w").write(doc)
        kstats.append((n, kwtitle[n], live))
        urls.append(path)

    open(os.path.join(ROOT, "gonggu", "index.html"), "w").write(index_page(stats, kstats))

    # 사이트맵
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, f, p in [("/", "daily", "1.0"), ("/gonggu/", "daily", "0.9")] + [(u, "daily", "0.8") for u in urls]:
        sm.append(f"  <url><loc>{SITE}{u}</loc><lastmod>{TODAY.isoformat()}</lastmod><changefreq>{f}</changefreq><priority>{p}</priority></url>")
    sm.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write("\n".join(sm) + "\n")

    # llms.txt (AI 검색용 안내 파일)
    live_list = sorted([s for s in stats if s[1]], key=lambda s: -s[1])
    llms = [f"# 공구모아 (gonggumoa.com)", "",
            "> 인스타그램 인플루언서 공동구매(공구) 일정을 매일 모아 보여주는 서비스. "
            "브랜드별 '공구 언제?' 페이지에 진행 중·오픈 예정·최근 공구 일정이 정리되어 있습니다.", "",
            f"업데이트: {TODAY.isoformat()}", "", "## 키워드별 공구 모음"]
    llms += [f"- [{t} 공구]({SITE}{slug_url(n)}): 진행 중·예정 {c}건" for n, t, c in kstats]
    llms += ["", "## 브랜드별 공구 일정", f"- [전체 목록]({SITE}/gonggu/)"]
    llms += [f"- [{n} 공구 일정]({SITE}{slug_url(n)}): 진행 중·예정 {c}건" for n, c, _ in live_list]
    llms += [f"- [{n} 공구 일정]({SITE}{slug_url(n)})" for n, c, _ in stats if not c]
    open(os.path.join(ROOT, "llms.txt"), "w").write("\n".join(llms) + "\n")
    print(f"완료: 페이지 {len(urls)}개(키워드 {len(kstats)}), 진행/예정 있는 브랜드 {len(live_list)}개")


if __name__ == "__main__":
    main()
