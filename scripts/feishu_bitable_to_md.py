import os
import time
from dotenv import load_dotenv
from feishu_bitable_api_handler import FeishuBitableAPIHandler

# 加载环境变量
#load_dotenv(override=True)

# 从环境变量中获取 Feishu API 的 App ID 和 App Secret
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET')
FEISHU_BITABLE_APP_TOKEN = os.getenv('FEISHU_BITABLE_APP_TOKEN')
FEISHU_BITABLE_TABLE_ID = os.getenv('FEISHU_BITABLE_TABLE_ID')


def concat_text(data):
    """
    连接速读内容，将多个文本片段合并为一个字符串。
    
    :param data: 包含 'text' 字段的字典列表
    :return: 合并后的字符串
    """
    text_parts = []
    for item in data:
        if isinstance(item, dict) and 'text' in item:
            text_parts.append(item['text'])
    return ''.join(text_parts)

def fetch_bitable_data():
    """
    从 Feishu Bitable 获取数据。
    
    :return: 返回获取到的记录
    """
    # 获取今天的日期并转换为时间戳
    date = time.strftime("%Y-%m-%d")
    timestamp = int(time.mktime(time.strptime(date, "%Y-%m-%d"))) * 1000

    # 构建查询参数
    args = {
        "sort": [
            {
                "field_name": "推荐级别",
                "desc": True
            },            
            {
                "field_name": "创建时间",
                "desc": True
            }
        ],
        "filter": {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": "标题",
                    "operator": "isNotEmpty",
                    "value": []
                },
                {
                    "field_name": "创建时间",
                    "operator": "is",
                    "value": ["Yesterday"]
                }
            ]
        }
    }

    # 初始化 Feishu Bitable API 处理器
    feishu_bitable_api_handler = FeishuBitableAPIHandler(FEISHU_APP_ID, FEISHU_APP_SECRET)
    
    # 获取记录
    records = feishu_bitable_api_handler.get_record_list(FEISHU_BITABLE_APP_TOKEN, FEISHU_BITABLE_TABLE_ID, args)
    
    return records

def generate_markdown(records):
    """
    生成 Markdown 内容并保存到 data 目录。
    
    :param records: 从 Feishu Bitable 获取的记录
    """
    # 获取今天的日期并格式化
    today = time.strftime("%Y-%m-%d")

    # 初始化 Markdown 内容
    markdown_content = f"# Helixlife-AI-daily 今日资讯速读 | {today}\n\n"

    # 提取记录中的速读内容
    for record in records.get('data', {}).get('items', []):
        # 获取速读内容
        summary = concat_text(record.get('fields', {}).get('速读', [{}]))
        
        # 获取推荐级别
        rating = record.get('fields', {}).get('推荐级别', 0)

        # 将速读内容按行分割
        summary_lines = summary.split('\n')

        # 如果速读内容有多行，插入评分
        if len(summary_lines) > 1:
            first_line = summary_lines[0]
            remaining_lines = '\n'.join(summary_lines[1:])
            markdown_content += f'# {first_line}\n'
            markdown_content += f'- 推荐级别: {rating}\n'
            markdown_content += f'{remaining_lines}\n\n'
        else:
            # 如果速读内容只有一行，直接输出
            markdown_content += f'# {summary}\n'
            markdown_content += f'- 推荐级别: {rating}\n'

    # 确保 data 目录存在
    os.makedirs('data', exist_ok=True)

    # 保存文件到 data 目录
    file_name = f"data/helixlife-AI-daily-{today}.md"
    with open(file_name, 'w', encoding='utf-8') as file:
        file.write(markdown_content)
    
    print(f"文件 {file_name} 生成成功并已覆盖。")

def main():
    # 获取 Feishu Bitable 数据
    records = fetch_bitable_data()

    # 生成并保存 Markdown 文件
    generate_markdown(records)

if __name__ == "__main__":
    main()