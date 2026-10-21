"""
下载队列管理器
多任务队列：等待 / 下载中 / 已暂停 / 失败 / 已完成 五种状态；
按设置里的并发上限自动调度；暂停 = 终止进程（.part 断点保留），
继续 = 用同一条命令重启（yt-dlp 自动断点续传）。
"""

import threading
import time
import uuid
from enum import Enum

from PySide6.QtCore import QObject, QThread, Signal


class TaskState(Enum):
    WAITING = "等待中"
    RUNNING = "下载中"
    PAUSED = "已暂停"
    FAILED = "失败"
    DONE = "已完成"


class Task(QObject):
    """一个下载任务。字段变化后发 updated 信号，界面行自行刷新。"""

    updated = Signal()

    def __init__(self, url: str, output_dir, quality: str = "最高画质",
                 subtitle: bool = True, thumbnail: bool = True,
                 danmaku: bool = False, page_index: int = None,
                 page_title: str = "", sub_langs: str = "zh.*,en.*"):
        super().__init__()
        self.id = uuid.uuid4().hex[:12]
        self.url = url
        self.output_dir = str(output_dir)
        self.quality = quality
        self.subtitle = subtitle
        self.sub_langs = sub_langs or "zh.*,en.*"
        self.thumbnail = thumbnail
        self.danmaku = danmaku
        self.page_index = page_index          # 分 P 序号（1 起）；None = 整个视频
        self.page_title = page_title

        self.title = page_title or "解析中…"
        self.cover_url = ""
        self.meta = ""                        # UP主 · 时长 · 清晰度 等副信息
        self.state = TaskState.WAITING
        self.percent = 0.0
        self.speed_bps = 0.0
        self.eta = ""
        self.size_text = ""
        self.error = ""
        self.retry_count = 0
        self.filepath = ""                    # 完成后可打开的文件（尽力而为）

        # 内部
        self.pause_requested = False
        self.remove_requested = False
        self._cmd = None                      # 首次启动时固化的命令（续传一致性）

    def set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self.updated.emit()

    @property
    def state_text(self) -> str:
        if self.state == TaskState.FAILED and self.error:
            return self.error[:12]
        return self.state.value


class DownloadWorker(QThread):
    """单个任务的后台下载线程"""

    progress = Signal(dict)
    log = Signal(str)
    done = Signal(str, int)   # task_id, exit code（0 成功 / -2 中止 / 其他 失败）

    def __init__(self, downloader, task: Task, cookie_file, rate_limit: str,
                 proxy: str, auto_merge: bool):
        super().__init__()
        self.dl = downloader
        self.task = task
        self.cookie_file = cookie_file
        self.rate_limit = rate_limit
        self.proxy = proxy
        self.auto_merge = auto_merge

    def run(self):
        t = self.task
        code = -1
        try:
            code = self.dl.download(
                t.url, t.output_dir, t.quality, self.cookie_file,
                want_subtitle=t.subtitle, want_thumbnail=t.thumbnail,
                on_log=self.log.emit, on_progress=self.progress.emit,
                cancel_flag=lambda: t.pause_requested or t.remove_requested,
                rate_limit=self.rate_limit, proxy=self.proxy or None,
                auto_merge=self.auto_merge, cmd=t._cmd,
                sub_langs=t.sub_langs,
            )
            # 记下成片路径与真实大小，供「已完成」行打开文件 / 显示体积
            # （直接写属性、不发信号：这里还在工作线程，_on_done 会统一 emit）
            out = getattr(self.dl, "last_output", None)
            if code == 0 and out:
                from pathlib import Path
                from .downloader import human_size
                p = Path(out)
                try:
                    if p.exists():
                        t.filepath = str(p)
                        t.size_text = human_size(p.stat().st_size)
                        if t.danmaku:
                            # 成片同名 .xml（与 README 描述一致），避免标题被 yt-dlp 改写后对不上
                            from .downloader import fetch_danmaku
                            bvid = t.url.split("BV")[-1][:12]
                            fetch_danmaku(
                                f"BV{bvid}", page=t.page_index or 1,
                                output_path=p.with_suffix(".xml"),
                            )
                except OSError:
                    pass
                except Exception as exc:
                    self.log.emit(f"弹幕保存失败: {exc}")
        except Exception as exc:
            self.log.emit(f"下载异常: {exc}")
            code = -1
        self.done.emit(t.id, code)


