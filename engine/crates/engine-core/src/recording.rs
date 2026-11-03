//! Recording directory format: `events.jsonl` (one RawEvent per line) and
//! `manifest.json`, written last through a temp file + rename. Only a
//! manifest with `status == complete` whose hash and count match is loadable.
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::model::RawEvent;
use crate::ports::{RecordingWriter, SourceStats};

pub const RECORDING_FORMAT: u32 = 1;
pub const EVENTS_FILE: &str = "events.jsonl";
pub const MANIFEST_FILE: &str = "manifest.json";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RecordingStatus {
    Complete,
    Cancelled,
    FinalizeTimeout,
    WriterFailed,
    ProducerFailed,
    Lossy,
    /// Stopped by the max-duration limit, not by the operator.
    Truncated,
    /// The producer failed a liveness check at stop (events may be missing).
    SourceStale,
    Empty,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub format: u32,
    pub recording_id: String,
    pub status: RecordingStatus,
    pub reason: Option<String>,
    pub platform: String,
    pub target_process: String,
    pub input_origin: String,
    pub event_count: u64,
    pub events_sha256: String,
    pub dropped: u64,
    pub source: SourceStats,
    pub started_at_unix_ms: u64,
    pub duration_ms: u64,
    pub engine_version: String,
}

/// Facts the controller knows at seal time.
#[derive(Debug, Clone)]
pub struct Summary {
    pub recording_id: String,
    pub status: RecordingStatus,
    pub reason: Option<String>,
    pub platform: String,
    pub target_process: String,
    pub input_origin: String,
    pub dropped: u64,
    pub source: SourceStats,
    pub started_at_unix_ms: u64,
    pub duration_ms: u64,
}

pub struct FsRecordingWriter {
    dir: PathBuf,
    out: BufWriter<File>,
    hasher: Sha256,
    count: u64,
    next_seq: u64,
}

impl FsRecordingWriter {
    /// Creates `dir` (must not already contain a recording).
    pub fn create(dir: &Path) -> std::io::Result<Self> {
        fs::create_dir_all(dir)?;
        if dir.join(MANIFEST_FILE).exists() || dir.join(EVENTS_FILE).exists() {
            return Err(std::io::Error::new(
                std::io::ErrorKind::AlreadyExists,
                "recording directory not empty",
            ));
        }
        let out = BufWriter::new(
            File::options()
                .write(true)
                .create_new(true)
                .open(dir.join(EVENTS_FILE))?,
        );
        Ok(Self {
            dir: dir.to_path_buf(),
            out,
            hasher: Sha256::new(),
            count: 0,
            next_seq: 0,
        })
    }
}

impl RecordingWriter for FsRecordingWriter {
    fn write(&mut self, ev: &RawEvent) -> std::io::Result<()> {
        if ev.seq != self.next_seq {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("sequence gap: expected {}, got {}", self.next_seq, ev.seq),
            ));
        }
        let mut line = serde_json::to_vec(ev).map_err(std::io::Error::other)?;
        line.push(b'\n');
        self.out.write_all(&line)?;
        self.hasher.update(&line);
        self.count += 1;
        self.next_seq += 1;
        Ok(())
    }

    fn count(&self) -> u64 {
        self.count
    }

    fn seal(self: Box<Self>, s: &Summary) -> std::io::Result<Manifest> {
        let Self {
            dir,
            out,
            hasher,
            count,
            ..
        } = *self;
        let file = out.into_inner().map_err(|e| e.into_error())?;
        file.sync_all()?;
        let manifest = Manifest {
            format: RECORDING_FORMAT,
            recording_id: s.recording_id.clone(),
            status: s.status,
            reason: s.reason.clone(),
            platform: s.platform.clone(),
            target_process: s.target_process.clone(),
            input_origin: s.input_origin.clone(),
            event_count: count,
            events_sha256: hex(&hasher.finalize()),
            dropped: s.dropped,
            source: s.source.clone(),
            started_at_unix_ms: s.started_at_unix_ms,
            duration_ms: s.duration_ms,
            engine_version: env!("CARGO_PKG_VERSION").to_string(),
        };
        write_json_atomic(&dir.join(MANIFEST_FILE), &manifest)?;
        Ok(manifest)
    }
}

pub fn write_json_atomic<T: Serialize>(path: &Path, value: &T) -> std::io::Result<()> {
    let tmp = path.with_extension("json.tmp");
    {
        let mut f = File::create(&tmp)?;
        f.write_all(&serde_json::to_vec_pretty(value).map_err(std::io::Error::other)?)?;
        f.sync_all()?;
    }
    fs::rename(tmp, path)
}

pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn sha256_file(path: &Path) -> std::io::Result<String> {
    Ok(hex(&Sha256::digest(fs::read(path)?)))
}

#[derive(Debug, PartialEq, Eq)]
pub enum LoadError {
    Io(String),
    MissingManifest,
    BadManifest(String),
    NotComplete(RecordingStatus),
    HashMismatch,
    CountMismatch { manifest: u64, actual: u64 },
    BadEvent { line: u64, error: String },
    SequenceGap { line: u64 },
}

/// Loads a sealed, complete recording after checking integrity.
pub fn load(dir: &Path) -> Result<(Manifest, Vec<RawEvent>), LoadError> {
    let mpath = dir.join(MANIFEST_FILE);
    if !mpath.exists() {
        return Err(LoadError::MissingManifest);
    }
    let manifest: Manifest =
        serde_json::from_slice(&fs::read(&mpath).map_err(|e| LoadError::Io(e.to_string()))?)
            .map_err(|e| LoadError::BadManifest(e.to_string()))?;
    if manifest.format != RECORDING_FORMAT {
        return Err(LoadError::BadManifest(format!(
            "unsupported format {}",
            manifest.format
        )));
    }
    if manifest.status != RecordingStatus::Complete {
        return Err(LoadError::NotComplete(manifest.status));
    }
    let epath = dir.join(EVENTS_FILE);
    if sha256_file(&epath).map_err(|e| LoadError::Io(e.to_string()))? != manifest.events_sha256 {
        return Err(LoadError::HashMismatch);
    }
    let reader = BufReader::new(File::open(&epath).map_err(|e| LoadError::Io(e.to_string()))?);
    let mut events = Vec::new();
    for (i, line) in reader.lines().enumerate() {
        let line = line.map_err(|e| LoadError::Io(e.to_string()))?;
        let ev: RawEvent = serde_json::from_str(&line).map_err(|e| LoadError::BadEvent {
            line: i as u64,
            error: e.to_string(),
        })?;
        if ev.seq != i as u64 {
            return Err(LoadError::SequenceGap { line: i as u64 });
        }
        events.push(ev);
    }
    if events.len() as u64 != manifest.event_count {
        return Err(LoadError::CountMismatch {
            manifest: manifest.event_count,
            actual: events.len() as u64,
        });
    }
    Ok((manifest, events))
}
