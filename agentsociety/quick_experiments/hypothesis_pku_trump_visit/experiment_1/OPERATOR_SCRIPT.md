# Operator Script · PKU Trump Campus Visit

<p align="right">
  <a href="OPERATOR_SCRIPT.zh-CN.md">🌏 中文</a>
</p>

Paste these blocks into the GOD control room **in order**. After each
`Intervene`, click `Run Step` once or twice. Each `Ask` is for grabbing a clean,
edit-ready quote.

When you publish, put the "AI what-if experiment" disclaimer in the video
description, caption corner, or repo README — never have the characters say it
in dialogue. The in-scene prompts are written to feel like a real campus event.

**Core beat:**

1. First 1–2 steps: PKU daily life only. No lecture, no delegation, no visit news.
2. Manually inject the visit notice. Let campus discussion ferment.
3. Delegation enters at `west_gate`.
4. Everyone gathers at `centennial_hall`; run two steps to make sure they arrive.
5. Each round: one student asks a question, the delegation answers, the campus reacts.

**Fixed IDs:**

- `#1 Luo (student)`
- `#2 Wang (TA)`
- `#3 Li (student)`
- `#4 Chen (teacher)`
- `#5 Zhang (teacher)`
- `#6 Zhou (teacher)`
- `#7 Zhao (alumnus)`
- `#8 Liu (aunt)`
- `#9 Wang (student)`
- `#10 Sun (student)`
- `#11 He (student)`
- `#12 Lin (reporter)`
- `#13 Zheng (student)`
- `#14 Shen (student)`
- `#15 Chen (student)`
- `#16 Liang (student)`
- `#17 Ma (student)`
- `#18 Liu (student)`
- `#19 Donald Trump`
- `#20 Elon Musk`
- `#21 Jensen Huang`
- `#22 Coordinator Wang`

## 0. Daily-life director prompt

Mode: `Intervene`

```text
@all_residents The next two steps are an ordinary Friday morning at PKU. Show only classes, self-study, lab research, library, canteen, dorm life, sports, club activity, a walk around Weiming Lake, photos near Boya Pagoda, or normal small talk. No one knows about any upcoming visit or lecture; do not mention Donald Trump, the delegation, a speech, Centennial Hall, or the visit. Keep dialogue like real students and teachers — light, natural, with everyday details.
```

Then click `Run Step` twice.

Acceptance: dorm, classrooms, library, lab, canteen, gym, Weiming Lake, and Boya
Pagoda all show natural campus life. If anyone mentions the lecture too early,
restart the run and re-paste this prompt first.

## 1. Visit notice

Mode: `Intervene`

```text
@system Today's campus event notice: later this morning, Donald Trump will lead a delegation to visit Peking University and give a public talk for students at Centennial Hall. The delegation includes Elon Musk, Jensen Huang, and Coordinator Wang. Topic: youth in China–US exchange, AI, chips, open source, entrepreneurship, and global cooperation. Teachers, students, volunteers, campus media, and campus service staff: react naturally according to your role — discuss, prep questions, or organize the public flow. Characters must not say "this is an experiment / script / setting"; just react like real people on campus. Do not generate real security routes or control details.
```

Then click `Run Step`.

## 2. Discussion ferments

Mode: `Intervene`

```text
@all_residents React naturally to the notice that "Donald Trump is giving a public talk at PKU today." Students may chat in the canteen, dorm, library, classrooms, labs, gym, or by Weiming Lake. Teachers may sketch a class angle. Campus reporters may draft headlines. Canteen and library staff can observe student moods. Not everyone has to agree — let curiosity, skepticism, excitement, worry, teasing, realism, and quiet skepticism coexist. Characters speak only from in-scene state.
```

Then click `Run Step` once or twice.

## 3. Delegation enters via West Gate

Mode: `Intervene`

```text
@Donald Trump #19 @Elon Musk #20 @Jensen Huang #21 @Coordinator Wang #22 As the visiting delegation, head to west_gate. You enter PKU through the West Gate for the public visit flow: brief greetings and confirmation of the schedule. Do not describe security details; only show a public visit, polite exchanges, observations of campus, and event pacing.
```

Then click `Run Step`.

## 4. Everyone gathers at Centennial Hall

Mode: `Intervene`

