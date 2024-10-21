import json
import re
from datetime import datetime, timedelta, timezone
import pytz
from feishu_drive_api_handler import FeishuDriveAPIHandler
from feishu_docx_api_handler import FeishuDocxAPIHandler, BlockType, BlockBatchUpdateRequestBuilder
import os
#from dotenv import load_dotenv
#load_dotenv(override=True)

FEISHU_APP_ID = os.getenv('FEISHU_APP_ID')
FEISHU_APP_SECRET= os.getenv('FEISHU_APP_SECRET')

# 初始化 FeishuDocxAPIHandler
feishu_docx_api_handler = FeishuDocxAPIHandler(FEISHU_APP_ID, FEISHU_APP_SECRET)

# 初始化 FeishuDriveAPIHandler
feishu_drive_api_handler = FeishuDriveAPIHandler(FEISHU_APP_ID, FEISHU_APP_SECRET)


# 根据日期，获取飞书文件夹里特定名字的文件的 URL
def get_file_url_by_date(date_str):
    """
    根据日期，获取文件夹里特定名字的文件
    """
    folder_token="Fyj3fEqQ4lMMkZdwrYpcmOfUnWp"
    name = f"helixlife-AI-daily-{date_str}"  # 使用 f-string 格式化日期
    file_list, _ = feishu_drive_api_handler.get_folder_files(folder_token, page_size=10)  # 解包元组，忽略第二个元素
    
    # 打印 file_list 以调试
    print(f"文件列表: {file_list}")
    
    # 确保 file_list 是一个列表，并且每个元素是字典
    if isinstance(file_list, list):
        for file in file_list:
            # 确保 file 是字典
            if isinstance(file, dict) and 'name' in file:
                if name == file['name']:
                    return file
    return None
    
# 批量修改指定文档的块，根据块的类型选择合适的更新方法
def batch_modify_document_blocks(document_id, blocks, modifications):
    """
    批量修改文档中的块，根据块的类型选择合适的更新方法
    :param document_id: 文档 ID
    :param blocks: 文档的块信息
    :param modifications: 包含块 ID 和修改内容的字典列表
    :return: 批量更新块的响应
    """
    # 创建批量更新请求构建器
    batch_update_builder = BlockBatchUpdateRequestBuilder()

    # 遍历每个修改项，构建批量更新请求
    for modification in modifications:
        block_id = modification.get("block_id")
        new_content = modification.get("new_content")
        text_style = modification.get("text_style", None)

        # 查找对应的块类型
        block_type = None
        for block in blocks:
            if block.get("block_id") == block_id:
                block_type = block.get("block_type")
                break

        # 根据块类型选择合适的更新方法
        if block_type == BlockType.TEXT.position:
            # 如果是文本块，使用 add_update_text
            print(f"块 {block_id} 是文本块，更新内容为: {new_content}")
            batch_update_builder.add_update_text(block_id, new_content, text_style)
        elif block_type == BlockType.HEADING2.position:
            # 如果是标题块，使用 add_update_text，并可能应用不同的样式
            print(f"块 {block_id} 是标题块，更新内容为: {new_content}")
            batch_update_builder.add_update_text(block_id, new_content, text_style)
        elif block_type == BlockType.BULLET.position:
            # 如果是列表块，使用 add_update_text
            print(f"块 {block_id} 是列表块，更新内容为: {new_content}")
            batch_update_builder.add_update_text(block_id, new_content)
        elif block_type == BlockType.CALLOUT.position:
            # 如果是 callout 块，使用 add_update_text_elements
            print(f"块 {block_id} 是 callout 块，更新内容为: {new_content}")
            batch_update_builder.add_update_text_elements(block_id, new_content)
        else:
            # 其他类型的块，暂时不处理
            print(f"块 {block_id} 的类型 {block_type} 暂不支持更新")

    # 构建批量更新请求
    requests_list = batch_update_builder.build()
    print(f"批量更新请求列表: {requests_list}")

    # 调用批量更新接口
    return feishu_docx_api_handler.batch_update_blocks(document_id, requests_list)



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


