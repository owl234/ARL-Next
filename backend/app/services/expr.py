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


# 定义操作符
def safe_regex_match(x, pattern):
    try:
        clean_pat = pattern.strip('"')
        return bool(re.search(clean_pat, str(x), re.IGNORECASE))
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
        return operators[parsed[1]](evaluate_expression(parsed[2], variables), evaluate_expression(parsed[0], variables))
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
        return evaluate(expression, variables)
    except ParseException as e:
        raise ValueError(f"Invalid expression: {expression}  exception: {e}")
    except Exception as e:
        raise ValueError(f"Error evaluating expression: {expression} exception: {e}")


def check_expression(expression):
    try:
        _check_expression(expression)
        return True
    except ValueError as e:
        logger.error(e)
        # import traceback
        # traceback.print_exception(type(e), e, e.__traceback__)
        return False


def check_expression_with_error(expression):
    try:
        _check_expression(expression)
        return True, None,
    except ValueError as e:
        return False, e

