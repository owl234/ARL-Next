/**
 * 提取图片的主色调，内置超时与降级保护，避免解析挂死
 * @param {string} imageSrc - 图片的 Base64 或 URL
 * @param {number} timeoutMs - 超时时间（毫秒）
 * @returns {Promise<string>} 返回 RGB 颜色字符串，例如 "rgb(255, 0, 0)"
 */
export const extractDominantColor = (imageSrc, timeoutMs = 2500) => {
  return new Promise((resolve) => {
    const fallbackColor = '#fa541c';
    let isSettled = false;

    const timer = setTimeout(() => {
      if (!isSettled) {
        isSettled = true;
        resolve(fallbackColor);
      }
    }, timeoutMs);

    const img = new Image();
    img.crossOrigin = 'Anonymous';

    img.onload = () => {
      if (isSettled) return;
      isSettled = true;
      clearTimeout(timer);

      try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) return resolve(fallbackColor);

        // 为了性能，将图片缩小到 50x50 来提取颜色
        const width = 50;
        const height = 50;
        canvas.width = width;
        canvas.height = height;

        ctx.drawImage(img, 0, 0, width, height);

        let data;
        try {
          data = ctx.getImageData(0, 0, width, height).data;
        } catch (e) {
          return resolve(fallbackColor);
        }

        let r = 0, g = 0, b = 0;
        let count = 0;

        for (let i = 0; i < data.length; i += 4) {
          const red = data[i];
          const green = data[i + 1];
          const blue = data[i + 2];
          const alpha = data[i + 3];

          // 忽略透明度过低的像素
          if (alpha < 128) continue;

          // 忽略偏白或偏黑的像素，因为它们通常不适合作为主题色
          const brightness = (red * 299 + green * 587 + blue * 114) / 1000;
          if (brightness < 30 || brightness > 220) continue;

          r += red;
          g += green;
          b += blue;
          count++;
        }

        if (count === 0) {
          return resolve(fallbackColor);
        }

        r = Math.floor(r / count);
        g = Math.floor(g / count);
        b = Math.floor(b / count);

        // 为了确保颜色不会太浅，进行简单的亮度控制
        const finalBrightness = (r * 299 + g * 587 + b * 114) / 1000;
        if (finalBrightness > 200) {
          r = Math.max(0, r - 30);
          g = Math.max(0, g - 30);
          b = Math.max(0, b - 30);
        }

        resolve(`rgb(${r}, ${g}, ${b})`);
      } catch (e) {
        resolve(fallbackColor);
      }
    };

    img.onerror = () => {
      if (!isSettled) {
        isSettled = true;
        clearTimeout(timer);
        resolve(fallbackColor);
      }
    };

    img.src = imageSrc;
  });
};

/**
 * 将 File 对象进行高清智能压缩并转换为 Base64。
 * 限制最大分辨率为 1920x1080 并采用 WebP (降级 JPEG) 编码，
 * 从根源上杜绝超大高清壁纸（动辄数十 MB Base64）塞满 DOM 节点与 IndexedDB 导致浏览器主线程和 GPU 假死。
 */
export const processImageToBase64 = (file, maxWidth = 1920, maxHeight = 1080, quality = 0.85) => {
  return new Promise((resolve, reject) => {
    if (!file || !file.type || !file.type.startsWith('image/')) {
      return reject(new Error('请选择有效的图片文件'));
    }

    let objectUrl = null;
    try {
      objectUrl = URL.createObjectURL(file);
    } catch (e) {
      return reject(new Error('创建图片临时对象失败: ' + (e.message || '未知错误')));
    }

    const cleanup = () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    };

    const img = new Image();
    img.onload = () => {
      cleanup();
      try {
        let width = img.width;
        let height = img.height;

        // 若分辨率超出限制，等比例收缩至高清边界之内
        if (width > maxWidth || height > maxHeight) {
          const ratio = Math.min(maxWidth / width, maxHeight / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          return reject(new Error('创建 Canvas 2D 绘图上下文失败'));
        }

        ctx.drawImage(img, 0, 0, width, height);

        // 优先使用 WebP 编码，压缩比极高且色彩失真极小
        try {
          const webpData = canvas.toDataURL('image/webp', quality);
          if (webpData.startsWith('data:image/webp')) {
            return resolve(webpData);
          }
        } catch (err) {
          // 不支持 webp 则平滑降级
        }

        resolve(canvas.toDataURL('image/jpeg', quality));
      } catch (err) {
        reject(new Error('图片压缩处理失败: ' + (err.message || '未知错误')));
      }
    };

    img.onerror = () => {
      cleanup();
      reject(new Error('图片解码失败，请确认文件是否完整'));
    };

    img.src = objectUrl;
  });
};

/**
 * 封装 IndexedDB 操作，用于存储不受 5MB 限制的高清背景图
 */
export const dbHelper = {
  dbName: 'arl-next-theme-db',
  storeName: 'settings',
  init() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(this.dbName, 1);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          db.createObjectStore(this.storeName);
        }
      };
      req.onsuccess = (e) => resolve(e.target.result);
      req.onerror = (e) => reject(e.target.error);
    });
  },
  async get(key) {
    const db = await this.init();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(this.storeName, 'readonly');
      const store = tx.objectStore(this.storeName);
      const req = store.get(key);
      req.onsuccess = (e) => resolve(e.target.result);
      req.onerror = (e) => reject(e.target.error);
    });
  },
  async set(key, value) {
    const db = await this.init();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(this.storeName, 'readwrite');
      const store = tx.objectStore(this.storeName);
      const req = store.put(value, key);
      req.onsuccess = () => resolve();
      req.onerror = (e) => reject(e.target.error);
    });
  },
  async remove(key) {
    const db = await this.init();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(this.storeName, 'readwrite');
      const store = tx.objectStore(this.storeName);
      const req = store.delete(key);
      req.onsuccess = () => resolve();
      req.onerror = (e) => reject(e.target.error);
    });
  },
  async clear() {
    try {
      const db = await this.init();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(this.storeName, 'readwrite');
        const store = tx.objectStore(this.storeName);
        const req = store.clear();
        req.onsuccess = () => resolve();
        req.onerror = (e) => reject(e.target.error);
      });
    } catch (e) {
      console.warn('dbHelper.clear failed:', e);
    }
  }
};
