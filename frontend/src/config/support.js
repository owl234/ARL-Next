/**
 * ARL-Next 赞助打赏、公众号与作者微信支持配置
 * 
 * 💡 二维码图片替换指引：
 * 只要将您的真实二维码截图放置在 `frontend/src/assets/support/` 目录下即可自动被检测识别：
 *   - 打赏收款码：reward.png 或 reward.jpg
 *   - 官方公众号：mp.png 或 mp.jpg
 *   - 作者微信号：wechat.png 或 wechat.jpg
 * 若未放置真实 png/jpg，系统会自动优雅回退展示对应的矢量占位图。
 */

export const SUPPORT_CONFIG = {
  // 顶部导航栏入口文案与提示
  entry: {
    text: '支持作者',
    icon: '💖',
    tooltip: '关注公众号、加入技术交流群与赞助作者',
    showPulse: true, // 是否启用轻量心跳呼吸微光
  },

  // 默认激活的 Tab ('reward' | 'official' | 'wechat')
  defaultTab: 'reward',

  // 1. 赞助打赏配置
  reward: {
    tabTitle: '☕ 赞助打赏',
    badge: '请喝咖啡',
    title: '支持 ARL-Next 持续维护',
    desc: '如果 ARL-Next 对您的日常资产侦查与安全测试有所帮助，欢迎投喂支持，助力平台更多硬核特性研发！',
    subText: '微信支付 / 支付宝 扫码投喂',
  },

  // 2. 官方公众号配置
  official: {
    tabTitle: '📢 官方公众号',
    badge: '一手资讯',
    title: '关注官方微信公众号',
    name: 'owl安全',
    desc: '第一时间获取 ARL-Next 版本重构动态、指纹库升级以及红蓝对抗资产测绘实战干货。',
    subText: '微信「扫一扫」关注公众号',
  },

  // 3. 作者微信号 / 交流群配置
  wechat: {
    tabTitle: '💬 交流与反馈',
    badge: '技术交流',
    title: '添加作者微信 / 交流群',
    wechatId: 'owl234234', // 请替换为您的实际微信号
    desc: '欢迎添加作者微信交流资产测绘思路、反馈系统 Bug 或申请加入官方安全交流微信群。',
    subText: '微信扫码添加好友，备注「ARL」快速通过',
  }
};
