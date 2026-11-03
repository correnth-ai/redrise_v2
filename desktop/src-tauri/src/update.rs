//! Assisted update (P11). The channel publishes `latest.json` and a detached
//! Ed25519 signature `latest.json.sig` (base64). The app trusts only the
//! embedded public key; the installer download must match the signed size and
//! SHA-256 before it is ever executed. Applying waits for a safe point (no job
//! or recording on this station), stops the app-managed children cleanly and
//! hands over to the installer, which keeps the previous version for recovery.
use std::io::Read;
use std::path::PathBuf;

use base64::Engine as _;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::paths::Paths;

/// Release-channel public key (the private key never leaves the release vault).
pub const CHANNEL_PUBLIC_KEY_B64: &str = include_str!("../channel-public-key.b64");

/// Channel: `<data>/config/update.json` {"channel_url"} overrides the default
/// compiled into the release (REDRISE_CHANNEL_URL at build time; for the
/// closed beta, the local isolated site of P12).
pub fn channel_url(p: &Paths) -> Option<String> {
    std::fs::read(p.data_root.join("config").join("update.json")).ok()
        .and_then(|b| serde_json::from_slice::<Value>(&b).ok())
        .and_then(|v| v["channel_url"].as_str().map(String::from))
        .or_else(|| option_env!("REDRISE_CHANNEL_URL").map(String::from))
        .map(|s| s.trim_end_matches('/').to_string())
}

/// Update-channel log (`<data>/logs/update.log`): failed checks stay visible to support.
pub fn log(p: &Paths, line: &str) {
    use std::io::Write as _;
    let dir = p.data_root.join("logs");
    let _ = std::fs::create_dir_all(&dir);
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(dir.join("update.log")) {
        let t = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
        let _ = writeln!(f, "{t} {line}");
    }
}

fn fail(code: &str, what: &str, detail: String) -> Value {
    let mut v = crate::diag_err(code, what, &detail);
    v["diagnostic"]["module_hints"] = json!(["RR-UI", "RR-RUNTIME"]);
    // Texts aligned with contracts/errors.json for the update codes.
    let (category, completed, next, retry) = match code {
        "UPDATE-INVALID" => ("contract", "Nothing was installed; the current version and data are intact.",
                             "Tell support; do not install files received by other means.", "not_useful"),
        "UPDATE-CHANNEL-UNREACHABLE" => ("communication", "The installed version stays in use.", "No action is needed now.", "safe"),
        _ => ("communication", "The installed version stays in use.", "Try again later with Update now.", "safe"),
    };
    v["diagnostic"]["category"] = json!(category);
    v["diagnostic"]["completed"] = json!(completed);
    v["diagnostic"]["pending"] = json!("The update was not applied.");
    v["diagnostic"]["next_action"] = json!(next);
    v["diagnostic"]["retry"] = json!(retry);
    v
}

/// Pure verification of a signed manifest (unit-tested).
pub fn verify_manifest(manifest: &[u8], sig_b64: &str, key_b64: &str) -> Result<Value, String> {
    let key: [u8; 32] = base64::engine::general_purpose::STANDARD.decode(key_b64.trim()).map_err(|e| e.to_string())?
        .try_into().map_err(|_| "invalid public key".to_string())?;
    let sig: [u8; 64] = base64::engine::general_purpose::STANDARD.decode(sig_b64.trim()).map_err(|e| e.to_string())?
        .try_into().map_err(|_| "signature has an invalid size".to_string())?;
    VerifyingKey::from_bytes(&key).map_err(|e| e.to_string())?
        .verify(manifest, &Signature::from_bytes(&sig)).map_err(|_| "invalid signature".to_string())?;
    let v: Value = serde_json::from_slice(manifest).map_err(|e| e.to_string())?;
    if v["schema"] != "redrise.release/1" || v["version"].as_str().is_none() || v["installer"]["sha256"].as_str().map(|s| s.len()) != Some(64) {
        return Err("incompatible release manifest".into());
    }
    Ok(v)
}

/// "0.1.0-beta.2" > "0.1.0-beta.1" > "0.1.0-alpha"; a release without suffix is newer than its pre-releases.
pub fn newer(candidate: &str, current: &str) -> bool {
    fn key(v: &str) -> (Vec<u64>, Option<(String, u64)>) {
        let (core, pre) = v.split_once('-').map(|(a, b)| (a, Some(b))).unwrap_or((v, None));
        let nums = core.split('.').map(|x| x.parse().unwrap_or(0)).collect();
        let pre = pre.map(|p| {
            let (name, n) = p.rsplit_once('.').unwrap_or((p, "0"));
            (name.to_string(), n.parse().unwrap_or(0))
        });
        (nums, pre)
    }
    let (a, ap) = key(candidate);
    let (b, bp) = key(current);
    if a != b {
        return a > b;
    }
    match (ap, bp) {
        (None, Some(_)) => true,
        (Some(_), None) | (None, None) => false,
        (Some(x), Some(y)) => x > y,
    }
}

