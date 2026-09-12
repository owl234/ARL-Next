# -*- coding: utf-8 -*-
"""
Geo Pinyin & English normalization table for Chinese administrative divisions and ISPs.
Strictly maps Chinese administrative divisions to official English names / Pinyin and ISO codes.
"""
import re

# 34 省级行政区映射 (包含标准英文名与 ISO 3166-2 代码)
PROVINCE_MAP = {
    "北京": ("Beijing", "BJ"),
    "天津": ("Tianjin", "TJ"),
    "河北": ("Hebei", "HE"),
    "山西": ("Shanxi", "SX"),
    "内蒙古": ("Inner Mongolia", "NM"),
    "辽宁": ("Liaoning", "LN"),
    "吉林": ("Jilin", "JL"),
    "黑龙江": ("Heilongjiang", "HL"),
    "上海": ("Shanghai", "SH"),
    "江苏": ("Jiangsu", "JS"),
    "浙江": ("Zhejiang", "ZJ"),
    "安徽": ("Anhui", "AH"),
    "福建": ("Fujian", "FJ"),
    "江西": ("Jiangxi", "JX"),
    "山东": ("Shandong", "SD"),
    "河南": ("Henan", "HA"),
    "湖北": ("Hubei", "HB"),
    "湖南": ("Hunan", "HN"),
    "广东": ("Guangdong", "GD"),
    "广西": ("Guangxi", "GX"),
    "海南": ("Hainan", "HI"),
    "重庆": ("Chongqing", "CQ"),
    "四川": ("Sichuan", "SC"),
    "贵州": ("Guizhou", "GZ"),
    "云南": ("Yunnan", "YN"),
    "西藏": ("Tibet", "XZ"),
    "陕西": ("Shaanxi", "SN"),
    "甘肃": ("Gansu", "GS"),
    "青海": ("Qinghai", "QH"),
    "宁夏": ("Ningxia", "NX"),
    "新疆": ("Xinjiang", "XJ"),
    "台湾": ("Taiwan", "TW"),
    "香港": ("Hong Kong", "HK"),
    "澳门": ("Macau", "MO"),
}

