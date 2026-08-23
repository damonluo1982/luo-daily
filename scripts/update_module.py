# -*- coding: utf-8 -*-
"""Update one module of the workbench via DeepSeek + Tavily search.

Usage:
    python scripts/update_module.py stock|house|salary|huawei

Flow:
  1. run module-specific web searches (Tavily)
  2. stock: also fetch structured quotes (Tencent/Eastmoney APIs)
  3. DeepSeek generates the section inner HTML (style guide + old content as example)
  4. splice into index.html, refresh update-tag, log to data/updates.json
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import deepseek_chat, tavily_search, read_index, write_index, \
    splice_module, get_module_inner, log_update, strip_code_fence, today_str

STYLE_GUIDE = """你是「LUO每日必看」工作台的HTML内容生成器。工作台是手机优先的紧凑单页，红涨绿跌（中国股市惯例）。

【可用CSS类和惯用结构】
- <div class="key-view" style="border-left:3px solid var(--t1); padding:10px 12px;"> 重要结论卡片，内含
  <div class="kv-header">📌 标题 <span class="pill" style="background:var(--red-bg);color:var(--red);">日期标签</span></div>
  <div class="kv-body"><p>...</p></div>
- <div class="block"><div class="block-title">■ 标题</div><div class="mcard" style="padding:8px 10px;">...</div></div> 普通内容块
- 指数小卡：grid四列 <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:5px;">，
  每格 <div style="background:var(--red-light);border-radius:6px;padding:5px 6px;text-align:center;">
  <div style="font-size:8px;color:var(--t2);">名称</div><div style="font-size:13px;font-weight:800;">数值</div>
  <div style="font-size:9px;color:var(--red);font-weight:700;">涨跌幅</div></div>
  上涨背景var(--red-light)字色var(--red)，下跌背景var(--green-bg)字色var(--green)
- <div class="disc">⚠️ 免责声明</div> 放模块末尾
- 颜色变量：var(--red)/var(--red-light)/var(--red-bg)/var(--green)/var(--green-bg)/var(--t2)/var(--t3)/var(--border-light)

【硬性要求】
- 只输出HTML片段，不要输出<html><head><body>、不要markdown代码块
- 版面紧凑适配手机：字号10-13px，行高1.45，信息密度高，关键观点前置
- 所有数字必须来自我给你的数据/搜索结果，不确定的不要编造
- 中文输出"""

MODULE_CONFIG = {
    "stock": {
        "name": "A股投资预测",
        "queries": [
            "A股 今日收盘 上证指数 成交额 北向资金 涨跌家数",
            "A股 今日要闻 盘后重要消息 政策 公告 财经",
            "本周 申万一级行业 周涨跌幅 排行 板块",
            "A股 本周 关键事件 财经新闻 政策",
            "上海黄金交易所 Au9999 黄金价格 每日收盘 元/克 沪金",
        ],
        "prompt": """请更新「A股投资预测」模块，排列顺序严格为：
①今日收盘速览（指数卡片：上证/深成/创业板/沪深300/科创50的收盘点位+涨跌幅，两市成交额、北向资金、涨跌比，后接1段盘面要点）
②今日要闻（紧随盘面要点之后，3-5条超短要闻每条一行，只放与A股投资直接相关的当日要闻：政策发布/宏观数据/行业大事/海外市场影响等）
③今日涨跌幅最大板块（当日板块涨幅TOP5+跌幅TOP5，含当日涨跌幅；形式参照本周板块榜的紧凑样式，优先用下方提供的东财当日板块行情数据）
④本周总结（①-④条要点，含风格切换/资金流向分析）
⑤下周操作建议（对明天、未来一周、未来一个月的建议，用行业ETF视角，不对用户持仓给意见）
⑥本周涨跌幅最大板块（TOP5上涨+TOP5下跌，含周涨幅）
⑦本周关键事件（3-5条）
⑧黄金·过去一周每日收盘（统一用人民币元/克口径：优先上海黄金交易所Au9999或沪金主力每日收盘价；若仅查到国际金价（美元/盎司），按当日汇率换算为元/克并标注"按汇率换算"。flex横向排列每日数据：日期+收盘价（元/克）+涨跌幅，底部1行周涨幅摘要）
不要包含"行业ETF聚焦"板块。末尾加 <div class="disc">⚠️ AI风格模拟分析，不构成投资建议。数据来源东方财富/同花顺等公开渠道。红涨绿跌（中国股市惯例）。</div>""",
    },
    "house": {
        "name": "深圳房产投资建议",
        "queries": [
            "深圳 房产 本周 要闻 楼市 新闻",
            "全国 楼市 本周 政策 要闻 房地产",
            "深圳 二手房 一手房 最新成交量 均价",
            "深圳 龙华 坂田 福田 南山 宝安中心 房价 挂牌 最新",
            "深圳 楼市政策 房贷利率 最新",
            "深圳 法拍房 阿里拍卖 京东法拍 即将开拍 起拍价",
            "深圳 法拍房 成交 折价率 月度统计",
        ],
        "prompt": """请更新「深圳房产投资建议」模块：
