/*
 * Middle-button undecided resolver.
 *
 * Press middle → undecided (emit nothing yet).
 *   Ball moves  → hold middle-click (MMB drag).
 *   Left encoder → one Alt+Tab chord per detent (see `&mea`), marks session
 *                  so middle-release does not tap MCLK.
 *   Release undecided → tap middle-click.
 *
 * Each encoder detent is a full Alt↓ … Tab … Alt↑ chord (25ms after Alt so
 * Windows sees Alt held first). Keeping Alt down across detents looked right
 * in HID logs but the switcher still died after tick 1 (bare Tab afterward);
 * per-tick chords make every detent switch reliably.
 */

#define DT_DRV_COMPAT zmk_input_processor_mclk_alt

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/input/input.h>
#include <zephyr/dt-bindings/input/input-event-codes.h>
#include <drivers/input_processor.h>
#include <zephyr/logging/log.h>

#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zmk/event_manager.h>
#include <zmk/events/keycode_state_changed.h>
#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk/pointing.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#ifndef CONFIG_ZMK_MCLK_ALT_TAB_DELAY_MS
#define CONFIG_ZMK_MCLK_ALT_TAB_DELAY_MS 25
#endif

enum mclk_alt_mode {
    MCLK_ALT_IDLE = 0,
    MCLK_ALT_UNDECIDED,
    MCLK_ALT_MCLK,
    MCLK_ALT_ALT,
};

static enum mclk_alt_mode mclk_alt_mode;
static int mclk_alt_motion_threshold = 2;
static bool mclk_alt_alt_down;

static const struct device *mclk_alt_mkp_dev(void) {
    return DEVICE_DT_GET(DT_NODELABEL(mkp));
}

static void mclk_alt_set_mclk(bool pressed) {
    const struct device *mkp = mclk_alt_mkp_dev();
    if (!device_is_ready(mkp)) {
        return;
    }
    /* MB3 / MCLK → INPUT_BTN_2 */
    input_report_key(mkp, INPUT_BTN_0 + 2, pressed ? 1 : 0, true, K_FOREVER);
}

static void mclk_alt_set_alt(bool pressed, int64_t timestamp) {
    if (pressed == mclk_alt_alt_down) {
        return;
    }
    mclk_alt_alt_down = pressed;
    raise_zmk_keycode_state_changed_from_encoded(LEFT_ALT, pressed, timestamp);
}

static void mclk_alt_resolve_mclk(void) {
    if (mclk_alt_mode != MCLK_ALT_UNDECIDED) {
        return;
    }
    mclk_alt_mode = MCLK_ALT_MCLK;
    mclk_alt_set_mclk(true);
    LOG_DBG("middle undecided -> MCLK hold");
}

/* Arm Alt-Tab session (middle was held); do not press Alt yet. */
static bool mclk_alt_arm_encoder(void) {
    if (mclk_alt_mode == MCLK_ALT_ALT) {
        return true;
    }
    if (mclk_alt_mode != MCLK_ALT_UNDECIDED) {
        return false;
    }
    mclk_alt_mode = MCLK_ALT_ALT;
    LOG_DBG("middle undecided -> Alt-Tab armed");
    return true;
}

static int mclk_alt_handle_event(const struct device *dev, struct input_event *event,
                                 uint32_t param1, uint32_t param2,
                                 struct zmk_input_processor_state *state) {
    ARG_UNUSED(dev);
    ARG_UNUSED(param1);
    ARG_UNUSED(param2);
    ARG_UNUSED(state);

    if (mclk_alt_mode != MCLK_ALT_UNDECIDED) {
        return 0;
    }
    if (event->type != INPUT_EV_REL) {
        return 0;
    }
    if (event->code != INPUT_REL_X && event->code != INPUT_REL_Y) {
        return 0;
    }
    if (event->value >= mclk_alt_motion_threshold ||
        event->value <= -mclk_alt_motion_threshold) {
        mclk_alt_resolve_mclk();
    }
    return 0;
}

static struct zmk_input_processor_driver_api mclk_alt_ip_api = {
    .handle_event = mclk_alt_handle_event,
};

static int mclk_alt_ip_init(const struct device *dev) {
    ARG_UNUSED(dev);
    mclk_alt_mode = MCLK_ALT_IDLE;
    mclk_alt_alt_down = false;
    return 0;
}

