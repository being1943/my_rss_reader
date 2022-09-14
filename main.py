import json
import os
import pprint
import re
import shutil
import time
from datetime import datetime
from multiprocessing import Pool, Manager
from urllib.parse import urlparse

import feedparser
import pytz
import requests
import yagmail


def get_rss_info(feed_url, index, rss_info_list):
    result = {"result": []}
    request_success = False
    # 如果请求出错,则重新请求,最多五次
    for i in range(3):
        if not request_success:
            try:
                headers = {
                    # 设置用户代理头(为狼披上羊皮)
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36",
                    "Content-Encoding": "gzip"
                }
                # 三次分别设置8, 16, 24秒钟超时
                feed_url_content = requests.get(feed_url, timeout=(i + 1) * 8, headers=headers).content
                feed = feedparser.parse(feed_url_content)
                feed_entries = feed["entries"]
                feed_entries_length = len(feed_entries)
                print("==feed_url=>>", feed_url, "==len=>>", feed_entries_length)
                for entrie in feed_entries[0: feed_entries_length - 1]:
                    title = entrie["title"]
                    link = entrie["link"]
                    date = time.strftime("%Y-%m-%d", entrie["published_parsed"])

                    title = title.replace("\n", "")
                    title = title.replace("\r", "")

                    result["result"].append({
                        "title": title,
                        "link": link,
                        "date": date
                    })
                request_success = True
            except Exception as e:
                print(feed_url + "第+" + str(i) + "+次请求出错==>>", e)
                pass
        else:
            pass

    rss_info_list[index] = result["result"]
    print("本次爬取==》》", feed_url, "<<<===", index, result["result"])
    pprint.pp(result)
    # 剩余数量
    remaining_amount = 0

    for tmp_rss_info_atom in rss_info_list:
        if isinstance(tmp_rss_info_atom, int):
            remaining_amount = remaining_amount + 1

    print("当前进度 | 剩余数量", remaining_amount, "已完成==>>", len(rss_info_list) - remaining_amount)
    return result["result"]


def send_mail(email, title, contents):
    # 判断secret.json是否存在
    try:
        with open(os.path.join(os.getcwd(), "secret.json"), 'r', encoding='utf-8') as load_f:
            load_dict = json.load(load_f)
            user = load_dict["user"]
            password = load_dict["password"]
            host = load_dict["host"]
            # print(load_dict)
            yag = yagmail.SMTP(user=user, password=password, host=host)
            # 发送邮件
            yag.send(email, title, contents)
    except:
        print("发送邮件失败")

    # 连接邮箱服务器
    # yag = yagmail.SMTP(user=user, password=password, host=host)