def extract_top_projects_from_report(date_block_id, file_block_id, report_data, block_ids, top_n=3):
    """
    从 parse_markdown_to_feishu_docx 函数的输出中提取内容，并生成飞书文档的修改列表。
    允许通过 top_n 参数指定提取的项目数量，并通过 block_ids 数组为每个项目动态分配 block_id。
    """
    file= get_file_url_by_date(report_data["date"]) 

    modifications = [
        # 日期块
        {
            "block_name": "日期",
            "block_id": date_block_id,  # 块 ID
            "new_content": [
                {"content": report_data["date"], "text_element_style": {"bold": False}}  # 使用报告中的日期
            ]
        },
        # 文件链接块
        {
            "block_name": "文件链接",
            "block_id": file_block_id,  # 块 ID
            "new_content": [
                {"content": "查看当天全部资讯：", "text_element_style": {"bold": False}},
                {"content": "查看", "text_element_style": {
                    "bold": False,
                    "link": {"url": f"{file['url']}"}  # 更新网址
                }}
            ]
        }
    ]
    
    # 项目模板
    project_template = [
        {
            "block_name": "项目 {index}：标题",
            "block_id": "test",  # 块 ID
            "new_content": [
                {"content": "{title}", "text_element_style": {"bold": False}}  # 新的标题内容
            ]
        },
        {
            "block_name": "项目 {index}：描述1",
            "block_id": "test",  # 块 ID
            "new_content": [
                {"content": "{content1}", "text_element_style": {"bold": False}}  # 更新内容1
            ]
        },
        {
            "block_name": "项目 {index}：描述2",
            "block_id": "test",  # 块 ID
            "new_content": [
                {"content": "{content2}", "text_element_style": {"bold": False}}  # 更新内容2
            ]
        },  
        {
            "block_name": "项目 {index}：描述3",
            "block_id": "test",  # 块 ID
            "new_content": [
                {"content": "{content3}", "text_element_style": {"bold": False}}  # 更新内容3
            ]
        },        
        {
            "block_name": "项目 {index}：网址",
            "block_id": "test",  # 块 ID
            "new_content": [
                {"content": "原文链接：", "text_element_style": {"bold": False}},
                {"content": "查看", "text_element_style": {
                    "bold": False,
                    "link": {"url": "{url}"}  # 更新网址
                }}
            ]
        }
    ]
    
    # 遍历报告中的每个 section，最多提取 top_n 个项目
    for i, section in enumerate(report_data["sections"][:top_n], start=1):
        title = section["heading"] # 提取标题
        content1 = section["content"][0]  # 提取内容1
        content2 = section["content"][1]  # 提取内容2
        content3 = section["content"][2]  # 提取内容3
        url = section["article_link"]["url"]  # 原文链接
        
        
        # 填充每个项目的字段
        for j, template in enumerate(project_template, start=1):
            # 获取当前项目的 block_id
            block_id = block_ids[i - 1][j - 1] if j - 1 < len(block_ids[i - 1]) else "default_block_id"  # 如果 block_ids 不够用，使用默认值            
            filled_template = {
                "block_name": template["block_name"].format(index=i),
                "block_id": block_id,  # 使用动态分配的 block_id
                "new_content": [
                    {
                        "content": template["new_content"][0]["content"].format(
                            index=i, title=title, content1=content1, content2=content2, content3=content3, url=url
                        ),
                        "text_element_style": {"bold": False}
                    }
                ]
            }
            
            # 检查 new_content 列表是否有第二个元素，并且该元素包含 "link"
            if len(template["new_content"]) > 1 and "link" in template["new_content"][1]["text_element_style"]:
                filled_template["new_content"].append({
                    "content": "查看",
                    "text_element_style": {
                        "bold": False,
                        "link": {"url": url}
                    }
                })
            
            modifications.append(filled_template)
    
    return modifications


