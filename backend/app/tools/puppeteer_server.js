const http = require('http');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

let puppeteerLib = null;
function getPuppeteer() {
    if (!puppeteerLib) {
        puppeteerLib = require('puppeteer-core');
    }
    return puppeteerLib;
}

const wappalyzerCode = fs.readFileSync(path.join(__dirname, 'wappalyzer.js'), 'utf8');
const wappalyzerScript = new vm.Script(wappalyzerCode);
const json = JSON.parse(fs.readFileSync(path.join(__dirname, 'apps.json'), 'utf8'));

function parsePositiveInt(raw, fallback, min = 1, max = 10000) {
    if (raw === undefined || raw === null || raw === '') return fallback;
    const str = String(raw).trim();
    if (!/^[1-9][0-9]*$/.test(str)) return fallback;
    const n = parseInt(str, 10);
    if (!Number.isFinite(n) || n < min) return fallback;
    return Math.min(n, max);
}

// ==========================================
// 1. 异步信号量并发队列 (Concurrency Control)
// ==========================================
class ConcurrencySemaphore {
    constructor(maxConcurrent = 2) {
        this.maxConcurrent = maxConcurrent;
        this.currentRunning = 0;
        this.queue = [];
    }

    async acquire() {
        if (this.currentRunning < this.maxConcurrent) {
            this.currentRunning++;
            return Promise.resolve();
        }
        return new Promise(resolve => this.queue.push(resolve));
    }

    release() {
        this.currentRunning = Math.max(0, this.currentRunning - 1);
        if (this.queue.length > 0) {
            this.currentRunning++;
            const next = this.queue.shift();
            next();
        }
    }
}

const semaphore = new ConcurrencySemaphore(2); // 严格限制 Chromium 最多同时活跃 2 个页面

// ==========================================
// 2. 浏览器实例与串行排空轮转管理
// ==========================================
const MAX_REQUESTS = parsePositiveInt(process.env.PUPPETEER_MAX_REQUESTS, 200, 1, 10000);
const CLOSE_TIMEOUT_MS = parsePositiveInt(process.env.PUPPETEER_CLOSE_TIMEOUT_MS, 3000, 100, 30000);
const ROTATE_DRAIN_TIMEOUT_MS = parsePositiveInt(process.env.PUPPETEER_ROTATE_DRAIN_TIMEOUT_MS, 35000, 100, 120000);

function closeWithTimeout(fn, timeoutMs = CLOSE_TIMEOUT_MS) {
    let timerId;
    const timeoutPromise = new Promise(resolve => {
        timerId = setTimeout(resolve, timeoutMs);
        if (timerId.unref) timerId.unref();
    });
    return Promise.race([
        Promise.resolve().then(fn).catch(() => true),
        timeoutPromise
    ]).finally(() => {
        if (timerId) clearTimeout(timerId);
    });
}

function killBrowserProcess(proc, killFn = process.kill) {
    if (!proc || !proc.pid) return;
    const pid = proc.pid;
    // 先尝试向独立进程组发 SIGKILL，回收 Chromium 主进程及其 renderer/crashpad 子树；
    // 若未独立成组则回退单 PID 强杀（容器 init: true 兜底回收孤儿进程）。
    try {
        killFn(-pid, 'SIGKILL');
    } catch (e) {
        try {
            killFn(pid, 'SIGKILL');
        } catch (_) {}
    }
}

function normalizeProxyArg(raw) {
    if (!raw || typeof raw !== 'string') return '';
    const trimmed = raw.trim();
    if (!trimmed) return '';
    try {
        const parsed = new URL(trimmed);
        if (parsed.username || parsed.password) {
            return '';
        }
        const scheme = parsed.protocol.replace(/:$/, '').toLowerCase();
        if (scheme === 'socks5h') {
            return `socks5://${parsed.host}`;
        }
        if (scheme === 'http' || scheme === 'https' || scheme === 'socks5') {
            return `${scheme}://${parsed.host}`;
        }
        return '';
    } catch (e) {
        return '';
    }
}

class BrowserWrapper {
    constructor(browser, { drainTimeoutMs = ROTATE_DRAIN_TIMEOUT_MS, closeTimeoutMs = CLOSE_TIMEOUT_MS, killFn = process.kill } = {}) {
        this.browser = browser;
        this.activeTasks = 0;
        this.isRetired = false;
        this.destroyed = false;
        this.drainTimeoutMs = drainTimeoutMs;
        this.closeTimeoutMs = closeTimeoutMs;
        this.killFn = killFn;
        this._drainResolvers = [];
        this._destroyPromise = null;
    }

