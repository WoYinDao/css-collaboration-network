"""
find_communities.py —— 阶段四:在合作网络里找"学派"(社群),并产出一组真正有用的图。

相比单张"毛球图",这里产出 4 张直接回答问题的图(都存到 figures/):
  1. papers_per_year.png      —— 逐年论文数:这个领域怎么发展起来的。
  2. top_authors.png          —— 核心作者排行(合作最广 / 发文最多)。
  3. coauthor_network.png     —— 网络图,但给每个学派标上"主题词",颜色才有意义。
  4. communities_overview.png —— 各学派规模 + 代表主题词一览。

社群发现用内置于 networkx 的 Louvain 算法,只在最大连通块(巨核)上运行。
"""

import json
import os
import re
import sys
from collections import Counter

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
    """图1:逐年论文数。"""
    years = [w.get("publication_year") for w in works if w.get("publication_year")]
    c = Counter(years)
    xs = sorted(c)
    ys = [c[y] for y in xs]
    plt.figure(figsize=(11, 5.5))
    plt.bar(xs, ys, color="#4C72B0")
    plt.title("Computational Social Science: number of papers per year", fontsize=14)
    plt.xlabel("Year")
    plt.ylabel("Papers")
    plt.grid(axis="y", alpha=0.3)
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


def fig_network(H, communities, node2comm, comm_titles, path):
    """图3:网络图,每个较大学派在质心处标主题词。"""
    deg = dict(H.degree())
    pos = nx.spring_layout(H, seed=SEED, k=0.15, iterations=50)
    cmap = plt.cm.tab20

    node_colors = [cmap(node2comm[a] % 20) for a in H.nodes()]
    node_sizes = [10 + 4 * deg.get(a, 0) for a in H.nodes()]

    plt.figure(figsize=(16, 16))
    nx.draw_networkx_edges(H, pos, alpha=0.06, width=0.4)
    nx.draw_networkx_nodes(H, pos, node_color=node_colors, node_size=node_sizes,
                           linewidths=0.2, edgecolors="white")

    # 给人数 >= 20 的学派,在其质心标上"主题词"(前 2 个),白底框便于阅读
    for idx, comm in enumerate(communities):
        if len(comm) < 20:
            continue
        xs = [pos[a][0] for a in comm]
        ys = [pos[a][1] for a in comm]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        label = ", ".join(top_words(comm_titles[idx], k=2))
        if not label:
            continue
        plt.text(cx, cy, label, fontsize=12, fontweight="bold",
                 ha="center", va="center",
                 bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.85))

    plt.title("Computational Social Science — Co-authorship Network (giant component)\n"
              f"{H.number_of_nodes()} authors; color = Louvain community, labels = community topic words",
              fontsize=15)
    plt.axis("off")
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

    cmap = plt.cm.tab20
    colors = [cmap(idx % 20) for idx, _ in big]

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

    # 巨核 + Louvain
    giant_nodes = max(nx.connected_components(G), key=len)
    H = G.subgraph(giant_nodes).copy()
    communities = sorted(nx_comm.louvain_communities(H, weight="weight", seed=SEED),
                         key=len, reverse=True)
    print(f"巨核 {H.number_of_nodes()} 人,Louvain 找到 {len(communities)} 个学派\n")

    node2comm = {aid: idx for idx, comm in enumerate(communities) for aid in comm}

    # 每篇论文按"多数作者所属学派"归类,聚合标题
    comm_titles = {idx: [] for idx in range(len(communities))}
    for w in works:
        votes = Counter()
        for a in w.get("authorships", []):
            aid = (a.get("author") or {}).get("id")
            if aid in node2comm:
                votes[node2comm[aid]] += 1
        if votes:
            comm_titles[votes.most_common(1)[0][0]].append(w.get("display_name") or "")

    # 控制台速览(人数 >= 8 的学派)
    deg = dict(H.degree())
    for idx, comm in enumerate(communities):
        if len(comm) < 8:
            continue
        core = sorted(comm, key=lambda a: deg.get(a, 0), reverse=True)[:4]
        core_names = ", ".join(H.nodes[a].get("name", a) for a in core)
        print(f"学派#{idx}({len(comm)}人) 主题[{', '.join(top_words(comm_titles[idx], 5))}] 核心:{core_names}")

    # 四张图
    print("\n正在生成 4 张图...")
    fig_papers_per_year(works, os.path.join(FIG_DIR, "papers_per_year.png"))
    fig_top_authors(G, os.path.join(FIG_DIR, "top_authors.png"))
    fig_network(H, communities, node2comm, comm_titles, os.path.join(FIG_DIR, "coauthor_network.png"))
    fig_communities_overview(communities, comm_titles, os.path.join(FIG_DIR, "communities_overview.png"))
    print(f"完成,图已存到 {FIG_DIR}/(papers_per_year / top_authors / coauthor_network / communities_overview).png")


if __name__ == "__main__":
    main()
