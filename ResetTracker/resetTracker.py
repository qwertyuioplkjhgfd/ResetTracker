import time
import json
import csv
import glob
import os
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


def ms_to_string(ms, returnTime=False):
    ms = int(ms)
    t = datetime(1970, 1, 1) + timedelta(milliseconds=ms)
    if returnTime:
        return t
    return t.strftime("%H:%M:%S")


class NewRecord(FileSystemEventHandler):
    buffer = None
    sessionStart = None
    buffer_observer = None
    prev = None
    src_path = None
    reset_count = 0
    rta_spent = 0
    splitless_count = 0

    def __init__(self):
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
        self.reset_count += 1
        self.this_run = [None] * (len(advChecks) + 2 + len(statsChecks) + 3)
        self.path = evt.src_path
        with open(self.path, "r") as record_file:
            try:
                self.data = json.load(record_file)
            except Exception as e:
                # skip
                return
        if self.data is None:
            print("Record file couldnt be read")
            return
        if not self.ensure_run():
            print("Run failed validation")
            return

        self.rta_spent += self.data["final_rta"]
        if self.data["final_rta"] == 0:
            return
        uids = list(self.data["stats"].keys())
        if len(uids) == 0:
            return
        stats = self.data["stats"][uids[0]]["stats"]
        adv = self.data["advancements"]

        # Advancements
        has_done_something = False
        self.this_run[0] = ms_to_string(self.data["final_rta"])
        for idx in range(len(advChecks)):
            # Prefer to read from timelines
            if advChecks[idx][0] == "timelines" and self.this_run[idx + 1] is None:
                for tl in self.data["timelines"]:
                    if tl["name"] == advChecks[idx][1]:
                        self.this_run[idx + 1] = ms_to_string(tl["igt"])
                        has_done_something = True
            # Read other stuff from advancements
            elif (advChecks[idx][0] in adv and adv[advChecks[idx][0]]["complete"] and self.this_run[idx + 1] is None):
                self.this_run[idx +
                              1] = ms_to_string(adv[advChecks[idx][0]]["criteria"][advChecks[idx][1]]["igt"])
                has_done_something = True

        # If nothing was done, just count as reset
        if not has_done_something:
            # From earlier we know that final_rta > 0 so this is a splitless non-wall/bg reset
            self.splitless_count += 1
            return

        # Stats
        self.this_run[len(advChecks) + 1] = ms_to_string(
            self.data["final_igt"])
        self.this_run[len(advChecks) + 2] = ms_to_string(
            self.data["retimed_igt"])
        for idx in range(1, len(statsChecks)):
            if (
                statsChecks[idx][0] in stats
                and statsChecks[idx][1] in stats[statsChecks[idx][0]]
            ):
                self.this_run[len(advChecks) + 2 + idx] = str(
                    stats[statsChecks[idx][0]][statsChecks[idx][1]]
                )

        # Push to csv
        d = ms_to_string(int(self.data["date"]), returnTime=True)
        data = ([str(d)] + self.this_run +
                [str(self.reset_count), ms_to_string(self.rta_spent), str(self.splitless_count)])

        with open(statsCsv, "r") as infile:
            reader = list(csv.reader(infile))
            reader.insert(0, data)

        with open(statsCsv, "w", newline="") as outfile:
            writer = csv.writer(outfile)
            for line in reader:
                writer.writerow(line)
        self.reset_count = 0
        self.rta_spent = 0
        self.splitless_count = 0


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
    if settings["delete-old-records"]:
        files = glob.glob(f'{settings["path"]}\\*.json')
        for f in files:
            os.remove(f)
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
