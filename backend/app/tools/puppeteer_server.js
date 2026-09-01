const http = require('http');
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const wappalyzerCode = fs.readFileSync(path.join(__dirname, 'wappalyzer.js'), 'utf8');
const vm = require('vm');
const wappalyzerScript = new vm.Script(wappalyzerCode);
const json = JSON.parse(fs.readFileSync(path.join(__dirname, 'apps.json'), 'utf8'));

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
        this.currentRunning--;
        if (this.queue.length > 0) {
            this.currentRunning++;
            const next = this.queue.shift();
            next();
        }
    }
}

const semaphore = new ConcurrencySemaphore(2); // 严格限制 Chromium 最多同时活跃 2 个页面

// ==========================================
// 2. 浏览器实例与动态引用计数管理
// ==========================================
let currentBrowserWrapper = null;
let requestsCount = 0;
let isRotating = false;
const MAX_REQUESTS = 200; // 每 200 次请求自愈轮转一次 (平衡 V8 堆内存释放与 Chromium 启动开销)

class BrowserWrapper {
    constructor(browser) {
        this.browser = browser;
        this.activeTasks = 0;
        this.isRetired = false;
        this.fallbackTimeoutId = null;
    }

    acquireTask() {
        this.activeTasks++;
    }

    releaseTask() {
        this.activeTasks--;
        if (this.isRetired && this.activeTasks <= 0) {
            this.destroy();
        }
    }

    retire() {
        this.isRetired = true;
        if (this.activeTasks <= 0) {
            this.destroy();
        } else {
            // 兜底 35 秒强制回收（防止个别异常任务挂死）
            this.fallbackTimeoutId = setTimeout(() => {
                console.log('[BrowserManager] Fallback 35s reached for retired browser, forcing destroy...');
                this.destroy();
            }, 35000);
        }
    }

    destroy() {
        if (this.fallbackTimeoutId) {
            clearTimeout(this.fallbackTimeoutId);
            this.fallbackTimeoutId = null;
        }
        if (this.browser) {
            console.log('[BrowserManager] Retiring old browser: all in-flight tasks finished. Releasing memory.');
            const b = this.browser;
            this.browser = null;
            b.close().catch(() => true);
            if (b.process() && b.process().pid) {
                try {
                    process.kill(b.process().pid, 'SIGKILL');
                } catch(e) {}
            }
        }
    }
}

async function launchBrowserInstance() {
    const browser = await puppeteer.launch({
        executablePath: '/usr/bin/chromium',
        args: [
            '--no-sandbox', 
            '--disable-setuid-sandbox', 
            '--disable-dev-shm-usage', 
            '--ignore-certificate-errors', 
            '--disable-gpu',
            '--js-flags=--max-old-space-size=512',
            '--disable-site-isolation-trials',
            '--disable-extensions',
            '--mute-audio'
        ],
        ignoreHTTPSErrors: true
    });
    return new BrowserWrapper(browser);
}

async function checkRotation() {
    if (requestsCount >= MAX_REQUESTS && !isRotating) {
        isRotating = true;
        requestsCount = 0; // 重置计数
        console.log('[BrowserManager] Max requests reached (200), performing seamless rolling restart...');
        
        const oldWrapper = currentBrowserWrapper;
        try {
            const newWrapper = await launchBrowserInstance();
            currentBrowserWrapper = newWrapper;
            console.log('[BrowserManager] New browser spawned. Handing over traffic...');
            if (oldWrapper) {
                oldWrapper.retire();
            }
        } catch (e) {
            console.error('[BrowserManager] Failed to launch new browser during rotation:', e);
        } finally {
            isRotating = false;
        }
    }
}

