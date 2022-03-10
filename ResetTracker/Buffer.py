from watchdog.events import FileSystemEventHandler
from Records import Records
from watchdog.observers import Observer


class Buffer(FileSystemEventHandler):
    r_observer = None
    records = None

    def __init__(self):
        self.records = Records()

    def on_created(self, event):
        if not event.is_directory:
            return

        self.r_observer = Observer()
        self.r_observer.schedule(
            self.records,
            event.src_path,
            recursive=False,
        )
        self.r_observer.start()

    def stop(self):
        if self.r_observer is not None:
            self.r_observer.stop()

    def getRun(self):
        if self.records is not None and self.records.getRun()[0] is None:
            return None
        elif self.records is not None:
            return self.records.getRun()
