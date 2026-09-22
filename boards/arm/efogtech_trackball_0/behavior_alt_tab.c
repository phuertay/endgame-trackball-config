/*
 * Encoder Alt-Tab.
 *
 * The tri-state swapper presses Alt only on its first activation, then emits
 * Tab alone. The other encoder direction was a raw Shift+Tab. The follower
 * invokes those bindings directly and does not raise position events, so the
 * swapper's ignored-key-positions never see the reverse tick. Rolling the
 * encoder therefore produced one Alt and then bare Tab / Shift+Tab.
 *
 * Each detent here makes sure the hold-key (Left Alt) is down, then taps
 * param1. Alt is not pressed again while it is already down — a second press
 * would bump ZMK's explicit-modifier count and a single release would leave
 * it stuck. Alt releases after the encoder goes idle, or when any other key
 * is pressed.
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
#include <zmk/hid.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

struct behavior_alt_tab_config {
    uint32_t hold_key;
    int release_after_ms;
};

struct behavior_alt_tab_data {
    const struct device *dev;
    bool active;
    bool tap_down;
    int64_t hold_until;
    struct k_work_delayable release_work;
};

static const struct device *alt_tab_dev;

static void alt_tab_release_hold(struct behavior_alt_tab_data *data, int64_t timestamp) {
    const struct behavior_alt_tab_config *cfg = data->dev->config;

    data->hold_until = 0;
    if (!data->active) {
        return;
    }
    data->active = false;
    if (zmk_hid_is_pressed(cfg->hold_key)) {
        raise_zmk_keycode_state_changed_from_encoded(cfg->hold_key, false, timestamp);
    }
    LOG_DBG("alt-tab session ended");
}

static void alt_tab_end(struct behavior_alt_tab_data *data, int64_t timestamp) {
    k_work_cancel_delayable(&data->release_work);
    alt_tab_release_hold(data, timestamp);
}

static void alt_tab_release_work(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct behavior_alt_tab_data *data =
        CONTAINER_OF(dwork, struct behavior_alt_tab_data, release_work);
    int64_t now = k_uptime_get();

    /* A newer detent already pushed the deadline out from another thread. */
    if (data->active && now < data->hold_until) {
        k_work_schedule(&data->release_work, K_MSEC(data->hold_until - now));
        return;
    }
    alt_tab_release_hold(data, now);
}

static void alt_tab_ensure_held(const struct behavior_alt_tab_config *cfg, int64_t timestamp) {
    if (zmk_hid_is_pressed(cfg->hold_key)) {
        return;
    }
    raise_zmk_keycode_state_changed_from_encoded(cfg->hold_key, true, timestamp);
}

static int on_alt_tab_pressed(struct zmk_behavior_binding *binding,
                              struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    struct behavior_alt_tab_data *data = dev->data;
    const struct behavior_alt_tab_config *cfg = dev->config;

    /* Refresh before the tap so an in-flight release cannot drop Alt first. */
    data->active = true;
    data->hold_until = k_uptime_get() + cfg->release_after_ms;
    k_work_reschedule(&data->release_work, K_MSEC(cfg->release_after_ms));

    alt_tab_ensure_held(cfg, event.timestamp);

    data->tap_down = true;
    raise_zmk_keycode_state_changed_from_encoded(binding->param1, true, k_uptime_get());
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_alt_tab_released(struct zmk_behavior_binding *binding,
                               struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    struct behavior_alt_tab_data *data = dev->data;

    if (data->tap_down) {
        data->tap_down = false;
        raise_zmk_keycode_state_changed_from_encoded(binding->param1, false, event.timestamp);
    }
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
    data->tap_down = false;
    data->hold_until = 0;
    k_work_init_delayable(&data->release_work, alt_tab_release_work);
    alt_tab_dev = dev;
    return 0;
}

static int alt_tab_position_listener(const zmk_event_t *eh) {
    const struct zmk_position_state_changed *ev = as_zmk_position_state_changed(eh);

    if (ev == NULL || !ev->state || alt_tab_dev == NULL) {
        return ZMK_EV_EVENT_BUBBLE;
    }

    struct behavior_alt_tab_data *data = alt_tab_dev->data;
    if (!data->active) {
        return ZMK_EV_EVENT_BUBBLE;
    }

    /* Any real key commits the switcher. Encoder slots are not position events. */
    alt_tab_end(data, ev->timestamp);
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(behavior_alt_tab, alt_tab_position_listener);
ZMK_SUBSCRIPTION(behavior_alt_tab, zmk_position_state_changed);

#define AT_INST(n)                                                                                 \
    static struct behavior_alt_tab_data behavior_alt_tab_data_##n = {};                            \
    static const struct behavior_alt_tab_config behavior_alt_tab_config_##n = {                    \
        .hold_key = DT_INST_PROP(n, hold_key),                                                     \
        .release_after_ms = DT_INST_PROP_OR(n, release_after_ms, 500),                             \
    };                                                                                             \
    BEHAVIOR_DT_INST_DEFINE(n, behavior_alt_tab_init, NULL, &behavior_alt_tab_data_##n,            \
                            &behavior_alt_tab_config_##n, POST_KERNEL,                             \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &behavior_alt_tab_driver_api);

DT_INST_FOREACH_STATUS_OKAY(AT_INST)
