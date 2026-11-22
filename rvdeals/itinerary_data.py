"""Corridors for the trip plans.

km = APPROXIMATE driving distance from the start of the corridor. Campgrounds are well-known
public or RV parks along the way; seasons, hours, closures and reservations change, so every
plan page labels them "check before you go".
"""

# Warnings: (months they apply to, text). Month numbers 1-12.
W = {
    "bc_winter": ({10, 11, 12, 1, 2, 3, 4}, "BC winter tire / chain rules apply on most highways Oct 1 to Mar 31, and on mountain passes to Apr 30. Check DriveBC."),
    "rogers": ({11, 12, 1, 2, 3, 4}, "Rogers Pass (Hwy 1) can close for hours for avalanche control. Check DriveBC before you leave Golden or Revelstoke."),
    "coquihalla": ({11, 12, 1, 2, 3}, "Coquihalla (Hwy 5) gets heavy snow and sudden closures. Check DriveBC; Hwy 1 through the Fraser Canyon is the backup."),
    "bc_parks": ({10, 11, 12, 1, 2, 3, 4}, "Many BC provincial park campgrounds are closed or have no services from fall to spring."),
    "rockies_parks": ({10, 11, 12, 1, 2, 3, 4, 5}, "Most Banff and Jasper campgrounds close for winter (Tunnel Mountain Village II and Lake Louise hard-sided usually stay open). Moraine Lake road is closed to private vehicles; shuttle only in season."),
    "parks_pass": (set(range(1, 13)), "You need a Parks Canada pass to stop in Banff, Yoho, Glacier or Jasper national parks."),
    "jasper_fire": (set(range(1, 13)), "Jasper was hit by a major wildfire in 2024; some services and campgrounds may still be limited."),
    "ont_parks": ({10, 11, 12, 1, 2, 3, 4, 5}, "Most Ontario provincial park campgrounds close from mid-October to mid-May."),
    "superior": ({11, 12, 1, 2, 3, 4}, "Hwy 17 along Lake Superior has winter storms, closures and long gaps between services. Fuel up often."),
    "prairie": ({12, 1, 2, 3}, "Prairie blizzards and extreme cold can close the Trans-Canada. Check provincial road reports daily."),
    "grapevine": ({12, 1, 2, 3}, "I-5 over the Grapevine (Tejon Pass) closes in snow. Check Caltrans QuickMap."),
    "siskiyou": ({11, 12, 1, 2, 3}, "I-5 Siskiyou Summit (Oregon border) often needs chains in winter. Check TripCheck and Caltrans."),
    "big_sur": (set(range(1, 13)), "Hwy 1 through Big Sur has had long landslide closures. Check Caltrans QuickMap; US-101 inland is the backup."),
    "redwood_rv": (set(range(1, 13)), "Some redwood park roads ban RVs or limit length (for example Howland Hill Road). Stay on US-101 with a big rig."),
    "oregon_coast": ({11, 12, 1, 2, 3}, "Winter storms and slides can close parts of US-101 on the Oregon coast. Check TripCheck."),
    "crater_lake": ({10, 11, 12, 1, 2, 3, 4, 5, 6}, "Crater Lake's Rim Drive and Mazama campground are closed most of the year outside summer."),
    "desert_heat": ({5, 6, 7, 8, 9}, "Extreme desert heat in Nevada and Death Valley: carry extra water and drive in the morning."),
    "high_desert": ({11, 12, 1, 2, 3}, "High desert passes on US-95 / US-395 / US-97 can be icy. Check NVroads and TripCheck."),
    "wildfire": ({7, 8, 9}, "Wildfire season: smoke and road closures are common in BC, Washington, Oregon and California. Check before each day's drive."),
}

