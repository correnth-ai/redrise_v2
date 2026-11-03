//! RedRise Engine domain.
//!
//! Single responsibilities per module: `capture` (lifecycle and bounded
//! finalization), `recording` (on-disk format and integrity), `compile`
//! (recording -> IR), `ir` (versioned procedure), `execute` (procedure ->
//! input through ports). OS access lives behind `ports`; adapters are in
//! other crates.

pub mod capture;
pub mod compile;
pub mod execute;
pub mod ir;
pub mod model;
pub mod ports;
pub mod recording;

pub const PLATFORM_WINDOWS_X64: &str = "windows-x86_64";
