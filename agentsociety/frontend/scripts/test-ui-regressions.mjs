import assert from 'node:assert/strict';
import test from 'node:test';

import {
    displayStoredReplayText,
    getMapZoomBounds,
    shouldShowInitialReplayLoader,
    snapAxisToDevicePixels,
    snapZoomToTileGrid,
} from '../src/pages/PixelReplay/replayPure.ts';

const PLACEHOLDER = 'Stored message contains non-English content.';
const VILLE_WIDTH = 140 * 32;
const VILLE_HEIGHT = 100 * 32;

test('english replay keeps stored Chinese instead of the placeholder', () => {
    const stored = 'Jiuwen Mei 正在前往学校教室。';
    const shown = displayStoredReplayText(stored, 'en');
    assert.equal(shown, stored);
    assert.notEqual(shown, PLACEHOLDER);
    assert.equal(
        displayStoredReplayText('我会把当前情况整理清楚，并同步给需要知道的人。', 'en-US')
            .includes('non-English'),
        false,
    );
});

test('chinese ui returns the stored text unchanged', () => {
    const stored = 'Jiuwen Alice 正在公园和大家碰头';
    assert.equal(displayStoredReplayText(stored, 'zh'), stored);
});

test('default cover zoom lands on whole tile pixels and still covers the view', () => {
    const viewportWidth = 980;
    const viewportHeight = 872;
    const { fitZoom } = getMapZoomBounds(viewportWidth, viewportHeight, VILLE_WIDTH, VILLE_HEIGHT, 32);
    const cover = Math.max(viewportWidth / VILLE_WIDTH, viewportHeight / VILLE_HEIGHT);
    assert.ok(fitZoom + 1e-9 >= cover);
    assert.equal(Math.round(fitZoom * 32), fitZoom * 32);
    const scroll = snapAxisToDevicePixels(VILLE_WIDTH / 2 - viewportWidth / 2, fitZoom);
    assert.equal(Math.round(scroll * fitZoom), scroll * fitZoom);
});

test('wheel zoom stays on the tile grid inside the camera limits', () => {
    const zoom = snapZoomToTileGrid(0.3, 32, 0.2, 1.8);
    assert.equal(Math.round(zoom * 32), zoom * 32);
    assert.ok(zoom >= 0.2);
    assert.ok(zoom <= 1.8);
});

test('wheel zoom can return to the fitted zoom for a small map', () => {
    const { fitZoom, minZoom, maxZoom } = getMapZoomBounds(980, 872, 384, 384, 32);
    assert.equal(snapZoomToTileGrid(fitZoom + 0.06, 32, minZoom, maxZoom), fitZoom);

    const zoomedOut = snapZoomToTileGrid(fitZoom - 0.06, 32, minZoom, maxZoom);
    assert.ok(zoomedOut < fitZoom);
    assert.equal(snapZoomToTileGrid(zoomedOut + 0.06, 32, minZoom, maxZoom), fitZoom);
});

test('language refresh does not show the first-frame loader once a frame exists', () => {
    assert.equal(shouldShowInitialReplayLoader(true, false), true);
    assert.equal(shouldShowInitialReplayLoader(true, true), false);
    assert.equal(shouldShowInitialReplayLoader(false, true), false);
});
