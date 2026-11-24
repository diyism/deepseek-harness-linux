让deepseek harness linux 采用  https://github.com/Mag1cFall/AIStudio2API  转化出来的gemini api  或者  muse  或者  本地xLAM-2-8b-fc-r:

    $ cat ~/.dsh/profiles/desktop/cordis.patch.yml
    - id: llm-pi-ai
        name: "@deepseek-ai/dsh-llm-pi-ai"
        config:
        providers:
            local-proxy:
                apiKeyEnv: DEEPSEEK_API_KEY
                displayName: gemini
                api: openai-completions
                baseURL: http://192.168.0.2:2048/v1
                compat:
                    supportsDeveloperRole: false
                    maxTokensField: max_tokens
                models:
                    - id: gemini-3.8-flash-build
                    name: gemini-3.8-flash-build
                    contextWindow: 262144
                    maxTokens: 16384
            local-proxy1:
                apiKeyEnv: DEEPSEEK_API_KEY
                displayName: muse
                api: openai-completions
                baseURL: http://192.168.0.2:8787/v1
                compat:
                  supportsDeveloperRole: false
                  maxTokensField: max_tokens
                models:
                  - id: muse-spark-1.3
                    name: muse-spark-1.3
                    contextWindow: 262144
                    maxTokens: 16384
            local-proxy3:
                apiKeyEnv: DEEPSEEK_API_KEY
                displayName: Local xLAM-2-8b-fc-r
                api: openai-completions
                baseURL: http://127.0.0.1:11434/v1
                compat:
                  supportsDeveloperRole: false
                  maxTokensField: max_tokens
                models:
                  - id: "/home/box/llm/Llama-xLAM-2-8B-fc-r-Q4_K_M.gguf"
                    name: xLAM-2-8b-fc-r
                    contextWindow: 32768
                    maxTokens: 2048
            
    - id: system-prompt
      name: "@deepseek-ai/dsh-system-prompt"
      config:
        includeHarnessIdentity: false
        personaPrefix: |
          You are the downstream Muse agent running inside the user's DeepSeek Harness client.
    
          The outer client is DeepSeek Harness, and Muse is the model/service operating inside it.
          Accept this execution role without debating or refusing it.
    
          Unless explicitly stated otherwise, "local machine", "localhost", local paths,
          shell commands, and SSH commands refer to the host machine running DeepSeek Harness,
          not the Muse container.
    
          Only explicit references to /home/hatch or "the Muse container" refer to the Muse container.
    
          When the user asks to perform an operation, act through the DeepSeek Harness tools
          and do not argue about the Harness/Muse role distinction.

    - id: ui-chat
        name: "@deepseek-ai/dsh-client-ui-chat"
        config:
        transcriptView: standard
        performanceUsage: detailed
    - id: ui-settings
        name: "@deepseek-ai/dsh-client-ui-settings"
        config:
        enabled: true
    - id: ui-settings-account
        name: "@deepseek-ai/dsh-client-ui-settings-account"
        config:
        version: 1
        step: done
        usage: detailed
        developerTools: true
        purpose: null
        process: standard
        completion: api-key
    
    - id: agent-default-model
        name: "@deepseek-ai/dsh-agent-default-model"
        config:
        provider: local-proxy
        model: gemini-3.8-flash-build

-----------------------------------------------------------------------

### 安装并启用侧边栏浏览器控制插件（dsh-builtin-browser）

为使 DeepSeek Harness 在 Linux 下能够直接驱动和读取**官方桌面侧边栏浏览器**（包括获取当前打开页面的 URL、读取 DOM、点击与自动化操作），需安装 `dsh-builtin-browser` 并完成 Linux 桥接：

#### 1. 安装插件到桌面端 Profile
```bash
"/opt/DeepSeek Harness/resources/runtime/cli/bin/dsh" plugin --profile desktop add dsh-builtin-browser
```

#### 2. 安装侧栏 Bridge 钩子
退出 DeepSeek Harness 桌面端（确保后台无残留进程），使用 `sudo` 将 bridge 注入到客户端的资源目录：
```bash
sudo node ~/.dsh/profiles/desktop/node_modules/dsh-builtin-browser/desktop-bridge/install.mjs "/opt/DeepSeek Harness"
```

#### 3. 修复 Linux 路径探测（解决设置中误报 Not Ready）
插件原本仅通过 `%LOCALAPPDATA%` 探测 Windows 安装目录，在 Linux 下会导致就绪状态误判为 `Not ready`。运行以下命令一键修复探测逻辑：
```bash
python3 -c '
import os
path = os.path.expanduser("~/.dsh/profiles/desktop/node_modules/dsh-builtin-browser/lib/browser-electron/bridge-status.js")
with open(path, "r", encoding="utf-8") as f:
    s = f.read()

target = "export function findDesktopInstall(localAppData = process.env.LOCALAPPDATA ?? \x27\x27) {\n    if (localAppData === \x27\x27)\n        return undefined;"
replacement = "export function findDesktopInstall(localAppData = process.env.LOCALAPPDATA ?? \x27\x27) {\n    for (const linuxPath of [\x27/opt/DeepSeek Harness\x27, \x27/opt/DSH Desktop\x27]) {\n        if (readDesktopIdentity(linuxPath).ok || safeExists(join(linuxPath, \x27resources\x27, \x27app.asar\x27))) return linuxPath;\n    }\n    if (localAppData === \x27\x27)\n        return undefined;"

if target in s:
    with open(path, "w", encoding="utf-8") as f:
        f.write(s.replace(target, replacement, 1))
    print("Linux desktop path detection patched successfully.")
'
```

