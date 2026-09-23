/*
 * Encoder Alt-Tab.
 *
 * Each detent taps param1 (Tab or Shift+Tab) while Left Alt stays down.
 * Alt is released only after the encoder has been idle, or when another key
 * is pressed, which commits the OS switcher.
 *
 * zmk_hid_is_pressed() is not a usable "is Alt down?" check here. On the ESB
 * dongle the relay listener handles key events before hid_listener and returns
 * HANDLED, so the global HID modifier counts never move. Trusting them pressed
 * Alt on every detent (the relay's refcount climbed and one release could not
 * clear it) or skipped the release entirely, and the host then saw bare Tab.
 */

#define DT_DRV_COMPAT zmk_behavior_alt_tab

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <drivers/behavior.h>
#include <zephyr/logging/log.h>

#include <zmk/behavior.h>
#include <zmk/event_manager.h>
#include <zmk/events/keycode_state_changed.h>
#include <zmk/events/position_state_changed.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

/* Let the host observe Alt alone before the first Tab of a session. A Tab in
 * the same instant Alt goes down is delivered to the focused app once the
 * previous session has committed. */
#define ALT_TAB_ARM_MS 15
#define ALT_TAB_TAP_MS 25

struct behavior_alt_tab_config {
    uint32_t hold_key;
    int release_after_ms;
};

struct behavior_alt_tab_data {
    const struct device *dev;
    bool active;
    bool hold_down;
    bool tap_down;
    bool defer_tap;
    bool tap_owned;
    bool end_after_tap;
    uint32_t tap_keycode;
    int64_t hold_until;
    struct k_work_delayable release_work;
    struct k_work_delayable defer_work;
    struct k_work_delayable tap_release_work;
};

static const struct device *alt_tab_dev;

static void alt_tab_release_tap(struct behavior_alt_tab_data *data, int64_t timestamp) {
    if (!data->tap_down) {
        return;
    }
    data->tap_down = false;
    data->tap_owned = false;
    raise_zmk_keycode_state_changed_from_encoded(data->tap_keycode, false, timestamp);
}

static void alt_tab_release_alt(struct behavior_alt_tab_data *data, int64_t timestamp) {
    const struct behavior_alt_tab_config *cfg = data->dev->config;

    data->active = false;
    data->end_after_tap = false;
    data->defer_tap = false;
    k_work_cancel_delayable(&data->defer_work);
    if (!data->hold_down) {
        return;
    }
    data->hold_down = false;
    raise_zmk_keycode_state_changed_from_encoded(cfg->hold_key, false, timestamp);
    LOG_DBG("alt-tab session ended");
}

static void alt_tab_after_tap(struct behavior_alt_tab_data *data, int64_t timestamp) {
    if (data->end_after_tap && !data->tap_down && !data->defer_tap) {
        alt_tab_release_alt(data, timestamp);
    }
}

static void alt_tab_end(struct behavior_alt_tab_data *data, int64_t timestamp) {
    k_work_cancel_delayable(&data->release_work);
    if (!data->active && !data->hold_down && !data->defer_tap) {
        return;
    }
    /* Drop a not-yet-sent Tab. Releasing Alt while Tab is still down makes the
     * focused app repeat Tab, so a tap that is already down finishes first. */
    if (data->defer_tap && !data->tap_down) {
        alt_tab_release_alt(data, timestamp);
        return;
    }
    if (data->tap_down) {
        data->end_after_tap = true;
        data->active = false;
        return;
    }
    alt_tab_release_alt(data, timestamp);
}

static void alt_tab_release_work(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct behavior_alt_tab_data *data =
        CONTAINER_OF(dwork, struct behavior_alt_tab_data, release_work);
    int64_t now = k_uptime_get();

    if (data->active && now < data->hold_until) {
        k_work_schedule(&data->release_work, K_MSEC(data->hold_until - now));
        return;
    }
    alt_tab_end(data, now);
}

static void alt_tab_press_tap(struct behavior_alt_tab_data *data, uint32_t keycode,
                              int64_t timestamp) {
    /* ESB treats a second press of a key that is already down as a no-op, so
     * the host never sees the new edge. Release first when a detent overlaps. */
    if (data->tap_down) {
        alt_tab_release_tap(data, timestamp);
    }
    data->tap_keycode = keycode;
    data->tap_down = true;
    raise_zmk_keycode_state_changed_from_encoded(keycode, true, timestamp);
}

static void alt_tab_tap_release_work(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct behavior_alt_tab_data *data =
        CONTAINER_OF(dwork, struct behavior_alt_tab_data, tap_release_work);

    if (!data->tap_owned) {
        return;
    }
    alt_tab_release_tap(data, k_uptime_get());
    alt_tab_after_tap(data, k_uptime_get());
}

