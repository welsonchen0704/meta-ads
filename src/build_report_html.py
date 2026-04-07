"""
build_report_html.py
從 analyze_ads.py 的輸出資料，產生 HTML 週報視覺儀表板。
同時包含：
- Token 到期自動提醒（剩 7 天 Telegram 警告）
- 週對週比較（從 Notion 撈上週數據）
輸出：output/weekly_report_YYYY-MM-DD.html + output/index.html（固定連結）
"""

import os
import html as html_lib
from datetime import datetime, date, timedelta
from pathlib import Path


# ─── 工具函式 ──────────────────────────────────────────────────────────────

def fmt_num(n, decimals=0):
    if n is None:
        return "─"
    try:
        if decimals == 0:
            return f"{int(round(n)):,}"
        else:
            return f"{n:,.{decimals}f}"
    except (TypeError, ValueError):
        return "─"


def roas_class(roas):
    if roas is None:
        return "muted"
    if roas >= 5:
        return "green"
    if roas >= 3:
        return "amber"
    return "red"


def roas_fill_class(roas):
    if roas is None:
        return "fill-red"
    if roas >= 5:
        return "fill-green"
    if roas >= 3:
        return "fill-amber"
    return "fill-red"


def roas_pct(roas, cap=15):
    if roas is None:
        return 0
    return min(100, round(roas / cap * 100))


def safe(text, max_len=60):
    if not text:
        return "─"
    t = html_lib.escape(str(text))
    return t[:max_len] + "…" if len(t) > max_len else t


# ─── Token 到期提醒 ────────────────────────────────────────────────────────

def check_token_expiry(token_expiry_str: str) -> tuple:
    try:
        expiry = datetime.strptime(token_expiry_str, "%Y-%m-%d").date()
        days_left = (expiry - date.today()).days
    except Exception:
        days_left = 999

    if days_left <= 0:
        html = f'<div class="token-warn">⚠️ Meta Access Token 已於 {token_expiry_str} 過期！請立即重新產生 Token 並更新 GitHub Secret META_ACCESS_TOKEN。</div>'
    elif days_left <= 7:
        html = f'<div class="token-warn">⚠️ Meta Access Token 將於 {days_left} 天後（{token_expiry_str}）到期，請本週重新產生 Token。</div>'
    else:
        html = f'<div class="token-warn ok">✓ Meta Access Token 有效（還有 {days_left} 天，到期：{token_expiry_str}）</div>'

    return html, days_left


def send_token_warning_telegram(days_left: int, bot_token: str, chat_id: str):
    """剩餘 7 天內才發送 Telegram 警告。"""
    if days_left > 7:
        return
    import requests
    token_expiry = os.environ.get("META_TOKEN_EXPIRY", "未設定")
    if days_left <= 0:
        msg = f"🔴 *Meta Token 已過期！*\n到期日：{token_expiry}\n請立即重新產生並更新 GitHub Secret。"
    else:
        msg = f"⚠️ *Meta Token 即將到期*\n剩餘：{days_left} 天（到期：{token_expiry}）\n請本週重新產生 Token。"
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"[WARN] Telegram token warning failed: {e}")


# ─── 週對週比較 ────────────────────────────────────────────────────────────

def fetch_last_week_roas(notion_token: str, db_id: str, current_week_label: str):
    try:
        import requests
        year, week = map(int, current_week_label.split("-W"))
        current_monday = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u").date()
        last_monday = current_monday - timedelta(weeks=1)
        last_week_label = last_monday.strftime("%G-W%V")

        headers = {
            "Authorization": f"Bearer {notion_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        payload = {
            "filter": {"property": "週次", "rich_text": {"equals": last_week_label}},
            "page_size": 1,
        }
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        val = results[0].get("properties", {}).get("整體ROAS", {}).get("number")
        return float(val) if val is not None else None
    except Exception as e:
        print(f"[WARN] fetch_last_week_roas failed: {e}")
        return None


def roas_wow_html(current_roas: float, last_roas) -> str:
    if last_roas is None:
        return '<div class="kpi-sub">上週 ─（無資料）</div>'
    diff = current_roas - last_roas
    pct = (diff / last_roas * 100) if last_roas else 0
    arrow = "▲" if diff >= 0 else "▼"
    color = "var(--green)" if diff >= 0 else "var(--red)"
    return f'<div class="kpi-sub" style="color:{color}">{arrow} {abs(pct):.1f}% vs 上週 {last_roas:.2f}x</div>'


# ─── 廣告列 HTML ───────────────────────────────────────────────────────────