    acquireTask() {
        this.activeTasks++;
    }

    releaseTask() {
        this.activeTasks = Math.max(0, this.activeTasks - 1);
        if (this.isRetired && this.activeTasks === 0) {
            this._resolveDrained();
        }
    }

    _resolveDrained() {
        const resolvers = this._drainResolvers.splice(0);
        for (const resolve of resolvers) {
            resolve();
        }
    }

    async retireAndDestroy() {
        this.isRetired = true;
        if (this.activeTasks > 0) {
            await new Promise(resolve => {
                let timerId;
                const done = () => {
                    if (timerId) {
                        clearTimeout(timerId);
                        timerId = null;
                    }
                    resolve();
                };
                this._drainResolvers.push(done);
                timerId = setTimeout(() => {
                    console.log(`[BrowserManager] Drain timeout (${this.drainTimeoutMs}ms) reached for retired browser, forcing destroy...`);
                    done();
                }, this.drainTimeoutMs);
                if (timerId.unref) timerId.unref();
            });
        }
        await this.destroy();
    }

    destroy() {
        if (this._destroyPromise) {
            return this._destroyPromise;
        }
        this._destroyPromise = (async () => {
            if (this.destroyed) return;
            this.destroyed = true;
            const b = this.browser;
            this.browser = null;
            if (!b) return;
            console.log('[BrowserManager] Closing retired browser instance to release memory.');
            const proc = typeof b.process === 'function' ? b.process() : null;
            await closeWithTimeout(() => b.close(), this.closeTimeoutMs);
            killBrowserProcess(proc, this.killFn);
        })();
        return this._destroyPromise;
    }
}

async function launchRawBrowser() {
    const args = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--ignore-certificate-errors',
        '--disable-gpu',
        '--js-flags=--max-old-space-size=512',
        '--disable-site-isolation-trials',
        '--disable-extensions',
        '--mute-audio'
    ];
    return getPuppeteer().launch({
        executablePath: '/usr/bin/chromium',
        args,
        ignoreHTTPSErrors: true
    });
}

class BrowserLifecycleManager {
    constructor({
        launchFn = launchRawBrowser,
        maxRequests = MAX_REQUESTS,
        drainTimeoutMs = ROTATE_DRAIN_TIMEOUT_MS,
        closeTimeoutMs = CLOSE_TIMEOUT_MS,
        killFn = process.kill
    } = {}) {
        this.launchFn = launchFn;
        this.maxRequests = maxRequests;
        this.drainTimeoutMs = drainTimeoutMs;
        this.closeTimeoutMs = closeTimeoutMs;
        this.killFn = killFn;
        this.currentWrapper = null;
        this.initPromise = null;
        this.rotationPromise = null;
        this.requestsCount = 0;
    }

    async ensureActiveBrowser() {
        // 串行轮转期间新请求统一在此等待，待旧实例完成回收后再切入新实例
        if (this.rotationPromise) {
            await this.rotationPromise;
        }
        if (
            this.currentWrapper &&
            !this.currentWrapper.isRetired &&
            this.currentWrapper.browser &&
            this.currentWrapper.browser.isConnected()
        ) {
            return this.currentWrapper;
        }
        if (!this.initPromise) {
            this.initPromise = (async () => {
                const staleWrapper = this.currentWrapper;
                this.currentWrapper = null;
                if (staleWrapper) {
                    await staleWrapper.retireAndDestroy();
                }
                const browser = await this.launchFn();
                const newWrapper = new BrowserWrapper(browser, {
                    drainTimeoutMs: this.drainTimeoutMs,
                    closeTimeoutMs: this.closeTimeoutMs,
                    killFn: this.killFn
                });
                this.currentWrapper = newWrapper;
                this.requestsCount = 0;
                console.log('[BrowserManager] Initialized active Chromium instance (per-context proxy isolation)');
                return newWrapper;
            })().finally(() => {
                this.initPromise = null;
            });
        }
        return this.initPromise;
    }

    async acquireActiveBrowser() {
        while (true) {
            const wrapper = await this.ensureActiveBrowser();
            if (wrapper && !wrapper.isRetired && wrapper.browser && wrapper.browser.isConnected()) {
                wrapper.acquireTask();
                return wrapper;
            }
            if (!this.rotationPromise && !this.initPromise) {
                return null;
            }
        }
    }

    recordRequest() {
        this.requestsCount++;
    }

