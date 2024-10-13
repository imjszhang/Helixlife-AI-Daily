import os
import time
import re
from datetime import datetime, timedelta, timezone
import pytz
from dotenv import load_dotenv
from feishu_docx_api_handler import FeishuDocxAPIHandler, BlockType, BlockFactory

# 加载环境变量
load_dotenv(override=True)

# 从环境变量中获取 Feishu API 的 App ID 和 App Secret
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET')
FEISHU_DOCX_FOLDER_TOKEN = os.getenv('FEISHU_DOCX_FOLDER_TOKEN')

# 解析Markdown内容，将其转换为日报的记录格式，并组织成指定的日报格式。
def parse_markdown_to_report_data(content, report_title, report_date):
    """
    解析Markdown内容，将其转换为日报的记录格式，并组织成指定的日报格式。
    """
    sections = []
    articles = content.split('# ')  # 每个新闻条目用 "# " 分隔

    for article in articles:
        lines = article.strip().splitlines()
        if not lines:
            continue

        section = {}
        content_list = []
        article_link = ""
        article_title = ""


        for i, line in enumerate(lines):
            if line.startswith('**'):  # 标题
                article_title = line.strip('**').strip()
            elif line.startswith('- '):  # 内容
                if line.startswith('- 原文链接：'):  # 原文链接
                    article_link = line.split('：', 1)[1].strip()
                else:
                    content_list.append(line[2:].strip())

        # 组装 section
        if not article_title:
            continue

        section['heading'] = article_title
        section['content'] = content_list
        section['article_link'] = {
            "text": "点击查看",
            "url": article_link
        }

        if section:
            sections.append(section)

    # 组装最终的 report_data
    report_data = {
        "title": report_title,
        "date": report_date,
        "sections": sections
    }

    return report_data



class DailyReportGenerator:
    def __init__(self, feishu_docx_api_handler: FeishuDocxAPIHandler):
        self.feishu_docx_api_handler = feishu_docx_api_handler

    def generate_report(self, document_id: str, parent_block_id: str, report_data: dict):
        """
        生成日报
        :param document_id: 文档 ID
        :param parent_block_id: 父块 ID
        :param report_data: 日报数据
        """
        # 创建标题块 (HEADING1)
        title_block = BlockFactory.create_block(
            BlockType.HEADING1, 
            [{"content": report_data["title"], "text_element_style": {"bold": True}}],
            style={"align": 1}
        )
        self.feishu_docx_api_handler.create_block(document_id, parent_block_id, [title_block])

        # 创建分割线块 (DIVIDER)
        divider_block = BlockFactory.create_divider_block()
        self.feishu_docx_api_handler.create_block(document_id, parent_block_id, [divider_block])

        # 创建各个部分的块
        for section in report_data["sections"]:
            # 创建每个部分的标题 (HEADING2)
            section_heading_block = BlockFactory.create_block(
                BlockType.HEADING2, 
                [{"content": section["heading"]}],
                style={"align": 1}
            )
            self.feishu_docx_api_handler.create_block(document_id, parent_block_id, [section_heading_block])

            # 创建每个部分的内容（无序列表）(BULLET)
            for content in section["content"]:
                content_block = BlockFactory.create_block(
                    BlockType.BULLET, 
                    [{"content": content}],
                    style={"align": 1}
                )
                self.feishu_docx_api_handler.create_block(document_id, parent_block_id, [content_block])

            # 添加原文链接块 (TEXT + LINK)
            if "article_link" in section:
                product_website_block = BlockFactory.create_block(
                    BlockType.TEXT, 
                    [{"content": f"原文链接："}, {"content": f"{section['article_link']['text']}", "text_element_style": {"link": {"url": section['article_link']['url']}}}]
                )
                self.feishu_docx_api_handler.create_block(document_id, parent_block_id, [product_website_block])

            # 添加分割线块 (DIVIDER)
            self.feishu_docx_api_handler.create_block(document_id, parent_block_id, [divider_block])


#根据日期，创建一个日报
def generate_daily_report(today):

    date_today = today.strftime('%Y-%m-%d')

    # 初始化 FeishuDocxAPIHandler
    feishu_docx_api_handler = FeishuDocxAPIHandler(FEISHU_APP_ID, FEISHU_APP_SECRET)
    # 创建一个新文档
    folder_token = os.getenv('FEISHU_DOCX_FOLDER_TOKEN')
    new_document_title = f"helixlifeAI-daily-{date_today}"
    new_document_id = feishu_docx_api_handler.create_new_document(new_document_title, folder_token=folder_token)

    if new_document_id:
        print(f"新文档已创建，文档 ID 为: {new_document_id}")

        # 获取根块 ID
        root_block_id = new_document_id  # 根块的 block_id 通常与 document_id 相同

       # 获取最新的Markdown文件内容
        file_path = f'data/helixlifeAI-daily-{date_today}.md'

        # 读取指定的Markdown文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                markdown_content = file.read()
        except FileNotFoundError:
            print(f"Error: File not found: {file_path}")
            return None

        # 日报数据
        if markdown_content:
            report_title = f"HelixlifeAI 今日资讯速读 | {date_today}"
            report_date = f"{date_today}"
            report_data = parse_markdown_to_report_data(markdown_content, report_title, report_date)
            #print(report_data)

        # 创建日报生成器
        report_generator = DailyReportGenerator(feishu_docx_api_handler)

        # 生成日报
        report_generator.generate_report(new_document_id, root_block_id, report_data)
        print(f"{date_today}日报文档已创建。")
        return new_document_id
    else:
        print(f"{date_today}日报文档创建失败。")
        return None

def main():
    # 获取今天的日期并格式化
    today = datetime.now(timezone.utc)+timedelta(hours=8)
    
    # 生成今天的日报
    generate_daily_report(today)
   

if __name__ == "__main__":
    main()