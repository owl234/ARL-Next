const test = require('node:test');
const assert = require('node:assert/strict');

const {
    BrowserLifecycleManager,
    closeWithTimeout,
    killBrowserProcess,
    parsePositiveInt,
    takeScreenshot,
} = require('../app/tools/puppeteer_server');

function makeFakeBrowser(id, events, { closeDelayMs = 0, hangClose = false } = {}) {
    let connected = true;
    return {
        id,
        isConnected: () => connected,
        process: () => ({ pid: 10000 + id }),
        close: () => {
            events.push(`close_start:${id}`);
            if (hangClose) {
                return new Promise(() => {});
            }
            return new Promise((resolve) => {
                setTimeout(() => {
                    connected = false;
                    events.push(`close_done:${id}`);
                    resolve();
                }, closeDelayMs);
            });
        },
    };
}

test('parsePositiveInt parses valid bounds and falls back cleanly', () => {
    assert.equal(parsePositiveInt('100', 200), 100);
    assert.equal(parsePositiveInt(' 250 ', 200), 250);
    assert.equal(parsePositiveInt('0', 200), 200);
    assert.equal(parsePositiveInt('-5', 200), 200);
    assert.equal(parsePositiveInt('abc', 200), 200);
    assert.equal(parsePositiveInt(undefined, 200), 200);
    assert.equal(parsePositiveInt('999999', 200, 1, 10000), 10000);
});

test('killBrowserProcess tries process group kill first and falls back to single pid', () => {
    const calls = [];
    killBrowserProcess({ pid: 4321 }, (pid, sig) => {
        calls.push([pid, sig]);
    });
    assert.deepEqual(calls, [[-4321, 'SIGKILL']]);

    const fallbackCalls = [];
    killBrowserProcess({ pid: 4321 }, (pid, sig) => {
        fallbackCalls.push([pid, sig]);
        if (pid < 0) throw new Error('ESRCH');
    });
    assert.deepEqual(fallbackCalls, [[-4321, 'SIGKILL'], [4321, 'SIGKILL']]);
});

test('serial rotation drains active task and destroys old browser BEFORE launching new browser', async () => {
    const events = [];
    let seq = 0;
    const manager = new BrowserLifecycleManager({
        maxRequests: 2,
        drainTimeoutMs: 500,
        closeTimeoutMs: 200,
        killFn: (pid, sig) => events.push(`kill:${pid}:${sig}`),
        launchFn: async () => {
            const id = ++seq;
            events.push(`launch:${id}`);
            return makeFakeBrowser(id, events, { closeDelayMs: 20 });
        },
    });

    const w1 = await manager.acquireActiveBrowser();
    const w2 = await manager.acquireActiveBrowser();
    assert.equal(w1, w2);
    assert.equal(w1.browser.id, 1);

    // 模拟第 2 次请求达到轮转上限，此时仍有 1 个在途任务 (w2)
    manager.recordRequest();
    manager.recordRequest();
    w1.releaseTask();

    const rotPromise = manager.maybeRotate();
    // 轮转期间并发进来的新请求必须等待旧实例排空+销毁+新实例启动，绝不附着到旧实例
    const nextAcquirePromise = manager.acquireActiveBrowser();

    await new Promise((r) => setTimeout(r, 30));
    // 旧实例尚未排空，不得提前启动第 2 个 Chromium（规避双实例内存峰值）
    assert.equal(seq, 1);

    // 释放最后一个在途任务，触发旧实例关闭与新实例启动
    w2.releaseTask();
    await rotPromise;

    const w3 = await nextAcquirePromise;
    assert.equal(w3.browser.id, 2);
    w3.releaseTask();

    const closeDoneIdx = events.indexOf('close_done:1');
    const killIdx = events.indexOf('kill:-10001:SIGKILL');
    const launch2Idx = events.indexOf('launch:2');
    assert.ok(closeDoneIdx !== -1 && killIdx !== -1 && launch2Idx !== -1, `events=${events}`);
    assert.ok(closeDoneIdx < launch2Idx, `old browser must finish closing before new launch: ${events}`);
    assert.ok(killIdx < launch2Idx, `old browser process group must be killed before new launch: ${events}`);
});

test('serial rotation force-destroys stuck browser on drain timeout and hung close()', async () => {
    const events = [];
    let seq = 0;
    const manager = new BrowserLifecycleManager({
        maxRequests: 1,
        drainTimeoutMs: 60,
        closeTimeoutMs: 60,
        killFn: (pid, sig) => events.push(`kill:${pid}:${sig}`),
        launchFn: async () => {
            const id = ++seq;
            events.push(`launch:${id}`);
            return makeFakeBrowser(id, events, { hangClose: id === 1 });
        },
    });

    // 模拟 1 个永远不 releaseTask 的卡死请求 + 1 个触发轮转的请求
    const stuck = await manager.acquireActiveBrowser();
    assert.equal(stuck.browser.id, 1);
    manager.recordRequest();

    const t0 = Date.now();
    await manager.maybeRotate();
    const elapsed = Date.now() - t0;

    assert.ok(elapsed < 1000, `rotation hung too long: ${elapsed}ms`);
    assert.ok(events.includes('kill:-10001:SIGKILL'));
    assert.ok(events.includes('launch:2'));
    assert.equal(manager.currentWrapper.browser.id, 2);
});

test('takeScreenshot never hangs semaphore when page.close() and context.close() freeze on timeout', async () => {
    const hungPage = {
        setUserAgent: async () => {},
        evaluateOnNewDocument: async () => {},
        on: () => {},
        setRequestInterception: async () => {},
        setViewport: async () => {},
        goto: () => new Promise(() => {}),
        close: () => new Promise(() => {}),
    };
    const hungContext = {
        newPage: async () => hungPage,
        close: () => new Promise(() => {}),
    };
    const fakeWrapper = {
        browser: {
            createIncognitoBrowserContext: async () => hungContext,
        },
    };

    const t0 = Date.now();
    const res = await takeScreenshot('https://example.com', fakeWrapper, '', {
        hardTimeoutMs: 50,
        closeTimeoutMs: 50,
    });
    const elapsed = Date.now() - t0;

    assert.deepEqual(res, { url: 'https://example.com', base64: null });
    assert.ok(elapsed < 600, `takeScreenshot hung on frozen close(): ${elapsed}ms`);
});

test('closeWithTimeout bounds hung close promise cleanly', async () => {
    const t0 = Date.now();
    await closeWithTimeout(() => new Promise(() => {}), 40);
    assert.ok(Date.now() - t0 < 300);
});