    maybeRotate() {
        if (this.requestsCount < this.maxRequests || this.rotationPromise) {
            return this.rotationPromise;
        }
        const oldWrapper = this.currentWrapper;
        this.requestsCount = 0;
        console.log(`[BrowserManager] Max requests reached (${this.maxRequests}), draining old browser before relaunch...`);
        this.rotationPromise = (async () => {
            try {
                // 先摘除并退休旧实例，排空在途页面并强杀残留进程组，再拉起新实例消除双实例内存峰值
                if (oldWrapper) {
                    this.currentWrapper = null;
                    await oldWrapper.retireAndDestroy();
                }
                const browser = await this.launchFn();
                this.currentWrapper = new BrowserWrapper(browser, {
                    drainTimeoutMs: this.drainTimeoutMs,
                    closeTimeoutMs: this.closeTimeoutMs,
                    killFn: this.killFn
                });
                console.log('[BrowserManager] Serial rotation complete: new Chromium instance ready.');
            } catch (e) {
                console.error('[BrowserManager] Serial rotation failed:', e);
            } finally {
                this.rotationPromise = null;
            }
        })();
        return this.rotationPromise;
    }
}

const browserManager = new BrowserLifecycleManager();

/**
 * 为每次扫描请求创建独立 incognito 上下文，确保 CDP 层的代理配置按请求精确生效且互不串扰。
 */
async function createContextForProxy(browser, proxyServerRaw = '') {
    const normalizedProxy = normalizeProxyArg(proxyServerRaw);
    if (normalizedProxy) {
        return browser.createIncognitoBrowserContext({ proxyServer: normalizedProxy });
    }
    return browser.createIncognitoBrowserContext();
}

function analyzeUrl(url, targetWrapper, proxyServer = '', { closeTimeoutMs = CLOSE_TIMEOUT_MS } = {}) {
    return new Promise(async (resolve) => {
        let page;
        let context;
        let timeoutId;
        let settled = false;

        const cleanupAndResolve = async (apps) => {
            if (settled) return;
            settled = true;
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
            const p = page;
            const c = context;
            page = null;
            context = null;
            if (p) await closeWithTimeout(() => p.close(), closeTimeoutMs);
            if (c) await closeWithTimeout(() => c.close(), closeTimeoutMs);
            resolve({ url: url, originalUrl: url, applications: apps || [] });
        };

        timeoutId = setTimeout(() => {
            console.log(`[Timeout] 32s limit reached for ${url}`);
            cleanupAndResolve([]);
        }, 32000);

        try {
            if (!targetWrapper || !targetWrapper.browser) {
                cleanupAndResolve([]);
                return;
            }

            // Create a new incognito context for isolation (binding per-request proxy via CDP)
            context = await createContextForProxy(targetWrapper.browser, proxyServer);
            page = await context.newPage();
            
            // Bypass WAF by mocking User-Agent and webdriver
            await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
            await page.evaluateOnNewDocument(() => {
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
            });

            await page.setViewport({ width: 1280, height: 1024 });

            // Resource blocking to save CPU and Bandwidth
            await page.setRequestInterception(true);
            page.on('request', (req) => {
                const resourceType = req.resourceType();
                if (['image', 'stylesheet', 'font', 'media'].includes(resourceType)) {
                    req.abort();
                } else {
                    req.continue();
                }
            });

            let headers = {};
            let html = '';

            page.on('response', response => {
                // We want the headers from the main document response
                if (response.url().replace(/\/$/, '') === url.replace(/\/$/, '') || response.url() === url) {
                    const contentType = response.headers()['content-type'];
                    if (response.status() === 200 && contentType && contentType.includes('text/html')) {
                        headers = response.headers();
                    }
                }
            });

            try {
                await page.goto(url, { waitUntil: 'networkidle2', timeout: 25000 });
            } catch (e) {
                // timeout is fine, we might still have DOM
            }

            html = await page.content();
            
            // Truncate huge HTML to avoid regex explosion in wappalyzer
            if (html.length > 50000) {
                html = html.substring(0, 25000) + html.substring(html.length - 25000, html.length);
            }

            const environmentVarsArray = await page.evaluate(() => {
                return Object.keys(window);
            });
            const environmentVars = environmentVarsArray.slice(0, 500).join(' ');

            // 提前关闭页面与上下文并做超时保护，避免进入 Wappalyzer 解析时继续占用渲染器内存
            const p = page;
            const c = context;
            page = null;
            context = null;
            if (p) await closeWithTimeout(() => p.close(), closeTimeoutMs);
            if (c) await closeWithTimeout(() => c.close(), closeTimeoutMs);

            // Evaluate Wappalyzer using a precompiled vm.Script to save massive CPU cycles while maintaining state isolation
            const contextObj = {};
            vm.createContext(contextObj);
            wappalyzerScript.runInContext(contextObj);
            const wappalyzer = contextObj.wappalyzer;

            wappalyzer.apps = json.apps;
            wappalyzer.categories = json.categories;

            wappalyzer.driver = {
                log: function(args) { },
                displayApps: function() {
                    let apps = [];
                    for (let app in wappalyzer.detected[url]) {
                        let cats = [];
                        wappalyzer.apps[app].cats.forEach(function(cat) {
                            cats.push(wappalyzer.categories[cat].name);
                        });
                        apps.push({
                            name: app,
                            confidence: wappalyzer.detected[url][app].confidenceTotal.toString(),
                            version: wappalyzer.detected[url][app].version,
                            icon: wappalyzer.apps[app].icon || 'default.svg',
                            website: wappalyzer.apps[app].website,
                            categories: cats
                        });
                    }
                    this.sendResponse(apps);
                },
                sendResponse: function(apps) {
                    cleanupAndResolve(apps);
                }
            };

            const parsedUrl = new URL(url);
            wappalyzer.analyze(parsedUrl.hostname, url, {
                html: html,
                headers: headers,
                env: environmentVars
            });

        } catch (e) {
            cleanupAndResolve([]);
        }
    });
}