def boost_stop_row(ad: dict) -> str:
    name     = safe(ad.get("ad_name", "─"), 45)
    spend    = fmt_num(ad.get("spend"))
    roas     = ad.get("purchase_roas")
    cpa      = fmt_num(ad.get("cpa"))
    rc       = roas_class(roas)
    rf       = roas_fill_class(roas)
    roas_str = f"{roas:.2f}x" if roas is not None else "─"
    pct      = roas_pct(roas)
    return f"""
    <tr>
      <td>
        <div class="ad-name">{name}</div>
        <div class="ad-meta">曝光 {fmt_num(ad.get('impressions'))}｜CTR {ad.get('ctr', 0):.2f}%｜頻率 {ad.get('frequency', 0):.1f}</div>
      </td>
      <td class="mono-val">{spend}</td>
      <td><div class="roas-cell"><span class="mono-val {rc}">{roas_str}</span><div class="roas-mini-bar"><div class="roas-mini-fill {rf}" style="width:{pct}%"></div></div></div></td>
      <td class="mono-val {rc}">{cpa}</td>
    </tr>"""


def watch_row(ad: dict) -> str:
    name     = safe(ad.get("ad_name", "─"), 40)
    roas     = ad.get("purchase_roas")
    rc       = roas_class(roas)
    roas_str = f"{roas:.2f}x" if roas is not None else "─"
    return f"""
    <tr>
      <td><div class="ad-name">{name}</div></td>
      <td class="mono-val">{fmt_num(ad.get('spend'))}</td>
      <td class="mono-val">{fmt_num(ad.get('purchases'))}</td>
      <td class="mono-val {rc}">{roas_str}</td>
      <td class="mono-val">{fmt_num(ad.get('cpa'))}</td>
      <td class="mono-val">{ad.get('ctr', 0):.2f}%</td>
      <td class="mono-val">{fmt_num(ad.get('cpm'), 1)}</td>
      <td class="mono-val">{ad.get('frequency', 0):.1f}</td>
    </tr>"""


def insuf_row(ad: dict) -> str:
    name = safe(ad.get("ad_name", "─"), 50)
    return f"""
    <tr>
      <td><div class="ad-name">{name}</div></td>
      <td class="mono-val muted">{fmt_num(ad.get('spend'))}</td>
      <td class="mono-val muted">{fmt_num(ad.get('impressions'))}</td>
      <td class="mono-val muted">{ad.get('ctr', 0):.2f}%</td>
      <td class="mono-val muted">{fmt_num(ad.get('cpm'), 1)}</td>
    </tr>"""


def dist_row_html(ad: dict, max_spend: float) -> str:
    name     = safe(ad.get("ad_name", "─"), 28)
    roas     = ad.get("purchase_roas") or 0
    spend    = ad.get("spend") or 0
    pct      = round((spend / max_spend * 100)) if max_spend else 0
    roas_str = f"{roas:.2f}x" if roas else "─"
    color    = "green" if roas >= 5 else "amber" if roas >= 3 else "red"
    return f"""
    <div class="dist-row">
      <div class="dist-label">{name}</div>
      <div class="dist-bar-bg"><div class="dist-bar-fill" style="width:{pct}%"></div></div>
      <div class="dist-val" style="color:var(--{color})">{roas_str}</div>
    </div>"""


# ─── 主函式 ────────────────────────────────────────────────────────────────

