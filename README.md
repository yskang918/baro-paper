# 바로논문 (baro-paper)

관심 분야의 **연구 트렌드와 빈틈을 함께 브레인스토밍**하거나 연구 아이디어 하나로 시작해 **문헌 조사 → 연구 필요성·근거·연구 세팅 → 할지 말지 판단 → 계획서 → 집필·분석·시각화·심사 → 학교 양식 그대로 한글(hwpx) 파일**까지 이어 주는 Claude Code 플러그인입니다. 연구 시간을 아끼기 위한 도구이고, 결정은 연구자가 합니다. 단계마다 결과 파일을 남기고, 결정할 곳에서 멈추고 묻습니다.

> 개인 연구용·비상업 도구입니다(CC BY-NC 4.0). 설문 응답·데이터·논문을 지어내지 않습니다. 인용 문헌은 학술 DB에서 실제로 있는지 확인합니다.

## 설치

Claude Code(유료 구독 필요)에서 아래 두 줄을 차례로 입력합니다.

```
/plugin marketplace add yskang918/baro-paper
/plugin install baro-paper@baro-paper
```

Claude Code를 다시 시작한 뒤 이렇게 시작합니다.

```
/baro-paper:start
```

처음 실행하면 필요한 것을 점검하고, 동의를 받아 자동으로 설치합니다(파이썬 패키지, 함께 쓰는 플러그인 2개). 파이썬 3.9 이상이 필요합니다. 없으면 설치 방법을 안내합니다.

## 무엇을 하나요

| 단계 | 하는 일 | 결과 파일 |
|---|---|---|
| 0 브레인스토밍 | 분야의 연도별 논문 수·뜨는 주제·핵심 논문, 연구 흐름, 빈틈(대상·방법·이론·분야 간) → 아이디어 후보 5~10개를 함께 고르기 | `연구/_아이디어탐색_<분야>/` |
| 1 아이디어 | 질문으로 대상·기간·자료를 확인 | `00_아이디어.md` |
| 2 문헌 | KCI·OpenAlex 검색 + insane-research 넓은 조사, 모든 문헌 실제 존재 확인 | `01_문헌/` |
| 3 연구 설계 | 필요성(근거)·연구문제·방법·일정·윤리 | `02_연구설계.md` |
| 4 판단 | 새로움·실행 가능성·윤리 등 8개 기준 점수, 가장 강한 반론과 살릴 방법 → 진행 여부 결정 | `03_판단보고서.md` |
| 5 계획서 | 연구계획서 초안 | `04_연구계획서.md` |
| 6 집필 | 장별 개요 승인 후 집필(한국어 논문 규칙, 문체 프로필) | `05_원고/` |
| 7 분석 | 받은 실제 자료만 분석, 결과표와 한글 그림 | `06_분석/` |
| 8 심사 | 여러 관점 심사와 고칠 목록 | `07_심사/` |
| 9 양식 | 받은 견본·지침을 그대로 읽어 hwpx 조판, 값 대조·쪽 그림 대조 | `08_제출/` |

결과는 작업 폴더의 `연구/<주제>/`에 쌓이고, `진행상태.md`로 언제든 이어서 할 수 있습니다("이어서 하자").

## 명령

| 명령 | 용도 |
|---|---|
| `/baro-paper:start` | 처음부터 또는 이어서 |
| `/baro-paper:ideate` | 트렌드·빈틈으로 연구 아이디어 브레인스토밍 |
| `/baro-paper:setup` | 세팅 점검·설치, KCI 키 등록 |
| `/baro-paper:idea-review` | 할지 말지 판단 보고서만 |
| `/baro-paper:thesis-format` | 학교 양식으로 hwpx 만들기만 |
| `/baro-paper:style-learning` | 내 글·대화 기록으로 문체 프로필 만들기 |
| `/baro-paper:data-analysis` | 자료 분석·그림만 |
| `/baro-paper:thesis-writing-ko` | 한국어 논문 문체·인용·표기 규칙 |

## 학교 양식 (hwpx)

