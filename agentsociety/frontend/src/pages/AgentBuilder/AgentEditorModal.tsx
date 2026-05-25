import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Button,
    Collapse,
    Form,
    Input,
    InputNumber,
    Modal,
    Select,
    Space,
    Steps,
    Tag,
    Tooltip,
    Typography,
    Upload,
    message,
} from 'antd';
import type { FormInstance } from 'antd/es/form';
import {
    BgColorsOutlined,
    CheckCircleOutlined,
    ExperimentOutlined,
    PictureOutlined,
    ReloadOutlined,
    RobotOutlined,
    UploadOutlined,
    UserOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { fetchCustom } from '../../components/fetch';
import {
    jsonStringify,
    parseJsonObject,
    type AgentClassInfo,
    type AgentFormValues,
    type AgentRecord,
} from './agentEditor';
import './agentStudio.css';

const { Text, Paragraph } = Typography;

export type AgentStudioLocation = {
    id: string;
    name: string;
    aliases?: string[];
    localized?: Record<string, Record<string, unknown>>;
    interaction_ids?: string[];
};

export type AgentEditorSaveMeta = {
    initial_location?: string;
};

type AgentEditorModalProps = {
    open: boolean;
    editingAgentId: number | null;
    form: FormInstance<AgentFormValues>;
    initialValues?: AgentFormValues | null;
    agentClasses?: AgentClassInfo[];
    width?: number;
    minAgentId?: number;
    experimentContext?: Record<string, any>;
    mapId?: string;
    mapLocations?: AgentStudioLocation[];
    existingAgents?: AgentRecord[];
    initialLocation?: string;
    defaultInitialLocation?: string;
    onCancel: () => void;
    onSave: (agent: AgentRecord, meta?: AgentEditorSaveMeta) => void | Promise<void>;
};

type StudioOption = {
    id: string;
    label: string;
    description?: string;
};

type StudioGroup = {
    id: string;
    title: string;
    step: 'identity' | 'appearance' | 'personality' | 'daily';
    allow_custom: boolean;
    options: StudioOption[];
};

type StudioGenerateResponse = {
    groups: StudioGroup[];
    selected_choices: Record<string, string>;
    profile_patch: Record<string, any>;
    initial_location: string;
    warnings?: string[];
    character_asset?: CharacterAsset | null;
};

type CharacterAsset = {
    sprite_name: string;
    filename: string;
    image_url: string;
    frame_width: number;
    frame_height: number;
    source_photo_name?: string | null;
    generated_from_photo?: boolean;
    preview_data_url?: string | null;
    source?: Record<string, unknown>;
};

const defaultImageConfig = {
    image_provider: 'openai',
    image_api_base: 'https://api.openai.com/v1',
    image_model: 'gpt-image-1.5',
    image_api_key: '',
};

const allStepKeys = ['seed', 'identity', 'appearance', 'personality', 'daily', 'review'] as const;
type StepKey = typeof allStepKeys[number];
type ChoiceStepKey = Exclude<StepKey, 'seed' | 'review'>;

const stepIcons: Record<StepKey, React.ReactNode> = {
    seed: <RobotOutlined />,
    identity: <UserOutlined />,
    appearance: <BgColorsOutlined />,
    personality: <ExperimentOutlined />,
    daily: <ReloadOutlined />,
    review: <CheckCircleOutlined />,
};

const safeParseObject = (value: string, fallback: Record<string, any>) => {
    try {
        return parseJsonObject(value, 'json');
    } catch {
        return fallback;
    }
};

const asRecord = (value: unknown): Record<string, any> => (
    value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, any> : {}
);

const compactRecord = (value: Record<string, any>) => (
    Object.fromEntries(
        Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== '')
    )
);

const storableCharacterAsset = (asset?: CharacterAsset | null): CharacterAsset | null => {
    if (!asset) return null;
    const cleaned = compactRecord({
        sprite_name: asset.sprite_name,
        filename: asset.filename,
        image_url: asset.image_url,
        frame_width: asset.frame_width,
        frame_height: asset.frame_height,
        source_photo_name: asset.source_photo_name,
        generated_from_photo: asset.generated_from_photo,
        source: asset.source,
    }) as CharacterAsset;
    return cleaned.sprite_name && cleaned.filename ? cleaned : null;
};

const valueForOption = (group: StudioGroup, option: StudioOption) => (
    group.id === 'initial_location' ? option.id : option.label
);

const withPersistentChoice = (group: StudioGroup, value: string) => {
    const choice = value.trim();
    if (!choice) return group;
    const exists = group.options.some((option) => valueForOption(group, option) === choice);
    if (exists) return group;
    return {
        ...group,
        options: [{ id: `selected_${group.id}`, label: choice }, ...group.options],
    };
};

const labelForChoice = (group: StudioGroup | undefined, value: string) => {
    if (!group) return value;
    return group.options.find((option) => valueForOption(group, option) === value)?.label || value;
};

const firstLocationId = (locations: AgentStudioLocation[], fallback?: string) => (
    fallback || locations[0]?.id || 'park'
);

const shortText = (value: unknown, max = 180) => {
    const text = String(value || '').trim();
    return text.length > max ? `${text.slice(0, max)}...` : text;
};

const studioGroupMeta = (language: string): Record<string, { title: string; step: ChoiceStepKey; allow_custom: boolean }> => {
    const zh = !language.startsWith('en');
    return {
        identity_role: { title: zh ? '身份角色' : 'Role', step: 'identity', allow_custom: true },
        identity_function: { title: zh ? '剧情功能' : 'Scenario function', step: 'identity', allow_custom: true },
        appearance_form: { title: zh ? '形体' : 'Body', step: 'appearance', allow_custom: true },
        appearance_eyes: { title: zh ? '眼神' : 'Eyes', step: 'appearance', allow_custom: true },
        appearance_hair: { title: zh ? '发型' : 'Hair', step: 'appearance', allow_custom: true },
        appearance_style: { title: zh ? '服装风格' : 'Style', step: 'appearance', allow_custom: true },
        personality_core: { title: zh ? '核心性格' : 'Core personality', step: 'personality', allow_custom: true },
        personality_social: { title: zh ? '社交方式' : 'Social style', step: 'personality', allow_custom: true },
        personality_decision: { title: zh ? '决策倾向' : 'Decision style', step: 'personality', allow_custom: true },
        personality_mood: { title: zh ? '情绪底色' : 'Mood', step: 'personality', allow_custom: true },
        routine_goal: { title: zh ? '日常目标' : 'Daily goal', step: 'daily', allow_custom: true },
        routine_habit: { title: zh ? '日常习惯' : 'Daily habit', step: 'daily', allow_custom: true },
        relationship_style: { title: zh ? '关系习惯' : 'Relationship habit', step: 'daily', allow_custom: true },
        initial_location: { title: zh ? '初始位置' : 'Initial location', step: 'daily', allow_custom: false },
    };
};

