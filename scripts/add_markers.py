# -*- coding: utf-8 -*-
"""One-time setup: insert module splice markers into index.html.

Markers let update_module.py replace each section's content safely:
    <!--MOD:stock:START--> ... <!--MOD:stock:END-->
Only stock/house/salary/huawei need markers (HR-learn rotates client-side).
"""
import re, io, sys

PATH = r"C:\Users\LIYUAN\WorkBuddy\LUO每日必看-云端版\index.html"

with io.open(PATH, encoding="utf-8") as f:
    html = f.read()

SECTIONS = ["stock", "house", "salary", "huawei"]

for s in SECTIONS:
    start_marker = "<!--MOD:%s:START-->\n" % s
    end_marker = "<!--MOD:%s:END-->\n" % s
    if start_marker in html:
        print("already has marker for %s, skip" % s)
        continue

    # 1) START marker: right after the section-head closing tag
    pat = re.compile(
        r'(<div class="content-section[^"]*" id="section-%s">\s*'
        r'<div class="section-head">\s*'
        r'<div class="section-title">.*?</div>\s*'
        r'<div class="update-tag">.*?</div>\s*'
        r'</div>)' % s, re.S)
    m = pat.search(html)
    if not m:
        print("FAIL: section-head not found for %s" % s); sys.exit(1)
    html = html[:m.end()] + "\n  " + start_marker + html[m.end():]

    # 2) END marker: right before the section's closing </div>
    #    The section ends with "\n</div>\n\n<!-- ===== SECTION ..." (or before /main for last one)
    idx = html.find(start_marker)
    nxt = html.find("<!-- ===== SECTION", idx)
    if nxt == -1:
        # last section before /main
        tail_pat = re.compile(r'(\n</div>)\s*(\n</div><!-- /main -->)', re.S)
        tm = tail_pat.search(html, idx)
        if not tm:
            print("FAIL: section end not found for %s" % s); sys.exit(1)
        html = html[:tm.start()] + "\n  " + end_marker + html[tm.start():]
    else:
        # walk back from nxt to the last "</div>" before it
        seg = html[:nxt]
        pos = seg.rfind("</div>")
        if pos == -1:
            print("FAIL: closing div not found for %s" % s); sys.exit(1)
        html = html[:pos] + "  " + end_marker + html[pos:]

# sanity: marker balance
for s in SECTIONS:
    a = html.count("<!--MOD:%s:START-->" % s)
    b = html.count("<!--MOD:%s:END-->" % s)
    assert a == 1 and b == 1, "marker count wrong for %s: %d/%d" % (s, a, b)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(html)

print("markers inserted OK for:", ", ".join(SECTIONS))
