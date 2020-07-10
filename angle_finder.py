import collections
import heapq
import sys
from decimal import *

import motions


# QUICK USAGE:
#
# MOVEMENT_OPTIONS --- Motions grouped by the game state required to perform them.
#
# BASIC_COSTS --- How to rank each motion.
#      "ess up": 0.5,
#      "turn left": 1.0,
#    means that "turn left" is 2x faster/easier than "ess up".
#
# COST_CHAINS --- Sequential motions that are faster/slower.
#      ("ess left", "ess left"): 0.5,
#    means that every "ess left" preceded by an "ess left" costs 0.5.
#
#    e.g. "ess left / turn left / ess left" = 1.0 + 1.0 + 1.0
#    but  "ess left / ess left  / ess left" = 1.0 + 0.5 + 0.5
#
# COST_FLEX --- When returning multiple possible motion sequences, how much the
# total cost can deviate from optimal before it's not worth considering.
#
# Go to the bottom of this file to select angles and run the search.

getcontext().prec = 4 # Decimal to 4 places
sys.setrecursionlimit(5000) # basic searches can get a lil' wild

COST_FLEX = Decimal(8.0) #Not sure why but setting this higher yields more valid results and less fake ones
COST_TABLE = {}

MOVEMENT_OPTIONS = {
    "basic": [
        "ess left",
        "ess right",
    ],
    "target enabled": [
        "ess up",
        "turn left",
        "turn right",
        "turn 180",
    ],
    "no carry": [
        "sidehop sideroll left",
        "sidehop sideroll right",
        "ess down sideroll",
        "backflip sideroll",
    ],
    "sword": [
        "sword spin shield cancel",
    ],
    "biggoron": [
        "biggoron slash shield cancel",
        "biggoron spin shield cancel",
    ],
    "hammer": [
        "hammer shield cancel",
    ],
    "shield corners": [
        "shield top-right",
        "shield top-left",
        "shield bottom-left",
        "shield bottom-right",
    ],
    "c-up": [
        "c-up left",
        "c-up right",
    ],
    "deku": [
        "deku bubble left",
        "deku bubble right",
        "deku spin",
    ],
}
BASIC_COSTS = {
    "ess up": Decimal(0.75),
    "ess left": Decimal(0.1),
    "ess right": Decimal(0.1),
    "turn left": Decimal(1.0),
    "turn right": Decimal(1.0),
    "turn 180": Decimal(1.0),
    "sidehop sideroll left": Decimal(1.0),
    "sidehop sideroll right": Decimal(1.0),
    "ess down sideroll": Decimal(1.0),
    "backflip sideroll": Decimal(1.0),
    "sword spin shield cancel": Decimal(1.25),
    "biggoron slash shield cancel": Decimal(1.25),
    "biggoron spin shield cancel": Decimal(1.25),
    "hammer shield cancel": Decimal(1.25),
    "shield top-right": Decimal(1.0),
    "shield top-left": Decimal(1.0),
    "shield bottom-left": Decimal(1.0),
    "shield bottom-right": Decimal(1.0),
    "c-up left": Decimal(3.05),
    "c-up right": Decimal(3.05),
    "deku bubble left": Decimal(3.05),
    "deku bubble right": Decimal(3.05),
    "deku spin": Decimal(0.75),
}
COST_CHAINS = {
    # Consecutive identical movements remove the overhead, so each only costs a frame (0.05s).
    ("ess left", "ess left"): Decimal(0.05),
    ("ess right", "ess right"): Decimal(0.05),
    ("c-up left", "c-up left"): Decimal(0.05),
    ("c-up right", "c-up right"): Decimal(0.05),
    ("deku bubble left", "deku bubble left"): Decimal(0.05),
    ("deku bubble right", "deku bubble right"): Decimal(0.05),

    # Don't ever consider changing directions for reversible movements.
    ("ess left", "ess right"): Decimal(100),
    ("ess right", "ess left"): Decimal(100),
    ("c-up left", "c-up right"): Decimal(100),
    ("c-up right", "c-up left"): Decimal(100),

    # Don't consider any paths that have ess after a c-up to remove duplicates.
    ("c-up left", "ess left"): Decimal(100),
    ("c-up right", "ess right"): Decimal(100),
    ("c-up left", "ess right"): Decimal(100),
    ("c-up right", "ess left"): Decimal(100),    
}


