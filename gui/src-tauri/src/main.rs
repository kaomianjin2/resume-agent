use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    env,
    ffi::{OsStr, OsString},
    path::PathBuf,
    process::{Child, Command, ExitStatus, Stdio},
    sync::Mutex,
    thread,
    time::Duration,
};
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use tauri::Manager;

const CONFIG_PATH: &str = "config/interview-agent.toml";
const PYTHON_STATUS_SCRIPT: &str = r#"
from pathlib import Path
import json
from interview_agent.config import load_config
from interview_agent.storage import get_knowledge_base_status

config_path = Path("config/interview-agent.toml")
config = load_config(config_path)
print(json.dumps({
    "config_path": str(config_path),
    "knowledge_base_status": get_knowledge_base_status(config.storage.database_path),
}))
"#;

#[derive(Default)]
struct DesktopState {
    runtime: Mutex<RuntimeState>,
}

#[derive(Default)]
struct RuntimeState {
    python_process: Option<Child>,
    resume_path: Option<String>,
    jd_path: Option<String>,
    last_error: Option<String>,
    current_user: Option<String>,
    current_user_role: Option<String>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeSnapshot {
    is_desktop_shell: bool,
    python_runtime_running: bool,
    knowledge_base_status: String,
    config_path: String,
    resume_path: Option<String>,
    jd_path: Option<String>,
    last_error: Option<String>,
    current_user: Option<String>,
    current_user_role: Option<String>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct UserRecord {
    user_id: String,
    username: String,
    role: String,
    status: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct AddUserPayload {
    username: String,
    password: String,
    role: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateUserStatusPayload {
    username: String,
    status: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LoginPayload {
    username: String,
    password: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct StartMockInterviewPayload {
    session_id: String,
    target_role: String,
    question_count: Option<i32>,
    question_type: Option<String>,
    followup_rounds: Option<i32>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct StartAlgorithmPracticePayload {
    session_id: String,
    practice_topic: String,
    difficulty: Option<String>,
    question_count: Option<i32>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SubmitMockAnswerPayload {
    session_id: String,
    answer: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "lowercase")]
enum MaterialKind {
    Resume,
    Jd,
}

#[derive(Deserialize)]
struct PythonStatus {
    knowledge_base_status: String,
}

impl Drop for DesktopState {
    fn drop(&mut self) {
        if let Ok(mut runtime_state) = self.runtime.lock() {
            stop_process(&mut runtime_state);
        }
    }
}

#[tauri::command]
fn runtime_snapshot(state: tauri::State<'_, DesktopState>) -> Result<RuntimeSnapshot, String> {
    let mut runtime_state = state.runtime.lock().map_err(|_| "runtime state lock failed".to_string())?;
    Ok(build_snapshot(&mut runtime_state))
}

#[tauri::command]
fn remember_material_file(
    kind: MaterialKind,
    path: String,
    state: tauri::State<'_, DesktopState>,
) -> Result<RuntimeSnapshot, String> {
    let mut runtime_state = state.runtime.lock().map_err(|_| "runtime state lock failed".to_string())?;
    match kind {
        MaterialKind::Resume => runtime_state.resume_path = Some(path),
        MaterialKind::Jd => runtime_state.jd_path = Some(path),
    }
    runtime_state.last_error = None;
    Ok(build_snapshot(&mut runtime_state))
}

#[tauri::command]
fn prepare_interview_materials(session_id: String, state: tauri::State<'_, DesktopState>) -> Result<Value, String> {
    let (resume_path, jd_path) = {
        let runtime_state = state.runtime.lock().map_err(|_| "runtime state lock failed".to_string())?;
        (runtime_state.resume_path.clone(), runtime_state.jd_path.clone())
    };
    let resume_path = resume_path.unwrap_or_default();
    let jd_path = jd_path.unwrap_or_default();
    run_python_json(&format!(
        "from pathlib import Path; from interview_agent.gui_runtime import load_runtime; from interview_agent.kb.parser import extract_text; runtime=load_runtime({:?}); runtime.create_or_open_session({:?}); resume_text=extract_text(Path({:?})) if {:?} else ''; jd_text=extract_text(Path({:?})) if {:?} else ''; print_json(runtime.prepare_interview_materials(session_id={:?}, resume_text=resume_text, jd_text=jd_text))",
        CONFIG_PATH, session_id, resume_path, resume_path, jd_path, jd_path, session_id
    ))
}

#[tauri::command]
fn start_mock_interview(payload: StartMockInterviewPayload) -> Result<Value, String> {
    run_python_json(&format!(
        "from interview_agent.gui_runtime import load_runtime; runtime=load_runtime({:?}); runtime.create_or_open_session({:?}); print_json(runtime.start_mock_interview(session_id={:?}, target_role={:?}, question_count={:?}, followup_rounds={:?}, question_type={:?}))",
        CONFIG_PATH,
        payload.session_id,
        payload.session_id,
        payload.target_role,
        payload.question_count.unwrap_or(5),
        payload.followup_rounds.unwrap_or(1),
        payload.question_type.unwrap_or_else(|| "行为面试".to_string())
    ))
}

#[tauri::command]
fn start_algorithm_practice(payload: StartAlgorithmPracticePayload) -> Result<Value, String> {
    run_python_json(&format!(
        "from interview_agent.gui_runtime import load_runtime; runtime=load_runtime({:?}); runtime.create_or_open_session({:?}); print_json(runtime.start_algorithm_practice(session_id={:?}, practice_topic={:?}, difficulty={:?}, question_count={:?}))",
        CONFIG_PATH,
        payload.session_id,
        payload.session_id,
        payload.practice_topic,
        payload.difficulty.unwrap_or_else(|| "medium".to_string()),
        payload.question_count.unwrap_or(3)
    ))
}

#[tauri::command]
fn submit_mock_answer(payload: SubmitMockAnswerPayload) -> Result<Value, String> {
    run_python_json(&format!(
        "from interview_agent.gui_runtime import load_runtime; runtime=load_runtime({:?}); runtime.create_or_open_session({:?}); print_json(runtime.submit_mock_answer(session_id={:?}, answer={:?}))",
        CONFIG_PATH, payload.session_id, payload.session_id, payload.answer
    ))
}

#[tauri::command]
fn end_mock_interview(session_id: String) -> Result<Value, String> {
    run_python_json(&format!(
        "from interview_agent.gui_runtime import load_runtime; runtime=load_runtime({:?}); runtime.create_or_open_session({:?}); print_json(runtime.end_mock_interview({:?}))",
        CONFIG_PATH, session_id, session_id
    ))
}

#[tauri::command]
fn list_users() -> Result<Vec<UserRecord>, String> {
    let output = run_python_json(
        "from interview_agent.config import load_config; from interview_agent.storage import list_users; c=load_config('config/interview-agent.toml'); print_json(list_users(c.storage.database_path))",
    )?;
    let users = output
        .as_array()
        .ok_or_else(|| "invalid list_users payload".to_string())?;
    let mut records = Vec::with_capacity(users.len());
    for user in users {
        records.push(UserRecord {
            user_id: user.get("user_id").and_then(Value::as_str).unwrap_or_default().to_string(),
            username: user.get("username").and_then(Value::as_str).unwrap_or_default().to_string(),
            role: user.get("role").and_then(Value::as_str).unwrap_or_default().to_string(),
            status: user.get("status").and_then(Value::as_str).unwrap_or_default().to_string(),
        });
    }
    Ok(records)
}

#[tauri::command]
fn add_user(payload: AddUserPayload) -> Result<UserRecord, String> {
    let output = run_python_json(&format!(
        "from interview_agent.config import load_config; from interview_agent.storage import create_user; c=load_config('config/interview-agent.toml'); print_json(create_user(c.storage.database_path, username={:?}, password={:?}, role={:?}))",
        payload.username, payload.password, payload.role
    ))?;
    Ok(UserRecord {
        user_id: output.get("user_id").and_then(Value::as_str).unwrap_or_default().to_string(),
        username: output.get("username").and_then(Value::as_str).unwrap_or_default().to_string(),
        role: output.get("role").and_then(Value::as_str).unwrap_or_default().to_string(),
        status: output.get("status").and_then(Value::as_str).unwrap_or_default().to_string(),
    })
}

#[tauri::command]
fn update_user_status(payload: UpdateUserStatusPayload) -> Result<bool, String> {
    let output = run_python_json(&format!(
        "from interview_agent.config import load_config; from interview_agent.storage import set_user_status; c=load_config('config/interview-agent.toml'); print_json(set_user_status(c.storage.database_path, username={:?}, status={:?}))",
        payload.username, payload.status
    ))?;
    output
        .as_bool()
        .ok_or_else(|| "invalid update_user_status payload".to_string())
}

#[tauri::command]
fn login_user(payload: LoginPayload, state: tauri::State<'_, DesktopState>) -> Result<Option<UserRecord>, String> {
    let output = run_python_json(&format!(
        "from interview_agent.config import load_config; from interview_agent.storage import verify_login; c=load_config('config/interview-agent.toml'); print_json(verify_login(c.storage.database_path, username={:?}, password={:?}))",
        payload.username, payload.password
    ))?;
    if output.is_null() {
        return Ok(None);
    }
    let user_record = UserRecord {
        user_id: output.get("user_id").and_then(Value::as_str).unwrap_or_default().to_string(),
        username: output.get("username").and_then(Value::as_str).unwrap_or_default().to_string(),
        role: output.get("role").and_then(Value::as_str).unwrap_or_default().to_string(),
        status: output.get("status").and_then(Value::as_str).unwrap_or_default().to_string(),
    };
    let mut runtime_state = state.runtime.lock().map_err(|_| "runtime state lock failed".to_string())?;
    runtime_state.current_user = Some(user_record.username.clone());
    runtime_state.current_user_role = Some(user_record.role.clone());
    Ok(Some(user_record))
}

#[tauri::command]
fn logout_user(state: tauri::State<'_, DesktopState>) -> Result<(), String> {
    let mut runtime_state = state.runtime.lock().map_err(|_| "runtime state lock failed".to_string())?;
    runtime_state.current_user = None;
    runtime_state.current_user_role = None;
    Ok(())
}

#[tauri::command]
fn start_python_runtime(state: tauri::State<'_, DesktopState>) -> Result<RuntimeSnapshot, String> {
    let mut runtime_state = state.runtime.lock().map_err(|_| "runtime state lock failed".to_string())?;
    if child_is_running(&mut runtime_state) {
        return Ok(build_snapshot(&mut runtime_state));
    }

    let repo_root = repo_root()?;
    let mut command = uv_command();
    let child_process = command
        .args(["run", "interview-agent", "--config", CONFIG_PATH])
        .current_dir(repo_root)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("failed to start Python runtime: {error}"))?;

    runtime_state.python_process = Some(child_process);
    thread::sleep(Duration::from_millis(300));
    if !child_is_running(&mut runtime_state) {
        runtime_state.last_error = Some("Python runtime exited during startup".to_string());
    } else {
        runtime_state.last_error = None;
    }
    Ok(build_snapshot(&mut runtime_state))
}

#[tauri::command]
fn stop_python_runtime(state: tauri::State<'_, DesktopState>) -> Result<RuntimeSnapshot, String> {
    let mut runtime_state = state.runtime.lock().map_err(|_| "runtime state lock failed".to_string())?;
    stop_process(&mut runtime_state);
    runtime_state.last_error = None;
    Ok(build_snapshot(&mut runtime_state))
}

fn build_snapshot(runtime_state: &mut RuntimeState) -> RuntimeSnapshot {
    let python_runtime_running = child_is_running(runtime_state);
    let knowledge_base_status = match probe_knowledge_base_status() {
        Ok(status) => status,
        Err(error_message) => {
            runtime_state.last_error = Some(error_message);
            "unavailable".to_string()
        }
    };

    RuntimeSnapshot {
        is_desktop_shell: true,
        python_runtime_running,
        knowledge_base_status,
        config_path: CONFIG_PATH.to_string(),
        resume_path: runtime_state.resume_path.clone(),
        jd_path: runtime_state.jd_path.clone(),
        last_error: runtime_state.last_error.clone(),
        current_user: runtime_state.current_user.clone(),
        current_user_role: runtime_state.current_user_role.clone(),
    }
}

fn run_python_json(payload: &str) -> Result<Value, String> {
    let script = format!(
        "import json\nfrom pathlib import Path\nimport sys\nsys.path.insert(0, str(Path('src').resolve()))\ndef print_json(value):\n    print(json.dumps(value, ensure_ascii=False))\n{}\n",
        payload
    );
    let output = uv_command()
        .args(["run", "python", "-c", &script])
        .current_dir(repo_root()?)
        .output()
        .map_err(|error| format!("failed to run python command: {error}"))?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    serde_json::from_slice(&output.stdout).map_err(|error| format!("failed to parse python output: {error}"))
}

fn child_is_running(runtime_state: &mut RuntimeState) -> bool {
    let child_status = match runtime_state.python_process.as_mut() {
        Some(child_process) => child_process.try_wait(),
        None => return false,
    };

    match child_status {
        Ok(None) => true,
        Ok(Some(_)) => {
            runtime_state.python_process = None;
            false
        }
        Err(error) => {
            runtime_state.last_error = Some(error.to_string());
            runtime_state.python_process = None;
            false
        }
    }
}

fn stop_process(runtime_state: &mut RuntimeState) {
    if let Some(mut child_process) = runtime_state.python_process.take() {
        terminate_child_process(&mut child_process);
    }
}

fn terminate_child_process(child_process: &mut Child) -> Option<ExitStatus> {
    terminate_process_group(child_process.id());
    if let Some(exit_status) = wait_for_child_exit(child_process, Duration::from_millis(500)) {
        return Some(exit_status);
    }

    let _ = child_process.kill();
    child_process.wait().ok()
}

fn managed_command(program: impl AsRef<OsStr>) -> Command {
    let mut command = Command::new(program);
    #[cfg(unix)]
    {
        command.process_group(0);
    }
    command
}

fn uv_command() -> Command {
    managed_command(&resolve_uv_program())
}

fn resolve_uv_program() -> OsString {
    resolve_uv_program_with_path(env::var_os("PATH"))
}

fn resolve_uv_program_with_path(path_value: Option<OsString>) -> OsString {
    if let Some(program_path) = find_program_in_path("uv", path_value) {
        return program_path.into_os_string();
    }

    for candidate_path in fallback_uv_paths() {
        if candidate_path.is_file() {
            return candidate_path.into_os_string();
        }
    }

    OsString::from("uv")
}

fn find_program_in_path(program_name: &str, path_value: Option<OsString>) -> Option<PathBuf> {
    let path_value = path_value?;
    for search_directory in env::split_paths(&path_value) {
        let candidate_path = search_directory.join(program_name);
        if candidate_path.is_file() {
            return Some(candidate_path);
        }
    }
    None
}

fn fallback_uv_paths() -> Vec<PathBuf> {
    let mut candidate_paths = vec![
        PathBuf::from("/opt/homebrew/bin/uv"),
        PathBuf::from("/usr/local/bin/uv"),
        PathBuf::from("/usr/bin/uv"),
    ];
    if let Some(home_directory) = env::var_os("HOME") {
        let home_directory_path = PathBuf::from(home_directory);
        candidate_paths.push(home_directory_path.join(".local/bin/uv"));
        candidate_paths.push(home_directory_path.join(".cargo/bin/uv"));
    }
    candidate_paths
}

fn wait_for_child_exit(child_process: &mut Child, timeout: Duration) -> Option<ExitStatus> {
    let deadline = std::time::Instant::now() + timeout;
    loop {
        match child_process.try_wait() {
            Ok(Some(exit_status)) => return Some(exit_status),
            Ok(None) if std::time::Instant::now() < deadline => thread::sleep(Duration::from_millis(20)),
            Ok(None) => return None,
            Err(_) => return None,
        }
    }
}

#[cfg(unix)]
fn terminate_process_group(process_id: u32) {
    let process_group_id = -(process_id as i32);
    unsafe {
        libc::kill(process_group_id, libc::SIGTERM);
    }
}

#[cfg(not(unix))]
fn terminate_process_group(_process_id: u32) {
}

fn cleanup_python_runtime(state: &DesktopState) {
    if let Ok(mut runtime_state) = state.runtime.lock() {
        stop_process(&mut runtime_state);
    }
}

fn probe_knowledge_base_status() -> Result<String, String> {
    let output = uv_command()
        .args(["run", "python", "-c", PYTHON_STATUS_SCRIPT])
        .current_dir(repo_root()?)
        .output()
        .map_err(|error| format!("failed to probe Python runtime: {error}"))?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }

    let status: PythonStatus = serde_json::from_slice(&output.stdout)
        .map_err(|error| format!("failed to parse Python runtime status: {error}"))?;
    Ok(status.knowledge_base_status)
}

fn repo_root() -> Result<PathBuf, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .parent()
        .and_then(|gui_dir| gui_dir.parent())
        .map(PathBuf::from)
        .ok_or_else(|| "failed to resolve repository root".to_string())
}

fn main() {
    tauri::Builder::default()
        .manage(DesktopState::default())
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                cleanup_python_runtime(window.state::<DesktopState>().inner());
            }
        })
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            runtime_snapshot,
            remember_material_file,
            prepare_interview_materials,
            start_mock_interview,
            start_algorithm_practice,
            submit_mock_answer,
            end_mock_interview,
            start_python_runtime,
            stop_python_runtime,
            list_users,
            add_user,
            update_user_status,
            login_user,
            logout_user,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Interview Agent desktop shell");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn terminate_child_process_stops_running_process() {
        let mut child_process = Command::new("sleep")
            .arg("30")
            .spawn()
            .expect("spawn sleep process");

        let process_id = child_process.id();
        let _ = terminate_child_process(&mut child_process);
        let process_still_running = Command::new("kill")
            .args(["-0", &process_id.to_string()])
            .status()
            .expect("check process status")
            .success();

        assert!(!process_still_running);
    }