class QueueManager(QObject):
    """
    下载队列。UI 只跟这个类打交道：
      add_task() / pause() / resume() / retry() / remove() / clear_done() / pause_all()
      tasks 列表 + 每个任务的 updated 信号驱动界面刷新
    """

    task_added = Signal(object)      # Task
    task_removed = Signal(str)       # task_id
    task_done = Signal(object)       # Task（成功完成，用于系统通知）
    stats_changed = Signal()

    def __init__(self, downloader, settings, parent=None):
        super().__init__(parent)
        self.dl = downloader
        self.settings = settings
        self.tasks: list[Task] = []
        self._workers: dict[str, DownloadWorker] = {}
        self._logs: list[str] = []

    # ---------- 对外操作 ----------
    def add_task(self, task: Task):
        self.tasks.append(task)
        self.task_added.emit(task)
        self._pump()

    def pause(self, task_id: str):
        t = self._get(task_id)
        if t and t.state == TaskState.RUNNING:
            t.pause_requested = True
            t.set(state=TaskState.PAUSED, speed_bps=0.0)

    def resume(self, task_id: str):
        t = self._get(task_id)
        if t and t.state == TaskState.PAUSED:
            t.pause_requested = False
            t.set(state=TaskState.WAITING)
            self._pump()

    def retry(self, task_id: str):
        t = self._get(task_id)
        if t and t.state in (TaskState.FAILED, TaskState.DONE):
            t.retry_count += 1
            t.set(state=TaskState.WAITING, percent=0.0, error="",
                  speed_bps=0.0, eta="", size_text="")
            self._pump()

    def remove(self, task_id: str):
        t = self._get(task_id)
        if not t:
            return
        if t.state == TaskState.RUNNING:
            t.remove_requested = True
            t.set(speed_bps=0.0)
        else:
            self.tasks.remove(t)
            self.task_removed.emit(task_id)
        self.stats_changed.emit()

    def clear_done(self):
        for t in [x for x in self.tasks if x.state == TaskState.DONE]:
            self.tasks.remove(t)
            self.task_removed.emit(t.id)
        self.stats_changed.emit()

    def pause_all(self):
        for t in self.tasks:
            if t.state == TaskState.RUNNING:
                self.pause(t.id)

    def shutdown(self, timeout: float = 5.0):
        """退出前优雅关停：请求暂停并等待线程结束（避免线程存活时销毁崩溃）"""
        self.pause_all()
        deadline = time.time() + timeout
        for w in list(self._workers.values()):
            remain = max(0.0, deadline - time.time())
            w.wait(remain * 1000 if remain else 100)

    def start_all(self):
        for t in self.tasks:
            if t.state in (TaskState.PAUSED, TaskState.FAILED):
                if t.state == TaskState.FAILED:
                    t.retry_count += 1
                t.pause_requested = False
                t.set(state=TaskState.WAITING, error="",
                      speed_bps=0.0, eta="", size_text="")
        self._pump()

    # ---------- 统计 ----------
    def running_count(self) -> int:
        return sum(1 for t in self.tasks if t.state == TaskState.RUNNING)

    def total_speed_bps(self) -> float:
        return sum(t.speed_bps for t in self.tasks if t.state == TaskState.RUNNING)

    def counts(self) -> dict:
        return {
            "total": len(self.tasks),
            "running": self.running_count(),
            "failed": sum(1 for t in self.tasks if t.state == TaskState.FAILED),
            "done": sum(1 for t in self.tasks if t.state == TaskState.DONE),
        }

    def logs(self) -> list[str]:
        return self._logs

    # ---------- 调度 ----------
    def _get(self, task_id: str):
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def _pump(self):
        """把等待中的任务填进空闲并发位"""
        limit = max(1, int(self.settings.get("max_concurrent", 3)))
        for t in self.tasks:
            if self.running_count() >= limit:
                break
            if t.state == TaskState.WAITING:
                self._start(t)
        self.stats_changed.emit()

    def _start(self, t: Task):
        t.set(state=TaskState.RUNNING, error="", speed_bps=0.0)
        cookie = self.settings.cookie_file if self.settings.logged_in else None

        worker = DownloadWorker(
            self.dl, t, cookie,
            rate_limit=self.settings.get("rate_limit", ""),
            proxy=self.settings.proxy_url(),
            auto_merge=self.settings.get("auto_merge", True),
        )
        worker.progress.connect(lambda info, tid=t.id: self._on_progress(tid, info))
        worker.log.connect(self._on_log)
        worker.done.connect(self._on_done)
        self._workers[t.id] = worker

        # 首次启动固化命令，暂停后继续用同一条命令保证断点可用
        if t._cmd is None:
            from pathlib import Path
            t._cmd = self.dl.build_download_cmd(
                t.url, Path(t.output_dir), t.quality, cookie,
                t.subtitle, t.thumbnail,
                self.settings.get("rate_limit", ""),
                self.settings.proxy_url() or None,
                self.settings.get("auto_merge", True),
                t.sub_langs,
            )
        worker.start()

    def _on_progress(self, task_id: str, info: dict):
        t = self._get(task_id)
        if not t:
            return
        kw = {}
        if "percent" in info:
            kw["percent"] = info["percent"]
            kw["speed_bps"] = info.get("speed_bps", t.speed_bps)
            kw["eta"] = info.get("eta", "")
            kw["size_text"] = info.get("size", t.size_text)
        elif "stage" in info:
            kw["meta"] = info["stage"]
        if kw:
            t.set(**kw)

    def _on_log(self, text: str):
        self._logs.append(text)
        if len(self._logs) > 500:
            del self._logs[:200]

    def _on_done(self, task_id: str, code: int):
        self._workers.pop(task_id, None)
        t = self._get(task_id)
        if not t:
            self._pump()
            return

        if t.remove_requested:
            t.remove_requested = False
            self.tasks.remove(t)
            self.task_removed.emit(task_id)
        elif code == 0:
            t.set(state=TaskState.DONE, percent=100.0, speed_bps=0.0, eta="")
            self.task_done.emit(t)
        elif code == -2 and t.pause_requested:
            t.set(speed_bps=0.0)          # 状态已在 pause() 时置为 PAUSED
        elif code == -2:
            t.set(state=TaskState.WAITING, speed_bps=0.0)
        else:
            err = "下载失败"
            for line in reversed(self._logs[-40:]):
                if line.startswith("ERROR"):
                    err = line[6:60].strip() or err
                    break
            t.set(state=TaskState.FAILED, error=err, speed_bps=0.0, eta="")

        self._pump()
