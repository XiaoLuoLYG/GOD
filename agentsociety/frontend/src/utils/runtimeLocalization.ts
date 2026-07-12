export type LocalizedFields = Record<string, Record<string, unknown>>;

export type LocalizedMapLike = {
    map_id?: string;
    mapId?: string;
    display_name?: string;
    displayName?: string;
    localized?: LocalizedFields;
};

export type LocalizedLocationLike = {
    id: string;
    name?: string;
    aliases?: string[];
    localized?: LocalizedFields;
};

export type LocalizedInteractionLike = {
    id: string;
    name?: string;
    description?: string;
    localized?: LocalizedFields;
};

type Locale = 'en' | 'zh';

type BilingualText = {
    en: string;
    zh: string;
};

type InteractionLabels = {
    name: BilingualText;
    description?: BilingualText;
};

type FirstPartyMapLabels = {
    displayName: BilingualText;
    locations: Record<string, BilingualText>;
    interactions: Record<string, InteractionLabels>;
};

const FIRST_PARTY_MAP_LABELS: Record<string, FirstPartyMapLabels> = {
    the_ville: {
        displayName: { en: 'The Ville Pixel Map', zh: '维尔小镇像素地图' },
        locations: {
            home: { en: 'Home', zh: '家' },
            school: { en: 'School Classroom', zh: '学校教室' },
            library: { en: 'School Library', zh: '学校图书馆' },
            cafe: { en: 'Hobbs Cafe', zh: '霍布斯咖啡馆' },
            park: { en: 'Johnson Park', zh: '约翰逊公园' },
            supply_store: { en: 'Harvey Oak Supply Store', zh: '哈维橡树供给店' },
            market: { en: 'The Willows Market', zh: '柳树市场' },
            pharmacy: { en: 'The Willows Pharmacy', zh: '柳树药房' },
            pub: { en: 'The Rose and Crown Pub', zh: '玫瑰王冠酒馆' },
            dorm: { en: 'Oak Hill College Dormitory', zh: '橡树山学院宿舍' },
        },
        interactions: {
            cook_meal: { name: { en: 'Cook Meal', zh: '做饭' }, description: { en: 'Prepare a simple meal at home.', zh: '在家准备一顿普通饭菜。' } },
            eat_at_home: { name: { en: 'Eat at Home', zh: '在家吃饭' }, description: { en: 'Eat at home and return to the daily rhythm.', zh: '在家吃饭并恢复日常节奏。' } },
            sleep_at_home: { name: { en: 'Sleep', zh: '睡觉' }, description: { en: 'Sleep at home or take a short nap.', zh: '在家睡觉或午休。' } },
            relax_at_home: { name: { en: 'Relax at Home', zh: '居家休息' }, description: { en: 'Rest, organize belongings, or do a light activity at home.', zh: '在家休息、整理物品或做轻松活动。' } },
            attend_class: { name: { en: 'Attend Class', zh: '上课' }, description: { en: 'Attend class as a student in an Oak Hill College classroom.', zh: '作为学生在 Oak Hill College 教室上课。' } },
            teach_class: { name: { en: 'Teach Class', zh: '教书' }, description: { en: 'Teach a class in an Oak Hill College classroom.', zh: '作为老师在 Oak Hill College 教室教课。' } },
            study_after_class: { name: { en: 'Study After Class', zh: '课后学习' }, description: { en: 'Review, prepare lessons, or finish homework at school.', zh: '在学校复习、备课或完成作业。' } },
            read_book: { name: { en: 'Read', zh: '阅读' }, description: { en: 'Read in the school library.', zh: '在学校图书馆阅读。' } },
            study_library: { name: { en: 'Library Study', zh: '图书馆学习' }, description: { en: 'Study quietly in the school library.', zh: '在学校图书馆安静学习。' } },
            eat_light_meal: { name: { en: 'Light Meal', zh: '简餐' }, description: { en: 'Have a simple meal at Hobbs Cafe.', zh: '在 Hobbs Cafe 吃一顿简餐。' } },
            chat_over_coffee: { name: { en: 'Coffee Chat', zh: '咖啡聊天' }, description: { en: 'Chat with a friend at Hobbs Cafe.', zh: '在 Hobbs Cafe 和朋友聊天。' } },
            work_cafe_shift: { name: { en: 'Cafe Shift', zh: '咖啡馆值班' }, description: { en: 'Work behind the counter at Hobbs Cafe.', zh: '在 Hobbs Cafe 柜台工作。' } },
            take_walk: { name: { en: 'Take a Walk', zh: '散步' }, description: { en: 'Take a walk in Johnson Park.', zh: '在 Johnson Park 散步。' } },
            meet_friend: { name: { en: 'Meet a Friend', zh: '见朋友' }, description: { en: 'Meet and talk with a friend in Johnson Park.', zh: '在 Johnson Park 和朋友见面交流。' } },
            rest_on_bench: { name: { en: 'Rest on a Bench', zh: '长椅休息' }, description: { en: 'Rest briefly on a bench in Johnson Park.', zh: '在 Johnson Park 长椅上短暂休息。' } },
            coordinate_group: { name: { en: 'Park Meetup', zh: '公园碰头' }, description: { en: 'Meet in Johnson Park and coordinate the next activity.', zh: '在 Johnson Park 汇合并协调下一步活动。' } },
            inspect_supplies: { name: { en: 'Inspect Supplies', zh: '清点货架' }, description: { en: 'Check tools and household supplies at Harvey Oak Supply Store.', zh: '在 Harvey Oak Supply Store 查看工具和生活物资。' } },
            prepare_kit: { name: { en: 'Prepare Supplies', zh: '准备用品' }, description: { en: 'Organize supplies to take from Harvey Oak Supply Store.', zh: '在 Harvey Oak Supply Store 整理需要带走的用品。' } },
            repair_tools: { name: { en: 'Repair Tools', zh: '修理工具' }, description: { en: 'Use tools for repairs at Harvey Oak Supply Store.', zh: '在 Harvey Oak Supply Store 使用工具进行维修。' } },
            buy_food: { name: { en: 'Buy Food', zh: '买食物' }, description: { en: 'Buy food or household goods at The Willows Market.', zh: '在 The Willows Market 购买食物或生活用品。' } },
            work_shop_shift: { name: { en: 'Shop Shift', zh: '店铺值班' }, description: { en: 'Work a shop shift at The Willows Market.', zh: '在 The Willows Market 店铺工作。' } },
            buy_medicine: { name: { en: 'Buy Medicine', zh: '买药' }, description: { en: 'Buy medicine at The Willows Pharmacy.', zh: '在 The Willows Pharmacy 购买药品。' } },
            pharmacy_consultation: { name: { en: 'Pharmacy Consultation', zh: '药房咨询' }, description: { en: 'Ask about medicine or health concerns at The Willows Pharmacy.', zh: '在 The Willows Pharmacy 咨询药品或健康问题。' } },
            socialize_at_pub: { name: { en: 'Pub Socializing', zh: '酒馆社交' }, description: { en: 'Chat with acquaintances at The Rose and Crown Pub.', zh: '在 The Rose and Crown Pub 和熟人聊天。' } },
            eat_pub_meal: { name: { en: 'Pub Meal', zh: '酒馆用餐' }, description: { en: 'Eat a meal at The Rose and Crown Pub.', zh: '在 The Rose and Crown Pub 吃饭。' } },
            rest_at_dorm: { name: { en: 'Dorm Rest', zh: '宿舍休息' }, description: { en: 'Rest at the Oak Hill College dormitory.', zh: '在 Oak Hill College 宿舍休息。' } },
            eat_at_dorm: { name: { en: 'Dorm Meal', zh: '宿舍用餐' }, description: { en: 'Eat at the Oak Hill College dormitory.', zh: '在 Oak Hill College 宿舍吃饭。' } },
            tidy_home: { name: { en: 'Tidy Home', zh: '整理家务' }, description: { en: 'Clean the room or organize belongings at home.', zh: '在家收拾房间或整理物品。' } },
            read_at_home: { name: { en: 'Read at Home', zh: '在家阅读' }, description: { en: 'Read a book or magazine at home.', zh: '在家中翻一本书或杂志。' } },
            work_from_home: { name: { en: 'Work from Home', zh: '居家办公' }, description: { en: 'Handle remote work from home.', zh: '在家中远程处理工作。' } },
            video_call_family: { name: { en: 'Video Call Family', zh: '视频家人' }, description: { en: 'Have a video call with family at home.', zh: '在家中和家人视频通话。' } },
            water_plants: { name: { en: 'Water Plants', zh: '浇花' }, description: { en: 'Water or trim plants at home.', zh: '在家给花草浇水或修剪。' } },
            prepare_lesson: { name: { en: 'Prepare Lesson', zh: '备课' }, description: { en: 'Prepare course materials in the school classroom.', zh: '在学校教室准备课程材料。' } },
            grade_homework: { name: { en: 'Grade Homework', zh: '批改作业' }, description: { en: 'Grade student assignments in the classroom or office.', zh: '在学校教室或办公室批改学生作业。' } },
            hold_office_hours: { name: { en: 'Office Hours', zh: '课后答疑' }, description: { en: 'Receive students for questions or conversation at school.', zh: '在学校接待学生答疑或谈话。' } },
            school_meeting: { name: { en: 'School Meeting', zh: '教研例会' }, description: { en: 'Attend a teaching or administrative meeting at school.', zh: '在学校参加教研或行政例会。' } },
            research_topic: { name: { en: 'Research Materials', zh: '资料查阅' }, description: { en: 'Look up research materials in the school library.', zh: '在学校图书馆查找资料。' } },
            borrow_book: { name: { en: 'Borrow Book', zh: '借书' }, description: { en: 'Borrow a book from the library.', zh: '在图书馆办理借书手续。' } },
            return_book: { name: { en: 'Return Book', zh: '还书' }, description: { en: 'Return a borrowed book to the library.', zh: '在图书馆归还借出的书籍。' } },
            quiet_work: { name: { en: 'Quiet Work', zh: '安静办公' }, description: { en: 'Work quietly on personal tasks in the library.', zh: '在图书馆安静地进行个人办公。' } },
            order_coffee: { name: { en: 'Order Coffee', zh: '点咖啡' }, description: { en: 'Order a cup of coffee at Hobbs Cafe.', zh: '在 Hobbs Cafe 点一杯咖啡。' } },
            take_takeaway: { name: { en: 'Takeaway', zh: '外带' }, description: { en: 'Pack drinks or a light meal to go from Hobbs Cafe.', zh: '在 Hobbs Cafe 打包外带饮品或简餐。' } },
            casual_meetup: { name: { en: 'Casual Meetup', zh: '随性碰头' }, description: { en: 'Meet an acquaintance casually at Hobbs Cafe.', zh: '在 Hobbs Cafe 和熟人临时碰个面。' } },
            tidy_cafe: { name: { en: 'Tidy Cafe', zh: '整理咖啡馆' }, description: { en: 'Arrange tables, refill water, or clean the counter at Hobbs Cafe.', zh: '在 Hobbs Cafe 整理桌椅、补水或清洁吧台。' } },
            morning_exercise: { name: { en: 'Morning Exercise', zh: '晨练' }, description: { en: 'Exercise or stretch in Johnson Park.', zh: '在 Johnson Park 晨练或拉伸。' } },
            bird_watch: { name: { en: 'Bird Watching', zh: '观鸟' }, description: { en: 'Quietly watch birds in the trees at Johnson Park.', zh: '在 Johnson Park 安静看树上的鸟。' } },
            picnic: { name: { en: 'Simple Picnic', zh: '简单野餐' }, description: { en: 'Have a simple picnic or boxed meal on the grass in Johnson Park.', zh: '在 Johnson Park 草地上简单野餐或吃便当。' } },
            public_announcement: { name: { en: 'Public Announcement', zh: '公共播报' }, description: { en: 'Post a public notice or reminder to the group from Johnson Park.', zh: '在 Johnson Park 向群组发布公共公告或提醒。' } },
            restock_shelves: { name: { en: 'Restock Shelves', zh: '上货' }, description: { en: 'Restock shelves at Harvey Oak Supply Store.', zh: '在 Harvey Oak Supply Store 给货架上货。' } },
            customer_service: { name: { en: 'Customer Service', zh: '顾客接待' }, description: { en: 'Receive customers at Harvey Oak Supply Store.', zh: '在 Harvey Oak Supply Store 接待来店顾客。' } },
            lend_tools: { name: { en: 'Lend Tools', zh: '借出工具' }, description: { en: 'Lend tools to regular customers or neighbors at Harvey Oak Supply Store.', zh: '在 Harvey Oak Supply Store 借出工具给熟客或邻居。' } },
            restock_vegetables: { name: { en: 'Restock Produce', zh: '蔬果补货' }, description: { en: 'Restock the produce stand at The Willows Market.', zh: '在 The Willows Market 给蔬果摊补货。' } },
            haggle_price: { name: { en: 'Haggle Price', zh: '议价' }, description: { en: 'Negotiate prices with customers at The Willows Market.', zh: '在 The Willows Market 和顾客议价。' } },
            deliver_order: { name: { en: 'Deliver Order', zh: '送单' }, description: { en: 'Deliver an order to a nearby neighbor from The Willows Market.', zh: '在 The Willows Market 给附近邻居送一单。' } },
            chat_with_regular: { name: { en: 'Chat with Regulars', zh: '和老客闲聊' }, description: { en: 'Exchange greetings with regular customers at The Willows Market.', zh: '在 The Willows Market 和老顾客寒暄。' } },
            refill_prescription: { name: { en: 'Refill Prescription', zh: '续方' }, description: { en: 'Refill a prescription for a resident at The Willows Pharmacy.', zh: '在 The Willows Pharmacy 为居民办理处方续方。' } },
            blood_pressure_check: { name: { en: 'Blood Pressure Check', zh: '量血压' }, description: { en: 'Check and record a resident\'s blood pressure at The Willows Pharmacy.', zh: '在 The Willows Pharmacy 为居民量血压并记录。' } },
            organize_medicine_shelf: { name: { en: 'Organize Medicine Shelf', zh: '整理药架' }, description: { en: 'Organize medicines and check expiration dates at The Willows Pharmacy.', zh: '在 The Willows Pharmacy 整理药品和过期排查。' } },
            home_visit_prep: { name: { en: 'Home Visit Prep', zh: '上门准备' }, description: { en: 'Prepare supplies for a home follow-up visit at The Willows Pharmacy.', zh: '在 The Willows Pharmacy 整理上门随访需要带的用品。' } },
            watch_match: { name: { en: 'Watch Match', zh: '看比赛' }, description: { en: 'Watch a sports broadcast at The Rose and Crown Pub.', zh: '在 The Rose and Crown Pub 看一场比赛转播。' } },
            evening_chat: { name: { en: 'Evening Chat', zh: '晚间闲聊' }, description: { en: 'Chat with acquaintances in the evening at The Rose and Crown Pub.', zh: '在 The Rose and Crown Pub 和熟人晚间闲聊。' } },
            host_event: { name: { en: 'Host Small Event', zh: '主持小活动' }, description: { en: 'Organize a small event at The Rose and Crown Pub.', zh: '在 The Rose and Crown Pub 张罗一个小型活动。' } },
            study_in_dorm: { name: { en: 'Dorm Study', zh: '宿舍自习' }, description: { en: 'Study quietly at the Oak Hill College dormitory.', zh: '在 Oak Hill College 宿舍安静自习。' } },
            common_room_hangout: { name: { en: 'Common Room Hangout', zh: '公共区休闲' }, description: { en: 'Relax with classmates in the dormitory common room.', zh: '在 Oak Hill College 宿舍公共区和同学休闲。' } },
            video_call_home: { name: { en: 'Video Call Home', zh: '视频家里' }, description: { en: 'Video call family from the Oak Hill College dormitory.', zh: '在 Oak Hill College 宿舍和家人视频。' } },
        },
    },
    pku: {
        displayName: { en: 'Peking University Yanyuan', zh: '北京大学燕园' },
        locations: {
            west_gate: { en: 'Peking University West Gate', zh: '北京大学西门' },
            east_gate: { en: 'Peking University East Gate', zh: '北京大学东门' },
            south_gate: { en: 'Peking University South Gate', zh: '北京大学南门' },
            weiming_lake: { en: 'Weiming Lake', zh: '未名湖' },
            boya_pagoda: { en: 'Boya Pagoda', zh: '博雅塔' },
            library: { en: 'Peking University Library', zh: '北京大学图书馆' },
            centennial_hall: { en: 'Centennial Hall', zh: '百周年纪念讲堂' },
            teaching_building: { en: 'Teaching Building', zh: '教学楼' },
            dormitory: { en: 'Student Dormitory', zh: '学生宿舍' },
            canteen: { en: 'Student Canteen', zh: '学生食堂' },
            gymnasium: { en: 'Gymnasium', zh: '体育馆' },
            lab_building: { en: 'Science Laboratory Building', zh: '理科实验楼' },
            admin_building: { en: 'Administration Building', zh: '办公楼' },
            campus_green: { en: 'Campus Green', zh: '校园草坪' },
        },
        interactions: {
            enter_campus: { name: { en: 'Enter Campus', zh: '进入校园' }, description: { en: 'Enter or leave campus through a gate while checking plans.', zh: '通过校门进出校园并确认行程。' } },
            meet_at_gate: { name: { en: 'Gate Meetup', zh: '校门碰头' }, description: { en: 'Meet someone at a campus gate before moving inward.', zh: '在校门与他人会合后再进入校园。' } },
            campus_tour: { name: { en: 'Campus Tour', zh: '校园导览' }, description: { en: 'Guide visitors through landmark routes and share campus context.', zh: '带领访客走过校园地标路线并介绍背景。' } },
            walk_lake: { name: { en: 'Lake Walk', zh: '湖边散步' }, description: { en: 'Walk around Weiming Lake and hold a quiet conversation.', zh: '沿未名湖散步并安静交谈。' } },
            outdoor_reflection: { name: { en: 'Outdoor Reflection', zh: '户外思考' }, description: { en: 'Pause outdoors to reflect, plan, or decompress.', zh: '在户外停下来思考、规划或放松。' } },
            take_photo: { name: { en: 'Landmark Photo', zh: '地标拍照' }, description: { en: 'Take a landmark photo or describe what can be seen from the spot.', zh: '拍摄地标照片或描述当前位置所见。' } },
            study_library: { name: { en: 'Library Study', zh: '图书馆自习' }, description: { en: 'Study quietly, read notes, or prepare for class.', zh: '安静自习、阅读笔记或准备课程。' } },
            borrow_book: { name: { en: 'Borrow or Return Books', zh: '借还图书' }, description: { en: 'Borrow, return, or search for a book.', zh: '借书、还书或检索图书。' } },
            research_discussion: { name: { en: 'Research Discussion', zh: '科研讨论' }, description: { en: 'Discuss papers, experiments, or a research question.', zh: '讨论论文、实验或科研问题。' } },
            attend_lecture: { name: { en: 'Attend Lecture', zh: '参加讲座' }, description: { en: 'Attend a lecture, forum, or talk.', zh: '参加讲座、论坛或报告。' } },
            public_talk: { name: { en: 'Public Talk', zh: '公共报告' }, description: { en: 'Give or listen to a public campus talk.', zh: '发表或聆听校园公共报告。' } },
            club_event: { name: { en: 'Club Event', zh: '社团活动' }, description: { en: 'Coordinate a student club event.', zh: '协调学生社团活动。' } },
            attend_class: { name: { en: 'Attend Class', zh: '上课' }, description: { en: 'Attend or teach a scheduled class.', zh: '参加或讲授计划中的课程。' } },
            office_hours: { name: { en: 'Office Hours', zh: '答疑办公' }, description: { en: 'Ask questions, tutor, or hold office hours.', zh: '答疑、辅导或开展办公时间。' } },
            group_project: { name: { en: 'Group Project', zh: '小组作业' }, description: { en: 'Work with classmates on a group task.', zh: '与同学合作完成小组任务。' } },
            rest_dorm: { name: { en: 'Dorm Rest', zh: '宿舍休息' }, description: { en: 'Rest, reset, or return to the dorm.', zh: '在宿舍休息、调整或返回宿舍。' } },
            chat_roommates: { name: { en: 'Roommate Chat', zh: '宿舍聊天' }, description: { en: 'Talk with roommates about daily campus life.', zh: '和室友聊校园日常。' } },
            prepare_day: { name: { en: 'Prepare to Leave', zh: '准备出门' }, description: { en: 'Pack books, check schedule, and prepare for the next activity.', zh: '整理书本、查看日程并准备下一项活动。' } },
            eat_canteen: { name: { en: 'Canteen Meal', zh: '食堂用餐' }, description: { en: 'Eat a meal in the student canteen.', zh: '在学生食堂用餐。' } },
            casual_meetup: { name: { en: 'Casual Meetup', zh: '随意见面' }, description: { en: 'Meet informally over food or a break.', zh: '在用餐或休息时随意见面。' } },
            share_news: { name: { en: 'Share News', zh: '交换消息' }, description: { en: 'Share recent campus news or plans.', zh: '交流近期校园消息或计划。' } },
            exercise: { name: { en: 'Exercise', zh: '运动锻炼' }, description: { en: 'Exercise indoors or on nearby sports grounds.', zh: '在室内或附近运动场锻炼。' } },
            team_practice: { name: { en: 'Team Practice', zh: '团队训练' }, description: { en: 'Coordinate sports practice or a team routine.', zh: '协调体育训练或团队练习。' } },
            wellness_check: { name: { en: 'Wellness Check', zh: '健康打卡' }, description: { en: 'Check personal health and energy after exercise.', zh: '运动后确认个人健康和精力状态。' } },
            run_experiment: { name: { en: 'Run Experiment', zh: '实验操作' }, description: { en: 'Run a lab task or inspect experimental results.', zh: '执行实验任务或检查实验结果。' } },
            lab_safety_check: { name: { en: 'Lab Safety Check', zh: '实验安全检查' }, description: { en: 'Check equipment, lab safety, or experiment setup.', zh: '检查设备、实验安全或实验准备情况。' } },
            department_meeting: { name: { en: 'Department Meeting', zh: '院系会议' }, description: { en: 'Attend an administrative or academic meeting.', zh: '参加行政或学术会议。' } },
            paperwork: { name: { en: 'Paperwork', zh: '事务办理' }, description: { en: 'Handle paperwork, permissions, or coordination tasks.', zh: '处理材料、权限或协调事务。' } },
        },
    },
};