정해 둔 양식이 없습니다. 그때그때 주는 양식을 읽습니다.
- **견본 파일**(그 양식으로 쓴 hwpx/hwp)을 주면 파일 안의 실제 값(용지·여백·글꼴·크기·줄간격·들여쓰기·쪽번호)을 그대로 읽고, 장·절·본문·표 제목 같은 역할을 표본 글로 추천한 뒤 확인을 받습니다.
- **지침 문서**만 주면 규칙을 하나씩 뽑아 출처(쪽·원문)와 함께 규칙표로 만들고, 지침에 없거나 애매한 값은 묻습니다.
- 조판 뒤 값 대조 보고서(맞춘 항목 / 사용자가 정한 항목 / 확인 못 한 항목)를 남깁니다. Windows에 한글이 있으면 PDF·쪽 그림으로 견본과 눈으로도 대조합니다.
- 아직 안 되는 것: 표지·인준서·목차(한글에서 마지막에 붙이기), 각주, 수식, 셀 병합 표.

## 문체 학습

자기 원고(hwpx·hwp·docx·pdf·md)나 논문 작업 대화 기록을 **직접 주면** 끝맺음·문장 길이·연결어·인용 방식·자주 고친 표현을 분석해 `문체프로필.md`를 만들고 집필에 적용합니다. 주지 않으면 만들지 않으며, 자료는 내 컴퓨터에만 남습니다.

## 선택 설정

- **KCI API 키**(국내 논문 검색 권장): https://open.kci.go.kr 에서 OPEN API 키를 신청하고 `/baro-paper:setup`에서 붙여 넣으면 `~/.baro-paper/config.json`에 저장됩니다. 없으면 OpenAlex로 국내 학술지 일부를 찾습니다.
- **한글 보안 모듈**(Windows + 한글, 쪽 그림 대조용): 한글이 자동화로 파일을 열 때 뜨는 허용 창을 생략해 주는 한컴 공식 모듈입니다. 보안 설정이라 사용자가 직접 실행합니다. Claude Code 입력창에 아래처럼 입력합니다(경로는 setup이 알려 줌).
  ```
  ! python "<플러그인 경로>/skills/setup/scripts/setup.py" install-hancom
  ```
- macOS에서 `python` 명령이 없고 `python3`만 있으면 학술 검색 도구가 켜지지 않을 수 있습니다. `/baro-paper:setup`에서 안내합니다.

## 함께 쓰는 도구와 라이선스

바로논문은 아래 도구를 **묶어서 나눠 주지 않고**, 세팅 때 각 원본 저장소에서 설치합니다.

| 도구 | 쓰는 곳 | 라이선스 |
|---|---|---|
| [insane-research](https://github.com/fivetaku/gptaku_plugins) (fivetaku) | 넓은 문헌·근거 조사 | MIT |
| [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) (Cheng-I Wu) | 집필·인용 점검·심사 | CC BY-NC 4.0 |
| [OpenAlex](https://openalex.org), [Crossref](https://www.crossref.org), [KCI Open API](https://open.kci.go.kr) | 문헌 검색·존재 확인 | 각 서비스 이용 조건 |
| [한컴 보안 모듈](https://github.com/hancom-io/devcenter-archive) | 한글 자동화(선택) | 한컴 배포 조건 |
| markitdown, pandas, scipy, statsmodels, matplotlib, PyMuPDF | 문서 읽기·분석·그림 | 각 라이선스 |

설계 참고: Stanford NLP AI-Researcher(MIT)의 아이디어 생성→중복 합치기→순위 흐름, Chain-of-Ideas(DAMO-NLP-SG, Apache-2.0)의 연구 흐름 사슬, research-gap-finder(MIT)의 빈틈 네 갈래, PaperOrchestra(Google Research)의 문헌 확인·개요 우선 방식, AI-Scientist(Sakana AI)의 새로움 판정 방식(코드는 쓰지 않음).

## 라이선스

바로논문 자체 코드와 문서: [CC BY-NC 4.0](LICENSE) — 출처를 밝히면 비상업 목적으로 자유롭게 쓰고 고칠 수 있습니다.