# 中国全部 340+ 地级市及主要县级市官方英文/拼音规范表
CITY_MAP = {
    # 直辖市 (与省同名)
    "北京": "Beijing", "上海": "Shanghai", "天津": "Tianjin", "重庆": "Chongqing",
    # 河北
    "石家庄": "Shijiazhuang", "唐山": "Tangshan", "秦皇岛": "Qinhuangdao", "邯郸": "Handan",
    "邢台": "Xingtai", "保定": "Baoding", "张家口": "Zhangjiakou", "承德": "Chengde",
    "沧州": "Cangzhou", "廊坊": "Langfang", "衡水": "Hengshui", "雄安": "Xiong'an",
    # 山西
    "太原": "Taiyuan", "大同": "Datong", "阳泉": "Yangquan", "长治": "Changzhi",
    "晋城": "Jincheng", "朔州": "Shuozhou", "晋中": "Jinzhong", "运城": "Yuncheng",
    "忻州": "Xinzhou", "临汾": "Linfen", "吕梁": "Lvliang",
    # 内蒙古
    "呼和浩特": "Hohhot", "包头": "Baotou", "乌海": "Wuhai", "赤峰": "Chifeng",
    "通辽": "Tongliao", "鄂尔多斯": "Ordos", "呼伦贝尔": "Hulunbuir", "巴彦淖尔": "Bayan Nur",
    "乌兰察布": "Ulanqab", "兴安": "Hinggan", "锡林郭勒": "Xilingol", "阿拉善": "Alxa",
    # 辽宁
    "沈阳": "Shenyang", "大连": "Dalian", "鞍山": "Anshan", "抚顺": "Fushun",
    "本溪": "Benxi", "丹东": "Dandong", "锦州": "Jinzhou", "营口": "Yingkou",
    "阜新": "Fuxin", "辽阳": "Liaoyang", "盘锦": "Panjin", "铁岭": "Tieling",
    "朝阳": "Chaoyang", "葫芦岛": "Huludao",
    # 吉林
    "长春": "Changchun", "吉林": "Jilin", "四平": "Siping", "辽源": "Liaoyuan",
    "通化": "Tonghua", "白山": "Baishan", "松原": "Songyuan", "白城": "Baicheng",
    "延边": "Yanbian",
    # 黑龙江
    "哈尔滨": "Harbin", "齐齐哈尔": "Qiqihar", "鸡西": "Jixi", "鹤岗": "Hegang",
    "双鸭山": "Shuangyashan", "大庆": "Daqing", "伊春": "Yichun", "佳木斯": "Jiamusi",
    "七台河": "Qitaihe", "牡丹江": "Mudanjiang", "黑河": "Heihe", "绥化": "Suihua",
    "大兴安岭": "Daxing'anling",
    # 江苏
    "南京": "Nanjing", "无锡": "Wuxi", "徐州": "Xuzhou", "常州": "Changzhou",
    "苏州": "Suzhou", "南通": "Nantong", "连云港": "Lianyungang", "淮安": "Huai'an",
    "盐城": "Yancheng", "扬州": "Yangzhou", "镇江": "Zhenjiang", "泰州": "Taizhou",
    "宿迁": "Suqian", "昆山": "Kunshan", "江阴": "Jiangyin", "张家港": "Zhangjiagang",
    "常熟": "Changshu", "太仓": "Taicang", "宜兴": "Yixing",
    # 浙江
    "杭州": "Hangzhou", "宁波": "Ningbo", "温州": "Wenzhou", "嘉兴": "Jiaxing",
    "湖州": "Huzhou", "绍兴": "Shaoxing", "金华": "Jinhua", "衢州": "Quzhou",
    "舟山": "Zhoushan", "台州": "Taizhou", "丽水": "Lishui", "义乌": "Yiwu",
    "诸暨": "Zhuji", "慈溪": "Cixi", "余姚": "Yuyao", "乐清": "Yueqing", "瑞安": "Rui'an",
    # 安徽
    "合肥": "Hefei", "芜湖": "Wuhu", "蚌埠": "Bengbu", "淮南": "Huainan",
    "马鞍山": "Ma'anshan", "淮北": "Huaibei", "铜陵": "Tongling", "安庆": "Anqing",
    "黄山": "Huangshan", "滁州": "Chuzhou", "阜阳": "Fuyang", "宿州": "Suzhou",
    "六安": "Lu'an", "亳州": "Bozhou", "池州": "Chizhou", "宣城": "Xuancheng",
    # 福建
    "福州": "Fuzhou", "厦门": "Xiamen", "莆田": "Putian", "三明": "Sanming",
    "泉州": "Quanzhou", "漳州": "Zhangzhou", "南平": "Nanping", "龙岩": "Longyan",
    "宁德": "Ningde", "晋江": "Jinjiang", "石狮": "Shishi",
    # 江西
    "南昌": "Nanchang", "景德镇": "Jingdezhen", "萍乡": "Pingxiang", "九江": "Jiujiang",
    "新余": "Xinyu", "鹰潭": "Yingtan", "赣州": "Ganzhou", "吉安": "Ji'an",
    "宜春": "Yichun", "抚州": "Fuzhou", "上饶": "Shangrao",
    # 山东
    "济南": "Jinan", "青岛": "Qingdao", "淄博": "Zibo", "枣庄": "Zaozhuang",
    "东营": "Dongying", "烟台": "Yantai", "潍坊": "Weifang", "济宁": "Jining",
    "泰安": "Tai'an", "威海": "Weihai", "日照": "Rizhao", "临沂": "Linyi",
    "德州": "Dezhou", "聊城": "Liaocheng", "滨州": "Binzhou", "菏泽": "Heze",
    # 河南
    "郑州": "Zhengzhou", "开封": "Kaifeng", "洛阳": "Luoyang", "平顶山": "Pingdingshan",
    "安阳": "Anyang", "鹤壁": "Hebi", "新乡": "Xinxiang", "焦作": "Jiaozuo",
    "濮阳": "Puyang", "许昌": "Xuchang", "漯河": "Luohe", "三门峡": "Sanmenxia",
    "南阳": "Nanyang", "商丘": "Shangqiu", "信阳": "Xinyang", "周口": "Zhoukou",
    "驻马店": "Zhumadian", "济源": "Jiyuan",
    # 湖北
    "武汉": "Wuhan", "黄石": "Huangshi", "十堰": "Shiyan", "宜昌": "Yichang",
    "襄阳": "Xiangyang", "鄂州": "Ezhou", "荆门": "Jingmen", "孝感": "Xiaogan",
    "荆州": "Jingzhou", "黄冈": "Huanggang", "咸宁": "Xianning", "随州": "Suizhou",
    "恩施": "Enshi", "仙桃": "Xiantao", "潜江": "Qianjiang", "天门": "Tianmen",
    # 湖南
    "长沙": "Changsha", "株洲": "Zhuzhou", "湘潭": "Xiangtan", "衡阳": "Hengyang",
    "邵阳": "Shaoyang", "岳阳": "Yueyang", "常德": "Changde", "张家界": "Zhangjiajie",
    "益阳": "Yiyang", "郴州": "Chenzhou", "永州": "Yongzhou", "怀化": "Huaihua",
    "娄底": "Loudi", "湘西": "Xiangxi",
    # 广东
    "广州": "Guangzhou", "韶关": "Shaoguan", "深圳": "Shenzhen", "珠海": "Zhuhai",
    "汕头": "Shantou", "佛山": "Foshan", "江门": "Jiangmen", "湛江": "Zhanjiang",
    "茂名": "Maoming", "肇庆": "Zhaoqing", "惠州": "Huizhou", "梅州": "Meizhou",
    "汕尾": "Shanwei", "河源": "Heyuan", "阳江": "Yangjiang", "清远": "Qingyuan",
    "东莞": "Dongguan", "中山": "Zhongshan", "潮州": "Chaozhou", "揭阳": "Jieyang",
    "云浮": "Yunfu",
    # 广西
    "南宁": "Nanning", "柳州": "Liuzhou", "桂林": "Guilin", "梧州": "Wuzhou",
    "北海": "Beihai", "防城港": "Fangchenggang", "钦州": "Qinzhou", "贵港": "Guigang",
    "玉林": "Yulin", "百色": "Baise", "贺州": "Hezhou", "河池": "Hechi",
    "来宾": "Laibin", "崇左": "Chongzuo",
    # 海南
    "海口": "Haikou", "三亚": "Sanya", "三沙": "Sansha", "儋州": "Danzhou",
    # 四川
    "成都": "Chengdu", "自贡": "Zigong", "攀枝花": "Panzhihua", "泸州": "Luzhou",
    "德阳": "Deyang", "绵阳": "Mianyang", "广元": "Guangyuan", "遂宁": "Suining",
    "内江": "Neijiang", "乐山": "Leshan", "南充": "Nanchong", "眉山": "Meishan",
    "宜宾": "Yibin", "广安": "Guang'an", "达州": "Dazhou", "雅安": "Ya'an",
    "巴中": "Bazhong", "资阳": "Ziyang", "阿坝": "Aba", "甘孜": "Garze", "凉山": "Liangshan",
    # 贵州
    "贵阳": "Guiyang", "六盘水": "Liupanshui", "遵义": "Zunyi", "安顺": "Anshun",
    "毕节": "Bijie", "铜仁": "Tongren", "黔西南": "Qianxinan", "黔东南": "Qiandongnan",
    "黔南": "Qiannan",
    # 云南
    "昆明": "Kunming", "曲靖": "Qujing", "玉溪": "Yuxi", "保山": "Baoshan",
    "昭通": "Zhaotong", "丽江": "Lijiang", "普洱": "Pu'er", "临沧": "Lincang",
    "楚雄": "Chuxiong", "红河": "Honghe", "文山": "Wenshan", "西双版纳": "Xishuangbanna",
    "大理": "Dali", "德宏": "Dehong", "怒江": "Nujiang", "迪庆": "Diqing",
    # 西藏
    "拉萨": "Lhasa", "日喀则": "Shigatse", "昌都": "Chamdo", "林芝": "Nyingchi",
    "山南": "Shannan", "那曲": "Nagqu", "阿里": "Ngari",
    # 陕西
    "西安": "Xi'an", "铜川": "Tongchuan", "宝鸡": "Baoji", "咸阳": "Xianyang",
    "渭南": "Weinan", "延安": "Yan'an", "汉中": "Hanzhong", "榆林": "Yulin",
    "安康": "Ankang", "商洛": "Shangluo",
    # 甘肃
    "兰州": "Lanzhou", "嘉峪关": "Jiayuguan", "金昌": "Jinchang", "白银": "Baiyin",
    "天水": "Tianshui", "武威": "Wuwei", "张掖": "Zhangye", "平凉": "Pingliang",
    "酒泉": "Jiuquan", "庆阳": "Qingyang", "定西": "Dingxi", "陇南": "Longnan",
    "临夏": "Linxia", "甘南": "Gannan",
    # 青海
    "西宁": "Xining", "海东": "Haidong", "海北": "Haibei", "黄南": "Huangnan",
    "海南州": "Hainan", "果洛": "Golog", "玉树": "Yushu", "海西": "Haixi",
    # 宁夏
    "银川": "Yinchuan", "石嘴山": "Shizuishan", "吴忠": "Wuzhong", "固原": "Guyuan",
    "中卫": "Zhongwei",
    # 新疆
    "乌鲁木齐": "Urumqi", "克拉玛依": "Karamay", "吐鲁番": "Turpan", "哈密": "Hami",
    "昌吉": "Changji", "博尔塔拉": "Bortala", "巴音郭楞": "Bayingolin", "阿克苏": "Aksu",
    "克孜勒苏": "Kizilsu", "喀什": "Kashgar", "和田": "Hotan", "伊犁": "Ili",
    "塔城": "Tacheng", "阿勒泰": "Altay",
    # 港澳台
    "香港": "Hong Kong", "澳门": "Macau", "台北": "Taipei", "高雄": "Kaohsiung",
    "台中": "Taichung", "台南": "Tainan", "新北": "New Taipei", "桃园": "Taoyuan",
    "新竹": "Hsinchu", "基隆": "Keelung", "嘉义": "Chiayi"
}