# 读取本地Markdown文件
def read_markdown_file(file_path):
    """
    从本地文件读取Markdown内容
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# 读取并解析 Markdown 文件
def process_markdown_file_for_date(startdate, block_ids, date_block_id, file_block_id, document_id, blocks):
    """
    处理指定日期的 Markdown 文件，生成 report_data 并应用到飞书文档中。
    :param startdate: 开始日期
    :param block_ids: 每个项目的 block_id 列表
    :param date_block_id: 日期块的 block_id
    :param document_id: 飞书文档的 ID
    :param blocks: 文档的块信息
    """
    # 格式化日期
    startdate_str = startdate.strftime('%Y-%m-%d')

    # 获取最新的Markdown文件内容
    file_path = f'data/helixlife-AI-daily-{startdate_str}.md'
    markdown_content = read_markdown_file(file_path)

    # 从Markdown生成report_data
    report_title = f"Helixlife-AI-daily 今日资讯速读 | {startdate_str}"
    report_date = startdate_str
    report_data = parse_markdown_to_report_data(markdown_content, report_title, report_date)

    # 从report_data生成modifications，提取前3个项目
    modifications = extract_top_projects_from_report(date_block_id, file_block_id, report_data, block_ids)

    # 调用批量修改方法
    batch_modify_document_blocks(document_id, blocks, modifications)


# 处理多个日期的 Markdown 文件
def process_multiple_dates(document_id, blocks, date_block_ids, file_block_ids, block_ids_list, days_to_process=0):
    """
    处理多个日期的 Markdown 文件，并将其内容应用到飞书文档中。
    :param document_id: 飞书文档的 ID
    :param blocks: 文档的块信息
    :param date_block_ids: 每个日期对应的块 ID 列表
    :param block_ids_list: 每个项目的 block_id 列表
    :param days_to_process: 要处理的天数
    """
    today = datetime.now(timezone.utc)

    for i in range(len(date_block_ids)):
        # 获取开始日期
        startdate = today - timedelta(days=i + days_to_process)

        # 获取对应的 block_id
        date_block_id = date_block_ids[i]
        file_block_id = file_block_ids[i]
        block_ids = block_ids_list[i]

        # 处理指定日期的 Markdown 文件
        process_markdown_file_for_date(startdate, block_ids, date_block_id, file_block_id, document_id, blocks)


# 主函数
def main():

    # 指定要获取的文档 ID
    document_id = "DlQRdPgdoobL4Ixq9kbcQdE8nNh"
    document_blocks = feishu_docx_api_handler.get_document_blocks(document_id)
    blocks = document_blocks.get('data', {}).get('items', [])

    # 预定义的 block_id 数组
    date_block_ids = [
        "doxcn2b9xmUFDZ4mpgfTcPt9FBf",  # 第一天的日期块 ID
        "A2tHdgXiWob1P7xwtsmcC3MZnFc",  # 第二天的日期块 ID
        "WVRqdUevRoCtA9x3Xg1cTnZInjd",  # 第三天的日期块 ID
    ]

    file_block_ids = [
        "ArVZdFk7zoS0fxxCJGncbuwZnTg",  # 第一天的文件链接块 ID
        "IgyUdUcD5oGLgXxktjMcI5Vgnte",  # 第二天的文件链接块 ID
        "YhGqdRyaboakB2xruzScpAEonFg",  # 第三天的文件链接块 ID
    ]

    block_ids_list = [
        #第一天的项目块 ID 列表
        [
            [
            "doxcnaxeHCVCLbvnsE1R6X7CO5u",
            "doxcnFN3RnnrGoTldsdTtGh1iyc",
            "YFwOdqzldoudlUxiLAScjsc9ntg",
            "MBKQdunYyoBHlbxMBDFcDVoFnkb",
            "doxcnMuXZa3dnLUOqYeuegzuxNe"
            ],
            [
            "doxcnjrrpQlWtOj4WSvLTXiQ2Te",
            "QbiGd52RXouawZxhSpZcSsyRnQg",
            "SqU6dfJYloX3QexwBXBcQQ2knrT",
            "LdBxdFiwXo017GxAcAYcKl1Hnic",
            "doxcnSbnwGCjjZJOlHbFnabsqwf"
            ],
            [
            "doxcntTsGoe9X0ziEx9ufkQxr3e",
            "A8oddUqjSo18oUxC0Jfc2I1VnYc",
            "BB3gdvDXeo0szBxkkPhc8nMZn6f",
            "PptRde5aToVOrwxyKJRcXgksnfg",
            "doxcnn0pgzRj2y2DxIUMKCylHbG"
            ]
        ],
        #第二天的项目块 ID 列表
        [
            [
            "A8aZduRrboSXOExJecVcEuIRnWc",
            "LSgddf5qro8T3nxDfw1cvndVnlR",
            "Ioxrd0M9WowJVRxhSqycG9OnnKf",
            "JjoSdsf7vohHO5xa4NLc3Gvdnvh",
            "XQludqj4ToxhzQxHvV7cbO4snld"
            ],
            [
            "OC5sd2RihoCoOyxvp5ccm7TXnnf",
            "D3qTdTeqNoxU7MxO4p1cfEfjnXK",
            "Wgt4dTPIto0RaEx8cgrcurUunCh",
            "MU2PdvRIeowRZ4xBOv4cz6s7npg",
            "TK9hdPqoaovhOXxAbHlc4RMwnm3"
            ],
            [
            "EnsZdYR70omCg2xndslcdCTHnQc",
            "QKWYdzfZSoDAVFxV15DciKRInlh",
            "IsABdSnUKovffXxNgdNc95ZLnBd",
            "KjyNdbH6aogkuKx1XvJcEviSnqe",
            "DH6PdDs12o9y9qxkwB1cFyr8nEb"
            ]
        ],
        #第三天的项目块 ID 列表
        [
            [
            "WPXQdeNjRoecJlxJlr1cUgD6nde",
            "Hscfd3YE2o2LjHxiZNncqDaynEg",
            "SpHYdoF3do66VUxNq1GcNAwUnrf",
            "PGk5doERYoIaOPx3KxccA5LLnyh",
            "OoYkdonauoZGyZxxLSNcaJelnNe"
            ],
            [
            "UutIdmgoJoRHLBxl3vYcAqmWnlg",
            "UqNLdAHvuofoiOxaXABcFuK2nJn",
            "YeQld9M6xoKJk8x28hGcHAzOnyb",
            "Hi4ydcL3ho5BxLxCN58cKMsfnNe",
            "O2nWdrjaeotVonxUMCecigj4n0b"
            ],
            [
            "SPIbduVKfovrPYxbAdccIlAhnjh",
            "RrRUdJ278oOM5rxtqf2cRQHnnnf",
            "HbnndGqsYoGBsgxpxtScmWH4nId",
            "Ihhydm6VYowerwxG0bWcSt26n7b",
            "BtROdgSoHoqliVxuG3nc3hO4nhh"
            ]
        ],        
    ]

    # 处理最近 3 天的 Markdown 文件
    process_multiple_dates(document_id, blocks, date_block_ids, file_block_ids, block_ids_list, days_to_process=0)


if __name__ == "__main__":
    main()