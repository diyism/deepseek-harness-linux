#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-click patch: add 下载链接 / 下载图片 to the DSH sidebar browser menu.

v2 (2026-11-18): the main-process helper HEAD-probes the target before
dispatching, so a URL whose basename has no extension (e.g. a GitHub avatar
URL) still gets a usable filename: the extension is guessed from the
Content-Type and passed as aria2c --out. Servers that send a
Content-Disposition filename are left to aria2c as before. Running v2 over
a v1 install upgrades it in place (helper + listener blocks are replaced;
menu items and backups are left alone).

What it does (DSH desktop 0.2.1-rc.2, Electron):
  [1] lib/main.js -- adds a "下载链接" item next to "在浏览器中打开链接" and a
      "下载图片" item next to "复制图片地址" in the webview context menu
      (DSH-CONTEXTMENU-WEBVIEW block). Clicking one fetches the webview session
      cookies for the target URL (HttpOnly included), HEAD-probes the URL for
      a usable filename, and dispatches a dsh-download-to-terminal
      CustomEvent to the renderer window.
  [2] ui-sidebar-browser lib/client.js -- adds "webTerminals" to the inject
      array and registers a download listener inside apply(ctx): on the event
      it opens a fresh sidebar terminal tab, focuses it, waits until the
      terminal view is writable, then prints the aria2c command (no trailing
      newline, so the user reviews it and presses Enter).
  [3] ui-sidebar-browser package.json -- adds @deepseek-ai/dsh-api-terminal-
      controller to dsh.client.inject so ctx.webTerminals is available.

