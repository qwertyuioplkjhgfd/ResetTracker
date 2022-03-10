import datetime
import json
import time
from datetime import datetime, timedelta
import time
from watchdog.events import FileSystemEventHandler


def ms_to_string(ms):
    ms = int(ms)
    time = datetime.fromtimestamp(ms / 1000.0)
    return time.strftime("%H:%M:%S")


class Records(FileSystemEventHandler):
    advChecks = [
        ("minecraft:recipes/misc/charcoal", "has_log"),
        ("minecraft:story/iron_tools", "iron_pickaxe"),
        ("timelines", 0),
        ("timelines", 1),
        ("timelines", 2),
        ("timelines", 3),
        ("timelines", 4),
        ("timelines", 5),
    ]

    statsChecks = [
        "nothing lol",
        ("minecraft:dropped", "minecraft:gold_ingot"),
        ("minecraft:picked_up", "minecraft:blaze_rod"),
        ("minecraft:killed", "minecraft:blaze"),
        ("minecraft:custom", "minecraft:damage_taken"),
        ("minecraft:custom", "minecraft:sprint_one_cm"),
        ("minecraft:custom", "minecraft:boat_one_cm"),
        ("minecraft:picked_up", "minecraft:flint"),
        ("minecraft:mined", "minecraft:gravel"),
        ("minecraft:mined", "minecraft:prismarine"),
        # for identifying structureless
        ("minecraft:crafted", "minecraft:furnace"),
        # for identifying structureless
        ("minecraft:crafted", "minecraft:iron_ingot"),
        # for identifying structureless
        ("minecraft:mined", "minecraft:iron_ore"),
        ("minecraft:mined", "minecraft:hay_block"),  # for identifying village
        ("minecraft:killed", "minecraft:iron_golem"),  # for identifying village
        ("minecraft:mined", "minecraft:magma_block"),  # for identifying shipwreck
        # for identifying shipwreck
        ("minecraft:crafted", "minecraft:wooden_axe"),
        ("minecraft:custom", "minecraft:swim_one_cm"),
        ("minecraft:custom", "minecraft:deaths"),
        ("minecraft:custom", "minecraft:time_since_death"),
        ("minecraft:custom", "minecraft:traded_with_villager"),
        ("minecraft:killed", "minecraft:enderman"),
        ("minecraft:crafted", "minecraft:shield"),
        ("minecraft:crafted", "minecraft:bucket"),
        ("minecraft:picked_up", "minecraft:ender_eye"),
    ]

    def __init__(self):
        self.this_run = [None] * \
            (len(self.advChecks) + 1 + len(self.statsChecks))
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

    def on_modified(self, event):
        self.path = event.src_path
        with open(self.path, "r") as record_file:
            self.data = json.load(record_file)
        if self.data is None:
            print("Record file couldnt be read")
            return
        if not self.ensure_run():
            print("Run failed validation")
            return

        uid = self.data["stats"].keys()[0]
        stats = self.data["stats"][uid]["stats"]
        adv = self.data["advancements"]

        # Advancements
        self.this_run[0] = ms_to_string(self.data["retimed_igt"])
        for idx in range(len(self.advChecks)):
            # Prefer to read from timelines
            if self.advChecks[idx][0] == "timelines":
                self.this_run[idx + 1] = ms_to_string(
                    self.data["timelines"][self.advChecks[idx][1]]["igt"])
            # Read other stuff from advancements
            elif (self.advChecks[idx][0] in adv and adv[self.advChecks[idx][0]]["complete"] and self.this_run[idx + 1] is None):
                self.this_run[idx +
                              1] = ms_to_string(adv[self.advChecks[idx][0]]["criteria"][self.advChecks[idx][1]]["igt"])

        # Stats
        self.this_run[len(self.advChecks)] = ms_to_string(
            self.data["final_igt"])
        for idx in range(1, len(self.statsChecks)):
            if (
                self.statsChecks[idx][0] in stats
                and self.statsChecks[idx][1] in stats[self.statsChecks[idx][0]]
            ):
                self.this_run[len(self.advChecks) + idx] = str(
                    stats[self.statsChecks[idx][0]][self.statsChecks[idx][1]]
                )

    def getRun(self):
        return self.this_run
