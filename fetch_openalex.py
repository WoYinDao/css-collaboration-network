"""
fetch_openalex.py —— 从 OpenAlex 抓取「计算社会科学」相关论文的元数据。

做了什么:
- 用「标题或摘要里含确切短语 computational social science」来界定这个领域(约 2520 篇)。
- 只取建网络要用的字段:论文 id、标题、年份、被引数、作者与所属机构。
- 用「游标(cursor)翻页」把所有结果一页页拿下来。
- 出错自动重试(指数退避),每次请求之间留礼貌间隔。
- 支持断点续传:中途断了,再跑一次会从上次的游标接着抓,不重复。

结果存成 data/works.jsonl —— 每行一条 JSON,适合大数据、方便追加。
(data/ 已被 .gitignore 忽略;别人 clone 后重跑此脚本即可重建。)
"""

import json
import os
import time

import requests

# ============ 可调参数(想换研究对象,改这里就行)============
BASE_URL = "https://api.openalex.org/works"
# 领域界定:标题或摘要包含确切短语 "computational social science"
SEARCH_PHRASE = "computational social science"
FILTER = f'title_and_abstract.search:"{SEARCH_PHRASE}"'
# 只取这几个顶层字段(authorships 自带作者+机构的嵌套信息)
SELECT = "id,display_name,publication_year,cited_by_count,authorships"
PER_PAGE = 200            # 每页条数(接口可能上限更低,没关系,游标会自动多翻几页)
SLEEP_BETWEEN = 0.2       # 每次请求之间歇 0.2 秒,礼貌访问
MAX_RETRIES = 5           # 单页最多重试次数
BACKOFF_BASE = 2          # 退避基数:第 n 次重试等待 2**n 秒

OUTPUT_PATH = os.path.join("data", "works.jsonl")
CHECKPOINT_PATH = os.path.join("data", ".fetch_checkpoint.json")

# polite pool:从环境变量读邮箱(不写死在代码里,方便公开仓库)
# 在 PowerShell 里设置:$env:OPENALEX_MAILTO="你的邮箱"
MAILTO = os.environ.get("OPENALEX_MAILTO", "").strip()


def fetch_page(session, cursor):
    """抓一页。带重试 + 退避;成功返回解析后的 JSON(字典)。"""
    params = {
        "filter": FILTER,
        "select": SELECT,
        "per-page": PER_PAGE,
        "cursor": cursor,
    }
    if MAILTO:
        params["mailto"] = MAILTO

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(BASE_URL, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            # 这些是「可重试」的临时性错误:限流或服务器抽风
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = BACKOFF_BASE ** attempt
                print(f"    收到 {resp.status_code},第 {attempt} 次重试前等待 {wait}s ...")
                time.sleep(wait)
                continue
            # 其它错误(比如 400 参数写错)就没必要重试了,直接报出来
            resp.raise_for_status()
        except requests.RequestException as exc:
            wait = BACKOFF_BASE ** attempt
            print(f"    网络异常({exc}),第 {attempt} 次重试前等待 {wait}s ...")
            time.sleep(wait)

    raise RuntimeError(f"连续 {MAX_RETRIES} 次都失败,放弃。")


def load_checkpoint():
    """若存在断点文件,返回上次保存的游标;否则返回 None。"""
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("cursor")
    return None


def save_checkpoint(cursor):
    """保存「下一页」的游标,供断点续传用。"""
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump({"cursor": cursor}, f)


def count_lines(path):
    """数一下文件已有多少行(断点续传时用来显示累计进度)。"""
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def main():
    os.makedirs("data", exist_ok=True)

    # 决定是「续传」还是「从头开始」
    saved_cursor = load_checkpoint()
    if saved_cursor:
        cursor = saved_cursor
        file_mode = "a"          # 追加,接着上次写
        total = count_lines(OUTPUT_PATH)
        print(f"发现断点,从上次的游标继续(已有 {total} 篇)。")
    else:
        cursor = "*"             # 游标翻页的起点
        file_mode = "w"          # 从头写,覆盖旧文件
        total = 0
        print("从头开始抓取。")

    if MAILTO:
        print(f"已启用 polite pool(mailto={MAILTO})。")
    else:
        print("未设置邮箱(OPENALEX_MAILTO),走普通访问通道,小数据量没问题。")

    session = requests.Session()
    session.headers.update({"User-Agent": f"opencode-css/0.1 (mailto:{MAILTO or 'unset'})"})

    page = 0
    with open(OUTPUT_PATH, file_mode, encoding="utf-8") as f:
        while cursor:
            page += 1
            data = fetch_page(session, cursor)
            results = data.get("results", [])
            for work in results:
                f.write(json.dumps(work, ensure_ascii=False) + "\n")
            total += len(results)

            cursor = data["meta"].get("next_cursor")   # 没有下一页时是 None
            save_checkpoint(cursor)

            target = data["meta"].get("count", "?")
            print(f"第 {page:>2} 页:本页 {len(results):>3} 篇,累计 {total} / {target}")

            if not results:        # 防御:空页就停
                break
            time.sleep(SLEEP_BETWEEN)

    # 抓完了:删掉断点文件,留个干净结尾
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)
    print(f"\n完成!共 {total} 篇,已存到 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
