import hashlib
from .expr import parse_expression, evaluate_expression

# 缓存，避免重复解析
parsed_cache = {}


class FingerPrint:
    def __init__(self, app_name: str, human_rule: str):
        self.app_name = app_name
        self.human_rule = human_rule
        self.parsed = None
        self.has_not_or_regex = False
        self.literals = {'body': set(), 'header': set(), 'title': set()}

    def _extract(self, parsed):
        if self.has_not_or_regex:
            return
        
        if isinstance(parsed, str):
            return

        if len(parsed) == 1:
            self._extract(parsed[0])
            return
            
        if len(parsed) == 2:
            if parsed[0] == '!':
                self.has_not_or_regex = True
            else:
                self._extract(parsed[1])
            return
            
        if len(parsed) >= 3 and len(parsed) % 2 == 1:
            # Boolean logic operations
            if parsed[1] in ('||', '&&'):
                for i in range(0, len(parsed), 2):
                    self._extract(parsed[i])
                return
            elif len(parsed) == 3:
                # Atom: [var, op, val]
                var = parsed[0]
                op = parsed[1]
                val = parsed[2]
                
                if op in ('~=', '~', '!='):
                    self.has_not_or_regex = True
                    return
                elif op in ('=', '=='):
                    if isinstance(var, str) and var in self.literals and isinstance(val, str) and val.startswith('"'):
                        from .expr import unquote_string, is_bad_clause_content
                        if not is_bad_clause_content(var, val):
                            clean_val = unquote_string(val)
                            if clean_val:
                                # 长度太短的字面量不作为短路条件，防止短路失败率过高
                                if len(clean_val) >= 2:
                                    self.literals[var].add(clean_val)
                return

        # Fallback for unexpected structure
        self.has_not_or_regex = True

    def identify(self, variables: dict) -> bool:
        if self.parsed is None:
            self.build_parsed()

        if self.parsed is False:
            return False

        return evaluate_expression(self.parsed, variables)

    def build_parsed(self):
        rule_hash = hashlib.md5(self.human_rule.encode()).hexdigest()
        if rule_hash in parsed_cache:
            cached_data = parsed_cache[rule_hash]
            self.parsed = cached_data['parsed']
            self.has_not_or_regex = cached_data['has_not_or_regex']
            self.literals = {k: set(v) for k, v in cached_data['literals'].items()}
        else:
            try:
                self.parsed = parse_expression(self.human_rule)
                self._extract(self.parsed)
            except Exception as e:
                from app.utils import get_logger
                get_logger().warning(f"Failed to parse rule {self.app_name}: {e}")
                self.parsed = False
                self.has_not_or_regex = True
            parsed_cache[rule_hash] = {
                'parsed': self.parsed,
                'has_not_or_regex': self.has_not_or_regex,
                'literals': {k: set(v) for k, v in self.literals.items()}
            }
