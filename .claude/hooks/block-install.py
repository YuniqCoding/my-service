"""block-install — AI가 명령 창으로 도구를 설치·연결하려 하면 막는 PreToolUse 훅."""  # 이 파일이 하는 일을 적은 설명 글
import json  # JSON 글자를 읽고 쓰는 도구를 불러온다
import re  # 글자 모양(정규식)으로 찾는 도구를 불러온다
import sys  # 입력을 받고 프로그램을 끝내는 도구를 불러온다

TITLE = "설치 자물쇠"  # 경고창 제목
MESSAGE = "[도구 설치는 허락을 먼저 받아 주세요]"  # 경고창 안에 보이는 문장
REASON = "도구 이름과 쓰는 까닭을 답에 적고 사용자 허락을 받아라"  # 막을 때 AI에게 돌려보내는 이유

# 명령 글자에 이 낱말이 있으면 설치·연결 명령으로 본다
INSTALL_WORDS = [  # 설치·연결 낱말 목록을 시작한다
    "pip install", "npm install", "winget install", "choco install", "scoop install",  # 파이썬 · 노드 · 윈도우 프로그램 설치 낱말
    "conda install", "yarn add", "pnpm add", "Install-Module", "Install-Package",  # 그 밖의 설치 낱말과 PowerShell 설치 낱말
    "claude mcp add",  # Claude 에 새 도구(MCP)를 연결하는 낱말
]  # 낱말 목록을 닫는다
INSTALL_RE = re.compile(  # 위 낱말들을 한꺼번에 찾는 글자 모양을 만든다
    r"(?<![\w-])(" + "|".join(r"\s+".join(map(re.escape, w.split())) for w in INSTALL_WORDS) + r")(?![\w-])",  # 낱말 사이 띄어쓰기는 몇 칸이든 되고, 앞뒤에 다른 글자가 붙어 있으면 찾지 않는다
    re.IGNORECASE,  # 대문자 · 소문자를 가리지 않는다
)  # 글자 모양 만들기를 닫는다


def is_install(command):  # 설치 명령인지 알아보는 함수
    """명령 글자에 설치 낱말이 들어 있는지 본다."""  # 함수 설명 글
    return bool(INSTALL_RE.search(command or ""))  # 낱말을 찾았으면 참, 못 찾았으면 거짓을 돌려준다


def show_warning():  # 경고창을 띄우는 함수
    """화면 한가운데, 다른 창보다 맨 앞에 경고창을 띄우고 [확인]을 기다린다."""  # 함수 설명 글
    import tkinter as tk  # 창을 만드는 도구를 불러온다

    root = tk.Tk()  # 창을 하나 만든다
    root.title(TITLE)  # 창 제목을 넣는다
    root.resizable(False, False)  # 창 크기를 못 바꾸게 한다
    root.attributes("-topmost", True)  # 다른 창보다 항상 맨 앞에 두게 한다

    tk.Label(root, text=MESSAGE, font=("Malgun Gothic", 12), padx=40, pady=24).pack()  # 경고 문장을 창에 놓는다
    tk.Button(root, text="확인", width=10, command=root.destroy).pack(pady=(0, 18))  # 누르면 창이 닫히는 [확인] 버튼을 놓는다

    root.update_idletasks()  # 창 크기를 계산해 두게 한다
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()  # 창의 너비와 높이를 잰다
    x = (root.winfo_screenwidth() - w) // 2  # 화면 가로 한가운데가 되는 자리를 구한다
    y = (root.winfo_screenheight() - h) // 2  # 화면 세로 한가운데가 되는 자리를 구한다
    root.geometry(f"{w}x{h}+{x}+{y}")  # 창을 그 자리에 놓는다

    root.lift()  # 창을 위로 끌어올린다
    root.focus_force()  # 창에 입력이 가게 한다
    try:  # 소리 내기를 해 본다
        import winsound  # 윈도우 소리를 내는 도구를 불러온다
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)  # 알림 소리 한 번
    except Exception:  # 소리 내기에 실패하면
        pass  # 소리를 못 내도 창은 그대로 띄운다
    root.bind("<Return>", lambda e: root.destroy())  # 엔터 키를 눌러도 창이 닫히게 한다
    root.mainloop()  # 창을 띄우고 닫힐 때까지 기다린다


def main():  # 훅이 불릴 때 실행되는 함수
    data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))  # Claude Code 가 넘겨준 입력을 읽는다
    command = (data.get("tool_input") or {}).get("command", "")  # 입력에서 실행하려는 명령 글자를 꺼낸다

    if data.get("tool_name") not in ("Bash", "PowerShell") or not is_install(command):  # 명령 창 도구가 아니거나 설치 명령이 아니면
        sys.exit(0)  # 설치 명령이 아니면 그냥 통과

    try:  # 경고창 띄우기를 해 본다
        show_warning()  # 경고창을 띄운다
    except Exception:  # 경고창 띄우기에 실패하면
        pass  # 창을 못 띄워도 막는 것은 그대로 한다

    print(json.dumps({  # 막는다는 결정을 JSON 글자로 내보낸다
        "hookSpecificOutput": {  # 훅이 돌려주는 결정 묶음
            "hookEventName": "PreToolUse",  # 도구 실행 직전에 걸린 훅이라는 표시
            "permissionDecision": "deny",  # 실행을 거절한다
            "permissionDecisionReason": REASON,  # AI에게 돌려보내는 이유
        }  # 결정 묶음을 닫는다
    }))  # 내보내기를 닫는다
    sys.exit(0)  # 프로그램을 정상으로 끝낸다


if __name__ == "__main__":  # 이 파일을 직접 실행했을 때만
    main()  # main 함수를 실행한다