DEVICE_DT_INST_DEFINE(0, mclk_alt_ip_init, NULL, NULL, NULL, POST_KERNEL,
                      CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &mclk_alt_ip_api);

/* --- middle button behavior --- */

#undef DT_DRV_COMPAT
#define DT_DRV_COMPAT zmk_behavior_mclk_alt

struct behavior_mclk_alt_config {
    int motion_threshold;
};

static int on_mca_pressed(struct zmk_behavior_binding *binding,
                          struct zmk_behavior_binding_event event) {
    ARG_UNUSED(binding);
    ARG_UNUSED(event);
    mclk_alt_mode = MCLK_ALT_UNDECIDED;
    LOG_DBG("middle pressed (undecided)");
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_mca_released(struct zmk_behavior_binding *binding,
                           struct zmk_behavior_binding_event event) {
    ARG_UNUSED(binding);
    enum mclk_alt_mode mode = mclk_alt_mode;
    mclk_alt_mode = MCLK_ALT_IDLE;

    switch (mode) {
    case MCLK_ALT_UNDECIDED:
        /* Quick tap → middle click */
        mclk_alt_set_mclk(true);
        mclk_alt_set_mclk(false);
        LOG_DBG("middle release undecided -> MCLK tap");
        break;
    case MCLK_ALT_MCLK:
        mclk_alt_set_mclk(false);
        LOG_DBG("middle release -> MCLK up");
        break;
    case MCLK_ALT_ALT:
        /* Encoder chords already release Alt each detent; clear any leftover. */
        mclk_alt_set_alt(false, event.timestamp);
        LOG_DBG("middle release -> Alt-Tab session end");
        break;
    default:
        break;
    }
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api mca_driver_api = {
    .binding_pressed = on_mca_pressed,
    .binding_released = on_mca_released,
};

static int mca_init(const struct device *dev) {
    const struct behavior_mclk_alt_config *cfg = dev->config;
    mclk_alt_motion_threshold = cfg->motion_threshold;
    return 0;
}

#define MCA_INST(n)                                                                                \
    static const struct behavior_mclk_alt_config behavior_mclk_alt_config_##n = {                 \
        .motion_threshold = DT_INST_PROP_OR(n, motion_threshold, 2),                               \
    };                                                                                             \
    BEHAVIOR_DT_INST_DEFINE(n, mca_init, NULL, NULL, &behavior_mclk_alt_config_##n, POST_KERNEL,  \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &mca_driver_api);

DT_INST_FOREACH_STATUS_OKAY(MCA_INST)

/* --- left-encoder: one Alt+Tab chord per detent while middle is held --- */

#undef DT_DRV_COMPAT
#define DT_DRV_COMPAT zmk_behavior_middle_encoder_alt

static uint32_t mea_held_keycode;
static bool mea_key_down;

static int on_mea_pressed(struct zmk_behavior_binding *binding,
                          struct zmk_behavior_binding_event event) {
    if (!mclk_alt_arm_encoder()) {
        /* Middle not held — ignore (no bare Tab / no unsolicited Alt-Tab). */
        mea_key_down = false;
        return ZMK_BEHAVIOR_OPAQUE;
    }

    /* Full chord per detent: Alt must be down before Tab for the OS switcher. */
    mclk_alt_set_alt(true, event.timestamp);
    k_msleep(CONFIG_ZMK_MCLK_ALT_TAB_DELAY_MS);

    mea_held_keycode = binding->param1;
    mea_key_down = true;
    raise_zmk_keycode_state_changed_from_encoded(binding->param1, true, k_uptime_get());
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_mea_released(struct zmk_behavior_binding *binding,
                           struct zmk_behavior_binding_event event) {
    ARG_UNUSED(binding);
    if (mea_key_down) {
        mea_key_down = false;
        raise_zmk_keycode_state_changed_from_encoded(mea_held_keycode, false, event.timestamp);
    }
    /* Finish the chord so this detent commits even if Alt was dropped mid-hold. */
    mclk_alt_set_alt(false, event.timestamp);
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api mea_driver_api = {
    .binding_pressed = on_mea_pressed,
    .binding_released = on_mea_released,
};

#define MEA_INST(n)                                                                                \
    BEHAVIOR_DT_INST_DEFINE(n, NULL, NULL, NULL, NULL, POST_KERNEL,                                \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &mea_driver_api);

DT_INST_FOREACH_STATUS_OKAY(MEA_INST)
