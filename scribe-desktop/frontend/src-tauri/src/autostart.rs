use tauri::{AppHandle, Runtime};
use tauri_plugin_autostart::ManagerExt;

/// Passed to the login item so the app can tell a login launch from a normal one.
pub const LOGIN_LAUNCH_ARG: &str = "--hidden";

#[cfg(not(debug_assertions))]
const STORE_FILE: &str = "preferences.json";
// Recorded once so a later opt-out is never undone by the default-on logic.
#[cfg(not(debug_assertions))]
const DEFAULT_APPLIED_KEY: &str = "open_at_login_default_applied";

// A restart reuses the original args, so this env var (inherited by the child) marks it as not a login launch.
const SHOW_WINDOW_ENV: &str = "WUSOOLSCRIBE_SHOW_WINDOW";

pub fn launched_at_login() -> bool {
    std::env::var_os(SHOW_WINDOW_ENV).is_none() && std::env::args().any(|arg| arg == LOGIN_LAUNCH_ARG)
}

/// Called before an update restart so the relaunched app shows its window.
#[tauri::command]
pub fn prepare_relaunch() {
    std::env::set_var(SHOW_WINDOW_ENV, "1");
}

/// Turns open-at-login on the first time this runs, for new and existing users alike.
// Skipped in debug builds: it would register the dev binary as a login item.
#[cfg(not(debug_assertions))]
pub fn apply_default<R: Runtime>(app: &AppHandle<R>) {
    use tauri_plugin_store::StoreExt;

    let store = match app.store(STORE_FILE) {
        Ok(store) => store,
        Err(e) => {
            log::warn!("Open at login: could not open preferences store: {}", e);
            return;
        }
    };
    if store.get(DEFAULT_APPLIED_KEY).is_some() {
        return;
    }
    if let Err(e) = app.autolaunch().enable() {
        // Not marked applied, so the next launch retries.
        log::warn!("Open at login: could not enable by default: {}", e);
        return;
    }
    store.set(DEFAULT_APPLIED_KEY, true);
    if let Err(e) = store.save() {
        log::warn!("Open at login: could not save default marker: {}", e);
    }
}

#[cfg(debug_assertions)]
pub fn apply_default<R: Runtime>(_app: &AppHandle<R>) {}

#[tauri::command]
pub fn get_open_at_login<R: Runtime>(app: AppHandle<R>) -> Result<bool, String> {
    app.autolaunch().is_enabled().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn set_open_at_login<R: Runtime>(app: AppHandle<R>, enabled: bool) -> Result<(), String> {
    let manager = app.autolaunch();
    let result = if enabled { manager.enable() } else { manager.disable() };
    result.map_err(|e| e.to_string())
}
