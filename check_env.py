# check_env.py —— 环境自检脚本
# 作用:把这个项目要用到的库逐个 import 一遍,并打印它们的版本号。
# 判断标准:能从头跑到尾、不报错,就说明环境装好了。

import sys          # sys:Python 自带,用来读取 Python 自身的信息(比如版本)
import pandas       # 数据处理
import networkx     # 网络分析
import matplotlib   # 画图
import requests     # 抓数据(网络请求)

# 下面用 f"..." 这种「格式化字符串」:大括号 {} 里能直接塞变量,
# Python 会自动把它替换成变量里的实际内容。
print(f"Python     版本: {sys.version.split()[0]}")
print(f"pandas     版本: {pandas.__version__}")
print(f"networkx   版本: {networkx.__version__}")
print(f"matplotlib 版本: {matplotlib.__version__}")
print(f"requests   版本: {requests.__version__}")

print()  # 打印一个空行,纯粹为了排版好看
print("环境自检通过:四个库都能正常导入,可以进入下一阶段。")
