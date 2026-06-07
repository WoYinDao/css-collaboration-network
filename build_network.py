"""
build_network.py —— 读入论文数据,搭建作者合作(合著)网络,并算几个基础指标。

网络怎么建:
- 节点(point)= 一位作者(用 OpenAlex 的作者 id 唯一标识,避免重名混淆)。
- 边(edge)  = 两位作者合写过论文;合写次数越多,边的 weight 越大。
- 个别论文作者极多(几十上百人),会造出巨大的"全连接团"扭曲网络,
  所以作者数超过 MAX_AUTHORS_FOR_EDGES 的论文「只计作者、不连边」。

输出:
- 屏幕打印基础指标(每个指标附一句通俗解释)。
- 把网络存成 data/coauthor_network.graphml,供阶段四(找学派+画图)直接读取。
"""

import itertools
import json
import os
import sys
from collections import Counter

import networkx as nx

# 统一用 UTF-8 输出,避免作者名里的特殊字符(如希腊字母、特殊连字符)
# 在某些控制台/管道编码下触发 UnicodeEncodeError。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INPUT_PATH = os.path.join("data", "works.jsonl")
GRAPH_OUT = os.path.join("data", "coauthor_network.graphml")
MAX_AUTHORS_FOR_EDGES = 50   # 作者多于此数的论文不连边(只计作者)


def load_works(path):
    """逐行读 JSONL,每行解析成一篇论文(字典)。"""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def build_graph(works):
    G = nx.Graph()
    paper_count = Counter()       # 作者 id -> 在本数据集里写了几篇
    skipped_big = 0               # 因作者过多而未连边的论文数

    for w in works:
        # 取出这篇论文里「有 id 的作者」,顺便去重(同一篇里偶有重复)
        authors = {}
        for a in w.get("authorships", []):
            au = a.get("author") or {}
            aid = au.get("id")
            if aid:
                authors[aid] = au.get("display_name") or ""

        # 加节点 + 累计每位作者的论文数
        for aid, name in authors.items():
            if not G.has_node(aid):
                G.add_node(aid, name=name)
            paper_count[aid] += 1

        # 连边:论文内两两作者之间连边(合著关系)
        if len(authors) > MAX_AUTHORS_FOR_EDGES:
            skipped_big += 1
            continue
        for a1, a2 in itertools.combinations(authors.keys(), 2):
            if G.has_edge(a1, a2):
                G[a1][a2]["weight"] += 1
            else:
                G.add_edge(a1, a2, weight=1)

    # 把论文数写进节点属性(GraphML 会一起存下来)
    for aid, c in paper_count.items():
        G.nodes[aid]["papers"] = c

    return G, paper_count, skipped_big


def name_of(G, aid):
    return G.nodes[aid].get("name", aid)


def main():
    works = list(load_works(INPUT_PATH))
    print(f"读入论文:{len(works)} 篇\n")

    G, paper_count, skipped_big = build_graph(works)
    n = G.number_of_nodes()
    m = G.number_of_edges()

    print("=" * 56)
    print("基础网络指标")
    print("=" * 56)

    # 1) 规模
    print(f"\n[规模] 节点 {n} 个、边 {m} 条")
    print("  - 节点=不同作者人数;边=有过合作的作者对数。")
    if skipped_big:
        print(f"  - 注:有 {skipped_big} 篇论文作者超过 {MAX_AUTHORS_FOR_EDGES} 人,只计作者未连边。")

    # 2) 度:每个作者有多少个不同的合作者
    degrees = [d for _, d in G.degree()]
    avg_deg = sum(degrees) / n if n else 0
    max_deg = max(degrees) if degrees else 0
    print(f"\n[度] 平均 {avg_deg:.2f}、最大 {max_deg}")
    print("  - 一个作者的'度'=他有多少位不同的合作者。平均度反映这领域合作的普遍程度。")

    # 3) 连通性:网络是连成一片还是碎成很多块
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    giant = components[0] if components else set()
    giant_frac = len(giant) / n if n else 0
    print(f"\n[连通性] 连通块 {len(components)} 个;最大一块含 {len(giant)} 人(占 {giant_frac:.1%})")
    print("  - '连通块'=互相能通过合作关系连到一起的人群。最大块叫'巨核',")
    print("    巨核越大,说明这领域越像一个彼此连通的整体,而非各自为政的小圈子。")

    # 4) 合作最多的作者(按不同合作者数 = 度)
    top_by_degree = sorted(G.degree, key=lambda x: x[1], reverse=True)[:10]
    print("\n[合作最广的 10 位作者](按不同合作者数量)")
    for aid, deg in top_by_degree:
        print(f"  {deg:>4} 位合作者 | {paper_count[aid]:>3} 篇 | {name_of(G, aid)}")

    # 5) 发文最多的作者(按论文数)
    print("\n[发文最多的 10 位作者](按本数据集内论文数)")
    for aid, cnt in paper_count.most_common(10):
        print(f"  {cnt:>3} 篇 | {G.degree(aid):>4} 位合作者 | {name_of(G, aid)}")

    # 存档,供阶段四使用
    nx.write_graphml(G, GRAPH_OUT)
    print(f"\n网络已存到 {GRAPH_OUT}")


if __name__ == "__main__":
    main()