function takeScreenshot(url, targetWrapper, proxyServer = '', { closeTimeoutMs = CLOSE_TIMEOUT_MS, hardTimeoutMs = 25000 } = {}) {
    return new Promise(async (resolve) => {
        let page;
        let context;
        let timeoutId;
        let settled = false;

        const cleanupAndResolve = async (base64) => {
            if (settled) return;
            settled = true;
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
            const p = page;
            const c = context;
            page = null;
            context = null;
            if (p) await closeWithTimeout(() => p.close(), closeTimeoutMs);
            if (c) await closeWithTimeout(() => c.close(), closeTimeoutMs);
            resolve({ url: url, base64: base64 || null });
        };

        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            console.error(`[Security Block] Invalid protocol for URL: ${url}`);
            resolve({ url: url, base64: null });
            return;
        }

        timeoutId = setTimeout(() => {
            console.log(`[Screenshot Timeout] ${hardTimeoutMs}ms limit reached for ${url}`);
            cleanupAndResolve(null);
        }, hardTimeoutMs);
        if (timeoutId.unref) timeoutId.unref();
        
        try {
            if (!targetWrapper || !targetWrapper.browser) {
                cleanupAndResolve(null);
                return;
            }

            context = await createContextForProxy(targetWrapper.browser, proxyServer);
            page = await context.newPage();
            
            // Bypass WAF by mocking User-Agent and webdriver
            await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
            await page.evaluateOnNewDocument(() => {
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
            });
            
            page.on('dialog', async dialog => {
                await dialog.dismiss().catch(() => {});
            });

            await page.setRequestInterception(true);
            page.on('request', (req) => {
                if (req.isInterceptResolutionHandled && req.isInterceptResolutionHandled()) return;
                const rt = req.resourceType();
                if (['media', 'font', 'websocket', 'manifest'].includes(rt)) {
                    req.abort().catch(() => {});
                } else {
                    req.continue().catch(() => {});
                }
            });

            await page.setViewport({ width: 1024, height: 768 });

            const gotoPromise = page.goto(url, { waitUntil: 'load', timeout: 15000 });
            gotoPromise.catch(() => {});
            
            let gotoTimeoutId;
            const timeoutPromise = new Promise((_, reject) => {
                gotoTimeoutId = setTimeout(() => reject(new Error('Goto Hard Timeout')), 15000);
                if (gotoTimeoutId.unref) gotoTimeoutId.unref();
            });
            
            try {
                await Promise.race([gotoPromise, timeoutPromise]);
            } catch (gotoErr) {
                if (!settled) console.error(`Goto warning [${url}]:`, gotoErr.message);
            } finally {
                clearTimeout(gotoTimeoutId);
            }

            if (settled || !page) return;
            await new Promise(r => {
                const t = setTimeout(r, 3000);
                if (t.unref) t.unref();
            });
            if (settled || !page) return;

            let height = 768;
            try {
                const evalPromise = page.evaluate(() => {
                    if (document.body) { document.body.style.backgroundColor = 'white'; }
                    try {
                        let style = document.createElement('style');
                        style.innerHTML = 'html, body { height: auto !important; overflow: visible !important; min-height: 100% !important; }';
                        document.head.appendChild(style);
                    } catch(e) {}
                    
                    let maxH = 768;
                    try {
                        maxH = Math.max(
                            document.body ? document.body.scrollHeight : 768,
                            document.documentElement ? document.documentElement.scrollHeight : 768,
                            document.body ? document.body.offsetHeight : 768,
                            document.documentElement ? document.documentElement.offsetHeight : 768,
                            document.body ? document.body.clientHeight : 768,
                            document.documentElement ? document.documentElement.clientHeight : 768
                        );
                    } catch(e) {}
                    
                    return maxH > 2048 ? 2048 : (maxH < 768 ? 768 : maxH);
                });
                evalPromise.catch(() => {}); 
                
                let evalTimeoutId;
                const evalTimeout = new Promise((_, reject) => {
                    evalTimeoutId = setTimeout(() => reject(new Error('Evaluate Timeout')), 5000);
                    if (evalTimeoutId.unref) evalTimeoutId.unref();
                });
                
                height = await Promise.race([evalPromise, evalTimeout]);
                if (typeof height !== 'number') height = 768;
                clearTimeout(evalTimeoutId); 
            } catch (evalErr) {
                if (!settled) console.error(`Evaluate warning [${url}]:`, evalErr.message);
                height = 768;
            }

            if (settled || !page) return;
            try {
                await page.setViewport({ width: 1024, height: height });
            } catch(vpErr) {}

            if (settled || !page) return;
            let base64 = null;
            try {
                base64 = await page.screenshot({ type: 'jpeg', quality: 30, encoding: 'base64' });
            } catch (ssErr) {
                if (settled || !page) return;
                console.error(`Screenshot error [${url}]:`, ssErr.message);
                await new Promise(r => {
                    const t = setTimeout(r, 1000);
                    if (t.unref) t.unref();
                });
                if (settled || !page) return;
                try {
                    await page.setViewport({ width: 1024, height: 768 });
                    base64 = await page.screenshot({ type: 'jpeg', quality: 30, encoding: 'base64', clip: {x: 0, y: 0, width: 1024, height: 768} });
                } catch (ssErr2) {
                    if (!settled) console.error(`Screenshot fallback error [${url}]:`, ssErr2.message);
                }
            }
            cleanupAndResolve(base64);
        } catch (e) {
            console.error(`Screenshot error [${url}]:`, e.message);
            cleanupAndResolve(null);
        }
    });
}