# 常见国内运营商 / 云厂商英文映射
ISP_MAP = {
    # 港澳台知名运营商 (优先匹配，避免被短词误伤)
    "中华电信": "Chunghwa Telecom",
    "台湾大哥大": "Taiwan Mobile",
    "远传电信": "FarEasTone",
    "香港宽频": "HKBN",
    "电讯盈科": "PCCW",
    "和记电讯": "HGC",
    "数码通": "SmarTone",
    "澳门电讯": "CTM",

    # 大陆主流运营商与科技网络
    "电信": "China Telecom",
    "中国电信": "China Telecom",
    "联通": "China Unicom",
    "中国联通": "China Unicom",
    "移动": "China Mobile",
    "中国移动": "China Mobile",
    "铁通": "China Tietong",
    "广电": "China Broadnet",
    "教育网": "CERNET",
    "科技网": "CSTNET",

    # 主流云厂商与 CDN / IDC
    "阿里": "Alibaba",
    "阿里云": "Alibaba",
    "腾讯": "Tencent",
    "腾讯云": "Tencent",
    "华为": "Huawei",
    "华为云": "Huawei",
    "百度": "Baidu",
    "百度云": "Baidu",
    "金山云": "Kingsoft Cloud",
    "京东云": "JD Cloud",
    "火山引擎": "Volcengine",
    "字节跳动": "ByteDance",
    "网宿": "Wangsu Science & Technology",
    "白山云": "Baishan Cloud",
    "长城宽带": "Great Wall Broadband",
}

