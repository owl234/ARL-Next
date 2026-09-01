import re
from app.utils import get_logger
from pyparsing import CaselessLiteral, Word, alphas,\
    nums, QuotedString, Group,ParserElement, infixNotation, opAssoc, ParseException

ParserElement.enablePackrat()


logger = get_logger()

# 定义操作符
equals = CaselessLiteral("=")
contains = CaselessLiteral("==")
not_contains = CaselessLiteral("!=")
regex_match = CaselessLiteral("~=") | CaselessLiteral("~")
and_op = CaselessLiteral("&&")
or_op = CaselessLiteral("||")
not_op = CaselessLiteral("!")

# 定义变量和值的语法
variable = Word(alphas + "_")

integer = Word(nums)

escape_char = "\\"
quoted_string = QuotedString('"', escChar=escape_char, unquoteResults=False)

# 允许未被双引号包裹的普通字符作为 value（比如 body=X_FIB_Register）以最大化语法兼容性
bare_word = Word(alphas + nums + "_-")
value = quoted_string | integer | bare_word


# 归拢所有的比较操作符，将长操作符置于短操作符之前防止 eager matching 截断
comparison_op = contains | not_contains | regex_match | equals
atom_expr = Group(variable + comparison_op + value) | Group(not_op + variable)

# 定义表达式语法
bool_expr = infixNotation(
    atom_expr,
    [
        (not_op, 1, opAssoc.RIGHT),
        (and_op, 2, opAssoc.LEFT),
        (or_op, 2, opAssoc.LEFT),
    ]
)


from functools import lru_cache

@lru_cache(maxsize=150000)
def get_compiled_pattern(pattern):
    return re.compile(pattern, re.IGNORECASE)

# 定义操作符
def safe_regex_match(x, pattern):
    try:
        clean_pat = pattern.strip('"')
        compiled_pat = get_compiled_pattern(clean_pat)
        return bool(compiled_pat.search(str(x)))
    except Exception:
        return False

operators = {
    '==': lambda x, y: x == y,
    '!=': lambda x, y: x not in y,
    '=': lambda x, y: x in y,
    '~=': safe_regex_match,
    '~': safe_regex_match,
    '!': lambda x: not x,
    '&&': lambda x, y: x and y,
    '||': lambda x, y: x or y
}


# 对双引号包裹的字符串进行 unquote
def unquote_string(s):
    # 去掉引号
    s = s[1:-1]

    # 处理转义字符
    s = s.replace('\\\\', '\\')
    s = s.replace('\\n', '\n')
    s = s.replace('\\t', '\t')
    s = s.replace('\\r', '\r')
    s = s.replace('\\"', '"')

    return s


def preprocess_expression(expr: str) -> str:
    """
    [指纹规则预处理器]
    1. 自动重映射变量: 比如将 server="xxx" 转换为 header="xxx"（在 ARL 中 Server 通常也包含在 Header 中），
       从而避免 Unknown variable 报错并能有效比对。
    2. 解决嵌套双引号冲突: 匹配 body="<a href="http://...">" 形式的不规范双引号，将内部嵌套的引号进行反斜杠转义。
    """
    # 1. 变量映射
    expr = re.sub(r'\bserver\s*(=|==|!=)\s*', r'header\1', expr)

    # 2. 引号转义处理
    pattern = r'\b([a-zA-Z0-9_\-]+)\s*(=|==|!=|~=|~)\s*"'
    pos = 0
    result = []
    
    while True:
        match = re.search(pattern, expr[pos:])
        if not match:
            result.append(expr[pos:])
            break
            
        start_idx = pos + match.start()
        result.append(expr[pos:start_idx])
        
        var_name = match.group(1)
        op = match.group(2)
        
        rem = expr[pos + match.end():]
        close_pat = r'"(?:\s*\)*\s*(?:\|\||&&)\s*\(*\s*[a-zA-Z0-9_\-]+\s*(?:=|==|!=|~=|~)\s*"|$)'
        close_match = re.search(close_pat, rem)
        if close_match:
            close_quote_idx = close_match.start()
            content = rem[:close_quote_idx]
            content_cleaned = content.replace('\\"', '"').replace('"', '\\"')
            result.append(f'{var_name}{op}"{content_cleaned}"')
            pos = pos + match.end() + close_quote_idx + 1
        else:
            last_quote_idx = rem.rfind('"')
            if last_quote_idx != -1:
                content = rem[:last_quote_idx]
                content_cleaned = content.replace('\\"', '"').replace('"', '\\"')
                result.append(f'{var_name}{op}"{content_cleaned}"')
                result.append(rem[last_quote_idx + 1:])
                pos = pos + match.end() + len(rem)
            else:
                result.append(expr[start_idx:pos + match.end()])
                pos = pos + match.end()
                
    return "".join(result)


# 解析表达式
def parse_expression(expression):
    expression = preprocess_expression(expression)
    result = bool_expr.parseString(expression, parseAll=True)
    return result.as_list()


