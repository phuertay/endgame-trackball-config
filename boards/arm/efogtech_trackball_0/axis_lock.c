/*
 * Scroll-axis lock: hard-lock ball motion to one axis on the scroll layer.
 *
 * Default: Y only (vertical scroll).
 * `&axlk` tap         → permanently toggle Y ↔ X (re-locks if unlocked)
 * `&axlk` hold        → temporarily use the other axis until release
 * `&axlk` double-tap  → release both axes (free X+Y scroll)
 */

#define DT_DRV_COMPAT zmk_input_processor_axis_lock

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <drivers/input_processor.h>
#include <zephyr/dt-bindings/input/input-event-codes.h>
#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

static bool axis_lock_horizontal;
static bool axis_lock_momentary;
static bool axis_lock_unlocked;

static bool axis_lock_effective_horizontal(void) {
    return axis_lock_momentary ? !axis_lock_horizontal : axis_lock_horizontal;
}

static void axis_lock_toggle(void) {
    if (axis_lock_unlocked) {
        axis_lock_unlocked = false;
        LOG_DBG("scroll axis lock: re-locked %s only", axis_lock_horizontal ? "X" : "Y");
        return;
    }
    axis_lock_horizontal = !axis_lock_horizontal;
    LOG_DBG("scroll axis lock: %s only (persistent)", axis_lock_horizontal ? "X" : "Y");
}

static void axis_lock_release_both(void) {
    axis_lock_unlocked = true;
    axis_lock_momentary = false;
    LOG_DBG("scroll axis lock: both axes released");
}

static void axis_lock_momentary_set(bool pressed) {
    axis_lock_momentary = pressed;
    LOG_DBG("scroll axis lock momentary %s -> effective %s only", pressed ? "on" : "off",
            axis_lock_effective_horizontal() ? "X" : "Y");
}

static int axis_lock_handle_event(const struct device *dev, struct input_event *event,
                                  uint32_t param1, uint32_t param2,
                                  struct zmk_input_processor_state *state) {
    ARG_UNUSED(dev);
    ARG_UNUSED(param1);
    ARG_UNUSED(param2);
    ARG_UNUSED(state);

    if (event->type != INPUT_EV_REL) {
        return 0;
    }

    /* Unlocked + not momentarily constrained: pass X and Y through. */
    if (axis_lock_unlocked && !axis_lock_momentary) {
        return 0;
    }

    if (axis_lock_effective_horizontal()) {
        if (event->code == INPUT_REL_Y) {
            event->value = 0;
            event->sync = false;
        }
    } else if (event->code == INPUT_REL_X) {
        event->value = 0;
        event->sync = false;
    }

    return 0;
}

static struct zmk_input_processor_driver_api axis_lock_driver_api = {
    .handle_event = axis_lock_handle_event,
};

static int axis_lock_ip_init(const struct device *dev) {
    ARG_UNUSED(dev);
    axis_lock_horizontal = false;
    axis_lock_momentary = false;
    axis_lock_unlocked = false;
    return 0;
}

DEVICE_DT_INST_DEFINE(0, axis_lock_ip_init, NULL, NULL, NULL, POST_KERNEL,
                      CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &axis_lock_driver_api);

/* --- tap=toggle / hold=momentary / double-tap=release both --- */

#undef DT_DRV_COMPAT
#define DT_DRV_COMPAT zmk_behavior_axis_lock

#include <drivers/behavior.h>
#include <zmk/behavior.h>

#ifndef CONFIG_ZMK_AXIS_LOCK_TAPPING_TERM_MS
#define CONFIG_ZMK_AXIS_LOCK_TAPPING_TERM_MS 200
#endif

struct behavior_axis_lock_config {
    int tapping_term_ms;
};

struct behavior_axis_lock_data {
    const struct device *dev;
    bool held;
    bool decided_hold;
    bool pending_tap;
    bool second_press;
    int64_t press_time;
    struct k_work_delayable decide_work;
    struct k_work_delayable tap_work;
};

static void axis_lock_decide(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct behavior_axis_lock_data *data =
        CONTAINER_OF(dwork, struct behavior_axis_lock_data, decide_work);

    if (data->held && !data->decided_hold && !data->second_press) {
        data->decided_hold = true;
        data->pending_tap = false;
        axis_lock_momentary_set(true);
    }
}

static void axis_lock_commit_tap(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct behavior_axis_lock_data *data =
        CONTAINER_OF(dwork, struct behavior_axis_lock_data, tap_work);

    if (data->pending_tap) {
        data->pending_tap = false;
        axis_lock_toggle();
    }
}

static int on_axlk_pressed(struct zmk_behavior_binding *binding,
                           struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    struct behavior_axis_lock_data *data = dev->data;
    const struct behavior_axis_lock_config *cfg = dev->config;

    data->held = true;
    data->decided_hold = false;
    data->press_time = event.timestamp;

    if (data->pending_tap) {
        /* Second press within the quick-tap window → double-tap. */
        k_work_cancel_delayable(&data->tap_work);
        data->pending_tap = false;
        data->second_press = true;
        return ZMK_BEHAVIOR_OPAQUE;
    }

    data->second_press = false;
    k_work_reschedule(&data->decide_work, K_MSEC(cfg->tapping_term_ms));
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_axlk_released(struct zmk_behavior_binding *binding,
                            struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    struct behavior_axis_lock_data *data = dev->data;
    const struct behavior_axis_lock_config *cfg = dev->config;

    k_work_cancel_delayable(&data->decide_work);
    data->held = false;

    if (data->second_press) {
        data->second_press = false;
        data->decided_hold = false;
        axis_lock_release_both();
        ARG_UNUSED(event);
        return ZMK_BEHAVIOR_OPAQUE;
    }

    if (data->decided_hold) {
        axis_lock_momentary_set(false);
        data->decided_hold = false;
    } else {
        /* Defer toggle until quick-tap window expires (or second press arrives). */
        data->pending_tap = true;
        k_work_reschedule(&data->tap_work, K_MSEC(cfg->tapping_term_ms));
    }

    ARG_UNUSED(event);
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api axlk_driver_api = {
    .binding_pressed = on_axlk_pressed,
    .binding_released = on_axlk_released,
};

static int axlk_init(const struct device *dev) {
    struct behavior_axis_lock_data *data = dev->data;
    data->dev = dev;
    data->held = false;
    data->decided_hold = false;
    data->pending_tap = false;
    data->second_press = false;
    k_work_init_delayable(&data->decide_work, axis_lock_decide);
    k_work_init_delayable(&data->tap_work, axis_lock_commit_tap);
    return 0;
}

#define AXLK_INST(n)                                                                               \
    static struct behavior_axis_lock_data behavior_axis_lock_data_##n = {};                        \
    static const struct behavior_axis_lock_config behavior_axis_lock_config_##n = {               \
        .tapping_term_ms = DT_INST_PROP_OR(n, tapping_term_ms, 200),                               \
    };                                                                                             \
    BEHAVIOR_DT_INST_DEFINE(n, axlk_init, NULL, &behavior_axis_lock_data_##n,                      \
                            &behavior_axis_lock_config_##n, POST_KERNEL,                           \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &axlk_driver_api);

DT_INST_FOREACH_STATUS_OKAY(AXLK_INST)