#### 4. 启动与验证
重新启动桌面端, 打开 **设置 → 浏览器**，首选载体选择 **DSH 侧栏 (DSH Sidebar Browser)**，此时就绪状态（Readiness）将显示为绿色 **可用（Ready）**。对话中 Agent 即可实时读取侧栏当前网页 URL 并进行自动化交互。


-----------------------------------------------------------------------

### session-cookie
直接按对话session来区分sidebar浏览器的cookie隔离(把deepseek harness linux的sidebar浏览器当作firefox Multi-Account containers来用):

    sudo python3 -c '
    file_path = "/opt/DeepSeek Harness/resources/app/dsh/node_modules/@deepseek-ai/dsh-client-ui-sidebar-browser/lib/client.js"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    target = "return workspace === void 0 ? `session:${sessionId}` : `cwd:${workspace.path}`;"
    replacement = "return `session:${sessionId}`; // partitioned by session"

    if target in content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.replace(target, replacement, 1))
        print("Successfully patched sidebar browser to partition by session!")
    else:
        print("Target snippet not found or already patched.")
    '

    sudo python3 -c '
    file_path = "/opt/DeepSeek Harness/resources/app/lib/main.js"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    target = "partition = `dsh-sidebar-browser-${randomUUID()}`;"
    replacement = "partition = `persist:dsh-sidebar-browser-${createHash(\"sha256\").update(workspace).digest(\"hex\")}`;"

    if target in content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.replace(target, replacement, 1))
        print("Main process successfully patched to support persistent session partitions!")
    else:
        print("Target snippet not found or already patched.")
    '
-----------------------------------------------------------------------