DANGEROUS_STOPWORDS = {
    # 1. HTML meta & common attributes
    "description", "image", "content", "name", "author", "version", 
    "platform", "generator", "publisher", "copyright", "title", 
    "viewport", "keywords", "application-name", "default", "icon", 
    "text", "style", "main", "admin", "index", "user", "password", 
    "submit", "button", "footer", "header", "wrapper", "unclosed string",
    "var json = json.parse", "powered-by", "progid", "web_author", "designer",
    "username", "email", "search", "robots", "refresh", "expires",
    
    # 2. Generic JS code / URL patterns
    "window.location", "location.href", "document.location", "shortcut icon",
    "product", "framwork", "convert", "theme", "host", "server", "download",
    "reporter", "action.php", "plugins", "modules", "redirect", "baseurl", "list",
    "<span>no</span>", "fastjson",
    
    # 3. Generic login/index file names as body clause
    "login.jsp", "login.php", "login.aspx", "admin.php", "index.php", "index.html",
    "default.aspx", "home.php", "index.jsp", "index.do", "home.html", "about",
    "contact", "search", "help", "faq", "error", "404", "500", "forbidden",
    
    # 4. Generic Chinese phrases / error page text
    "入口校验失败", "没有找到站点", "可能原因", "cdn产品", "web服务",
    "检查端口是否正确", "/login", "系统自动生成", "扫码登录更安全",
    "站点创建成功", "文件服务器", "网络准入", "360", "3600防火墙", "防火墙", "防病毒",
    "主账套", "天融信", "广联达", "孚盟云", "明源云", "管理员",
    
    # 5. Short tokens
    "dns", "nas", "vpn", "crm", "cms", "vue", "ext", "iam", "prd",
    "vdi", "vwo", "ywa", "aui", "ce2", "uet", "spr", "h3c", "ait",
    "cws", "jit", "jqt", "llc", "lli", "nps", "usm", "vop", "wcm", "wwp",
    "a1", "_pa", "=fs", "sp=", "atom", "boei", "divi"
}


def is_bad_clause_content(var: str, val: str) -> bool:
    var_lower = str(var).lower()
    val_clean = unquote_string(val) if isinstance(val, str) and val.startswith('"') and val.endswith('"') else str(val)
    val_lower = val_clean.strip().lower()
    
    if val_lower in DANGEROUS_STOPWORDS:
        return True
    if var_lower in ("body", "title") and len(val_clean.strip()) <= 2:
        return True
    if var_lower == "body" and val_clean.strip().isdigit() and len(val_clean.strip()) <= 4:
        return True
    return False


#  递归求值
def evaluate_expression(parsed, variables):
    if isinstance(parsed, str):
        if parsed in variables:
            return variables[parsed]
        elif parsed.startswith('"'):
            return unquote_string(parsed)
        else:
            # 优雅降级：遇到任何未定义的变量，隐式返回空字符串
            return ""

    elif len(parsed) == 1:
        return evaluate_expression(parsed[0], variables)
    elif len(parsed) == 2:
        return operators[parsed[0]](evaluate_expression(parsed[1], variables))
    elif len(parsed) == 3:
        var = parsed[0]
        op = parsed[1]
        val = parsed[2]
        # 引擎层安全防御：若原子条件为泛化停用词或极短无意义词，直接判定不匹配
        if op in ('=', '==', '~=', '~') and is_bad_clause_content(var, val):
            return False
        return operators[op](evaluate_expression(val, variables), evaluate_expression(var, variables))
    elif len(parsed) > 3 and len(parsed) % 2 == 1:
        val = evaluate_expression(parsed[0], variables)
        for i in range(1, len(parsed), 2):
            op = parsed[i]
            next_val = evaluate_expression(parsed[i+1], variables)
            val = operators[op](val, next_val)
        return val



def evaluate(expression, variables):
    parsed = parse_expression(expression)
    return evaluate_expression(parsed, variables)


def _check_expression(expression):
    variables = {
        'body': "",
        'header': "",
        'title': "",
        'icon_hash': ""
    }
    try:
        parsed = parse_expression(expression)
        
        # 检查是否全部由垃圾停用词构成
        def extract_atoms(node):
            atoms = []
            if isinstance(node, list):
                if len(node) == 3 and isinstance(node[0], str) and isinstance(node[1], str):
                    atoms.append((node[0], node[1], node[2]))
                else:
                    for child in node:
                        atoms.extend(extract_atoms(child))
            return atoms
            
        atoms = extract_atoms(parsed)
        if atoms:
            all_bad = all(is_bad_clause_content(a[0], a[2]) for a in atoms)
            if all_bad:
                raise ValueError(f"规则包含高危泛化词/无意义原子条件，已拦截: {expression}")
                
        return evaluate_expression(parsed, variables)
    except ParseException as e:
        raise ValueError(f"Invalid expression: {expression}  exception: {e}")
    except ValueError as e:
        raise e
    except Exception as e:
        raise ValueError(f"Error evaluating expression: {expression} exception: {e}")


def check_expression(expression):
    try:
        _check_expression(expression)
        return True
    except ValueError as e:
        logger.error(e)
        return False


def check_expression_with_error(expression):
    try:
        _check_expression(expression)
        return True, None
    except ValueError as e:
        return False, e


