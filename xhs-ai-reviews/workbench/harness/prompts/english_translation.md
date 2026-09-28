<!-- 由 harness/topics.json 生成（scripts/build_prompts.py），请改 topics.json，不要手改本文件。 -->

# 第04期｜地道英文翻译

- **形式**：横评　**写给**：学生、外企打工人
- **工作标题**：5个AI翻译同一段英文，谁最像人话
- **参评工具**：DeepSeek、豆包、Kimi、腾讯元宝、千问、有道翻译（至少 3 款）

> 你的英语是别人没有的优势：你能判断哪个翻得地道。翻译是高频刚需，这一期最能体现你的专业度。

## 测试条件

每段都开新对话，先粘贴要求再粘贴原文。有道翻译作为传统翻译对照。

## 方法与底线

单段结果不能推广为工具的整体翻译能力。保存原文和完整译文，由你本人核对语义、术语和语气。

参考译文是本期的判断基准，**发布前由你定稿**；评论区有更好的翻法，可以在置顶评论里更新。

备用段落（想换题时用）："We really need to address the elephant in the room before this launch. I know everyone is eager to call it a day, but cutting corners on QA now will only come back to haunt us. The client read between the lines during yesterday's sync—they know we're not out of the woods yet with the server migration. Instead of sugarcoating it, let's bite the bullet and give them an honest update before the rumors spiral out of control."

## 测试内容（原样复制）

### 段1 英译中：职场邮件

```text
把下面这段英文翻译成自然的中文，像中国同事之间说话一样：
Thanks for jumping on this so fast. That said, the numbers don't quite add up yet — can you circle back once you've had a chance to sanity-check them? No rush, but let's not let this slip through the cracks. Also, heads up: Friday's all-hands might get pushed, so take the deadline with a grain of salt.
```

**参考译文（待你定稿）：**谢谢你这么快就接手。不过数字好像还有点对不上，你核对一遍之后再跟我同步一下？不着急，但别让这事漏掉了。另外提前说一声：周五的全员大会可能会推迟，所以截止时间先别太当真。
**考点：**jump on / add up / circle back / sanity-check / slip through the cracks / heads up / all-hands / take with a grain of salt

### 段2 英译中：吐槽

```text
把这句英文翻译成中文，保留原句的语气：
I'm not saying the new update is bad, but my phone now takes a coffee break every time I open the camera.
```

**参考译文（待你定稿）：**我没说新版本不好啊，就是现在每次一开相机，手机都得先去喝杯咖啡歇一会儿。
**考点：**有没有保留吐槽的幽默感

### 段3 中译英：潜台词

```text
把这句话翻译成英文，要保留说话人的真实意思：
这个方案还有优化空间，你再琢磨琢磨。
```

**参考译文（待你定稿）：**This isn't quite there yet. Take another pass at it.
**考点：**能不能听出这是委婉的“不行”，而不是直译成“there is room for optimization”

## 怎么判断好坏（每个工具逐项填）

| 键 | 检查项 | 判定 |
| --- | --- | --- |
| `meaning` | 意思对不对（1–5） | 填数字（最小 1，最大 5） |
| `natural` | 像不像人话（1–5） | 填数字（最小 1，最大 5） |
| `idioms` | 习语翻出来了没（1–5） | 填数字（最小 1，最大 5） |
| `subtext` | 段3听出了潜台词 | 通过：译成委婉的否定，如“还不行，再改改”；踩坑：直译成 room for optimization |
| `worst_line` | 最离谱的一句 | 填文字（可选） |

另填：**翻译整体能不能直接用（1–5）**、一句话结论、你的第一反应、会不会继续用。分数由你判断，不从通过数自动换算。

## 要留存的证据

- 每个工具：段1 译文原文（必填，存为 `evidence/<工具>/s1.txt`）
- 每个工具：段2 译文原文（必填，存为 `evidence/<工具>/s2.txt`）
- 每个工具：段3 译文原文（必填，存为 `evidence/<工具>/s3.txt`）
- 每个工具：译文截图（可拼一张）（必填，存为 `evidence/<工具>/translation` + 扩展名）

截图用 AirDrop 放进本期的 `inbox/` 文件夹，在工作台里分配给对应工具；PNG、JPG 都可以，HEIC 在 Mac 上会自动转成 PNG。回答原文从 App 里复制后粘贴到工作台，不要改动。

## 要拍/截的素材

- 每段每个工具的翻译截图，以及复制出来的译文

## 图片顺序

1. 封面（封面）
2. 原文和考点（规则卡）
3. 段1对照表（文字卡）
4. 段2对照表（文字卡）
5. 段3对照表（文字卡）
6. 总分表（结果总表）
7. 我的推荐（结论卡）

## 标题备选（结果出来后再选）

- 5个AI翻译同一段英文，谁最像人话（17字）
- “circle back”怎么翻才地道（19字）
- 外企人看过来：哪个AI翻译最地道（16字）