# ALGORITHM OVERVIEW
#
# There are 65536 angles possible, ranging 0x0000-0xFFFF.  There are several
# motions available that change the angle in different ways.
#
# The state of Link's angle is represented by a directed graph.  The nodes are
# angles; the edges are motions between angles.  We want to navigate the graph
# from one node to another in a way that minimizes the cost.
#
#     0x0000 -----(ess left)---------> 0x0708
#        \
#         --(sidehop sideroll left)--> 0xF070
#      ...
#
# The camera is pretty complicated, so some motions don't just "rotate Link
# X units clockwise".  In other words, they're not linear, or even invertible.
# We treat individual motions as opaque functions from angles to angles.  Those
# functions are located in "motions.py".
#
# The algorithm is:
#    1. Construct an empty graph.
#    2. Mark edges in the graph, exploring the fastest nodes first.
#    3. Walk backwards through the graph, starting from the final angle.
#
# Angles can be reached from many motion sequences.  The scoring we use won't
# be perfect for everyone, so to allow some variation we record multiple
# motions into each angle.  Specifically, at each node, we record the best
# edge into it for a given motion, treating our scoring as perfect.  Then, at
# the end, we return paths that are roughly as fast as the best path.  This
# seems to work well.


# Node
#   edges_in   - list of edges into this node
#   best       - float cost of the fastest path to this node; 'None' if the
#                node hasn't been encountered yet
# Edge
#   from_angle - integer angle (not a node object) this edge comes from
#   motion     - string, e.g. "ess up"
#   cost       - float cost of the fastest path to this edge, plus the cost of
#                the motion - could be different from the destination node's
#                'best' if this edge isn't on the fastest path to the node
Node = collections.namedtuple("Node", ["edges_in", "best"])
Edge = collections.namedtuple("Edge", ["from_angle", "motion", "cost"])

empty_node = lambda: Node(edges_in={}, best=None)


def maybe_add_edge(graph, edge, to_angle):
    """
    Add an edge to an angle, but only if the edge is the fastest way to get to
    the node for a given motion.

    Returns True if the edge was added, False if it wasn't.
    """

    def min_none(x, y):
        return x if (x is not None and x < y) else y

    to_node = graph[to_angle]
    edges_in = to_node.edges_in

    def add_edge():
        edges_in[edge.motion] = edge
        best = min_none(to_node.best, edge.cost)
        graph[to_angle] = Node(edges_in, best)

    if to_node.best == None:
        add_edge()  # first edge to the node
        return True

    if edge.cost > to_node.best + COST_FLEX:
        # edge costs too much
        return False

    if (edge.motion not in edges_in) or (edge.cost < edges_in[edge.motion].cost):
        # first edge via this motion, or cheaper than the previous edge via this motion
        add_edge()
        return True

    # have already found this node, via this motion, at least as quickly
    return False


def edges_out(graph, angle, last_motion, last_cost):
    """
    Iterator of edges out of an angle, given some particular previous motion and
    cost.  Needs the previous motion to calculate the cost of a chained motion.
    """

    if graph[angle].best < last_cost:
        # skip all edges if this edge isn't the cheapest way out
        # misses some valid edges, but it doesn't seem to matter much
        return

    for (motion, cost_increase) in COST_TABLE[last_motion].items():
        new_angle = motions.table[motion](angle)

        if new_angle is None:
            continue

        to_angle = new_angle & 0xFFFF
        from_angle = angle
        cost = last_cost + cost_increase

        yield (to_angle, Edge(from_angle, motion, cost))