def build_html_report(report_data: dict, output_dir: str = "output") -> str:
    """
    從 report_data 產生 HTML 儀表板。
    同時輸出：
    - weekly_report_YYYY-MM-DD.html（有日期的版本，保留歷史）
    - index.html（固定連結，永遠指向最新週報）
    """
    # 找模板
    script_dir = Path(__file__).parent
    template_candidates = [
        script_dir.parent / "templates" / "weekly_report.html",
        Path("templates/weekly_report.html"),
    ]
    tpl_path = next((p for p in template_candidates if p.exists()), None)
    if tpl_path is None:
        raise FileNotFoundError("找不到 templates/weekly_report.html")
    tpl = tpl_path.read_text(encoding="utf-8")

    # Token 到期
    token_expiry = os.environ.get("META_TOKEN_EXPIRY", "2026-06-06")
    token_warn_html, days_left = check_token_expiry(token_expiry)

    # 週對週 ROAS
    notion_token = os.environ.get("NOTION_API_TOKEN", os.environ.get("NOTION_TOKEN", ""))
    notion_db_id = os.environ.get("NOTION_DATABASE_ID_WEEKLY_REPORT", "9d880886-1364-4075-a0b5-f13b4ca46504")
    last_roas = fetch_last_week_roas(notion_token, notion_db_id, report_data["week_label"])
    current_roas = report_data.get("overall_roas", 0)
    wow_html = roas_wow_html(current_roas, last_roas)

    # 廣告列
    boost_rows = "".join(boost_stop_row(a) for a in report_data.get("boost_ads", []))
    stop_rows  = "".join(boost_stop_row(a) for a in report_data.get("stop_ads", []))
    watch_rows = "".join(watch_row(a)      for a in report_data.get("watch_ads", []))
    insuf_rows = "".join(insuf_row(a)      for a in report_data.get("insufficient_ads", []))
    if not boost_rows: boost_rows = '<tr><td colspan="4" style="color:var(--muted);padding:20px;text-align:center">本週無加碼候選</td></tr>'
    if not stop_rows:  stop_rows  = '<tr><td colspan="4" style="color:var(--muted);padding:20px;text-align:center">本週無暫停候選</td></tr>'
    if not watch_rows: watch_rows = '<tr><td colspan="8" style="color:var(--muted);padding:20px;text-align:center">本週無觀察名單</td></tr>'
    if not insuf_rows: insuf_rows = '<tr><td colspan="5" style="color:var(--muted);padding:20px;text-align:center">無資料</td></tr>'

    # 分佈圖
    top10 = report_data.get("top10_spend_ads", [])
    max_spend = max((a.get("spend") or 0 for a in top10), default=1)
    dist_rows = "".join(dist_row_html(a, max_spend) for a in top10)

    # CPA 顏色
    avg_cpa = report_data.get("avg_cpa", 0)
    cpa_class = "good" if avg_cpa < 400 else ("warn" if avg_cpa < 700 else "bad")

    # 替換模板
    replacements = {
        "{{WEEK_LABEL}}":         report_data.get("week_label", ""),
        "{{DATE_START}}":         report_data.get("date_start", ""),
        "{{DATE_END}}":           report_data.get("date_end", ""),
        "{{GENERATED_AT}}":       report_data.get("generated_at", ""),
        "{{TOKEN_WARN_HTML}}":    token_warn_html,
        "{{AI_SUMMARY}}":         html_lib.escape(report_data.get("ai_summary", "─")).replace("\n", "<br>"),
        "{{ROAS}}":               f"{current_roas:.2f}",
        "{{ROAS_PCT}}":           str(roas_pct(current_roas, cap=10)),
        "{{SPEND}}":              fmt_num(report_data.get("total_spend")),
        "{{PURCHASES}}":          fmt_num(report_data.get("total_purchases")),
        "{{REVENUE}}":            fmt_num(report_data.get("total_revenue")),
        "{{AVG_CPA}}":            fmt_num(avg_cpa, 0),
        "{{CPA_CLASS}}":          cpa_class,
        "{{AD_COUNT}}":           fmt_num(report_data.get("ad_count")),
        "{{CTR}}":                f"{report_data.get('overall_ctr', 0):.2f}",
        "{{COUNT_BOOST}}":        str(len(report_data.get("boost_ads", []))),
        "{{COUNT_STOP}}":         str(len(report_data.get("stop_ads", []))),
        "{{COUNT_WATCH}}":        str(len(report_data.get("watch_ads", []))),
        "{{COUNT_INSUFFICIENT}}": str(len(report_data.get("insufficient_ads", []))),
        "{{BOOST_ROWS}}":         boost_rows,
        "{{STOP_ROWS}}":          stop_rows,
        "{{WATCH_ROWS}}":         watch_rows,
        "{{INSUF_ROWS}}":         insuf_rows,
        "{{DIST_ROWS}}":          dist_rows,
        "{{NOTION_URL}}":         report_data.get("notion_url", "#"),
    }

    result = tpl
    for k, v in replacements.items():
        result = result.replace(k, str(v))

    # 週對週插入
    result = result.replace(
        '<div class="kpi-sub">目標 ≥ 5x</div>',
        f'<div class="kpi-sub">目標 ≥ 5x</div>{wow_html}'
    )

    Path(output_dir).mkdir(exist_ok=True)

    # 寫出有日期的版本
    filename = f"weekly_report_{report_data.get('date_end', 'unknown')}.html"
    out_path = Path(output_dir) / filename
    out_path.write_text(result, encoding="utf-8")
    print(f"[HTML] 報告已產生：{out_path}")

    # 同時寫出 index.html（固定連結，永遠是最新週報）
    index_path = Path(output_dir) / "index.html"
    index_path.write_text(result, encoding="utf-8")
    print(f"[HTML] index.html 已更新 → https://welsonchen0704.github.io/meta-ads/")

    return str(out_path)


def integrate_into_main(report_data: dict) -> str:
    """在 main.py 的最後呼叫，同時處理 Token 到期 Telegram 警告。"""
    bot_token    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id      = os.environ.get("TELEGRAM_CHAT_ID", "")
    token_expiry = os.environ.get("META_TOKEN_EXPIRY", "2026-06-06")
    _, days_left = check_token_expiry(token_expiry)
    send_token_warning_telegram(days_left, bot_token, chat_id)
    return build_html_report(report_data)
