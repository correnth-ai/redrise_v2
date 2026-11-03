//! HTTPS client to the team Core, pinned to the host certificate SHA-256
//! from the join code (P05-D5). Error bodies are the Core's diagnostics,
//! passed through unchanged; transport failures become CORE-UNREACHABLE.
use std::sync::Arc;
use std::time::Duration;

use rustls::client::danger::{HandshakeSignatureValid, ServerCertVerified, ServerCertVerifier};
use rustls::pki_types::{CertificateDer, ServerName, UnixTime};
use rustls::{DigitallySignedStruct, SignatureScheme};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::paths::Paths;

#[derive(Debug)]
struct Pinned {
    fp: String,
    provider: Arc<rustls::crypto::CryptoProvider>,
}

impl ServerCertVerifier for Pinned {
    fn verify_server_cert(&self, end_entity: &CertificateDer<'_>, _: &[CertificateDer<'_>], _: &ServerName<'_>,
                          _: &[u8], _: UnixTime) -> Result<ServerCertVerified, rustls::Error> {
        if format!("{:x}", Sha256::digest(end_entity.as_ref())) == self.fp {
            Ok(ServerCertVerified::assertion())
        } else {
            Err(rustls::Error::General("certificate fingerprint mismatch".into()))
        }
    }
    fn verify_tls12_signature(&self, m: &[u8], c: &CertificateDer<'_>, d: &DigitallySignedStruct)
                              -> Result<HandshakeSignatureValid, rustls::Error> {
        rustls::crypto::verify_tls12_signature(m, c, d, &self.provider.signature_verification_algorithms)
    }
    fn verify_tls13_signature(&self, m: &[u8], c: &CertificateDer<'_>, d: &DigitallySignedStruct)
                              -> Result<HandshakeSignatureValid, rustls::Error> {
        rustls::crypto::verify_tls13_signature(m, c, d, &self.provider.signature_verification_algorithms)
    }
    fn supported_verify_schemes(&self) -> Vec<SignatureScheme> {
        self.provider.signature_verification_algorithms.supported_schemes()
    }
}

pub struct Client {
    base: String,
    token: Option<String>,
    agent: ureq::Agent,
}

fn transport(reason: &str, cid: &str, sent: bool, mismatch: bool) -> Value {
    let (code, what, pending, details) = if mismatch {
        ("CORE-CERT-MISMATCH", "The server answered with an identity different from the expected one.",
         "Nothing was sent to the server.", "Certificate fingerprint does not match.".to_string())
    } else {
        ("CORE-UNREACHABLE", "Could not talk to the team server.",
         if sent { "If the action had already been sent, its result is unknown." } else { "Nothing was sent to the server." },
         format!("{reason}. No answer does not prove a server failure."))
    };
    json!({"diagnostic": {
        "schema": "redrise.diagnostic/1", "error_code": code, "category": "communication", "what_happened": what,
        "completed": "The connection did not complete or there was no answer in time.", "pending": pending,
        "effect_state": if sent && !mismatch { "unknown" } else { "none" },
        "next_action": if mismatch { "Ask the administrator for a new team connection code." }
                       else { "Check that the server computer is on and on the same network; refresh the screen before repeating." },
        "retry": if mismatch { "not_useful" } else { "check_first" }, "details_summary": details, "reported_by": "RR-UI",
        "module_hints": ["RR-CORE", "RR-UI"], "diagnosis_status": "unconfirmed", "boundary": null, "correlation_id": cid,
        "version": {"desktop": env!("CARGO_PKG_VERSION")}, "technical_details": {"reason": reason}, "cause": null, "params": {"reason": reason}}})
}

impl Client {
    fn new(host: &str, port: u64, fp: &str, token: Option<String>) -> Result<Self, String> {
        let provider = Arc::new(rustls::crypto::ring::default_provider());
        let cfg = rustls::ClientConfig::builder_with_provider(provider.clone())
            .with_safe_default_protocol_versions().map_err(|e| e.to_string())?
            .dangerous().with_custom_certificate_verifier(Arc::new(Pinned { fp: fp.to_lowercase(), provider }))
            .with_no_client_auth();
        let agent = ureq::AgentBuilder::new().tls_config(Arc::new(cfg)).timeout_connect(Duration::from_secs(5))
            .timeout(Duration::from_secs(30)).build();
        Ok(Self { base: format!("https://{host}:{port}"), token, agent })
    }

    pub fn from_connection(p: &Paths, token: Option<String>) -> Result<Self, String> {
        let c = p.connection().ok_or("station not connected")?;
        Self::new(c["host"].as_str().unwrap_or_default(), c["port"].as_u64().unwrap_or(0),
                  c["fingerprint"].as_str().unwrap_or_default(), token)
    }

    pub fn from_host(p: &Paths, token: Option<String>) -> Result<Self, String> {
        let h = p.host_config().ok_or("server not prepared")?;
        Self::new("127.0.0.1", h["lan_port"].as_u64().unwrap_or(0), h["fingerprint"].as_str().unwrap_or_default(), token)
    }

    pub fn call(&self, method: &str, path: &str, body: &Value) -> Result<Value, Value> {
        let cid = crate::local::short_id();
        let mut req = self.agent.request(method, &format!("{}{}", self.base, path)).set("X-Correlation-Id", &cid);
        if let Some(t) = &self.token {
            req = req.set("Authorization", &format!("Bearer {t}"));
        }
        let sent = method != "GET";
        let res = if method == "GET" { req.call() } else { req.send_json(body.clone()) };
        match res {
            Ok(r) => r.into_json::<Value>().map_err(|e| transport(&format!("unreadable response: {e}"), &cid, sent, false)),
            Err(ureq::Error::Status(_, r)) => match r.into_json::<Value>() {
                Ok(v) if v.get("diagnostic").is_some() => Err(v),
                _ => Err(transport("error response without a diagnostic", &cid, sent, false)),
            },
            Err(ureq::Error::Transport(t)) => {
                let s = t.to_string();
                Err(transport(&s, &cid, sent && !s.contains("connect"), s.contains("fingerprint")))
            }
        }
    }
}
