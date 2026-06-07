"""
find_communities.py —— 阶段四:在合作网络里找"学派"(社群),并产出一组真正有用的图。

产出 4 张图(都存到 figures/):
  1. papers_per_year.png      —— 逐年论文数(标注未满整年的当前年)。
  2. top_authors.png          —— 核心作者排行(合作最广 / 发文最多)。
  3. coauthor_network.png     —— 前 12 大学派排成一圈,互不重叠,各标主题词。
  4. communities_overview.png —— 各学派规模 + 代表主题词一览。

社群发现用内置于 networkx 的 Louvain 算法,只在最大连通块(巨核)上运行。
"""

import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime

import matplotlib
matplotlib.use("Agg")            # 不弹窗,直接存文件
import matplotlib.pyplot as plt
import networkx as nx
from networkx.algorithms import community as nx_comm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

GRAPH_PATH = os.path.join("data", "coauthor_network.graphml")
WORKS_PATH = os.path.join("data", "works.jsonl")
FIG_DIR = "figures"
SEED = 42

# 做主题词时排除:检索词本身(几乎每个标题都有)+ 通用停用词
SEARCH_WORDS = {"computational", "computation", "social", "science", "sciences"}
STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with", "from",
    "by", "as", "at", "via", "using", "use", "based", "study", "studies", "analysis",
    "approach", "approaches", "new", "toward", "towards", "case", "research", "method",
    "methods", "model", "models", "data", "into", "between", "through", "across",
    "is", "are", "be", "this", "that", "their", "its", "we", "our", "how", "what",
    "can", "but", "der", "about", "during", "following", "not", "all", "more",
    "has", "have", "had", "will", "may", "also", "than", "when", "where", "which",
    "who", "it", "no", "do", "does",
}


def load_works(path):
    works = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                works.append(json.loads(line))
    return works


def top_words(titles, k=8):
    counter = Counter()
    for t in titles:
        for word in re.findall(r"[a-zA-Z]+", t.lower()):
            if len(word) < 3 or word in STOPWORDS or word in SEARCH_WORDS:
                continue
            counter[word] += 1
    return [w for w, _ in counter.most_common(k)]


def fig_papers_per_year(works, path):
    """图1:逐年论文数;把"未满整年的当前年"用灰色标出,避免误读。"""
    cur_year = datetime.now().year
    c = Counter(w.get("publication_year") for w in works if w.get("publication_year"))
    xs = sorted(c)
    ys = [c[y] for y in xs]
    colors = ["#4C72B0" if y < cur_year else "#BBBBBB" for y in xs]

    plt.figure(figsize=(11, 5.5))
    plt.bar(xs, ys, color=colors)
    plt.title("Computational Social Science: number of papers per year", fontsize=14)
    plt.xlabel("Year")
    plt.ylabel("Papers")
    plt.grid(axis="y", alpha=0.3)
    if cur_year in c:
        plt.annotate(f"{cur_year}: partial year\n(data fetched mid-{cur_year})",
                     xy=(cur_year, c[cur_year]),
                     xytext=(cur_year - 16, max(ys) * 0.72),
                     arrowprops=dict(arrowstyle="->", color="gray"),
                     fontsize=9, color="gray")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def fig_top_authors(G, path, top_n=15):
    """图2:核心作者排行(左:合作者数;右:论文数)。"""
    authors = list(G.nodes())
    by_collab = sorted(authors, key=lambda a: G.degree(a), reverse=True)[:top_n]
    by_papers = sorted(authors, key=lambda a: int(G.nodes[a].get("papers", 0)), reverse=True)[:top_n]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    names1 = [G.nodes[a].get("name", a) for a in by_collab][::-1]
    vals1 = [G.degree(a) for a in by_collab][::-1]
    ax1.barh(names1, vals1, color="#55A868")
    ax1.set_title("Most collaborators (distinct co-authors)")
    ax1.set_xlabel("Number of collaborators")

    names2 = [G.nodes[a].get("name", a) for a in by_papers][::-1]
    vals2 = [int(G.nodes[a].get("papers", 0)) for a in by_papers][::-1]
    ax2.barh(names2, vals2, color="#C44E52")
    ax2.set_title("Most papers (in this dataset)")
    ax2.set_xlabel("Number of papers")

    fig.suptitle("Core authors of Computational Social Science", fontsize=15)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_network(H, communities, comm_titles, path, top_k=12):
    """图3:前 top_k 大学派各成一团,均匀摆在一个圆环上,互不重叠,外侧标主题词。"""
    top_comms = communities[:top_k]
    shown = set().union(*top_comms)
    HH = H.subgraph(shown)
    deg = dict(HH.degree())
    cmap = plt.cm.tab20

    # 每个学派一个圆环位置;团内部用小型 spring 布局,再缩放、平移到该位置
    pos = {}
    node2i = {}
    centers = []
    for i, comm in enumerate(top_comms):
        ang = 2 * math.pi * i / top_k - math.pi / 2     # 从正上方开始排
        cx, cy = math.cos(ang), math.sin(ang)
        centers.append((ang, cx, cy, i, comm))
        sub = HH.subgraph(comm)
        if sub.number_of_nodes() <= 1:
            sub_pos = {n: (0.0, 0.0) for n in comm}
        else:
            sub_pos = nx.spring_layout(sub, seed=SEED, k=0.6, iterations=50)
        for node, (x, y) in sub_pos.items():
            pos[node] = (cx + 0.12 * x, cy + 0.12 * y)
            node2i[node] = i

    node_colors = [cmap(node2i[n] % 20) for n in HH.nodes()]
    node_sizes = [12 + 4 * deg.get(n, 0) for n in HH.nodes()]

    plt.figure(figsize=(15, 15))
    nx.draw_networkx_edges(HH, pos, alpha=0.05, width=0.4)
    nx.draw_networkx_nodes(HH, pos, node_color=node_colors, node_size=node_sizes,
                           linewidths=0.2, edgecolors="white")

    for ang, cx, cy, i, comm in centers:
        label = ", ".join(top_words(comm_titles[i], k=2)) or f"#{i}"
        lx, ly = 1.34 * math.cos(ang), 1.34 * math.sin(ang)
        ha = "left" if math.cos(ang) > 0.2 else ("right" if math.cos(ang) < -0.2 else "center")
        plt.text(lx, ly, f"{label}\n(n={len(comm)})", fontsize=11, fontweight="bold",
                 ha=ha, va="center",
                 bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.9))

    plt.title("Computational Social Science — the 12 largest schools (Louvain communities)\n"
              "each blob is one school on a ring, labeled with its top title words",
              fontsize=14)
    plt.axis("off")
    plt.xlim(-1.75, 1.75)
    plt.ylim(-1.75, 1.75)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()