# Each waypoint: key (for matching deals), name, km, stops, campground, warning keys.
COAST = {
    "name": "Scenic coast (US-101 / Hwy 1)",
    "kind": "scenic",
    "points": [
        ("san diego", "San Diego", 0, ["Balboa Park", "La Jolla Cove"], "Campland on the Bay", []),
        ("los angeles", "Los Angeles", 200, ["Santa Monica Pier", "Griffith Observatory"], "Dockweiler RV Park (Playa del Rey)", []),
        ("santa barbara", "Santa Barbara", 350, ["Old Mission Santa Barbara", "Stearns Wharf"], "Carpinteria State Beach", []),
        ("morro bay", "Morro Bay", 510, ["Morro Rock", "Hearst Castle (San Simeon)"], "Morro Bay State Park", ["big_sur"]),
        ("monterey", "Monterey", 720, ["Monterey Bay Aquarium", "17-Mile Drive", "Carmel-by-the-Sea"], "Marina Dunes RV Park (Marina)", ["big_sur"]),
        ("san francisco", "San Francisco", 900, ["Golden Gate Bridge viewpoints", "Muir Woods (reservation needed)"], "San Francisco RV Resort (Pacifica)", []),
        ("fort bragg", "Fort Bragg", 1180, ["Mendocino village", "Glass Beach"], "MacKerricher State Park", []),
        ("orick", "Orick (Redwoods)", 1430, ["Avenue of the Giants", "Lady Bird Johnson Grove"], "Elk Prairie Campground, Prairie Creek Redwoods SP", ["redwood_rv"]),
        ("crescent city", "Crescent City", 1540, ["Stout Grove", "Battery Point Lighthouse"], "Jedediah Smith Redwoods SP campground", ["redwood_rv"]),
        ("coos bay", "Coos Bay / Bandon", 1730, ["Bandon beach sea stacks", "Cape Arago"], "Sunset Bay State Park", ["oregon_coast"]),
        ("newport", "Newport", 1920, ["Oregon Coast Aquarium", "Yaquina Head lighthouse"], "South Beach State Park", ["oregon_coast"]),
        ("astoria", "Astoria", 2130, ["Cannon Beach / Haystack Rock", "Astoria Column"], "Fort Stevens State Park", ["oregon_coast"]),
        ("olympia", "Olympia", 2340, ["Washington State Capitol", "Nisqually wildlife refuge"], "Millersylvania State Park", []),
        ("seattle", "Seattle", 2440, ["Pike Place Market", "Kerry Park view"], "Dash Point State Park (Federal Way)", []),
        ("bellingham", "Bellingham", 2580, ["Chuckanut Drive", "Fairhaven"], "Larrabee State Park", []),
        ("vancouver", "Vancouver", 2680, ["Stanley Park", "Granville Island"], "Capilano River RV Park (North Vancouver)", []),
    ],
    "always": ["wildfire"],
}

I5 = {
    "name": "Fast inland (I-5)",
    "kind": "fast",
    "points": [
        ("san diego", "San Diego", 0, ["Balboa Park", "Old Town San Diego"], "Campland on the Bay", []),
        ("los angeles", "Los Angeles", 200, ["Griffith Observatory", "Santa Monica Pier"], "Dockweiler RV Park (Playa del Rey)", ["grapevine"]),
        ("los banos", "Los Banos", 620, ["Grapevine summit (Tejon Pass)", "San Luis Reservoir"], "San Luis Reservoir State Recreation Area", ["grapevine"]),
        ("san francisco", "San Francisco", 620, ["Golden Gate Bridge viewpoints", "Fisherman's Wharf"], "San Francisco RV Resort (Pacifica)", []),
        ("sacramento", "Sacramento", 820, ["Old Sacramento", "California State Railroad Museum"], "Cal Expo RV Park", []),
        ("mount shasta", "Mount Shasta area", 1160, ["Shasta Dam", "Castle Crags"], "Castle Crags State Park", ["siskiyou"]),
        ("medford", "Medford / Gold Hill", 1340, ["Ashland", "Crater Lake (side trip, seasonal)"], "Valley of the Rogue State Park", ["siskiyou", "crater_lake"]),
        ("eugene", "Eugene", 1610, ["Skinner Butte", "McKenzie River (side trip)"], "Armitage Park campground", []),
        ("portland", "Portland", 1790, ["Multnomah Falls (side trip)", "Powell's Books"], "Champoeg State Heritage Area", []),
        ("seattle", "Seattle", 2060, ["Pike Place Market", "Kerry Park view"], "Dash Point State Park (Federal Way)", []),
        ("bellingham", "Bellingham", 2200, ["Chuckanut Drive", "Fairhaven"], "Larrabee State Park", []),
        ("vancouver", "Vancouver", 2290, ["Stanley Park", "Granville Island"], "Capilano River RV Park (North Vancouver)", []),
    ],
    "always": ["wildfire"],
}
# The I-5 list has San Francisco as an alternative start; it is only used when the deal starts there.
I5_SF_ONLY = "san francisco"