    #[test]
    fn stop_process_clears_runtime_child() {
        let child_process = Command::new("sleep")
            .arg("30")
            .spawn()
            .expect("spawn sleep process");
        let mut runtime_state = RuntimeState {
            python_process: Some(child_process),
            ..RuntimeState::default()
        };

        stop_process(&mut runtime_state);

        assert!(runtime_state.python_process.is_none());
    }

    #[test]
    fn terminate_child_process_stops_process_tree() {
        let pid_file = std::env::temp_dir().join(format!(
            "interview-agent-desktop-child-{}.pid",
            std::process::id()
        ));
        let _ = std::fs::remove_file(&pid_file);
        let script = format!("sleep 30 & echo $! > {}; wait", pid_file.display());
        let mut child_process = managed_command("sh")
            .args(["-c", &script])
            .spawn()
            .expect("spawn shell process");

        for _ in 0..50 {
            if pid_file.exists() {
                break;
            }
            thread::sleep(Duration::from_millis(20));
        }

        let grandchild_process_id = std::fs::read_to_string(&pid_file)
            .expect("read grandchild pid")
            .trim()
            .to_string();

        let _ = terminate_child_process(&mut child_process);
        let process_still_running = Command::new("kill")
            .args(["-0", &grandchild_process_id])
            .status()
            .expect("check process status")
            .success();
        if process_still_running {
            let _ = Command::new("kill").arg(&grandchild_process_id).status();
        }
        let _ = std::fs::remove_file(&pid_file);

        assert!(!process_still_running);
    }

    #[test]
    fn find_program_in_path_resolves_uv_from_explicit_path() {
        let uv_path = resolve_uv_program();
        let uv_directory = PathBuf::from(&uv_path)
            .parent()
            .expect("uv parent directory")
            .to_path_buf();

        let resolved_path = find_program_in_path("uv", Some(uv_directory.into_os_string()))
            .expect("resolve uv from explicit path");

        assert_eq!(resolved_path, PathBuf::from(uv_path));
    }

    #[test]
    fn resolve_uv_program_falls_back_when_path_is_empty() {
        let uv_path = resolve_uv_program_with_path(Some(OsString::from("")));

        assert!(PathBuf::from(uv_path).is_file());
    }
}