def fig_communities_overview(communities, comm_titles, path):
    """图4:各学派规模 + 主题词一览(横向条形)。"""
    big = [(idx, comm) for idx, comm in enumerate(communities) if len(comm) >= 8]
    big.sort(key=lambda x: len(x[1]))   # 升序,最大的画在最上面
    labels = [", ".join(top_words(comm_titles[idx], k=3)) or f"community {idx}"
              for idx, _ in big]
    sizes = [len(comm) for _, comm in big]
    colors = [plt.cm.tab20(idx % 20) for idx, _ in big]

    plt.figure(figsize=(12, max(6, 0.5 * len(big))))
    plt.barh(range(len(big)), sizes, color=colors)
    plt.yticks(range(len(big)), labels, fontsize=10)
    for i, s in enumerate(sizes):
        plt.text(s + 0.5, i, str(s), va="center", fontsize=9)
    plt.title("Schools (Louvain communities) by size, labeled with top title words", fontsize=14)
    plt.xlabel("Number of authors")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    G = nx.read_graphml(GRAPH_PATH)
    works = load_works(WORKS_PATH)
    print(f"网络 {G.number_of_nodes()} 节点 / {G.number_of_edges()} 边;论文 {len(works)} 篇")

    giant_nodes = max(nx.connected_components(G), key=len)
    H = G.subgraph(giant_nodes).copy()
    communities = sorted(nx_comm.louvain_communities(H, weight="weight", seed=SEED),
                         key=len, reverse=True)
    print(f"巨核 {H.number_of_nodes()} 人,Louvain 找到 {len(communities)} 个学派\n")

    node2comm = {aid: idx for idx, comm in enumerate(communities) for aid in comm}

    comm_titles = {idx: [] for idx in range(len(communities))}
    for w in works:
        votes = Counter()
        for a in w.get("authorships", []):
            aid = (a.get("author") or {}).get("id")
            if aid in node2comm:
                votes[node2comm[aid]] += 1
        if votes:
            comm_titles[votes.most_common(1)[0][0]].append(w.get("display_name") or "")

    deg = dict(H.degree())
    for idx, comm in enumerate(communities):
        if len(comm) < 8:
            continue
        core = sorted(comm, key=lambda a: deg.get(a, 0), reverse=True)[:4]
        core_names = ", ".join(H.nodes[a].get("name", a) for a in core)
        print(f"学派#{idx}({len(comm)}人) 主题[{', '.join(top_words(comm_titles[idx], 5))}] 核心:{core_names}")

    print("\n正在生成 4 张图...")
    fig_papers_per_year(works, os.path.join(FIG_DIR, "papers_per_year.png"))
    fig_top_authors(G, os.path.join(FIG_DIR, "top_authors.png"))
    fig_network(H, communities, comm_titles, os.path.join(FIG_DIR, "coauthor_network.png"))
    fig_communities_overview(communities, comm_titles, os.path.join(FIG_DIR, "communities_overview.png"))
    print(f"完成,4 张图已存到 {FIG_DIR}/")


if __name__ == "__main__":
    main()
