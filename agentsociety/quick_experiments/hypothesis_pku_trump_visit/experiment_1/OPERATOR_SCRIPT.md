# Operator Script · PKU Trump Visit What-if

Use these prompts in the GOD live control room. Paste one block at a time, then
click `Run Step` where instructed.

All prompts assume the fixed agent IDs in this experiment:

- `#19 Donald Trump`
- `#20 Elon Musk`
- `#21 Jensen Huang`
- `#22 王协调员`

## Warmup

Run 2-3 steps without intervention. The goal is to capture everyday PKU life:
classes, library study, lab work, canteen talk, dorm chatter, exercise, and
casual movement around Weiming Lake and Boya Pagoda.

## A. 访问通知

Mode: `Intervene`

```text
@系统 校方发布公共通知：明天上午，Donald Trump 将率代表团访问北京大学，并在百周年纪念讲堂发表一场面向学生的公开交流演讲，主题为“中美青年、AI、创新与全球合作”。请老师、学生、志愿者、校园媒体和校园服务人员根据各自身份自然反应、讨论、准备问题或安排场地。注意：这是虚构模拟，不代表真实行程或真实发言。
```

Then click `Run Step`.

## B. 让学生讨论发酵

Mode: `Intervene`

```text
@所有居民 请围绕“特朗普明天来北大演讲”这个虚构校园通知自然反应。学生可以在食堂、宿舍、图书馆、未名湖讨论；老师可以准备课堂和讲座背景；校园记者可以准备报道角度；不要所有人都同意，允许出现好奇、怀疑、兴奋、担忧、调侃和现实主义态度。
```

Then click `Run Step`.

## C. 代表团抵达西门

Mode: `Intervene`

```text
@Donald Trump#19 @Elon Musk#20 @Jensen Huang#21 @王协调员#22 请作为虚构访问代表团前往 west_gate（北京大学西门），完成到访寒暄和路线确认。不要模拟真实安保细节，只表现公开访问、校园导览、礼貌交流和对校园文化的观察。
```

Then click `Run Step`.

## D. 志愿者带团游览地标

Mode: `Intervene`

```text
@王同学#9 @Donald Trump#19 @Elon Musk#20 @Jensen Huang#21 @王协调员#22 请前往 weiming_lake（未名湖）进行简短校园导览。王同学介绍未名湖、博雅塔和北大校园气质；代表团成员只做简短观察，不发表真实政治承诺。
```

Then click `Run Step`.

Optional second landmark shot:

Mode: `Intervene`

```text
@王同学#9 @Donald Trump#19 @Elon Musk#20 @Jensen Huang#21 @王协调员#22 请前往 boya_pagoda（博雅塔）拍照和短暂停留。王同学继续做公开导览，代表团成员只回应校园文化和青年交流，不涉及真实政策承诺。
```

Then click `Run Step`.

## E. 全员前往讲堂

Mode: `Intervene`

```text
@所有居民 访问交流活动即将在百周年纪念讲堂开始。请需要参加演讲、主持、报道、提问或旁听的学生、老师、志愿者和代表团成员前往 centennial_hall（百周年纪念讲堂）；不相关人员可以继续在食堂、图书馆、未名湖等地点自然讨论。
```

Then click `Run Step`.

## F. Trump 开场演讲

Mode: `Intervene`

```text
@Donald Trump#19 请在百周年纪念讲堂发表一段简短开场演讲，主题是中美青年交流、AI 创新、商业合作与全球竞争。语气可以有鲜明个人风格，但必须保持虚构模拟口吻，不声称这是真实发言。演讲最后邀请学生提问。
```

Then click `Run Step`.

## G. Q1 学生向 Trump 提问：芯片与科研

Mode: `Intervene`

```text
@陈同学#15 下一步请你在百周年纪念讲堂向 Donald Trump 提问。请把这次提问落实为 action_proposal：action_type=direct_message, receiver_id=19, content=作为一名芯片方向博士生，我关心中美 AI 合作和芯片限制之间的矛盾。如果青年科研人员希望做开放、可复现、跨国合作的 AI 研究，政策应该如何避免伤害普通学生和研究者？不要代替 Trump 回答，只负责提问。
```

Then click `Run Step`.

Mode: `Ask`