const GROUP_LABELS: Record<string, BilingualText> = {
    北大校园: { en: 'PKU Campus', zh: '北大校园' },
    GOD公开频道: { en: 'GOD Public Channel', zh: 'GOD公开频道' },
    'GOD 公开频道': { en: 'GOD Public Channel', zh: 'GOD 公开频道' },
    小镇群聊: { en: 'Town Chat', zh: '小镇群聊' },
    town: { en: 'Town Chat', zh: '小镇群聊' },
};

const STATUS_LABELS: Record<string, BilingualText> = {
    initializing: { en: 'Initializing', zh: '初始化中' },
    ready: { en: 'Ready', zh: '就绪' },
    就绪: { en: 'Ready', zh: '就绪' },
    idle: { en: 'Idle', zh: '空闲' },
    空闲: { en: 'Idle', zh: '空闲' },
    active: { en: 'Active', zh: '活跃' },
    活跃: { en: 'Active', zh: '活跃' },
    waiting: { en: 'Waiting', zh: '等待中' },
    等待: { en: 'Waiting', zh: '等待中' },
    等待中: { en: 'Waiting', zh: '等待中' },
    moving: { en: 'Moving', zh: '移动中' },
    移动中: { en: 'Moving', zh: '移动中' },
    walking: { en: 'Walking', zh: '行走中' },
    running_step: { en: 'Running step', zh: '运行步骤中' },
    auto: { en: 'Auto', zh: '自动执行中' },
    asking: { en: 'Asking', zh: '询问中' },
    intervening: { en: 'Intervening', zh: '干预中' },
    arrived: { en: 'Arrived', zh: '已到达' },
    stopped: { en: 'Stopped', zh: '已停止' },
    failed: { en: 'Failed', zh: '失败' },
    offline: { en: 'Offline', zh: '离线' },
};

