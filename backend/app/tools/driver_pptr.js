const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

// Execute wappalyzer.js in the current context so the global `wappalyzer` object is available
const wappalyzerCode = fs.readFileSync(path.join(__dirname, 'wappalyzer.js'), 'utf8');
eval(wappalyzerCode);

async function main() {
    const url = process.argv[2];
    if (!url) {
        console.error("Usage: node driver_pptr.js <url>");
        process.exit(1);
    }

    let browser;
    try {
        browser = await puppeteer.launch({
            executablePath: '/usr/bin/chromium',
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--ignore-certificate-errors'],
            ignoreHTTPSErrors: true
        });

        const page = await browser.newPage();
        await page.setViewport({ width: 1280, height: 1024 });

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
            await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
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

        // Setup wappalyzer
        const json = JSON.parse(fs.readFileSync(path.join(__dirname, 'apps.json'), 'utf8'));
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
                console.log(JSON.stringify({ url: url, originalUrl: url, applications: apps || [] }));
                process.exit(0);
            }
        };

        const parsedUrl = new URL(url);
        wappalyzer.analyze(parsedUrl.hostname, url, {
            html: html,
            headers: headers,
            env: environmentVars
        });

    } catch (e) {
        console.log(JSON.stringify({ url: url, originalUrl: url, applications: [] }));
        process.exit(1);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

main();
