// Pure helpers for the control-room regressions. No Phaser or React imports.

export const STORED_REPLAY_TEXT_EN: Record<string, string> = {
    'Jiuwen Alice 正在公园和大家碰头':
        'Jiuwen Alice is meeting everyone in Johnson Park.',
    'Jiuwen Charlie 正在学校进行课后答疑':
        'Jiuwen Charlie is holding office hours in the school classroom.',
    'Jiuwen Hana 正在家里做饭': 'Jiuwen Hana is cooking at home.',
    'Jiuwen Mei 正在市场店铺值班':
        'Jiuwen Mei is working a shop shift at The Willows Market.',
    前往哈维橡树供给店: 'Heading to Harvey Oak Supply Store.',
    前往学校教室: 'Heading to the school classroom.',
    前往家: 'Heading home.',
    前往柳树市场: 'Heading to The Willows Market.',
    前往约翰逊公园: 'Heading to Johnson Park.',
    'Jiuwen Bob 正在前往哈维橡树供给店。':
        'Jiuwen Bob is heading to Harvey Oak Supply Store.',
    '我会把当前情况整理清楚，并同步给需要知道的人。':
        'I will organize the current situation clearly and update the people who need to know.',
    '我先把摊位收拾好，再接待顾客。': 'I will tidy the stall first, then help customers.',
    '我用年轻人听得进去的方式聊。': 'I will talk in a way younger people can actually hear.',
    'Jiuwen Alice 在公园说：执行社区协调':
        'Jiuwen Alice says in Johnson Park: coordinating the community.',
};

export function translateKnownStoredReplayText(value: unknown, language: string): string | undefined {
    const text = String(value || '').trim();
    if (!language?.startsWith('en') || !text) {
        return undefined;
    }
    return STORED_REPLAY_TEXT_EN[text];
}

// Known phrases can be translated. Any other stored text, including Chinese, is shown as stored.
export function displayStoredReplayText(value: unknown, language: string): string {
    const text = String(value ?? '').trim();
    if (!text) {
        return '';
    }
    if (!language?.startsWith('en')) {
        return text;
    }
    return STORED_REPLAY_TEXT_EN[text] ?? text;
}

export function crispCoverZoom(
    viewportWidth: number,
    viewportHeight: number,
    mapWidth: number,
    mapHeight: number,
    tileSize: number,
): number {
    if (viewportWidth <= 0 || viewportHeight <= 0 || mapWidth <= 0 || mapHeight <= 0) {
        return 1;
    }
    const cover = Math.max(viewportWidth / mapWidth, viewportHeight / mapHeight);
    const safeTile = Math.max(1, tileSize);
    const steps = Math.max(1, Math.ceil(cover * safeTile - 1e-9));
    return steps / safeTile;
}

export function snapZoomToTileGrid(
    zoom: number,
    tileSize: number,
    minZoom: number,
    maxZoom: number,
): number {
    const safeTile = Math.max(1, tileSize);
    const minSteps = Math.max(1, Math.ceil(minZoom * safeTile - 1e-9));
    const maxSteps = Math.max(minSteps, Math.floor(maxZoom * safeTile + 1e-9));
    const steps = Math.min(maxSteps, Math.max(minSteps, Math.round(zoom * safeTile)));
    return steps / safeTile;
}

// Cover zoom snapped onto whole tile pixels. The upper bound can grow by less than one
// tile so a later clamp cannot push the default view back onto a fractional scale.
export function fitZoomOnTileGrid(
    viewportWidth: number,
    viewportHeight: number,
    mapWidth: number,
    mapHeight: number,
    tileSize: number,
    minZoom: number,
    maxZoom: number,
): number {
    const crisp = crispCoverZoom(viewportWidth, viewportHeight, mapWidth, mapHeight, tileSize);
    return snapZoomToTileGrid(crisp, tileSize, minZoom, Math.max(maxZoom, crisp));
}

export function snapAxisToDevicePixels(scroll: number, zoom: number): number {
    const safeZoom = Math.max(zoom, 0.0001);
    return Math.round(scroll * safeZoom) / safeZoom;
}

// The first-frame loader replaces the canvas. Once a frame exists, keep that canvas mounted.
export function shouldShowInitialReplayLoader(loading: boolean, hasFrame: boolean): boolean {
    return loading && !hasFrame;
}
