"""
topic_model.py —— 阶段五:对论文摘要做主题模型,看「研究前沿怎么随时间迁移」。

流程:
1. 把 OpenAlex 的 abstract_inverted_index(倒排索引)还原成摘要文本。
2. 标题 + 摘要拼一起,做 TF-IDF 向量化(含双词组,去停用词)。
3. 用 NMF 主题模型挖出 N_TOPICS 个主题,打印每个主题的关键词。
4. 给每篇论文判定一个主导主题,统计「各主题逐年占比」,画成堆叠面积图——
   一眼看出哪些主题在升、哪些在退(即研究前沿的迁移)。

产出:figures/topics_over_time.png、figures/topics_size.png
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKS_PATH = os.path.join("data", "works.jsonl")
FIG_DIR = "figures"
N_TOPICS = 10
START_YEAR = 2010          # 早年论文太少,主题占比噪声大,从这一年起看趋势
SEED = 42

# 检索词本身几乎每篇都有,放进停用词,免得每个主题都被它们占据
EXTRA_STOP = {"computational", "computation", "social", "science", "sciences",
              "using", "used", "use", "based", "paper", "study", "research",
              "approach", "data", "results", "method", "methods", "analysis",
              # 会议/出版样板词 & 缩写,避免形成"样板"主题
              "conference", "proceedings", "international", "workshop", "society",
              "americas", "chapter", "css", "springer", "abstract", "introduction",
              "article", "journal", "university", "press", "vol", "doi"}
STOP_WORDS = list(ENGLISH_STOP_WORDS.union(EXTRA_STOP))


def reconstruct_abstract(inv_index):
    """把 {词: [位置,...]} 的倒排索引拼回成一段文本。"""
    if not inv_index:
        return ""
    positions = {}
    for word, idxs in inv_index.items():
        for p in idxs:
            positions[p] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in range(max(positions) + 1) if i in positions)


# 法语/德语常见虚词:用来识别并剔除非英文的标题/摘要
_FOREIGN_MARKERS = {
    "der", "und", "die", "von", "das", "mit", "fur", "des", "den", "im", "zu",
    "auf", "ein", "eine", "als", "aus",                       # 德语
    "la", "le", "les", "une", "pour", "dans", "sur", "et", "en", "du", "aux",
    "avec", "presses", "bibliogr", "dir",                     # 法语
}


def looks_foreign(text):
    """粗略判断是否非英文:出现 2 个及以上法/德语虚词就当作非英文。"""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return sum(1 for t in tokens if t in _FOREIGN_MARKERS) >= 2


def load_docs(path):
    """返回 (文本列表, 年份列表, 有摘要的篇数)。"""
    docs, years, with_abs = [], [], 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            w = json.loads(line)
            abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
            if abstract and looks_foreign(abstract):
                abstract = ""        # 非英文摘要丢弃
            title = w.get("display_name") or ""
            if looks_foreign(title):
                continue             # 标题就是非英文(法/德语)的论文,整篇跳过
            text = (title + ". " + abstract).strip()
            if len(text) < 20:
                continue
            docs.append(text)
            years.append(w.get("publication_year"))
            if abstract:
                with_abs += 1
    return docs, years, with_abs


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    docs, years, with_abs = load_docs(WORKS_PATH)
    print(f"可用文本 {len(docs)} 篇,其中有摘要 {with_abs} 篇")

    # TF-IDF:单词 + 双词组;去掉过于稀有/过于普遍的词
    vectorizer = TfidfVectorizer(stop_words=STOP_WORDS, ngram_range=(1, 2),
                                 min_df=5, max_df=0.5,
                                 token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b")
    X = vectorizer.fit_transform(docs)
    vocab = vectorizer.get_feature_names_out()
    print(f"词表大小 {len(vocab)};开始训练 NMF({N_TOPICS} 个主题)...")

    nmf = NMF(n_components=N_TOPICS, random_state=SEED, init="nndsvda", max_iter=500)
    W = nmf.fit_transform(X)        # 文档 × 主题
    Hm = nmf.components_            # 主题 × 词

    # 每个主题的关键词 + 简短标签
    topic_labels = []
    print("\n各主题关键词:")
    for t in range(N_TOPICS):
        top_idx = Hm[t].argsort()[::-1][:10]
        words = [vocab[i] for i in top_idx]
        topic_labels.append(", ".join(words[:3]))
        print(f"  主题{t}: {', '.join(words)}")

    # 每篇论文的主导主题
    dominant = W.argmax(axis=1)

    # ---- 图1:各主题整体规模 ----
    sizes = Counter(dominant.tolist())
    order = [t for t, _ in sizes.most_common()]
    plt.figure(figsize=(11, 6))
    plt.barh([topic_labels[t] for t in order][::-1],
             [sizes[t] for t in order][::-1],
             color=[plt.cm.tab10(t % 10) for t in order][::-1])
    plt.title(f"Abstract topics (NMF, {N_TOPICS} topics) by number of papers", fontsize=13)
    plt.xlabel("Papers")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "topics_size.png"), dpi=180)
    plt.close()

    # ---- 图2:各主题逐年占比(堆叠面积)----
    cur_year = datetime.now().year
    yrs = sorted({y for y in years if y and START_YEAR <= y < cur_year})
    # 每年各主题的占比
    shares = np.zeros((N_TOPICS, len(yrs)))
    for col, y in enumerate(yrs):
        idx = [i for i, yy in enumerate(years) if yy == y]
        if not idx:
            continue
        counts = Counter(dominant[i] for i in idx)
        total = len(idx)
        for t in range(N_TOPICS):
            shares[t, col] = counts.get(t, 0) / total

    plt.figure(figsize=(13, 7))
    plt.stackplot(yrs, shares,
                  labels=[f"{topic_labels[t]}" for t in range(N_TOPICS)],
                  colors=[plt.cm.tab10(t % 10) for t in range(N_TOPICS)], alpha=0.85)
    plt.title("Research frontier over time — share of each abstract topic by year", fontsize=14)
    plt.xlabel("Year")
    plt.ylabel("Share of papers")
    plt.xlim(min(yrs), max(yrs))
    plt.ylim(0, 1)
    plt.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "topics_over_time.png"), dpi=180, bbox_inches="tight")
    plt.close()

    print(f"\n完成,图已存到 {FIG_DIR}/topics_size.png 和 topics_over_time.png")


if __name__ == "__main__":
    main()
