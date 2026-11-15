# 游戏 · 每游戏一个自包含工作区

汉化工作的**全部数据与产物**都在各自的游戏文件夹里，工具不掺游戏内容。

## 开新游戏（三步）

1. 把 `新游戏模板` 整个复制一份，重命名为游戏名（如 `千艶万匣`）
2. 把游戏的 `*.bin` 原包放进 `0_原版\`（只读，永远不动它）
3. 复制根目录的 `project.example.json` 为本游戏夹的 `project.json`，
   填好 `dirs` 八段（默认名即可）与 `engine_tool`（解包器 exe 路径，
   获取见 `vendor\README.md`）

之后所有脚本都通过 `project.json` 寻址：在游戏文件夹里运行
`python ..\..\scripts\xxx.py`（或 `scripts\prepare.py` 一键补齐骨架）。
`config.json`（API key）也放在游戏文件夹里，绝不外传。