const semanticGroupsForChoice = (groupId: string) => {
    if (groupId.startsWith('identity_')) return ['identity'];
    if (groupId.startsWith('personality_')) return ['personality'];
    if (groupId === 'routine_goal' || groupId === 'routine_habit' || groupId === 'initial_location') return ['routine'];
    if (groupId === 'relationship_style') return ['relationships'];
    return [];
};

const knownContextText: Record<string, Record<'en' | 'zh', string>> = {
    '上帝模式小镇 · 维尔普通工作日': {
        en: 'GOD Town · The Ville Ordinary Workday',
        zh: '上帝模式小镇 · 维尔普通工作日',
    },
    '晚春的一个工作日清晨 8:20。维尔小镇是一个 200 多人的小镇，10 位常住居民彼此熟识但不黏腻。天气晴朗微风，温度 18 摄氏度。镇上没有突发事件，是一段反映自然节奏的日常切片。': {
        en: 'A late-spring weekday morning at 8:20. The Ville is a town of just over 200 people, where 10 standing residents know one another well without being clingy. The weather is sunny with a light breeze at 18°C. Nothing unusual is happening in town; this is a natural slice of everyday life.',
        zh: '晚春的一个工作日清晨 8:20。维尔小镇是一个 200 多人的小镇，10 位常住居民彼此熟识但不黏腻。天气晴朗微风，温度 18 摄氏度。镇上没有突发事件，是一段反映自然节奏的日常切片。',
    },
    '北大校园日常观察': {
        en: 'PKU Campus Daily Observation',
        zh: '北大校园日常观察',
    },
    '2026-05-15，北京大学燕园。现在是一个普通周五上午，校园居民只知道自己的课程、科研、食堂、社团、宿舍和日常安排。后续公共事件只有在校内通知出现后才进入角色认知。': {
        en: 'May 15, 2026, Peking University Yanyuan. It is an ordinary Friday morning. Campus residents only know about their classes, research, canteens, clubs, dorms, and daily routines. Later public events enter character awareness only after an official campus notice appears.',
        zh: '2026-05-15，北京大学燕园。现在是一个普通周五上午，校园居民只知道自己的课程、科研、食堂、社团、宿舍和日常安排。后续公共事件只有在校内通知出现后才进入角色认知。',
    },
};

const localeKey = (language: string): 'en' | 'zh' => (language.startsWith('en') ? 'en' : 'zh');

const localizedContextValue = (
    context: Record<string, any>,
    field: 'title' | 'background' | 'world_setting',
    language: string,
) => {
    const locale = localeKey(language);
    const localized = context.localized?.[locale]?.[field];
    const raw = String(localized || context[field] || '').trim();
    return knownContextText[raw]?.[locale] || raw;
};