function analyzeUrl(url, targetWrapper) {
    return new Promise(async (resolve, reject) => {
        let page;
        let context;
        let timeoutId;

        const cleanupAndResolve = async (apps) => {
            if (timeoutId) clearTimeout(timeoutId);
            if (page) await page.close().catch(() => true);
            if (context) await context.close().catch(() => true);
            resolve({ url: url, originalUrl: url, applications: apps || [] });
        };

        timeoutId = setTimeout(() => {
            console.log(`[Timeout] 32s limit reached for ${url}`);
            cleanupAndResolve([]);
        }, 32000);

        try {
            if (!targetWrapper.browser) {
                cleanupAndResolve([]);
                return;
            }

            // Create a new incognito context for isolation
            context = await targetWrapper.browser.createIncognitoBrowserContext();
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

            // Close page and context
            await page.close();
            await context.close();

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

function takeScreenshot(url, targetWrapper) {
    return new Promise(async (resolve, reject) => {
        let page;
        let context;
        let timeoutId;

        const cleanupAndResolve = async (base64) => {
            if (timeoutId) clearTimeout(timeoutId);
            if (page) await page.close().catch(() => true);
            if (context) await context.close().catch(() => true);
            resolve({ url: url, base64: base64 || null });
        };

        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            console.error(`[Security Block] Invalid protocol for URL: ${url}`);
            resolve({ url: url, base64: null });
            return;
        }

        timeoutId = setTimeout(() => {
            console.log(`[Screenshot Timeout] 25s limit reached for ${url}`);
            cleanupAndResolve(null);
        }, 25000);
        
        try {
            if (!targetWrapper.browser) {
                cleanupAndResolve(null);
                return;
            }

            context = await targetWrapper.browser.createIncognitoBrowserContext();
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
            });
            
            try {
                await Promise.race([gotoPromise, timeoutPromise]);
            } catch (gotoErr) {
                console.error(`Goto warning [${url}]:`, gotoErr.message);
            } finally {
                clearTimeout(gotoTimeoutId);
            }
            
            await new Promise(r => setTimeout(r, 3000));

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
                });
                
                height = await Promise.race([evalPromise, evalTimeout]);
                if (typeof height !== 'number') height = 768;
                clearTimeout(evalTimeoutId); 
            } catch (evalErr) {
                console.error(`Evaluate warning [${url}]:`, evalErr.message);
                height = 768;
            }

            try {
                await page.setViewport({ width: 1024, height: height });
            } catch(vpErr) {}
            
            let base64 = null;
            try {
                base64 = await page.screenshot({ type: 'jpeg', quality: 30, encoding: 'base64' });
            } catch (ssErr) {
                console.error(`Screenshot error [${url}]:`, ssErr.message);
                await new Promise(r => setTimeout(r, 1000));
                try {
                    await page.setViewport({ width: 1024, height: 768 });
                    base64 = await page.screenshot({ type: 'jpeg', quality: 30, encoding: 'base64', clip: {x: 0, y: 0, width: 1024, height: 768} });
                } catch (ssErr2) {
                    console.error(`Screenshot fallback error [${url}]:`, ssErr2.message);
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
                
                // 绑定当前接收请求时的目标 BrowserWrapper 实例
                const targetWrapper = currentBrowserWrapper;
                if (!targetWrapper || !targetWrapper.browser) {
                    res.writeHead(503);
                    res.end('Browser instance is initializing');
                    return;
                }

                // 获取任务与并发信号量
                targetWrapper.acquireTask();
                await semaphore.acquire();

                let result;
                try {
                    if (req.url === '/screenshot') {
                        result = await takeScreenshot(url, targetWrapper);
                    } else {
                        result = await analyzeUrl(url, targetWrapper);
                    }
                } finally {
                    semaphore.release();
                    targetWrapper.releaseTask();
                }
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
                
                requestsCount++;
            } catch (e) {
                res.writeHead(500);
                res.end(e.message);
            } finally {
                checkRotation();
            }
        });
    } else {
        res.writeHead(200);
        res.end('Puppeteer Wappalyzer Server OK');
        checkRotation();
    }
});

launchBrowserInstance().then(wrapper => {
    currentBrowserWrapper = wrapper;
    server.listen(5005, '0.0.0.0', () => {
        console.log('Puppeteer server running on port 5005 (Semaphore=2, MaxV8=512MB)');
    });
}).catch(console.error);
