//! E02 finalization regressions with deterministic fake producers.
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use engine_core::capture::{run_capture, CaptureOptions, Control};
use engine_core::model::{RawEvent, RawKind, Rect, WindowRef};
use engine_core::ports::{
    EventTx, InputSource, Offer, RecordingWriter, RunningSource, SourceStats,
};
use engine_core::recording::{self, FsRecordingWriter, Manifest, RecordingStatus, Summary};

fn ev(seq: u64) -> RawEvent {
    RawEvent {
        seq,
        t_us: seq * 1000,
        kind: RawKind::Key {
            vk: 0x41,
            scan: 0x1E,
            down: seq.is_multiple_of(2),
            extended: false,
            ch: Some("a".into()),
            dead: false,
        },
        window: WindowRef {
            pid: 1,
            process_image: "notepad.exe".into(),
            class: "Notepad".into(),
            title: "t".into(),
            rect: Rect::default(),
        },
    }
}

fn opts(cap: usize, deadline_ms: u64) -> CaptureOptions {
    CaptureOptions {
        recording_id: "test".into(),
        platform: "windows-x86_64".into(),
        target_process: "notepad.exe".into(),
        input_origin: "synthetic-test".into(),
        channel_capacity: cap,
        max_duration: Duration::from_secs(30),
        finalize_deadline: Duration::from_millis(deadline_ms),
        started_at_unix_ms: 0,
    }
}

#[derive(Clone, Copy)]
enum Mode {
    /// Emit n events, then wait for stop.
    Emit(u64),
    /// Emit n events then panic.
    Panic(u64),
    /// Ignore stop forever (hung producer); keeps the sender alive.
    Hang,
    /// Emit n events, keep sending until the writer is gone.
    UntilWriterGone,
    /// Emit n events, then fail the liveness check at stop.
    Stale(u64),
}

struct Fake(Mode);
struct Running {
    stale: bool,
    stop: Arc<AtomicBool>,
    handle: JoinHandle<SourceStats>,
}

impl InputSource for Fake {
    fn spawn(self: Box<Self>, mut tx: EventTx) -> Result<Box<dyn RunningSource>, String> {
        let stop = Arc::new(AtomicBool::new(false));
        let s2 = stop.clone();
        let mode = self.0;
        let handle = thread::spawn(move || {
            let mut seq = 0u64;
            match mode {
                Mode::Emit(n) | Mode::Stale(n) => {
                    while seq < n {
                        tx.offer(ev(seq));
                        seq += 1;
                    }
                    while !s2.load(Ordering::SeqCst) {
                        thread::sleep(Duration::from_millis(5));
                    }
                }
                Mode::Panic(n) => {
                    while seq < n {
                        tx.offer(ev(seq));
                        seq += 1;
                    }
                    panic!("producer crashed");
                }
                Mode::Hang => loop {
                    thread::sleep(Duration::from_millis(50));
                    let _keep = &tx;
                },
                Mode::UntilWriterGone => loop {
                    if tx.offer(ev(seq)) == Offer::WriterGone {
                        break;
                    }
                    seq += 1;
                    thread::sleep(Duration::from_millis(1));
                },
            }
            drop(tx);
            SourceStats::default()
        });
        Ok(Box::new(Running {
            stale: matches!(mode, Mode::Stale(_)),
            stop,
            handle,
        }))
    }
}

impl RunningSource for Running {
    fn check_liveness(&self) -> Result<(), String> {
        if self.stale {
            Err("no callback observed (simulated)".into())
        } else {
            Ok(())
        }
    }
    fn request_stop(&self) {
        self.stop.store(true, Ordering::SeqCst);
    }
    fn join(self: Box<Self>) -> Result<SourceStats, String> {
        self.handle
            .join()
            .map_err(|_| "producer panicked".to_string())
    }
}

/// Writer that fails on the k-th write.
struct FailingWriter {
    inner: FsRecordingWriter,
    fail_at: u64,
}
impl RecordingWriter for FailingWriter {
    fn write(&mut self, e: &RawEvent) -> std::io::Result<()> {
        if e.seq == self.fail_at {
            return Err(std::io::Error::other("disk full (simulated)"));
        }
        self.inner.write(e)
    }
    fn count(&self) -> u64 {
        self.inner.count()
    }
    fn seal(self: Box<Self>, s: &Summary) -> std::io::Result<Manifest> {
        Box::new(self.inner).seal(s)
    }
}

fn stop_after(ms: u64) -> mpsc::Receiver<Control> {
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        thread::sleep(Duration::from_millis(ms));
        let _ = tx.send(Control::Stop);
    });
    rx
}

#[test]
fn complete_recording_drains_pending_events_and_loads() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let out = run_capture(
        Box::new(Fake(Mode::Emit(500))),
        w,
        stop_after(100),
        &opts(1024, 2000),
    );
    assert_eq!(out.status, RecordingStatus::Complete, "{:?}", out.reason);
    let (m, events) = recording::load(dir.path()).unwrap();
    assert_eq!(m.event_count, 500);
    assert_eq!(events.len(), 500);
}

#[test]
fn producer_panic_is_producer_failed_and_not_loadable() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let out = run_capture(
        Box::new(Fake(Mode::Panic(10))),
        w,
        stop_after(100),
        &opts(64, 2000),
    );
    assert_eq!(out.status, RecordingStatus::ProducerFailed);
    assert_eq!(
        recording::load(dir.path()).unwrap_err(),
        recording::LoadError::NotComplete(RecordingStatus::ProducerFailed)
    );
}