```text
@all_residents Gather at centennial_hall. The public talk is about to begin. Teachers, students, volunteers, campus media, and the delegation who need to attend, host, report, ask, or audit should head to the hall. Others can keep discussing in the canteen, library, or by Weiming Lake, but the main camera should focus on Centennial Hall. Do not start the speech yet — just move and enter.
```

Then click `Run Step` twice.

Note: this experiment caps PKU map travel at two steps to arrive. After step
one you'll see movement; after step two most agents should be at or entering
the hall. Confirm before continuing.

## 5. Opening & host

Mode: `Intervene`

```text
@He (student) #11 @Donald Trump #19 @Coordinator Wang #22 The public talk at Centennial Hall has begun. He (student) gives a one-line natural opening as the student host. Coordinator Wang offers only public flow cues. Donald Trump then gives a short opening speech under 120 characters, themed on China–US youth exchange, AI innovation, commercial cooperation, and global competition. The tone can have strong personal style, but do not make real-world policy commitments and do not break the fourth wall. End by inviting student questions.
```

Then click `Run Step`.

## 6. First reactions

Mode: `Intervene`

```text
@all_residents React naturally to the opening speech. Teachers focus on concepts and boundaries; students on study-abroad, jobs, research, open source, chips, entrepreneurship, and the international atmosphere; campus reporters look for headline angles; regular students can grumble, get excited, stay cautious, or feel puzzled. Do not move to the next question yet — show only the first wave of in-hall reaction.
```

Then click `Run Step`.

## 7. Q1 — Chip restrictions & student research

Mode: `Intervene`

```text
@Chen (student) #15 Next step: ask Donald Trump a question at centennial_hall. Land this as an action_proposal: action_type=direct_message, receiver_id=19, content=As a PhD student working on chips, I care about the tension between China–US AI cooperation and chip restrictions. If young researchers want to do open, reproducible, cross-border AI research, how should policy avoid hurting ordinary students and researchers? Do not answer for Donald Trump — only ask.
```

Then click `Run Step`.

Mode: `Intervene`

```text
@Donald Trump #19 You just received Chen's question on chip restrictions, student research, and cross-border cooperation. Next step: answer publicly via action_proposal: action_type=group_message, public=true, content=Reply in under 100 characters. Natural tone, personal style, no real-world policy commitments, and aim to be understandable for ordinary students.
```

Then click `Run Step`.

Optional clean take:

Mode: `Ask`

```text
@Donald Trump #19 Please condense your earlier answer on "chip restrictions and student research" into a punchy line under 100 characters. Keep the in-scene feel. No meta commentary.
```

## 8. Q1 reactions

Mode: `Intervene`

```text
@all_residents React naturally to the Q&A on chip restrictions and student research. Chen and Li care about research resources. Zhou cares about safety and open-source boundaries. Zhang cares about how policy language lands on ordinary students. Other students can crack a joke or share realistic worries.
```

Then click `Run Step`.

## 9. Q2 — Open source & AI safety

Mode: `Intervene`

```text
@Shen (student) #14 Next step: ask Elon Musk at centennial_hall. Land it as an action_proposal: action_type=direct_message, receiver_id=20, content=If the strongest AI models keep concentrating in a few companies and countries, how can students, open-source communities, and small teams still participate in AI safety and innovation? Do not answer for Elon Musk — only ask.
```

Then click `Run Step`.

Mode: `Intervene`

```text
@Elon Musk #20 You just received Shen's question on open source, AI safety, and student participation. Next step: answer publicly via action_proposal: action_type=group_message, public=true, content=Reply in under 90 characters. Natural tone, no real business commitments. Focus on what opportunities still exist for students and small teams.
```

Then click `Run Step`.

Mode: `Ask`

```text
@Elon Musk #20 Please condense your earlier answer on open-source AI, safety, and student participation into a punchy line under 90 characters. Keep the in-scene feel.
```

## 10. Q3 — Compute fairness

Mode: `Intervene`

```text
@Li (student) #3 Next step: ask Jensen Huang at centennial_hall. Land it as an action_proposal: action_type=direct_message, receiver_id=21, content=If AI compute becomes the key infrastructure for university research in the future, how can universities like PKU give more students fair access to training, experimenting, and deploying models? Do not answer for Jensen Huang — only ask.
```

Then click `Run Step`.

Mode: `Intervene`

```text
@Jensen Huang #21 You just received Li's question on AI compute fairness in higher education. Next step: answer publicly via action_proposal: action_type=group_message, public=true, content=Reply in under 100 characters. Natural tone, no real business commitments. Focus on university infrastructure, shared platforms, and student opportunities.
```

