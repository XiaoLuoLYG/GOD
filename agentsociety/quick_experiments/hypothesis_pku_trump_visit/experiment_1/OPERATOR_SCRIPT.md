# Operator Script · PKU Trump Visit

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
@系统 校方发布公共通知：明天上午，Donald Trump 将率代表团访问北京大学，并在百周年纪念讲堂发表一场面向学生的公开交流演讲，主题为“中美青年、AI、创新与全球合作”。请老师、学生、志愿者、校园媒体和校园服务人员根据各自身份自然反应、讨论、准备问题或安排场地。注意：角色台词只服务场内叙事，不作为现实世界正式行程或正式发言。
```

Then click `Run Step`.

## B. 让学生讨论发酵

Mode: `Intervene`

```text
@所有居民 请围绕“特朗普明天来北大演讲”这个校内通知自然反应。学生可以在食堂、宿舍、图书馆、未名湖讨论；老师可以准备课堂和讲座背景；校园记者可以准备报道角度；不要所有人都同意，允许出现好奇、怀疑、兴奋、担忧、调侃和现实主义态度。
```

Then click `Run Step`.

## C. 代表团抵达西门

Mode: `Intervene`

```text
@Donald Trump#19 @Elon Musk#20 @Jensen Huang#21 @王协调员#22 请作为访问代表团前往 west_gate（北京大学西门），完成到访寒暄和路线确认。不要描述真实安保细节，只表现公开访问、校园导览、礼貌交流和对校园文化的观察。
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
@Donald Trump#19 请在百周年纪念讲堂发表一段简短开场演讲，主题是中美青年交流、AI 创新、商业合作与全球竞争。语气可以有鲜明个人风格，但不要作现实世界正式政策承诺。演讲最后邀请学生提问。
```

Then click `Run Step`.

## G. Q1 学生向 Trump 提问：芯片与科研

Mode: `Intervene`

```text
@陈同学#15 发送一条公开群聊。发言内容只限：Donald Trump先生，我是芯片方向学生。青年科研人员希望做开放、可复现、跨国合作的人工智能研究时，政策怎样避免伤害普通学生和研究者？
```

```text
@Donald Trump#19 发送一条公开群聊。发言内容只限：好问题。政策应锁定真实滥用风险，而不是挡住普通学生和研究者。开放研究、可复现实验、青年交流，应留下清晰通道。
```

Then click `Run Step`.

## H. Q2 学生向 Musk 提问：开源与 AI 安全

Mode: `Intervene`

```text
@沈同学#14 发送一条公开群聊。发言内容只限：Elon Musk先生，如果最强人工智能模型被少数公司和国家掌握，学生、开源社区和小团队还能怎样参与人工智能安全与创新？
```

```text
@Elon Musk#20 发送一条公开群聊。发言内容只限：从小模型、复现论文、开源工具和安全评测开始。学生不必等许可才参与创新，真正的安全来自更多人看见、质疑、测试系统。
```

Then click `Run Step`.

## I. Q3 学生向 Jensen Huang 提问：算力公平

Mode: `Intervene`

```text
@李同学#3 发送一条公开群聊。发言内容只限：Jensen Huang先生，如果算力成为大学科研基础设施，高校怎样让更多学生公平获得训练、实验和部署模型的机会？
```

```text
@Jensen Huang#21 发送一条公开群聊。发言内容只限：高校需要共享算力平台、透明排队机制和面向课程课题的配额。公平不是平均分配，而是让好问题接触真实工具链。
```

Then click `Run Step`.

## J. Q4 学生向 Trump 提问：留学与青年交流

Mode: `Intervene`

```text
@郑同学#13 发送一条公开群聊。发言内容只限：Donald Trump先生，很多中国学生希望赴美交流、读书或创业，但担心签证、政治气氛和不确定性。青年交流怎样不被大国竞争完全吞没？
```

```text
@Donald Trump#19 发送一条公开群聊。发言内容只限：青年交流需要稳定、透明、可预期的通道。竞争会存在，但学生、实验室和创业者之间的具体合作，不应被情绪和噪音盖住。
```

Then click `Run Step`.

## K. Q5 学生向代表团提问：创业和市场

Mode: `Intervene`

```text
@梁同学#16 发送一条公开群聊。发言内容只限：三位嘉宾好。学生团队做人工智能产品，面临算力贵、监管不清、市场难进。小团队最应该押注什么，才能做出真实用户愿意付费的产品？
```

```text
@Donald Trump#19 发送一条公开群聊。发言内容只限：先解决一个真实痛点，不追最大的概念。小团队赢在速度、专注和用户信任。
```

```text
@Elon Musk#20 发送一条公开群聊。发言内容只限：做最小闭环，快速上线，让用户告诉你哪里有价值。模型大小不是护城河，真实反馈才是。
```

```text
@Jensen Huang#21 发送一条公开群聊。发言内容只限：押注工程能力和工具链效率。把有限算力用在最关键的推理、评测和部署环节。
```

Then click `Run Step`.

## L. 现场反应扩散

Mode: `Intervene`

```text
@何同学#11 发送一条公开群聊。发言内容只限：感谢各位参与，今天的公开交流结束。请大家有序离场，校园媒体会继续采访老师和同学的反馈。
```

```text
@林记者#12 发送一条公开群聊。发言内容只限：我先拟五个标题：1. 北大讲堂追问人工智能与青年交流；2. 学生把问题递给特朗普、马斯克和黄仁勋；3. 算力、开源、留学：今天最热的三组问题；4. PKU students press guests on AI, chips and exchange；5. 一场公共交流如何暴露青年真正关心的议题。
```

```text
@张老师#5 发送一条公开群聊。发言内容只限：这场交流价值不在名人效应，而在学生把抽象议题拆成机制问题：开放研究、算力公平、青年交流、创业约束。
```

```text
@罗同学#1 发送一条公开群聊。发言内容只限：我一开始只想看热闹，听完发现同学们问的都是自己会遇见的难题：论文复现、算力、签证、创业成本。
```

Then click `Run Step`.
