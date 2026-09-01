import os
import contextlib
from app.utils import get_logger

logger = get_logger()

@contextlib.contextmanager
def file_lock(f, exclusive=True):
    """
    跨进程/线程文件排他锁与共享锁（基于 fcntl.flock）
    """
    try:
        import fcntl
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(f.fileno(), mode)
        try:
            yield
        finally:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
    except (ImportError, AttributeError, OSError):
        # 兼容不支持 fcntl 的极少数系统环境
        yield


# 系统内置核心资产字典白名单（严禁彻底物理删除，防止扫描任务中断）
BUILTIN_ASSET_DICTS = {
    'domain_2w.txt',
    'domain_top300.txt',
    'altdnsdict.txt',
    'dnsserver.txt',
    'file_top_200.txt',
    'file_top_2000.txt',
    'port_top100.txt',
    'port_top1000.txt',
    'port_custom.txt',
    'port_all.txt',
    'blackdomain.txt',
    'black_asset_site.txt',
    'blackhexie.txt',
}

# 系统内置核心弱口令字典白名单（严禁彻底物理删除）
BUILTIN_BRUTE_DICTS = {
    'common_password.txt',
    'username_ssh.txt',
    'password_ssh.txt',
    'username_ftp.txt',
    'password_ftp.txt',
    'username_mysql.txt',
    'password_mysql.txt',
    'username_redis.txt',
    'password_redis.txt',
    'username_mongodb.txt',
    'password_mongodb.txt',
    'username_postgresql.txt',
    'password_postgresql.txt',
    'username_sqlserver.txt',
    'password_sqlserver.txt',
    'username_rdp.txt',
    'password_rdp.txt',
    'username_tomcat.txt',
    'password_tomcat.txt',
    'username_jenkins.txt',
    'password_jenkins.txt',
    'username_gitlab.txt',
    'password_gitlab.txt',
    'username_grafana.txt',
    'password_grafana.txt',
    'username_harbor.txt',
    'password_harbor.txt',
    'username_nexus.txt',
    'password_nexus.txt',
    'username_nacos.txt',
    'password_nacos.txt',
    'username_apisix.txt',
    'password_apisix.txt',
    'username_activemq.txt',
    'password_activemq.txt',
    'username_alibaba-druid.txt',
    'password_alibaba-druid.txt',
    'username_clickhouse.txt',
    'password_clickhouse.txt',
    'username_csts.txt',
    'password_csts.txt',
    'username_exchange.txt',
    'password_exchange.txt',
    'username_imap.txt',
    'password_imap.txt',
    'username_manageiq.txt',
    'password_manageiq.txt',
    'username_openfire.txt',
    'password_openfire.txt',
    'username_pop3.txt',
    'password_pop3.txt',
    'username_shiro.txt',
    'password_shiro.txt',
    'username_smtp.txt',
    'password_smtp.txt',
}

def is_builtin_dict(filename, is_brute=False):
    """判断是否为系统内置核心字典"""
    if is_brute:
        return filename in BUILTIN_BRUTE_DICTS
    return filename in BUILTIN_ASSET_DICTS


def count_file_lines(path):
    """
    通过 1MB 块二进制读取极速统计行数，比常规 Python for 循环快 20-50 倍，
    并精确探测文件末尾无换行符的情形。
    """
    if not os.path.exists(path):
        return 0
    try:
        count = 0
        last_byte = b'\n'
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                count += chunk.count(b'\n')
                if chunk:
                    last_byte = chunk[-1:]
        # 若文件非空且最后一个字节不是换行符，补计最后 1 行
        if count == 0:
            if os.path.getsize(path) > 0:
                return 1
            return 0
        elif last_byte != b'\n':
            count += 1
        return count
    except Exception as e:
        logger.error(f"Error counting lines in {path}: {e}")
        return 0


def append_to_dict_file(path, new_entries_str):
    """
    向字典追加条目（自动去重、清洗空白行与 BOM 字符、并发文件锁保护、仅追加增量行避免全量重写）
    """
    new_entries = [line.strip().lstrip('\ufeff') for line in new_entries_str.split('\n') if line.strip().lstrip('\ufeff')]
    if not new_entries:
        return 0, 0

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a+', encoding='utf-8', errors='ignore') as f:
            with file_lock(f, exclusive=True):
                f.seek(0)
                existing_set = set()
                for line in f:
                    stripped = line.strip().lstrip('\ufeff')
                    if stripped:
                        existing_set.add(stripped)

                to_append = []
                for e in new_entries:
                    if e not in existing_set:
                        existing_set.add(e)
                        to_append.append(e)

                if to_append:
                    # 检查已有文件末尾是否缺少换行符（通过底层 buffer 安全检查字节）
                    f.flush()
                    try:
                        f.buffer.seek(0, os.SEEK_END)
                        pos = f.buffer.tell()
                        if pos > 0:
                            f.buffer.seek(pos - 1)
                            if f.buffer.read(1) != b'\n':
                                f.write('\n')
                    except Exception:
                        pass

                    f.seek(0, os.SEEK_END)
                    f.write('\n'.join(to_append) + '\n')
                    f.flush()

                return len(new_entries), len(to_append)
    except Exception as e:
        logger.error(f"Error appending to {path}: {e}")
        raise e


def delete_entries_from_dict_file(path, entries_to_delete_set):
    """
    从字典中批量剔除条目（并发文件锁保护）
    """
    if not entries_to_delete_set:
        return 0

    if not os.path.exists(path):
        return 0

    deleted_count = 0
    try:
        with open(path, 'r+', encoding='utf-8', errors='ignore') as f:
            with file_lock(f, exclusive=True):
                f.seek(0)
                retained = []
                for line in f:
                    stripped = line.strip().lstrip('\ufeff')
                    if stripped in entries_to_delete_set:
                        deleted_count += 1
                    else:
                        if stripped:
                            retained.append(stripped)

                if deleted_count > 0:
                    f.seek(0)
                    f.truncate(0)
                    if retained:
                        f.write('\n'.join(retained) + '\n')
                    f.flush()

        return deleted_count
    except Exception as e:
        logger.error(f"Error deleting entries from {path}: {e}")
        raise e
