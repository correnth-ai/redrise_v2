//! Capture lifecycle with bounded finalization.
//!
//! End of stream is structural: the producer owns the only `EventTx`; when it
//! ends, the channel disconnects and the writer's blocking `recv` returns.
//! No queue counters, no `empty()` polling, no busy loops. The controller
//! waits for completion with a deadline and never promotes a partial
//! recording: only `Complete` is sealed as compilable.
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use crate::ports::{EventTx, InputSource, RecordingWriter, SourceStats};
use crate::recording::{Manifest, RecordingStatus, Summary};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Control {
    Stop,
    Cancel,
}

#[derive(Debug, Clone)]
pub struct CaptureOptions {
    pub recording_id: String,
    pub platform: String,
    pub target_process: String,
    pub input_origin: String,
    pub channel_capacity: usize,
    pub max_duration: Duration,
    /// Time allowed after the stop request for producer + writer to finish.
    pub finalize_deadline: Duration,
    pub started_at_unix_ms: u64,
}

#[derive(Debug)]
pub struct CaptureOutcome {
    pub status: RecordingStatus,
    pub manifest: Option<Manifest>,
    pub reason: Option<String>,
    pub finalize_ms: u64,
}

enum WriterEnd {
    /// Stream ended (all senders dropped); writer handed back for sealing.
    Drained(Box<dyn RecordingWriter>),
    Failed(String, Box<dyn RecordingWriter>),
}

/// Runs one capture until `control` yields Stop/Cancel, the control channel
/// closes, `max_duration` elapses, or the writer fails.
pub fn run_capture(
    source: Box<dyn InputSource>,
    writer: Box<dyn RecordingWriter>,
    control: Receiver<Control>,
    opts: &CaptureOptions,
) -> CaptureOutcome {
    let (tx, rx) = mpsc::sync_channel(opts.channel_capacity.max(1));
    let dropped = Arc::new(AtomicU64::new(0));
    let writer_gone = Arc::new(AtomicBool::new(false));
    let event_tx = EventTx::new(tx, dropped.clone(), writer_gone.clone());
    let started = Instant::now();

    // Writer thread: blocking recv until disconnect or write error.
    let (wdone_tx, wdone_rx) = mpsc::channel::<WriterEnd>();
    let (wfail_tx, wfail_rx) = mpsc::channel::<()>();
    let mut w = writer;
    thread::Builder::new()
        .name("rr-capture-writer".into())
        .spawn(move || {
            let end = loop {
                match rx.recv() {
                    Ok(ev) => {
                        if let Err(e) = w.write(&ev) {
                            let _ = wfail_tx.send(());
                            drop(rx); // producers now observe WriterGone
                            break WriterEnd::Failed(e.to_string(), w);
                        }
                    }
                    Err(_) => break WriterEnd::Drained(w),
                }
            };
            let _ = wdone_tx.send(end);
        })
        .expect("spawn writer");

    let running = match source.spawn(event_tx) {
        Ok(r) => r,
        Err(e) => {
            // event_tx was moved into spawn and dropped on error; writer drains.
            return finish_without_source(
                wdone_rx,
                opts,
                RecordingStatus::ProducerFailed,
                e,
                started,
            );
        }
    };

    // Wait for a stop condition without spinning.
    let mut cancelled = false;
    let mut truncated = false;
    let mut reason: Option<String> = None;
    let deadline_total = started + opts.max_duration;
    loop {
        if wfail_rx.try_recv().is_ok() {
            reason = Some("writer failed during capture".into());
            break;
        }
        let now = Instant::now();
        if now >= deadline_total {
            // A demonstration cut off by the limit is not a usable recording.
            truncated = true;
            reason = Some("max duration reached; recording truncated".into());
            break;
        }
        let slice = (deadline_total - now).min(Duration::from_millis(200));
        match control.recv_timeout(slice) {
            Ok(Control::Stop) => break,
            Ok(Control::Cancel) => {
                cancelled = true;
                break;
            }
            Err(RecvTimeoutError::Timeout) => continue,
            Err(RecvTimeoutError::Disconnected) => break,
        }
    }

    // Liveness before stopping: a producer that silently stopped delivering
    // (e.g. an OS-removed hook) must not yield a complete recording.
    let liveness = running.check_liveness();

    // Bounded finalization.
    let stop_at = Instant::now();
    running.request_stop();
    let (jtx, jrx) = mpsc::channel::<Result<SourceStats, String>>();
    thread::Builder::new()
        .name("rr-capture-join".into())
        .spawn(move || {
            let _ = jtx.send(running.join());
        })
        .expect("spawn joiner");

    let remaining = |t: Instant| opts.finalize_deadline.saturating_sub(t.elapsed());
    let source_result = match jrx.recv_timeout(remaining(stop_at)) {
        Ok(r) => r,
        Err(_) => {
            return CaptureOutcome {
                status: RecordingStatus::FinalizeTimeout,
                manifest: None,
                reason: Some("producer did not stop before the finalize deadline".into()),
                finalize_ms: stop_at.elapsed().as_millis() as u64,
            }
        }
    };
    let writer_end = match wdone_rx.recv_timeout(remaining(stop_at)) {
        Ok(end) => end,
        Err(_) => {
            return CaptureOutcome {
                status: RecordingStatus::FinalizeTimeout,
                manifest: None,
                reason: Some("writer did not drain before the finalize deadline".into()),
                finalize_ms: stop_at.elapsed().as_millis() as u64,
            }
        }
    };

    let dropped_n = dropped.load(Ordering::Relaxed);
    let (status, writer, stats) = match (writer_end, source_result) {
        (WriterEnd::Failed(e, w), r) => {
            reason = Some(format!("writer error: {e}"));
            (RecordingStatus::WriterFailed, w, r.unwrap_or_default())
        }
        (WriterEnd::Drained(w), Err(e)) => {
            reason = Some(format!("producer failed: {e}"));
            (RecordingStatus::ProducerFailed, w, SourceStats::default())
        }
        (WriterEnd::Drained(w), Ok(stats)) => {
            let st = if cancelled {
                RecordingStatus::Cancelled
            } else if truncated {
                RecordingStatus::Truncated
            } else if let Err(e) = &liveness {
                reason = Some(format!("producer not live at stop: {e}"));
                RecordingStatus::SourceStale
            } else if dropped_n > 0 {
                reason = Some(format!("{dropped_n} events dropped (channel full)"));
                RecordingStatus::Lossy
            } else {
                RecordingStatus::Complete
            };
            (st, w, stats)
        }
    };
    seal(
        writer, status, reason, stats, dropped_n, opts, started, stop_at,
    )
}