VEGAS = {
    "name": "Desert and Cascades (US-95 / US-97 / I-5)",
    "kind": "scenic",
    "points": [
        ("phoenix", "Phoenix", 0, ["Desert Botanical Garden", "Camelback Mountain"], "Look up current RV parks in Phoenix", ["desert_heat"]),
        ("kingman", "Kingman", 300, ["Historic Route 66 museum", "Oatman (side trip)"], "Look up current RV parks in Kingman", ["desert_heat"]),
        ("las vegas", "Las Vegas", 480, ["Hoover Dam", "Red Rock Canyon"], "Look up current RV parks in Las Vegas", ["desert_heat"]),
        ("beatty", "Beatty", 670, ["Rhyolite ghost town", "Death Valley (side trip)"], "Furnace Creek Campground, Death Valley NP (side trip)", ["desert_heat"]),
        ("hawthorne", "Hawthorne / Walker Lake", 990, ["Walker Lake", "Tonopah Historic Mining Park (on the way)"], "Walker Lake (Sportsman's Beach) recreation area", ["desert_heat", "high_desert"]),
        ("reno", "Reno", 1170, ["Virginia City", "Lake Tahoe (side trip)"], "Washoe Lake State Park", ["high_desert"]),
        ("susanville", "Susanville", 1340, ["Eagle Lake", "Bizz Johnson rail trail"], "Eagle Lake campgrounds, Lassen National Forest (seasonal)", ["high_desert"]),
        ("klamath falls", "Klamath Falls", 1600, ["Upper Klamath Lake", "Crater Lake (side trip, seasonal)"], "Collier Memorial State Park (Chiloquin)", ["high_desert", "crater_lake"]),
        ("bend", "Bend", 1830, ["Smith Rock State Park", "Newberry Volcanic Monument"], "Tumalo State Park", ["high_desert"]),
        ("the dalles", "The Dalles", 2040, ["Columbia River Gorge", "Multnomah Falls"], "Memaloose State Park (seasonal)", []),
        ("portland", "Portland", 2170, ["Powell's Books", "Washington Park"], "Champoeg State Heritage Area", []),
        ("seattle", "Seattle", 2440, ["Pike Place Market", "Kerry Park view"], "Dash Point State Park (Federal Way)", []),
        ("bellingham", "Bellingham", 2580, ["Chuckanut Drive", "Fairhaven"], "Larrabee State Park", []),
        ("vancouver", "Vancouver", 2670, ["Stanley Park", "Granville Island"], "Capilano River RV Park (North Vancouver)", []),
    ],
    "always": ["wildfire"],
}

_ROCKIES_TAIL = [
    ("kamloops", "Kamloops", 0, ["Riverside Park", "BC Wildlife Park"], "Paul Lake Provincial Park", ["bc_parks", "bc_winter"]),
    ("merritt", "Merritt", 90, ["Nicola Valley lakes", "Coquihalla summit"], "Monck Provincial Park", ["bc_parks", "coquihalla", "bc_winter"]),
    ("hope", "Hope", 200, ["Othello Tunnels (seasonal)", "Bridal Veil Falls"], "Silver Lake Provincial Park", ["bc_parks", "coquihalla", "bc_winter"]),
    ("vancouver", "Vancouver", 350, ["Stanley Park", "Granville Island"], "Capilano River RV Park (North Vancouver)", []),
]


def _shift(points, km0):
    return [(k, n, km + km0, s, c, w) for (k, n, km, s, c, w) in points]


