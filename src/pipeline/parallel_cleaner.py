"""
parallel_cleaner.py 鈥?骞惰娓呮礂鍣?
鏀寔鎵归噺鏂囦欢骞惰娓呮礂锛屾彁鍗囨竻娲楅€熷害3-5鍊?
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CleaningTask:
    """娓呮礂浠诲姟"""

    file_path: str
    file_hash: str
    file_size: int
    status: str = "pending"  # pending, processing, completed, failed
    result: Optional[Dict] = None
    error: Optional[str] = None
    start_time: float = 0
    end_time: float = 0


class IncrementalCleaner:
    """澧為噺娓呮礂鍣?鈥?璺宠繃宸叉竻娲楁枃浠?""

    def __init__(self, state_file: str = "cleaning_state.json"):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """鍔犺浇娓呮礂鐘舵€?""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"鍔犺浇娓呮礂鐘舵€佸け璐? {e}")
        return {}

    def _save_state(self):
        """淇濆瓨娓呮礂鐘舵€?""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"淇濆瓨娓呮礂鐘舵€佸け璐? {e}")

    def get_file_hash(self, file_path: str) -> str:
        """璁＄畻鏂囦欢hash锛堝熀浜庢枃浠惰矾寰?澶у皬+淇敼鏃堕棿锛?""
        try:
            stat = os.stat(file_path)
            content = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
            return hashlib.sha256(content.encode()).hexdigest()
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            #  fallback: 鍩轰簬鏂囦欢璺緞
            return hashlib.sha256(file_path.encode()).hexdigest()

    def need_cleaning(self, file_path: str) -> bool:
        """妫€鏌ユ枃浠舵槸鍚﹂渶瑕佹竻娲?""
        file_hash = self.get_file_hash(file_path)

        # 妫€鏌ユ槸鍚﹀凡娓呮礂
        if file_hash in self.state:
            entry = self.state[file_hash]
            # 妫€鏌ユ枃浠舵槸鍚﹁淇敼
            if entry.get("status") == "completed":
                try:
                    current_stat = os.stat(file_path)
                    saved_size = entry.get("file_size", 0)
                    saved_mtime = entry.get("file_mtime", 0)

                    # 鏂囦欢澶у皬鎴栦慨鏀规椂闂村彉鍖栵紝闇€瑕侀噸鏂版竻娲?
                    if current_stat.st_size != saved_size or current_stat.st_mtime != saved_mtime:
                        logger.info(f"鏂囦欢宸蹭慨鏀癸紝闇€瑕侀噸鏂版竻娲? {file_path}")
                        return True

                    logger.info(f"鏂囦欢宸叉竻娲楋紝璺宠繃: {file_path}")
                    return False
                except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                    return True
            elif entry.get("status") == "failed":
                # 澶辫触鐨勪换鍔″彲浠ラ噸璇?
                return True

        return True

    def mark_cleaning(self, file_path: str):
        """鏍囪鏂囦欢寮€濮嬫竻娲?""
        file_hash = self.get_file_hash(file_path)
        try:
            stat = os.stat(file_path)
            self.state[file_hash] = {
                "file_path": file_path,
                "file_hash": file_hash,
                "file_size": stat.st_size,
                "file_mtime": stat.st_mtime,
                "status": "processing",
                "start_time": time.time(),
            }
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            self.state[file_hash] = {
                "file_path": file_path,
                "file_hash": file_hash,
                "status": "processing",
                "start_time": time.time(),
            }
        self._save_state()

    def mark_completed(self, file_path: str, result: Dict):
        """鏍囪鏂囦欢娓呮礂瀹屾垚"""
        file_hash = self.get_file_hash(file_path)
        if file_hash in self.state:
            self.state[file_hash].update(
                {
                    "status": "completed",
                    "end_time": time.time(),
                    "result_summary": {
                        "text_length": len(result.get("text", "")),
                        "chunks_count": len(result.get("chunks", [])),
                    },
                }
            )
            self._save_state()

    def mark_failed(self, file_path: str, error: str):
        """鏍囪鏂囦欢娓呮礂澶辫触"""
        file_hash = self.get_file_hash(file_path)
        if file_hash in self.state:
            self.state[file_hash].update({"status": "failed", "end_time": time.time(), "error": error})
            self._save_state()

    def get_stats(self) -> Dict:
        """鑾峰彇娓呮礂缁熻"""
        total = len(self.state)
        completed = len([v for v in self.state.values() if v.get("status") == "completed"])
        failed = len([v for v in self.state.values() if v.get("status") == "failed"])
        processing = len([v for v in self.state.values() if v.get("status") == "processing"])

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "success_rate": completed / total * 100 if total > 0 else 0,
        }


class ParallelCleaner:
    """骞惰娓呮礂鍣?鈥?鏀寔澶氳繘绋?澶氱嚎绋嬪苟琛屾竻娲?""

    def __init__(self, max_workers: int = 4, use_process_pool: bool = True):
        self.max_workers = max_workers
        self.use_process_pool = use_process_pool
        self.incremental = IncrementalCleaner()

        # 鏍规嵁浠诲姟绫诲瀷閫夋嫨鎵ц鍣?
        if use_process_pool:
            self.executor = ProcessPoolExecutor(max_workers=max_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def clean_single_file(self, file_path: str, cleaner_func) -> CleaningTask:
        """娓呮礂鍗曚釜鏂囦欢"""
        task = CleaningTask(
            file_path=file_path,
            file_hash=self.incremental.get_file_hash(file_path),
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        )

        # 妫€鏌ユ槸鍚﹂渶瑕佹竻娲?
        if not self.incremental.need_cleaning(file_path):
            task.status = "completed"
            task.result = {"skipped": True, "reason": "already_cleaned"}
            return task

        # 鏍囪寮€濮嬫竻娲?
        self.incremental.mark_cleaning(file_path)
        task.status = "processing"
        task.start_time = time.time()

        try:
            # 鍦ㄧ嚎绋嬫睜涓墽琛屾竻娲?
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, cleaner_func, file_path)

            task.result = result
            task.status = "completed"
            task.end_time = time.time()

            # 鏍囪瀹屾垚
            self.incremental.mark_completed(file_path, result)

            logger.info(f"鏂囦欢娓呮礂瀹屾垚: {file_path} ({task.end_time - task.start_time:.2f}s)")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.end_time = time.time()

            # 鏍囪澶辫触
            self.incremental.mark_failed(file_path, str(e))

            logger.error(f"鏂囦欢娓呮礂澶辫触: {file_path} - {e}")

        return task

    async def clean_batch(self, file_paths: List[str], cleaner_func) -> List[CleaningTask]:
        """鎵归噺骞惰娓呮礂"""
        logger.info(f"寮€濮嬫壒閲忔竻娲? {len(file_paths)} 涓枃浠? 骞跺彂鏁? {self.max_workers}")

        start_time = time.time()

        # 鍒涘缓鎵€鏈変换鍔?
        tasks = [self.clean_single_file(fp, cleaner_func) for fp in file_paths]

        # 骞惰鎵ц
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 澶勭悊寮傚父
        cleaning_tasks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task = CleaningTask(
                    file_path=file_paths[i],
                    file_hash=self.incremental.get_file_hash(file_paths[i]),
                    file_size=0,
                    status="failed",
                    error=str(result),
                )
            else:
                task = result
            cleaning_tasks.append(task)

        end_time = time.time()
        total_time = end_time - start_time

        # 缁熻缁撴灉
        completed = len([t for t in cleaning_tasks if t.status == "completed"])
        failed = len([t for t in cleaning_tasks if t.status == "failed"])
        skipped = len([t for t in cleaning_tasks if t.result and t.result.get("skipped")])

        logger.info(f"鎵归噺娓呮礂瀹屾垚: 鎴愬姛 {completed}, 澶辫触 {failed}, 璺宠繃 {skipped}, 鑰楁椂 {total_time:.2f}s")

        return cleaning_tasks

    def get_stats(self) -> Dict:
        """鑾峰彇娓呮礂缁熻"""
        return {
            "parallel": {"max_workers": self.max_workers, "use_process_pool": self.use_process_pool},
            "incremental": self.incremental.get_stats(),
        }


