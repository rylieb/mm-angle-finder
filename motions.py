import gzip

# generally just ess up, but also considered adjusting
# the camera when turning left / right / 180
def ess_up_adjust_noncached(angle):

    # camera bullshit as determined by manual testing

    # don't bother, these just snap to 0x4000 and 0x8000
    if (0x385F <= angle < 0x4000) or (0x794F <= angle < 0x8000):
        return False

    # these snap to 0xc001
    if 0xBEBF <= angle < 0xC001:
        return False

    # these snap to 0x0000
    if 0xFF8F <= angle:
        return False

    # these gravitate towards 0xbe81
    if 0xBE4F <= angle < 0xBE7F:
        return 0xBE81

    # these gravitate towards 0xbec1
    if 0xBE7F <= angle < 0xBEBF:
        return 0xBEC1

    # these gravitate towards 0xff91
    if 0xFF5F <= angle < 0xFF8F:
        return 0xFF91

    global camera_angles
    for index in range(len(camera_angles)):
        camera_angle = camera_angles[index]
        if (camera_angle & 0xFFF0) >= (angle & 0xFFF0):
            # more camera bullshit go to hell
            if (0xF55F <= angle < 0xF8BF) and (angle & 0xF == 0xF):
                index += 1  # if we're in the above range and last char is f
            if 0xF8BF <= angle:
                index += 1  # however this happens automatically when above 0xf8bf
            if (0xB43F <= angle < 0xB85F) and (angle & 0xF == 0xF):
                index += 1  # samething but for another value range
            if 0xB85F <= angle < 0xC001:
                index += 1  # automatic again
            if angle & 0xF == 0xF:
                # snapping up happens on the f threshold apparently
                return camera_angles[index + 1] & 0xFFFF
            return camera_angles[index] & 0xFFFF
        index += 1


CAMERA_SNAPS = []

try:
    with gzip.open("camera_snaps.txt.gz", "rt") as cam:
        for line in cam:
            if line.strip() == "False":
                CAMERA_SNAPS.append(False)
            else:
                CAMERA_SNAPS.append(int(line))
except:
    camera_angles = []
    with open("camera_favored.txt", "r") as f:
        for line in f:
            camera_angles.append(int(line.strip(), 16))

    for angle in range(0xFFFF + 1):
        if (angle % 0x1000) == 0:
            print(f"Caching camera movements ({hex(angle)})...", end="\r")
        CAMERA_SNAPS.append(ess_up_adjust_noncached(angle))
    print("\nDone.")

    with gzip.open("camera_snaps.txt.gz", "wt") as cam:
        for angle in CAMERA_SNAPS:
            print(angle, file=cam)


# basic movement options

def ess_left(angle):
    return angle + 0x0708


def ess_right(angle):
    return angle - 0x0708


# cardinal turns (gc/vc only)

def ess_up_adjust(angle):
    return CAMERA_SNAPS[angle]

def turn_left(angle):
    angle = ess_up_adjust(angle)  # camera auto adjusts similar to ess up
    if not angle:
        return None
    return angle + 0x4000


def turn_right(angle):
    angle = ess_up_adjust(angle)
    if not angle:
        return None
    return angle - 0x4000


def turn_180(angle):
    angle = ess_up_adjust(angle)
    if not angle:
        return None
    return angle + 0x8000


# c-up movement

def c_up_right(angle):
    return angle - 0x03c0


def c_up_left(angle):
    return angle + 0x03c0


# deku movement

def deku_bubble_right(angle):
    return angle - 0x379


def deku_bubble_left(angle):
    return angle + 0x377


def deku_spin(angle):
    return angle - 0x01e0


def mask_transition(angle): #jp n64 builds only (includes jp vc, but not jp gcn)
    return turn_180(angle)


#hold sidehops (all regions gcn and us/pal vc only)

def mask_hold_sidehop_left(angle):
    return angle + 0x4000

def mask_hold_sidehop_right(angle):
    return angle - 0x4000


#4 frame sidehops (all regions gcn and us/pal vc only)

def human_4_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 1*0x12C

def human_4_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 1*0x12C

def deku_4_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 1*0x258

def deku_4_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 1*0x258