# 预先按匹配词长度降序排列，确保长词优先于“电信”等短词命中
SORTED_ISP_MAP = sorted(ISP_MAP.items(), key=lambda x: len(x[0]), reverse=True)


def clean_admin_suffix(name: str) -> str:
    """去除省、市、自治区、特别行政区等行政后缀"""
    if not name:
        return ""
    # 特殊全称匹配优先
    for full in ("内蒙古自治区", "广西壮族自治区", "西藏自治区", "宁夏回族自治区", "新疆维吾尔自治区", "香港特别行政区", "澳门特别行政区"):
        if name.startswith(full[:2]) or name == full:
            return full[:3] if "内蒙古" in full else full[:2]

    suffixes = ("特别行政区", "壮族自治区", "回族自治区", "维吾尔自治区", "自治区", "自治州", "地区", "省", "市", "县", "盟", "旗")
    clean = name
    for s in suffixes:
        if clean.endswith(s) and len(clean) > len(s):
            clean = clean[:-len(s)]
            break
    return clean


def normalize_region(raw_region: str) -> tuple:
    """
    将中文省份归一化为标准英文名与代码
    返回: (region_name, region_code)
    """
    if not raw_region or raw_region in ("0", "None", "null", "未知"):
        return None, None

    # 直接匹配
    if raw_region in PROVINCE_MAP:
        return PROVINCE_MAP[raw_region]

    # 去后缀匹配
    cleaned = clean_admin_suffix(raw_region)
    if cleaned in PROVINCE_MAP:
        return PROVINCE_MAP[cleaned]

    # 前缀 2-3 字匹配
    for p_name, info in PROVINCE_MAP.items():
        if raw_region.startswith(p_name):
            return info

    # 若原本就是英文（如海外 IP 经 ip2region 返回英文地区）
    if re.match(r"^[A-Za-z\s\.\-']+$", raw_region):
        return raw_region.strip(), None

    return raw_region.strip(), None