def explore(starting_angles):
    """Produce a graph from the given starting angles."""

    graph = [empty_node() for _ in range(0xFFFF + 1)]
    queue = []  # priority queue of '(edge_cost, from_angle, last_motion)'
    seen = 0

    for angle in starting_angles:
        edges_in = {None: Edge(from_angle=None, motion=None, cost=0)}
        best = 0

        graph[angle] = Node(edges_in, best)
        heapq.heappush(queue, (Decimal(0.0), angle, None))
        seen += 1

    previous_cost = 0  # only print status when cost increases

    while len(queue) > 0:
        if seen == (0xFFFF + 1):
            # have encountered all nodes, exit early
            # misses some valid edges, but it doesn't seem to matter much
            break

        (cost, angle, motion) = heapq.heappop(queue)

        if cost > previous_cost + Decimal(1.0):
            print(f"Exploring ({len(queue)}), current cost at {cost}", end="\r")
            previous_cost = cost

        for to_angle, edge in edges_out(graph, angle, motion, cost):
            if graph[to_angle].best == None:
                seen += 1

            if maybe_add_edge(graph, edge, to_angle):
                # this is a new or cheaper edge, explore from here
                heapq.heappush(queue, (edge.cost, to_angle, edge.motion))

    print("\nDone.")
    return graph


# A path is a list of motions, e.g. ["ess up", "ess up", "turn left"].


def cost_of_path(path):
    cost = 0
    last = None
    for next in path:
        cost += COST_TABLE[last][next]
        last = next
    return cost


def navigate_all(graph, angle, path=None, seen=None, flex=COST_FLEX):
    """
    Iterator of paths to a given angle, whose costs differ from the best
    path by no more than COST_FLEX.

    The first yielded path is guaranteed to be the cheapest (or tied with other
    equally cheapest paths), but the second path is NOT necessarily
    second-cheapest (or tied with the first).  The costs of yielded paths are
    not ordered except for the first.

    Yields values of the form
        (angle, path)
    where 'angle' is an integer 0x0000-0xFFFF, and 'path' is a list of motions.
    """

    # 'flex' starts at the maximum permissible deviation from the optimal path.
    # As the function recurses, 'flex' decreases by the deviation from optimal
    # at each node.

    if path is None:
        # instantiate new objects in case the function is called multiple times
        path = []
        seen = set()

    node = graph[angle]

    if None in node.edges_in:
        # this is a starting node
        yield angle, list(reversed(path))

    elif angle in seen:
        # found a cycle (possible by e.g. 'ess left'->'ess right', where 'flex'
        # lets the running cost increase a little)
        pass

    else:
        seen.add(angle)

        # explore the fastest edges first
        # note that this doesn't guarantee the ordering of paths; some paths
        #   through a slower edge at this step might be faster in the end
        # however, A fastest path will be yielded first
        edges = sorted(node.edges_in.values(), key=lambda e: e.cost)

        for edge in edges:
            new_flex = (node.best - edge.cost) + flex

            if new_flex < 0:
                # ran out of flex!  any paths from here will cost too much
                break

            path.append(edge.motion)
            yield from navigate_all(graph, edge.from_angle, path, seen, new_flex)
            path.pop()

        seen.remove(angle)


def print_path(angle, description, path):
    # keep track of repeated motions to simplify the path reading
    prev_motion    = None
    iterations     = 1
    motions_output = []

    print("start at {:#06x}: ".format(angle)+description)

    for motion in path:
        if prev_motion == motion:
            # keep track of how many times a motion is repeated
            iterations += 1
        elif prev_motion:
            # once it stops repeating, add it to the motion list
            motions_output.append({
                "motion": f"{iterations} {prev_motion}",
                "angle":  f"0x{angle:04x}"
            })
            iterations = 1

        # update the angle using the current motion and set prev_motion
        angle = motions.table[motion](angle) & 0xFFFF
        prev_motion = motion

    # finally, run one last time
    motions_output.append({
        "motion": f"{iterations} {prev_motion}",
        "angle":  f"0x{angle:04x}"
    })

    # get the padding amount based on the length for the largest motion string
    text_length = len(max([output["motion"] for output in motions_output], key=len))
    for motion in motions_output:
        # print out each motion
        print(f"{motion['motion']:<{text_length}} to {motion['angle']}")


