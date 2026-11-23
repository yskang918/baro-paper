---
name: thesis-format
description: 사용자가 그때 준 제출 양식(견본 hwpx·hwp, 또는 지침 문서 pdf·hwp·docx)을 정확히 읽어 그 서식 그대로 원고를 한글(hwpx) 파일로 조판하고, 맞게 됐는지 값과 쪽 그림으로 대조한다. "학교 양식으로", "hwpx로 만들어", "논문 양식 맞춰", "한글 파일로", start 5·9단계에서 사용.
---

# 제출 양식 조판

도구: `python "${CLAUDE_PLUGIN_ROOT}/skills/thesis-format/scripts/hwpx_tool.py" <명령>` (`python3`도 됨)

**정해 둔 양식은 없다.** 매번 사용자가 준 양식을 읽는다. 짐작으로 채우지 않고, 모르는 값은 묻는다.

## 1. 양식 받기
AskUserQuestion으로 무엇이 있는지 묻는다.
- (가장 정확) **견본 파일**: 그 학교·학회 양식으로 실제 작성된 hwpx(또는 hwp) — 선배 논문 파일, 학교가 준 서식 파일
- **지침 문서**: "본문 신명조 11pt, 줄간격 180" 같은 규칙이 글로 적힌 pdf·hwp·docx
- 둘 다 있으면 둘 다 받는다. 견본 값이 기준이고, 지침과 다르면 알려 준다.

hwp는 hwpx로 바꾼다(Windows+한글+보안 모듈): `hwpx_tool.py convert 양식.hwp -o 양식.hwpx`. 안 되면 사용자에게 한글에서 "다른 이름으로 저장 → HWPX"를 부탁한다.

## 2-A. 견본 파일이 있을 때
```bash
python hwpx_tool.py profile 견본.hwpx -o 08_제출/양식분석.json --md 08_제출/양식분석.md --map-out 08_제출/map.json
```
- `양식분석.md`를 보여 준다: 용지·여백·쪽번호, 이름 붙은 스타일, **실제 쓰인 문단 서식과 표본 글**, 역할 추천.
- 추천은 표본 글 모양으로 짐작한 것이다. 표본을 보여 주며 확인받는다. 특히 **추천하지 못한 역할**(인용, 목록, 표 안 글자, 표·그림을 담는 문단 등)은 표본 표에서 맞는 서식 번호를 골라 달라고 하거나, 비슷한 것을 제안해 확인받는다.
- 견본이 지침 설명 문서인지(본문에 "(신명조 17pt, 진하게)" 같은 설명이 적혀 있음) 진짜 논문 견본인지 먼저 본다. **설명 문서라면 2-B로 간다.**
- 확정된 `map.json` 형식: 역할마다 `{"style": "스타일 id", "paraPr": "문단 모양 id", "charPr": "글자 모양 id"}`. 스타일 이름으로도 된다: `{"style_name": "본문"}`. `_options`: `chapter_page_break`(장마다 새 쪽), `figure_caption_below`(그림 제목을 그림 아래).

## 2-B. 지침 문서만 있을 때
1. 지침을 읽는다(pdf·docx는 markitdown, hwpx는 그대로, hwp는 convert 뒤).
2. 규칙을 하나씩 `spec.json`으로 옮긴다. **규칙마다 `source`에 지침의 쪽·줄·원문을 적는다.**
```json
{"page": {"paper_mm": [210, 297], "margin_mm": {"top": 40, "bottom": 40, "left": 37, "right": 37, "header": 8, "footer": 12, "gutter": 0}},
 "_options": {"chapter_page_break": true, "figure_caption_below": true},
 "roles": {"chapter": {"font": "신명조", "size_pt": 17, "bold": true, "align": "CENTER", "line_spacing": 180, "space_after_pt": 43, "source": "p.3 'Ⅰ. (신명조 17pt, 진하게, 가운데 정렬)'"},
           "body": {"font": "신명조", "size_pt": 11, "align": "JUSTIFY", "line_spacing": 180, "indent_chars": 2, "source": "p.3 '본문 신명조 11pt(줄간격 180)', '2칸 들여 시작'"}}}
```
   쓸 수 있는 값: font, font_latin, size_pt, bold, italic, align(JUSTIFY/LEFT/CENTER/RIGHT), line_spacing(%), indent_pt 또는 indent_chars, left_pt, right_pt, space_before_pt, space_after_pt, page_break_before, keep_with_next, spacing_pct(자간), ratio_pct(장평), style_name.