def replace_readme():
    # 读取EditREADME.md
    print("replace_readme")
    with open(os.path.join(os.getcwd(), "EditREADME.md"), 'r', encoding='utf-8') as load_f:
        edit_readme_md = load_f.read();

        before_info_list = re.findall(r'\{\{latest_content\}\}.*\[订阅地址\]\(.*\)', edit_readme_md);
        # 填充统计RSS数量
        # 填充统计时间
        ga_rss_datetime = datetime.fromtimestamp(int(time.time()), pytz.timezone('Asia/Shanghai')).strftime(
            '%Y-%m-%d %H:%M:%S')

        new_edit_readme_md = edit_readme_md \
            .replace("{{rss_num}}", str(len(before_info_list))) \
            .replace("{{ga_rss_datetime}}", str(ga_rss_datetime))
        # 使用进程池进行数据获取，获得rss_info_list
        before_info_list_len = len(before_info_list)
        rss_info_list = Manager().list(range(before_info_list_len))
        print('初始化完毕==》', rss_info_list)

        # 创建一个最多开启8进程的进程池
        po = Pool(8)

        for index, before_info in enumerate(before_info_list):
            # 获取link
            link = re.findall(r'\[订阅地址\]\((.*)\)', before_info)[0]
            po.apply_async(get_rss_info, (link, index, rss_info_list))

        # 关闭进程池,不再接收新的任务,开始执行任务
        po.close()

        # 主进程等待所有子进程结束
        po.join()
        pprint.pprint(list(rss_info_list))

        for index, before_info in enumerate(before_info_list):
            # 获取link
            link = re.findall(r'\[订阅地址\]\((.*)\)', before_info)[0]
            # 生成超链接
            rss_acticle_list = rss_info_list[index]
            parse_result = urlparse(link)
            scheme_netloc_url = str(parse_result.scheme) + "://" + str(parse_result.netloc)

            # 加入到索引
            try:
                new_num, today_news_list = extract_today_rss(rss_acticle_list)
            except:
                print("An exception occurred")
            latest_content = ''
            for rss_acticle in rss_acticle_list[:5]:
                latest_content = latest_content + " ‣ " + f'<a href="{rss_acticle["link"]}" target="_blank">{rss_acticle["title"]}</a><br/>'

            if not latest_content:
                latest_content = "[暂无法通过爬虫获取信息, 点击进入源网站主页](" + scheme_netloc_url + ")"
            # if len(rss_acticle_list) > 0:
            #     rss_acticle_list[0]["title"] = rss_acticle_list[0]["title"].replace("|", "\|")
            #     rss_acticle_list[0]["title"] = rss_acticle_list[0]["title"].replace("[", "\[")
            #     rss_acticle_list[0]["title"] = rss_acticle_list[0]["title"].replace("]", "\]")
            #
            #     latest_content = "[" + rss_acticle_list[0]["title"] + (" 🌈 " + rss_acticle_list[0]["date"] if (
            #             rss_acticle_list[0]["date"] == datetime.today().strftime("%Y-%m-%d")) else " \| " +
            #                                                                                        rss_acticle_list[0][
            #                                                                                            "date"]) + "](" + \
            #                      rss_acticle_list[0]["link"] + ")"
            #
            # if len(rss_acticle_list) > 1:
            #     rss_acticle_list[1]["title"] = rss_acticle_list[1]["title"].replace("|", "\|")
            #     rss_acticle_list[1]["title"] = rss_acticle_list[1]["title"].replace("[", "\[")
            #     rss_acticle_list[1]["title"] = rss_acticle_list[1]["title"].replace("]", "\]")
            #
            #     latest_content = latest_content + "<br/>[" + rss_acticle_list[1]["title"] + (
            #         " 🌈 " + rss_acticle_list[0]["date"] if (
            #                 rss_acticle_list[0]["date"] == datetime.today().strftime("%Y-%m-%d")) else " \| " +
            #                                                                                            rss_acticle_list[
            #                                                                                                0][
            #                                                                                                "date"]) + "](" + \
            #                      rss_acticle_list[1]["link"] + ")"

            # 生成after_info
            after_info = before_info.replace("{{latest_content}}", latest_content)
            print("====latest_content==>", latest_content)
            # 替换edit_readme_md中的内容
            new_edit_readme_md = new_edit_readme_md.replace(before_info, after_info)

    # 替换EditREADME中的索引
    new_edit_readme_md = new_edit_readme_md.replace("{{news}}", ''.join(today_news_list))
    # 替换EditREADME中的新文章数量索引
    new_edit_readme_md = new_edit_readme_md.replace("{{new_num}}", str(new_num))
    # 添加CDN
    new_edit_readme_md = new_edit_readme_md.replace("./_media",
                                                    "https://cdn.jsdelivr.net/gh/zhaoolee/garss/_media")

    # 将新内容
    with open(os.path.join(os.getcwd(), "README.md"), 'w', encoding='utf-8') as load_f:
        load_f.write(new_edit_readme_md)
    return new_edit_readme_md


def extract_today_rss(rss_acticle_list):
    new_num = 0
    today_news_list = list()
    """获取今日Rss信息放到新闻"""
    for rss_acticle in rss_acticle_list:
        if rss_acticle["date"] == datetime.today().strftime("%Y-%m-%d"):
            new_num = new_num + 1
            today_news_list.append(
                f"<div style='line-height:3;{'background-color:#FAF6EA;' if new_num % 2 == 0 else ''}'>"
                f"<a href='{rss_acticle['link']}' style='line-height:2;text-decoration:none;display:block;color:#584D49;' target='_blank'>🌈 {new_num}. {rss_acticle['title']}</a></div>")
    return new_num, today_news_list


# 将README.md复制到docs中

def cp_readme_md_to_docs():
    shutil.copyfile(os.path.join(os.getcwd(), "README.md"), os.path.join(os.getcwd(), "docs", "README.md"))


def cp_media_to_docs():
    if os.path.exists(os.path.join(os.getcwd(), "docs", "_media")):
        shutil.rmtree(os.path.join(os.getcwd(), "docs", "_media"))
    shutil.copytree(os.path.join(os.getcwd(), "_media"), os.path.join(os.getcwd(), "docs", "_media"))


def get_email_list():
    email_list = []
    with open(os.path.join(os.getcwd(), "tasks.json"), 'r', encoding='utf-8') as load_f:
        load_dic = json.load(load_f)
        for task in load_dic["tasks"]:
            email_list.append(task["email"])
    return email_list


# 创建opml订阅文件

