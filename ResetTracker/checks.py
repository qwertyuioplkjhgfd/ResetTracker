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
