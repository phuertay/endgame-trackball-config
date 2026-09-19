/*
 * Alt-tab "swapper" behavior.
 *
 * Holds a modifier (hold-key, e.g. LEFT_ALT) across repeated activations and
 * taps param1 (e.g. TAB, or LS(TAB) for reverse) each time. The modifier is
 * released after `release-after-ms` of inactivity, which commits the OS app
 * switcher. Meant to be triggered repeatedly by an encoder tick.
 */

#define DT_DRV_COMPAT zmk_behavior_alt_tab

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <drivers/behavior.h>
#include <zephyr/logging/log.h>

#include <zmk/behavior.h>
#include <zmk/event_manager.h>
#include <zmk/events/keycode_state_changed.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

struct behavior_alt_tab_config {
    uint32_t hold_key;
    int release_after_ms;
};

struct behavior_alt_tab_data {
    const struct device *dev;
    bool active;
    struct k_work_delayable release_work;
};

static void behavior_alt_tab_release(struct k_work *work) {
    struct k_work_delayable *dwork = k_work_delayable_from_work(work);
    struct behavior_alt_tab_data *data = CONTAINER_OF(dwork, struct behavior_alt_tab_data, release_work);
    const struct behavior_alt_tab_config *cfg = data->dev->config;

    if (data->active) {
        data->active = false;
        raise_zmk_keycode_state_changed_from_encoded(cfg->hold_key, false, k_uptime_get());
        LOG_DBG("alt-tab session ended, released hold-key 0x%08X", cfg->hold_key);
    }
}

static int on_alt_tab_pressed(struct zmk_behavior_binding *binding,
                              struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    struct behavior_alt_tab_data *data = dev->data;
    const struct behavior_alt_tab_config *cfg = dev->config;

    if (!data->active) {
        data->active = true;
        raise_zmk_keycode_state_changed_from_encoded(cfg->hold_key, true, event.timestamp);
        LOG_DBG("alt-tab session started, holding key 0x%08X", cfg->hold_key);
    }

    raise_zmk_keycode_state_changed_from_encoded(binding->param1, true, event.timestamp);
    k_work_reschedule(&data->release_work, K_MSEC(cfg->release_after_ms));
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_alt_tab_released(struct zmk_behavior_binding *binding,
                               struct zmk_behavior_binding_event event) {
    raise_zmk_keycode_state_changed_from_encoded(binding->param1, false, event.timestamp);
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
    k_work_init_delayable(&data->release_work, behavior_alt_tab_release);
    return 0;
}

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