static void alt_tab_defer_work(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct behavior_alt_tab_data *data =
        CONTAINER_OF(dwork, struct behavior_alt_tab_data, defer_work);

    if (!data->defer_tap || !data->hold_down || !data->active) {
        data->defer_tap = false;
        return;
    }
    data->defer_tap = false;
    alt_tab_press_tap(data, data->tap_keycode, k_uptime_get());
    if (!data->hold_down) {
        alt_tab_release_tap(data, k_uptime_get());
        return;
    }
    /* press_tap clears tap_owned when it replaces an overlapping detent. */
    data->tap_owned = true;
    k_work_reschedule(&data->tap_release_work, K_MSEC(ALT_TAB_TAP_MS));
}

static void alt_tab_sync_tap(struct behavior_alt_tab_data *data, uint32_t keycode,
                             int64_t timestamp) {
    if (data->defer_tap) {
        data->defer_tap = false;
        k_work_cancel_delayable(&data->defer_work);
    }
    /* A self-timed tap from session start must not release this newer detent. */
    data->tap_owned = false;
    k_work_cancel_delayable(&data->tap_release_work);
    alt_tab_press_tap(data, keycode, timestamp);
}

static int on_alt_tab_pressed(struct zmk_behavior_binding *binding,
                              struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    struct behavior_alt_tab_data *data = dev->data;
    const struct behavior_alt_tab_config *cfg = dev->config;
    const bool fresh = !data->hold_down;

    data->active = true;
    data->end_after_tap = false;
    data->hold_until = k_uptime_get() + cfg->release_after_ms;
    k_work_reschedule(&data->release_work, K_MSEC(cfg->release_after_ms));

    if (fresh) {
        data->hold_down = true;
        raise_zmk_keycode_state_changed_from_encoded(cfg->hold_key, true, event.timestamp);
        data->defer_tap = true;
        data->tap_keycode = binding->param1;
        k_work_reschedule(&data->defer_work, K_MSEC(ALT_TAB_ARM_MS));
        return ZMK_BEHAVIOR_OPAQUE;
    }

    alt_tab_sync_tap(data, binding->param1, k_uptime_get());
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_alt_tab_released(struct zmk_behavior_binding *binding,
                               struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    struct behavior_alt_tab_data *data = dev->data;

    /* Session-start tap is armed on a delay; the follower's 5ms release
     * arrives before that tap exists. A self-timed tap releases itself. */
    if (data->defer_tap || data->tap_owned) {
        return ZMK_BEHAVIOR_OPAQUE;
    }
    alt_tab_release_tap(data, event.timestamp);
    alt_tab_after_tap(data, event.timestamp);
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api behavior_alt_tab_driver_api = {
    .binding_pressed = on_alt_tab_pressed,
    .binding_released = on_alt_tab_released,
};

static int behavior_alt_tab_init(const struct device *dev) {
    struct behavior_alt_tab_data *data = dev->data;

    data->dev = dev;
    data->active = false;
    data->hold_down = false;
    data->tap_down = false;
    data->defer_tap = false;
    data->tap_owned = false;
    data->end_after_tap = false;
    data->hold_until = 0;
    k_work_init_delayable(&data->release_work, alt_tab_release_work);
    k_work_init_delayable(&data->defer_work, alt_tab_defer_work);
    k_work_init_delayable(&data->tap_release_work, alt_tab_tap_release_work);
    alt_tab_dev = dev;
    return 0;
}

static int alt_tab_position_listener(const zmk_event_t *eh) {
    const struct zmk_position_state_changed *ev = as_zmk_position_state_changed(eh);

    if (ev == NULL || !ev->state || alt_tab_dev == NULL) {
        return ZMK_EV_EVENT_BUBBLE;
    }

    struct behavior_alt_tab_data *data = alt_tab_dev->data;
    if (!data->active && !data->hold_down) {
        return ZMK_EV_EVENT_BUBBLE;
    }

    alt_tab_end(data, ev->timestamp);
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(behavior_alt_tab, alt_tab_position_listener);
ZMK_SUBSCRIPTION(behavior_alt_tab, zmk_position_state_changed);

#define AT_INST(n)                                                                                 \
    static struct behavior_alt_tab_data behavior_alt_tab_data_##n = {};                            \
    static const struct behavior_alt_tab_config behavior_alt_tab_config_##n = {                    \
        .hold_key = DT_INST_PROP(n, hold_key),                                                     \
        .release_after_ms = DT_INST_PROP_OR(n, release_after_ms, 750),                             \
    };                                                                                             \
    BEHAVIOR_DT_INST_DEFINE(n, behavior_alt_tab_init, NULL, &behavior_alt_tab_data_##n,            \
                            &behavior_alt_tab_config_##n, POST_KERNEL,                             \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &behavior_alt_tab_driver_api);

DT_INST_FOREACH_STATUS_OKAY(AT_INST)
