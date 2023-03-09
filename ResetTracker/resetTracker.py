import time
import json
import math
import csv
import glob
import os
import nightbotcmds
import twitchcmds
import commandupdater
from datetime import datetime, timedelta
import threading
import Sheets
from Sheets import main, setup
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from checks import advChecks, statsChecks
import asyncio
import traceback
import logging

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
command_updater = None


def ms_to_string(ms, returnTime=False):
    if ms is None:
        return None
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
    prev_datetime = None
    wall_resets = 0
    rta_spent = 0
    splitless_count = 0
    break_rta = 0

    def __init__(self):
        self.path = None
        self.data = None

    def ensure_run(self):
        if self.path is None:
            return False, "Path error"
        if self.data is None:
            return False, "Empty data error"
        if self.data['run_type'] != 'random_seed':
            return False, "Set seed detected, will not track"
        return True, ""

    def on_created(self, evt):
        try:
            self.process_file(evt.src_path)
        except Exception as e:
            print('Error reading records file')
            traceback.print_exc()
            logging.error('Error reading records file')
            logging.error(traceback.format_exc())
        
    def process_file(self, path):
        self.this_run = [None] * (len(advChecks) + 2 + len(statsChecks))
        self.path = path
        with open(self.path, "r") as record_file:
            try:
                self.data = json.load(record_file)
            except Exception as e:
                # skip
                return
        if self.data is None:
            print("Record file couldnt be read")
            return
        validation = self.ensure_run()
        if not validation[0]:
            print(validation[1])
            return

        # Calculate breaks
        if self.prev_datetime is not None:
            run_offset = self.prev_datetime + \
                timedelta(milliseconds=self.data["final_rta"])
            self.prev_datetime = datetime.now()
            run_differ = self.prev_datetime - run_offset
            if run_differ > timedelta(seconds=settings["break-offset"]):
                self.break_rta += run_differ.total_seconds() * 1000
        else:
            self.prev_datetime = datetime.now()

        if self.data["final_rta"] == 0:
            self.wall_resets += 1
            return
        uids = list(self.data["stats"].keys())
        if len(uids) == 0:
            return
        stats = self.data["stats"][uids[0]]["stats"]
        adv = self.data["advancements"]
        lan = self.data["open_lan"]
        if lan is not None:
            lan = int(lan)
        else:
            lan = math.inf

        self.this_run[0] = ms_to_string(self.data["final_rta"])
        
        #increment completion count
        if self.data["is_completed"] and lan > self.data["final_igt"]:
            command_updater.completion(self.data["final_igt"])
            
        # Advancements
        has_done_something = False
        for idx in range(len(advChecks)):
            time = None
            check = advChecks[idx]
            # Prefer to read from timelines
            if check[0] == "timelines" and self.this_run[idx + 1] is None:
                for tl in self.data["timelines"]:
                    if tl["name"] == check[1]:
                        if lan > int(tl["rta"]):
                            self.this_run[idx + 1] = ms_to_string(tl["igt"])
                            time = tl["igt"]
                            has_done_something = True
            # Read other stuff from advancements
            elif (check[0] in adv and adv[check[0]]["complete"] and self.this_run[idx + 1] is None):
                criteria = adv[check[0]]["criteria"]
                if check[1] in criteria and lan > int(criteria[check[1]]["rta"]):
                    time = criteria[check[1]]["igt"]
                    self.this_run[idx +
                                  1] = ms_to_string(time)
                    has_done_something = True

            if time is not None:
                #hardcode some cases for twitch commands
                if check[1] == "nether_travel":
                    command_updater.blind(int(time))
                elif check[1] == "enter_end":
                    command_updater.enter_end(int(time))

        # If nothing was done, just count as reset
        if not has_done_something:
            # From earlier we know that final_rta > 0 so this is a splitless non-wall/bg reset
            self.splitless_count += 1
            # Only account for splitless RTA
            self.rta_spent += self.data["final_rta"]
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

        # Generate other stuff
        iron_source = "None"
        if "minecraft:story/smelt_iron" in adv or "minecraft:story/iron_tools" in adv or (
                "minecraft:crafted" in stats and "minecraft:diamond_pickaxe" in stats["minecraft:crafted"]):
            iron_source = "Structureless"
            # If mined haybale or killed golem then village
            if ("minecraft:mined" in stats and "minecraft:hay_block" in stats["minecraft:mined"]) or (
                    "minecraft:killed" in stats and "minecraft:iron_golem" in stats["minecraft:killed"]):
                iron_source = "Village"
            elif "minecraft:used" in stats and ("minecraft:cooked_salmon" in stats["minecraft:used"] or "minecraft:cooked_cod" in stats["minecraft:used"]):
                iron_source = "Buried Treasure"
            elif "minecraft:adventure/adventuring_time" in adv:
                for biome in adv["minecraft:adventure/adventuring_time"]["criteria"]:
                    # If youre in an ocean before 3m
                    if "ocean" in biome and int(adv["minecraft:adventure/adventuring_time"]["criteria"][biome]["igt"]) < 180000:
                        iron_source = "Ship/BT"
                        break

        enter_type = "None"
        if "minecraft:story/enter_the_nether" in adv:
            enter_type = "Obsidian"
            if "minecraft:mined" in stats and "minecraft:magma_block" in stats["minecraft:mined"]:
                if "minecraft:story/lava_bucket" in adv:
                    enter_type = "Magma Ravine"
                else:
                    enter_type = "Bucketless"
            elif "minecraft:story/lava_bucket" in adv:
                enter_type = "Lava Pool"

        gold_source = "None"
        if ("minecraft:dropped" in stats and "minecraft:gold_ingot" in stats["minecraft:dropped"]) or (
            "minecraft:picked_up" in stats and (
                "minecraft:gold_ingot" in stats["minecraft:picked_up"] or "minecraft:gold_block" in stats["minecraft:picked_up"])):
            gold_source = "Classic"
            if "minecraft:mined" in stats and "minecraft:dark_prismarine" in stats["minecraft:mined"]:
                gold_source = "Monument"
            elif "minecraft:nether/find_bastion" in adv:
                gold_source = "Bastion"

        spawn_biome = "None"
        if "minecraft:adventure/adventuring_time" in adv:
            for biome in adv["minecraft:adventure/adventuring_time"]["criteria"]:
                if adv["minecraft:adventure/adventuring_time"]["criteria"][biome]["igt"] == 0:
                    spawn_biome = biome.split(":")[1]

        iron_time = adv["minecraft:story/smelt_iron"]["igt"] if "minecraft:story/smelt_iron" in adv else None

        # Push to csv
        d = ms_to_string(int(self.data["date"]), returnTime=True)
        data = ([str(d), iron_source, enter_type, gold_source, spawn_biome] + self.this_run +
                [ms_to_string(iron_time), str(self.wall_resets), str(self.splitless_count),
                 ms_to_string(self.rta_spent), ms_to_string(self.break_rta)])

        with open(statsCsv, "r") as infile:
            reader = list(csv.reader(infile))
            reader.insert(0, data)

        with open(statsCsv, "w", newline="") as outfile:
            writer = csv.writer(outfile)
            for line in reader:
                writer.writerow(line)
                
        # update twitch command
        asyncio.run(command_updater.update_command())
        
        # Reset all counters/sums
        self.wall_resets = 0
        self.rta_spent = 0
        self.splitless_count = 0
        self.break_rta = 0
        