①本周房产要闻（放最前面，3-6条每条一行超短要闻，深圳相关优先放前，全国重大楼市政策/土地/利率要闻放后；形式参照A股"今日要闻"的紧凑样式）
②市场速览（成交量/均价/政策关键数据卡片）
③成交数据和市场趋势（核心区南山/福田、次核心区宝中/坂田、外围区龙华观澜/深圳北站）
④法拍房板块（重点）：月度统计速览（放盘量/成交量/成交率/折价率）→月度趋势表（近4个月）→折价率趋势提示→已成交笋盘→即将开拍笋盘
- 重点片区房源（坂田/龙华/宝安中心/南山/福田）用 <div class="mcard fp-hot" ...> 高亮（红边框+浅红背景），标题前加⭐片区标签（如⭐南山）
- 非重点片区不加高亮排在最后
- 每套笋盘标注风险评估（税费/清场/过户/产权）
- 法拍板块末尾说明：红色边框+⭐为重点关注片区房源
⑤未来半年行情预测
末尾加 <div class="disc">⚠️ 数据来自公开渠道，法拍房有风险，投资需谨慎。</div>""",
    },
    "salary": {
        "name": "薪酬COE热点",
        "queries": [
            "腾讯 字跳动 比亚迪 小米 中兴 荣耀 调薪 股权激励 最新",
            "美世 Mercer 2026 薪酬调研 涨薪 人才趋势 报告",
            "怡安 Aon 人力资本趋势 薪酬 报告",
            "深圳 最低工资 社保缴费基数 最新 政策",
            "AI人才 芯片 半导体 薪酬 最新",
        ],
        "prompt": """请更新「薪酬COE热点」模块，按四模块框架：
①核心速览（3-5条关键洞察卡片，前置）
②华为竞争对手薪酬动态（腾讯/字节/比亚迪/小米/中兴/荣耀等：调薪、股权激励、应届生薪酬包）
③咨询公司人才趋势（美世Mercer+怡安Aon+其他：年度薪酬调研/涨薪预测/AI对人才影响/行业分化）
④劳动工资政策（最低工资、社保基数变化及人力成本影响）
⑤AI/科技人才薪酬动态
⑥COE行动建议（短期/中期/长期）
末尾加 <div class="disc">⚠️ 信息来自公开渠道，仅供内部参考。</div>""",
    },
    "huawei": {
        "name": "华为最新消息",
        "queries": [
            "华为 最新 业绩 营收 任正非 讲话",
            "华为 手机 出货量 市场份额 最新",
            "鸿蒙智行 问界 交付 最新",
            "华为 昇腾 麒麟 芯片 最新 进展",
            "华为 HarmonyOS 鸿蒙 生态 装机量 最新",
            "华为 海外市场 美国制裁 最新动态",
        ],
        "prompt": """请更新「华为最新消息」模块，六大维度：
①核心速览（3-5条最重要的动态卡片）
②集团动态（财务卡片：营收/利润/研发投入，任正非讲话，组织变动）
③各产业板块经营（终端/ICT基础设施/企业业务云计算/智能汽车/数字能源/海思）
④全球市场份额（手机/5G设备/云计算/智能汽车交付排名）
⑤HarmonyOS生态（装机量、开发者、原生应用）与芯片突破（麒麟/昇腾）
⑥国际化/地缘动态
每个板块给具体数字和来源。末尾加 <div class="disc">⚠️ 信息来自公开渠道。</div>""",
    },
}


def build_data_block(module):
    cfg = MODULE_CONFIG[module]
    parts = []
    parts.append("今天是 %s。\n" % datetime.date.today().strftime("%Y年%m月%d日 %A"))

    if module == "stock":
        import fetch_stock
        q = fetch_stock.fetch_index_quotes()
        if q:
            parts.append("【实时行情API数据（腾讯/东财，可信度高）】\n" + q + "\n")
        s = fetch_stock.fetch_sector_rank()
        if s:
            parts.append(s + "\n")

    parts.append("【网络搜索结果（按相关性，可能有噪声，请甄别，注意时效性，过期信息不要用）】")
    for i, query in enumerate(cfg["queries"]):
        results = tavily_search(query)
        parts.append("\n搜索%d: %s" % (i + 1, query))
        if not results:
            parts.append("（无结果）")
        for r in results:
            parts.append("- [%s] %s" % (r["title"][:60], r["content"][:500]))
    return "\n".join(parts)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in MODULE_CONFIG:
        print("usage: python update_module.py stock|house|salary|huawei")
        sys.exit(1)
    module = sys.argv[1]
    cfg = MODULE_CONFIG[module]

    html = read_index()
    old_inner = get_module_inner(html, module)
    if len(old_inner) > 9000:
        old_inner = old_inner[:9000] + "\n<!--(截断)-->"
    data_block = build_data_block(module)

    messages = [
        {"role": "system", "content": STYLE_GUIDE},
        {"role": "user",
         "content": ("%s\n\n【当前模块的旧版内容（仅供风格参考，数据全部用新数据替换）】\n%s\n\n【新数据】\n%s\n\n"
                     "请输出完整的新模块HTML片段（替换旧内容全部），最后一行单独输出：\n===SUMMARY===<本模块一句话要点摘要，30字内>"
                     % (cfg["prompt"], old_inner, data_block))},
    ]

    print("calling DeepSeek for module: %s ..." % module)
    out = deepseek_chat(messages)

    if "===SUMMARY===" in out:
        body, summary = out.rsplit("===SUMMARY===", 1)
        summary = summary.strip().splitlines()[0].strip()[:60]
    else:
        body, summary = out, cfg["name"] + "已更新"

    body = strip_code_fence(body)
    # safety: body must not contain section/doctype level tags
    for bad in ["</html", "<html", "<!DOCTYPE", "</body", "<body"]:
        if bad.lower() in body.lower():
            print("[error] output contains document-level tags, abort")
            sys.exit(2)
    if len(body) < 400:
        print("[error] output too short (%d chars), abort to avoid blank module" % len(body))
        sys.exit(3)

    html = splice_module(html, module, body)
    write_index(html)
    log_update(module, summary)
    print("module %s updated, summary: %s" % (module, summary))


if __name__ == "__main__":
    main()
