const puppeteer = require('puppeteer-core');

async function main() {
    let url = '';
    let save_name = '';

    for (let i = 0; i < process.argv.length; i++) {
        if (process.argv[i].startsWith('-u=')) {
            url = process.argv[i].substring(3);
        } else if (process.argv[i].startsWith('-s=')) {
            save_name = process.argv[i].substring(3);
        }
    }

    if (!url || !save_name) {
        console.error("Usage: node screenshot_pptr.js -u=http://www.baidu.com -s=baidu.jpg");
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

        // Go to URL and wait until there are no more than 2 network connections for at least 500 ms.
        // This gives SPA (React/Vue) time to load.
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
        
        // Wait an extra second for any rendering/animations to settle
        await new Promise(r => setTimeout(r, 1000));

        // Evaluate dynamic height and force expansion of 100vh elements
        const height = await page.evaluate(() => {
            document.body.style.backgroundColor = 'white';
            try {
                let style = document.createElement('style');
                style.innerHTML = 'html, body { height: auto !important; overflow: visible !important; min-height: 100% !important; }';
                document.head.appendChild(style);
            } catch(e) {}
            
            let maxH = 1024;
            const elements = document.querySelectorAll('*');
            for (let el of elements) {
                if (el.scrollHeight > maxH) {
                    maxH = el.scrollHeight;
                }
            }
            return maxH > 5000 ? 5000 : maxH;
        });

        await page.setViewport({ width: 1280, height: height });

        // Capture full page screenshot
        await page.screenshot({ path: save_name, type: 'jpeg', quality: 90, fullPage: true });

    } catch (e) {
        console.error("Screenshot error:", e.message);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

main();