def get_command_updater():
    # check if method is 'chat' or 'nightbot'
    # if not, check if enabled, and default to chat
    if 'method' not in settings['twitch']:
        if 'enabled' in settings['twitch']:
            settings['twitch']['method'] = 'chat' if settings['twitch']['enabled'] else 'none'
        else:
            settings['twitch']['method'] = input('What method would you like to use for updating twitch commands? (chat/nightbot/none) ') or 'none'
    method = settings['twitch']['method']
    if method == 'nightbot':
        return nightbotcmds.NightbotCommandUpdater(settings)
    elif method == 'chat':
        return twitchcmds.TwitchCommandUpdater(settings)
    elif method in ('none', ''):
        return commandupdater.CommandUpdater(settings)
    else:
        print(f'Invalid method {method} for twitch command updating. Defaulting to none.')
        return commandupdater.CommandUpdater(settings)
        
    
async def trackermain():
    settings_file = open("settings.json", "w")
    json.dump(settings, settings_file, indent=2)
    settings_file.close()
    
    logging.basicConfig(
        filename='debug.log', 
        encoding='utf-8', 
        level=logging.DEBUG, 
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

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
            json.dump(settings, settings_file, indent=2)
            settings_file.close()
        else:
            break
    if settings["delete-old-records"]:
        files = glob.glob(f'{settings["path"]}\\*.json')
        for f in files:
            os.remove(f)
    setup(settings)
    t = threading.Thread(
        target=main, name="sheets"
    )  # < Note that I did not actually call the function, but instead sent it as a parameter
    t.daemon = True

    global command_updater
    command_updater = get_command_updater()
    await command_updater.setup()
    with open('settings.json', 'w') as settings_file:
        json.dump(settings, settings_file, indent=2)

    t.start()  # < This actually starts the thread execution in the background
    print("Tracking...")
    print("Type 'quit' when you are done")
    live = True

    try:
        while live:
            try:
                loop = asyncio.get_event_loop()
                val = await loop.run_in_executor(None, input, "% ")
            except:
                val = ""
            args = val.split(' ')
            if (val == "help") or (val == "?"):
                print('help - print this help message')
                print("quit - quit")
                print("reset - resets twitch counters")
                print('update <counter> <value> - updates specified twitch counter. counter can be "blinds", "sub4", "sub330", "sub3", "ees", "completions", "blindtimes", "eestimes", "completiontimes". for lists (e.g. blindtimes), value should be a space-separated list of times')
                print('undo - deletes latest entry')
                print('eval <python code> - evaluates python code')
            elif (val == "stop") or (val == "quit"):
                print("Stopping...")
                live = False
            elif (val == "reset"):
                print("Resetting counters...")
                command_updater.reset()
                await command_updater.update_command()
                print("...done")
            elif args[0] == 'update':
                if len(args) < 3:
                    print('update <counter> <value> - updates specified twitch counter. counter can be "blinds", "sub4", "sub330", "sub3", "ees", "completions", "blindtimes", "eestimes", "completiontimes". for lists (e.g. blindtimes), value should be a space-separated list of times')
                elif command_updater.updatecounter(args[1], args[2:]):
                    await command_updater.update_command()
                    print("Counter set")
                else:
                    print("unknown counter", args[1])
            elif val == 'undo':
                with open(statsCsv, "r") as infile:
                    reader = list(csv.reader(infile))
                if len(reader) != 0:
                    print('Deleting latest entry from stats.csv', reader.pop(0))
                    with open(statsCsv, "w", newline="") as outfile:
                        writer = csv.writer(outfile)
                        for line in reader:
                            writer.writerow(line)
                else:
                    if settings['sheets']['enabled']:
                        print('Deleting latest entry from Google Sheets')
                        Sheets.dataSheet.delete_rows(2)
            elif args[0] == 'eval':
                try:
                    r = eval(' '.join(args[1:]))
                    if r is not None:
                        print(r)
                except Exception as e:
                    traceback.print_exc()
            elif args[0] == 'await':
                try:
                    r = eval(' '.join(args[1:]))
                    r = await r
                    if r is not None:
                        print(r)
                except Exception as e:
                    traceback.print_exc()
            elif val == '':
                pass
            else:
                print("Invalid command. Type 'help' for help")
            await asyncio.sleep(0.05)
    finally:
        newRecordObserver.stop()
        newRecordObserver.join()
        
        await command_updater.stop()

if __name__ == "__main__":
    asyncio.run(trackermain())