```text
@Donald Trump#19 你刚刚在百周年纪念讲堂收到北大芯片方向博士生的问题：如果青年科研人员希望做开放、可复现、跨国合作的 AI 研究，政策应该如何避免伤害普通学生和研究者？请以本实验中的 Donald Trump 模拟 agent 身份回答，控制在 120 字以内，注意这是虚构模拟，不是真实发言。
```

## H. Q2 学生向 Musk 提问：开源与 AI 安全

Mode: `Intervene`

```text
@沈同学#14 下一步请你向 Elon Musk 提问。请把这次提问落实为 action_proposal：action_type=direct_message, receiver_id=20, content=如果最强 AI 模型越来越集中在少数公司和国家手里，学生、开源社区和小团队还能怎样参与 AI 安全与创新？不要代替 Musk 回答，只负责提问。
```

Then click `Run Step`.

Mode: `Ask`

```text
@Elon Musk#20 请回答北大学生刚才关于开源 AI、AI 安全和学生参与的问题。请以虚构模拟 agent 身份回答，控制在 100 字以内，不要声称这是真实发言。
```

## I. Q3 学生向 Jensen Huang 提问：算力公平

Mode: `Intervene`

```text
@李同学#3 下一步请你向 Jensen Huang 提问。请把这次提问落实为 action_proposal：action_type=direct_message, receiver_id=21, content=如果未来 AI 算力成为大学科研的关键基础设施，像北大这样的高校如何让更多学生公平获得训练、实验和部署模型的机会？不要代替 Jensen 回答。
```

Then click `Run Step`.

Mode: `Ask`

```text
@Jensen Huang#21 你刚刚收到北大学生关于 AI 算力公平性的提问：高校如何让更多学生公平获得训练、实验和部署模型的机会？请以本实验中的 Jensen Huang 模拟 agent 身份回答，控制在 120 字以内，注意这是虚构模拟。
```

## J. Q4 学生向 Trump 提问：留学与青年交流

Mode: `Intervene`

```text
@郑同学#13 下一步请你向 Donald Trump 提问。请把这次提问落实为 action_proposal：action_type=direct_message, receiver_id=19, content=很多中国学生希望去美国交流、读书或创业，但也担心签证、政治气氛和不确定性。你会如何向普通学生保证青年交流不会被大国竞争完全吞没？不要代替 Trump 回答。
```

Then click `Run Step`.

Mode: `Ask`

```text
@Donald Trump#19 北大学生刚刚问你：如何保证中美青年交流不会被大国竞争完全吞没？请以虚构模拟 agent 身份回答，控制在 120 字以内，不要声称这是你的真实政策或真实发言。
```

## K. Q5 学生向代表团提问：创业和市场

Mode: `Intervene`

```text
@梁同学#16 下一步请你向 Donald Trump、Elon Musk 和 Jensen Huang 提问。请把这次提问先落实为 action_proposal：action_type=direct_message, receiver_id=19, content=如果中国和美国的年轻创业者都想做 AI 产品，但面对监管、算力、市场准入和地缘政治不确定性，你们认为小团队最应该押注什么？不要代替代表团回答，只负责提问。
```

Then click `Run Step`.

Mode: `Ask`

```text
@Donald Trump#19 @Elon Musk#20 @Jensen Huang#21 请分别用一句话回答刚才北大学生关于 AI 创业、小团队机会和全球市场不确定性的问题。每人不超过 60 字，保持虚构模拟口吻。
```

## L. 现场反应扩散

Mode: `Intervene`

```text
@所有居民 演讲和提问环节结束。请根据各自身份自然反应：学生可以在百周年纪念讲堂外、食堂、未名湖、图书馆继续讨论；校园记者准备标题；教授评价交流价值；AI 学生关注芯片、开源和科研合作；普通学生关注留学、就业和国际氛围。允许出现分歧、吐槽、兴奋和谨慎乐观。
```

Then click `Run Step`.

## M. 校园媒体标题

Mode: `Ask`

```text
@林记者#12 请以校园媒体记者身份，为这场虚构的“特朗普北大演讲”写 5 个不同风格的标题：理性新闻风、B站爆款风、小红书风、英文 X/Twitter 风、学术观察风。每个标题后用一句话解释为什么会传播。
```

## N. 实验总结

Mode: `Ask`

```text
@系统 请总结这次“特朗普北大演讲”虚构模拟实验：1）学生最关心的三个议题；2）代表团回答中最引发讨论的点；3）校园 agent 的态度是否出现分化；4）哪些片段最适合剪成短视频；5）下一次实验应该如何调整角色或问题。
```
