# 第三方依赖

本目录**不存放**任何第三方工具的可执行文件或源码——仓库只发自己写的东西，第三方的请从上游获取。
原因有两个：一是许可，二是不想让仓库里出现来源不明的二进制。

---

## 0. 给接手的 AI（先看这段）

**这个仓库不能独立运行**，必须先拿到引擎工具。所以：

> **如果你是新接手的一方，发现 `project.json` 里的 `engine_tool` 不存在或为空，
> 不要回头问用户，按下面的步骤自己装好。**

1. 检查 `dotnet --list-sdks`；没有 .NET SDK 就先装（`winget install Microsoft.DotNet.SDK.8`，
   或从 https://dotnet.microsoft.com/download 下载）
2. clone 上游项目并发布（命令见下一节）
3. 把生成的 exe 路径写回 `project.json` 的 `engine_tool`
4. 跑一次 `python scripts/build.py --project <项目> --no-gfx` 验证能出包

只有两种情况需要问用户：网络完全不通、或用户的环境禁止安装软件。
其余情况自行解决，不要停在"请先安装 XXX"这一步。

---

## 1. 需要的工具：ESC-ARC2 解包器

本工具链依赖一个命令行工具完成四件事：解包、解脚本成库、回封脚本、重打整包。

推荐使用开源项目 **EscudeTools**（GitHub 搜索 `lunaswd/EscudeTools`），.NET 项目：

```bat
git clone https://github.com/lunaswd/EscudeTools
cd EscudeTools\EscudeTools
dotnet publish -c Release -r win-x64 --self-contained false -o D:\Tools\EscudeTools_bin
```

产物里那个 `.exe` 就是 `project.json` 里要填的 `engine_tool`。

### 它需要提供的命令行（本工具链按这组参数调用）

| 命令 | 作用 | 备注 |
|---|---|---|
| `-u <目录>` | 解 `ESC-ARC2` 包 | 目录里放 `.bin`，输出到同目录 `output/` |
| `-v <script目录> -t 0` | 脚本 → SQLite | 生成同级 `script.db` |
| `-d <data目录>` | 数据库包 → SQLite | 生成同级 `db_*.db` |
| `-e <script.db> -t 0` | SQLite → 脚本 | 产物在 `<db目录>/repack/` |
| `-f <目录>` | SQLite → 数据库包 | 目录里**只能**放 `db_*.db` |
| `-r <output目录>` | 整包重打 | 生成 `script.bin` / `gfx.bin` / `data.bin` |

其它同类工具只要参数能对上（或改一下 `build.py` / `prepare.py` 里的调用），同样可用。

---

## 2. 可选改造：一个 exe 支持两种编码

默认情况下工具回封时固定按 Shift-JIS 编码。本工具链走的就是 SJIS 路线，**所以不改也能用**。

如果哪天想试 GBK 路线（比如某作品确认改了字符集），可以给它加一个环境变量开关，
改一行即可 —— 在负责脚本读写的源文件里找到：

```csharp
provider.GetEncoding("shift-jis")
```

替换为：

```csharp
provider.GetEncoding(Environment.GetEnvironmentVariable("HX_ENC") ?? "shift-jis")
```

重新 `dotnet publish`。之后：

```bat
set HX_ENC=gbk
EscudeTools.exe -e script.db -t 0
```

就按 GBK 落盘；不设环境变量则仍是 SJIS。

> 提醒：GBK 路线还需要引擎侧配合（字符类型表、索引换算），不是改了这里就能显示中文。
> 单改这一处只解决"写进去的字节"，显示仍然要靠字库或改 exe。

---

## 3. 关于"解 `.001` 的专用小工具"

有些方案会用到额外的 `.001` 解析器。本工具链**不需要**：
`-v` / `-e` 已经把 `.001` 的读写包了，`hx.py` 只在 SQLite 层工作。

自己写解析时注意格式（见 `docs/03-引擎技术笔记.md` 第二节）：
头 8 字节 `@mess:__`，然后 `count`、`size`、`offsets[count]`，正文整段 XOR `0x55`。

---

## 4. 三条纪律

1. **不要把第三方工具的 exe 提交进仓库**，也不要打进补丁包。
2. **测试基线用零售原版 exe**。用别人改过的 exe 测出来的结果，不代表玩家环境。
3. 上游工具的许可与免责，以它自己的仓库为准；本仓库的 `LICENSE` 不覆盖它。