class ChunkCache:
    """鍒嗗潡缂撳瓨鍣?鈥?缂撳瓨宸插垎鍧楃粨鏋滐紝閬垮厤閲嶅澶勭悊"""

    def __init__(self, cache_dir: str = "chunk_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, file_hash: str) -> str:
        """鑾峰彇缂撳瓨鏂囦欢璺緞"""
        return os.path.join(self.cache_dir, f"{file_hash}.json")

    def get_cached_chunks(self, file_path: str) -> Optional[List[Dict]]:
        """鑾峰彇缂撳瓨鐨勫垎鍧楃粨鏋?""
        try:
            # 璁＄畻鏂囦欢hash
            stat = os.stat(file_path)
            content = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
            file_hash = hashlib.sha256(content.encode()).hexdigest()

            cache_path = self._get_cache_path(file_hash)

            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    logger.info(f"缂撳瓨鍛戒腑: {file_path} -> {len(cached)} 涓垎鍧?)
                    return cached

            return None

        except Exception as e:
            logger.warning(f"璇诲彇缂撳瓨澶辫触: {e}")
            return None

    def cache_chunks(self, file_path: str, chunks: List[Dict]):
        """缂撳瓨鍒嗗潡缁撴灉"""
        try:
            # 璁＄畻鏂囦欢hash
            stat = os.stat(file_path)
            content = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
            file_hash = hashlib.sha256(content.encode()).hexdigest()

            cache_path = self._get_cache_path(file_hash)

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)

            logger.info(f"缂撳瓨鍒嗗潡: {file_path} -> {len(chunks)} 涓垎鍧?)

        except Exception as e:
            logger.warning(f"鍐欏叆缂撳瓨澶辫触: {e}")

    def clear_cache(self):
        """娓呯┖缂撳瓨"""
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.cache_dir, filename))
            logger.info("鍒嗗潡缂撳瓨宸叉竻绌?)
        except Exception as e:
            logger.warning(f"娓呯┖缂撳瓨澶辫触: {e}")

    def get_cache_stats(self) -> Dict:
        """鑾峰彇缂撳瓨缁熻"""
        try:
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]
            total_size = sum(os.path.getsize(os.path.join(self.cache_dir, f)) for f in cache_files)
            return {
                "cache_count": len(cache_files),
                "cache_size_mb": total_size / (1024 * 1024),
                "cache_dir": self.cache_dir,
            }
        except Exception as e:
            return {"error": str(e)}


# 鍏ㄥ眬瀹炰緥
_parallel_cleaner: Optional[ParallelCleaner] = None
_chunk_cache: Optional[ChunkCache] = None


def get_parallel_cleaner(max_workers: int = 4) -> ParallelCleaner:
    """鑾峰彇鍏ㄥ眬骞惰娓呮礂鍣?""
    global _parallel_cleaner
    if _parallel_cleaner is None:
        _parallel_cleaner = ParallelCleaner(max_workers=max_workers)
    return _parallel_cleaner


def get_chunk_cache() -> ChunkCache:
    """鑾峰彇鍏ㄥ眬鍒嗗潡缂撳瓨鍣?""
    global _chunk_cache
    if _chunk_cache is None:
        _chunk_cache = ChunkCache()
    return _chunk_cache


async def clean_files_parallel(file_paths: List[str], cleaner_func, max_workers: int = 4) -> List[CleaningTask]:
    """骞惰娓呮礂鏂囦欢鐨勪究鎹峰嚱鏁?""
    cleaner = get_parallel_cleaner(max_workers)
    return await cleaner.clean_batch(file_paths, cleaner_func)


def clean_file_with_cache(file_path: str, cleaner_func) -> Dict:
    """甯︾紦瀛樼殑鏂囦欢娓呮礂"""
    cache = get_chunk_cache()

    # 妫€鏌ョ紦瀛?
    cached = cache.get_cached_chunks(file_path)
    if cached:
        return {"chunks": cached, "from_cache": True}

    # 鎵ц娓呮礂
    result = cleaner_func(file_path)

    # 缂撳瓨缁撴灉
    if result and "chunks" in result:
        cache.cache_chunks(file_path, result["chunks"])

    return result