#[test]
fn hung_producer_hits_finalize_deadline_without_spinning() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let t = Instant::now();
    let out = run_capture(
        Box::new(Fake(Mode::Hang)),
        w,
        stop_after(50),
        &opts(64, 300),
    );
    let elapsed = t.elapsed();
    assert_eq!(out.status, RecordingStatus::FinalizeTimeout);
    assert!(elapsed < Duration::from_millis(1500), "took {elapsed:?}");
    // Nothing sealed: no manifest, so not compilable.
    assert_eq!(
        recording::load(dir.path()).unwrap_err(),
        recording::LoadError::MissingManifest
    );
}

#[test]
fn writer_error_stops_capture_and_is_writer_failed() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FailingWriter {
        inner: FsRecordingWriter::create(dir.path()).unwrap(),
        fail_at: 5,
    });
    // No stop signal: the writer failure itself must end the capture.
    let (_keep, rx) = mpsc::channel::<Control>();
    let t = Instant::now();
    let out = run_capture(Box::new(Fake(Mode::UntilWriterGone)), w, rx, &opts(8, 2000));
    assert_eq!(
        out.status,
        RecordingStatus::WriterFailed,
        "{:?}",
        out.reason
    );
    assert!(t.elapsed() < Duration::from_secs(3));
    assert!(recording::load(dir.path()).is_err());
}

#[test]
fn overflow_marks_recording_lossy() {
    let dir = tempfile::tempdir().unwrap();
    struct Slow(FsRecordingWriter);
    impl RecordingWriter for Slow {
        fn write(&mut self, e: &RawEvent) -> std::io::Result<()> {
            thread::sleep(Duration::from_millis(2));
            self.0.write(e)
        }
        fn count(&self) -> u64 {
            self.0.count()
        }
        fn seal(self: Box<Self>, s: &Summary) -> std::io::Result<Manifest> {
            Box::new(self.0).seal(s)
        }
    }
    // Producer emits 200 events at once into a capacity-4 channel: drops.
    let w = Box::new(Slow(FsRecordingWriter::create(dir.path()).unwrap()));
    let out = run_capture(
        Box::new(Fake(Mode::Emit(200))),
        w,
        stop_after(200),
        &opts(4, 3000),
    );
    assert_eq!(out.status, RecordingStatus::Lossy, "{:?}", out.reason);
    let m = out.manifest.unwrap();
    assert!(m.dropped > 0 && m.event_count + m.dropped == 200);
    assert!(recording::load(dir.path()).is_err());
}

#[test]
fn cancel_is_cancelled_and_not_loadable() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let (tx, rx) = mpsc::channel();
    tx.send(Control::Cancel).unwrap();
    let out = run_capture(Box::new(Fake(Mode::Emit(3))), w, rx, &opts(64, 2000));
    assert_eq!(out.status, RecordingStatus::Cancelled);
    assert!(recording::load(dir.path()).is_err());
}

#[test]
fn empty_recording_is_not_complete() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let out = run_capture(
        Box::new(Fake(Mode::Emit(0))),
        w,
        stop_after(20),
        &opts(64, 2000),
    );
    assert_eq!(out.status, RecordingStatus::Empty);
    assert!(recording::load(dir.path()).is_err());
}

#[test]
fn tampered_events_fail_integrity() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let out = run_capture(
        Box::new(Fake(Mode::Emit(4))),
        w,
        stop_after(30),
        &opts(64, 2000),
    );
    assert_eq!(out.status, RecordingStatus::Complete);
    let p = dir.path().join(recording::EVENTS_FILE);
    let mut s = std::fs::read_to_string(&p).unwrap();
    s = s.replacen("\"a\"", "\"b\"", 1);
    std::fs::write(&p, s).unwrap();
    assert_eq!(
        recording::load(dir.path()).unwrap_err(),
        recording::LoadError::HashMismatch
    );
}

#[test]
fn refuses_to_reuse_a_recording_directory() {
    let dir = tempfile::tempdir().unwrap();
    let _first = FsRecordingWriter::create(dir.path()).unwrap();
    assert!(FsRecordingWriter::create(dir.path()).is_err());
}

#[test]
fn max_duration_truncates_and_is_not_loadable() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let (_keep, rx) = mpsc::channel::<Control>();
    let mut o = opts(64, 2000);
    o.max_duration = Duration::from_millis(150);
    let out = run_capture(Box::new(Fake(Mode::Emit(5))), w, rx, &o);
    assert_eq!(out.status, RecordingStatus::Truncated);
    assert_eq!(
        recording::load(dir.path()).unwrap_err(),
        recording::LoadError::NotComplete(RecordingStatus::Truncated)
    );
}

#[test]
fn stale_producer_at_stop_is_not_complete() {
    let dir = tempfile::tempdir().unwrap();
    let w = Box::new(FsRecordingWriter::create(dir.path()).unwrap());
    let out = run_capture(
        Box::new(Fake(Mode::Stale(5))),
        w,
        stop_after(30),
        &opts(64, 2000),
    );
    assert_eq!(out.status, RecordingStatus::SourceStale);
    assert!(recording::load(dir.path()).is_err());
}
