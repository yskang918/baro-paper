# 카드(card.json) 형식

`make_card.py card.json -o 판단카드.html --open` 으로 한 장짜리 html을 만든다. 카드는 **한 화면에서 읽고 결정**하는 용도다. 문장은 짧고 쉽게, 항목은 3개 안팎으로. 숫자와 인용은 `자료/`의 확인된 것만 쓴다(카드에서 새로 지어내지 않음).

## 판단 카드 (start 4단계 끝)
```json
{
 "title": "연구 제목(짧게)",
 "date": "YYYY-MM-DD",
 "mode": "빠른 판단",
 "one_line": "무엇을 알아보는 연구인지 한 문장. **강조**는 두 군데까지",
 "verdict": "진행 | 조건부 진행 | 고쳐서 다시 | 보류",
 "verdict_reason": "결론 이유 1~2문장",
 "score": "평균 3.4 / 5",
 "rqs": [{"id": "RQ1", "type": "관계", "text": "02_RQ대응표.md의 문장 그대로", "answerable": "예 | 조건부 | 아니오"}],
 "why": [{"point": "해 볼 만한 이유 한 줄", "evidence": "근거(저자, 연도 / 숫자·출처)"}],
 "todo_before": ["결정 전에 확인할 것"],
 "risks": [{"risk": "걸림돌", "fix": "이렇게 하면 풀림"}],
 "cost": [{"label": "기간", "value": "…"}, {"label": "대상", "value": "…"}, {"label": "준비물", "value": "…"}, {"label": "사람", "value": "…"}, {"label": "승인", "value": "…"}],
 "scores": [{"name": "새로움", "score": 3}],
 "unverified": ["확인하지 못한 것"],
 "charts": [{"title": "그래프 제목", "path": "자료/그림.png"}],
 "files": [{"label": "펼쳐 볼 자료 이름", "path": "자료/02_RQ대응표.md"}]
}
```

## 아이디어 카드 (ideate 끝)
`"kind": "idea"`를 넣고 `verdict`는 비운다. `candidates`에 추천 순서대로 3개(많아도 5개):
```json
{"kind": "idea", "title": "분야 × 키워드 — 대상", "one_line": "트렌드와 빈틈 한 문장",
 "candidates": [{"rank": 1, "title": "후보 제목", "question": "연구 질문", "gap": "채우는 빈틈", "method": "대략적 방법",
                 "risk": "가장 큰 걸림돌", "scores": {"새로움": 4, "실행": 4, "관심": 5}, "feasible": "예 | 조건부 | 아니오"}],
 "why": [...], "todo_before": [...], "charts": [...], "unverified": [...], "files": [...]}
```
후보 점수·문장은 `자료/아이디어후보.md`의 값을 그대로 옮긴다.
