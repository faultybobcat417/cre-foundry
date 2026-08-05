#!/usr/bin/env python3
import subprocess, time, sys, os

BROWSER = "Google Chrome"

def run_js(js_code):
    escaped = js_code.replace("\\", "\\\\").replace('"', '\\"')
    applescript = (
        'tell application "' + BROWSER + '"\n'
        + '    set jsResult to execute front window\'s active tab javascript "' + escaped + '"\n'
        + '    return jsResult\n'
        + 'end tell'
    )
    result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        err = result.stderr.strip()
        if "not allowed" in err.lower() or "authorization" in err.lower():
            return "__PERMISSION_ERROR__"
        return None
    return result.stdout.strip()

def is_generating():
    js = '(function(){return !!(document.querySelector(\'button[aria-label="Stop"]\') || document.querySelector(\'button[data-testid="stop-button"]\') || document.querySelector(\'button svg[class*="stop"]\'));)})()'
    return run_js(js) == "true"

def get_latest_code():
    js = '(function(){let msgs=document.querySelectorAll(\'[data-message-author-role="assistant"]\');if(!msgs.length)msgs=document.querySelectorAll(\'article\');let last=msgs[msgs.length-1];if(!last)return"__NO_MSG__";let pres=last.querySelectorAll(\'pre\');if(!pres.length)return"__NO_CODE__";let code=pres[pres.length-1].querySelector(\'code\');let text=code?code.innerText:pres[pres.length-1].innerText;return text;})()'
    return run_js(js)

def send_chatgpt_message(text):
    safe = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    js = (
        '(function(){let input=document.querySelector(\'#prompt-textarea\')||'
        + 'document.querySelector(\'textarea[placeholder*="message"]\')||'
        + 'document.querySelector(\'div[contenteditable="true"]\');'
        + 'if(!input)return"NO_INPUT";input.focus();'
        + 'if(input.tagName===\'TEXTAREA\'||input.tagName===\'INPUT\'){'
        + 'input.value="' + safe + '";'
        + 'input.dispatchEvent(new Event(\'input\',{bubbles:true}));'
        + 'input.dispatchEvent(new Event(\'change\',{bubbles:true}));}'
        + 'else if(input.isContentEditable){'
        + 'input.innerText="' + safe + '";'
        + 'input.dispatchEvent(new Event(\'input\',{bubbles:true}));}'
        + 'setTimeout(function(){'
        + 'let btn=document.querySelector(\'button[data-testid="send-button"]\')||'
        + 'document.querySelector(\'button[aria-label="Send"]\');'
        + 'if(btn&&!btn.disabled)btn.click();'
        + 'else input.dispatchEvent(new KeyboardEvent(\'keydown\',{key:\'Enter\',bubbles:true}));},300);'
        + 'return"SENT";})()'
    )
    return run_js(js)

def run_shell_command(cmd):
    print(f"   Executing: {cmd[:80]}{'...' if len(cmd)>80 else ''}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=os.getcwd())
        out, err, code = result.stdout, result.stderr, result.returncode
        output = out
        if err.strip():
            output += f"\n\n[stderr]:\n{err}"
        output += f"\n\n[exit code: {code}]"
        print(f"   Exit code: {code}")
        return output
    except subprocess.TimeoutExpired:
        return "Command timed out after 120 seconds"
    except Exception as e:
        return f"Error: {e}"

def main():
    print("=" * 60)
    print("🤖 ChatGPT Terminal Loop (Mac Native)")
    print("=" * 60)
    print(f"Browser: {BROWSER}")
    print(f"Project directory: {os.getcwd()}")
    print("Make sure ChatGPT is open in the FRONT tab of Chrome.")
    print("Press Ctrl+C to stop at any time.")
    print("=" * 60)
    input("\nPress Enter when ready...")
    last_code = None
    iteration = 0
    while True:
        iteration += 1
        print(f"\n{'─' * 50}")
        print(f"🔄 Iteration {iteration}")
        print(f"{'─' * 50}")
        print("⏳ Waiting for ChatGPT to finish typing...")
        wait_count = 0
        while is_generating() and wait_count < 60:
            time.sleep(1)
            wait_count += 1
        if is_generating():
            print("⚠️  Still generating after 60s, proceeding anyway...")
        time.sleep(2)
        print("📋 Reading latest code block...")
        code = get_latest_code()
        if code == "__PERMISSION_ERROR__":
            print("❌ macOS blocked Terminal from controlling Chrome.")
            print("   Go to: System Settings → Privacy & Security → Accessibility")
            print("   Add and enable 'Terminal' (or 'Python').")
            print("   Then run this script again.")
            break
        if code is None:
            print("❌ AppleScript failed. Is Chrome running with ChatGPT open?")
            time.sleep(5)
            continue
        if code == "__NO_MSG__":
            print("❌ No assistant message found. Retrying in 5s...")
            time.sleep(5)
            continue
        if code == "__NO_CODE__":
            print("✅ No code block found. ChatGPT appears to be done.")
            print("🛑 Loop stopped.")
            break
        if code == last_code:
            print("⏸ Same code as last time. Waiting for new message...")
            time.sleep(5)
            continue
        last_code = code
        display = code[:100].replace(chr(10), ' ')
        print(f"⚡ Command ({len(code)} chars):")
        print(f"   {display}{'...' if len(code)>100 else ''}")
        print("🖥️  Running in local terminal...")
        output = run_shell_command(code)
        reply = f"Here is the terminal output:\n\n```\n{output}\n```\n\nkeep going"
        print("📤 Sending output back to ChatGPT...")
        result = send_chatgpt_message(reply)
        print(f"   Send result: {result}")
        print(f"{'─' * 50}")
        print("✅ Round complete. Waiting for next response...")
        time.sleep(6)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Loop stopped by user.")
        sys.exit(0)