def create_opml():
    result = "";
    result_v1 = "";

    # <outline text="CNET News.com" description="Tech news and business reports by CNET News.com. Focused on information technology, core topics include computers, hardware, software, networking, and Internet media." htmlUrl="http://news.com.com/" language="unknown" title="CNET News.com" type="rss" version="RSS2" xmlUrl="http://news.com.com/2547-1_3-0-5.xml"/>

    with open(os.path.join(os.getcwd(), "EditREADME.md"), 'r', encoding='utf-8') as load_f:
        edit_readme_md = load_f.read();

        ## 将信息填充到opml_info_list
        opml_info_text_list = re.findall(r'.*\{\{latest_content\}\}.*\[订阅地址\]\(.*\).*', edit_readme_md);

        for opml_info_text in opml_info_text_list:
            # print('==', opml_info_text)

            opml_info_text_format_data = re.match(r'\|(.*)\|(.*)\|(.*)\|(.*)\|.*\[订阅地址\]\((.*)\).*\|',
                                                  opml_info_text)

            # print("data==>>", opml_info_text_format_data)

            # print("总信息", opml_info_text_format_data[0].strip())
            # print("编号==>>", opml_info_text_format_data[1].strip())
            # print("text==>>", opml_info_text_format_data[2].strip())
            # print("description==>>", opml_info_text_format_data[3].strip())
            # print("data004==>>", opml_info_text_format_data[4].strip())
            print('##', opml_info_text_format_data[2].strip())
            print(opml_info_text_format_data[3].strip())
            print(opml_info_text_format_data[5].strip())

            opml_info = {}
            opml_info["text"] = opml_info_text_format_data[2].strip()
            opml_info["description"] = opml_info_text_format_data[3].strip()
            opml_info["htmlUrl"] = opml_info_text_format_data[5].strip()
            opml_info["title"] = opml_info_text_format_data[2].strip()
            opml_info["xmlUrl"] = opml_info_text_format_data[5].strip()

            # print('opml_info==>>', opml_info);

            opml_info_text = '<outline  text="{text}" description="{description}" htmlUrl="{htmlUrl}" language="unknown" title="{title}" type="rss" version="RSS2" xmlUrl="{xmlUrl}"/>'

            opml_info_text_v1 = '      <outline text="{title}" title="{title}" type="rss"  \n            xmlUrl="{xmlUrl}" htmlUrl="{htmlUrl}"/>'

            opml_info_text = opml_info_text.format(
                text=opml_info["text"],
                description=opml_info["description"],
                htmlUrl=opml_info["htmlUrl"],
                title=opml_info["title"],
                xmlUrl=opml_info["xmlUrl"]
            )

            opml_info_text_v1 = opml_info_text_v1.format(
                htmlUrl=opml_info["htmlUrl"],
                title=opml_info["title"],
                xmlUrl=opml_info["xmlUrl"]
            )

            result = result + opml_info_text + "\n"

            result_v1 = result_v1 + opml_info_text_v1 + "\n"

    zhaoolee_github_garss_subscription_list = "";
    with open(os.path.join(os.getcwd(), "rss-template-v2.txt"), 'r', encoding='utf-8') as load_f:
        zhaoolee_github_garss_subscription_list_template = load_f.read();
        GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
        date_created = datetime.utcnow().strftime(GMT_FORMAT);
        date_modified = datetime.utcnow().strftime(GMT_FORMAT);
        zhaoolee_github_garss_subscription_list = zhaoolee_github_garss_subscription_list_template.format(result=result,
                                                                                                          date_created=date_created,
                                                                                                          date_modified=date_modified);
        # print(zhaoolee_github_garss_subscription_list);

    # 将内容写入
    with open(os.path.join(os.getcwd(), "zhaoolee_github_garss_subscription_list_v2.opml"), 'w',
              encoding='utf-8') as load_f:
        load_f.write(zhaoolee_github_garss_subscription_list)

    zhaoolee_github_garss_subscription_list_v1 = ""
    with open(os.path.join(os.getcwd(), "rss-template-v1.txt"), 'r', encoding='utf-8') as load_f:
        zhaoolee_github_garss_subscription_list_template = load_f.read();
        zhaoolee_github_garss_subscription_list_v1 = zhaoolee_github_garss_subscription_list_template.format(
            result=result_v1);
        # print(zhaoolee_github_garss_subscription_list_v1);

    # 将内容写入
    with open(os.path.join(os.getcwd(), "zhaoolee_github_garss_subscription_list_v1.opml"), 'w',
              encoding='utf-8') as load_f:
        load_f.write(zhaoolee_github_garss_subscription_list_v1)

    # print(result)


def main():
    create_opml()
    new_read_me = replace_readme()
    cp_readme_md_to_docs()
    cp_media_to_docs()
    email_list = get_email_list()

    mail_re = r'邮件内容区开始>([.\S\s]*)<邮件内容区结束'
    re_result = re.findall(mail_re, new_read_me)

    try:
        send_mail(email_list, f"My-Rss-Reader每日速递（{datetime.today().strftime('%Y-%m-%d')}）", re_result)
    except Exception as e:
        print("==邮件设信息置错误===》》", e)


if __name__ == "__main__":
    main()
