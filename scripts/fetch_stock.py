# -*- coding: utf-8 -*-
"""Fetch A-share structured data from free public quote APIs (no key needed).

Sources:
- Tencent qt.gtimg.cn  : index quotes (sh000001/sz399001/sz399006/sh000300/sh000016)
- Eastmoney push2      : sector board daily ranking (top gainers / losers, main flow)

All calls degrade gracefully: on failure returns "" so the pipeline continues
with search-only data.
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

INDEX_CODES = [
    ("sh000001", "上证指数"), ("sz399001", "深证成指"), ("sz399006", "创业板指"),
    ("sh000300", "沪深300"), ("sh000688", "科创50"),
]


def fetch_index_quotes():
    """Return text table of index quotes: name/close/chg%/turnover."""
    try:
        codes = ",".join(c for c, _ in INDEX_CODES)
        r = requests.get("https://qt.gtimg.cn/q=" + codes,
                         headers=HEADERS, timeout=15)
        r.encoding = "gbk"
        lines = []
        for row in r.text.strip().split(";"):
            row = row.strip()
            if "=" not in row:
                continue
            parts = row.split("=")[1].strip('"').split("~")
            if len(parts) < 33:
                continue
            name = parts[1]
            price = parts[3]
            pct = parts[32]
            # index 37 = turnover in 万元 for indices (fallback blank)
            vol = parts[37] + "万" if len(parts) > 37 and parts[37] else ""
            lines.append("%s: 最新%s, 涨跌幅%s%%, 成交额%s" % (name, price, pct, vol))
        return "\n".join(lines)
    except Exception as e:
        print("[warn] index quotes failed:", e)
        return ""


def fetch_sector_rank():
    """Return top/bottom 8 sector boards with daily chg% and main net inflow."""
    def _fetch(po):
        try:
            url = ("https://push2.eastmoney.com/api/qt/clist/get"
                   "?pn=1&pz=8&po=%d&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50"
                   "&fields=f3,f12,f14,f62" % po)
            r = requests.get(url, headers=HEADERS, timeout=15)
            j = r.json()
            out = []
            for d in j.get("data", {}).get("diff", []):
                nm = d.get("f14", "")
                pct = d.get("f3", "")
                flow = d.get("f62", "")
                flow_s = ""
                if isinstance(flow, (int, float)) and flow != "-":
                    flow_s = "主力净流入%.1f亿" % (flow / 1e8)
                out.append("%s(%s%% %s)" % (nm, pct, flow_s))
            return out
        except Exception as e:
            print("[warn] sector rank failed:", e)
            return []
    top = _fetch(1)
    bottom = _fetch(0)
    s = ""
    if top:
        s += "今日涨幅前8板块: " + ", ".join(top) + "\n"
    if bottom:
        s += "今日跌幅前8板块: " + ", ".join(bottom)
    return s


if __name__ == "__main__":
    print(fetch_index_quotes())
    print()
    print(fetch_sector_rank())
