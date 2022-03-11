import time
import json
import csv
from datetime import datetime, timedelta
import threading
from Sheets import main, setup
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from checks import advChecks, statsChecks

statsCsv = "stats.csv"
try:
    settings_file = open("settings.json")
    settings = json.load(settings_file)
    settings_file.close()
except Exception as e:
    print(e)
    print(
        "Could not find settings.json, make sure you have the file in the same directory as the exe, and named exactly 'settings.json'"
    )
    wait = input("")


def ms_to_string(ms):
    ms = int(ms)
    time = datetime(1970, 1, 1) + timedelta(milliseconds=ms)
    return time.strftime("%H:%M:%S")


class NewRecord(FileSystemEventHandler):
    buffer = None
    sessionStart = None
    buffer_observer = None
    prev = None
    src_path = None

    def __init__(self):
        self.this_run = [None] * (len(advChecks) + 1 + len(statsChecks))
        self.path = None
        self.data = None

    def ensure_run(self):
        if self.path is None:
            return False
        if self.data is None:
            return False
        # Ensure its not a set seed
        if "RandomSpeedrun #" not in self.data['world_name']:
            return False
        return True

    def on_created(self, evt):
        self.path = evt.src_path
        with open(self.path, "r") as record_file:
            self.data = json.load(record_file)
        if self.data is None:
            print("Record file couldnt be read")
            return
        if not self.ensure_run():
            print("Run failed validation")
            return

        # Ensure there are stats
        skipStats = len(self.data["stats"].keys()) == 0
        if not skipStats:
            uid = list(self.data["stats"].keys())[0]
            stats = self.data["stats"][uid]["stats"]
        adv = self.data["advancements"]

        # Advancements
        self.this_run[0] = ms_to_string(self.data["retimed_igt"])
        for idx in range(len(advChecks)):
            # Prefer to read from timelines
            if advChecks[idx][0] == "timelines" and self.this_run[idx + 1] is None:
                if len(self.data["timelines"]) > advChecks[idx][1]:
                    self.this_run[idx + 1] = ms_to_string(
                        self.data["timelines"][advChecks[idx][1]]["igt"])
            # Read other stuff from advancements
            elif (advChecks[idx][0] in adv and adv[advChecks[idx][0]]["complete"] and self.this_run[idx + 1] is None):
                self.this_run[idx +
                              1] = ms_to_string(adv[advChecks[idx][0]]["criteria"][advChecks[idx][1]]["igt"])

        # Stats
        if not skipStats:
            self.this_run[len(advChecks)] = ms_to_string(
                self.data["final_igt"])
            for idx in range(1, len(statsChecks)):
                if (
                    statsChecks[idx][0] in stats
                    and statsChecks[idx][1] in stats[statsChecks[idx][0]]
                ):
                    self.this_run[len(advChecks) + idx] = str(
                        stats[statsChecks[idx][0]][statsChecks[idx][1]]
                    )

        # Push to csv
        d = datetime.strptime(self.path.split(
            ".")[0].split("\\")[-1], "%y-%m-%d-%H-%M-%S")
        data = ([str(d)] + self.this_run)

        with open(statsCsv, "r") as infile:
            reader = list(csv.reader(infile))
            reader.insert(0, data)

        with open(statsCsv, "w", newline="") as outfile:
            writer = csv.writer(outfile)
            for line in reader:
                writer.writerow(line)


if __name__ == "__main__":
    settings_file = open("settings.json", "w")
    json.dump(settings, settings_file)
    settings_file.close()

    while True:
        try:
            newRecordObserver = Observer()
            event_handler = NewRecord()
            newRecordObserver.schedule(
                event_handler, settings["path"], recursive=False)
            print("tracking: ", settings["path"])
            newRecordObserver.start()
            print("Started")
        except Exception as e:
            print("Records directory could not be found")
            settings["path"] = input(
                "Path to SpeedrunIGT records folder: "
            )
            settings_file = open("settings.json", "w")
            json.dump(settings, settings_file)
            settings_file.close()
        else:
            break
    setup()
    t = threading.Thread(
        target=main, name="sheets"
    )  # < Note that I did not actually call the function, but instead sent it as a parameter
    t.daemon = True
    t.start()  # < This actually starts the thread execution in the background

    print("Tracking...")
    print("Type 'quit' when you are done")
    live = True

    try:
        while live:
            try:
                val = input("")
            except:
                val = ""
            if (val == "help") or (val == "?"):
                print("there is literally one other command and it's quit")
            if (val == "stop") or (val == "quit"):
                live = False
            time.sleep(1)
    finally:
        newRecordObserver.stop()
        newRecordObserver.join()