fn get(url: &str, limit: u64) -> Result<Vec<u8>, String> {
    let r = ureq::get(url).timeout(std::time::Duration::from_secs(60)).call().map_err(|e| e.to_string())?;
    let mut buf = Vec::new();
    r.into_reader().take(limit).read_to_end(&mut buf).map_err(|e| e.to_string())?;
    Ok(buf)
}

pub fn check(p: &Paths) -> Result<Value, Value> {
    let Some(base) = channel_url(p) else {
        return Ok(json!({"configured": false, "available": false}));
    };
    let unreachable = |e: String| fail("UPDATE-CHANNEL-UNREACHABLE", "Could not check for updates.", e);
    let manifest = get(&format!("{base}/latest.json"), 64 * 1024).map_err(unreachable)?;
    let sig = get(&format!("{base}/latest.json.sig"), 4096).map_err(unreachable)?;
    let v = verify_manifest(&manifest, &String::from_utf8_lossy(&sig), CHANNEL_PUBLIC_KEY_B64)
        .map_err(|e| fail("UPDATE-INVALID", "The offered update is not trusted and was ignored.", e))?;
    let current = env!("CARGO_PKG_VERSION");
    let available = newer(v["version"].as_str().unwrap(), current);
    Ok(json!({"configured": true, "available": available, "current": current, "release": v}))
}

pub fn download(p: &Paths, release: &Value) -> Result<PathBuf, Value> {
    let base = channel_url(p).ok_or_else(|| fail("UPDATE-INVALID", "Update channel not configured.", "no channel".into()))?;
    let name = release["installer"]["file"].as_str().unwrap_or("");
    if name.is_empty() || name.contains(['/', '\\']) || !name.ends_with(".exe") {
        return Err(fail("UPDATE-INVALID", "The offered update is not trusted and was ignored.", "invalid file name".into()));
    }
    let size = release["installer"]["size"].as_u64().unwrap_or(0);
    let dir = p.data_root.join("updates");
    std::fs::create_dir_all(&dir).map_err(|e| fail("UPDATE-DOWNLOAD", "Could not download the update.", e.to_string()))?;
    let part = dir.join(format!("{name}.part"));
    let bytes = get(&format!("{base}/{name}"), size + 1)
        .map_err(|e| fail("UPDATE-DOWNLOAD", "Could not download the update.", e))?;
    std::fs::write(&part, &bytes).map_err(|e| fail("UPDATE-DOWNLOAD", "Could not download the update.", e.to_string()))?;
    let digest = format!("{:x}", Sha256::digest(&bytes));
    if bytes.len() as u64 != size || Some(digest.as_str()) != release["installer"]["sha256"].as_str() {
        let _ = std::fs::remove_file(&part);
        return Err(fail("UPDATE-INVALID", "The downloaded package is incomplete or corrupted and was not installed.",
                        format!("size {} of {size}; sha256 {}", bytes.len(), &digest[..16])));
    }
    let done = dir.join(name);
    std::fs::rename(&part, &done).map_err(|e| fail("UPDATE-DOWNLOAD", "Could not prepare the update.", e.to_string()))?;
    Ok(done)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};

    fn signed(body: &str) -> (Vec<u8>, String, String) {
        let k = SigningKey::from_bytes(&[7u8; 32]);
        let b64 = base64::engine::general_purpose::STANDARD;
        (body.as_bytes().to_vec(), b64.encode(k.sign(body.as_bytes()).to_bytes()), b64.encode(k.verifying_key().to_bytes()))
    }

    const OK: &str = r#"{"schema":"redrise.release/1","version":"0.1.0-beta.2","installer":{"file":"x.exe","size":1,"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}"#;

    #[test]
    fn valid_signature_accepted() {
        let (m, s, k) = signed(OK);
        assert_eq!(verify_manifest(&m, &s, &k).unwrap()["version"], "0.1.0-beta.2");
    }

    #[test]
    fn tampered_manifest_or_wrong_key_refused() {
        let (mut m, s, k) = signed(OK);
        m[40] ^= 1;
        assert!(verify_manifest(&m, &s, &k).is_err());
        let (m2, s2, _) = signed(OK);
        let other = base64::engine::general_purpose::STANDARD.encode(SigningKey::from_bytes(&[9u8; 32]).verifying_key().to_bytes());
        assert!(verify_manifest(&m2, &s2, &other).is_err());
        assert!(verify_manifest(&m2, "AAAA", &other).is_err());
    }

    #[test]
    fn incompatible_manifest_refused_even_if_signed() {
        let (m, s, k) = signed(r#"{"schema":"redrise.release/0","version":"9.9.9","installer":{"sha256":"x"}}"#);
        assert!(verify_manifest(&m, &s, &k).is_err());
    }

    #[test]
    fn version_order() {
        assert!(newer("0.1.0-beta.2", "0.1.0-beta.1"));
        assert!(newer("0.1.0", "0.1.0-beta.9"));
        assert!(newer("0.2.0-beta.1", "0.1.9"));
        assert!(!newer("0.1.0-beta.1", "0.1.0-beta.1"));
        assert!(!newer("0.1.0-beta.1", "0.1.0"));
    }
}