def collect_paths(graph, angle, sample_size=sys.maxsize, number=10):
    """Sample 'sample_size' paths, returning the 'number' cheapest of those.

    Returns a list of
        (cost, angle, path)
    where 'cost' is the float cost, 'angle' is an integer 0x0000-0xFFFF,
    and 'path' is a list of motions.
    """

    paths = []

    for angle, path in navigate_all(graph, angle):
        paths.append((cost_of_path(path), angle, path))

##        if len(paths) == sample_size:
##            break

    paths.sort()
    return paths[:number]


def initialize_cost_table():
    COST_TABLE[None] = BASIC_COSTS.copy()

    for motion, cost in BASIC_COSTS.items():
        COST_TABLE[motion] = BASIC_COSTS.copy()
    for (first, then), cost in COST_CHAINS.items():
        COST_TABLE[first][then] = cost

    all_motions = set(BASIC_COSTS.keys())
    allowed_motions = {m for group in ALLOWED_GROUPS for m in MOVEMENT_OPTIONS[group]}
    disallowed_motions = all_motions - allowed_motions

    for motion in disallowed_motions:
        del COST_TABLE[motion]
    for first in COST_TABLE:
        for motion in disallowed_motions:
            del COST_TABLE[first][motion]


ALLOWED_GROUPS = [
     "basic",
##     "target enabled",
##     "no carry",
##     "sword",
##     "biggoron",
##     "hammer",
##     "shield corners",
##     "c-up",
##     "deku",
]

initialize_cost_table()


