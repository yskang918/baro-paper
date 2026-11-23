#!/usr/bin/env python3
"""바로논문 세팅 점검·설치.

  python setup.py check                 지금 상태를 JSON으로 보여 준다(아무것도 바꾸지 않음)
  python setup.py install-python        분석·시각화·문서 읽기 파이썬 패키지 설치(pip --user)
  python setup.py install-plugins       insane-research, academic-research-skills 플러그인 설치
  python setup.py install-hancom        한글 자동화 보안 모듈 설치(Windows+한글, 한컴 공식 저장소에서 받음)
  python setup.py set-kci-key KEY       KCI Open API 키 저장(~/.baro-paper/config.json)
  python setup.py set-email EMAIL       OpenAlex 예의 요청용 연락처(선택)
  python setup.py request-openalex-key EMAIL  OpenAlex 무료 개인 키 요청(이메일로 확인 링크가 옴, 사용자 동의 후)
  python setup.py set-openalex-key KEY  OpenAlex 키 저장
"""
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

HOME = os.path.expanduser("~")
CONF_DIR = os.path.join(HOME, ".baro-paper")
CONF = os.path.join(CONF_DIR, "config.json")
PY_PKGS = ["pandas", "numpy", "scipy", "statsmodels", "matplotlib", "openpyxl", "pymupdf", "markitdown[pdf,docx,pptx,xlsx]"]
PLUGINS = [
    # (플러그인 이름, 마켓플레이스 이름, 마켓플레이스 주소)
    ("insane-research", "gptaku-plugins", "https://github.com/fivetaku/gptaku_plugins.git"),
    ("academic-research-skills", "academic-research-skills", "Imbad0202/academic-research-skills"),
]
HANCOM_ZIP = "https://github.com/hancom-io/devcenter-archive/raw/main/hwp-automation/%EB%B3%B4%EC%95%88%EB%AA%A8%EB%93%88(Automation).zip"


def out(obj):
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def load_conf():
    try:
        return json.load(open(CONF, encoding="utf-8"))
    except Exception:
        return {}


