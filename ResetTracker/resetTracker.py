from pyasn1.type.univ import Null


try:
    import os
    import traceback
    import json
    import csv
    import time
    from datetime import datetime
    import threading
    from Sheets import main, setup
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    from Buffer import Buffer

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

    class Saves(FileSystemEventHandler):
        buffer = None
        sessionStart = None
        buffer_observer = None
        prev = None
        src_path = None
        multiplier = None
        static = None

        def __init__(self):
            self.multiplier = settings["filter_mult"]
            self.static = settings["filter_static"]

        def on_created(self, event):
            if self.sessionStart is None:
                self.sessionStart = datetime.now()

            if self.buffer_observer is not None:
                self.buffer.stop()
                self.buffer_observer.stop()
                if self.buffer.stats.getRun()[0] is not None:
                    data = (
                        [str(datetime.now())] +
                        self.buffer.getRun()
                    )
                    # add_data to csv
                    h, m, s = data[1].split(":")
                    seconds = int(h) * 3600 + int(m) * 60 + int(s)
                    # print("Seconds", seconds)
                    print(data[1:10])
                    with open(statsCsv, "r") as infile:
                        reader = list(csv.reader(infile))
                        reader.insert(0, data)

                    with open(statsCsv, "w", newline="") as outfile:
                        writer = csv.writer(outfile)
                        for line in reader:
                            writer.writerow(line)

            self.buffer_observer = None

            if not event.is_directory:
                return

            self.src_path = event.src_path
            print("New record created", self.src_path)

            self.buffer = Buffer()
            self.buffer_observer = Observer()
            self.buffer_observer.schedule(
                self.buffer, self.src_path, recursive=False)

            try:
                self.buffer_observer.start()
            except Exception as e:
                pass

        def getTotalTime(self):
            return (
                self.buffer.achievements.endTime - self.sessionStart
            ).total_seconds()

    if __name__ == "__main__":
        settings["path"] = input(
            "Path to SpeedrunIGT records folder: "
        )
        settings_file = open("settings.json", "w")
        json.dump(settings, settings_file)
        settings_file.close()

        while True:
            try:
                savesObserver = Observer()
                event_handler = Saves()
                savesObserver.schedule(
                    event_handler, settings["path"], recursive=False)
                print("tracking: ", settings["path"])
                savesObserver.start()
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
            savesObserver.stop()
            savesObserver.join()

except Exception as e:
    print("Unexpected error please send to TheTalkingMime#4431 for help")
    traceback.print_exc()
    input("")