if __name__ == "__main__":
    
    ALLOWED_ANGLE_GROUPS = [
        "cardinals",
        "downstairs",
##        "downstairs climbable",
##        "upstairs",
##        "damage boost",
        ]

    cardinals_dict = {
        0x0000: "Southern wall (entrance to tunnel, observatory door)",
        0x4000: "Eastern wall (tunnel, starpost by observatory door)",
        0x8000: "Northern wall (double boxes, yellow stair flight, couch)",
        0xc000: "Western wall (tunnel, starpost by observatory door)",
        }
        
    downstairs_dict = {
        0x54d1: "SW face of vase",
        0x1526: "NW face of vase",
        0xd4d1: "NE face of face",
        0x2aac: "SE downstairs wall",
        0x5554: "NE downstairs wall (cyan stair flight)",
        0xd563: "Cyan staircase railing",
        0x9a42: "Bottom edge of railing",
        0x5572: "Outside of stairs, front",
        0x556b: "Outside of stairs, middle",
        0x555b: "Outside of stairs, back",
        0x673f: "Corner between crystal and vase",
        0x794c: "Corner between vase and double boxes",
        0xa9fe: "Corner between double boxes and stacked boxes",
        0xabe3: "Stacked boxes",
        0x6228: "Cucco feed",
        0x8207: "Corner between Cucco feed and climbable box",
        0xaab4: "Climbable box, climbable globe table",
        0xea51: "Corner between climbable box and climbable globe table",
        0x87ab: "Corner between climbable globe table and wall",
        0xd554: "SW downstairs wall (clock)",
        }
    
    downstairs_climbable_dict = {
        0xaaac: "Wall behind climbable box",
        0xaa95: "Wall behind climbable globe table",
        0xeaa5: "Globe",
        0xeb27: "Globe spin axis support",
        }
        
    upstairs_dict = {
        0xaa6f: "NW wall (red stair flight)",
        0xaa68: "NW wall trim",
        0xaa42: "NW wall trim corner ",
        0xd57a: "SW wall trim corner",
        0xd589: "SW wall trim (magenta stair flight)",
        0xd5a7: "NE face of all starposts",
        0x95a7: "SE face of starpost at top of stairs",
        0xd535: "SW upstairs wall",
        0x28c2: "SE upstairs wall",
        0x554c: "NE upstairs wall",
        0xaab4: "NW upstairs wall",
        0xd52d: "Railing by couch",
        0xff01: "N face of telescope platform",
        0x14c9: "NW face of starposts",
        0x9602: "SE face of starposts on telescope platform",
        0xd581: "Telescope front side",
        0x16ee: "Telescope right side",
        0x6ab4: "Telescope back side",
        0x93ae: "Telescope left side",
        0xaa95: "SE face of telescope platform",
        0x563e: "SW face of telescope platform",
        0x564c: "Inner wall near top of magenta stairs",
        0x56ca: "Inner wall near middle/bottom of magenta stairs",
        0x2ac3: "Red staircase railing",
        }

    #The cost algorithm seems to have a hard time finding the best one when there's multiple initial angles,
    #due to assuming that you should break up multiple ESS or C-Ups into separate steps, even going so far
    #as to include reversing direction for no reason. As a workaround, only uncomment one at a time.
    damage_boost_dict = {
	0x2bbc: "place bomb in corner by vase, crouchstab, slash",
	0x40f4: "hold bomb after",
	0x2d2c: "2 fast slashes",
	0x28b4: "drop against tunnel wall, crouchstab",
	0x2d0c: "drop against tunnel wall, vert slash, 2 hold b",
	0x4244: "hold bomb after",
	0x2d24: "vert, crouch, 2 hold",
	0x0edc: "back wall, 3 hori",
	0x03d4: "no walls, vert slash",
	0x4244: "hold bomb after",
	0x0c7c: "vert, hold",
	0x19dc: "back wall hori, vert hold",
	0x1fdc: "hold bomb after",
	0x0cf4: "2 hori, vert hold",
	0x2d14: "vase, vert hold, hori hold, hori",
	0x3024: "vase, vert, vert hold, hori hold",
	0x62bc: "vase, throw, 2 vert",
	0x65fc: "vase, throw, jumpslash",
	0x2d24: "3 hori, jump",
	0x2a24: "vert, hori, vert, jump",
	0x307c: "vert, fast hori",
	0x34d4: "vase, js, 2 vert, drop bomb, 3 vert?",
	0x1aac: "back wall, crouch, hori",
	0x1a04: "no walls, 4 vert",
	0x3d24: "no walls, 2 hori, 1 hold",
	0x2ab4: "no walls, 2 vert, 2 jump",
	0x249c: "no walls, 3 vert, 1 forward",
	0x25dc: "no walls, 2 vert, 1 forward",
	0x294c: "no walls, vert, thrust, hold",
	0x2d04: "vase, crouchstab, thrust",
	0x2d14: "vase, 2 crouch, 1 thrust",
	0x2bb4: "vase, 3 hori # best that ends with you not in the right position to uncull the moons tear",
	0xee2c: "ess f463, hori",
	0xbc8c: "place bomb, ess ed5b, hori",
	0xccb4: "place bomb, ess f463, 2 hori",
	0x0834: "ess f463, 3 hori",
	0x113c: "ess 178b, hori",
	0xed2c: "ess df4b, 2hold, hori",
	0xe014: "ess e653, hori",
	0x184c: "ess 1e93, hori",
	0x1544: "ess 97b, 3 hold #bestsofar",
	0xe674: "ess 97b, 1 hori, 1 hold",
	0x1754: "ess 97b, 1 hori, 2 hold",
	0x1814: "ess 1e93, 1 hori 1 hold",
	0x3174: "ess 259b, 3 hold OR shield drop instantly swordless, 1 dry roll",
	0x3384: "ess 259b, 1 hori 2 hold",
	0xfbf4: "ess 273, 1 hold",
	0x12e4: "ess 273, 2 hori 1 hold",
	0x0b64: "ess 273, 4 hori",
	0xc484: "ess f463, 2 hold",
	0xf7cc: "ess f463, 4 hori",
	0xf6ec: "ess f463, 2 hori 2 hold",
	0xfBa4: "ess e653, overhead",
	0xe3e4: "ess e653, place",
	0xe014: "ess e653, 1 hori",
	0xdfdc: "ess e653, 1 hold",
	0xe9b4: "ess e653, 4 hori",
	0xed2c: "ess df4b, 1 hori 2 hold",
	0xe06c: "ess d843, 3 hori 1 hold",
	0xd814: "ess ca33, 1 hori 2 hold",
	0xa7ec: "ess c32b, 2 hori 0 hold #ok",
	0xa024: "ess c32b, 2 hori 0 hold #actually we cannot do hold because it changes your targeting angle i am dumb.",
	0xbf0c: "ess b51x, 4",
	0xaba4: "ess aexx, 0",
	0x92dc: "ess aexx, 2",
	0xb174: "ess aexx, 4",
	0x1f84: "ess a3ab3, 2 #6e, 5c",
	0x5454: "ess 56d3, 0",
	0x3ba4: "ess 56d3, 2 #2e, 10c",
	0x6f44: "ess 6dbx, 4",
	0x7084: "ess 72xx, 0",
	0x9d44: "ess 88xx, -1",
	0xb974: "ess a42b, -1 #THIS WORKS HOLY FUCKING SHIT 84ess left",
	0xae1c: "ess a42b, 4",
	0xa4f4: "ess ab33, 1",
	0xbf0c: "ess ab33, 3",
	0xfd24: "1 ess right (259b), drop, 1 ess left (2ca3), 2 hori",
	0x4db4: "1 ess right (259b), drop, 1 ess left (2ca3), 3 hori",
	0x328c: "1 ess left (33ab), drop, 1 ess right (2ca3), 1 hori",
	0x0434: "drop, 1 ess left (33ab), 2 hori#68 ess, 8 cup",
	0x2b94: "drop, 1 ess right (259b), 1 hori#64 ess, 26 cup",
	0x4374: "shield drop, y=.345 (starts repeating here)",
	0x42dc: "shield drop, y=.334",
	0x4244: "shield drop, y=.722 (cycle2, 1st red dim) #26 ess left, 4 cup left",
	0x4434: "shield drop, y=.369",
	0x3f34: "shield drop instantly, 3 hori",
	0x359c: "shield drop instantly, 1 vert, 2 hori #31 ess left, 2 cup right #Best so far that does end with you in the right position.",
	0x2e2c: "shield drop instantly, 1 hori, 3 thrust",
	0x29b4: "shield drop instantly, 3 vert, 1 hold",
	0x2d0c: "2 ess right, shield drop instantly, 4 #39, 5",
	0xe674: "3 ess right, shield drop instantly, 0 #66, 3",
	0x440c: "3 ess right, shield drop instantly, 1",
	0x2f4c: "ess 0273 ess right, shield drop instantly, 1",
	0x02dc: "ess right to f463, shield drop instantly, 4 #33, 5",
	0x1f94: "ess lef 4fcb, shield drop instantly, 1 #32, 2",
	0x6244: "ess lef 4fcb, shield drop instantly, 3 #32, 2",
	0x2ecc: "shield drop instantly, 2 dry roll",
	0x0164: "shield drop instantly, 2 dry roll against tunnel wall #66, 11",
	0x564c: "shield drop instantly, dry roll against wall, 1 hori #47, 1",
	0x434c: "shield drop instantly, dry roll vert, thrust, crouch, dry roll in corner, vert",
	0x42dc: "shield drop, hori slash wall",
	0x353c: "vase, vert, js, shield drop bomb, 2 crouch",
	0x2624: "shield drop instantly, 4 vert #30, 4",
	0x2f44: "shield drop instantly swordless, 1 vert, 1 thrust, 1 hori or, roll, hori, js",
	0x2d1c: "shield drop instantly swordless, 1 roll, 2 vert, 1 hori #1,8 this one is fucking siiiick",
	0x2e24: "shield drop instantly swordless, 1 roll, 1 vert, 1 thrust, 1 hori",
	0x23fc: "drop bomb, pick up instadrop, 1 vert",
	0x2d04: "drop bomb, pick up instadrop, dry roll, 1 hori",
	0x28fc: "drop bomb, pick up instadrop, 1 vert, 1 thrust, 1 hori",
	0x2e24: "instadrop, vert, left, vert",
	0x37cc: "instadrop sword, vert, 2 left",
	0x38a4: "instadrop sword, vert, 3 left (or swordless, 1 untarget vert, 1 hori)",
	0x2ecc: "instadrop swordless, vert, 3 right",
	0x2bbc: "instadrop swordless, 2vert, right, thrust",
	0x32cc: "instadrop sword, vert, right",
        0x405c: "swordless, vert untarget, diagonal untarget",
        0x2d2c: "swordless, vert, thrust, diagonal untarget",
        0x328c: "swordless, crouchstab, js",
        0x2e1c: "swordless, crouchstab, 2 js, diagonal", #31, 0
        0x2e24: "swordless, crouchstab, 2 js, diagonal untarget",
        0x2e1c: "sworded, crouchstab, 2 js, diagonal untarget",
        }

    starting_angles_switcher = {
        "cardinals": cardinals_dict,
        "downstairs": downstairs_dict,
        "downstairs climbable": downstairs_climbable_dict,
        "upstairs": upstairs_dict,
        "damage boost": damage_boost_dict,        
        }
        
    starting_angles_dict = {
        }

    for angle_group in ALLOWED_ANGLE_GROUPS:
        starting_angles_dict.update(starting_angles_switcher[angle_group])
    
    starting_angles=list(starting_angles_dict)
    
    # Create a graph starting at the given angles.
    graph = explore(starting_angles)
    paths = []




    # DESIRED ANGLES - Uncomment only one.

    # Stale reference drop angle (at most 12 words prior to Link + 0xAD4)
    #for angle in list(range(0x0a44,0x0a74+0x1,0x4)):



    # JP 1.0 TARGETING ANGLES
    # Targeting angle (save context)[playing file]
    #for angle in [0xBD23]:

    # Targeting angle (heap copy)[playing file]
    #for angle in [0x1B57]:

    # Targeting angle (heap copy)[created file]
    #for angle in [0x2CA3]:

    # All targeting angles
    #for angle in [0xBD23,0x1B57,0x2CA3]:


    # JP 1.1 TARGETING ANGLES
    # Targeting angle (save context)[playing file]
    #for angle in [0xBDCF]:

    # Targeting angle (heap copy)[playing file]
    #for angle in [0x1C07]:

    # Targeting angle (heap copy)[created file]
    #for angle in [0x2D53]:

    # All targeting angles
    for angle in [0xBDCF,0x1C07,0x2D53]:


    # FACING ANGLES (same for both)
    # Facing angle (save context)
    #for angle in [0x0807]:

    # Facing angle (heap copy)
    #for angle in [0x0814]:



    
    # Collect the 5 fastest sequences of the first 50 visited.  The fastest
    # sequence collected is at least tied as the fastest sequence overall.
        paths.extend(collect_paths(graph, angle, sample_size=sys.maxsize, number=5))
    # Results seem to be better with an unlimited sample_size, but everything after the 6th
    # result is invalid with a COST_FLEX of 8. Any higher COST_FLEX increases processing time
    # dramatically, so we have to limit the number of results to 6. It still seems to miss some
    # good ones though sadly. I think it's breaking up c-ups when there's more than 2 of them.
    # It seems to disproportionately dislike large numbers of c-up and small numbers of ess.

    paths.sort()

    for cost, angle, path in paths:
        print(f"cost: {cost}\n-----")
        try:
            description = starting_angles_dict[angle]
        except:
            description=""
        print_path(angle, description, path)
        print("-----\n")

    if len(paths) == 0:
        print("No way to get to the desired angle!")
        print("Add some more motions.")