ROCKIES_CALGARY = {
    "name": "Through the Rockies (Hwy 1)",
    "kind": "scenic",
    "points": [
        ("calgary", "Calgary", 0, ["Calgary Tower", "Heritage Park"], "Look up current RV parks in Calgary", []),
        ("banff", "Banff", 130, ["Lake Minnewanka", "Banff Gondola"], "Tunnel Mountain Village II (Banff NP)", ["rockies_parks", "parks_pass"]),
        ("lake louise", "Lake Louise", 190, ["Lake Louise lakeshore", "Moraine Lake (shuttle, seasonal)"], "Lake Louise hard-sided campground", ["rockies_parks", "parks_pass"]),
        ("golden", "Golden", 270, ["Kicking Horse Pass", "Emerald Lake (Yoho NP)"], "Golden Municipal Campground", ["bc_winter", "rogers", "parks_pass"]),
        ("revelstoke", "Revelstoke", 420, ["Rogers Pass Discovery Centre", "Meadows in the Sky Parkway (summer)"], "Blanket Creek Provincial Park", ["bc_winter", "rogers", "bc_parks"]),
        ("salmon arm", "Salmon Arm", 525, ["Shuswap Lake", "Salmon Arm wharf"], "Shuswap Lake Provincial Park (Scotch Creek)", ["bc_winter", "bc_parks"]),
    ] + _shift(_ROCKIES_TAIL, 630),
    "always": ["wildfire"],
}

ROCKIES_EDMONTON = {
    "name": "Jasper and the Yellowhead (Hwy 16 / Hwy 5)",
    "kind": "scenic",
    "points": [
        ("edmonton", "Edmonton", 0, ["Muttart Conservatory", "Old Strathcona"], "Look up current RV parks in Edmonton", []),
        ("hinton", "Hinton", 290, ["Beaver Boardwalk", "Athabasca Lookout"], "William A. Switzer Provincial Park", []),
        ("jasper", "Jasper", 365, ["Maligne Canyon", "Jasper SkyTram (seasonal)"], "Whistlers or Wapiti campground (Jasper NP)", ["rockies_parks", "parks_pass", "jasper_fire"]),
        ("mount robson", "Mount Robson", 450, ["Mount Robson visitor centre", "Rearguard Falls"], "Robson Meadows, Mount Robson Provincial Park", ["bc_parks", "bc_winter"]),
        ("clearwater", "Clearwater", 690, ["Wells Gray Park: Helmcken Falls", "Spahats Creek Falls"], "North Thompson River Provincial Park", ["bc_parks", "bc_winter"]),
    ] + _shift(_ROCKIES_TAIL, 815),
    "always": ["wildfire"],
}

_TC = [  # Sudbury to Calgary along the Trans-Canada, km from Sudbury
    ("sudbury", "Sudbury", 0, ["Science North", "Big Nickel"], "Windy Lake Provincial Park", ["ont_parks"]),
    ("sault ste marie", "Sault Ste. Marie", 310, ["Agawa Canyon Tour Train (seasonal)", "Boardwalk on the St. Marys River"], "Pancake Bay Provincial Park (80 km north)", ["ont_parks", "superior"]),
    ("wawa", "Wawa", 540, ["Agawa Rock pictographs", "Wawa goose"], "Rabbit Blanket Lake, Lake Superior Provincial Park", ["ont_parks", "superior"]),
    ("marathon", "Marathon", 720, ["Pukaskwa National Park", "Pebble beach"], "Neys Provincial Park", ["ont_parks", "superior"]),
    ("nipigon", "Nipigon", 890, ["Nipigon River Bridge lookout", "Red Rock cuesta"], "Rainbow Falls Provincial Park", ["ont_parks", "superior"]),
    ("thunder bay", "Thunder Bay", 1000, ["Kakabeka Falls", "Terry Fox Monument"], "Kakabeka Falls Provincial Park", ["ont_parks", "superior"]),
    ("dryden", "Dryden", 1340, ["Wabigoon Lake", "Max the Moose"], "Aaron Provincial Park", ["ont_parks", "superior"]),
    ("kenora", "Kenora", 1480, ["Lake of the Woods cruise (seasonal)", "Kenora harbourfront"], "Rushing River Provincial Park", ["ont_parks"]),
    ("winnipeg", "Winnipeg", 1690, ["The Forks", "Canadian Museum for Human Rights"], "Birds Hill Provincial Park", ["prairie"]),
    ("brandon", "Brandon", 1900, ["Riverbank Discovery Centre", "Spruce Woods sand dunes (side trip)"], "Spruce Woods Provincial Park (side trip)", ["prairie"]),
    ("regina", "Regina", 2260, ["RCMP Heritage Centre", "Wascana Centre"], "Buffalo Pound Provincial Park", ["prairie"]),
    ("swift current", "Swift Current", 2500, ["Saskatchewan Landing", "Swift Current Museum"], "Saskatchewan Landing Provincial Park", ["prairie"]),
    ("medicine hat", "Medicine Hat", 2720, ["Saamis Tepee", "Cypress Hills (side trip)"], "Cypress Hills Interprovincial Park (Elkwater, side trip)", ["prairie"]),
    ("calgary", "Calgary", 3010, ["Calgary Tower", "Heritage Park"], "Look up current RV parks in Calgary", []),
]
_ROCKIES_AFTER_CALGARY = [p for p in ROCKIES_CALGARY["points"] if p[0] != "calgary"]

