"""
Snowflake ID 生成器
"""
import time
import threading


class Snowflake:
    # 起始时间戳 (2025-01-01 00:00:00)
    EPOCH = 1735689600000

    # 位数分配
    WORKER_ID_BITS = 10
    SEQUENCE_BITS = 12

    MAX_WORKER_ID = (1 << WORKER_ID_BITS) - 1   # 1023
    MAX_SEQUENCE  = (1 << SEQUENCE_BITS) - 1     # 4095

    # 位移
    TIMESTAMP_SHIFT = WORKER_ID_BITS + SEQUENCE_BITS  # 22
    WORKER_ID_SHIFT = SEQUENCE_BITS                    # 12

    def __init__(self, worker_id: int = 1):
        if worker_id < 0 or worker_id > self.MAX_WORKER_ID:
            raise ValueError(f"worker_id 必须在 0~{self.MAX_WORKER_ID} 之间")
        self.worker_id = worker_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _current_millis(self) -> int:
        return int(time.time() * 1000)

    def _wait_next_millis(self, last: int) -> int:
        """时钟回拨时阻塞等待"""
        ts = self._current_millis()
        while ts <= last:
            ts = self._current_millis()
        return ts

    def next_id(self) -> int:
        with self.lock:
            ts = self._current_millis()

            if ts < self.last_timestamp:
                # 时钟回拨，等待追上
                ts = self._wait_next_millis(self.last_timestamp)

            if ts == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                if self.sequence == 0:
                    # 当毫秒内序列号用完，等下一毫秒
                    ts = self._wait_next_millis(self.last_timestamp)
            else:
                self.sequence = 0

            self.last_timestamp = ts

            return (
                ((ts - self.EPOCH) << self.TIMESTAMP_SHIFT)
                | (self.worker_id << self.WORKER_ID_SHIFT)
                | self.sequence
            )


# 全局单例
snowflake = Snowflake(worker_id=1)