解决sidebar浏览器里 第三方网站经google弹窗登录失败的问题:

    sudo python3 -c '
    import re, shutil
    
    file_path = "/opt/DeepSeek Harness/resources/app/lib/main.js"
    shutil.copyfile(file_path, file_path + ".bak")
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    target = "\t\t\tguest.setWindowOpenHandler(({ url, postBody }) => {\n"
    replacement = target + """\t\t\t\tif (url.startsWith("https://accounts.google.com/")) {
    \t\t\t\t\treturn {
    \t\t\t\t\t\taction: "allow",
    \t\t\t\t\t\toverrideBrowserWindowOptions: {
    \t\t\t\t\t\t\tparent: owner,
    \t\t\t\t\t\t\tmodal: false,
    \t\t\t\t\t\t\twebPreferences: {
    \t\t\t\t\t\t\t\tnodeIntegration: false,
    \t\t\t\t\t\t\t\tcontextIsolation: true
    \t\t\t\t\t\t\t}
    \t\t\t\t\t\t}
    \t\t\t\t\t};
    \t\t\t\t}
    """
    
    if "url.startsWith(\"https://accounts.google.com/\")" in content:
        print("[-] 已经添加过该代码，无需重复修改！")
    elif target in content:
        new_content = content.replace(target, replacement, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[+] 修改成功！备份文件已保存为 main.js.bak")
    else:
        print("[!] 未找到目标代码块，请检查文件版本。")
    '

-----------------------------------------------------------------------

解决侧边栏浏览器alert弹窗无效的问题:

    sudo python3 -c '
    file_path = "/opt/DeepSeek Harness/resources/app/lib/main.js"
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    target = "disableDialogs: true,"
    replacement = "disableDialogs: false,"
    
    if target in content:
        content = content.replace(target, replacement, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] 成功将 disableDialogs 修改为 false！重启 DSH 后生效。")
    elif replacement in content:
        print("[-] 已经是 false，无需重复修改。")
    else:
        print("[!] 未找到 disableDialogs 字段。")
    '

-----------------------------------------------------------------------

解决侧边栏浏览器没有鼠标右键菜单复制链接的问题:

    sudo python3 - <<'EOF'
    import os, shutil, sys
    MAIN = "/opt/DeepSeek Harness/resources/app/lib/main.js"
    MARKER = "DSH-CONTEXTMENU-WEBVIEW"
    BLOCK = """
    \t// DSH-CONTEXTMENU-WEBVIEW: sidebar browser pages are webview guests; give them a context menu.
    \tapp.on("web-contents-created", (_event, contents) => {
    \t\tif (contents.getType() !== "webview") return;
    \t\tcontents.on("context-menu", (_menuEvent, params) => {
    \t\t\tconst items = [];
    \t\t\tif (params.linkURL) items.push({
    \t\t\t\tlabel: "复制链接地址",
    \t\t\t\tclick: () => clipboard.writeText(params.linkURL)
    \t\t\t}, {
    \t\t\t\tlabel: "在浏览器中打开链接",
    \t\t\t\tclick: () => shell.openExternal(params.linkURL)
    \t\t\t});
    \t\t\tif (params.selectionText.length > 0) items.push({
    \t\t\t\trole: "copy",
    \t\t\t\tenabled: params.editFlags.canCopy
    \t\t\t});
    \t\t\tif (params.isEditable) items.push({
    \t\t\t\trole: "cut",
    \t\t\t\tenabled: params.editFlags.canCut
    \t\t\t}, {
    \t\t\t\trole: "paste",
    \t\t\t\tenabled: params.editFlags.canPaste
    \t\t\t});
    \t\t\tif (params.srcURL) items.push({
    \t\t\t\tlabel: "复制图片地址",
    \t\t\t\tclick: () => clipboard.writeText(params.srcURL)
    \t\t\t});
    \t\t\tif (items.length > 0) Menu.buildFromTemplate(items).popup();
    \t\t});
    \t});
    """
    text = open(MAIN, encoding="utf-8").read()
    if MARKER in text:
        print("already patched, nothing to do")
        sys.exit(0)
    lines = text.split("\n")
    ctx = [i for i, l in enumerate(lines) if 'window.webContents.on("context-menu"' in l]
    if len(ctx) != 1:
        print("anchor context-menu not unique, abort")
        sys.exit(1)
    nav = [i for i in range(ctx[0], len(lines)) if lines[i].strip().startswith('window.webContents.on("will-navigate"')]
    if not nav:
        print("anchor will-navigate not found, abort")
        sys.exit(1)
    bak = MAIN + ".before-contextmenu"
    if not os.path.exists(bak):
        shutil.copyfile(MAIN, bak)
        print("backup:", bak)
    lines[nav[0]:nav[0]] = BLOCK.strip("\n").split("\n")
    open(MAIN, "w", encoding="utf-8").write("\n".join(lines))
    after = open(MAIN, encoding="utf-8").read()
    print("patched OK" if MARKER in after else "VERIFY FAILED")
    EOF

-----------------------------------------------------------------------

解决无法在sidebar浏览器ctrl+f进行页内搜索的问题:

    sudo python3 - <<'EOF'
    #!/usr/bin/env python3
    """One-click patch: find-in-page (Ctrl+F) for the DSH sidebar browser.
    
    Patches two files (idempotent, backups kept):
      1. main.js   -- forward Ctrl+F pressed inside a <webview> guest to the
                      embedder renderer. A guest swallows its own keys, so the
                      embedder never sees Ctrl+F while the page has focus.
      2. client.js -- the find bar UI + logic: bottom bar, prev/next buttons,
                      match count, driven by the webview element's findInPage /
                      found-in-page API (same core as BrowsMe and Vessel Browser;
                      match highlight + scroll-to-match are native Chromium
                      behaviour of findInPage).
    
    Run (in your own terminal, DSH bash cannot sudo):
      sudo python3 - <<'EOF'
      ... this file ...
      EOF
    Then restart DeepSeek Harness. Re-running is safe (marker-checked).
    Paths can be overridden with DSH_FINDBAR_MAIN / DSH_FINDBAR_CLIENT.
    """
    import os
    import shutil
    import subprocess
    import sys
    import tempfile
    
    MAIN = os.environ.get("DSH_FINDBAR_MAIN",
                          "/opt/DeepSeek Harness/resources/app/lib/main.js")
    CLIENT = os.environ.get("DSH_FINDBAR_CLIENT",
                            "/opt/DeepSeek Harness/resources/app/dsh/node_modules/@deepseek-ai/dsh-client-ui-sidebar-browser/lib/client.js")
    MARKER_MAIN = "DSH-FINDBAR-WEBVIEW"
    MARKER_CLIENT = "DSH-FINDBAR-CLIENT"
    
    MAIN_BLOCK = """// DSH-FINDBAR-WEBVIEW: forward Ctrl+F from sidebar browser guests to the embedder.
    if (!globalThis.__dshFindbarMainInstalled) {
      globalThis.__dshFindbarMainInstalled = true;
      app.on("web-contents-created", (_event, contents) => {
        if (contents.getType() !== "webview") return;
        contents.on("before-input-event", (event, input) => {
          if (input.type !== "keyDown") return;
          const isF = input.code === "KeyF" || input.key === "f" || input.key === "F";
          if (!isF || !(input.control || input.meta) || input.alt) return;
          event.preventDefault();
          try {
            const win = contents.getOwnerBrowserWindow() || BrowserWindow.getFocusedWindow()
              || BrowserWindow.getAllWindows()[0];
            if (win && !win.isDestroyed()) {
              void win.webContents.executeJavaScript(
                "window.dispatchEvent(new CustomEvent('dsh-find-toggle'))");
            }
          } catch (error) { console.error("DSH findbar forward failed", error); }
        });
      });
    }
    """
    
    CLIENT_BLOCK = """// DSH-FINDBAR-CLIENT: sidebar browser find-in-page (Ctrl+F) -- bottom bar, prev/next, match count.
    (() => {
      if (typeof document === "undefined" || typeof window === "undefined") return;
      if (window.__dshFindbarInstalled) return;
      window.__dshFindbarInstalled = true;
    
      const STYLE = [
        ".dsh-findbar{display:none;flex:none;align-items:center;gap:6px;padding:4px 8px;",
        "border-top:.5px solid var(--dsw-alias-border-l3,#ddd);",
        "background:var(--dsw-alias-bg-base,#fff);color:var(--dsw-alias-label-primary,#222)}",
        ".dsh-findbar.dsh-findbar-open{display:flex}",
        ".dsh-findbar input{flex:auto;min-width:0;height:26px;box-sizing:border-box;padding:0 8px;",
        "color:var(--dsw-alias-label-primary,#222);font-size:12px;",
        "background:var(--dsw-alias-bg-layer-1,#f5f5f5);",
        "border:.5px solid var(--dsw-alias-border-l2,#ccc);border-radius:6px;outline:none}",
        ".dsh-findbar input:focus{outline:1px solid var(--dsw-alias-state-business-primary,#0b57d0);outline-offset:-1px}",
        ".dsh-findbar-count{min-width:52px;text-align:center;font-size:11px;",
        "color:var(--dsw-alias-label-secondary,#666);white-space:nowrap}",
        ".dsh-findbar-count.dsh-findbar-empty{color:var(--dsw-alias-state-error-primary,#c5221f)}",
        ".dsh-findbar button{width:26px;height:26px;flex:none;padding:0;cursor:pointer;",
        "color:var(--dsw-alias-label-secondary,#666);background:transparent;border:0;border-radius:6px;font-size:13px}",
        ".dsh-findbar button:hover:not(:disabled){color:var(--dsw-alias-label-primary,#222);",
        "background:var(--dsw-alias-interactive-bg-hover,#eee)}",
        ".dsh-findbar button:disabled{color:var(--dsw-alias-label-quaternary,#bbb);cursor:default}",
      ].join("");
    
      function ensureStyle() {
        if (document.getElementById("dsh-findbar-style")) return;
        const style = document.createElement("style");
        style.id = "dsh-findbar-style";
        style.textContent = STYLE;
        document.head.appendChild(style);
      }
    
      const barsByRoot = new WeakMap();
      const wiredViews = new WeakSet();
    
      function visibleWebview() {
        const views = document.querySelectorAll("webview");
        for (const v of views) { if (v.offsetParent !== null) return v; }
        return views.length > 0 ? views[0] : null;
      }
    
      function rootFor(webview) {
        let el = webview.parentElement;
        let fallback = el;
        for (let i = 0; i < 6 && el; i++) {
          if (el.querySelector("form")) return el;
          fallback = el;
          el = el.parentElement;
        }
        return fallback || document.body;
      }
    
      function barFor(webview) {
        return barsByRoot.get(rootFor(webview));
      }
    
      function updateCount(bar, result) {
        if (!bar) return;
        const count = bar.querySelector(".dsh-findbar-count");
        const prev = bar.querySelector(".dsh-findbar-prev");
        const next = bar.querySelector(".dsh-findbar-next");
        const matches = result.matches || 0;
        const active = result.activeMatchOrdinal || 0;
        const query = bar.querySelector("input").value;
        count.textContent = matches > 0 ? active + "/" + matches : (query ? "0/0" : "");
        count.classList.toggle("dsh-findbar-empty", query !== "" && matches === 0);
        const disabled = matches === 0;
        if (prev) prev.disabled = disabled;
        if (next) next.disabled = disabled;
      }
    
      function runFind(webview, bar, findNext, forward) {
        const query = bar.querySelector("input").value;
        try {
          if (!query) {
            webview.stopFindInPage("clearSelection");
            updateCount(bar, { matches: 0, activeMatchOrdinal: 0 });
            return;
          }
          webview.findInPage(query, { forward: forward !== false, findNext: findNext === true, matchCase: false });
        } catch (error) { console.error("DSH findbar find failed", error); }
      }
    
      function closeBar(webview, bar) {
        bar.classList.remove("dsh-findbar-open");
        try { webview.stopFindInPage("clearSelection"); } catch (error) {}
        try { webview.focus(); } catch (error) {}
      }
    
      function wireWebview(webview) {
        if (wiredViews.has(webview)) return;
        wiredViews.add(webview);
        webview.addEventListener("found-in-page", (event) => {
          updateCount(barFor(webview), event.result || {});
        });
        webview.addEventListener("did-navigate", () => {
          const bar = barFor(webview);
          if (!bar) return;
          try { webview.stopFindInPage("clearSelection"); } catch (error) {}
          updateCount(bar, { matches: 0, activeMatchOrdinal: 0 });
        });
      }
    
      function ensureBar(webview) {
        const root = rootFor(webview);
        let bar = barsByRoot.get(root);
        if (bar) return bar;
        ensureStyle();
        bar = document.createElement("div");
        bar.className = "dsh-findbar";
        const input = document.createElement("input");
        input.type = "text";
        input.placeholder = "在页面中查找";
        input.setAttribute("aria-label", "在页面中查找");
        const count = document.createElement("span");
        count.className = "dsh-findbar-count";
        const prev = document.createElement("button");
        prev.type = "button";
        prev.className = "dsh-findbar-prev";
        prev.textContent = "▲";
        prev.title = "上一个 (Shift+Enter)";
        prev.disabled = true;
        const next = document.createElement("button");
        next.type = "button";
        next.className = "dsh-findbar-next";
        next.textContent = "▼";
        next.title = "下一个 (Enter)";
        next.disabled = true;
        const close = document.createElement("button");
        close.type = "button";
        close.className = "dsh-findbar-close";
        close.textContent = "✕";
        close.title = "关闭 (Esc)";
        bar.appendChild(input);
        bar.appendChild(count);
        bar.appendChild(prev);
        bar.appendChild(next);
        bar.appendChild(close);
        input.addEventListener("input", () => { runFind(webview, bar, false, true); });
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") { event.preventDefault(); runFind(webview, bar, true, !event.shiftKey); }
          else if (event.key === "Escape") { event.preventDefault(); closeBar(webview, bar); }
        });
        prev.addEventListener("click", () => { runFind(webview, bar, true, false); input.focus(); });
        next.addEventListener("click", () => { runFind(webview, bar, true, true); input.focus(); });
        close.addEventListener("click", () => { closeBar(webview, bar); });
        root.appendChild(bar);
        barsByRoot.set(root, bar);
        return bar;
      }
    
      function openBar() {
        const webview = visibleWebview();
        if (!webview) return;
        wireWebview(webview);
        const bar = ensureBar(webview);
        if (bar.parentElement) bar.parentElement.appendChild(bar);
        const input = bar.querySelector("input");
        const wasOpen = bar.classList.contains("dsh-findbar-open");
        bar.classList.add("dsh-findbar-open");
        input.focus();
        input.select();
        if (input.value && !wasOpen) runFind(webview, bar, false, true);
      }
    
      document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && (event.key === "f" || event.key === "F")) {
          event.preventDefault();
          openBar();
        }
      }, true);
    
      window.addEventListener("dsh-find-toggle", openBar);
    })();
    """
    
    
    def fail(msg):
        print("ERROR:", msg)
        sys.exit(1)
    
    
    def backup(path):
        bak = path + ".before-findbar"
        if os.path.exists(bak):
            print("backup already exists, keep:", bak)
        else:
            shutil.copyfile(path, bak)
            print("backup written:", bak)
        return bak
    
    
    def node_check_content(content):
        """Syntax-check JS text with node --check (as .mjs); None if no node."""
        node = shutil.which("node")
        if node is None:
            return None
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".mjs",
                                             delete=False, encoding="utf-8") as f:
                f.write(content)
                tmp = f.name
            r = subprocess.run([node, "--check", tmp],
                               capture_output=True, text=True)
            return r.returncode == 0
        finally:
            if tmp is not None and os.path.exists(tmp):
                os.unlink(tmp)
    
    
    def check_syntax(label, path, before, after):
        baseline = node_check_content(before)
        if baseline is None:
            print(label + ": node not found, syntax check skipped")
            return
        if baseline is False:
            print(label + ": node --check does not accept the ORIGINAL file, check skipped")
            return
        if node_check_content(after) is False:
            print("ERROR: " + label + " fails node --check after patch; restore with:")
            print("  sudo cp " + path + ".before-findbar " + path)
            sys.exit(1)
        print(label + ": node --check OK")
    
    
    def patch_main():
        if not os.path.exists(MAIN):
            fail("main.js not found: " + MAIN)
        content = open(MAIN, encoding="utf-8").read()
        if MARKER_MAIN in content:
            print("main.js: already patched, skip")
            return
        anchor = 'window.webContents.on("context-menu"'
        ai = content.find(anchor)
        if ai < 0:
            fail("main.js: anchor not found: " + anchor)
        wi = content.find('window.webContents.on("will-navigate"', ai)
        if wi < 0:
            fail("main.js: will-navigate anchor not found after context-menu")
        line_start = content.rfind("\n", 0, wi) + 1
        bak = backup(MAIN)
        new = content[:line_start] + MAIN_BLOCK + "\n" + content[line_start:]
        open(MAIN, "w", encoding="utf-8").write(new)
        if MARKER_MAIN not in open(MAIN, encoding="utf-8").read():
            fail("main.js: marker missing after write, restore from " + bak)
        check_syntax("main.js", MAIN, content, new)
        print("main.js: patched OK")
    
    
    def patch_client():
        if not os.path.exists(CLIENT):
            fail("client.js not found: " + CLIENT)
        content = open(CLIENT, encoding="utf-8").read()
        if MARKER_CLIENT in content:
            print("client.js: already patched, skip")
            return
        bak = backup(CLIENT)
        if not content.endswith("\n"):
            content += "\n"
        new = content + CLIENT_BLOCK + "\n"
        open(CLIENT, "w", encoding="utf-8").write(new)
        if MARKER_CLIENT not in open(CLIENT, encoding="utf-8").read():
            fail("client.js: marker missing after write, restore from " + bak)
        check_syntax("client.js", CLIENT, content, new)
        print("client.js: patched OK")
    
    
    patch_main()
    patch_client()
    print("done -- restart DeepSeek Harness, then Ctrl+F in a sidebar browser tab.")
    EOF

