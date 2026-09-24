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


def get_dict_lock_path(dict_path: str) -> str:
    """
    获取字典专属的独立配套排他锁文件路径。
    保持独立锁文件 inode 不可变，彻底消除 os.replace 替换原文件导致的锁失效与并发覆盖竞态。
    """
    return dict_path + ".lock"


@contextlib.contextmanager
def dict_lock(dict_path: str, exclusive: bool = True):
    """
    字典文件生命周期排他锁上下文管理器。
    自动创建并持有 <dict_path>.lock 文件锁，完整覆盖从数据读取、临时文件写入到原子替换的全周期。
    """
    os.makedirs(os.path.dirname(dict_path), exist_ok=True)
    lock_path = get_dict_lock_path(dict_path)
    with open(lock_path, 'a') as f_lock:
        with file_lock(f_lock, exclusive=exclusive):
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


import hashlib
import uuid


def hash_dict_entry(entry: str) -> bytes:
    """
    计算字典条目的 64 位紧凑 Blake2b 二进制哈希（仅 8 字节）。
    在百万级大字典去重时将单条条目内存从 60~80 字节降至 8 字节，节约 90%+ 内存占用。
    """
    return hashlib.blake2b(entry.encode('utf-8', errors='ignore'), digest_size=8).digest()


def create_dict_file(path, content):
    """
    流式创建字典文件（64位紧凑哈希去重、原子写盘、排他锁保护）
    避免将大字典拆分为巨型列表和全量 join 导致内存激增。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    seen_hashes = set()
    dir_name = os.path.dirname(path)
    base_name = os.path.basename(path)
    tmp_path = os.path.join(dir_name, f".tmp_create_{base_name}_{uuid.uuid4().hex}")

    try:
        count = 0
        with open(tmp_path, 'w', encoding='utf-8', errors='ignore') as f_out:
            for line in content.splitlines():
                stripped = line.strip().lstrip('\ufeff')
                if stripped:
                    h = hash_dict_entry(stripped)
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        f_out.write(stripped + '\n')
                        count += 1
        with dict_lock(path, exclusive=True):
            os.replace(tmp_path, path)
        return count
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        logger.error(f"Error creating dictionary file {path}: {e}")
        raise e


def append_to_dict_file(path, new_entries_str):
    """
    向字典追加条目（64位紧凑哈希自动去重、清洗空白行与 BOM 字符、并发文件锁保护、流式增量追加避免全量重写）
    """
    new_entries = [line.strip().lstrip('\ufeff') for line in new_entries_str.splitlines() if line.strip().lstrip('\ufeff')]
    if not new_entries:
        return 0, 0

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with dict_lock(path, exclusive=True):
            with open(path, 'a+', encoding='utf-8', errors='ignore') as f:
                f.seek(0)
                existing_hashes = set()
                for line in f:
                    stripped = line.strip().lstrip('\ufeff')
                    if stripped:
                        existing_hashes.add(hash_dict_entry(stripped))

                to_append_count = 0
                f.flush()
                # 检查已有文件末尾是否缺少换行符
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
                for e in new_entries:
                    h = hash_dict_entry(e)
                    if h not in existing_hashes:
                        existing_hashes.add(h)
                        f.write(e + '\n')
                        to_append_count += 1
                f.flush()

                return len(new_entries), to_append_count
    except Exception as e:
        logger.error(f"Error appending to {path}: {e}")
        raise e


def delete_entries_from_dict_file(path, entries_to_delete_set):
    """
    从字典中批量剔除条目（基于 64位紧凑哈希集合 + 逐行流式读写 + 临时文件原子替换，内存严格受控于待删除集体积）
    """
    if not entries_to_delete_set or not os.path.exists(path):
        return 0

    delete_hashes = {hash_dict_entry(e) for e in entries_to_delete_set if e}
    if not delete_hashes:
        return 0

    deleted_count = 0
    dir_name = os.path.dirname(path)
    base_name = os.path.basename(path)
    tmp_path = os.path.join(dir_name, f".tmp_del_{base_name}_{uuid.uuid4().hex}")

    try:
        with dict_lock(path, exclusive=True):
            if not os.path.exists(path):
                return 0

            with open(path, 'r', encoding='utf-8', errors='ignore') as f_in, \
                 open(tmp_path, 'w', encoding='utf-8', errors='ignore') as f_out:
                for line in f_in:
                    stripped = line.strip().lstrip('\ufeff')
                    if stripped and hash_dict_entry(stripped) in delete_hashes:
                        deleted_count += 1
                    elif stripped:
                        f_out.write(stripped + '\n')
                f_out.flush()

            if deleted_count > 0:
                os.replace(tmp_path, path)
            else:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        return deleted_count
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        logger.error(f"Error deleting entries from {path}: {e}")
        raise e
