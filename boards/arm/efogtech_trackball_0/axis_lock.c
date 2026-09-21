/*
 * Scroll-axis lock: hard-lock ball motion to one axis on the scroll layer.
 *
 * Default: Y only (vertical scroll). Toggle with &axlk to allow X only
 * (horizontal scroll). The other axis is zeroed before xy→scroll mapping.
 */

#define DT_DRV_COMPAT zmk_input_processor_axis_lock

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <drivers/input_processor.h>
#include <zephyr/dt-bindings/input/input-event-codes.h>
#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

/* 0 = Y-only (default), 1 = X-only */
static bool axis_lock_horizontal;

bool zmk_axis_lock_is_horizontal(void) { return axis_lock_horizontal; }

void zmk_axis_lock_toggle(void) {
    axis_lock_horizontal = !axis_lock_horizontal;
    LOG_DBG("scroll axis lock: %s only", axis_lock_horizontal ? "X" : "Y");
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

    if (axis_lock_horizontal) {
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

static int axis_lock_init(const struct device *dev) {
    ARG_UNUSED(dev);
    axis_lock_horizontal = false;
    return 0;
}

DEVICE_DT_INST_DEFINE(0, axis_lock_init, NULL, NULL, NULL, POST_KERNEL,
                      CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &axis_lock_driver_api);

/* --- toggle behavior --- */

#undef DT_DRV_COMPAT
#define DT_DRV_COMPAT zmk_behavior_axis_lock_toggle

#include <drivers/behavior.h>
#include <zmk/behavior.h>

static int on_axlk_pressed(struct zmk_behavior_binding *binding,
                           struct zmk_behavior_binding_event event) {
    ARG_UNUSED(binding);
    ARG_UNUSED(event);
    zmk_axis_lock_toggle();
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_axlk_released(struct zmk_behavior_binding *binding,
                            struct zmk_behavior_binding_event event) {
    ARG_UNUSED(binding);
    ARG_UNUSED(event);
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api axlk_driver_api = {
    .binding_pressed = on_axlk_pressed,
    .binding_released = on_axlk_released,
};

static int axlk_init(const struct device *dev) {
    ARG_UNUSED(dev);
    return 0;
}

#define AXLK_INST(n)                                                                               \
    BEHAVIOR_DT_INST_DEFINE(n, axlk_init, NULL, NULL, NULL, POST_KERNEL,                          \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &axlk_driver_api);

DT_INST_FOREACH_STATUS_OKAY(AXLK_INST)