const server = http.createServer(async (req, res) => {
    if (req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk.toString());
        req.on('end', async () => {
            try {
                const data = JSON.parse(body);
                const url = data.url;
                if (!url) {
                    res.writeHead(400);
                    res.end('Missing url');
                    return;
                }
                
                // 先获取并发信号量（上限 2），再原子登记到活跃浏览器，确保退休实例最多只需排空 1 个在途任务
                const proxyServer = data.proxy_server || '';
                let targetWrapper = null;
                let result;
                await semaphore.acquire();
                try {
                    targetWrapper = await browserManager.acquireActiveBrowser();
                    if (!targetWrapper || !targetWrapper.browser) {
                        res.writeHead(503);
                        res.end('Browser instance is initializing');
                        return;
                    }
                    if (req.url === '/screenshot') {
                        result = await takeScreenshot(url, targetWrapper, proxyServer);
                    } else {
                        result = await analyzeUrl(url, targetWrapper, proxyServer);
                    }
                    browserManager.recordRequest();
                } finally {
                    if (targetWrapper) {
                        targetWrapper.releaseTask();
                    }
                    browserManager.maybeRotate();
                    semaphore.release();
                }

                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
            } catch (e) {
                res.writeHead(500);
                res.end(e.message);
            }
        });
    } else {
        res.writeHead(200);
        res.end('Puppeteer Wappalyzer Server OK');
        browserManager.maybeRotate();
    }
});

if (require.main === module) {
    browserManager.ensureActiveBrowser().then(() => {
        server.listen(5005, '0.0.0.0', () => {
            console.log(`Puppeteer server running on port 5005 (Semaphore=2, MaxV8=512MB, MaxRequests=${MAX_REQUESTS}, SerialRotation=true)`);
        });
    }).catch(console.error);
}

module.exports = {
    ConcurrencySemaphore,
    BrowserWrapper,
    BrowserLifecycleManager,
    closeWithTimeout,
    killBrowserProcess,
    parsePositiveInt,
    normalizeProxyArg,
    analyzeUrl,
    takeScreenshot
};
