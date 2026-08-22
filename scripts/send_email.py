# -*- coding: utf-8 -*-
"""Send the daily summary email via QQ mail SMTP.

Reads data/updates.json, collects today's updated modules, sends ONE plain
email with one summary line per module + site link at the end.

Env vars: SMTP_USER (QQ邮箱), SMTP_PASS (授权码), MAIL_TO (收件人), SITE_URL
"""
import os, sys, smtplib, ssl
from email.mime.text import MIMEText
from email.header import Header

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import today_updates, today_str


def build_body():
    ups = today_updates()
    if not ups:
        return None
    lines = ["今日已更新："]
    for u in ups:
        lines.append("· %s - %s" % (u.get("name", u.get("module")), u.get("summary", "")))
    site = os.environ.get("SITE_URL", "")
    if site:
        lines.append("点击查看：" + site)
    return "\n".join(lines)


def main():
    body = build_body()
    if not body:
        print("no updates today, skip email")
        return

    user = os.environ.get("SMTP_USER", "")
    pwd = os.environ.get("SMTP_PASS", "")
    to = os.environ.get("MAIL_TO", user)
    if not user or not pwd:
        print("[error] SMTP_USER/SMTP_PASS not set")
        sys.exit(1)

    m, d = today_str().split("-")[1:]
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header("【LUO每日必看】%s月%s日 内容已更新" % (int(m), int(d)), "utf-8")
    msg["From"] = user
    msg["To"] = to

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=ctx) as s:
        s.login(user, pwd)
        s.sendmail(user, [to], msg.as_string())
    print("email sent to", to)
    print("---")
    print(body)


if __name__ == "__main__":
    main()