const ACTION_LABELS: Record<string, BilingualText> = {
    继续日常安排: { en: 'Continue daily routine', zh: '继续日常安排' },
    等待: { en: 'Wait', zh: '等待' },
    idle: { en: 'Idle', zh: '空闲' },
};

const EMOTION_LABELS: Record<string, BilingualText> = {
    calm: { en: 'Calm', zh: '平静' },
    平静: { en: 'Calm', zh: '平静' },
    neutral: { en: 'Neutral', zh: '中性' },
    中性: { en: 'Neutral', zh: '中性' },
    focused: { en: 'Focused', zh: '专注' },
    专注: { en: 'Focused', zh: '专注' },
    content: { en: 'Content', zh: '满足' },
    满足: { en: 'Content', zh: '满足' },
    curious: { en: 'Curious', zh: '好奇' },
    好奇: { en: 'Curious', zh: '好奇' },
    engaged: { en: 'Engaged', zh: '投入' },
    投入: { en: 'Engaged', zh: '投入' },
    tired: { en: 'Tired', zh: '疲惫' },
    疲惫: { en: 'Tired', zh: '疲惫' },
    anxious: { en: 'Anxious', zh: '焦虑' },
    焦虑: { en: 'Anxious', zh: '焦虑' },
};

function pickLocale(language?: string): Locale {
    return language?.toLowerCase().startsWith('en') ? 'en' : 'zh';
}