Run:  sudo python3 dsh_patch_download_menu.py
DSH does not need to be stopped while patching, but restart DSH afterwards.
Backups are written next to each file as <file>.before-download-menu (only
the first run backs up). Re-running is safe: already-patched files are skipped.
A DSH update overwrites these files; re-run this script after updating.
"""

import json
import os
import re
import shutil
import subprocess
import sys

DSH_ROOT = "/opt/DeepSeek Harness/resources/app"
MAIN_JS = DSH_ROOT + "/lib/main.js"
BROWSER_DIR = DSH_ROOT + "/dsh/node_modules/@deepseek-ai/dsh-client-ui-sidebar-browser"
BROWSER_CLIENT = BROWSER_DIR + "/lib/client.js"
BROWSER_PKG = BROWSER_DIR + "/package.json"
BACKUP_SUFFIX = ".before-download-menu"
CONTROLLER_PKG = "@deepseek-ai/dsh-api-terminal-controller"

# JS inserted into ui-sidebar-browser lib/client.js, right after the
# sidebarRightTabs.register effect inside apply(ctx). Indentation is tabs.
CLIENT_EFFECT = """\t\t// DSH-DOWNLOAD-TO-TERMINAL-V2: a 下载链接/下载图片 click in the sidebar browser
\t\t// context menu arrives here as a dsh-download-to-terminal CustomEvent from the main
\t\t// process; open a fresh sidebar terminal and print the aria2c command (no newline).
\t\t// detail.outName (v2) carries a filename with an extension guessed from the
\t\t// Content-Type, used as aria2c --out when the URL basename has none.
\t\tctx.effect(() => {
\t\t\tconst shellQuote = (value) => "'" + String(value).replace(/'/g, "'\\\\''") + "'";
\t\t\tconst onDownload = async (event) => {
\t\t\t\ttry {
\t\t\t\t\tconst detail = event.detail || {};
\t\t\t\t\tif (!detail.url) return;
\t\t\t\t\tlet command = "aria2c --content-disposition";
\t\t\t\t\tif (detail.outName) command += " --out=" + shellQuote(detail.outName);
\t\t\t\t\tif (detail.cookieHeader) command += " --header=" + shellQuote("Cookie: " + detail.cookieHeader);
\t\t\t\t\tif (detail.pageUrl) command += " --referer=" + shellQuote(detail.pageUrl);
\t\t\t\t\tcommand += " " + shellQuote(detail.url);
\t\t\t\t\tconst before = new Set(ctx.sidebarRight.openTabs.getSnapshot().map((tab) => tab.tabId));
\t\t\t\t\tctx.sidebarRight.openTab("terminal", {});
\t\t\t\t\tconst deadline = Date.now() + 5000;
\t\t\t\t\tlet entry;
\t\t\t\t\twhile (Date.now() < deadline) {
\t\t\t\t\t\tentry = ctx.sidebarRight.openTabs.getSnapshot().find((tab) => !before.has(tab.tabId) && tab.kind === "terminal");
\t\t\t\t\t\tif (entry !== void 0) break;
\t\t\t\t\t\tawait new Promise((resolve) => setTimeout(resolve, 100));
\t\t\t\t\t}
\t\t\t\t\tif (entry === void 0) {
\t\t\t\t\t\tconsole.warn("[dsh-download] new terminal tab did not appear");
\t\t\t\t\t\treturn;
\t\t\t\t\t}
\t\t\t\t\tctx.sidebarRight.focus(entry.tabId);
\t\t\t\t\tlet view;
\t\t\t\t\tfor (let attempt = 0; attempt < 20; attempt++) {
\t\t\t\t\t\ttry {
\t\t\t\t\t\t\tconst navigation = ctx.sidebarRight.tabDomain.occurrence(entry.sessionId, { id: entry.tabId }).navigation.getSnapshot();
\t\t\t\t\t\t\tview = ctx.webTerminals.view(entry.sessionId, entry.tabId, navigation.address, navigation.params?.terminalId, navigation.params?.shellPath);
\t\t\t\t\t\t\tbreak;
\t\t\t\t\t\t} catch (error) {
\t\t\t\t\t\t\tawait new Promise((resolve) => setTimeout(resolve, 100));
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t\tif (view === void 0) {
\t\t\t\t\t\tconsole.warn("[dsh-download] could not open the terminal view");
\t\t\t\t\t\treturn;
\t\t\t\t\t}
\t\t\t\t\tconst writableDeadline = Date.now() + 10000;
\t\t\t\t\tfor (;;) {
\t\t\t\t\t\tconst state = typeof view.state.getSnapshot === "function" ? view.state.getSnapshot() : view.state;
\t\t\t\t\t\tif (state.writable === true) break;
\t\t\t\t\t\tif (Date.now() > writableDeadline) {
\t\t\t\t\t\t\tconsole.warn("[dsh-download] terminal never became writable");
\t\t\t\t\t\t\treturn;
\t\t\t\t\t\t}
\t\t\t\t\t\tawait new Promise((resolve) => setTimeout(resolve, 100));
\t\t\t\t\t}
\t\t\t\t\tview.write(command);
\t\t\t\t} catch (error) {
\t\t\t\t\tconsole.error("[dsh-download] failed to print aria2c command:", error);
\t\t\t\t}
\t\t\t};
\t\t\twindow.addEventListener("dsh-download-to-terminal", onDownload);
\t\t\treturn () => window.removeEventListener("dsh-download-to-terminal", onDownload);
\t\t}, "ui-sidebar-browser.download-to-terminal");"""


def main_helper(ind):
    """JS helper inserted into lib/main.js before the DSH-CONTEXTMENU-WEBVIEW
    block. `ind` is that block's indentation. v2: HEAD-probes the target so
    a URL whose basename has no extension still gets a usable --out name
    (extension guessed from Content-Type); servers that send a
    Content-Disposition filename are left to aria2c as before. Any probe
    failure falls back to the plain command."""
    mime = [
        ("image/png", "png"),
        ("image/jpeg", "jpg"),
        ("image/gif", "gif"),
        ("image/webp", "webp"),
        ("image/avif", "avif"),
        ("image/svg+xml", "svg"),
        ("image/bmp", "bmp"),
        ("image/x-icon", "ico"),
        ("image/tiff", "tif"),
        ("application/pdf", "pdf"),
        ("application/zip", "zip"),
        ("application/x-tar", "tar"),
        ("application/gzip", "gz"),
        ("application/x-7z-compressed", "7z"),
        ("application/x-xz", "xz"),
        ("application/zstd", "zst"),
        ("application/x-rar-compressed", "rar"),
        ("application/vnd.android.package-archive", "apk"),
        ("application/x-debian-package", "deb"),
        ("application/x-rpm", "rpm"),
        ("application/json", "json"),
        ("application/xml", "xml"),
        ("text/html", "html"),
        ("text/plain", "txt"),
        ("text/css", "css"),
        ("text/csv", "csv"),
        ("application/javascript", "js"),
        ("text/javascript", "js"),
        ("application/wasm", "wasm"),
        ("video/mp4", "mp4"),
        ("video/webm", "webm"),
        ("video/x-matroska", "mkv"),
        ("audio/mpeg", "mp3"),
        ("audio/ogg", "ogg"),
        ("audio/wav", "wav"),
        ("audio/flac", "flac"),
        ("audio/mp4", "m4a"),
    ]
    lines = [
        ind + "// DSH-DOWNLOAD-TO-TERMINAL-V2: HEAD-probe the target for a usable filename,",
        ind + "// then hand the download to the renderer as a dsh-download-to-terminal event.",
        ind + "const DSH_DOWNLOAD_MIME_EXT = {",
    ]
    for mime_type, ext in mime:
        lines.append(ind + "\t\"" + mime_type + "\": \"" + ext + "\",")
    lines += [
        ind + "};",
        ind + "function dshDownloadExtForMime(contentType) {",
        ind + "\tif (!contentType) return null;",
        ind + "\tconst mime = String(contentType).split(\";\")[0].trim().toLowerCase();",
        ind + "\treturn Object.prototype.hasOwnProperty.call(DSH_DOWNLOAD_MIME_EXT, mime) ? DSH_DOWNLOAD_MIME_EXT[mime] : null;",
        ind + "}",
        ind + "function dshDownloadFilenameFromDisposition(value) {",
        ind + "\tif (!value) return null;",
        ind + "\tconst star = /filename\\*\\s*=\\s*[^']*''([^;]+)/i.exec(value);",
        ind + "\tif (star) {",
        ind + "\t\ttry { return decodeURIComponent(star[1]); } catch (error) { return star[1]; }",
        ind + "\t}",
        ind + '\tconst plain = /filename\\s*=\\s*"([^"]+)"|filename\\s*=\\s*([^;]+)/i.exec(value);',
        ind + "\tif (plain) return (plain[1] || plain[2] || \"\").trim() || null;",
        ind + "\treturn null;",
        ind + "}",
        ind + "async function dshDownloadHead(url, headers, redirects) {",
        ind + "\tif (redirects > 5) return null;",
        ind + "\ttry {",
        ind + "\t\tconst lib = url.startsWith(\"https:\") ? await import(\"node:https\") : await import(\"node:http\");",
        ind + "\t\tconst result = await new Promise((resolve) => {",
        ind + "\t\t\tconst req = lib.request(url, { method: \"HEAD\", headers, timeout: 5000 }, (res) => {",
        ind + "\t\t\t\tres.resume();",
        ind + "\t\t\t\tresolve({ status: res.statusCode, headers: res.headers });",
        ind + "\t\t\t});",
        ind + "\t\t\treq.on(\"timeout\", () => { req.destroy(); resolve(null); });",
        ind + "\t\t\treq.on(\"error\", () => resolve(null));",
        ind + "\t\t\treq.end();",
        ind + "\t\t});",
        ind + "\t\tif (!result) return null;",
        ind + "\t\tif (result.status >= 300 && result.status < 400 && result.headers.location) {",
        ind + "\t\t\treturn dshDownloadHead(new URL(result.headers.location, url).href, headers, redirects + 1);",
        ind + "\t\t}",
        ind + "\t\treturn result;",
        ind + "\t} catch (error) {",
        ind + "\t\treturn null;",
        ind + "\t}",
        ind + "}",
        ind + "async function sendDownloadToTerminal(contents, url) {",
        ind + "\ttry {",
        ind + "\t\tconst cookies = await contents.session.cookies.get({ url });",
        ind + "\t\tconst cookieHeader = cookies.map((c) => c.name + \"=\" + c.value).join(\"; \");",
        ind + "\t\tconst pageUrl = contents.getURL();",
        ind + "\t\tlet outName = null;",
        ind + "\t\ttry {",
        ind + "\t\t\tconst probeHeaders = { Accept: \"*/*\" };",
        ind + "\t\t\tif (cookieHeader) probeHeaders.Cookie = cookieHeader;",
        ind + "\t\t\tif (pageUrl) probeHeaders.Referer = pageUrl;",
        ind + "\t\t\tconst head = await dshDownloadHead(url, probeHeaders, 0);",
        ind + "\t\t\tif (head && head.status >= 200 && head.status < 300) {",
        ind + "\t\t\t\tconst cdName = dshDownloadFilenameFromDisposition(head.headers[\"content-disposition\"]);",
        ind + "\t\t\t\tif (!cdName) {",
        ind + "\t\t\t\t\tconst base = decodeURIComponent(new URL(url).pathname.split(\"/\").pop() || \"\");",
        ind + "\t\t\t\t\tif (base && base.indexOf(\".\") === -1) {",
        ind + "\t\t\t\t\t\tconst ext = dshDownloadExtForMime(head.headers[\"content-type\"]);",
        ind + "\t\t\t\t\t\tif (ext) outName = base + \".\" + ext;",
        ind + "\t\t\t\t\t}",
        ind + "\t\t\t\t}",
        ind + "\t\t\t}",
        ind + "\t\t} catch (error) {",
        ind + "\t\t\tconsole.warn(\"[dsh-download] filename probe failed, using plain command:\", error);",
        ind + "\t\t}",
        ind + "\t\tconst win = contents.getOwnerBrowserWindow() || BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0];",
        ind + "\t\tif (!win) return;",
        ind + "\t\tconst payload = JSON.stringify({ url, pageUrl, cookieHeader, outName });",
        ind + "\t\tawait win.webContents.executeJavaScript(\"window.dispatchEvent(new CustomEvent('dsh-download-to-terminal', { detail: \" + payload + \" }))\");",
        ind + "\t} catch (error) {",
        ind + "\t\tconsole.error(\"[dsh-download] failed to dispatch download event:\", error);",
        ind + "\t}",
        ind + "}",
    ]
    return "\n".join(lines)


def link_item(match):
    """Append a 下载链接 item after the 在浏览器中打开链接 item."""
    ind = match.group(1)
    return ("click: () => shell.openExternal(params.linkURL)\n"
            + ind + "}, {\n"
            + ind + "\tlabel: \"下载链接\",\n"
            + ind + "\tclick: () => sendDownloadToTerminal(contents, params.linkURL)\n"
            + ind + "});")


def image_item(match):
    """Append a 下载图片 item after the 复制图片地址 item."""
    ind = match.group(1)
    return ("click: () => clipboard.writeText(params.srcURL)\n"
            + ind + "}, {\n"
            + ind + "\tlabel: \"下载图片\",\n"
            + ind + "\tclick: () => sendDownloadToTerminal(contents, params.srcURL)\n"
            + ind + "});")


def fail(message):
    print("FAIL: " + message)
    return False


def backup(path):
    target = path + BACKUP_SUFFIX
    if os.path.exists(target):
        print("  backup already exists: " + target)
        return
    shutil.copyfile(path, target)
    print("  backup written: " + target)


def check_syntax(path):
    """node --check when node exists; None when node is missing."""
    node = shutil.which("node")
    if node is None:
        return None
    result = subprocess.run([node, "--check", path],
                            capture_output=True, text=True)
    return result.returncode == 0


def patch_main():
    print("[1/3] main.js: " + MAIN_JS)
    if not os.path.isfile(MAIN_JS):
        return fail("main.js not found at " + MAIN_JS)
    with open(MAIN_JS, "r", encoding="utf-8") as handle:
        text = handle.read()
    if "DSH-DOWNLOAD-TO-TERMINAL-V2" in text:
        print("  already patched (v2), skipping")
        return True
    if "DSH-DOWNLOAD-TO-TERMINAL" in text:
        # v1 installed: replace only the helper block (menu items unchanged).
        v1_helper = re.compile(
            r"^([ \t]*)// DSH-DOWNLOAD-TO-TERMINAL: fetch this webview session cookies.*?\n"
            r"[ \t]*\}\n(?=[ \t]*// DSH-CONTEXTMENU-WEBVIEW:)",
            re.MULTILINE | re.DOTALL)
        found = v1_helper.search(text)
        if found is None or len(v1_helper.findall(text)) != 1:
            return fail("v1 helper block not found exactly once")
        text = v1_helper.sub(lambda m: main_helper(found.group(1)) + "\n",
                             text, count=1)
        backup(MAIN_JS)
        with open(MAIN_JS, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("  upgraded: helper v1 -> v2 (HEAD probe + --out filename)")
        return True
    marker = re.compile(r"^([ \t]*)// DSH-CONTEXTMENU-WEBVIEW:.*$", re.MULTILINE)
    if len(marker.findall(text)) != 1:
        return fail("DSH-CONTEXTMENU-WEBVIEW marker not found exactly once")
    text = marker.sub(lambda m: main_helper(m.group(1)) + "\n" + m.group(0),
                      text, count=1)
    link_pattern = re.compile(
        r"click: \(\) => shell\.openExternal\(params\.linkURL\)\n([ \t]*)\}\);")
    if len(link_pattern.findall(text)) != 1:
        return fail("linkURL menu item anchor not found exactly once")
    text = link_pattern.sub(link_item, text, count=1)
    image_pattern = re.compile(
        r"click: \(\) => clipboard\.writeText\(params\.srcURL\)\n([ \t]*)\}\);")
    if len(image_pattern.findall(text)) != 1:
        return fail("srcURL menu item anchor not found exactly once")
    text = image_pattern.sub(image_item, text, count=1)
    backup(MAIN_JS)
    with open(MAIN_JS, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("  patched: helper + 下载链接 + 下载图片")
    return True


def add_webterminals_inject(text):
    """Insert "webTerminals" into the inject array. Returns (text, True) on
    success, (text, False) when the anchor is not found exactly once."""
    inject_pattern = re.compile(
        r"^([ \t]*)\"sidebarRightTabs\"\n([ \t]*)\];$", re.MULTILINE)
    if len(inject_pattern.findall(text)) != 1:
        return text, False
    text = inject_pattern.sub(
        lambda m: m.group(1) + "\"sidebarRightTabs\",\n"
        + m.group(1) + "\"webTerminals\"\n" + m.group(2) + "];",
        text, count=1)
    return text, True


def indented_effect(base):
    """CLIENT_EFFECT re-indented to the given base indent."""
    return "\n".join(
        (base + line[2:]) if line.startswith("\t\t") else line
        for line in CLIENT_EFFECT.split("\n"))


def patch_client():
    print("[2/3] browser client.js: " + BROWSER_CLIENT)
    if not os.path.isfile(BROWSER_CLIENT):
        return fail("browser client.js not found at " + BROWSER_CLIENT)
    with open(BROWSER_CLIENT, "r", encoding="utf-8") as handle:
        text = handle.read()
    if "DSH-DOWNLOAD-TO-TERMINAL-V2" in text:
        print("  already patched (v2), skipping")
        return True
    if "dsh-download-to-terminal" in text:
        # v1 installed: replace only the listener effect block.
        v1_effect = re.compile(
            r"^([ \t]*)// DSH-DOWNLOAD-TO-TERMINAL: a 下载链接.*?\n"
            r"[ \t]*\}, \"ui-sidebar-browser\.download-to-terminal\"\);",
            re.MULTILINE | re.DOTALL)
        found = v1_effect.search(text)
        if found is None or len(v1_effect.findall(text)) != 1:
            return fail("v1 listener block not found exactly once")
        text = v1_effect.sub(lambda m: indented_effect(found.group(1)),
                             text, count=1)
        if '"webTerminals"' not in text:
            text, ok = add_webterminals_inject(text)
            if not ok:
                return fail("inject array anchor not found exactly once")
        backup(BROWSER_CLIENT)
        with open(BROWSER_CLIENT, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("  upgraded: listener v1 -> v2 (--out filename)")
        return True
    text, ok = add_webterminals_inject(text)
    if not ok:
        return fail("inject array anchor not found exactly once")
    register_pattern = re.compile(
        r"^([ \t]*)ctx\.effect\(\(\) => ctx\.sidebarRightTabs\.register\(\{\n"
        r"[ \t]*\.\.\.browserDefinition\(t\),\n"
        r"[ \t]*keepMounted: desktop !== void 0\n"
        r"[ \t]*\}\), \"ui-sidebar-browser\.type\"\);", re.MULTILINE)
    found = register_pattern.search(text)
    if found is None or len(register_pattern.findall(text)) != 1:
        return fail("sidebarRightTabs.register anchor not found exactly once")
    text = register_pattern.sub(
        lambda m: m.group(0) + "\n" + indented_effect(found.group(1)),
        text, count=1)
    backup(BROWSER_CLIENT)
    with open(BROWSER_CLIENT, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("  patched: webTerminals inject + download listener")
    return True


def patch_package():
    print("[3/3] browser package.json: " + BROWSER_PKG)
    if not os.path.isfile(BROWSER_PKG):
        return fail("browser package.json not found at " + BROWSER_PKG)
    with open(BROWSER_PKG, "r", encoding="utf-8") as handle:
        text = handle.read()
    try:
        data = json.loads(text)
    except ValueError as error:
        return fail("package.json is not valid JSON: %s" % error)
    inject = data.get("dsh", {}).get("client", {}).get("inject", [])
    if CONTROLLER_PKG in inject:
        print("  already patched, skipping")
        return True
    anchor = "        \"@deepseek-ai/dsh-client-ui-session\"\n      ],"
    if text.count(anchor) != 1:
        return fail("package.json inject anchor found %d times, expected 1"
                    % text.count(anchor))
    replacement = ("        \"@deepseek-ai/dsh-client-ui-session\",\n"
                   "        \"" + CONTROLLER_PKG + "\"\n      ],")
    text = text.replace(anchor, replacement, 1)
    try:
        json.loads(text)
    except ValueError as error:
        return fail("patched package.json is not valid JSON: %s" % error)
    backup(BROWSER_PKG)
    with open(BROWSER_PKG, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("  patched: added " + CONTROLLER_PKG + " to dsh.client.inject")
    return True


def main():
    print("DSH sidebar browser download-menu patch v2 (0.2.1-rc.2)")
    print("DSH does not need to be stopped; restart it after patching.")
    baseline = {}
    for path in (MAIN_JS, BROWSER_CLIENT):
        baseline[path] = check_syntax(path)
    ok = True
    ok = patch_main() and ok
    ok = patch_client() and ok
    ok = patch_package() and ok
    if not ok:
        print("ABORTED: one or more steps failed; files already patched stay patched.")
        return 1
    for path in (MAIN_JS, BROWSER_CLIENT):
        after = check_syntax(path)
        if baseline[path] is True and after is False:
            print("FAIL: node --check now fails on " + path
                  + "; restore from " + path + BACKUP_SUFFIX)
            return 1
        if after is True:
            print("node --check OK: " + path)
    print("DONE. Restart DSH, then right-click a link or image in the sidebar browser.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