TRANS_CANADA_TORONTO = {
    "name": "Trans-Canada (Hwy 69 / 17 / 1)",
    "kind": "fast",
    "points": [
        ("toronto", "Toronto", 0, ["CN Tower", "Distillery District"], "Look up current RV parks near Toronto", ["ont_parks"]),
        ("parry sound", "Parry Sound", 230, ["30,000 Islands cruise (seasonal)", "Killbear beaches"], "Killbear Provincial Park", ["ont_parks"]),
    ] + _shift(_TC, 390) + _shift(_ROCKIES_AFTER_CALGARY, 3400 - 0),
    "always": ["wildfire", "bc_winter"],
}

TRANS_CANADA_MONTREAL = {
    "name": "Trans-Canada via Ottawa (Hwy 17 / 1)",
    "kind": "fast",
    "points": [
        ("montreal", "Montreal", 0, ["Old Montreal", "Mount Royal lookout"], "Look up current RV parks near Montreal", ["ont_parks"]),
        ("ottawa", "Ottawa", 200, ["Parliament Hill", "ByWard Market"], "Look up current RV parks near Ottawa", ["ont_parks"]),
        ("mattawa", "Mattawa", 520, ["Ottawa River lookouts", "Voyageur Heritage Centre"], "Samuel de Champlain Provincial Park", ["ont_parks"]),
    ] + _shift(_TC, 730) + _shift(_ROCKIES_AFTER_CALGARY, 3740),
    "always": ["wildfire", "bc_winter"],
}

CORRIDORS = [COAST, I5, VEGAS, ROCKIES_CALGARY, ROCKIES_EDMONTON, TRANS_CANADA_TORONTO, TRANS_CANADA_MONTREAL]

# Unambiguous names for Google Maps links ("Hope" alone could be anywhere).
MAPS = {
    "san diego": "San Diego, CA", "los angeles": "Los Angeles, CA", "santa barbara": "Santa Barbara, CA",
    "morro bay": "Morro Bay, CA", "monterey": "Monterey, CA", "san francisco": "San Francisco, CA",
    "fort bragg": "Fort Bragg, CA", "orick": "Orick, CA", "crescent city": "Crescent City, CA",
    "coos bay": "Coos Bay, OR", "newport": "Newport, OR", "astoria": "Astoria, OR", "olympia": "Olympia, WA",
    "seattle": "Seattle, WA", "bellingham": "Bellingham, WA", "vancouver": "Vancouver, BC",
    "los banos": "Los Banos, CA", "sacramento": "Sacramento, CA", "mount shasta": "Mount Shasta, CA",
    "medford": "Medford, OR", "eugene": "Eugene, OR", "portland": "Portland, OR",
    "phoenix": "Phoenix, AZ", "kingman": "Kingman, AZ", "las vegas": "Las Vegas, NV", "beatty": "Beatty, NV",
    "hawthorne": "Hawthorne, NV", "reno": "Reno, NV", "susanville": "Susanville, CA",
    "klamath falls": "Klamath Falls, OR", "bend": "Bend, OR", "the dalles": "The Dalles, OR",
    "calgary": "Calgary, AB", "banff": "Banff, AB", "lake louise": "Lake Louise, AB", "golden": "Golden, BC",
    "revelstoke": "Revelstoke, BC", "salmon arm": "Salmon Arm, BC", "kamloops": "Kamloops, BC",
    "merritt": "Merritt, BC", "hope": "Hope, BC", "edmonton": "Edmonton, AB", "hinton": "Hinton, AB",
    "jasper": "Jasper, AB", "mount robson": "Mount Robson Provincial Park, BC", "clearwater": "Clearwater, BC",
    "toronto": "Toronto, ON", "parry sound": "Parry Sound, ON", "sudbury": "Sudbury, ON",
    "sault ste marie": "Sault Ste. Marie, ON", "wawa": "Wawa, ON", "marathon": "Marathon, ON",
    "nipigon": "Nipigon, ON", "thunder bay": "Thunder Bay, ON", "dryden": "Dryden, ON", "kenora": "Kenora, ON",
    "winnipeg": "Winnipeg, MB", "brandon": "Brandon, MB", "regina": "Regina, SK",
    "swift current": "Swift Current, SK", "medicine hat": "Medicine Hat, AB", "montreal": "Montreal, QC",
    "ottawa": "Ottawa, ON", "mattawa": "Mattawa, ON",
}