function titleizeId(value: string): string {
    return value
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

function hasHan(value: string): boolean {
    return /[\u4e00-\u9fff]/.test(value);
}

function stableLabelId(value: string): string {
    let hash = 0;
    Array.from(value || 'item').forEach((char) => {
        hash = ((hash * 31) + char.charCodeAt(0)) >>> 0;
    });
    return hash.toString(36).slice(0, 6) || 'item';
}

function fallbackEnglishLabel(fallback: string, kind: string): string {
    const title = titleizeId(fallback);
    if (title && !hasHan(title)) {
        return title;
    }
    return `${kind} ${stableLabelId(fallback)}`;
}

function avoidHanInEnglish(value: string, fallback: string, locale: Locale, kind: string): string {
    return locale === 'en' && hasHan(value) ? fallbackEnglishLabel(fallback, kind) : value;
}

function readLocalizedString(
    localized: LocalizedFields | undefined,
    locale: Locale,
    field: string,
): string | undefined {
    const value = localized?.[locale]?.[field];
    return typeof value === 'string' && value.trim() !== '' ? value : undefined;
}

function readLocalizedStringArray(
    localized: LocalizedFields | undefined,
    locale: Locale,
    field: string,
): string[] | undefined {
    const value = localized?.[locale]?.[field];
    if (!Array.isArray(value)) {
        return undefined;
    }
    const items = value
        .map((item) => String(item).trim())
        .filter(Boolean);
    return items.length > 0 ? items : undefined;
}

function mapIdFor(value: LocalizedMapLike | string | undefined): string {
    if (typeof value === 'string') {
        return value;
    }
    return String(value?.map_id || value?.mapId || '');
}

function localizedLocationCandidates(
    mapId: string,
    location: LocalizedLocationLike,
): string[] {
    const labels = FIRST_PARTY_MAP_LABELS[mapId]?.locations[location.id];
    return [
        location.id,
        location.name,
        ...(location.aliases || []),
        readLocalizedString(location.localized, 'en', 'name'),
        readLocalizedString(location.localized, 'zh', 'name'),
        ...(readLocalizedStringArray(location.localized, 'en', 'aliases') || []),
        ...(readLocalizedStringArray(location.localized, 'zh', 'aliases') || []),
        labels?.en,
        labels?.zh,
    ]
        .map((item) => String(item || '').trim())
        .filter(Boolean);
}

function findLocation(
    raw: string,
    mapId: string,
    locations: LocalizedLocationLike[],
): LocalizedLocationLike | undefined {
    const normalized = raw.trim();
    if (!normalized) {
        return undefined;
    }
    return locations.find((location) => (
        localizedLocationCandidates(mapId, location).some((candidate) => (
            candidate === normalized
            || (normalized.length >= 2 && candidate.includes(normalized))
        ))
    ));
}

function localizedInteractionCandidates(
    mapId: string,
    interaction: LocalizedInteractionLike,
): string[] {
    const labels = FIRST_PARTY_MAP_LABELS[mapId]?.interactions[interaction.id];
    return [
        interaction.id,
        interaction.name,
        readLocalizedString(interaction.localized, 'en', 'name'),
        readLocalizedString(interaction.localized, 'zh', 'name'),
        labels?.name.en,
        labels?.name.zh,
    ]
        .map((item) => String(item || '').trim())
        .filter(Boolean);
}

function localizeInteractionReference(
    raw: unknown,
    language: string | undefined,
    mapId: string,
    interactions: LocalizedInteractionLike[],
): string {
    if (raw === undefined || raw === null || raw === '') {
        return '';
    }
    const text = String(raw).trim();
    const match = interactions.find((interaction) => (
        localizedInteractionCandidates(mapId, interaction).some((candidate) => candidate === text)
    ));
    if (match) {
        return localizeMapInteraction(mapId, match, language).name || text;
    }
    const fallback = Object.entries(FIRST_PARTY_MAP_LABELS[mapId]?.interactions || {})
        .find(([, label]) => label.name.en === text || label.name.zh === text);
    return fallback
        ? fallback[1].name[pickLocale(language)]
        : text;
}

export function localizeMapDisplayName(
    map: LocalizedMapLike,
    language?: string,
): string {
    const locale = pickLocale(language);
    const mapId = mapIdFor(map);
    const value = readLocalizedString(map.localized, locale, 'display_name')
        || FIRST_PARTY_MAP_LABELS[mapId]?.displayName[locale]
        || String(map.display_name || map.displayName || mapId || '').trim()
        || titleizeId(mapId);
    return avoidHanInEnglish(value, mapId, locale, 'Map');
}

export function localizeMapLocationName(
    mapId: string,
    location: LocalizedLocationLike,
    language?: string,
): string {
    const locale = pickLocale(language);
    const value = readLocalizedString(location.localized, locale, 'name')
        || FIRST_PARTY_MAP_LABELS[mapId]?.locations[location.id]?.[locale]
        || String(location.name || '').trim()
        || titleizeId(location.id);
    return avoidHanInEnglish(value, location.id, locale, 'Location');
}

export function localizeMapLocationAliases(
    mapId: string,
    location: LocalizedLocationLike,
    language?: string,
): string[] {
    const locale = pickLocale(language);
    const fallback = FIRST_PARTY_MAP_LABELS[mapId]?.locations[location.id]?.[locale];
    return readLocalizedStringArray(location.localized, locale, 'aliases')
        || location.aliases
        || (fallback ? [fallback] : []);
}

export function localizeMapInteraction(
    mapId: string,
    interaction: LocalizedInteractionLike,
    language?: string,
    metadata?: LocalizedInteractionLike,
): LocalizedInteractionLike {
    const locale = pickLocale(language);
    const source = metadata || interaction;
    const fallback = FIRST_PARTY_MAP_LABELS[mapId]?.interactions[interaction.id];
    return {
        ...interaction,
        name: readLocalizedString(source.localized, locale, 'name')
            || fallback?.name[locale]
            || interaction.name
            || titleizeId(interaction.id),
        description: readLocalizedString(source.localized, locale, 'description')
            || fallback?.description?.[locale]
            || interaction.description
            || '',
    };
}

export function localizeLocationReference(
    raw: unknown,
    language: string | undefined,
    map: LocalizedMapLike,
    locations: LocalizedLocationLike[],
): string {
    if (raw === undefined || raw === null || raw === '') {
        return localizeMapDisplayName(map, language);
    }
    const text = String(raw).trim();
    const mapId = mapIdFor(map);
    const direct = findLocation(text, mapId, locations);
    if (direct) {
        return localizeMapLocationName(mapId, direct, language);
    }
    const fallbackLocation = Object.entries(FIRST_PARTY_MAP_LABELS[mapId]?.locations || {})
        .find(([, label]) => label.en === text || label.zh === text);
    if (fallbackLocation) {
        return FIRST_PARTY_MAP_LABELS[mapId].locations[fallbackLocation[0]][pickLocale(language)];
    }
    const mapName = FIRST_PARTY_MAP_LABELS[mapId]?.displayName;
    if (mapName && (mapName.en === text || mapName.zh === text)) {
        return mapName[pickLocale(language)];
    }
    return text;
}

export function localizeGroupName(raw: unknown, language?: string): string {
    if (raw === undefined || raw === null || raw === '') {
        return '';
    }
    const text = String(raw).trim();
    return GROUP_LABELS[text]?.[pickLocale(language)] || text;
}

export function localizeStatusLabel(raw: unknown, language?: string, fallback = 'idle'): string {
    const value = String(raw || fallback).trim();
    return STATUS_LABELS[value]?.[pickLocale(language)] || titleizeId(value);
}

export function isMovingRuntimeStatus(raw: unknown): boolean {
    const value = String(raw || '').trim().toLowerCase();
    return value === 'moving' || value === 'walking' || value === '移动中' || value === '行走中';
}

export function localizeEmotionLabel(raw: unknown, language?: string): string | undefined {
    if (raw === undefined || raw === null || raw === '') {
        return undefined;
    }
    const value = String(raw).trim();
    return EMOTION_LABELS[value]?.[pickLocale(language)] || value;
}

export function localizeRuntimeAction(
    raw: unknown,
    language: string | undefined,
    map: LocalizedMapLike,
    locations: LocalizedLocationLike[],
    interactions: LocalizedInteractionLike[],
    fallback: string,
): string {
    if (raw === undefined || raw === null || raw === '') {
        return fallback;
    }
    const text = String(raw).trim();
    const locale = pickLocale(language);
    const arrived = text.match(/^已到达\s*(.+)$/);
    if (arrived) {
        const location = localizeLocationReference(arrived[1], language, map, locations);
        return locale === 'en' ? `Arrived at ${location}` : `已到达${location}`;
    }
    const heading = text.match(/^正在前往\s*(.+)$/);
    if (heading) {
        const location = localizeLocationReference(heading[1], language, map, locations);
        return locale === 'en' ? `Heading to ${location}` : `正在前往${location}`;
    }
    const headingShort = text.match(/^前往\s*(.+)$/);
    if (headingShort) {
        const location = localizeLocationReference(headingShort[1], language, map, locations);
        return locale === 'en' ? `Heading to ${location}` : `前往${location}`;
    }
    const doing = text.match(/^(.+?)\s*正在\s*(.+?)进行(.+)$/) || text.match(/^正在\s*(.+?)进行(.+)$/);
    if (doing) {
        const hasSubject = doing.length === 4;
        const subject = hasSubject ? doing[1] : '';
        const location = localizeLocationReference(doing[hasSubject ? 2 : 1], language, map, locations);
        const interaction = localizeInteractionReference(doing[hasSubject ? 3 : 2], language, mapIdFor(map), interactions);
        if (locale === 'en') {
            return subject
                ? `${subject} is doing ${interaction} at ${location}`
                : `Doing ${interaction} at ${location}`;
        }
        return subject
            ? `${subject} 正在${location}进行${interaction}`
            : `正在${location}进行${interaction}`;
    }
    return ACTION_LABELS[text]?.[locale] || text;
}

export function localizeSystemEvent(
    raw: unknown,
    language: string | undefined,
    map: LocalizedMapLike,
    locations: LocalizedLocationLike[],
): string | undefined {
    if (raw === undefined || raw === null || raw === '') {
        return undefined;
    }
    const text = String(raw).trim();
    const locale = pickLocale(language);
    if (locale === 'zh') {
        return text;
    }

    const direct = text.match(/^(.+?)\s*给\s*(.+?)\s*发了私信。?$/);
    if (direct) {
        return `${direct[1]} sent a direct message to ${direct[2]}.`;
    }
    const group = text.match(/^(.+?)\s*在\s*(.+?)\s*发了消息。?$/);
    if (group) {
        return `${group[1]} posted in ${localizeGroupName(group[2], language)}.`;
    }
    const arrived = text.match(/^(.+?)\s*已到达\s*(.+?)。?$/);
    if (arrived) {
        return `${arrived[1]} arrived at ${localizeLocationReference(arrived[2], language, map, locations)}.`;
    }
    const heading = text.match(/^(.+?)\s*正在前往\s*(.+?)。?$/);
    if (heading) {
        return `${heading[1]} is heading to ${localizeLocationReference(heading[2], language, map, locations)}.`;
    }
    const mapArrival = text.match(/^智能体已到达\s*(.+?)。?$/) || text.match(/^智能体抵达\s*(.+?)。?$/);
    if (mapArrival) {
        return `Agents arrived at ${localizeLocationReference(mapArrival[1], language, map, locations)}.`;
    }
    return text;
}
