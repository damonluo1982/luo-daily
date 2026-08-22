# -*- coding: utf-8 -*-
"""Common utilities: DeepSeek API, Tavily search, HTML splice, update log."""
import json, os, re, io, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
UPDATES = os.path.join(ROOT, "data", "updates.json")

MODULES = ["stock", "house", "salary", "huawei"]
MODULE_NAMES = {
    "stock": "A股投资预测", "house": "深圳房产", "salary": "薪酬COE",
    "huawei": "华为最新消息", "learn": "HR学习",
}


def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")


def deepseek_chat(messages, max_tokens=7000, temperature=0.7):
    """Call DeepSeek chat API. Returns text content."""
    import requests
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    r = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"},
        json={"model": "deepseek-chat",
              "messages": messages,
              "max_tokens": max_tokens,
              "temperature": temperature,
              "stream": False},
        timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def tavily_search(query, max_results=6):
    """Tavily web search. Returns list of {title,url,content}."""
    import requests
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        print("[warn] TAVILY_API_KEY not set, skip search:", query[:40])
        return []
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": key, "query": query,
                  "search_depth": "advanced",
                  "max_results": max_results,
                  "include_answer": False},
            timeout=60)
        r.raise_for_status()
        return [{"title": x.get("title", ""),
                 "url": x.get("url", ""),
                 "content": x.get("content", "")}
                for x in r.json().get("results", [])]
    except Exception as e:
        print("[warn] tavily failed:", e)
        return []


def read_index():
    with io.open(INDEX, encoding="utf-8") as f:
        return f.read()


def write_index(html):
    with io.open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)


def get_module_inner(html, module):
    s = "<!--MOD:%s:START-->" % module
    e = "<!--MOD:%s:END-->" % module
    i = html.find(s)
    j = html.find(e)
    if i == -1 or j == -1:
        raise RuntimeError("markers missing for module " + module)
    return html[i + len(s):j]


def splice_module(html, module, new_inner):
    """Replace content between markers; keep markers themselves."""
    s = "<!--MOD:%s:START-->" % module
    e = "<!--MOD:%s:END-->" % module
    i = html.find(s)
    j = html.find(e)
    if i == -1 or j == -1:
        raise RuntimeError("markers missing for module " + module)
    body = "\n" + new_inner.strip() + "\n  "
    html = html[:i + len(s)] + body + html[j:]

    # update the section's update-tag (scoped: between section start and marker start)
    sec = html.find('id="section-%s"' % module)
    if sec != -1:
        seg_end = html.find(s, sec)
        seg = html[sec:seg_end]
        t = datetime.date.today()
        tag = "更新：%d/%d" % (t.month, t.day)
        new_seg = re.sub(r'(<div class="update-tag">)[^<]*(</div>)',
                         r'\g<1>' + tag + r'\g<2>',
                         seg, count=1)
        html = html[:sec] + new_seg + html[seg_end:]
    return html


def log_update(module, summary):
    """Append today's update record to data/updates.json (dedup by module+date)."""
    os.makedirs(os.path.dirname(UPDATES), exist_ok=True)
    data = {"updates": []}
    if os.path.exists(UPDATES):
        try:
            with io.open(UPDATES, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"updates": []}
    today = today_str()
    data["updates"] = [u for u in data.get("updates", [])
                       if not (u.get("module") == module and u.get("date") == today)]
    data["updates"].append({"module": module,
                            "name": MODULE_NAMES.get(module, module),
                            "date": today, "summary": summary})
    # keep last 90 days
    cutoff = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
    data["updates"] = [u for u in data["updates"] if u.get("date", "") >= cutoff]
    with io.open(UPDATES, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def today_updates():
    if not os.path.exists(UPDATES):
        return []
    try:
        with io.open(UPDATES, encoding="utf-8") as f:
            data = json.load(f)
        today = today_str()
        return [u for u in data.get("updates", []) if u.get("date") == today]
    except Exception:
        return []


def strip_code_fence(text):
    """Remove markdown code fences if the model wrapped output."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n", "", t)
        t = re.sub(r"\n```\s*$", "", t)
    return t.strip()