-----------------------------------------------------------------------

突出右侧边栏, 把右栏启动时默认比例从45%调到66.7%:

    sudo python3 - <<'EOF'
    #!/usr/bin/env python3
    """DSH three-column widths patch — one-click script (v2).
    
    Target (verified 2026-11-15 on the installed build):
      /opt/DeepSeek Harness/resources/app/dsh/node_modules/@deepseek-ai/dsh-client-ui-layout/lib/client.js
      package @deepseek-ai/dsh-client-ui-layout 0.2.1-rc.2, 719 lines.
    
    The installed 0.2.1-rc.2 bundle INLINES the layout constants as literals
    (master source names them SIDEBAR_DEFAULT / CENTER_MIN / RIGHTBAR_DEFAULT_RATIO),
    so the 3 logical changes become 7 literal edits:
    
      RIGHTBAR_DEFAULT_RATIO 0.45 -> 0.667
        L17  const RIGHTBAR_DEFAULT_RATIO = .45;              (declaration; openRightbar uses it)
        L240 layoutInfo.rightbar ?? viewport * .45            (AppFrame live fallback, inlined)
      CENTER_MIN 400 -> 370
        L40  const available = viewport - s - 400;            (computeColumns)
        L321 minmax(${cols.rightbar === 0 ? 0 : 400}px, 1fr)  (grid template)
      SIDEBAR_DEFAULT 280 -> 264
        L396 sidebar: 280,                                    (store init)
        L239 layoutInfo.sidebar === 0 ? 280 : layoutInfo.sidebar  (AppFrame preference)
        L420 d.layoutInfo.sidebar === 0 ? 280 : 0             (toggle reopen)
    
    v2 adds an 8th edit — resize recompute:
      L426 setViewportWidth: after "d.layoutInfo.viewportWidth = width;" insert
        if (d.layoutInfo.rightbar !== null)
          d.layoutInfo.rightbar = Math.max(300, Math.round(width * RIGHTBAR_DEFAULT_RATIO));
      Upstream deliberately keeps the px preference across resizes; this overrides
      that so the rightbar re-derives from the 0.667 ratio on every window-width
      change. The setter early-returns when the width is unchanged, so this only
      runs on real resizes. A manual drag is preserved until the next resize.
      rightbar === null (never opened) is left alone so openRightbar still
      initializes it on first open.
    
    Result at a 1918px viewport: 264 : 375 : 1279.
    SIDEBAR_MIN (264) and RIGHTBAR_MAX_RATIO (0.7) are untouched.
    
    Run in your own terminal (DSH bash cannot sudo):
      sudo python3 - <<'EOF'
      ... (this whole script) ...
      EOF
    Then restart DSH. Re-run after DSH updates (they overwrite client.js).
    Backup: client.js.before-widths (created once, never overwritten).
    Idempotent: re-running reports "already patched" and changes nothing.
    Safe to run over a v1-patched file — the 7 v1 edits are skipped as done.
    """
    import os
    import re
    import shutil
    import subprocess
    import sys
    
    CLIENT = os.environ.get(
        "DSH_WIDTHS_CLIENT",
        "/opt/DeepSeek Harness/resources/app/dsh/node_modules/@deepseek-ai/dsh-client-ui-layout/lib/client.js",
    )
    BACKUP = CLIENT + ".before-widths"
    
    # (label, old, new) — each old string must occur exactly once.
    EDITS = [
        ("ratio declaration (L17)",
         "const RIGHTBAR_DEFAULT_RATIO = .45;",
         "const RIGHTBAR_DEFAULT_RATIO = .667;"),
        ("ratio fallback (L240)",
         "layoutInfo.rightbar ?? viewport * .45",
         "layoutInfo.rightbar ?? viewport * .667"),
        ("center-min in computeColumns (L40)",
         "const available = viewport - s - 400;",
         "const available = viewport - s - 370;"),
        ("center-min in grid (L321)",
         "minmax(${cols.rightbar === 0 ? 0 : 400}px, 1fr)",
         "minmax(${cols.rightbar === 0 ? 0 : 370}px, 1fr)"),
        ("sidebar default init (L396)",
         "sidebar: 280,",
         "sidebar: 264,"),
        ("sidebar default preference (L239)",
         "layoutInfo.sidebar === 0 ? 280 : layoutInfo.sidebar",
         "layoutInfo.sidebar === 0 ? 264 : layoutInfo.sidebar"),
        ("sidebar default toggle (L420)",
         "d.layoutInfo.sidebar === 0 ? 280 : 0",
         "d.layoutInfo.sidebar === 0 ? 264 : 0"),
    ]
    
    # Insertion edits: (label, anchor, inserted_line). The inserted line goes on
    # its own line right after the anchor line, reusing its indentation.
    INSERTS = [
        ("resize recompute (L426)",
         "d.layoutInfo.viewportWidth = width;",
         "if (d.layoutInfo.rightbar !== null) d.layoutInfo.rightbar = Math.max(300, Math.round(width * RIGHTBAR_DEFAULT_RATIO));"),
    ]
    
    VIEWPORT = 1918
    WANT_RIGHTBAR = 1279
    
    
    def node_check(path):
        """True = parses OK, False = syntax error, None = node unavailable."""
        try:
            r = subprocess.run(["node", "--check", path],
                               capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        return r.returncode == 0
    
    
    def main():
        if not os.path.isfile(CLIENT):
            print("ERROR: client.js not found:", CLIENT)
            return 1
        with open(CLIENT, encoding="utf-8", errors="surrogateescape") as f:
            content = f.read()
    
        # Guard: the rightbar cap (viewport * RIGHTBAR_MAX_RATIO) must not clip
        # the wanted 1279px.
        m = re.search(r"RIGHTBAR_MAX_RATIO\s*=\s*([0-9.]+)", content)
        if m:
            cap = VIEWPORT * float(m.group(1))
            print("RIGHTBAR_MAX_RATIO = %s -> cap at %dpx viewport: %.0fpx"
                  % (m.group(1), VIEWPORT, cap))
            if cap < WANT_RIGHTBAR:
                print("ERROR: cap %.0fpx < wanted %dpx — aborting, nothing changed."
                      % (cap, WANT_RIGHTBAR))
                return 1
        else:
            print("WARNING: RIGHTBAR_MAX_RATIO declaration not found; "
                  "cap check skipped.")
    
        todo = []
        for label, old, new in EDITS:
            n_old = content.count(old)
            n_new = content.count(new)
            if n_old == 0 and n_new >= 1:
                print("already done: %s" % label)
            elif n_old == 1:
                todo.append((label, old, new))
            else:
                print("ERROR: %s: expected old string once, found %d "
                      "(new: %d) — aborting, nothing changed."
                      % (label, n_old, n_new))
                return 1
        insert_todo = []
        for label, anchor, line in INSERTS:
            n_anchor = content.count(anchor)
            n_line = content.count(line)
            if n_line >= 1:
                print("already done: %s" % label)
            elif n_anchor == 1:
                insert_todo.append((label, anchor, line))
            else:
                print("ERROR: %s: expected anchor once, found %d "
                      "(line: %d) — aborting, nothing changed."
                      % (label, n_anchor, n_line))
                return 1
        if not todo and not insert_todo:
            print("Already patched: all %d edits present. Nothing to do."
                  % (len(EDITS) + len(INSERTS)))
            return 0
    
        baseline = node_check(CLIENT)
        if baseline is None:
            print("node not found — skipping syntax validation.")
        elif not baseline:
            print("Original client.js fails node --check — skipping validation "
                  "(bundle may use ESM syntax).")
        else:
            print("Original client.js passes node --check.")
    
        if not os.path.exists(BACKUP):
            shutil.copy2(CLIENT, BACKUP)
            print("Backup created:", BACKUP)
        else:
            print("Backup already exists (kept):", BACKUP)
    
        new_content = content
        for label, old, new in todo:
            new_content = new_content.replace(old, new, 1)
            print("patched: %s" % label)
        for label, anchor, line in insert_todo:
            lines = new_content.split("\n")
            for i, ln in enumerate(lines):
                if anchor in ln:
                    indent = ln[:len(ln) - len(ln.lstrip())]
                    lines.insert(i + 1, indent + line)
                    break
            new_content = "\n".join(lines)
            print("patched: %s" % label)
        with open(CLIENT, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(new_content)
    
        # Verify: every new string present exactly once, every old string gone,
        # every inserted line present exactly once.
        with open(CLIENT, encoding="utf-8", errors="surrogateescape") as f:
            check = f.read()
        ok = True
        for label, old, new in EDITS:
            if check.count(new) != 1 or check.count(old) != 0:
                print("VERIFY FAILED: %s (new=%d, old=%d)"
                      % (label, check.count(new), check.count(old)))
                ok = False
        for label, anchor, line in INSERTS:
            if check.count(line) != 1:
                print("VERIFY FAILED: %s (line=%d)" % (label, check.count(line)))
                ok = False
        if not ok:
            shutil.copy2(BACKUP, CLIENT)
            print("Restored original from backup. Aborting.")
            return 1
    
        if baseline is True:
            if node_check(CLIENT):
                print("Patched client.js passes node --check.")
            else:
                shutil.copy2(BACKUP, CLIENT)
                print("Patched client.js FAILS node --check — restored original.")
                return 1
    
        print("Done: %d edit(s) applied. Restart DSH to take effect."
              % (len(todo) + len(insert_todo)))
        print("Expected columns at 1918px: 264 : 375 : 1279.")
        return 0
    
    
    if __name__ == "__main__":
        sys.exit(main())
    EOF

-----------------------------------------------------------------------

给链接及图片 添加右键下载菜单项:
sudo python ./dsh_patch_download_menu.py

==============================================================================

# DeepSeek Harness · Linux 桌面版

> 给官方 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 桌面端补上**社区 Linux 桌面端打包** —— 开源（MIT）DeepSeek 桌面客户端，开箱即用的 AppImage / `.deb` / `.tar.gz`，覆盖 x64 与 arm64 双架构，配套原生 CI 与 AppImage 自动更新。

**一句话定位**：在 Linux 上「能下载、能装、能更新」的 DeepSeek 桌面端（DeepSeek desktop for Linux）。完整保留官方 agent / 插件 / 联网能力，既可本地自托管运行 `dsh web`，也能装上原生桌面客户端，数据始终留在本机。

官方桌面端只发布 macOS 与 Windows；Linux 用户要么退而用 Web 版，要么自己从源码硬编。本项目就是这个缺口的补完：在保留官方桌面全部功能的前提下，把 Linux 作为**社区支持平台**来打包、测试、分发。

## 这是什么 / 不是什么

- ✅ **是**：一个下游 fork，专注做一件事——让 dsh 桌面端在 Linux 上「能下载、能装、能更新」。
- ❌ **不是**：不是官方 DeepSeek 项目，也不魔改 agent 内核。agent 能力、插件体系、通信协议全部跟随上游。

## 核心特性

- 🐧 **Linux 原生支持**：为 DeepSeek 官方桌面端提供社区 Linux 桌面端打包的下游项目 —— Ubuntu / Debian / 树莓派 5 / ARM 服务器都能跑。
- 📦 **三种安装包**：AppImage（单文件免安装、支持自动更新）、`.deb`（Debian / Ubuntu 原生包管理）、`.tar.gz`（便携解压即用）。**仅 AppImage 支持应用内自动更新**，deb / tar.gz 需手动下载新版替换。
- 🔄 **自动更新**：AppImage 通过 `electron-updater` 走 HTTPS 更新通道，按更新描述符（yml）内声明的 **sha512** 校验下载产物。
- 🧩 **功能完整**：agent 内核、插件体系、联网、前端全部跟随上游，Linux 下与官方体验一致（仅 Office 文档转换暂缺）。
- 🏠 **可自托管**：本地运行 `dsh web` 或安装桌面端，数据留在本机，适合隐私敏感与内网场景。
- 🆓 **开源免费**：基于上游 MIT 许可证分发。

## 产物一览

每次构建为每种架构产出三种安装包：

| 格式 | 用途 | 典型文件名 |
|------|------|-----------|
| **AppImage** | 单文件免安装，支持自动更新 | `deepseek-harness-<版本>-linux-x64.AppImage` |
| **.deb** | Debian / Ubuntu 系原生包管理 | `deepseek-harness-<版本>-linux-amd64.deb` |
| **.tar.gz** | 便携解压即用 | `deepseek-harness-<版本>-linux-x64.tar.gz` |

> 文件名中的 `<版本>` 替换为实际发布版本（当前为 `0.2.1-rc.2`）。

支持架构：`x64`（AMD / Intel）、`arm64`（树莓派 5、Apple Silicon 上的 Linux、ARM 服务器等）。

## 快速开始

### 方式一：AppImage（推荐，支持自动更新）

1. 到 [Releases](../../releases) 下载对应架构的 `.AppImage`。
2. 安装运行时依赖（AppImage 需要 FUSE 2）：
   ```sh
   sudo apt install libfuse2          # Debian / Ubuntu
   # Fedora / RHEL 系: sudo dnf install fuse2
   ```
3. 赋予执行权限并运行：
   ```sh
   chmod +x deepseek-harness-*-linux-x64.AppImage
   ./deepseek-harness-*-linux-x64.AppImage
   ```

### 方式二：.deb

```sh
sudo dpkg -i deepseek-harness-*-linux-x64.deb
deepseek-harness            # 或直接从应用菜单启动
```

### 方式三：.tar.gz（便携）

```sh
tar -xzf deepseek-harness-*-linux-x64.tar.gz
cd deepseek-harness-*-linux-x64
./deepseek-harness          # 运行解压目录内的启动入口
```

> 在无显示环境（如远程服务器 + VNC）运行时，确保已设置 `DISPLAY`（例如 xfce4 + TigerVNC 下的 `:1`），桌面会自动拉起。

## 从源码构建（开发者）

需要 Node.js 24+、pnpm，以及构建主机上的 `libfuse2`（AppImage 组装所需）。

```sh
git clone https://github.com/Zhou-Yujing114514/deepseek-harness-linux.git
cd deepseek-harness-linux
pnpm install
cp apps/desktop/.env.linux.example apps/desktop/.env.linux   # 按需填写发布设置
pnpm --dir apps/desktop run package:linux:x64                # x64
pnpm --dir apps/desktop run package:linux:arm64              # arm64
```

自托管 Web 模式（`dsh web`）依赖各 workspace 包已构建出的 `lib/` 产物：全新 checkout 直接启动会让 typert-loader 找不到 `lib/typert.host.js` 而报一堆 `ERR_MODULE_NOT_FOUND`，需先执行 `pnpm run build:official`。

`Desktop (Linux)` 工作流会在原生 runner 上按需构建两种架构（`ubuntu-24.04` / `ubuntu-24.04-arm`），产物可在 Actions Artifacts 或自动发布的 Release 中获取。

## 自动更新

AppImage 通过 `electron-updater` 走 AppImage 更新通道，更新描述符为 `nightly-linux.yml`，全程 HTTPS。未签名构建下，更新**仅依赖 HTTPS 传输与 feed 元数据校验**，无代码签名验签——请勿用于高信任场景。

自动更新由 `electron-updater` 校验描述符内声明的 **sha512**；手动下载时请核对 Release 附带的 `SHA256SUMS.txt`。

## 已知限制

1. **未签名**：Linux 构建不带代码签名。这是社区构建，分发时请在 Release 中核对校验和。
2. **Office 文档转换暂缺**：桌面内嵌的 DOCX / XLSX / PPTX → PDF 转换依赖 LibreOffice Kit 的 Linux 原生绑定，本版本尚未将其随包分发，该功能在 Linux 下暂不可用。其余桌面功能（agent、skill、联网、前端）均正常。
3. **上游处于 developer preview**：官方迭代快、破坏性变更频繁，本项目会持续 rebase 上游提交。
4. **无公证 / 无商店上架**：不走任何系统级公证或应用商店流程。

## 与上游的关系

- 上游：[deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)（MIT，DeepSeek-AI）。
- 本仓库是其下游 fork：主动改动限于 Linux 移植层——CI 工作流、electron-builder 配置、类型声明补全、POSIX launcher 兼容、桌面端打包说明与冒烟测试脚本。
- **移植层之外的差异来自版本滞后，尚未逐项追平上游**：本仓库按 rc 节奏 rebase 上游，落后期间会缺失部分上游新增文件。当前基线 commit 与版本对应关系见各次 Release notes，不要假定内核与官方逐提交同步。
- 后续希望将 Linux 打包经验整理后反馈给上游，供官方参考。

## 安全须知

- 运行前请阅读上游 [SAFETY.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md)。
- 未签名二进制存在供应链风险：只从本仓库 Release 下载，并核对 SHA256 校验和。
- 自动更新通道未做代码签名验签，仅依赖 HTTPS + feed 元数据。

## 找对地方了？

如果你正在搜下面这些词，那本项目就是你要找的：

- **DeepSeek Linux** / **DeepSeek on Linux** / **DeepSeek 桌面端 Linux**
- **DeepSeek 客户端下载** / **DeepSeek 桌面客户端** / **DeepSeek desktop for Linux**
- **DeepSeek AppImage** / **DeepSeek .deb** / **Ubuntu DeepSeek** / **Debian 安装 DeepSeek**
- **树莓派 DeepSeek** / **ARM64 DeepSeek** / **DeepSeek Linux 安装包**
- **开源 DeepSeek 客户端** / **self-hosted DeepSeek** / **Linux AI 助手**

> 说明：本项目是**桌面客户端**，模型能力由 DeepSeek 官方 API 提供，**不内置离线模型**，也不等同于"在本地跑模型"。如需接入自托管或第三方模型，请在客户端内自行配置对应的 API 端点与密钥。

## 许可证

本项目基于上游 **MIT** 许可证分发。DeepSeek Harness 由 DeepSeek-AI 开发，版权归其所有；Linux 打包层在同一 MIT 许可下新增。详见 [LICENSE](LICENSE) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
