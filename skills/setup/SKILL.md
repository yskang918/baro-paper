---
name: setup
description: 바로논문 처음 세팅과 점검. 필요한 파이썬 패키지·플러그인(insane-research, academic-research-skills) 설치, KCI API 키 등록, 한글 자동화 보안 모듈 안내. "세팅", "설치", "KCI 키", "처음 시작" 요청이나 start 스킬의 점검에서 할 일이 나왔을 때 사용.
---

# 바로논문 세팅

스크립트: `${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py` (`python`이 없으면 `python3`)

## 1. 점검
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py" check
```
결과를 쉬운 말로 표로 보여 준다: 된 것 / 할 것 / 선택.

파이썬이 없거나 3.9보다 낮으면: Windows는 https://www.python.org/downloads/ 에서 설치하면서 "Add python.exe to PATH"를 체크하라고 안내하고, macOS는 `brew install python` 또는 python.org 설치를 안내한다. 설치 후 Claude Code를 다시 시작하라고 한다.

`python_command_for_mcp`가 false이면(주로 macOS) 학술 검색 도구가 켜지지 않는다. 사용자에게 터미널에서 `ln -s "$(which python3)" /usr/local/bin/python`(관리자 암호 필요) 또는 python.org 설치판으로 `python` 명령을 만들게 안내하고, 사용자가 직접 실행하게 한다.

## 2. 설치 (한 번에 묻고 진행)

AskUserQuestion으로 "필요한 것을 설치할까요?"를 한 번 묻고, 동의하면 차례로 실행한다.
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py" install-python
python "${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py" install-plugins
```
- install-python: pandas·scipy·statsmodels·matplotlib·openpyxl·pymupdf·markitdown (사용자 영역에 설치)
- install-plugins: `insane-research`(넓은 조사, MIT), `academic-research-skills`(집필·심사, CC BY-NC 4.0)를 원본 저장소에서 설치. 설치 후 **Claude Code를 다시 시작해야** 보인다고 알린다.
- 실패하면 로그 끝부분을 보여 주고, 사용자가 직접 실행할 명령을 `! 명령` 형태로 알려 준다.

## 3. OpenAlex 키 (강력 권장)

OpenAlex는 키가 없으면 **같은 인터넷(학교·집 공유기)을 쓰는 사람 모두가 작은 하루 한도를 나눠 쓴다.** 문헌 조사 한 번에도 다 떨어질 수 있다(한국 시간 오전 9시에 다시 채워짐). 키는 무료다.
1. 사용자에게 설명하고 동의를 받는다: "OpenAlex에 이메일 주소를 보내 무료 키를 요청합니다. 메일로 온 링크를 누르면 키가 켜집니다. 보낼까요?" — **동의 없이 이메일을 보내지 않는다.** 이메일 주소도 사용자에게 직접 받는다(짐작해서 넣지 않음).
2. 동의하면:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py" request-openalex-key "사용자이메일"
```
3. 키가 저장되지 않았거나 이미 키가 있으면: `set-openalex-key "키"`. 직접 받는 방법: https://help.openalex.org/api/authentication/
4. 메일 링크를 누른 뒤 Claude Code를 다시 시작하라고 안내한다.

## 4. KCI API 키 (선택, 국내 논문 검색에 권장)

없어도 OpenAlex로 국내 학술지 일부를 찾을 수 있다고 먼저 말한다. 원하면:
1. https://open.kci.go.kr 접속 → 로그인 → OPEN API → 키 신청 (승인되면 마이페이지에서 키 확인)
2. 키를 받으면 대화창에 붙여 달라고 하고 저장한다:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py" set-kci-key "받은키"
```
키는 이 컴퓨터의 `~/.baro-paper/config.json`에만 저장된다고 알린다. 저장 뒤 Claude Code를 다시 시작하면 baro-scholar가 새 키를 읽는다.

## 5. 한글 보안 모듈 (선택, Windows + 한글이 있을 때만)

만든 hwpx를 한글 프로그램으로 PDF·쪽 그림으로 그려 견본과 눈으로 대조할 때 필요하다. 없으면 파일 안의 값 대조만 한다.
이 모듈은 한글이 자동화로 파일을 열 때마다 띄우는 "접근 허용" 창을 생략하게 해 주므로, **사용자가 직접 실행하도록** 안내한다(Claude가 대신 실행하지 않는다). 설명: 한컴 공식 저장소(hancom-io/devcenter-archive)의 보안 모듈을 `~/.baro-paper/hancom`에 받고, 사용자 레지스트리(HKCU\Software\HNC\HwpAutomation\Modules)에 등록한다. 되돌리려면 그 값과 폴더를 지우면 된다.

사용자에게 그대로 입력하라고 보여 줄 명령(경로는 실제 경로로 바꿔서):
```
! python "<플러그인 경로>/skills/setup/scripts/setup.py" install-hancom
```

## 6. 끝

다시 `check`를 돌려 결과를 보여 주고, 다시 시작이 필요한지 알린 뒤 "연구 아이디어를 말씀해 주세요"로 start 1단계에 들어간다.