# ------------------------------------------------------------------ free and cheap overnight options
# General rules by region, not promises about a specific spot: every option is "check before you go",
# and each night gets a map search for free camping near that town.
FREE_BY_REGION = {
    "US": [
        ("National forest or BLM land", "Free dispersed camping, no hookups, usually up to 14 days in any 28"),
        ("Store car parks", "Some Walmart, Cabela's and Cracker Barrel stores allow one night: ask inside first"),
        ("Rest areas", "A few hours' sleep is allowed in some states; check the posted limit"),
    ],
    "BC": [
        ("BC recreation sites", "Many free or low-cost forest sites on gravel roads; first come, first served"),
        ("Rest areas", "Short rest stops only: no camping set-up"),
    ],
    "AB": [
        ("Provincial recreation areas", "Basic sites, often cheaper than parks; some free in the off-season"),
        ("Store car parks", "Some stores allow one night: ask inside first"),
    ],
    "MB": [("Store car parks", "Some stores allow one night: ask inside first")],
    "SK": [("Store car parks", "Some stores allow one night: ask inside first"),
           ("Regional parks", "Small-town parks, often cheaper than provincial parks")],
    "ON": [
        ("Crown land", "Free for Canadian residents, up to 21 days on one site; visitors from outside Canada need a permit in the north; no services"),
        ("Store car parks", "Some stores allow one night: ask inside first"),
    ],
    "QC": [("Store car parks", "Some stores allow one night: ask inside first")],
}
NATIONAL_PARK_NOTE = "Inside national parks you must use a campground: no free camping."
CITY = {"vancouver", "seattle", "los angeles", "san francisco", "san diego", "las vegas", "phoenix",
        "toronto", "montreal", "ottawa", "calgary", "edmonton", "portland", "sacramento", "winnipeg"}
IN_NATIONAL_PARK = {"banff", "lake louise", "jasper"}
STATE_TO_REGION = {"CA": "US", "OR": "US", "WA": "US", "NV": "US", "AZ": "US"}


def free_options(key: str) -> tuple[list[tuple[str, str]], str]:
    """([(option, detail)], note) for an overnight stop."""
    place = MAPS.get(key, "")
    code = place.rsplit(", ", 1)[-1] if ", " in place else ""
    region = STATE_TO_REGION.get(code, code)
    opts = list(FREE_BY_REGION.get(region, []))
    note = ""
    if key in IN_NATIONAL_PARK:
        note = NATIONAL_PARK_NOTE
        opts = []
    elif key in CITY:
        note = "Free overnight spots are rare in the city: plan a paid site here, or stay free outside town."
        opts = [o for o in opts if o[0] == "Store car parks"]
    return opts, note


FREE_TIP = ("Free spots have no hookups. Fill water and empty tanks at a sani-dump (many gas stations, "
            "rest areas and campgrounds have one), and keep the RV's power for lights and the fridge.")
