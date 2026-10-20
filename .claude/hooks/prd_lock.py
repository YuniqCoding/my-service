"""PRD 자물쇠 — AI가 폴더 맨 위 PRD.md 를 Write·Edit 하거나 명령으로 바꾸려 하면 막는 PreToolUse 훅."""
import json
import os
import re
import sys

TITLE = "PRD 자물쇠"
MESSAGE = "[기획서는 직접 고쳐 주세요]"
REASON = "PRD.md 는 잠겨 있으니 고치지 말고 바꿀 내용을 제안만 하라"

# 명령 글자 안에서 prd.md 로 끝나는 경로를 찾는다 (큰따옴표 · 작은따옴표 · 따옴표 없음)
PATH_RE = re.compile(
    r'"([^"\n]*?prd\.md)"|\'([^\'\n]*?prd\.md)\'|([^\s"\'|;&<>=(),]*prd\.md)(?![\w.-])',
    re.IGNORECASE,
)
# 명령 맨 앞에 올 때만 "바꾸는 명령" 으로 보는 짧은 이름들
WRITE_FIRST = {
    "tee", "rm", "mv", "touch", "truncate", "dd", "del", "erase", "ren", "rename", "move",
    "sc", "ac", "ri", "mi", "rni", "ni", "clc",
}
COPY_FIRST = {"cp", "copy", "cpi", "copy-item"}
# 명령 어디에 있든 "바꾸는 명령" 으로 보는 이름과 코드 조각
WRITE_ANYWHERE = re.compile(
    r"(?<![\w-])(set-content|add-content|out-file|clear-content|remove-item|move-item"
    r"|rename-item|new-item|tee-object)(?![\w-])"
    r"|writealltext|writealllines|writeallbytes|appendalltext|appendalllines"
    r"|write_text|write_bytes|\.write\(|open\([^)]*,\s*[\"'][wax+]",
    re.IGNORECASE,
)
INPLACE_FLAG = re.compile(r"\s(-[a-z]*i[a-z.]*|--in-place)\b", re.IGNORECASE)


def is_prd(file_path, base_dir):
    """고치려는 파일이 폴더 맨 위 PRD.md 인지 본다. 대소문자는 가리지 않는다."""
    if not file_path:
        return False
    if not os.path.isabs(file_path):
        file_path = os.path.join(base_dir, file_path)
    target = os.path.normcase(os.path.abspath(file_path))
    prd = os.path.normcase(os.path.abspath(os.path.join(base_dir, "PRD.md")))
    return target == prd


def path_is_prd(token, cwd, base_dir):
    """명령 안의 경로 글자가 폴더 맨 위 PRD.md 를 가리키는지 본다."""
    if "$" in token or "%" in token:  # 변수가 섞여 풀 수 없으면 파일 이름만 본다
        return os.path.basename(token.replace("\\", "/")).lower() == "prd.md"
    token = re.sub(r"^/([a-zA-Z])/", r"\1:/", token)  # Git Bash 의 /c/... 를 C:/... 로
    if not os.path.isabs(token):
        token = os.path.join(cwd, token)
    return is_prd(token, base_dir)


def command_writes_prd(command, cwd, base_dir):
    """명령이 PRD.md 를 바꾸는지 본다. 읽기만 하는 명령은 False."""
    for seg in re.split(r"\|\||&&|[|;\n]", command):
        hits = [m for m in PATH_RE.finditer(seg)
                if path_is_prd(m.group(1) or m.group(2) or m.group(3), cwd, base_dir)]
        if not hits:
            continue
        if any(re.search(r">>?\s*$", seg[:m.start()]) for m in hits):
            return True  # > PRD.md , >> PRD.md
        if WRITE_ANYWHERE.search(seg):
            return True
        words = seg.strip().lstrip("({$& ").split()
        first = os.path.basename(words[0].replace("\\", "/")).lower() if words else ""
        if first.endswith(".exe"):
            first = first[:-4]
        if first in WRITE_FIRST:
            return True
        if first in ("sed", "perl") and INPLACE_FLAG.search(seg):
            return True
        if first in COPY_FIRST:  # 복사는 PRD.md 가 받는 쪽(맨 뒤)일 때만 막는다
            last = hits[-1]
            if not seg[last.end():].strip() or re.search(r"-destination\s+$", seg[:last.start()], re.IGNORECASE):
                return True
    return False


def show_warning():
    """화면 한가운데, 다른 창보다 맨 앞에 경고창을 띄우고 [확인]을 기다린다."""
    import tkinter as tk

    root = tk.Tk()
    root.title(TITLE)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    tk.Label(root, text=MESSAGE, font=("Malgun Gothic", 12), padx=40, pady=24).pack()
    tk.Button(root, text="확인", width=10, command=root.destroy).pack(pady=(0, 18))

    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.lift()
    root.focus_force()
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)  # 알림 소리 한 번
    except Exception:
        pass  # 소리를 못 내도 창은 그대로 띄운다
    root.bind("<Return>", lambda e: root.destroy())
    root.mainloop()


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    base_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    tool_input = data.get("tool_input") or {}

    if data.get("tool_name") in ("Bash", "PowerShell"):
        cwd = data.get("cwd") or base_dir
        blocked = command_writes_prd(tool_input.get("command", ""), cwd, base_dir)
    else:
        blocked = is_prd(tool_input.get("file_path", ""), base_dir)

    if not blocked:
        sys.exit(0)  # PRD.md 를 바꾸는 것이 아니면 그냥 통과

    try:
        show_warning()
    except Exception:
        pass  # 창을 못 띄워도 막는 것은 그대로 한다

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
