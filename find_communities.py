"""
find_communities.py —— 在合作网络里找"学派"(社群),并画成彩色网络图。

做了什么:
1. 读入 data/coauthor_network.graphml(阶段三建好的网络)。
2. 取出最大连通块"巨核"(真正有结构的核心圈)。
3. 用 Louvain 社群发现算法把巨核划成若干社群(=可能的学派/师承群体)。
4. 对每个社群:列出最核心的几位作者,并从他们论文标题里提取高频词作为"研究主题"的代理。
5. 画出巨核网络:不同社群不同颜色,核心作者标名字,导出到 figures/coauthor_network.png。

为什么用 Louvain:内置于 networkx、无需额外安装,是最经典常用的社群发现算法。
"""

import os
import re
import sys
from collections import Counter

import matplotlib
matplotlib.use("Agg")            # 不弹窗,直接把图存成文件(更适合脚本/服务器)
import matplotlib.pyplot as plt
import networkx as nx
from networkx.algorithms import community as nx_comm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

GRAPH_PATH = os.path.join("data", "coauthor_network.graphml")
WORKS_PATH = os.path.join("data", "works.jsonl")
FIG_PATH = os.path.join("figures", "coauthor_network.png")
SEED = 42                        # 固定随机种子,保证每次结果一致

# 这些词几乎每个标题都有(就是我们的检索词)或太通用,做主题词时排除掉
SEARCH_WORDS = {"computational", "computation", "social", "science", "sciences"}
STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with", "from",
    "by", "as", "at", "via", "using", "use", "based", "study", "studies", "analysis",
    "approach", "approaches", "new", "toward", "towards", "case", "research", "method",
    "methods", "model", "models", "data", "an", "into", "between", "through", "across",
    "is", "are", "be", "this", "that", "their", "its", "we", "our", "how", "what",
    "can", "but", "der", "about", "during", "following", "not", "all", "more",
    "has", "have", "had", "will", "may", "also", "than", "when", "where", "which",
    "who", "it", "no", "do", "does",
}


def load_author_titles(path):
    """读 works.jsonl,返回 {作者id: [该作者参与的论文标题, ...]}。"""
    author_titles = {}
    import json
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            w = json.loads(line)
            title = w.get("display_name") or ""
            for a in w.get("authorships", []):
                aid = (a.get("author") or {}).get("id")
                if aid:
                    author_titles.setdefault(aid, []).append(title)
    return author_titles


def top_words(titles, k=8):
    """从一堆标题里数出最高频的 k 个词(去掉检索词和停用词)。"""
    counter = Counter()
    for t in titles:
        for word in re.findall(r"[a-zA-Z]+", t.lower()):
            if len(word) < 3 or word in STOPWORDS or word in SEARCH_WORDS:
                continue
            counter[word] += 1
    return [w for w, _ in counter.most_common(k)]


def main():
    G = nx.read_graphml(GRAPH_PATH)
    print(f"读入网络:{G.number_of_nodes()} 个节点、{G.number_of_edges()} 条边")

    # 取巨核
    giant_nodes = max(nx.connected_components(G), key=len)
    H = G.subgraph(giant_nodes).copy()
    print(f"巨核:{H.number_of_nodes()} 人、{H.number_of_edges()} 条合作边\n")

    # Louvain 社群发现(用边权重,固定种子)
    communities = nx_comm.louvain_communities(H, weight="weight", seed=SEED)
    communities = sorted(communities, key=len, reverse=True)
    print(f"Louvain 找到 {len(communities)} 个社群(学派候选),规模前几名:")
    print("  " + ", ".join(str(len(c)) for c in communities[:12]) + " ...\n")

    # 作者 -> 社群编号
    node2comm = {}
    for idx, comm in enumerate(communities):
        for aid in comm:
            node2comm[aid] = idx

    # 把每篇论文按"多数作者所属社群"归到某个社群,聚合标题
    import json
    comm_titles = {idx: [] for idx in range(len(communities))}
    with open(WORKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            w = json.loads(line)
            votes = Counter()
            for a in w.get("authorships", []):
                aid = (a.get("author") or {}).get("id")
                if aid in node2comm:
                    votes[node2comm[aid]] += 1
            if votes:
                comm_titles[votes.most_common(1)[0][0]].append(w.get("display_name") or "")

    # 每个社群:核心作者(按巨核内的度)+ 主题词
    print("=" * 60)
    print("各社群画像(只看人数 >= 8 的较大社群)")
    print("=" * 60)
    deg = dict(H.degree())
    for idx, comm in enumerate(communities):
        if len(comm) < 8:
            continue
        core = sorted(comm, key=lambda a: deg.get(a, 0), reverse=True)[:5]
        core_names = [H.nodes[a].get("name", a) for a in core]
        words = top_words(comm_titles[idx])
        print(f"\n社群 #{idx}（{len(comm)} 人）")
        print(f"  核心作者: {', '.join(core_names)}")
        print(f"  主题高频词: {', '.join(words)}")

    # ---------- 可视化 ----------
    os.makedirs("figures", exist_ok=True)
    print("\n正在布局并绘图(节点较多,稍等几秒)...")
    pos = nx.spring_layout(H, seed=SEED, k=0.15, iterations=50)

    cmap = plt.cm.tab20
    node_colors = [cmap(node2comm[a] % 20) for a in H.nodes()]
    node_sizes = [10 + 4 * deg.get(a, 0) for a in H.nodes()]

    plt.figure(figsize=(16, 16))
    nx.draw_networkx_edges(H, pos, alpha=0.08, width=0.4)
    nx.draw_networkx_nodes(H, pos, node_color=node_colors, node_size=node_sizes,
                           linewidths=0.2, edgecolors="white")

    # 只给度最高的 18 位核心作者标名字,避免糊成一团
    top_authors = sorted(H.nodes(), key=lambda a: deg.get(a, 0), reverse=True)[:18]
    labels = {a: H.nodes[a].get("name", a) for a in top_authors}
    nx.draw_networkx_labels(H, pos, labels=labels, font_size=9,
                            font_color="black", font_weight="bold")

    plt.title("Computational Social Science — Co-authorship Network (giant component)\n"
              f"{H.number_of_nodes()} authors, colored by Louvain community",
              fontsize=15)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(FIG_PATH, dpi=200, bbox_inches="tight")
    print(f"图已保存到 {FIG_PATH}")


if __name__ == "__main__":
    main()
