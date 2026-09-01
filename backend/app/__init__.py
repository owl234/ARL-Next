import warnings

# 关闭警告
warnings.filterwarnings("ignore", category=UserWarning,
                        message="Python 3.6 is no longer supported by the Python core team")

# 关闭高权限使用celery警告
warnings.filterwarnings("ignore", category=UserWarning,
                        message="You're running the worker with superuser privileges")

# 修复高版本 Numpy 移除 float、int、object 等属性导致旧版 openpyxl 报错的问题
try:
    import numpy as np
    for attr, target in [('float', float), ('int', int), ('object', object), ('bool', bool), ('complex', complex), ('typeDict', getattr(np, 'sctypeDict', {}))]:
        try:
            setattr(np, attr, target)
        except Exception:
            pass
except ImportError:
    pass