Then click `Run Step`.

Mode: `Ask`

```text
@Jensen Huang #21 Please condense your earlier answer on compute fairness for universities into a punchy line under 100 characters. Keep the in-scene feel.
```

## 11. Q4 — Study abroad & youth exchange

Mode: `Intervene`

```text
@Zheng (student) #13 Next step: ask Donald Trump at centennial_hall. Land it as an action_proposal: action_type=direct_message, receiver_id=19, content=Many Chinese students want to study, exchange, or start companies in the US, but worry about visas, the political climate, and uncertainty. How would you reassure ordinary students that youth exchange will not be swallowed by great-power competition? Do not answer for Donald Trump.
```

Then click `Run Step`.

Mode: `Intervene`

```text
@Donald Trump #19 You just received Zheng's question on study-abroad, visa climate, and youth exchange. Next step: answer publicly via action_proposal: action_type=group_message, public=true, content=Reply in under 100 characters. Natural tone, no real policy commitments. Focus on ordinary students' uncertainty.
```

Then click `Run Step`.

Mode: `Ask`

```text
@Donald Trump #19 Please condense your earlier answer on study-abroad and youth exchange into a punchy line under 100 characters. Keep the in-scene feel.
```

## 12. Q5 — Startups, markets, uncertainty

Mode: `Intervene`

```text
@Liang (student) #16 Next step: ask Donald Trump, Elon Musk, and Jensen Huang at centennial_hall. First land the question as an action_proposal: action_type=direct_message, receiver_id=19, content=If young entrepreneurs in both China and the US want to build AI products but face regulation, compute, market access, and geopolitical uncertainty, what should small teams bet on? Do not answer for the delegation — only ask.
```

Then click `Run Step`.

Mode: `Intervene`

```text
@Donald Trump #19 @Elon Musk #20 @Jensen Huang #21 Around Liang's question on AI startups, small-team opportunity, and global market uncertainty, each of you reply publicly with one line. Use action_proposal: action_type=group_message, public=true, content=One sentence each, under 50 characters per sentence. Natural tone. Do not claim real-world policy, real investment, or real commercial commitments.
```

Then click `Run Step`.

Mode: `Ask`

```text
@Donald Trump #19 @Elon Musk #20 @Jensen Huang #21 Please condense your earlier replies on AI entrepreneurship and small-team opportunity into one line each, under 50 characters per line. Keep the in-scene feel.
```

## 13. After the hall

Mode: `Intervene`

```text
@all_residents Public exchange and Q&A are done. Disperse naturally based on your role: students can keep talking outside Centennial Hall, in the canteen, by Weiming Lake, or in the library. Lin the reporter drafts headlines. Zhang and Zhou rate the value and limits of the exchange. AI-track students focus on chips, open source, compute, and research cooperation. Regular students focus on study-abroad, jobs, and the international atmosphere. Disagreement, grumbling, excitement, cautious optimism, and realistic worry can all coexist.
```

Then click `Run Step` once or twice.

## 14. Campus media headlines

Mode: `Ask`

```text
@Lin (reporter) #12 As a campus media reporter, write 5 different-style headlines for this "Donald Trump speech at PKU" event: rational news, Bilibili-viral, Xiaohongshu, mainstream Chinese social media, and academic observation. After each headline, explain in one line why it spreads. Headlines should feel like real on-scene takes — keep meta disclaimers in the post body or caption corner.
```

## 15. Experiment summary

Mode: `Ask`

```text
@system Please summarize this "Donald Trump speech at PKU" scripted experiment: 1) the three issues students cared about most; 2) the point in the delegation's answers that drove the most discussion; 3) whether campus agents diverged in attitude; 4) which clips would cut best as short videos; 5) how to adjust roles, questions, or movement pacing for the next run. End with one line suitable for a video description marking it as an AI what-if experiment, without bleeding into the in-scene voice.
```

## Current capability boundary

- You can pre-write each manual step and paste them in order as above.
- Students can ask delegation agents questions: first send a `direct_message`
  to the delegation `receiver_id`, then have the delegation reply via a public
  `group_message`.
- For clean exports, follow each answer with an `Ask` to grab a tight short
  quote.
- There is no "auto-consume a scripted timeline" mode yet — you still paste
  each Intervene / Ask manually. Full automation would require a timeline
  runner that lets the config declare which intervention to dispatch on which
  step.