def goron_4_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 1*0xB4

def goron_4_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 1*0xB4


#3 frame sidehops (all regions gcn and us/pal vc only)

def human_3_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 2*0x12C

def human_3_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 2*0x12C

def deku_3_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 2*0x258

def deku_3_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 2*0x258

def goron_3_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 2*0xB4

def goron_3_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 2*0xB4


#2 frame sidehops (all regions gcn and us/pal vc only)

def human_2_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 3*0x12C

def human_2_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 3*0x12C

def deku_2_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 3*0x258

def deku_2_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 3*0x258

def goron_2_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 3*0xB4

def goron_2_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 3*0xB4


#1 frame sidehops (all regions gcn and us/pal vc only)

def human_1_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 4*0x12C

def human_1_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 4*0x12C

def deku_1_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 4*0x258

def deku_1_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 4*0x258

def goron_1_frame_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 4*0xB4

def goron_1_frame_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 4*0xB4


#tap sidehops (us/pal n64 builds, and all gcn builds only)

def human_tap_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 5*0x12C

def human_tap_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 5*0x12C

def deku_tap_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 5*0x258

def deku_tap_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 5*0x258

def goron_tap_sidehop_left(angle):
    return mask_hold_sidehop_left(angle) - 5*0xB4

def goron_tap_sidehop_right(angle):
    return mask_hold_sidehop_right(angle) + 5*0xB4



table = {
    "ess up": ess_up_adjust,
    "ess left": ess_left,
    "ess right": ess_right,
    "turn left": turn_left,
    "turn right": turn_right,
    "turn 180": turn_180,
    "c-up right": c_up_right,
    "c-up left": c_up_left,
    "deku bubble right": deku_bubble_right,
    "deku bubble left": deku_bubble_left,
    "deku spin": deku_spin,
    "mask transition": mask_transition,
    "mask hold sidehop left": mask_hold_sidehop_left,
    "mask hold sidehop right": mask_hold_sidehop_right,
    "human 4 frame sidehop left": human_4_frame_sidehop_left,
    "human 4 frame sidehop right": human_4_frame_sidehop_right,
    "deku 4 frame sidehop left": deku_4_frame_sidehop_left,
    "deku 4 frame sidehop right": deku_4_frame_sidehop_right,
    "goron 4 frame sidehop left": goron_4_frame_sidehop_left,
    "goron 4 frame sidehop right": goron_4_frame_sidehop_right,
    "human 3 frame sidehop left": human_3_frame_sidehop_left,
    "human 3 frame sidehop right": human_3_frame_sidehop_right,
    "deku 3 frame sidehop left": deku_3_frame_sidehop_left,
    "deku 3 frame sidehop right": deku_3_frame_sidehop_right,
    "goron 3 frame sidehop left": goron_3_frame_sidehop_left,
    "goron 3 frame sidehop right": goron_3_frame_sidehop_right,
    "human 2 frame sidehop left": human_2_frame_sidehop_left,
    "human 2 frame sidehop right": human_2_frame_sidehop_right,
    "deku 2 frame sidehop left": deku_2_frame_sidehop_left,
    "deku 2 frame sidehop right": deku_2_frame_sidehop_right,
    "goron 2 frame sidehop left": goron_2_frame_sidehop_left,
    "goron 2 frame sidehop right": goron_2_frame_sidehop_right,
    "human 1 frame sidehop left": human_1_frame_sidehop_left,
    "human 1 frame sidehop right": human_1_frame_sidehop_right,
    "deku 1 frame sidehop left": deku_1_frame_sidehop_left,
    "deku 1 frame sidehop right": deku_1_frame_sidehop_right,
    "goron 1 frame sidehop left": goron_1_frame_sidehop_left,
    "goron 1 frame sidehop right": goron_1_frame_sidehop_right,
    "human tap sidehop left": human_tap_sidehop_left,
    "human tap sidehop right": human_tap_sidehop_right,
    "deku tap sidehop left": deku_tap_sidehop_left,
    "deku tap sidehop right": deku_tap_sidehop_right,
    "goron tap sidehop left": goron_tap_sidehop_left,
    "goron tap sidehop right": goron_tap_sidehop_right,
}
