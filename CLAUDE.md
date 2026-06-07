# 项目:计算社会科学领域的合作网络分析(opencode-css)

## 这个项目在做什么
用 OpenAlex 的公开学术数据,把「计算社会科学(computational social science)」这个领域**本身**当成研究对象,分析它的作者合作网络:
- 核心作者是谁;
- 分成哪几个学派(网络社群);
- 这些年怎么发展演化。

## 当前首要目标(2026-06 更新)
**把项目做成、并发布到 GitHub。** 学习是次要、且由用户按自己节奏慢慢来。
因此协作时:
- **优先把功能跑通、把仓库整理干净**,不必为每个小步骤停下来等确认;
- 但要保证 **代码注释充分(中文)+ README 讲清楚**,让仓库本身成为用户日后自学的材料;
- **关键决策(尤其影响结果或对外发布的)仍要先问用户**;`gh repo create` / push 这类对外动作,执行前必须确认。

## 用户画像
- 计算机大一,编程基本从零开始。
- 全程用**中文**解释,默认对方不懂术语,先讲概念再上代码。

## 技术栈与环境
- 系统:Windows 11,**Windows PowerShell 5.1**。
  - 注意:PowerShell 5.1 的 `>` 默认写 UTF-16;要存 UTF-8 文本用 `... | Out-File -Encoding utf8 文件名`。
- Python:3.9.2,虚拟环境在 `.venv\`。
  - 激活:`.\.venv\Scripts\Activate.ps1`(成功后提示符前出现绿色 `(.venv)`)。
  - Claude 用工具跑脚本时,直接用 `.\.venv\Scripts\python.exe` 调用 venv 里的解释器。
- 已装核心库:pandas、networkx、matplotlib、requests(见 `requirements.txt`)。
- 数据源:OpenAlex(https://docs.openalex.org)。访问时加邮箱进 polite pool、控制频率、做重试与断点续传。

## 路线图(主线 1–4,5–6 为进阶)
1. 搭环境 ✅(已完成)
2. 从 OpenAlex 抓「计算社会科学」相关论文元数据,存本地
3. 建作者合著网络 + 基础网络指标
4. 社群发现(找学派)+ 可视化导出图片
5. (进阶)对摘要做主题模型 / embedding,看前沿迁移(可用 DGX + Qwen)
6. (进阶)切某年网络,用 R 的 RSiena/ergm 跑 ERGM 做统计推断

## 约定
- 代码注释、变量命名尽量清晰;面向初学者可读。
- 维护 `requirements.txt`(用 `pip freeze | Out-File -Encoding utf8 requirements.txt`)。
- 大体积原始数据放 `data/`(已被 .gitignore 忽略),靠脚本可重建;图片成果保留以便 README 展示。
