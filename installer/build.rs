//! Embeds the Windows manifest of the installer (redrise-setup.manifest): asInvoker, Common Controls 6 for the
//! InstallRS wizard, per-monitor DPI. The uninstaller is the same stub, so it carries the same manifest.
fn main() {
    println!("cargo:rerun-if-changed=redrise-setup.manifest");
    if std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default() == "windows" {
        let mut res = winresource::WindowsResource::new();
        res.set_manifest_file("redrise-setup.manifest");
        res.set("ProductName", "RedRise");
        res.set("FileDescription", "Instalar RedRise");
        res.set("CompanyName", "Correnth");
        res.compile().expect("Windows resources of the installer");
    }
}