const absoluteAssetUrl = (url?: string) => {
    if (!url) return '';
    if (/^https?:\/\//i.test(url)) return url;
    const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
    return `${base}${url.startsWith('/') ? url : `/${url}`}`;
};

export const AgentEditorModal: React.FC<AgentEditorModalProps> = ({
    open,
    editingAgentId,
    form,
    initialValues,
    agentClasses = [],
    width = 980,
    minAgentId = 0,
    experimentContext = {},
    mapId = 'the_ville',
    mapLocations = [],
    existingAgents = [],
    initialLocation,
    defaultInitialLocation,
    onCancel,
    onSave,
}) => {
    const { t, i18n } = useTranslation();
    const copy = (key: string, values?: Record<string, unknown>) => t(`agentBuilder.studio.${key}`, values) as string;
    const [currentStep, setCurrentStep] = useState(0);
    const [agentId, setAgentId] = useState(1);
    const [agentType, setAgentType] = useState('JiuwenClawAgent');
    const [name, setName] = useState('');
    const [sourcePrompt, setSourcePrompt] = useState('');
    const [mbti, setMbti] = useState('');
    const [photoName, setPhotoName] = useState('');
    const [photoFile, setPhotoFile] = useState<File | null>(null);
    const [photoPreviewUrl, setPhotoPreviewUrl] = useState('');
    const [characterAsset, setCharacterAsset] = useState<CharacterAsset | null>(null);
    const [imageConfig, setImageConfig] = useState(defaultImageConfig);
    const [groups, setGroups] = useState<StudioGroup[]>([]);
    const [selectedChoices, setSelectedChoices] = useState<Record<string, string>>({});
    const [customChoices, setCustomChoices] = useState<Record<string, string>>({});
    const [initialLocationValue, setInitialLocationValue] = useState(firstLocationId(mapLocations, defaultInitialLocation));
    const [profileJsonText, setProfileJsonText] = useState('{}');
    const [kwargsJsonText, setKwargsJsonText] = useState('{}');
    const [customEditingGroup, setCustomEditingGroup] = useState<string | null>(null);
    const [customText, setCustomText] = useState('');
    const [generating, setGenerating] = useState(false);
    const [characterGenerating, setCharacterGenerating] = useState(false);
    const [generationRound, setGenerationRound] = useState(0);
    const [warnings, setWarnings] = useState<string[]>([]);
    const [autoGeneratePending, setAutoGeneratePending] = useState(false);
    const [touchedSemanticGroups, setTouchedSemanticGroups] = useState<Set<string>>(() => new Set());

    const profileForView = useMemo(() => safeParseObject(profileJsonText, {}), [profileJsonText]);
    const appearanceForView = asRecord(profileForView.appearance);
    const hasExistingSprite = Boolean(appearanceForView.character_sprite);
    const hasVisualReference = Boolean(photoFile || photoName || characterAsset || hasExistingSprite);
    const stepKeys = useMemo<StepKey[]>(() => (
        hasVisualReference ? allStepKeys.filter((key) => key !== 'appearance') : [...allStepKeys]
    ), [hasVisualReference]);
    const currentStepKey = stepKeys[currentStep] || 'review';

    const visibleGroups = useMemo(() => (
        groups.filter((group) => group.step === currentStepKey)
    ), [currentStepKey, groups]);

    const groupById = useMemo(() => {
        const map = new Map<string, StudioGroup>();
        groups.forEach((group) => map.set(group.id, group));
        return map;
    }, [groups]);

    const contextTitle = localizedContextValue(experimentContext, 'title', i18n.language) || copy('currentExperiment');
    const contextBackground = localizedContextValue(experimentContext, 'background', i18n.language)
        || localizedContextValue(experimentContext, 'world_setting', i18n.language);
    const selectedLocationLabel = labelForChoice(groupById.get('initial_location'), initialLocationValue);

    const buildLocalGroups = (
        nextSelected: Record<string, string>,
        nextCustom: Record<string, string>,
    ): StudioGroup[] => {
        const meta = studioGroupMeta(i18n.language);
        const locale = localeKey(i18n.language);
        return Object.entries(meta).map(([id, item]) => {
            if (id === 'initial_location') {
                return {
                    id,
                    title: item.title,
                    step: item.step,
                    allow_custom: false,
                    options: mapLocations.map((location) => ({
                        id: location.id,
                        label: String(location.localized?.[locale]?.name || location.name || location.id),
                    })),
                };
            }
            const values = [nextCustom[id], nextSelected[id]].filter((value): value is string => Boolean(value));
            const options = Array.from(new Set(values)).map((value, index) => ({
                id: `stored_${id}_${index}`,
                label: value,
            }));
            return {
                id,
                title: item.title,
                step: item.step,
                allow_custom: item.allow_custom,
                options,
            };
        });
    };

    const withStoredChoices = (
        sourceGroups: StudioGroup[],
        nextSelected: Record<string, string>,
        nextCustom: Record<string, string>,
    ) => {
        const baseGroups = sourceGroups.length ? sourceGroups : buildLocalGroups(nextSelected, nextCustom);
        return baseGroups.map((group) => {
            if (group.id === 'initial_location') {
                return group.options.length ? group : buildLocalGroups(nextSelected, nextCustom).find((item) => item.id === group.id) || group;
            }
            return [nextCustom[group.id], nextSelected[group.id]]
                .filter((value): value is string => Boolean(value))
                .reduce((current, value) => withPersistentChoice(current, value), group);
        });
    };

    const assetFromProfile = (profile: Record<string, any>): CharacterAsset | null => {
        const studio = asRecord(profile.agent_studio);
        const source = asRecord(studio.source);
        const existingAsset = studio.character_asset || source.character_asset || asRecord(profile.appearance).character_asset;
        if (existingAsset && typeof existingAsset === 'object' && typeof existingAsset.sprite_name === 'string') {
            return existingAsset as CharacterAsset;
        }
        const appearance = asRecord(profile.appearance);
        const spriteName = String(appearance.character_sprite || '').trim();
        if (!spriteName) return null;
        const filename = String(appearance.character_sprite_filename || `${spriteName}.png`);
        return {
            sprite_name: spriteName,
            filename,
            image_url: `/api/v1/god/setup/agent-studio/characters/${encodeURIComponent(mapId)}/${encodeURIComponent(filename)}`,
            frame_width: 32,
            frame_height: 32,
            source: asRecord(appearance.character_sprite_source),
        };
    };

    const buildStudioDraft = (
        profile: Record<string, any>,
        studio: Record<string, any>,
        nextInitialLocation?: string,
    ) => {
        const appearance = asRecord(profile.appearance);
        const personality = asRecord(profile.personality);
        const routine = asRecord(profile.routine);
        const selected = { ...asRecord(studio.selected_choices) } as Record<string, string>;
        const custom = { ...asRecord(studio.custom_choices) } as Record<string, string>;
        const legacyChoices: Record<string, unknown> = {
            identity_role: profile.role,
            identity_function: profile.scenario_role || profile.role,
            appearance_form: appearance.form,
            appearance_eyes: appearance.eyes,
            appearance_hair: appearance.hair,
            appearance_style: appearance.style,
            personality_core: personality.core || profile.persona,
            personality_social: personality.social,
            personality_decision: personality.decision,
            personality_mood: personality.mood,
            routine_goal: routine.goal || profile.goal,
            routine_habit: routine.habit || profile.daily_routine,
            relationship_style: routine.relationship_style || profile.relationships,
        };
        Object.entries(legacyChoices).forEach(([id, raw]) => {
            const value = String(raw || '').trim();
            if (!value) return;
            if (!selected[id]) selected[id] = value;
            if (!custom[id] && !asRecord(studio.selected_choices)[id]) custom[id] = value;
        });
        selected.initial_location = String(
            nextInitialLocation
            || selected.initial_location
            || routine.initial_location
            || firstLocationId(mapLocations, defaultInitialLocation)
        );
        const storedGroups = Array.isArray(studio.groups) ? studio.groups as StudioGroup[] : [];
        return {
            selected,
            custom,
            groups: withStoredChoices(storedGroups, selected, custom),
        };
    };

    const mergeProfilePatch = (
        currentProfile: Record<string, any>,
        patch: Record<string, any>,
        nextSelected: Record<string, string>,
        nextCustom: Record<string, string>,
        nextCharacterAsset: CharacterAsset | null = characterAsset,
        nextPhotoName = photoName,
        nextName = name,
    ) => {
        const patchAppearance = asRecord(patch.appearance);
        const storedCharacterAsset = storableCharacterAsset(nextCharacterAsset);
        const nextAppearance: Record<string, any> = {
            ...asRecord(currentProfile.appearance),
            ...patchAppearance,
        };
        if (storedCharacterAsset) {
            nextAppearance.character_asset = storedCharacterAsset;
            nextAppearance.character_sprite = storedCharacterAsset.sprite_name;
            nextAppearance.character_sprite_filename = storedCharacterAsset.filename;
            nextAppearance.character_sprite_source = storedCharacterAsset.source || {};
        }
        const currentStudio = asRecord(currentProfile.agent_studio);
        const patchStudio = asRecord(patch.agent_studio);
        const { groups: _currentGroups, ...currentStudioRest } = currentStudio;
        const { groups: _patchGroups, ...patchStudioRest } = patchStudio;
        const { appearance: _patchAppearance, agent_studio: _patchAgentStudio, ...patchRest } = patch;
        return {
            ...currentProfile,
            ...patchRest,
            appearance: nextAppearance,
            name: nextName || patch.name || currentProfile.name,
            scenario: patch.scenario || currentProfile.scenario || contextBackground,
            agent_studio: {
                version: 1,
                ...currentStudioRest,
                ...patchStudioRest,
                source: {
                    ...asRecord(currentStudio.source),
                    ...asRecord(patchStudio.source),
                    prompt: sourcePrompt,
                    mbti: mbti || undefined,
                    photo_name: nextPhotoName || undefined,
                    character_asset: storedCharacterAsset || undefined,
                },
                selected_choices: nextSelected,
                custom_choices: nextCustom,
                map_id: mapId,
                character_asset: storedCharacterAsset || undefined,
            },
        };
    };

    const applyProfilePatch = (
        patch: Record<string, any>,
        nextSelected: Record<string, string>,
        nextCustom: Record<string, string>,
        nextCharacterAsset: CharacterAsset | null = characterAsset,
        nextPhotoName = photoName,
        nextName = name,
    ) => {
        const currentProfile = safeParseObject(profileJsonText, {});
        setProfileJsonText(jsonStringify(mergeProfilePatch(
            currentProfile,
            patch,
            nextSelected,
            nextCustom,
            nextCharacterAsset,
            nextPhotoName,
            nextName,
        )));
    };

    const patchFromSelections = (
        nextSelected: Record<string, string>,
        nextCustom: Record<string, string>,
        nextGroups = groups,
        nextCharacterAsset: CharacterAsset | null = characterAsset,
        nextPhotoName = photoName,
        semanticScope?: 'all' | Set<string>,
    ) => {
        const label = (id: string) => labelForChoice(nextGroups.find((group) => group.id === id), nextSelected[id] || '');
        const role = label('identity_role') || 'participant';
        const functionLabel = label('identity_function') || role;
        const core = label('personality_core');
        const social = label('personality_social');
        const decision = label('personality_decision');
        const mood = label('personality_mood');
        const goal = label('routine_goal');
        const habit = label('routine_habit');
        const relation = label('relationship_style');
        const location = labelForChoice(nextGroups.find((group) => group.id === 'initial_location'), nextSelected.initial_location || initialLocationValue);
        const zh = !i18n.language.startsWith('en');
        const includeSemantic = (key: string) => semanticScope === 'all' || Boolean(semanticScope?.has(key));
        const storedCharacterAsset = storableCharacterAsset(nextCharacterAsset);
        const appearancePatch = compactRecord({
            ...(hasVisualReference ? {} : {
                form: label('appearance_form'),
                eyes: label('appearance_eyes'),
                hair: label('appearance_hair'),
                style: label('appearance_style'),
            }),
            photo_reference: nextPhotoName || undefined,
            character_asset: storedCharacterAsset || undefined,
            character_sprite: nextCharacterAsset?.sprite_name,
            character_sprite_filename: nextCharacterAsset?.filename,
            character_sprite_source: nextCharacterAsset?.source,
        });
        const patch: Record<string, any> = {
            name,
            mbti: mbti || undefined,
            appearance: appearancePatch,
            personality: compactRecord({ core, social, decision, mood }),
            routine: compactRecord({
                goal,
                habit,
                relationship_style: relation,
                initial_location: nextSelected.initial_location || initialLocationValue,
                initial_location_label: location,
            }),
            agent_studio: {
                version: 1,
                source: { prompt: sourcePrompt, mbti, photo_name: nextPhotoName, character_asset: storedCharacterAsset },
                selected_choices: nextSelected,
                custom_choices: nextCustom,
                map_id: mapId,
                character_asset: storedCharacterAsset,
            },
        };
        if (includeSemantic('identity')) {
            patch.role = role;
            patch.scenario_role = functionLabel;
        }
        if (includeSemantic('personality')) {
            const personaParts = zh
                ? [
                    core,
                    social,
                    decision ? `倾向于${decision}` : '',
                    mood ? `情绪底色是${mood}` : '',
                    sourcePrompt ? `设定种子：${sourcePrompt}` : '',
                ]
                : [
                    core,
                    social,
                    decision ? `tends toward ${decision}` : '',
                    mood ? `emotional tone: ${mood}` : '',
                    sourcePrompt ? `Seed: ${sourcePrompt}` : '',
                ];
            patch.persona = `${personaParts.filter(Boolean).join(zh ? '，' : '; ')}${zh ? '。' : '.'}`;
        }
        if (includeSemantic('routine')) {
            patch.goal = goal;
            const routineParts = zh
                ? [
                    habit,
                    location ? `常在${location}附近活动` : '',
                    goal ? `围绕“${goal}”安排日常` : '',
                ]
                : [
                    habit,
                    location ? `usually acts around ${location}` : '',
                    goal ? `organizes the day around "${goal}"` : '',
                ];
            patch.daily_routine = `${routineParts.filter(Boolean).join(zh ? '，' : '; ')}${zh ? '。' : '.'}`;
        }
        if (includeSemantic('relationships')) {
            patch.relationships = zh
                ? `关系习惯是${relation}，会根据当前实验背景和其他居民反应调整互动。`
                : `Relationship habit: ${relation}; adapts to the current scenario and other residents' reactions.`;
        }
        if (semanticScope === 'all') {
            patch.constraints = zh
                ? '只能使用当前地图已有地点行动；地图外概念会转译为当前地图内的行为。'
                : 'Use only locations available on the current map; off-map concepts are translated into behavior on this map.';
            patch.scenario = contextBackground;
        }
        return patch;
    };

    const requestGeneration = async (
        nextRound = generationRound,
        lockedChoices = selectedChoices,
        nextCustom = customChoices,
        rerollGroupId?: string,
    ) => {
        setGenerating(true);
        try {
            const response = await fetchCustom('/api/v1/god/setup/agent-studio/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    experiment_context: experimentContext,
                    map_id: mapId,
                    map_locations: mapLocations,
                    existing_agents: existingAgents,
                    language: i18n.language,
                    source: {
                        prompt: sourcePrompt,
                        mbti,
                        photo_name: photoName,
                        character_asset: storableCharacterAsset(characterAsset),
                        round: nextRound,
                        reroll_group: rerollGroupId,
                    },
                    locked_choices: lockedChoices,
                    custom_choices: nextCustom,
                }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json() as StudioGenerateResponse;
            const generatedGroups = payload.groups || [];
            const rerolledGroup = rerollGroupId ? generatedGroups.find((group) => group.id === rerollGroupId) : undefined;
            const rerolledDefault = rerolledGroup?.options?.[0]
                ? valueForOption(rerolledGroup, rerolledGroup.options[0])
                : '';
            const rerolledSelection = rerollGroupId
                ? selectedChoices[rerollGroupId] || payload.selected_choices?.[rerollGroupId] || rerolledDefault
                : '';
            const nextRerolledGroup = rerolledGroup && rerolledSelection
                ? withPersistentChoice(rerolledGroup, rerolledSelection)
                : rerolledGroup;
            const nextGroups = rerollGroupId
                ? groups.map((group) => (group.id === rerollGroupId ? nextRerolledGroup || group : group))
                : generatedGroups;
            const nextSelected = rerollGroupId
                ? {
                    ...selectedChoices,
                    [rerollGroupId]: rerolledSelection,
                }
                : {
                    ...payload.selected_choices,
                    ...Object.fromEntries(
                        Object.entries(lockedChoices).filter(([key, value]) => value && key !== 'initial_location')
                    ),
                };
            const nextInitialLocation = payload.initial_location || nextSelected.initial_location || firstLocationId(mapLocations, defaultInitialLocation);
            nextSelected.initial_location = nextInitialLocation;
            setGroups(nextGroups);
            setSelectedChoices(nextSelected);
            setInitialLocationValue(nextInitialLocation);
            setWarnings(payload.warnings || []);
            if (payload.character_asset) {
                setCharacterAsset(payload.character_asset);
            }
            const generatedName = String(payload.profile_patch?.name || '').trim();
            const shouldAdoptName = !editingAgentId || !name || /^Agent[_\s]\d+$|^Jiuwen Agent \d+$/i.test(name);
            const nextName = shouldAdoptName && generatedName ? generatedName : name;
            if (nextName !== name) {
                setName(nextName);
            }
            const semanticScope = rerollGroupId ? new Set(semanticGroupsForChoice(rerollGroupId)) : 'all';
            const nextPatch = rerollGroupId
                ? patchFromSelections(
                    nextSelected,
                    nextCustom,
                    nextGroups,
                    payload.character_asset || characterAsset,
                    photoName,
                    semanticScope,
                )
                : (payload.profile_patch || {});
            applyProfilePatch(
                nextPatch,
                nextSelected,
                nextCustom,
                payload.character_asset || characterAsset,
                photoName,
                nextName,
            );
            message.success(copy('generated'));
        } catch (error) {
            message.error(copy('generateFailed', { error: error instanceof Error ? error.message : String(error) }));
        } finally {
            setGenerating(false);
        }
    };

    useEffect(() => {
        if (!open) return;
        const values = initialValues || form.getFieldsValue();
        const profile = safeParseObject(values.profile_json || '{}', {});
        const kwargs = safeParseObject(values.kwargs_json || '{}', {});
        const studio = asRecord(profile.agent_studio);
        const isNewAgent = editingAgentId === null;
        const draft = isNewAgent
            ? {
                selected: { initial_location: initialLocation || firstLocationId(mapLocations, defaultInitialLocation) },
                custom: {},
                groups: [] as StudioGroup[],
            }
            : buildStudioDraft(profile, studio, initialLocation);
        const nextCharacterAsset = assetFromProfile(profile);
        const nextName = String(values.name || profile.name || `Agent ${values.agent_id || 1}`);
        setCurrentStep(0);
        setAgentId(Number(values.agent_id || minAgentId || 1));
        setAgentType(String(values.agent_type || 'JiuwenClawAgent'));
        setName(nextName);
        setSourcePrompt(String(asRecord(studio.source).prompt || ''));
        setMbti(String(profile.mbti || asRecord(studio.source).mbti || ''));
        setPhotoName(String(asRecord(studio.source).photo_name || asRecord(profile.appearance).photo_reference || ''));
        setPhotoFile(null);
        setPhotoPreviewUrl('');
        setCharacterAsset(nextCharacterAsset);
        setImageConfig(defaultImageConfig);
        setSelectedChoices(draft.selected);
        setCustomChoices(draft.custom);
        setGroups(draft.groups);
        setInitialLocationValue(draft.selected.initial_location);
        setProfileJsonText(jsonStringify(profile));
        setKwargsJsonText(jsonStringify(kwargs));
        setWarnings([]);
        setTouchedSemanticGroups(new Set());
        setAutoGeneratePending(isNewAgent && !draft.groups.length);
        // Values are intentionally loaded when the modal opens.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, editingAgentId, initialValues]);

    useEffect(() => {
        setCurrentStep((value) => Math.min(value, stepKeys.length - 1));
    }, [stepKeys.length]);

    useEffect(() => {
        if (!photoPreviewUrl) return undefined;
        return () => URL.revokeObjectURL(photoPreviewUrl);
    }, [photoPreviewUrl]);

    useEffect(() => {
        if (!open || !autoGeneratePending) return;
        setAutoGeneratePending(false);
        void requestGeneration(0, selectedChoices, customChoices);
        // Wait for the modal-open initialization state to settle before auto-generating.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, autoGeneratePending]);

    const selectCharacterPhoto = (file: File) => {
        setPhotoName(file.name);
        setPhotoFile(file);
        setPhotoPreviewUrl(URL.createObjectURL(file));
        setCharacterAsset(null);
    };

    const requestCharacterGeneration = async () => {
        if (!photoFile) {
            message.warning(copy('spritePhotoRequired'));
            return;
        }
        setCharacterGenerating(true);
        try {
            const data = new FormData();
            data.append('file', photoFile);
            data.append('map_id', mapId);
            data.append('agent_id', String(agentId));
            data.append('agent_name', name || `Agent ${agentId}`);
            data.append('prompt', sourcePrompt);
            data.append('mbti', mbti);
            data.append('appearance_json', JSON.stringify({}));
            data.append('image_api_key', imageConfig.image_api_key);
            data.append('image_api_base', imageConfig.image_api_base);
            data.append('image_model', imageConfig.image_model);
            data.append('image_provider', imageConfig.image_provider);
            const response = await fetchCustom('/api/v1/god/setup/agent-studio/character', {
                method: 'POST',
                body: data,
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const nextAsset = await response.json() as CharacterAsset;
            setCharacterAsset(nextAsset);
            const nextPatch = patchFromSelections(selectedChoices, customChoices, groups, nextAsset, photoFile.name);
            applyProfilePatch(nextPatch, selectedChoices, customChoices, nextAsset, photoFile.name);
            setImageConfig((current) => ({ ...current, image_api_key: '' }));
            message.success(copy('characterGenerated'));
        } catch (error) {
            message.error(copy('characterFailed', { error: error instanceof Error ? error.message : String(error) }));
        } finally {
            setCharacterGenerating(false);
        }
    };

    const selectChoice = (group: StudioGroup, value: string) => {
        const nextSelected = { ...selectedChoices, [group.id]: value };
        const nextInitial = group.id === 'initial_location' ? value : initialLocationValue;
        const semanticScope = new Set(semanticGroupsForChoice(group.id));
        setTouchedSemanticGroups((current) => new Set([...current, ...semanticScope]));
        setSelectedChoices(nextSelected);
        if (group.id === 'initial_location') {
            setInitialLocationValue(value);
        }
        applyProfilePatch(
            patchFromSelections({ ...nextSelected, initial_location: nextInitial }, customChoices, groups, characterAsset, photoName, semanticScope),
            { ...nextSelected, initial_location: nextInitial },
            customChoices,
        );
    };

    const saveCustomChoice = (group: StudioGroup) => {
        const value = customText.trim();
        if (!value) return;
        const nextCustom = { ...customChoices, [group.id]: value };
        const nextSelected = { ...selectedChoices, [group.id]: value };
        const semanticScope = new Set(semanticGroupsForChoice(group.id));
        setTouchedSemanticGroups((current) => new Set([...current, ...semanticScope]));
        const nextGroups = groups.map((item) => {
            if (item.id !== group.id) return item;
            const exists = item.options.some((option) => option.label === value);
            return exists ? item : {
                ...item,
                options: [{ id: `custom_${group.id}`, label: value }, ...item.options],
            };
        });
        setCustomChoices(nextCustom);
        setSelectedChoices(nextSelected);
        setGroups(nextGroups);
        setCustomEditingGroup(null);
        setCustomText('');
        applyProfilePatch(
            patchFromSelections(nextSelected, nextCustom, nextGroups, characterAsset, photoName, semanticScope),
            nextSelected,
            nextCustom,
        );
    };

    const rerollOptions = async (groupId?: string) => {
        const nextRound = generationRound + 1;
        setGenerationRound(nextRound);
        const lockedChoices = groupId
            ? Object.fromEntries(Object.entries(selectedChoices).filter(([key]) => key !== groupId))
            : selectedChoices;
        await requestGeneration(nextRound, lockedChoices, customChoices, groupId);
    };

    const submitAgent = async () => {
        if (photoFile && !characterAsset) {
            message.warning(copy('spriteRequiredBeforeSave'));
            return;
        }
        try {
            const baseProfile = parseJsonObject(profileJsonText, 'profile_json');
            const nextSelected = { ...selectedChoices, initial_location: initialLocationValue };
            const profile = mergeProfilePatch(
                baseProfile,
                patchFromSelections(nextSelected, customChoices, groups, characterAsset, photoName, touchedSemanticGroups),
                nextSelected,
                customChoices,
                characterAsset,
                photoName,
                name,
            );
            const extraKwargs = parseJsonObject(kwargsJsonText, 'kwargs_json');
            const agent: AgentRecord = {
                agent_id: Number(agentId),
                agent_type: agentType,
                kwargs: {
                    ...extraKwargs,
                    id: Number(agentId),
                    name,
                    profile,
                },
            };
            await onSave(agent, { initial_location: initialLocationValue });
        } catch (error) {
            message.error(error instanceof Error ? error.message : t('agentBuilder.editor.invalidForm'));
        }
    };

    const renderCharacterPreview = (compact = false) => {
        const role = labelForChoice(groupById.get('identity_role'), selectedChoices.identity_role || '');
        const core = labelForChoice(groupById.get('personality_core'), selectedChoices.personality_core || '');
        const form = labelForChoice(groupById.get('appearance_form'), selectedChoices.appearance_form || '');
        return (
            <div className={`agent-studio-preview-card ${compact ? 'compact' : ''}`}>
                <div className="agent-studio-preview-header">
                    <Space size={6}>
                        <PictureOutlined />
                        <Text strong>{copy('previewTitle')}</Text>
                    </Space>
                    {characterGenerating && <Tag color="blue">{copy('generatingCharacter')}</Tag>}
                </div>
                <div className="agent-studio-preview-body">
                    {characterAsset ? (
                        <img
                            className="agent-studio-sprite-preview"
                            src={characterAsset.preview_data_url || absoluteAssetUrl(characterAsset.image_url)}
                            alt={copy('characterAlt')}
                        />
                    ) : (
                        <div className="agent-studio-preview-placeholder" aria-label={copy('characterAlt')}>
                            <span className="agent-studio-preview-head" />
                            <span className="agent-studio-preview-body-shape" />
                            <span className="agent-studio-preview-leg left" />
                            <span className="agent-studio-preview-leg right" />
                        </div>
                    )}
                    <div className="agent-studio-preview-copy">
                        <Text strong>{name || copy('unnamed')}</Text>
                        <Space wrap size={[6, 6]}>
                            {role && <Tag color="blue">{role}</Tag>}
                            {core && <Tag color="purple">{core}</Tag>}
                            {form && <Tag>{form}</Tag>}
                            {selectedLocationLabel && <Tag color="green">{selectedLocationLabel}</Tag>}
                        </Space>
                        <Text type="secondary">
                            {characterAsset ? copy('spriteReady', { file: characterAsset.filename }) : copy('previewEmpty')}
                        </Text>
                    </div>
                </div>
            </div>
        );
    };

    const renderSeedStep = () => (
        <div className="agent-studio-grid">
            <div className="agent-studio-main">
                <div className="agent-studio-field-row">
                    <Form.Item label={t('agentBuilder.fields.agentId')} required>
                        <InputNumber
                            min={minAgentId}
                            value={agentId}
                            onChange={(value) => {
                                setAgentId(Number(value || minAgentId || 1));
                                if (photoFile) setCharacterAsset(null);
                            }}
                            style={{ width: '100%' }}
                        />
                    </Form.Item>
                    <Form.Item label={t('agentBuilder.fields.agentType')} required>
                        {agentClasses.length ? (
                            <Select
                                value={agentType}
                                onChange={setAgentType}
                                showSearch
                                options={agentClasses.map((item) => ({
                                    value: item.type,
                                    label: `${item.type}${item.is_custom ? ` (${t('agentBuilder.editor.customClassSuffix')})` : ''}`,
                                }))}
                            />
                        ) : (
                            <Input value={agentType} onChange={(event) => setAgentType(event.target.value)} />
                        )}
                    </Form.Item>
                    <Form.Item label={t('agentBuilder.fields.name')} required>
                        <Input
                            value={name}
                            onChange={(event) => {
                                setName(event.target.value);
                                if (photoFile) setCharacterAsset(null);
                            }}
                            placeholder={copy('namePlaceholder')}
                        />
                    </Form.Item>
                </div>
                <Form.Item label={copy('seedPrompt')}>
                    <Input.TextArea
                        rows={4}
                        value={sourcePrompt}
                        onChange={(event) => setSourcePrompt(event.target.value)}
                        placeholder={copy('seedPlaceholder')}
                    />
                </Form.Item>
                <div className="agent-studio-field-row compact">
                    <Form.Item label="MBTI">
                        <Input value={mbti} onChange={(event) => setMbti(event.target.value.toUpperCase())} placeholder="INTP / ENFJ" maxLength={4} />
                    </Form.Item>
                    <Form.Item label={copy('photoReference')}>
                        <Upload
                            beforeUpload={(file) => {
                                selectCharacterPhoto(file);
                                return false;
                            }}
                            showUploadList={false}
                            maxCount={1}
                            accept="image/*"
                        >
                            <Tooltip title={photoName || undefined}>
                                <Button className="agent-studio-photo-button" icon={<UploadOutlined />}>
                                    <span className="agent-studio-photo-name">{photoName || copy('choosePhoto')}</span>
                                </Button>
                            </Tooltip>
                        </Upload>
                    </Form.Item>
                    <Form.Item label=" " colon={false}>
                        <Button type="primary" icon={<RobotOutlined />} loading={generating} onClick={() => requestGeneration()}>
                            {copy('generate')}
                        </Button>
                    </Form.Item>
                </div>
                {photoFile && (
                    <div className="agent-studio-sprite-panel">
                        <div className="agent-studio-preview-row">
                            {photoPreviewUrl && (
                                <div className="agent-studio-preview-box">
                                    <Text type="secondary">{copy('referencePreview')}</Text>
                                    <img src={photoPreviewUrl} alt={photoName} />
                                </div>
                            )}
                            <div className="agent-studio-preview-box sprite">
                                <Text type="secondary">{copy('spritePreview')}</Text>
                                {characterAsset ? (
                                    <img
                                        src={characterAsset.preview_data_url || absoluteAssetUrl(characterAsset.image_url)}
                                        alt={characterAsset.sprite_name}
                                    />
                                ) : (
                                    <div className="agent-studio-preview-empty">{copy('spritePending')}</div>
                                )}
                            </div>
                        </div>
                        <div className="agent-studio-field-row image-config">
                            <Form.Item label="IMAGE_GEN_PROVIDER">
                                <Select
                                    value={imageConfig.image_provider}
                                    onChange={(value) => setImageConfig((current) => ({ ...current, image_provider: value }))}
                                    options={[{ value: 'openai', label: 'openai' }]}
                                />
                            </Form.Item>
                            <Form.Item label="IMAGE_GEN_API_BASE">
                                <Input
                                    value={imageConfig.image_api_base}
                                    onChange={(event) => setImageConfig((current) => ({ ...current, image_api_base: event.target.value }))}
                                />
                            </Form.Item>
                            <Form.Item label="IMAGE_GEN_MODEL_NAME">
                                <Input
                                    value={imageConfig.image_model}
                                    onChange={(event) => setImageConfig((current) => ({ ...current, image_model: event.target.value }))}
                                />
                            </Form.Item>
                            <Form.Item label="IMAGE_GEN_API_KEY">
                                <Input.Password
                                    value={imageConfig.image_api_key}
                                    onChange={(event) => setImageConfig((current) => ({ ...current, image_api_key: event.target.value }))}
                                    autoComplete="off"
                                />
                            </Form.Item>
                        </div>
                        <Space wrap>
                            <Button type="primary" icon={<RobotOutlined />} loading={characterGenerating} onClick={requestCharacterGeneration}>
                                {copy('generateSprite')}
                            </Button>
                            {characterAsset && <Tag color="green">{characterAsset.sprite_name}</Tag>}
                        </Space>
                    </div>
                )}
            </div>
            <div className="agent-studio-side">
                <Text strong>{copy('worldContext')}</Text>
                <Paragraph className="agent-studio-context-title">{contextTitle}</Paragraph>
                <Paragraph type="secondary">{shortText(contextBackground || copy('noContext'))}</Paragraph>
                <Space wrap>
                    <Tag color="blue">{mapId}</Tag>
                    <Tag>{copy('locationCount', { count: mapLocations.length })}</Tag>
                </Space>
                {renderCharacterPreview(true)}
                {warnings.map((warning) => (
                    <Alert key={warning} type="info" showIcon message={warning} style={{ marginTop: 10 }} />
                ))}
            </div>
        </div>
    );

    const renderChoiceGroup = (group: StudioGroup) => {
        const selected = selectedChoices[group.id] || '';
        return (
            <section key={group.id} className="agent-studio-choice-group">
                <div className="agent-studio-choice-header">
                    <Text strong>{group.title}</Text>
                    <Tooltip title={copy('rerollTooltip')}>
                        <Button size="small" icon={<ReloadOutlined />} onClick={() => rerollOptions(group.id)} loading={generating} />
                    </Tooltip>
                </div>
                <div className="agent-studio-choice-list">
                    {group.options.map((option) => {
                        const value = valueForOption(group, option);
                        return (
                            <button
                                key={`${group.id}-${option.id}-${option.label}`}
                                type="button"
                                className={`agent-studio-choice ${selected === value ? 'selected' : ''}`}
                                onClick={() => selectChoice(group, value)}
                                title={option.label}
                            >
                                <span>{shortText(option.label, 80)}</span>
                                {option.description && <small>{option.description}</small>}
                            </button>
                        );
                    })}
                    {group.allow_custom && (
                        customEditingGroup === group.id ? (
                            <div className="agent-studio-custom">
                                <Input.TextArea
                                    size="small"
                                    value={customText}
                                    onChange={(event) => setCustomText(event.target.value)}
                                    onPressEnter={() => saveCustomChoice(group)}
                                    placeholder={copy('customPlaceholder')}
                                    maxLength={1200}
                                    autoSize={{ minRows: 1, maxRows: 5 }}
                                />
                                <Button size="small" type="primary" onClick={() => saveCustomChoice(group)}>{copy('useCustom')}</Button>
                            </div>
                        ) : (
                            <button
                                type="button"
                                className={`agent-studio-choice custom ${customChoices[group.id] && selected === customChoices[group.id] ? 'selected' : ''}`}
                                onClick={() => {
                                    setCustomEditingGroup(group.id);
                                    setCustomText(customChoices[group.id] || '');
                                }}
                            >
                                <span>{shortText(customChoices[group.id] || copy('customChoice'), 80)}</span>
                            </button>
                        )
                    )}
                </div>
            </section>
        );
    };

    const renderChoiceStep = () => (
        <>
            <div className="agent-studio-stepbar">
                <Text type="secondary">{copy('pickHint')}</Text>
                <Button icon={<ReloadOutlined />} onClick={() => rerollOptions()} loading={generating}>{copy('reroll')}</Button>
            </div>
            <div className="agent-studio-choice-grid">
                {visibleGroups.map(renderChoiceGroup)}
            </div>
        </>
    );

    const renderReviewStep = () => (
        <div className="agent-studio-review">
            <div className="agent-studio-review-grid">
                {renderCharacterPreview()}
                <div className="agent-studio-review-summary">
                    <div>
                        <Text strong>{name || copy('unnamed')}</Text>
                        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                            {shortText(safeParseObject(profileJsonText, {}).persona || copy('noPreviewPersona'), 180)}
                        </Paragraph>
                    </div>
                    <Space wrap>
                        <Tag color="blue">{labelForChoice(groupById.get('identity_role'), selectedChoices.identity_role || '')}</Tag>
                        <Tag color="purple">{labelForChoice(groupById.get('personality_core'), selectedChoices.personality_core || '')}</Tag>
                        <Tag color="green">{selectedLocationLabel}</Tag>
                    </Space>
                </div>
            </div>
            <Collapse
                ghost
                items={[
                    {
                        key: 'json',
                        label: copy('advancedJson'),
                        children: (
                            <Space direction="vertical" style={{ width: '100%' }}>
                                <Form.Item label={t('agentBuilder.fields.profileJson')}>
                                    <Input.TextArea rows={9} value={profileJsonText} onChange={(event) => setProfileJsonText(event.target.value)} spellCheck={false} />
                                </Form.Item>
                                <Form.Item label={t('agentBuilder.fields.extraKwargsJson')}>
                                    <Input.TextArea rows={6} value={kwargsJsonText} onChange={(event) => setKwargsJsonText(event.target.value)} spellCheck={false} />
                                </Form.Item>
                            </Space>
                        ),
                    },
                ]}
            />
        </div>
    );

    const stepItems = stepKeys.map((key) => ({
        title: copy(`steps.${key}`),
        icon: stepIcons[key],
    }));

    const content = currentStep === 0
        ? renderSeedStep()
        : currentStep === stepKeys.length - 1
            ? renderReviewStep()
            : renderChoiceStep();
    const saveDisabled = Boolean(photoFile && !characterAsset) || characterGenerating;

    return (
        <Modal
            title={editingAgentId === null ? t('agentBuilder.editor.addTitle') : t('agentBuilder.editor.editTitle')}
            open={open}
            onCancel={onCancel}
            width={width}
            destroyOnHidden
            forceRender
            footer={[
                <Button key="cancel" onClick={onCancel}>{t('agentBuilder.actions.cancel')}</Button>,
                <Button key="back" disabled={currentStep === 0} onClick={() => setCurrentStep((value) => Math.max(0, value - 1))}>{copy('back')}</Button>,
                currentStep < stepKeys.length - 1 ? (
                    <Button key="next" type="primary" onClick={() => setCurrentStep((value) => Math.min(stepKeys.length - 1, value + 1))}>{copy('next')}</Button>
                ) : (
                    <Button key="save" type="primary" disabled={saveDisabled} onClick={submitAgent}>{copy('saveAgent')}</Button>
                ),
            ]}
        >
            <div className="agent-studio">
                <Steps className="agent-studio-steps" current={currentStep} items={stepItems} size="small" />
                {content}
            </div>
        </Modal>
    );
};
