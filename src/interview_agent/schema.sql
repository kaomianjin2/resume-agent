PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT NOT NULL,
    state_key TEXT NOT NULL,
    state_value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, state_key),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS node_runs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    node_name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_payload TEXT NOT NULL,
    output_payload TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES knowledge_documents(document_id) ON DELETE CASCADE,
    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS knowledge_base_meta (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'member')),
    status TEXT NOT NULL CHECK (status IN ('enabled', 'disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_applications (
    job_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    external_job_id TEXT NOT NULL,
    job_url TEXT NOT NULL,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT NOT NULL,
    employment_type TEXT,
    salary_range TEXT,
    posted_at TEXT,
    remote_policy TEXT,
    level TEXT,
    experience_requirement TEXT,
    education_requirement TEXT,
    industry TEXT,
    company_size TEXT,
    funding_stage TEXT,
    tech_stack TEXT,
    benefits TEXT,
    published_at TEXT,
    detail_url TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    field_confidence TEXT NOT NULL,
    normalized_payload TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending_review', 'approved', 'submitted', 'failed', 'skipped', 'duplicate')),
    duplicate_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_application_filters (
    filter_id TEXT PRIMARY KEY,
    hard_filters TEXT NOT NULL,
    ranking_preferences TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_application_evaluations (
    evaluation_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    score REAL,
    hard_filter_status TEXT,
    strengths TEXT,
    risks TEXT,
    missing_information TEXT,
    resume_improvement_advice TEXT,
    application_message TEXT,
    recommended INTEGER NOT NULL DEFAULT 0 CHECK (recommended IN (0, 1)),
    recommendation_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES job_applications(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS application_confirmations (
    confirmation_batch_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    confirmed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_records (
    record_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    confirmation_batch_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending_review', 'approved', 'submitted', 'failed', 'skipped', 'duplicate')),
    submitted_at TEXT,
    failure_reason TEXT,
    platform_message TEXT,
    duplicate_detected INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_detected IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (job_id, confirmation_batch_id),
    FOREIGN KEY (job_id) REFERENCES job_applications(job_id) ON DELETE CASCADE,
    FOREIGN KEY (confirmation_batch_id) REFERENCES application_confirmations(confirmation_batch_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS collection_tasks (
    collection_task_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    search_keyword TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_platform_progress (
    progress_id TEXT PRIMARY KEY,
    collection_task_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    current_page INTEGER NOT NULL DEFAULT 0,
    last_job_offset INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    failure_reason TEXT,
    manual_takeover_required INTEGER NOT NULL DEFAULT 0 CHECK (manual_takeover_required IN (0, 1)),
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (collection_task_id, platform),
    FOREIGN KEY (collection_task_id) REFERENCES collection_tasks(collection_task_id) ON DELETE CASCADE
);