def save_conf(c):
    os.makedirs(CONF_DIR, exist_ok=True)
    json.dump(c, open(CONF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def run(cmd, timeout=600):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           shell=(os.name == "nt" and cmd[0] == "claude"))
        return p.returncode, (p.stdout + p.stderr).strip()
    except FileNotFoundError:
        return 127, f"{cmd[0]} 명령을 찾지 못함"
    except subprocess.TimeoutExpired:
        return 124, "시간 초과"


def has_module(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def installed_plugins():
    code, txt = run(["claude", "plugin", "list", "--json"], 120)
    if code != 0:
        return None, txt
    try:
        data = json.loads(txt[txt.find("["):]) if "[" in txt else json.loads(txt)
    except Exception:
        return None, txt[:300]
    names = set()
    for p in data if isinstance(data, list) else data.get("plugins", []):
        pid = p.get("id") or p.get("name") or ""
        names.add(pid.split("@")[0])
    return names, ""


def hancom_status():
    if os.name != "nt":
        return {"hangul": False, "module": False, "note": "Windows가 아니라 한글 자동화는 쓰지 않음(수치 대조만)"}
    import winreg
    hangul = False
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"HWPFrame.HwpObject")
        hangul = True
    except OSError:
        pass
    module = None
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\HNC\HwpAutomation\Modules")
        i = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(k, i)
                if os.path.exists(str(val)):
                    module = {"name": name, "path": val}
                i += 1
            except OSError:
                break
    except OSError:
        pass
    return {"hangul": hangul, "module": bool(module), "module_info": module}


def korean_font():
    try:
        from matplotlib import font_manager
        names = {f.name for f in font_manager.fontManager.ttflist}
        for f in ("Malgun Gothic", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR"):
            if f in names:
                return f
    except Exception:
        pass
    return None


def check():
    plugins, err = installed_plugins()
    conf = load_conf()
    res = {
        "os": platform.system(), "python": sys.version.split()[0], "python_ok": sys.version_info >= (3, 9),
        "python_packages": {m: has_module(m) for m in ("pandas", "scipy", "statsmodels", "matplotlib", "openpyxl", "fitz", "markitdown")},
        "korean_font_for_charts": korean_font(),
        "plugins": {p[0]: (p[0] in plugins) if plugins is not None else None for p in PLUGINS},
        "plugin_check_error": err or None,
        "hancom": hancom_status(),
        "kci_api_key": bool(os.environ.get("KCI_API_KEY") or conf.get("kci_api_key")),
        "openalex_api_key": bool(os.environ.get("OPENALEX_API_KEY") or conf.get("openalex_api_key")),
        "config_path": CONF,
        "git": shutil.which("git") is not None,
        "python_command_for_mcp": shutil.which("python") is not None,
    }
    todo = []
    if not res["python_ok"]:
        todo.append("파이썬 3.9 이상 설치 필요")
    if not res["python_command_for_mcp"]:
        todo.append("python 명령 없음: 학술 검색 도구(baro-scholar)가 'python'으로 실행됨 — macOS는 python.org 설치판 사용 또는 'python' 별칭 필요")
    if not all(res["python_packages"].values()):
        todo.append("install-python")
    if res["plugins"] and not all(v for v in res["plugins"].values() if v is not None):
        todo.append("install-plugins")
    if res["hancom"].get("hangul") and not res["hancom"].get("module"):
        todo.append("install-hancom(선택: 한글로 쪽 그림 대조)")
    if not res["openalex_api_key"]:
        todo.append("OpenAlex 키(권장: 없으면 같은 인터넷을 쓰는 사람과 하루 한도를 나눠 써서 조사 중 막힐 수 있음)")
    if not res["kci_api_key"]:
        todo.append("set-kci-key(선택: 없으면 OpenAlex로 대신)")
    res["todo"] = todo
    out(res)


def install_python():
    # 이미 있는 패키지는 건드리지 않는다(다른 프로그램 보호). 없는 것만 설치.
    mods = {"pandas": "pandas", "numpy": "numpy", "scipy": "scipy", "statsmodels": "statsmodels", "matplotlib": "matplotlib",
            "openpyxl": "openpyxl", "pymupdf": "fitz", "markitdown[pdf,docx,pptx,xlsx]": "markitdown"}
    need = [p for p in PY_PKGS if not has_module(mods.get(p, p))]
    if not need:
        out({"ok": True, "log_tail": "모두 이미 설치되어 있음"})
        return
    code, txt = run([sys.executable, "-m", "pip", "install", "--user", "--no-warn-script-location"] + need, 1800)
    out({"ok": code == 0, "log_tail": txt[-1500:]})


def install_plugins():
    log, ok = [], True
    plugins, _ = installed_plugins()
    code, mtxt = run(["claude", "plugin", "marketplace", "list"], 120)
    for name, market, src in PLUGINS:
        if plugins and name in plugins:
            log.append(f"{name}: 이미 설치됨")
            continue
        if market not in mtxt:
            c, t = run(["claude", "plugin", "marketplace", "add", src], 300)
            log.append(f"마켓플레이스 {market} 추가: {'성공' if c == 0 else '실패 ' + t[-300:]}")
            ok &= c == 0
        c, t = run(["claude", "plugin", "install", f"{name}@{market}", "-y"], 600)
        if c != 0 and "unknown option" in t.lower():
            c, t = run(["claude", "plugin", "install", f"{name}@{market}"], 600)
        log.append(f"{name} 설치: {'성공' if c == 0 else '실패 ' + t[-300:]}")
        ok &= c == 0
    out({"ok": ok, "log": log, "next": "Claude Code를 다시 시작해야 새 플러그인이 보입니다."})


def install_hancom():
    if os.name != "nt":
        out({"ok": False, "message": "Windows에서만 필요합니다."})
        return
    st = hancom_status()
    if not st["hangul"]:
        out({"ok": False, "message": "한글 프로그램이 설치되어 있지 않습니다. 한글 없이도 조판은 되고, 수치 대조만 합니다."})
        return
    if st["module"]:
        out({"ok": True, "message": "이미 등록됨", "module": st["module_info"]})
        return
    dest = os.path.join(CONF_DIR, "hancom")
    os.makedirs(dest, exist_ok=True)
    data = urllib.request.urlopen(urllib.request.Request(HANCOM_ZIP, headers={"User-Agent": "baro-paper"}), timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    dll = None
    for n in z.namelist():
        # zip 안 파일 이름 인코딩이 cp437로 읽히는 경우 대비
        if n.lower().endswith(".dll"):
            target = os.path.join(dest, os.path.basename(n.encode("cp437", "ignore").decode("cp949", "ignore") or n))
            with open(target, "wb") as f:
                f.write(z.read(n))
            if "filepathchecker" in os.path.basename(target).lower():
                dll = target
    if not dll:
        dlls = [os.path.join(dest, x) for x in os.listdir(dest) if x.lower().endswith(".dll")]
        dll = dlls[0] if dlls else None
    if not dll:
        out({"ok": False, "message": "zip 안에서 보안 모듈 DLL을 찾지 못했습니다.", "files": z.namelist()})
        return
    import winreg
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\HNC\HwpAutomation\Modules")
    winreg.SetValueEx(k, "FilePathCheckerModule", 0, winreg.REG_SZ, dll)
    out({"ok": True, "dll": dll, "registry": r"HKCU\Software\HNC\HwpAutomation\Modules\FilePathCheckerModule",
         "undo": r"레지스트리 값을 지우고 ~/.baro-paper/hancom 폴더를 지우면 원래대로 돌아갑니다."})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "check":
        check()
    elif cmd == "install-python":
        install_python()
    elif cmd == "install-plugins":
        install_plugins()
    elif cmd == "install-hancom":
        install_hancom()
    elif cmd == "set-kci-key":
        c = load_conf(); c["kci_api_key"] = sys.argv[2].strip(); save_conf(c)
        out({"ok": True, "saved": CONF, "note": "키는 이 컴퓨터의 설정 파일에만 저장됩니다."})
    elif cmd == "request-openalex-key":
        email = sys.argv[2].strip()
        req = urllib.request.Request("https://api.openalex.org/api-keys", data=json.dumps({"email": email}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "baro-paper"}, method="POST")
        try:
            body = json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")
        except Exception as e:
            out({"ok": False, "message": f"요청 실패: {e}. https://help.openalex.org/api/authentication/ 에서 직접 받으세요."})
            return
        key = body.get("api_key") or body.get("key") or (body.get("data") or {}).get("api_key") if isinstance(body, dict) else None
        if key:
            c = load_conf(); c["openalex_api_key"] = key; save_conf(c)
        out({"ok": True, "saved_key": bool(key), "response_keys": list(body)[:10] if isinstance(body, dict) else None,
             "next": "받은 메일의 링크를 누르면 키가 켜집니다. 키가 저장되지 않았으면 메일에 적힌 키를 set-openalex-key로 넣으세요."})
    elif cmd == "set-openalex-key":
        c = load_conf(); c["openalex_api_key"] = sys.argv[2].strip(); save_conf(c)
        out({"ok": True, "saved": CONF, "note": "키는 이 컴퓨터의 설정 파일에만 저장됩니다. Claude Code를 다시 시작하면 적용됩니다."})
    elif cmd == "set-email":
        c = load_conf(); c["contact_email"] = sys.argv[2].strip(); save_conf(c)
        out({"ok": True, "saved": CONF})
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