3. **지침에 없는 값·애매한 값**("두 줄 띄움"을 몇 pt로 볼지, 표 제목 서식 등)은 목록으로 보여 주고 사용자가 정하게 한다. 정한 값은 source에 "사용자 결정"이라고 적는다.
4. 양식 파일을 만든다. 바탕 파일(`--base`)은 사용자가 준 hwpx가 있으면 그것, 없으면 `${CLAUDE_PLUGIN_ROOT}/skills/thesis-format/assets/blank.hwpx`:
```bash
python hwpx_tool.py spec --spec spec.json --base 바탕.hwpx -o 08_제출/양식.hwpx --map-out 08_제출/map.json
```
   글꼴 이름은 지침에 적힌 대로 넣는다. 그 글꼴이 사용자 컴퓨터에 없으면 한글이 다른 글꼴로 보여 줄 수 있다고 알린다.

## 3. 원고 준비 (Markdown)
`#` 장, `##` 절, `###` 항, `####` 목 / 빈 줄로 문단 / `**굵게**` / `> ` 긴 인용 / `- ` 목록 / 표는 `<표 Ⅱ-1> 제목` 줄 다음에 Markdown 표 / 그림은 `![[그림 Ⅱ-1] 제목](그림.png)` / 쪽 나눔 `<!-- pagebreak -->` / `# 참고문헌` 아래 문단은 참고문헌 항목 / `출처:`·`※`로 시작하면 주석.

## 4. 조판과 대조
```bash
python hwpx_tool.py build --template 08_제출/양식.hwpx(또는 견본.hwpx) --map 08_제출/map.json --md 원고.md -o 08_제출/결과.hwpx
python hwpx_tool.py verify --template <같은 양식> --map 08_제출/map.json --out 08_제출/결과.hwpx --md 원고.md -o 08_제출/대조.md
```
- 2-B(지침 문서)로 만든 양식이면 `verify`에 `--spec spec.json`을 꼭 붙인다. 지침에서 뽑은 값과 실제 파일 값이 같은지 역할마다 대조한다.
- `verify`: 쪽 설정·쪽번호가 견본과 같은지, 역할마다 글꼴·크기·정렬·줄간격이 양식 정의와 같은지, map에 없는 서식을 쓴 문단, 표·그림 번호가 이어지는지, 원고 글이 빠졌는지.
- 경고(`warnings`)에 "역할이 map에 없어 대신 넣음"이 있으면 그 역할을 map에 정해 다시 조판한다.

## 5. 눈으로 대조 (Windows + 한글 + 보안 모듈이 있을 때)
```bash
python hwpx_tool.py render 08_제출/결과.hwpx --out-dir 08_제출/쪽그림
python hwpx_tool.py render 견본.hwpx --out-dir 08_제출/견본쪽그림
```
쪽 그림을 Read로 열어 견본과 나란히 본다: 제목 위치, 들여쓰기, 표 모양, 쪽 넘김, 쪽번호. 다르면 map이나 spec을 고쳐 다시 한다(최대 3번). 보안 모듈이 없으면 setup 스킬 4번을 안내하고, 사용자가 한글로 직접 열어 보게 한다.

## 6. 보고
`대조.md`를 바탕으로 세 가지로 나눠 알린다: **맞춘 항목 / 사용자가 정한 항목 / 확인하지 못한 항목**(예: 표지·인준서·목차는 따로 만들어야 함, 견본 중간의 머리말 변경은 옮기지 않음). 표지·목차는 한글에서 마지막에 넣는 것이 정확하다고 안내한다.

## 한계 (사용자에게 숨기지 않는다)
- 한 섹션(본문)만 조판한다. 표지·인준서·초록·목차처럼 쪽 설정이 다른 부분은 견본의 해당 부분을 쓰거나 한글에서 붙인다.
- 각주, 수식, 셀 병합 표는 아직 지원하지 않는다(표는 단순 표로 들어간다).
- 글꼴 파일이 없는 컴퓨터에서는 다른 글꼴로 보일 수 있다(파일 안 서식 값은 맞음).