#[allow(clippy::too_many_arguments)]
fn seal(
    writer: Box<dyn RecordingWriter>,
    mut status: RecordingStatus,
    mut reason: Option<String>,
    stats: SourceStats,
    dropped: u64,
    opts: &CaptureOptions,
    started: Instant,
    stop_at: Instant,
) -> CaptureOutcome {
    if status == RecordingStatus::Complete && writer.count() == 0 {
        status = RecordingStatus::Empty;
        reason = Some("no events captured on the target".into());
    }
    let summary = Summary {
        recording_id: opts.recording_id.clone(),
        status,
        reason: reason.clone(),
        platform: opts.platform.clone(),
        target_process: opts.target_process.clone(),
        input_origin: opts.input_origin.clone(),
        dropped,
        source: stats,
        started_at_unix_ms: opts.started_at_unix_ms,
        duration_ms: started.elapsed().as_millis() as u64,
    };
    let finalize_ms = stop_at.elapsed().as_millis() as u64;
    match writer.seal(&summary) {
        Ok(m) => CaptureOutcome {
            status,
            manifest: Some(m),
            reason,
            finalize_ms,
        },
        Err(e) => CaptureOutcome {
            status: RecordingStatus::WriterFailed,
            manifest: None,
            reason: Some(format!("seal failed: {e}")),
            finalize_ms,
        },
    }
}

fn finish_without_source(
    wdone_rx: Receiver<WriterEnd>,
    opts: &CaptureOptions,
    status: RecordingStatus,
    reason: String,
    started: Instant,
) -> CaptureOutcome {
    let stop_at = Instant::now();
    match wdone_rx.recv_timeout(opts.finalize_deadline) {
        Ok(WriterEnd::Drained(w)) | Ok(WriterEnd::Failed(_, w)) => seal(
            w,
            status,
            Some(reason),
            SourceStats::default(),
            0,
            opts,
            started,
            stop_at,
        ),
        Err(_) => CaptureOutcome {
            status: RecordingStatus::FinalizeTimeout,
            manifest: None,
            reason: Some(reason),
            finalize_ms: 0,
        },
    }
}