def normalize_city(raw_city: str, region_name: str = None) -> str:
    """
    将中文城市归一化为官方英文/拼音
    """
    if not raw_city or raw_city in ("0", "None", "null", "未知"):
        return None

    # 直辖市特判
    if region_name in ("Beijing", "Shanghai", "Tianjin", "Chongqing"):
        return region_name

    # 直接匹配
    if raw_city in CITY_MAP:
        return CITY_MAP[raw_city]

    # 去后缀匹配
    cleaned = clean_admin_suffix(raw_city)
    if cleaned in CITY_MAP:
        return CITY_MAP[cleaned]

    for c_name, en_name in CITY_MAP.items():
        if raw_city.startswith(c_name):
            return en_name

    # 若原本就是纯英文
    if re.match(r"^[A-Za-z\s\.\-']+$", raw_city):
        return raw_city.strip()

    return cleaned


def normalize_isp(raw_isp: str) -> str:
    """将 ISP / 运营商名称归一化（长词优先匹配）"""
    if not raw_isp or raw_isp in ("0", "None", "null", "未知"):
        return None
    for k, v in SORTED_ISP_MAP:
        if k in raw_isp:
            return v
    return raw_isp.strip()


def parse_ip2region_record(raw_str: str) -> dict:
    """
    解析 ip2region 返回的格式字符串:
    标准格式: 国家|省份/区域|城市|ISP|国别代码 (由 ip2region_v4 输出)
    返回干净的英文 Geo 字典
    """
    if not raw_str:
        return {}

    parts = raw_str.split("|")
    while len(parts) < 5:
        parts.append("0")

    raw_country, raw_region, raw_city, raw_isp, raw_cc = parts[:5]

    if raw_country in ("0", "Reserved", "未分配", "内网IP"):
        return {}

    country_name = "China" if raw_country in ("中国", "CN") else raw_country
    country_code = "CN" if country_name == "China" else (raw_cc if raw_cc != "0" else None)

    region_name, region_code = normalize_region(raw_region)
    city_name = normalize_city(raw_city, region_name)
    isp_name = normalize_isp(raw_isp)

    return {
        "country_name": country_name,
        "country_code": country_code,
        "region_name": region_name,
        "region_code": region_code,
        "city": city_name,
        "isp": isp_name,
    }
