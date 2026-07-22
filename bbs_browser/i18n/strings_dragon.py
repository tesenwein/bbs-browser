"""Uebersetzungskatalog fuer dragon.py (Door Game 'Der Uralte Wurm')."""

STRINGS = {
    "dragon.title": {"de": "DER URALTE WURM", "en": "THE ANCIENT WYRM"},
    "dragon.welcome": {
        "de": "Der Dorfplatz liegt im Fackelschein. Der Wald wartet.",
        "en": "The village square lies in torchlight. The forest is waiting.",
    },
    "dragon.menu_subtitle": {"de": "Rang {level} · {gold} Gold · q verlaesst das Door",
                             "en": "Rank {level} · {gold} gold · q leaves the door"},
    "dragon.head_place": {"de": "DRAUSSEN", "en": "OUTSIDE"},
    "dragon.head_town": {"de": "IM DORF", "en": "IN TOWN"},
    "dragon.menu_forest": {"de": "In den Wald", "en": "Enter the forest"},
    "dragon.menu_forest_value": {"de": "noch {n} Kaempfe heute", "en": "{n} fights left today"},
    "dragon.menu_master": {"de": "Zum Meister", "en": "Visit your master"},
    "dragon.menu_dragon": {"de": "Der Uralte Wurm", "en": "The Ancient Wyrm"},
    "dragon.menu_dragon_value": {"de": "ab Rang 12", "en": "rank 12 and up"},
    "dragon.menu_weapons": {"de": "Waffenschmied", "en": "Weapon smith"},
    "dragon.menu_armor": {"de": "Ruestkammer", "en": "Armoury"},
    "dragon.menu_tavern": {"de": "Wirtshaus", "en": "Tavern"},
    "dragon.menu_tavern_value": {"de": "{gold} Gold in der Tasche", "en": "{gold} gold in your purse"},
    "dragon.menu_stats": {"de": "Heldenbrief", "en": "Character sheet"},
    "dragon.state_alive": {"de": "{hp}/{max} LP", "en": "{hp}/{max} HP"},
    "dragon.state_dead": {"de": "gefallen — morgen wieder", "en": "fallen — back tomorrow"},
    "dragon.unknown_choice": {"de": "Das gibt es hier nicht.", "en": "No such thing here."},

    # Kampf
    "dragon.combat_title": {"de": "KAMPF · {foe}", "en": "COMBAT · {foe}"},
    "dragon.combat_intro": {"de": "{foe} stellt sich dir in den Weg!", "en": "{foe} blocks your path!"},
    "dragon.combat_status": {"de": "  Du: {you}/{max} LP     {foe}: {foe_hp} LP",
                              "en": "  You: {you}/{max} HP     {foe}: {foe_hp} HP"},
    "dragon.combat_prompt": {"de": "(A)ngriff  (H)eiltrank  (F)liehen  (S)tatus > ",
                              "en": "(A)ttack  (H)eal  (F)lee  (S)tats > "},
    "dragon.hit": {"de": "Du triffst {foe} fuer {dmg} Schaden.", "en": "You hit {foe} for {dmg} damage."},
    "dragon.hit_crit": {"de": "VOLLTREFFER! {foe} nimmt {dmg} Schaden.",
                         "en": "CRITICAL HIT! {foe} takes {dmg} damage."},
    "dragon.foe_hit": {"de": "{foe} trifft dich fuer {dmg} Schaden.", "en": "{foe} hits you for {dmg} damage."},
    "dragon.foe_down": {"de": "{foe} sinkt zu Boden.", "en": "{foe} drops to the ground."},
    "dragon.spoils": {"de": "Beute: {gold} Gold, {exp} Erfahrung.", "en": "Spoils: {gold} gold, {exp} experience."},
    "dragon.flee_ok": {"de": "Du machst dich aus dem Staub.", "en": "You slip away."},
    "dragon.flee_fail": {"de": "Die Flucht misslingt!", "en": "Your escape fails!"},
    "dragon.flee_blocked": {"de": "Hier gibt es kein Zurueck.", "en": "There is no way back here."},
    "dragon.no_potion": {"de": "Kein Heiltrank mehr im Beutel.", "en": "No healing potion left."},
    "dragon.potion_used": {"de": "Der Trank bringt {hp} LP zurueck ({left} uebrig).",
                            "en": "The potion restores {hp} HP ({left} left)."},

    # Tod
    "dragon.dead_title": {"de": "GEFALLEN", "en": "SLAIN"},
    "dragon.dead_msg": {"de": "{foe} hat dich erschlagen. {gold} Gold bleiben im Dreck liegen.",
                         "en": "{foe} has slain you. {gold} gold stays in the dirt."},
    "dragon.dead_hint": {"de": "Morgen stehst du wieder auf — Erfahrung und Ausruestung bleiben.",
                          "en": "You rise again tomorrow — experience and gear stay with you."},
    "dragon.you_are_dead": {"de": "Fuer heute bist du tot.", "en": "You are dead for today."},
    "dragon.no_fights_left": {"de": "Keine Kraft mehr fuer heute — morgen wieder.",
                               "en": "No strength left today — come back tomorrow."},

    # Meister
    "dragon.master_not_yet": {"de": "Der Meister winkt ab: {need} Erfahrung fehlen noch.",
                               "en": "Your master waves you off: {need} experience short."},
    "dragon.master_topped": {"de": "Du hast alles gelernt, was die Meister lehren koennen.",
                              "en": "You have learned everything the masters can teach."},
    "dragon.master_challenge": {"de": "{master} zieht die Klinge: 'Zeig, was du kannst.'",
                                 "en": "{master} draws a blade: 'Show me what you have.'"},
    "dragon.level_up_title": {"de": "AUFSTIEG", "en": "RANK UP"},
    "dragon.level_up": {"de": "Rang {level} erreicht — {hp} Lebenspunkte.",
                         "en": "Rank {level} reached — {hp} hit points."},

    # Laeden
    "dragon.shop_title_weapon": {"de": "WAFFENSCHMIED", "en": "WEAPON SMITH"},
    "dragon.shop_title_armor": {"de": "RUESTKAMMER", "en": "ARMOURY"},
    "dragon.shop_subtitle": {"de": "{gold} Gold · Enter kauft, q zurueck",
                              "en": "{gold} gold · Enter buys, q returns"},
    "dragon.shop_price": {"de": "{price} Gold  (+{power})", "en": "{price} gold  (+{power})"},
    "dragon.shop_owned": {"de": "in Gebrauch", "en": "in use"},
    "dragon.shop_old": {"de": "verkauft", "en": "sold"},
    "dragon.shop_have_better": {"de": "Damit bist du schon besser bedient.", "en": "You already carry better."},
    "dragon.shop_too_poor": {"de": "Es fehlen {missing} Gold.", "en": "You are {missing} gold short."},
    "dragon.shop_bought": {"de": "{name} gehoert jetzt dir.", "en": "{name} is yours now."},

    # Wirtshaus
    "dragon.tavern_title": {"de": "WIRTSHAUS ZUM SCHIEFEN MODEM", "en": "THE CROOKED MODEM INN"},
    "dragon.tavern_heal": {"de": "Wunden versorgen", "en": "Patch up wounds"},
    "dragon.tavern_heal_value": {"de": "{hp} LP fehlen · {price} Gold", "en": "{hp} HP missing · {price} gold"},
    "dragon.tavern_potion": {"de": "Heiltrank kaufen", "en": "Buy a healing potion"},
    "dragon.tavern_potion_value": {"de": "{price} Gold · {have} im Beutel", "en": "{price} gold · {have} in the bag"},
    "dragon.tavern_deposit": {"de": "Gold einzahlen", "en": "Deposit gold"},
    "dragon.tavern_withdraw": {"de": "Gold abheben", "en": "Withdraw gold"},
    "dragon.tavern_bank_value": {"de": "Truhe: {bank}", "en": "Chest: {bank}"},
    "dragon.tavern_amount": {"de": "Wieviel? ", "en": "How much? "},
    "dragon.tavern_bank_ok": {"de": "Tasche: {gold} · Truhe: {bank}", "en": "Purse: {gold} · Chest: {bank}"},
    "dragon.tavern_fit": {"de": "Kein Kratzer an dir.", "en": "Not a scratch on you."},
    "dragon.tavern_healed": {"de": "{hp} LP geflickt fuer {price} Gold.", "en": "{hp} HP patched for {price} gold."},
    "dragon.tavern_potion_bought": {"de": "Trank gekauft — {have} im Beutel.",
                                     "en": "Potion bought — {have} in the bag."},

    # Drache
    "dragon.dragon_title": {"de": "DIE HOEHLE DES URALTEN WURMS", "en": "THE ANCIENT WYRM'S LAIR"},
    "dragon.dragon_name": {"de": "Der Uralte Wurm", "en": "The Ancient Wyrm"},
    "dragon.dragon_intro": {"de": "Heisse Luft schlaegt dir entgegen. Kein Zurueck.",
                             "en": "Hot air hits your face. No way back."},
    "dragon.dragon_too_weak": {"de": "So weit bist du nicht — Rang {level} braucht es.",
                                "en": "Not yet — rank {level} is required."},
    "dragon.dragon_won_title": {"de": "DER DRACHE IST TOT", "en": "THE DRAGON IS DEAD"},
    "dragon.dragon_won": {"de": "Das Dorf feiert dich. Zum {times}. Mal. Ein neuer Held faengt von vorn an.",
                           "en": "The village cheers for you. Time number {times}. A new hero starts over."},

    # Heldenbrief
    "dragon.stats_title": {"de": "HELDENBRIEF · {handle}", "en": "CHARACTER SHEET · {handle}"},
    "dragon.stat_level": {"de": "Rang", "en": "Rank"},
    "dragon.stat_hp": {"de": "Lebenspunkte", "en": "Hit points"},
    "dragon.stat_exp": {"de": "Erfahrung", "en": "Experience"},
    "dragon.stat_weapon": {"de": "Waffe", "en": "Weapon"},
    "dragon.stat_armor": {"de": "Ruestung", "en": "Armour"},
    "dragon.stat_gold": {"de": "Gold", "en": "Gold"},
    "dragon.stat_bank": {"de": "Truhe", "en": "chest"},
    "dragon.stat_potions": {"de": "Heiltraenke", "en": "Potions"},
    "dragon.stat_fights": {"de": "Kaempfe heute", "en": "Fights today"},
    "dragon.stat_kills": {"de": "Erlegt", "en": "Kills"},
    "dragon.stat_duels": {"de": "davon Anrufer", "en": "callers among them"},
    "dragon.stat_slain": {"de": "Drachen erlegt", "en": "Dragons slain"},
    "dragon.exp_of": {"de": "{exp} / {need}", "en": "{exp} / {need}"},

    # Anrufer im Wald
    "dragon.caller_encounter": {"de": "Am Bach steht {handle} — und will Streit.",
                                 "en": "{handle} is standing by the creek — looking for trouble."},

    # Gegner: Praefix + Grundtyp je Rang (mit '|' getrennt)
    "dragon.monster_prefixes": {
        "de": "Rostiger|Fauchender|Einaeugiger|Struppiger|Bleicher|Hinkender|Grimmiger|Zottiger",
        "en": "Rusty|Hissing|One-eyed|Scruffy|Pale|Limping|Grim|Shaggy",
    },
    "dragon.monster_bases": {
        "de": "Waldkobold|Sumpfratte|Wegelagerer|Hoehlentroll|Moorhund|Klingengeist|"
              "Steinriese|Nachtmahr|Schattenritter|Basilisk|Feuerlindwurm|Drachenwaechter",
        "en": "Forest goblin|Swamp rat|Highwayman|Cave troll|Moor hound|Blade wraith|"
              "Stone giant|Night mare|Shadow knight|Basilisk|Fire wyrm|Dragon warden",
    },
    "dragon.masters": {
        "de": "Meister Halvar|Meisterin Ingrid|Meister Bosco|Meisterin Runa|Meister Torvald|"
              "Meisterin Alma|Meister Cedric|Meisterin Yara|Meister Osric|Meisterin Freya|"
              "Meister Gundar|Die Alte vom Turm",
        "en": "Master Halvar|Master Ingrid|Master Bosco|Master Runa|Master Torvald|"
              "Master Alma|Master Cedric|Master Yara|Master Osric|Master Freya|"
              "Master Gundar|The Crone of the Tower",
    },

    # Waffen und Ruestungen
    "dragon.weapon_0": {"de": "Blosse Faeuste", "en": "Bare fists"},
    "dragon.weapon_1": {"de": "Rostiger Dolch", "en": "Rusty dagger"},
    "dragon.weapon_2": {"de": "Kurzschwert", "en": "Short sword"},
    "dragon.weapon_3": {"de": "Streitaxt", "en": "Battle axe"},
    "dragon.weapon_4": {"de": "Runenklinge", "en": "Rune blade"},
    "dragon.weapon_5": {"de": "Drachentoeter", "en": "Dragonslayer"},
    "dragon.armor_0": {"de": "Leinenhemd", "en": "Linen shirt"},
    "dragon.armor_1": {"de": "Lederwams", "en": "Leather jerkin"},
    "dragon.armor_2": {"de": "Kettenhemd", "en": "Chain mail"},
    "dragon.armor_3": {"de": "Schuppenpanzer", "en": "Scale armour"},
    "dragon.armor_4": {"de": "Plattenruestung", "en": "Plate armour"},
    "dragon.armor_5": {"de": "Drachenschuppen", "en": "Dragon scales"},
}
